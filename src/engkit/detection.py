"""Bounded, read-only project detection driven by declarative pack rules.

Manifests are parsed as data (json / yaml / toml); nothing is executed and
nothing is written. Absent evidence means "unknown", never "absent".
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engkit.fsutil import sha256_file
from engkit.packs import Registry
from engkit.profiles import STACK_CATEGORIES, Diagnostic, empty_component

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - depends on runtime
    tomllib = None

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".engkit", ".claude", ".agents", ".codex", ".idea", ".vscode",
    "node_modules", "bower_components", "vendor", "third_party", "target", "build", "dist", "out",
    ".venv", "venv", "env", "__pycache__", ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".gradle", ".next", ".nuxt", ".cache", ".terraform", "coverage", "bin", "obj", ".dart_tool", "Pods",
}
MAX_DEPTH = 8
MAX_DIRS = 5000
MAX_PARSE_BYTES = 1024 * 1024
VALUE_MAX = 120


@dataclass
class Detection:
    project_name: str
    components: list[dict] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)  # relevant input path -> sha256
    diagnostics: list[Diagnostic] = field(default_factory=list)
    truncated: bool = False
    # component id -> command -> (argv template, status, source) for commands that
    # depend on a package manager detection could not determine. Resolution fills
    # them in when the profile declares exactly one package manager.
    templates: dict[str, dict[str, tuple[list[str], str, str]]] = field(default_factory=dict)

    def as_profile(self) -> dict:
        return {
            "schema_version": 1,
            "project": {"name": self.project_name, "mode": "existing"},
            "components": self.components,
        }


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "project"


def walk(root: Path, diagnostics: list[Diagnostic]) -> tuple[list[str], bool]:
    """Return sorted relative directories (``"."`` first) within bounds."""
    dirs: list[str] = []
    truncated = False
    queue = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        rel = "." if current == root else current.relative_to(root).as_posix()
        dirs.append(rel)
        if len(dirs) >= MAX_DIRS:
            truncated = True
            diagnostics.append(Diagnostic("warning", "detection-truncated", f"stopped after {MAX_DIRS} directories; results may be incomplete"))
            break
        if depth >= MAX_DEPTH:
            continue
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError as exc:
            diagnostics.append(Diagnostic("warning", "unreadable", f"cannot list directory: {exc.strerror}", rel))
            continue
        for e in entries:
            if e.name in SKIP_DIRS or e.is_symlink():
                continue  # never follow symlinks during detection
            if e.is_dir(follow_symlinks=False):
                queue.append((Path(e.path), depth + 1))
    return sorted(dirs, key=lambda d: (d != ".", d)), truncated


def _regular_file(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)


class _Parsed:
    def __init__(self):
        self.cache: dict[tuple[str, str], object] = {}

    def load(self, path: Path, kind: str, rel: str, diagnostics: list[Diagnostic]):
        key = (rel, kind)
        if key in self.cache:
            return self.cache[key]
        value = None
        try:
            if path.stat().st_size > MAX_PARSE_BYTES:
                diagnostics.append(Diagnostic("warning", "too-large", "file too large to parse; key rules skipped", rel))
            else:
                text = path.read_text(encoding="utf-8")
                if kind == "json":
                    value = json.loads(text)
                elif kind == "yaml":
                    value = yaml.safe_load(text)
                elif kind == "toml":
                    if tomllib is None:
                        diagnostics.append(Diagnostic("info", "parser-unavailable", "TOML parsing needs Python 3.11+; key rules skipped", rel))
                    else:
                        value = tomllib.loads(text)
        except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
            diagnostics.append(Diagnostic("warning", "parse-error", f"could not parse as {kind}: {str(exc).splitlines()[0][:200]}", rel))
        self.cache[key] = value
        return value


def _lookup(data, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _render_value(value) -> str:
    """Deterministic text for a parsed value; YAML/TOML dates or mixed-type keys are not JSON-native."""
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError, RecursionError):
        return str(value)


def _rule_matches(root: Path, rel_dir: str, rule: dict, parsed: _Parsed, det: Detection):
    """Return (matched_file_rel, field, value) or None."""
    for name in rule["files"]:
        rel = name if rel_dir == "." else f"{rel_dir}/{name}"
        path = root / rel
        if not _regular_file(path):
            continue
        det.inputs[rel] = sha256_file(path)
        if "parse" not in rule:
            return rel, None, "present"
        data = parsed.load(path, rule["parse"], rel, det.diagnostics)
        if data is None:
            continue
        if "key" not in rule:
            return rel, None, f"parsed as {rule['parse']}"
        found, value = _lookup(data, rule["key"])
        if found:
            text = value if isinstance(value, str) else _render_value(value)
            return rel, rule["key"], text[:VALUE_MAX]
    return None


def detect(project_root: Path, registry: Registry) -> Detection:
    root = project_root
    det = Detection(project_name=slug(root.name))
    dirs, det.truncated = walk(root, det.diagnostics)
    packs = registry.valid_packs()
    parsed = _Parsed()

    component_roots: list[str] = []
    for rel_dir in dirs:
        for pack in packs:
            if any(r.get("component") and _rule_matches(root, rel_dir, r, parsed, det) for r in pack.detect):
                component_roots.append(rel_dir)
                break

    used_ids: set[str] = set()
    for rel_dir in component_roots:
        cid = "root" if rel_dir == "." else slug(rel_dir)
        base, n = cid, 2
        while cid in used_ids:
            cid, n = f"{base}-{n}", n + 1
        used_ids.add(cid)
        det.components.append(_build_component(root, rel_dir, cid, packs, parsed, det))

    if not det.components:
        comp = empty_component("root", ".")
        comp["unresolved"] = ["No recognized manifests were found; define the stack manually (engkit project define)."]
        det.components.append(comp)
        det.diagnostics.append(Diagnostic("info", "unknown-stack",
                                          "no pack detection rule matched; using the generic fallback component 'root'"))
    return det


def _build_component(root: Path, rel_dir: str, cid: str, packs, parsed: _Parsed, det: Detection) -> dict:
    comp = empty_component(cid, rel_dir)
    candidates: dict[str, list[tuple[list[str], str, str]]] = {}  # command -> [(argv, status, source)]
    matched_packs: list[str] = []
    for pack in packs:
        for rule in pack.detect:
            m = _rule_matches(root, rel_dir, rule, parsed, det)
            if not m:
                continue
            src, fld, value = m
            if pack.id not in matched_packs:
                matched_packs.append(pack.id)
            ev = {"source": src, "field": fld, "value": value, "confidence": "confirmed"}
            if ev not in comp["evidence"]:
                comp["evidence"].append(ev)
            for cat, items in (rule.get("stack") or {}).items():
                for item in items:
                    if item not in comp["stack"][cat]:
                        comp["stack"][cat].append(item)
                        comp["evidence"].append({"source": src, "field": fld, "value": f"{cat}: {item} (pack {pack.id})",
                                                 "confidence": "inferred"})
            for name, cmd in (rule.get("commands") or {}).items():
                source = f"{src}#{fld}" if fld else src
                candidates.setdefault(name, []).append((list(cmd["argv"]), cmd.get("status", "inferred"), source))

    pms = comp["stack"]["package_managers"]
    if len(pms) > 1:
        det.diagnostics.append(Diagnostic(
            "warning", "ambiguous-package-manager",
            f"conflicting package-manager evidence ({', '.join(pms)}); not selecting one. Declare stack.package_managers explicitly.",
            rel_dir, cid))
    for name in sorted(candidates):
        resolved = []
        for argv, status, source in candidates[name]:
            if "{package_manager}" in argv:
                if len(pms) != 1:
                    det.diagnostics.append(Diagnostic(
                        "warning", "ambiguous-command",
                        f"command '{name}' depends on the package manager, which is {'ambiguous' if pms else 'unknown'}",
                        source, cid))
                    det.templates.setdefault(cid, {})[name] = (list(argv), status, source)
                    resolved.append(None)
                    continue
                argv = [pms[0] if a == "{package_manager}" else a for a in argv]
            resolved.append((argv, status, source))
        concrete = [r for r in resolved if r is not None]
        distinct = {tuple(r[0]) for r in concrete}
        if len(distinct) == 1 and len(concrete) == len(resolved):
            argv, status, source = concrete[0]
            comp["commands"][name] = {"argv": argv, "cwd": rel_dir, "status": status, "source": source}
        else:
            if len(distinct) > 1:
                det.diagnostics.append(Diagnostic(
                    "warning", "ambiguous-command",
                    f"command '{name}' has conflicting candidates: " + "; ".join(" ".join(a) for a in sorted(distinct)),
                    rel_dir, cid))
            comp["commands"][name] = {"argv": [], "cwd": rel_dir, "status": "ambiguous",
                                      "source": ", ".join(sorted({r[2] for r in candidates[name] if r}))}
    comp["packs"] = sorted(matched_packs)
    for cat in STACK_CATEGORIES:
        comp["stack"][cat] = sorted(comp["stack"][cat])
    return comp
