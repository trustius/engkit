"""Declarative technology packs: local registry discovery and dependency resolution.

Packs are data only. Nothing in a pack is executed: detection rules are file
names and parsed keys, fragments are ``string.Template`` text with a fixed
placeholder set, and references are copied verbatim.
"""

from __future__ import annotations

import heapq
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from engkit.fsutil import UnsafePathError, is_within, safe_relpath, sha256_bytes
from engkit.profiles import (
    COMMAND_NAME_RE,
    COMMAND_STATUSES,
    EXACT_VERSION_RE,
    ID_RE,
    ITEM_ID_RE,
    PROFILE_SCHEMA_VERSION,
    STACK_CATEGORIES,
    Diagnostic,
    load_yaml_file,
)

PACK_SCHEMA_VERSION = 1
PACK_KEYS = {
    "schema_version", "kind", "id", "version", "description", "profile_schema", "applies_to",
    "dependencies", "conflicts", "incompatible_stack", "detect", "references", "fragments",
}
RULE_KEYS = {"files", "component", "parse", "key", "stack", "commands", "note"}
PARSERS = ("json", "yaml", "toml")
FRAGMENT_PLACEHOLDERS = {"component_id", "component_root", "pack_id", "pack_version", "project_name"}
PLACEHOLDER_RE = re.compile(r"\$(?:(\$)|([_a-z][_a-z0-9]*)|\{([_a-z][_a-z0-9]*)\}|())", re.IGNORECASE)
ARGV_PLACEHOLDERS = {"{package_manager}"}


@dataclass
class Pack:
    id: str
    version: str
    description: str
    origin: str  # "bundled" or project-relative ".engkit/packs/<id>"
    directory: Path
    data: dict
    content_hash: str = ""
    errors: list[Diagnostic] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def dependencies(self) -> list[tuple[str, str]]:
        return [(d["id"], d["version"]) for d in self.data.get("dependencies", []) or []]

    @property
    def detect(self) -> list[dict]:
        return self.data.get("detect", []) or []

    @property
    def references(self) -> list[str]:
        return self.data.get("references", []) or []

    @property
    def fragments(self) -> list[str]:
        return self.data.get("fragments", []) or []

    @property
    def applies_to(self) -> list[str]:
        return (self.data.get("applies_to") or {}).get("stack", []) or []


@dataclass
class Registry:
    packs: dict[str, Pack] = field(default_factory=dict)
    duplicates: dict[str, list[str]] = field(default_factory=dict)  # id -> manifest locations
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def valid_packs(self) -> list[Pack]:
        return [p for _, p in sorted(self.packs.items()) if p.valid]


def project_packs_dir(project_root: Path) -> Path:
    return project_root / ".engkit" / "packs"


def discover(bundled_root: Path, project_root: Path | None) -> Registry:
    """Discover bundled and project-local packs. Never overrides one source with the other."""
    reg = Registry()
    found: list[Pack] = []
    sources = [(bundled_root / "packs", "bundled", bundled_root / "packs")]
    if project_root is not None:
        pdir = project_packs_dir(project_root)
        if os.path.islink(pdir) or os.path.islink(pdir.parent):
            reg.diagnostics.append(Diagnostic("error", "unsafe-path", "project pack directory must not be a symlink", ".engkit/packs"))
        elif pdir.is_dir():
            sources.append((pdir, "project", project_root))
    for base, kind, rel_base in sources:
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if entry.name.startswith("."):
                continue
            label = "bundled" if kind == "bundled" else entry.relative_to(rel_base).as_posix()
            if entry.is_symlink():
                reg.diagnostics.append(Diagnostic("error", "unsafe-path", "pack directory must not be a symlink", label))
                continue
            if not entry.is_dir():
                continue
            found.append(load_pack(entry, label))
    by_id: dict[str, list[Pack]] = {}
    for p in found:
        by_id.setdefault(p.id or p.directory.name, []).append(p)
    for pid, group in sorted(by_id.items()):
        if len(group) > 1:
            locs = [_location(p) for p in group]
            reg.duplicates[pid] = locs
            reg.diagnostics.append(Diagnostic(
                "error", "duplicate-pack-id",
                f"pack id '{pid}' is defined more than once: {', '.join(locs)}; use a distinct id for a custom pack", locs[-1]))
            continue
        pack = group[0]
        reg.packs[pid] = pack
        reg.diagnostics.extend(pack.errors)
    return reg


