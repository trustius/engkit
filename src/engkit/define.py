"""`stack validate` and `project define`: explicit stack definitions and profiles."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from engkit import fsutil, packs, profiles
from engkit.detection import detect, slug
from engkit.errors import EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK
from engkit.profiles import Diagnostic, has_errors
from engkit.resolution import PROFILE_REL, compatibility, load_explicit, requested_packs, resolve


@dataclass
class Outcome:
    status: str
    exit_code: int
    diagnostics: list[Diagnostic] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)


def load_stack(stack_file: Path) -> tuple[dict | None, list[Diagnostic]]:
    data, diags = profiles.load_yaml_file(stack_file)
    if diags:
        return None, diags
    diags = profiles.validate_stack_definition(data, str(stack_file))
    return (None if has_errors(diags) else data), diags


def validate_stack(stack_file: Path, project_root: Path, resource_root: Path) -> Outcome:
    """Validate a stack definition plus its pack references against the project's registry."""
    stack, diags = load_stack(stack_file)
    registry = packs.discover(resource_root, project_root)
    diags = diags + [d for d in registry.diagnostics if d.level == "error" and d.code == "duplicate-pack-id"]
    if stack is not None:
        candidate = _profile_from_stack(stack, project_root, "new")
        res = resolve({"project": candidate["project"], "components": []}, candidate)
        pack_res = packs.resolve(registry, requested_packs(res.profile), str(stack_file))
        diags += res.diagnostics + pack_res.diagnostics
        if pack_res.ok:
            diags += compatibility(res.profile, pack_res, registry)
    status = "invalid" if has_errors(diags) else "valid"
    return Outcome(status, EXIT_FAILURE if status == "invalid" else EXIT_OK, diags)


def _profile_from_stack(stack: dict, project_root: Path, mode: str) -> dict:
    project = {"name": slug(project_root.name), "mode": mode}
    sp = stack.get("project") or {}
    if "mode" in sp:
        project["mode"] = sp["mode"]
    if sp.get("description"):
        project["description"] = sp["description"]
    project["constraints"] = dict(sp.get("constraints") or {})
    profile = {"schema_version": profiles.PROFILE_SCHEMA_VERSION, "project": project}
    if stack.get("defaults"):
        profile["defaults"] = stack["defaults"]
    profile["components"] = stack["components"]
    return profile


def define(stack_file: Path, project_root: Path, resource_root: Path, *, dry_run: bool = False) -> Outcome:
    check = validate_stack(stack_file, project_root, resource_root)
    if check.exit_code != EXIT_OK:
        return Outcome("invalid", EXIT_FAILURE, check.diagnostics, ["stack definition is invalid; nothing was written"])
    stack, _ = load_stack(stack_file)
    registry = packs.discover(resource_root, project_root)
    detected = detect(project_root, registry)
    has_evidence = any(c["evidence"] for c in detected.components)
    candidate = _profile_from_stack(stack, project_root, "existing" if has_evidence else "new")
    diags = list(check.diagnostics)
    if has_evidence:
        reconciled = resolve(detected.as_profile(), candidate)
        diags += [d for d in reconciled.diagnostics if d.code in ("contradiction", "component-id-conflict")]
        diags += [d for d in detected.diagnostics if d.level != "info"]
        if has_errors(reconciled.diagnostics):
            return Outcome("invalid", EXIT_FAILURE, diags,
                           ["the definition cannot be reconciled with detected components; nothing was written"])
    lines = []
    if any(d.code == "contradiction" for d in diags):
        lines.append("the definition contradicts detected evidence; explicit values will win (see warnings)")

    target = project_root / PROFILE_REL
    payload = profiles.canonical_yaml(candidate).encode()
    if os.path.lexists(target):
        existing, ediags = load_explicit(project_root)
        if target.is_symlink() or existing is None:
            return Outcome("conflict", EXIT_CONFLICT, diags + ediags,
                           [f"{PROFILE_REL} exists and could not be compared; it was left untouched"])
        if existing == candidate:
            return Outcome("already defined", EXIT_OK, diags, [f"{PROFILE_REL} already matches this definition"])
        return Outcome("conflict", EXIT_CONFLICT, diags, [
            f"{PROFILE_REL} already exists with different content; it was left untouched.",
            "Edit it by hand, or move it aside and run project define again."])
    if dry_run:
        return Outcome("dry-run", EXIT_OK, diags, lines + [f"dry run: would write {PROFILE_REL}:", payload.decode()])
    try:
        engkit_dir = fsutil.ensure_real_dirs(project_root, (".engkit",))
        tmp = engkit_dir / f".project.yaml.{uuid.uuid4().hex}.tmp"
        fsutil.write_file(tmp, payload, exclusive=True)
        try:
            os.link(tmp, target)  # atomic and never replaces an existing profile
        finally:
            tmp.unlink()
    except FileExistsError:
        return Outcome("conflict", EXIT_CONFLICT, diags, [f"{PROFILE_REL} appeared concurrently; it was left untouched"])
    except (OSError, fsutil.UnsafePathError) as exc:
        return Outcome("error", EXIT_IO, diags, [f"cannot write {PROFILE_REL}: {exc}"])
    return Outcome("defined", EXIT_OK, diags, lines + [f"wrote {PROFILE_REL}",
                                                      "next: engkit project generate --project-dir <root> --dry-run"])
