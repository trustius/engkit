"""Versioned project-profile and stack-definition contracts, validation and merging.

Pure functions over parsed data: nothing here writes files or runs commands.
The JSON Schema documents in ``schemas/`` describe the same contract for
editors; this module is the authoritative validator (see docs/profiles.md).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from engkit.fsutil import UnsafePathError, safe_relpath

PROFILE_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1,)

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ITEM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.+_-]*$")
COMMAND_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_CONSTRAINT = r"(?:==|!=|>=|<=|~=|[<>^~=])?\s*[0-9][0-9A-Za-z.*+-]*"
VERSION_CONSTRAINT_RE = re.compile(rf"^{_CONSTRAINT}(?:\s*,\s*{_CONSTRAINT})*$")
EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

STACK_CATEGORIES = ("languages", "runtimes", "frameworks", "datastores", "build_tools", "package_managers", "tools")
COMMAND_STATUSES = ("unknown", "documented", "inferred", "verified", "ambiguous")
CONFIDENCE = ("confirmed", "inferred", "unknown")
MODES = ("existing", "new")

PROFILE_KEYS = {"schema_version", "project", "defaults", "components", "overrides"}
PROJECT_KEYS = {"name", "mode", "description", "constraints"}
DEFAULTS_KEYS = {"commands", "conventions", "packs"}
COMPONENT_KEYS = {"id", "root", "description", "stack", "commands", "conventions", "packs", "evidence", "unresolved"}
COMMAND_KEYS = {"argv", "cwd", "status", "source", "description"}
CONVENTION_KEYS = {"references", "notes"}
EVIDENCE_KEYS = {"source", "field", "value", "confidence"}
STACK_DEF_KEYS = {"schema_version", "kind", "id", "description", "project", "defaults", "components"}

# Merge rules (docs/profiles.md): scalars override, mappings merge recursively,
# lists are replaced -- except fields declared here.
KEYED_LISTS = {"components": "id"}  # merged item-by-item using this key
UNION_LISTS = {"evidence"}  # conflicting evidence is retained, deduplicated

LAYERS = ("detected", "defaults", "explicit", "override")


@dataclass
class Diagnostic:
    level: str  # error | warning | info
    code: str
    message: str
    location: str = ""
    component: str = ""

    def as_dict(self) -> dict:
        d = {"level": self.level, "code": self.code, "message": self.message}
        if self.location:
            d["location"] = self.location
        if self.component:
            d["component"] = self.component
        return d

    def format(self, with_level: bool = True) -> str:
        where = f"{self.location}: " if self.location else ""
        comp = f"[{self.component}] " if self.component else ""
        text = f"{where}{comp}{self.message} ({self.code})"
        return f"{self.level}: {text}" if with_level else text


def has_errors(diags: list[Diagnostic]) -> bool:
    return any(d.level == "error" for d in diags)


# --- loading -----------------------------------------------------------------

def load_yaml_file(path: Path) -> tuple[object, list[Diagnostic]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, [Diagnostic("error", "not-found", "file not found", str(path))]
    except (OSError, UnicodeDecodeError) as exc:
        return None, [Diagnostic("error", "unreadable", f"cannot read file: {exc}", str(path))]
    return parse_yaml(text, str(path))


def parse_yaml(text: str, location: str) -> tuple[object, list[Diagnostic]]:
    try:
        return yaml.safe_load(text), []
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"{location}:{mark.line + 1}" if mark else location
        return None, [Diagnostic("error", "malformed-yaml", f"malformed YAML: {getattr(exc, 'problem', exc)}", where)]


# --- validation --------------------------------------------------------------

class _V:
    def __init__(self, location: str):
        self.location = location
        self.diags: list[Diagnostic] = []

    def err(self, code: str, msg: str, path: str, component: str = "") -> None:
        self.diags.append(Diagnostic("error", code, msg, f"{self.location}#{path}" if path else self.location, component))

    def warn(self, code: str, msg: str, path: str, component: str = "") -> None:
        self.diags.append(Diagnostic("warning", code, msg, f"{self.location}#{path}" if path else self.location, component))

    def keys(self, obj: dict, allowed: set, path: str) -> None:
        for k in sorted(set(obj) - allowed, key=str):
            self.err("unknown-field", f"unknown field '{k}'", f"{path}.{k}" if path else str(k))

    def mapping(self, obj, path: str) -> bool:
        if not isinstance(obj, dict):
            self.err("type", "expected a mapping", path)
            return False
        return True

    def str_list(self, obj, path: str) -> bool:
        if not isinstance(obj, list) or not all(isinstance(x, str) for x in obj):
            self.err("type", "expected a list of strings", path)
            return False
        return True


def _check_schema_version(v: _V, data: dict) -> bool:
    sv = data.get("schema_version")
    if sv is None:
        v.err("schema-version", "missing schema_version", "schema_version")
        return False
    if not isinstance(sv, int) or isinstance(sv, bool):
        v.err("schema-version", "schema_version must be an integer", "schema_version")
        return False
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        v.err("schema-version", f"unsupported schema_version {sv} (supported: {list(SUPPORTED_SCHEMA_VERSIONS)})", "schema_version")
        return False
    return True


def validate_profile(data: object, location: str = ".engkit/project.yaml") -> list[Diagnostic]:
    v = _V(location)
    if not v.mapping(data, ""):
        return v.diags
    v.keys(data, PROFILE_KEYS, "")
    if not _check_schema_version(v, data):
        return v.diags
    project = data.get("project")
    if project is None:
        v.err("required", "missing 'project'", "project")
    else:
        _validate_project(v, project, "project")
    if "defaults" in data:
        _validate_defaults(v, data["defaults"], "defaults")
    comps = data.get("components", [])
    ids = _validate_components(v, comps, "components", partial=False)
    overrides = data.get("overrides", {})
    if overrides is None:
        overrides = {}
    if v.mapping(overrides, "overrides"):
        for cid, ov in overrides.items():
            if not isinstance(cid, str) or not ID_RE.match(cid):
                v.err("invalid-id", f"override key {cid!r} is not a valid component id", f"overrides.{cid}")
                continue
            if ids is not None and cid not in ids:
                v.warn("override-unknown-component",
                       f"override for '{cid}' does not match an explicit component; it applies only if detection finds it",
                       f"overrides.{cid}")
            _validate_component(v, ov, f"overrides.{cid}", partial=True)
    return v.diags


def validate_stack_definition(data: object, location: str) -> list[Diagnostic]:
    v = _V(location)
    if not v.mapping(data, ""):
        return v.diags
    v.keys(data, STACK_DEF_KEYS, "")
    if not _check_schema_version(v, data):
        return v.diags
    if data.get("kind") != "stack":
        v.err("kind", "kind must be 'stack'", "kind")
    sid = data.get("id")
    if not isinstance(sid, str) or not ID_RE.match(sid):
        v.err("invalid-id", "id must use lower-case letters, digits and hyphens", "id")
    if "description" in data and not isinstance(data["description"], str):
        v.err("type", "description must be a string", "description")
    if "project" in data:
        project = data["project"]
        if v.mapping(project, "project"):
            v.keys(project, PROJECT_KEYS - {"name"}, "project")
            _validate_project(v, {k: x for k, x in project.items() if k != "name"} | {"name": "x"}, "project")
    if "defaults" in data:
        _validate_defaults(v, data["defaults"], "defaults")
    comps = data.get("components")
    if not comps:
        v.err("required", "a stack definition needs at least one component", "components")
    else:
        _validate_components(v, comps, "components", partial=False)
    return v.diags


def _validate_project(v: _V, project, path: str) -> None:
    if not v.mapping(project, path):
        return
    v.keys(project, PROJECT_KEYS, path)
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        v.err("required", "project.name must be a non-empty string", f"{path}.name")
    mode = project.get("mode", "existing")
    if mode not in MODES:
        v.err("enum", f"project.mode must be one of {list(MODES)}", f"{path}.mode")
    if "description" in project and not isinstance(project["description"], str):
        v.err("type", "description must be a string", f"{path}.description")
    constraints = project.get("constraints", {})
    if constraints is not None and v.mapping(constraints, f"{path}.constraints"):
        for k, val in constraints.items():
            if not isinstance(k, str):
                v.err("type", "constraint keys must be strings", f"{path}.constraints")
            elif not _is_plain(val):
                v.err("type", "constraint values must be scalars or lists of scalars", f"{path}.constraints.{k}")


def _is_plain(val) -> bool:
    scalar = (str, int, float, bool, type(None))
    return isinstance(val, scalar) or (isinstance(val, list) and all(isinstance(x, scalar) for x in val))


def _validate_defaults(v: _V, defaults, path: str) -> None:
    if defaults is None or not v.mapping(defaults, path):
        return
    v.keys(defaults, DEFAULTS_KEYS, path)
    if "commands" in defaults:
        _validate_commands(v, defaults["commands"], f"{path}.commands", "", allow_no_cwd=True)
    if "conventions" in defaults:
        _validate_conventions(v, defaults["conventions"], f"{path}.conventions")
    if "packs" in defaults:
        _validate_pack_refs(v, defaults["packs"], f"{path}.packs")


def _validate_components(v: _V, comps, path: str, partial: bool) -> set | None:
    if comps is None:
        return set()
    if not isinstance(comps, list):
        v.err("type", "components must be a list", path)
        return None
    ids: set = set()
    roots: dict = {}
    for idx, comp in enumerate(comps):
        cpath = f"{path}[{idx}]"
        _validate_component(v, comp, cpath, partial)
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id")
        if isinstance(cid, str):
            if cid in ids:
                v.err("duplicate-id", f"duplicate component id '{cid}'", f"{cpath}.id", cid)
            ids.add(cid)
        root = comp.get("root")
        if isinstance(root, str):
            if root in roots:
                v.err("duplicate-root", f"components '{roots[root]}' and '{cid}' share root '{root}'", f"{cpath}.root", str(cid))
            roots[root] = cid
    return ids


def _validate_component(v: _V, comp, path: str, partial: bool) -> None:
    if not v.mapping(comp, path):
        return
    v.keys(comp, COMPONENT_KEYS - ({"id"} if partial else set()), path)
    cid = comp.get("id", "")
    if not partial:
        if not isinstance(cid, str) or not ID_RE.match(cid):
            v.err("invalid-id", f"component id {cid!r} must use lower-case letters, digits and hyphens", f"{path}.id")
            cid = ""
        if "root" not in comp:
            v.err("required", "component root is required", f"{path}.root", cid)
    if "root" in comp:
        try:
            safe_relpath(comp["root"], "root")
        except UnsafePathError as exc:
            v.err("unsafe-path", str(exc), f"{path}.root", cid)
    if "description" in comp and not isinstance(comp["description"], str):
        v.err("type", "description must be a string", f"{path}.description", cid)
    if "stack" in comp:
        _validate_stack(v, comp["stack"], f"{path}.stack", cid)
    if "commands" in comp:
        _validate_commands(v, comp["commands"], f"{path}.commands", cid, allow_no_cwd=True)
    if "conventions" in comp:
        _validate_conventions(v, comp["conventions"], f"{path}.conventions")
    if "packs" in comp:
        _validate_pack_refs(v, comp["packs"], f"{path}.packs")
    if "evidence" in comp:
        ev = comp["evidence"]
        if not isinstance(ev, list):
            v.err("type", "evidence must be a list", f"{path}.evidence", cid)
        else:
            for i, e in enumerate(ev):
                epath = f"{path}.evidence[{i}]"
                if not v.mapping(e, epath):
                    continue
                v.keys(e, EVIDENCE_KEYS, epath)
                if not isinstance(e.get("source"), str):
                    v.err("required", "evidence.source must be a relative path string", epath, cid)
                else:
                    try:
                        safe_relpath(e["source"], "evidence source")
                    except UnsafePathError as exc:
                        v.err("unsafe-path", str(exc), epath, cid)
                if e.get("confidence", "unknown") not in CONFIDENCE:
                    v.err("enum", f"confidence must be one of {list(CONFIDENCE)}", epath, cid)
    if "unresolved" in comp:
        v.str_list(comp["unresolved"], f"{path}.unresolved")


def _validate_stack(v: _V, stack, path: str, cid: str) -> None:
    if not v.mapping(stack, path):
        return
    v.keys(stack, set(STACK_CATEGORIES), path)
    for cat, items in stack.items():
        if cat not in STACK_CATEGORIES:
            continue
        if items is None:
            continue
        if not isinstance(items, list):
            v.err("type", f"{cat} must be a list", f"{path}.{cat}", cid)
            continue
        seen = set()
        for i, item in enumerate(items):
            ipath = f"{path}.{cat}[{i}]"
            iid, ver = stack_item(item)
            if iid is None:
                v.err("type", "stack item must be an id string or {id, version}", ipath, cid)
                continue
            if isinstance(item, dict):
                v.keys(item, {"id", "version"}, ipath)
            if not ITEM_ID_RE.match(iid):
                v.err("invalid-id", f"stack id {iid!r} must be lower-case (letters, digits, . + _ -)", ipath, cid)
            if ver is not None and (not isinstance(ver, str) or not VERSION_CONSTRAINT_RE.match(ver)):
                v.err("version-syntax", f"invalid version constraint {ver!r}", ipath, cid)
            if iid in seen:
                v.err("duplicate-entry", f"duplicate {cat} entry '{iid}'", ipath, cid)
            seen.add(iid)


def stack_item(item) -> tuple[str | None, object]:
    if isinstance(item, str):
        return item, None
    if isinstance(item, dict) and isinstance(item.get("id"), str):
        return item["id"], item.get("version")
    return None, None


def _validate_commands(v: _V, commands, path: str, cid: str, allow_no_cwd: bool) -> None:
    if not v.mapping(commands, path):
        return
    for name, cmd in commands.items():
        cpath = f"{path}.{name}"
        if not isinstance(name, str) or not COMMAND_NAME_RE.match(name):
            v.err("invalid-id", f"command name {name!r} is invalid", cpath, cid)
        if not v.mapping(cmd, cpath):
            continue
        v.keys(cmd, COMMAND_KEYS, cpath)
        argv = cmd.get("argv", [])
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            v.err("type", "argv must be a list of strings (commands are never run through a shell)", f"{cpath}.argv", cid)
        status = cmd.get("status", "unknown")
        if status not in COMMAND_STATUSES:
            v.err("enum", f"status must be one of {list(COMMAND_STATUSES)}", f"{cpath}.status", cid)
        elif isinstance(argv, list) and not argv and status not in ("unknown", "ambiguous"):
            v.err("required", f"status '{status}' requires a non-empty argv", f"{cpath}.argv", cid)
        if "cwd" in cmd:
            try:
                safe_relpath(cmd["cwd"], "cwd")
            except UnsafePathError as exc:
                v.err("unsafe-path", str(exc), f"{cpath}.cwd", cid)
        elif not allow_no_cwd:
            v.err("required", "cwd is required", f"{cpath}.cwd", cid)
        if "source" in cmd and not isinstance(cmd["source"], str):
            v.err("type", "source must be a string", f"{cpath}.source", cid)


def _validate_conventions(v: _V, conv, path: str) -> None:
    if not v.mapping(conv, path):
        return
    v.keys(conv, CONVENTION_KEYS, path)
    if "references" in conv and v.str_list(conv["references"], f"{path}.references"):
        for i, ref in enumerate(conv["references"]):
            try:
                safe_relpath(ref, "reference")
            except UnsafePathError as exc:
                v.err("unsafe-path", str(exc), f"{path}.references[{i}]")
    if "notes" in conv:
        v.str_list(conv["notes"], f"{path}.notes")


def pack_ref(item) -> tuple[str | None, str | None]:
    if isinstance(item, str):
        return item, None
    if isinstance(item, dict) and isinstance(item.get("id"), str):
        ver = item.get("version")
        return item["id"], ver if isinstance(ver, str) else None
    return None, None


def _validate_pack_refs(v: _V, packs, path: str) -> None:
    if not isinstance(packs, list):
        v.err("type", "packs must be a list", path)
        return
    seen = set()
    for i, item in enumerate(packs):
        pid, ver = pack_ref(item)
        ipath = f"{path}[{i}]"
        if pid is None or not ID_RE.match(pid):
            v.err("invalid-id", "pack entry must be an id or {id, version}", ipath)
            continue
        if isinstance(item, dict):
            v.keys(item, {"id", "version"}, ipath)
            if "version" in item and (not isinstance(item["version"], str) or not EXACT_VERSION_RE.match(item["version"])):
                v.err("version-syntax", "pack version pins must be exact (MAJOR.MINOR.PATCH)", ipath)
        if pid in seen:
            v.err("duplicate-entry", f"duplicate pack '{pid}'", ipath)
        seen.add(pid)


# --- normalization and merging ----------------------------------------------

def empty_component(cid: str, root: str) -> dict:
    return {
        "id": cid,
        "root": root,
        "stack": {c: [] for c in STACK_CATEGORIES},
        "commands": {},
        "conventions": {"references": [], "notes": []},
        "packs": [],
        "evidence": [],
        "unresolved": [],
    }


def merge(base, overlay, *, key: str = "", provenance: dict | None = None, layer: str = "", prefix: str = ""):
    """Merge ``overlay`` onto ``base`` (neither is modified) using the declared rules."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = copy.deepcopy(base)
        for k, val in overlay.items():
            child = f"{prefix}.{k}" if prefix else str(k)
            if k in out:
                out[k] = merge(out[k], val, key=k, provenance=provenance, layer=layer, prefix=child)
            else:
                out[k] = copy.deepcopy(val)
                _mark(provenance, child, layer, val)
        return out
    if isinstance(base, list) and isinstance(overlay, list):
        if key in KEYED_LISTS:
            return _merge_keyed(base, overlay, KEYED_LISTS[key], provenance, layer, prefix)
        if key in UNION_LISTS:
            out = copy.deepcopy(base)
            for item in overlay:
                if item not in out:
                    out.append(copy.deepcopy(item))
            return out
    _mark(provenance, prefix, layer, overlay)
    return copy.deepcopy(overlay)


def _mark(provenance, path, layer, value) -> None:
    if provenance is None or not layer:
        return
    if isinstance(value, dict) and value:
        for k, v in value.items():
            _mark(provenance, f"{path}.{k}", layer, v)
    else:
        provenance[path] = layer


def _merge_keyed(base: list, overlay: list, key: str, provenance, layer, prefix) -> list:
    out = [copy.deepcopy(x) for x in base]
    index = {x.get(key): i for i, x in enumerate(out) if isinstance(x, dict)}
    for item in overlay:
        k = item.get(key) if isinstance(item, dict) else None
        if k in index:
            out[index[k]] = merge(out[index[k]], item, provenance=provenance, layer=layer, prefix=f"{prefix}[{k}]")
        else:
            index[k] = len(out)
            out.append(copy.deepcopy(item))
            _mark(provenance, f"{prefix}[{k}]", layer, item)
    return out


def canonical_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True, width=1000)