def _location(p: Pack) -> str:
    return f"{p.origin}/pack.yaml" if p.origin != "bundled" else f"bundled:packs/{p.directory.name}/pack.yaml"


def load_pack(directory: Path, origin: str) -> Pack:
    manifest = directory / "pack.yaml"
    loc = f"{origin}/pack.yaml" if origin != "bundled" else f"bundled:packs/{directory.name}/pack.yaml"
    pack = Pack(id=directory.name, version="", description="", origin=origin, directory=directory, data={})
    if manifest.is_symlink() or not manifest.is_file():
        pack.errors.append(Diagnostic("error", "missing-manifest", "missing pack.yaml (or it is a symlink)", loc))
        return pack
    data, diags = load_yaml_file(manifest)
    if diags:
        pack.errors.extend(diags)
        return pack
    pack.errors.extend(validate_pack(data, directory, loc))
    if isinstance(data, dict):
        pack.data = data
        pack.id = data.get("id") if isinstance(data.get("id"), str) else directory.name
        pack.version = data.get("version") if isinstance(data.get("version"), str) else ""
        pack.description = data.get("description") if isinstance(data.get("description"), str) else ""
    if not pack.errors:
        pack.content_hash = _pack_hash(directory, pack)
    return pack


def _pack_hash(directory: Path, pack: Pack) -> str:
    parts = []
    for rel in ["pack.yaml", *pack.references, *pack.fragments]:
        parts.append(rel.encode() + b"\0" + (directory / rel).read_bytes())
    return sha256_bytes(b"\0\0".join(parts))


