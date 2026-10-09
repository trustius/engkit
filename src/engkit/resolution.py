"""Resolve the effective project profile: detection + explicit profile + overrides.

Precedence (lowest to highest): detected < defaults < explicit component < overrides.
Explicit configuration always wins; contradictions with detected evidence stay
visible as diagnostics. Read-only: no writes, no command execution.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from engkit import detection, packs, profiles
from engkit.profiles import STACK_CATEGORIES, Diagnostic, empty_component, merge, stack_item

PROFILE_REL = ".engkit/project.yaml"


@dataclass
class Resolved:
    profile: dict
    provenance: dict[str, dict[str, str]]  # component id -> field path -> layer
    diagnostics: list[Diagnostic] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)
    explicit_present: bool = False

    @property
    def ok(self) -> bool:
        return not profiles.has_errors(self.diagnostics)


def load_explicit(project_root: Path) -> tuple[dict | None, list[Diagnostic]]:
    path = project_root / PROFILE_REL
    if not path.exists() and not path.is_symlink():
        return None, []
    if path.is_symlink():
        return None, [Diagnostic("error", "unsafe-path", "project profile must not be a symlink", PROFILE_REL)]
    data, diags = profiles.load_yaml_file(path)
    if diags:
        return None, [Diagnostic(d.level, d.code, d.message, d.location.replace(str(project_root) + "/", "")) for d in diags]
    diags = profiles.validate_profile(data, PROFILE_REL)
    return (data if not profiles.has_errors(diags) else None), diags


def resolve(detected: dict, explicit: dict | None, templates: dict | None = None) -> Resolved:
    """Pure merge of a detected profile with an optional explicit profile."""
    diags: list[Diagnostic] = []
    project = copy.deepcopy(detected.get("project", {}))
    if explicit:
        project = merge(project, explicit.get("project", {}))
    project.setdefault("constraints", {})
    project.setdefault("mode", "existing")

    defaults = (explicit or {}).get("defaults") or {}
    explicit_comps = [_drop_null_stack(ec) for ec in (explicit or {}).get("components") or []]
    overrides = {cid: _drop_null_stack(o) for cid, o in ((explicit or {}).get("overrides") or {}).items()}

    detected_comps = {c["id"]: c for c in detected.get("components", [])}
    # An explicit id that names a detected component at a different root would merge
    # data from two directories; refuse it rather than guess.
    for ec in explicit_comps:
        other = detected_comps.get(ec["id"])
        if other is not None and other["root"] != ec.get("root"):
            diags.append(Diagnostic("error", "component-id-conflict",
                                    f"explicit component '{ec['id']}' (root {ec.get('root')!r}) reuses the id of the "
                                    f"detected component at {other['root']!r}; choose another id or match its root",
                                    PROFILE_REL, ec["id"]))
    if diags:
        return Resolved(profile={"schema_version": profiles.PROFILE_SCHEMA_VERSION, "project": project, "components": []},
                        provenance={}, diagnostics=diags)
    # An explicit component with a different id but the same root absorbs the detected one.
    by_root = {c["root"]: c["id"] for c in detected.get("components", [])}
    renames = {}
    for ec in explicit_comps:
        did = by_root.get(ec.get("root"))
        if did and did != ec["id"] and did not in {e["id"] for e in explicit_comps}:
            renames[did] = ec["id"]
    # Explicit components replace the generic fallback rather than coexisting with it.
    if explicit_comps and set(detected_comps) == {"root"} and not detected_comps["root"]["evidence"] and "root" not in renames:
        if not any(ec["id"] == "root" for ec in explicit_comps):
            detected_comps = {}

    order: list[str] = []
    result: dict[str, dict] = {}
    provenance: dict[str, dict[str, str]] = {}
    for did, comp in detected_comps.items():
        cid = renames.get(did, did)
        prov: dict[str, str] = {}
        base = empty_component(cid, comp["root"])
        merged = merge(base, {**comp, "id": cid}, provenance=prov, layer="detected")
        result[cid], provenance[cid] = merged, prov
        order.append(cid)
    for ec in explicit_comps:
        cid = ec["id"]
        prov = provenance.setdefault(cid, {})
        if cid not in result:
            result[cid] = empty_component(cid, ec["root"])
            order.append(cid)
    for cid in order:
        prov = provenance[cid]
        comp = result[cid]
        if defaults:
            layer = {k: copy.deepcopy(defaults[k]) for k in ("commands", "conventions", "packs") if k in defaults}
            comp = merge(comp, layer, provenance=prov, layer="defaults")
        ec = next((e for e in explicit_comps if e["id"] == cid), None)
        if ec:
            comp = merge(comp, ec, provenance=prov, layer="explicit")
        if cid in overrides:
            comp = merge(comp, overrides[cid], provenance=prov, layer="override")
        result[cid] = comp
    for cid in sorted(set(overrides) - set(result)):
        diags.append(Diagnostic("warning", "override-unknown-component",
                                f"override for '{cid}' matches no detected or explicit component", PROFILE_REL, cid))

    inverse = {v: k for k, v in renames.items()}
    for cid in order:
        comp = result[cid]
        _apply_templates(comp, (templates or {}).get(inverse.get(cid, cid), {}), provenance[cid])
        _fill_command_cwd(comp)
        if cid in detected_comps or cid in renames.values():
            src = detected_comps.get(cid) or detected_comps[next(k for k, v in renames.items() if v == cid)]
            diags.extend(_contradictions(cid, src, comp, provenance[cid]))
        comp["unresolved"] = _derive_unresolved(comp)

    profile = {
        "schema_version": profiles.PROFILE_SCHEMA_VERSION,
        "project": project,
        "components": [result[c] for c in sorted(order)],
    }
    return Resolved(profile=profile, provenance=provenance, diagnostics=diags)


def _drop_null_stack(layer: dict) -> dict:
    """A null stack category (``languages:`` with no value) means "not specified", not "replace with nothing"."""
    stack = layer.get("stack")
    if not isinstance(stack, dict) or all(v is not None for v in stack.values()):
        return layer
    return {**layer, "stack": {k: v for k, v in stack.items() if v is not None}}


def _apply_templates(comp: dict, templates: dict, prov: dict) -> None:
    """Fill package-manager-dependent commands once the profile names exactly one package manager."""
    pms = [stack_item(x)[0] for x in comp["stack"].get("package_managers") or []]
    if len(pms) != 1:
        return
    for name, (argv, status, source) in templates.items():
        cmd = comp["commands"].get(name)
        if cmd is None or prov.get(f"commands.{name}.argv") != "detected" or cmd.get("status") != "ambiguous":
            continue
        cmd["argv"] = [pms[0] if a == "{package_manager}" else a for a in argv]
        cmd["status"] = status
        cmd["source"] = source
        prov[f"commands.{name}.argv"] = "detected+" + prov.get("stack.package_managers", "explicit")


def _fill_command_cwd(comp: dict) -> None:
    for cmd in comp["commands"].values():
        cmd.setdefault("cwd", comp["root"])
        cmd.setdefault("status", "unknown")
        cmd.setdefault("argv", [])


def _contradictions(cid: str, detected: dict, final: dict, prov: dict) -> list[Diagnostic]:
    out = []
    for cat in STACK_CATEGORIES:
        d_ids = sorted(stack_item(x)[0] for x in (detected.get("stack") or {}).get(cat, []))
        f_ids = sorted(stack_item(x)[0] for x in final["stack"].get(cat, []))
        layer = prov.get(f"stack.{cat}")
        if d_ids and d_ids != f_ids and layer in ("explicit", "override", "defaults"):
            out.append(Diagnostic("warning", "contradiction",
                                  f"{layer} stack.{cat} {f_ids} differs from detected {d_ids}; explicit value wins",
                                  PROFILE_REL, cid))
    for name, dcmd in (detected.get("commands") or {}).items():
        fcmd = final["commands"].get(name)
        if fcmd and dcmd.get("argv") and fcmd.get("argv") != dcmd.get("argv"):
            layer = prov.get(f"commands.{name}.argv", "explicit")
            out.append(Diagnostic("warning", "contradiction",
                                  f"{layer} command '{name}' {fcmd.get('argv')} differs from detected {dcmd['argv']} "
                                  f"(from {dcmd.get('source', 'detection')}); explicit value wins", PROFILE_REL, cid))
    return out


def _derive_unresolved(comp: dict) -> list[str]:
    notes = list(comp.get("unresolved") or [])

    def add(note):
        if note not in notes:
            notes.append(note)

    if not any(comp["stack"].get(c) for c in STACK_CATEGORIES):
        add("Stack is unknown; no evidence or explicit definition identifies it.")
    if len(comp["stack"].get("package_managers", [])) > 1:
        add("Package manager is ambiguous (" + ", ".join(stack_item(x)[0] for x in comp["stack"]["package_managers"]) + "); declare one explicitly.")
    test = comp["commands"].get("test")
    if not test or not test.get("argv"):
        state = (test or {}).get("status", "missing")
        add(f"Test command is {'ambiguous' if state == 'ambiguous' else 'unknown'}; obtain it from project documentation.")
    for name, cmd in sorted(comp["commands"].items()):
        if name != "test" and cmd.get("status") == "ambiguous":
            add(f"Command '{name}' is ambiguous; declare it explicitly.")
    return notes


def requested_packs(profile: dict) -> list[tuple[str, str | None]]:
    seen: dict[str, str | None] = {}
    for comp in profile["components"]:
        for item in comp.get("packs") or []:
            pid, ver = profiles.pack_ref(item)
            if pid and (pid not in seen or ver):
                seen[pid] = ver
    return sorted(seen.items())


@dataclass
class ProjectState:
    root: Path
    registry: packs.Registry
    detection: detection.Detection
    explicit: dict | None
    resolved: Resolved
    pack_resolution: packs.Resolution


def inspect_project(project_root: Path, resource_root: Path) -> ProjectState:
    """Read-only: discover packs, detect, load explicit profile, resolve, resolve packs."""
    registry = packs.discover(resource_root, project_root)
    det = detection.detect(project_root, registry)
    explicit, explicit_diags = load_explicit(project_root)
    resolved = resolve(det.as_profile(), explicit, det.templates)
    resolved.explicit_present = (project_root / PROFILE_REL).exists()
    resolved.diagnostics = explicit_diags + _settled(det.diagnostics, resolved) + resolved.diagnostics
    resolved.inputs = dict(sorted(det.inputs.items()))
    pack_res = packs.Resolution()
    if not profiles.has_errors(explicit_diags):
        pack_res = packs.resolve(registry, requested_packs(resolved.profile), PROFILE_REL)
        pack_res.diagnostics.extend(compatibility(resolved.profile, pack_res, registry))
    return ProjectState(project_root, registry, det, explicit, resolved, pack_res)


def _settled(diags: list[Diagnostic], resolved: Resolved) -> list[Diagnostic]:
    """Drop package-manager ambiguity diagnostics that the explicit profile resolved."""
    final = {c["id"]: c for c in resolved.profile["components"]}
    out = []
    for d in diags:
        comp = final.get(d.component)
        if (d.code in ("ambiguous-package-manager", "ambiguous-command") and comp is not None
                and resolved.provenance.get(d.component, {}).get("stack.package_managers") not in (None, "detected")
                and len(comp["stack"].get("package_managers") or []) == 1):
            continue
        out.append(d)
    return out


def compatibility(profile: dict, pack_res: packs.Resolution, registry: packs.Registry) -> list[Diagnostic]:
    """Apply declared incompatibilities; unknown compatibility is a warning, never a pass."""
    out = []
    by_id = {p.id: p for p in pack_res.packs}
    for comp in profile["components"]:
        ids = {stack_item(x)[0] for cat in STACK_CATEGORIES for x in comp["stack"].get(cat, [])}
        comp_packs = [by_id[pid] for pid, _ in (profiles.pack_ref(x) for x in comp.get("packs") or []) if pid in by_id]
        covered = set()
        for p in comp_packs:
            covered.update(p.applies_to)
            for bad in p.data.get("incompatible_stack", []) or []:
                if bad in ids:
                    out.append(Diagnostic("error", "incompatible-stack",
                                          f"pack '{p.id}' declares stack '{bad}' incompatible", PROFILE_REL, comp["id"]))
        unknown = sorted(ids - covered)
        if unknown:
            out.append(Diagnostic("warning", "compatibility-unknown",
                                  f"no selected pack declares compatibility for: {', '.join(unknown)}", PROFILE_REL, comp["id"]))
    return out