def validate_pack(data: object, directory: Path, loc: str) -> list[Diagnostic]:
    errs: list[Diagnostic] = []

    def err(code, msg):
        errs.append(Diagnostic("error", code, msg, loc))

    if not isinstance(data, dict):
        err("type", "pack manifest must be a mapping")
        return errs
    for k in sorted(set(data) - PACK_KEYS, key=str):
        err("unknown-field", f"unknown field '{k}'")
    if data.get("schema_version") != PACK_SCHEMA_VERSION:
        err("schema-version", f"unsupported pack schema_version {data.get('schema_version')!r} (supported: {PACK_SCHEMA_VERSION})")
    if data.get("kind") != "pack":
        err("kind", "kind must be 'pack'")
    pid = data.get("id")
    if not isinstance(pid, str) or not ID_RE.match(pid):
        err("invalid-id", "id must use lower-case letters, digits and hyphens")
    elif pid != directory.name:
        err("id-mismatch", f"id '{pid}' does not match directory '{directory.name}'")
    if not isinstance(data.get("version"), str) or not EXACT_VERSION_RE.match(data["version"]):
        err("version-syntax", "version must be exact MAJOR.MINOR.PATCH")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        err("required", "description is required")
    ps = data.get("profile_schema")
    if not isinstance(ps, dict) or not all(isinstance(ps.get(k), int) for k in ("min", "max")):
        err("required", "profile_schema must be {min: int, max: int}")
    elif not ps["min"] <= PROFILE_SCHEMA_VERSION <= ps["max"]:
        err("schema-incompatible", f"pack supports profile schema {ps['min']}..{ps['max']}, engkit uses {PROFILE_SCHEMA_VERSION}")
    applies = data.get("applies_to", {})
    if not isinstance(applies, dict) or not _str_list(applies.get("stack", [])):
        err("type", "applies_to.stack must be a list of stack ids")
    for i, dep in enumerate(data.get("dependencies", []) or []):
        if not isinstance(dep, dict) or not isinstance(dep.get("id"), str) or not ID_RE.match(dep["id"]):
            err("invalid-dependency", f"dependencies[{i}] must be {{id, version}}")
        elif not isinstance(dep.get("version"), str) or not EXACT_VERSION_RE.match(dep["version"]):
            err("version-syntax", f"dependency '{dep['id']}' must pin an exact MAJOR.MINOR.PATCH version")
    if not _str_list(data.get("conflicts", []) or []):
        err("type", "conflicts must be a list of pack ids")
    if not _str_list(data.get("incompatible_stack", []) or []):
        err("type", "incompatible_stack must be a list of stack ids")
    for i, rule in enumerate(data.get("detect", []) or []):
        for msg in _validate_rule(rule):
            err("invalid-rule", f"detect[{i}]: {msg}")
    for key in ("references", "fragments"):
        items = data.get(key, []) or []
        if not _str_list(items):
            err("type", f"{key} must be a list of relative paths")
            continue
        for rel in items:
            msg = _check_contained(directory, rel)
            if msg:
                err("unsafe-path" if "escape" in msg or "relative" in msg else "missing-file", f"{key}: {msg}")
            elif key == "fragments":
                try:
                    tmsg = check_template((directory / rel).read_text(encoding="utf-8"), FRAGMENT_PLACEHOLDERS)
                except (OSError, UnicodeDecodeError) as exc:
                    tmsg = f"cannot read as UTF-8 text ({exc.__class__.__name__})"
                if tmsg:
                    err("invalid-template", f"fragment '{rel}': {tmsg}")
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if p.is_symlink() and not is_within(Path(os.path.realpath(p)), directory.resolve()):
                err("unsafe-path", f"symlink escapes pack directory: {p.relative_to(directory)}")
    return errs


def _str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _check_contained(directory: Path, rel: str) -> str | None:
    try:
        safe_relpath(rel, "path")
    except UnsafePathError as exc:
        return str(exc)
    p = directory / rel
    if not is_within(Path(os.path.realpath(p)), directory.resolve()):
        return f"'{rel}' escapes the pack directory"
    if p.is_symlink() or not p.is_file():
        return f"'{rel}' is missing or not a regular file"
    return None


def _validate_rule(rule) -> list[str]:
    if not isinstance(rule, dict):
        return ["rule must be a mapping"]
    out = [f"unknown field '{k}'" for k in sorted(set(rule) - RULE_KEYS, key=str)]
    files = rule.get("files")
    if not _str_list(files) or not files:
        out.append("files must be a non-empty list of relative file paths")
    else:
        for f in files:
            try:
                safe_relpath(f, "file")
            except UnsafePathError as exc:
                out.append(str(exc))
            if any(ch in f for ch in "*?["):
                out.append(f"'{f}': glob patterns are not supported")
    if "component" in rule and not isinstance(rule["component"], bool):
        out.append("component must be true/false")
    if "parse" in rule and rule["parse"] not in PARSERS:
        out.append(f"parse must be one of {list(PARSERS)}")
    if "key" in rule and ("parse" not in rule or not isinstance(rule["key"], str)):
        out.append("key requires parse and must be a dotted string")
    stack = rule.get("stack", {}) or {}
    if not isinstance(stack, dict):
        out.append("stack must be a mapping")
    else:
        for cat, items in stack.items():
            if cat not in STACK_CATEGORIES:
                out.append(f"unknown stack category '{cat}'")
            elif not _str_list(items) or not all(ITEM_ID_RE.match(x) for x in items):
                out.append(f"stack.{cat} must be a list of lower-case ids")
    cmds = rule.get("commands", {}) or {}
    if not isinstance(cmds, dict):
        out.append("commands must be a mapping")
    else:
        for name, cmd in cmds.items():
            if not isinstance(name, str) or not COMMAND_NAME_RE.match(name):
                out.append(f"invalid command name {name!r}")
            elif not isinstance(cmd, dict) or not _str_list(cmd.get("argv")) or not cmd["argv"]:
                out.append(f"command '{name}' needs a non-empty argv list")
            elif cmd.get("status", "inferred") not in COMMAND_STATUSES:
                out.append(f"command '{name}' has invalid status")
            else:
                for a in cmd["argv"]:
                    if "{" in a and a not in ARGV_PLACEHOLDERS:
                        out.append(f"command '{name}' uses unsupported placeholder in {a!r}")
    return out


def check_template(text: str, allowed: set[str]) -> str | None:
    bad = []
    for m in PLACEHOLDER_RE.finditer(text):
        escaped, named, braced, invalid = m.groups()
        if escaped:
            continue
        if invalid is not None:
            return f"invalid '$' at offset {m.start()} (use $$ for a literal dollar)"
        name = named or braced
        if name not in allowed:
            bad.append(name)
    if bad:
        return f"unknown placeholders {sorted(set(bad))} (allowed: {sorted(allowed)})"
    return None


# --- resolution --------------------------------------------------------------

@dataclass
class Resolution:
    packs: list[Pack] = field(default_factory=list)  # dependencies before dependents, id tie-break
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(d.level == "error" for d in self.diagnostics)


def resolve(registry: Registry, requested: list[tuple[str, str | None]], context: str = "") -> Resolution:
    """Resolve requested packs and their exact-version dependencies from the local registry."""
    res = Resolution()

    def error(code, msg):
        res.diagnostics.append(Diagnostic("error", code, msg, context))

    selected: dict[str, Pack] = {}
    edges: dict[str, set[str]] = {}
    stack = [(pid, ver, "profile") for pid, ver in sorted(requested, key=lambda x: x[0])]
    while stack:
        pid, ver, by = stack.pop()
        if pid in registry.duplicates:
            error("duplicate-pack-id", f"pack '{pid}' (required by {by}) is ambiguous: defined at {', '.join(registry.duplicates[pid])}")
            continue
        pack = registry.packs.get(pid)
        if pack is None:
            error("missing-pack", f"pack '{pid}' required by {by} was not found in bundled packs or .engkit/packs/{pid}/pack.yaml")
            continue
        if not pack.valid:
            error("invalid-pack", f"pack '{pid}' required by {by} is invalid: " + "; ".join(d.message for d in pack.errors))
            continue
        if ver is not None and ver != pack.version:
            error("version-mismatch", f"{by} requires {pid}@{ver} but the registry has {pid}@{pack.version} ({pack.origin})")
            continue
        if pid in selected:
            continue
        selected[pid] = pack
        edges[pid] = set()
        for dep_id, dep_ver in pack.dependencies:
            edges[pid].add(dep_id)
            stack.append((dep_id, dep_ver, f"{pid}@{pack.version}"))
    for pid, pack in sorted(selected.items()):
        for other in pack.data.get("conflicts", []) or []:
            if other in selected:
                error("pack-conflict", f"pack '{pid}' declares a conflict with selected pack '{other}'")
    if not res.ok:
        return res
    # Kahn's algorithm: dependencies first, lexical tie-break.
    indeg = {pid: len([d for d in deps if d in selected]) for pid, deps in edges.items()}
    dependents: dict[str, list[str]] = {pid: [] for pid in selected}
    for pid, deps in edges.items():
        for d in deps:
            dependents[d].append(pid)
    heap = [pid for pid, n in indeg.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        pid = heapq.heappop(heap)
        order.append(pid)
        for nxt in dependents[pid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(heap, nxt)
    if len(order) != len(selected):
        cyc = sorted(set(selected) - set(order))
        error("dependency-cycle", f"pack dependency cycle among: {', '.join(cyc)}")
        return res
    res.packs = [selected[p] for p in order]
    return res
