"""Deterministic project-context generation with explicit, recoverable replacement.

See docs/adr/0003-generation-transactions.md for the transaction contract:
lock -> stage -> verify -> backup -> journal -> swap -> verify -> clear.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import socket
import string
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from engkit import __version__, fsutil, packs, profiles
from engkit.errors import EXIT_BUSY, EXIT_CONFLICT, EXIT_FAILURE, EXIT_IO, EXIT_OK
from engkit.fsutil import UnsafePathError, sha256_bytes, tree_snapshot
from engkit.platforms import PLATFORMS
from engkit.profiles import STACK_CATEGORIES, stack_item
from engkit.resolution import PROFILE_REL, ProjectState, inspect_project

TEMPLATE_VERSION = 1
MANIFEST_VERSION = 1
GENERATED_REL = ".engkit/generated"
JOURNAL_REL = ".engkit/generation-transaction.json"
LOCK_REL = ".engkit/generation.lock"
STAGING_REL = ".engkit/staging"
BACKUPS_REL = ".engkit/backups"
MANIFEST = "manifest.json"
# Paths inside the bundle that engkit owns. Anything else is "unrecognized" and preserved.
MANAGED_PREFIXES = ("components/", "references/", "platform/")
MANAGED_FILES = ("PROJECT_CONTEXT.md", MANIFEST)
TX_RE = re.compile(r"^[0-9a-f]{32}$")
TEMPLATES = {
    "context": "PROJECT_CONTEXT.md.tmpl",
    "component": "component.md.tmpl",
    "claude": "platform-claude.md.tmpl",
    "codex": "platform-codex.md.tmpl",
}

# Test seam for failure injection: called with a stage name.
fault_hook = None


def _fault(stage: str) -> None:
    if fault_hook:
        fault_hook(stage)


def reference_path(pack_id: str, rel: str) -> str:
    """Bundle path for a pack reference: references/<pack-id>/<path below the pack's references/>."""
    return f"references/{pack_id}/{rel[len('references/'):] if rel.startswith('references/') else rel}"


def is_managed(rel: str) -> bool:
    return rel in MANAGED_FILES or rel.startswith(MANAGED_PREFIXES)


# --- rendering ---------------------------------------------------------------

def _template(resource_root: Path, key: str) -> string.Template:
    text = (resource_root / "templates" / TEMPLATES[key]).read_text(encoding="utf-8")
    return string.Template(text)


def _bullets(items: list[str], empty: str = "- None recorded.") -> str:
    return "\n".join(f"- {i}" for i in items) if items else empty


def _md(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _stack_text(stack: dict) -> list[str]:
    lines = []
    for cat in STACK_CATEGORIES:
        items = []
        for x in stack.get(cat) or []:
            iid, ver = stack_item(x)
            items.append(f"`{iid}`" + (f" ({ver})" if ver else ""))
        if items:
            lines.append(f"{cat.replace('_', ' ')}: {', '.join(items)}")
    return lines


def render(state: ProjectState, resource_root: Path, targets: list[str]) -> dict[str, bytes]:
    """Return the complete bundle (relative path -> bytes), manifest included. Pure and deterministic."""
    profile = state.resolved.profile
    project = profile["project"]
    pack_by_id = {p.id: p for p in state.pack_resolution.packs}
    common = {"engkit_version": __version__, "template_version": TEMPLATE_VERSION}
    files: dict[str, bytes] = {}

    rows, unresolved = [], []
    for comp in profile["components"]:
        stack = "; ".join(_stack_text(comp["stack"])) or "unknown"
        rows.append(f"| `{comp['id']}` | `{comp['root']}` | {_md(stack)} | [components/{comp['id']}.md](components/{comp['id']}.md) |")
        unresolved += [f"`{comp['id']}`: {u}" for u in comp.get("unresolved") or []]
        files[f"components/{comp['id']}.md"] = _render_component(resource_root, comp, pack_by_id, project, common)

    constraints = [f"{k}: {json.dumps(v, sort_keys=True) if not isinstance(v, str) else v}"
                   for k, v in sorted((project.get("constraints") or {}).items())]
    diags = sorted({d.format() for d in state.resolved.diagnostics + state.pack_resolution.diagnostics
                    if d.level in ("warning", "error")})
    context = _template(resource_root, "context").substitute(
        common,
        project_name=project.get("name", ""),
        mode=project.get("mode", "existing"),
        profile_source=(f"explicit `{PROFILE_REL}` merged with read-only detection" if state.resolved.explicit_present
                        else "read-only detection only (no explicit profile)"),
        constraints=_bullets(constraints, "- None declared."),
        components_table="\n".join(rows),
        unresolved=_bullets(unresolved),
        diagnostics=_bullets([f"`{_md(d)}`" for d in diags]),
    )
    files["PROJECT_CONTEXT.md"] = context.encode()

    for pack in state.pack_resolution.packs:
        for rel in pack.references:
            files[reference_path(pack.id, rel)] = (pack.directory / rel).read_bytes()

    component_list = ", ".join(f"`{c['id']}` at `{c['root']}`" for c in profile["components"])
    for target in targets:
        files[f"platform/{target}.md"] = _template(resource_root, target).substitute(
            common, project_name=project.get("name", ""), component_list=component_list).encode()

    files[MANIFEST] = _manifest(state, targets, files)
    return dict(sorted(files.items()))


def _render_component(resource_root: Path, comp: dict, pack_by_id: dict, project: dict, common: dict) -> bytes:
    cmds = []
    for name, cmd in sorted(comp["commands"].items()):
        argv = cmd.get("argv") or []
        shown = f"`{shlex.join(argv)}`" if argv else "_not determined_"
        cmds.append(f"**{name}** ({cmd.get('status', 'unknown')}): {shown}; argv `{json.dumps(argv)}`; cwd `{cmd.get('cwd', comp['root'])}`"
                    + (f"; source `{cmd['source']}`" if cmd.get("source") else ""))
    conv = comp.get("conventions") or {}
    conventions = [f"Reference: [`{r}`]({'../' * 3}{r})" for r in conv.get("references") or []]
    conventions += list(conv.get("notes") or [])
    pack_lines = []
    for item in comp.get("packs") or []:
        pid, _ = profiles.pack_ref(item)
        pack = pack_by_id.get(pid)
        if pack is None:
            pack_lines.append(f"`{pid}`: not resolved")
            continue
        pack_lines.append(f"`{pack.id}@{pack.version}` ({pack.origin}): {pack.description}")
        for rel in pack.references:
            pack_lines.append(f"  - [{rel}](../{reference_path(pack.id, rel)})")
        for frag in pack.fragments:
            text = string.Template((pack.directory / frag).read_text(encoding="utf-8")).substitute(
                component_id=comp["id"], component_root=comp["root"], pack_id=pack.id,
                pack_version=pack.version, project_name=project.get("name", ""))
            pack_lines.extend("  " + line for line in text.strip().splitlines())
    evidence = [f"| `{_md(e['source'])}` | {_md(e.get('field') or '-')} | {_md(e.get('value', ''))} | {e.get('confidence', 'unknown')} |"
                for e in comp.get("evidence") or []]
    ev_text = ("| Source | Field | Value | Confidence |\n|---|---|---|---|\n" + "\n".join(evidence)) if evidence else "- None recorded."
    text = _template(resource_root, "component").substitute(
        common,
        component_id=comp["id"],
        component_root=comp["root"],
        description=f"- Description: {comp['description']}\n" if comp.get("description") else "",
        stack=_bullets(_stack_text(comp["stack"]), "- Unknown."),
        commands=_bullets(cmds, "- None documented."),
        conventions=_bullets(conventions),
        packs="\n".join(f"- {p}" if not p.startswith("  ") else p for p in pack_lines) or "- None selected.",
        evidence=ev_text,
        unresolved=_bullets(comp.get("unresolved") or []),
    )
    return text.encode()


def canonical_json(data) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _manifest(state: ProjectState, targets: list[str], files: dict[str, bytes]) -> bytes:
    inputs = dict(state.resolved.inputs)
    explicit = state.root / PROFILE_REL
    if explicit.is_file():
        inputs[PROFILE_REL] = fsutil.sha256_file(explicit)
    data = {
        "manifest_version": MANIFEST_VERSION,
        "generator": {"name": "engkit", "version": __version__, "template_version": TEMPLATE_VERSION,
                      "profile_schema_version": profiles.PROFILE_SCHEMA_VERSION},
        "targets": sorted(targets),
        "profile_sha256": sha256_bytes(canonical_json(state.resolved.profile)),
        "resolved_profile": state.resolved.profile,
        "inputs": dict(sorted(inputs.items())),
        "packs": [{"id": p.id, "version": p.version, "origin": p.origin, "sha256": p.content_hash}
                  for p in state.pack_resolution.packs],
        "outputs": {rel: sha256_bytes(b) for rel, b in sorted(files.items())},
    }
    return canonical_json(data)


# --- bundle state -------------------------------------------------------------

@dataclass
class BundleState:
    exists: bool
    snapshot: dict[str, str] | None = None
    manifest: dict | None = None
    problems: list[str] = field(default_factory=list)  # manifest invalid, edited/missing outputs
    edited: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)


def read_bundle(project_root: Path) -> BundleState:
    gen = project_root / GENERATED_REL
    if not os.path.lexists(gen):
        return BundleState(exists=False)
    for problem in fsutil.check_no_symlinks(project_root, (".engkit", "generated")):
        raise UnsafePathError(problem)
    snap = tree_snapshot(gen)
    state = BundleState(exists=True, snapshot=snap)
    state.unrecognized = sorted(p for p in snap if not is_managed(p))
    raw = (gen / MANIFEST)
    if MANIFEST not in snap:
        state.problems.append("manifest.json is missing")
        return state
    try:
        manifest = json.loads(raw.read_text(encoding="utf-8"))
        outputs = manifest["outputs"]
        if not isinstance(outputs, dict) or not all(isinstance(v, str) for v in outputs.values()):
            raise ValueError("outputs must map paths to hashes")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        state.problems.append(f"manifest.json is invalid: {exc}")
        return state
    state.manifest = manifest
    for rel, digest in sorted(outputs.items()):
        if rel == MANIFEST:
            continue
        if rel not in snap:
            state.missing.append(rel)
        elif snap[rel] != digest:
            state.edited.append(rel)
    if state.missing:
        state.problems.append("missing outputs: " + ", ".join(state.missing))
    if state.edited:
        state.problems.append("edited outputs: " + ", ".join(state.edited))
    return state


def _desired_snapshot(bundle: dict[str, bytes]) -> dict[str, str]:
    return {rel: sha256_bytes(b) for rel, b in bundle.items()}


# --- reports ------------------------------------------------------------------

@dataclass
class Report:
    status: str
    exit_code: int
    lines: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"status": self.status, "exit_code": self.exit_code, "messages": self.lines, **self.data}


# --- lock and journal -----------------------------------------------------------

class LockBusy(Exception):
    pass


def _engkit_dir(project_root: Path) -> Path:
    return fsutil.ensure_real_dirs(project_root, (".engkit",))


def acquire_lock(project_root: Path, tx: str) -> Path:
    _engkit_dir(project_root)
    lock = project_root / LOCK_REL
    payload = canonical_json({"pid": os.getpid(), "host": socket.gethostname(), "transaction_id": tx})
    try:
        fsutil.write_file(lock, payload, exclusive=True)
    except FileExistsError:
        raise LockBusy(describe_lock(project_root)) from None
    return lock


def release_lock(project_root: Path, tx: str) -> None:
    lock = project_root / LOCK_REL
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.get("transaction_id") == tx and not lock.is_symlink():
        lock.unlink()


def describe_lock(project_root: Path) -> str:
    """Human-readable lock status. Locks are never reclaimed automatically."""
    lock = project_root / LOCK_REL
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
        pid, host = int(data.get("pid", -1)), data.get("host", "?")
    except (OSError, ValueError, TypeError):
        return f"{LOCK_REL} exists but is unreadable; another engkit generation may be running"
    if host == socket.gethostname() and not fsutil.pid_alive(pid):
        return (f"{LOCK_REL} is held by pid {pid}, which is not running on this host (stale). "
                f"After confirming no engkit process is using this project, delete {LOCK_REL} and retry.")
    return f"{LOCK_REL} is held by pid {pid} on {host}; another engkit generation is in progress. Retry later."


def read_journal(project_root: Path) -> dict | None:
    path = project_root / JOURNAL_REL
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        raise UnsafePathError(f"{JOURNAL_REL} must not be a symlink")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"invalid": str(exc)}


def _journal_problems(journal: dict) -> list[str]:
    tx = journal.get("transaction_id")
    if not isinstance(tx, str) or not TX_RE.match(tx):
        return ["transaction_id is missing or malformed"]
    expected = {
        "staging": f"{STAGING_REL}/{tx}",
        "aside": f"{STAGING_REL}/{tx}/previous",
        "backup": f"{BACKUPS_REL}/{tx}/generated" if journal.get("had_prior") else None,
    }
    problems = [f"{k} path {journal.get(k)!r} is not the expected {v!r}" for k, v in expected.items() if journal.get(k) != v]
    for key in ("prior_snapshot", "new_snapshot"):
        snap = journal.get(key)
        if snap is not None and not (isinstance(snap, dict) and all(_safe_rel(p) for p in snap)):
            problems.append(f"{key} contains unsafe paths")
    if journal.get("had_prior") and journal.get("prior_snapshot") is None:
        problems.append("prior_snapshot missing")
    return problems


def _safe_rel(p) -> bool:
    try:
        fsutil.safe_relpath(p)
        return True
    except UnsafePathError:
        return False


# --- generate -----------------------------------------------------------------

def generate(project_root: Path, resource_root: Path, targets: list[str], *,
             replace: bool = False, dry_run: bool = False) -> Report:
    targets = sorted(set(targets))
    for t in targets:
        if t not in PLATFORMS:
            return Report("error", EXIT_FAILURE, [f"unknown target '{t}'"])
    try:
        journal = read_journal(project_root)
    except UnsafePathError as exc:
        return Report("error", EXIT_FAILURE, [str(exc)])
    if journal is not None:
        return Report("blocked", EXIT_FAILURE, [
            f"an incomplete generation transaction is recorded in {JOURNAL_REL}; the generated bundle is unusable.",
            "Inspect it, then run: engkit project generate --project-dir <root> --recover-generated"])

    state = inspect_project(project_root, resource_root)
    errors = [d for d in state.resolved.diagnostics + state.pack_resolution.diagnostics if d.level == "error"]
    if errors:
        return Report("error", EXIT_FAILURE, ["cannot generate; fix these first:"] + [f"  {d.format()}" for d in errors])
    bundle = render(state, resource_root, targets)
    desired = _desired_snapshot(bundle)
    try:
        existing = read_bundle(project_root)
    except (UnsafePathError, OSError) as exc:
        return Report("error", EXIT_FAILURE, [f"unsafe or unreadable {GENERATED_REL}: {exc}"])

    data = {"outputs": sorted(desired), "targets": targets}
    if existing.exists:
        current_managed = {p: h for p, h in existing.snapshot.items() if is_managed(p)}
        if not existing.problems and current_managed == desired:
            return Report("unchanged", EXIT_OK, [f"{GENERATED_REL} is up to date; nothing to do."], data)
        reasons = list(existing.problems)
        changed = sorted(p for p in set(desired) | set(current_managed)
                         if desired.get(p) != current_managed.get(p) and p != MANIFEST)
        if changed:
            reasons.append("desired output differs: " + ", ".join(changed))
        elif not existing.problems:
            reasons.append("manifest.json differs (inputs, packs or generator changed)")
        data["conflicts"] = reasons
        if not replace:
            return Report("conflict", EXIT_CONFLICT, [f"{GENERATED_REL} differs from the desired output; nothing was written."]
                          + [f"  - {r}" for r in reasons]
                          + ["To replace the generated bundle (after a verified backup), run:",
                             f"  engkit project generate --project-dir <root>{_target_flag(targets)} --replace-generated"], data)
        collisions = sorted(set(existing.unrecognized) & set(desired))
        if collisions:
            return Report("conflict", EXIT_CONFLICT, ["unrecognized files collide with generated paths: " + ", ".join(collisions)], data)

    if dry_run:
        verb = "replace" if existing.exists else "create"
        lines = [f"dry run: would {verb} {GENERATED_REL} with {len(desired)} files:"] + [f"  {p}" for p in sorted(desired)]
        if existing.exists:
            lines.append(f"dry run: would back up the current bundle to {BACKUPS_REL}/<transaction-id>/generated "
                         f"and preserve {len(existing.unrecognized)} unrecognized file(s)")
        return Report("dry-run", EXIT_OK, lines, data)
    return _commit(project_root, bundle, existing, data)


def _target_flag(targets: list[str]) -> str:
    if set(targets) == set(PLATFORMS):
        return " --target all"
    return "".join(f" --target {t}" for t in targets)


def _commit(project_root: Path, bundle: dict[str, bytes], existing: BundleState, data: dict) -> Report:
    tx = uuid.uuid4().hex
    gen = project_root / GENERATED_REL
    try:
        acquire_lock(project_root, tx)
    except LockBusy as exc:
        return Report("busy", EXIT_BUSY, [str(exc)], data)
    except (OSError, UnsafePathError) as exc:
        return Report("error", EXIT_IO, [f"cannot create lock: {exc}"], data)

    staging = project_root / STAGING_REL / tx
    backup_root = project_root / BACKUPS_REL / tx
    new_dir = staging / "new"
    aside = staging / "previous"
    journal_path = project_root / JOURNAL_REL
    prior = existing.snapshot if existing.exists else None
    try:
        if os.path.lexists(journal_path):
            raise _Abort("busy", EXIT_BUSY, f"{JOURNAL_REL} appeared; another transaction is in progress")
        if _current_snapshot(gen) != prior:
            raise _Abort("conflict", EXIT_CONFLICT, f"{GENERATED_REL} changed since inspection; nothing was written")
        fsutil.ensure_real_dirs(project_root, (".engkit", "staging"))
        os.mkdir(staging)
        os.mkdir(new_dir)
        for rel, payload in bundle.items():
            if rel == MANIFEST:
                continue
            _write_rel(new_dir, rel, payload)
        for rel in existing.unrecognized:
            if existing.snapshot[rel] == "<dir>":  # a user-created empty directory
                fsutil.safe_relpath(rel)
                (new_dir / rel).mkdir(parents=True, exist_ok=True)
            else:
                _write_rel(new_dir, rel, (gen / rel).read_bytes())
        _write_rel(new_dir, MANIFEST, bundle[MANIFEST])  # manifest last
        _fault("after_staging")
        new_snapshot = tree_snapshot(new_dir)
        expected = {**_desired_snapshot(bundle), **{p: existing.snapshot[p] for p in existing.unrecognized}}
        if new_snapshot != expected:
            raise OSError("staged bundle failed verification")
    except _Abort as abort:
        _discard(staging)
        release_lock(project_root, tx)
        return Report(abort.status, abort.code, [abort.message], data)
    except (OSError, UnsafePathError) as exc:
        _discard(staging)
        release_lock(project_root, tx)
        return Report("error", EXIT_IO, [f"staging failed; active bundle untouched: {exc}"], data)

    if prior is not None:
        try:
            fsutil.ensure_real_dirs(project_root, (".engkit", "backups"))
            os.mkdir(backup_root)
            _fault("backup")
            fsutil.copy_tree_regular(gen, backup_root / "generated")
            if tree_snapshot(backup_root / "generated") != prior:
                raise OSError("backup verification failed")
        except (OSError, UnsafePathError) as exc:
            _discard(staging)
            shutil.rmtree(backup_root, ignore_errors=True)
            release_lock(project_root, tx)
            return Report("error", EXIT_IO, [f"backup failed; active bundle untouched: {exc}"], data)

    journal = {
        "journal_version": 1,
        "transaction_id": tx,
        "operation": "replace" if prior is not None else "create",
        "had_prior": prior is not None,
        "prior_snapshot": prior,
        "new_snapshot": new_snapshot,
        "staging": f"{STAGING_REL}/{tx}",
        "aside": f"{STAGING_REL}/{tx}/previous",
        "backup": f"{BACKUPS_REL}/{tx}/generated" if prior is not None else None,
    }
    try:
        fsutil.write_file(journal_path, canonical_json(journal), exclusive=True)
        fsutil.fsync_dir(journal_path.parent)
    except OSError as exc:
        _discard(staging)
        release_lock(project_root, tx)
        return Report("error", EXIT_IO, [f"cannot write journal; active bundle untouched: {exc}"], data)

    moved = False  # whether any rename touched the active bundle path
    try:
        _fault("after_journal")
        if _current_snapshot(gen) != prior:
            raise _Abort("conflict", EXIT_CONFLICT, f"{GENERATED_REL} changed during the transaction; nothing was written")
        moved = True
        if prior is not None:
            os.rename(gen, aside)
            _fault("after_aside")
        _rename_into_place(new_dir, gen)
        fsutil.fsync_dir(gen.parent)
        _fault("after_swap")
        if tree_snapshot(gen) != new_snapshot:
            raise OSError("published bundle failed verification")
    except Exception as exc:  # handled failure: roll back; interruptions leave the journal
        # Before any rename there is nothing to undo, and the active bundle may hold the
        # user's concurrent edit, which a rollback would misread as corruption.
        rolled_back, detail = _rollback(gen, aside, staging, prior, new_snapshot) if moved else (True, "")
        status, code = ("conflict", EXIT_CONFLICT) if isinstance(exc, _Abort) else ("error", EXIT_IO)
        msg = exc.message if isinstance(exc, _Abort) else str(exc)
        if rolled_back:
            journal_path.unlink()
            _discard(staging)
            release_lock(project_root, tx)
            return Report(status, code, [f"generation failed and was rolled back: {msg}" if moved else msg]
                          + ([f"backup retained at {BACKUPS_REL}/{tx}/generated"] if prior is not None else []), data)
        release_lock(project_root, tx)
        return Report("error", EXIT_IO, [
            f"generation failed ({msg}) and rollback failed ({detail}).",
            f"Transaction journal kept at {JOURNAL_REL}" + (f"; backup at {BACKUPS_REL}/{tx}/generated" if prior is not None else ""),
            "Run: engkit project generate --project-dir <root> --recover-generated"], data)

    journal_path.unlink()
    fsutil.fsync_dir(journal_path.parent)
    _discard(staging)
    release_lock(project_root, tx)
    data["transaction_id"] = tx
    if prior is not None:
        data["backup"] = f"{BACKUPS_REL}/{tx}/generated"
        return Report("replaced", EXIT_OK, [f"replaced {GENERATED_REL} ({len(bundle)} files)",
                                            f"previous bundle backed up at {BACKUPS_REL}/{tx}/generated (kept until you remove it)"], data)
    return Report("created", EXIT_OK, [f"created {GENERATED_REL} ({len(bundle)} files)"], data)


class _Abort(Exception):
    def __init__(self, status: str, code: int, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _current_snapshot(gen: Path) -> dict | None:
    if not os.path.lexists(gen):
        return None
    if gen.is_symlink():
        raise UnsafePathError(f"{gen} must not be a symlink")
    return tree_snapshot(gen)


def _write_rel(base: Path, rel: str, payload: bytes) -> None:
    fsutil.safe_relpath(rel)
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    fsutil.write_file(target, payload, exclusive=True)


def _rename_into_place(src: Path, dst: Path) -> None:
    try:
        fsutil.rename_noreplace(src, dst)
    except fsutil.NoReplaceUnsupported:
        if os.path.lexists(dst):
            raise FileExistsError(str(dst))
        os.rename(src, dst)


def _discard(staging: Path) -> None:
    if TX_RE.match(staging.name) and staging.parent.name == "staging" and not staging.is_symlink():
        shutil.rmtree(staging, ignore_errors=True)
        try:
            staging.parent.rmdir()  # only succeeds when no other transaction is staged
        except OSError:
            pass


def _rollback(gen: Path, aside: Path, staging: Path, prior: dict | None, new_snapshot: dict) -> tuple[bool, str]:
    try:
        current = _current_snapshot(gen)
        if current is not None and current != prior:
            if current != new_snapshot:
                return False, f"{gen} has unexpected contents"
            os.rename(gen, staging / "failed")
        if prior is not None and not os.path.lexists(gen):
            os.rename(aside, gen)
        if _current_snapshot(gen) != prior:
            return False, "restored bundle does not match the prior snapshot"
        return True, ""
    except Exception as exc:  # noqa: BLE001 - report, never mask the original failure
        return False, str(exc)


# --- recovery -------------------------------------------------------------------

def recover(project_root: Path, *, dry_run: bool = False) -> Report:
    try:
        journal = read_journal(project_root)
    except UnsafePathError as exc:
        return Report("error", EXIT_FAILURE, [str(exc)])
    if journal is None:
        return Report("nothing-to-recover", EXIT_OK, [f"no incomplete transaction ({JOURNAL_REL} absent)"])
    problems = ["journal is unreadable: " + journal["invalid"]] if "invalid" in journal else _journal_problems(journal)
    if problems:
        return Report("manual-recovery", EXIT_FAILURE, [f"{JOURNAL_REL} failed validation; nothing was changed:"]
                      + [f"  - {p}" for p in problems] + _manual_steps())
    tx = journal["transaction_id"]
    gen = project_root / GENERATED_REL
    aside = project_root / journal["aside"]
    backup = project_root / journal["backup"] if journal.get("backup") else None
    prior, new = journal.get("prior_snapshot"), journal.get("new_snapshot")
    try:
        for parts in ((".engkit", "generated"), (".engkit", "staging"), (".engkit", "backups")):
            for problem in fsutil.check_no_symlinks(project_root, parts):
                raise UnsafePathError(problem)
        current = _current_snapshot(gen)
    except (UnsafePathError, OSError) as exc:
        return Report("manual-recovery", EXIT_FAILURE, [f"unsafe state: {exc}"] + _manual_steps())

    if current == prior:
        plan = "the prior state is already in place; only transaction state needs clearing"
    elif current is None or current == new:
        source = _restore_source(aside, backup, prior)
        if prior is not None and source is None:
            return Report("manual-recovery", EXIT_FAILURE,
                          ["no verified copy of the prior bundle was found (aside copy and backup missing or changed)"] + _manual_steps())
        plan = ("restore the prior bundle from " + (str(source.relative_to(project_root)) if source else "absence")
                + ("" if current is None else f" and move the uncommitted bundle to {BACKUPS_REL}/{tx}/abandoned-generated"))
    else:
        return Report("manual-recovery", EXIT_CONFLICT, [
            f"{GENERATED_REL} contains edits made after the interruption; nothing was changed to avoid overwriting them."]
            + _manual_steps())
    if dry_run:
        return Report("dry-run", EXIT_OK, [f"dry run: would {plan}, validate it, then remove {JOURNAL_REL}"])

    try:
        acquire_lock(project_root, tx + "-recover")
    except LockBusy as exc:
        return Report("busy", EXIT_BUSY, [str(exc)])
    lock_tx = tx + "-recover"
    try:
        current = _current_snapshot(gen)
        if current != prior:
            if current is not None:
                if current != new:
                    raise _Abort("manual-recovery", EXIT_CONFLICT, f"{GENERATED_REL} changed during recovery")
                fsutil.ensure_real_dirs(project_root, (".engkit", "backups"))
                (project_root / BACKUPS_REL / tx).mkdir(exist_ok=True)
                os.rename(gen, project_root / BACKUPS_REL / tx / "abandoned-generated")
            if prior is not None:
                source = _restore_source(aside, backup, prior)
                if source is None:
                    raise _Abort("manual-recovery", EXIT_FAILURE, "prior bundle copy disappeared during recovery")
                restore = project_root / STAGING_REL / tx / "restore"
                if os.path.lexists(restore):
                    shutil.rmtree(restore)
                fsutil.ensure_real_dirs(project_root, (".engkit", "staging", tx))
                fsutil.copy_tree_regular(source, restore)
                if tree_snapshot(restore) != prior:
                    raise OSError("restored copy failed verification")
                _rename_into_place(restore, gen)
        if _current_snapshot(gen) != prior:
            raise OSError("recovered bundle does not match the prior snapshot")
        (project_root / JOURNAL_REL).unlink()
        _discard(project_root / STAGING_REL / tx)
    except _Abort as abort:
        release_lock(project_root, lock_tx)
        return Report(abort.status, abort.code, [abort.message] + _manual_steps())
    except (OSError, UnsafePathError) as exc:
        release_lock(project_root, lock_tx)
        return Report("error", EXIT_IO, [f"recovery failed: {exc}; journal kept"] + _manual_steps())
    release_lock(project_root, lock_tx)
    lines = [f"recovered: {GENERATED_REL} restored to its state before transaction {tx}"]
    if backup is not None:
        lines.append(f"backup retained at {journal['backup']}")
    return Report("recovered", EXIT_OK, lines, {"transaction_id": tx})


def _restore_source(aside: Path, backup: Path | None, prior: dict | None) -> Path | None:
    if prior is None:
        return None
    for candidate in (aside, backup):
        if candidate is None or not os.path.lexists(candidate) or candidate.is_symlink():
            continue
        try:
            if tree_snapshot(candidate) == prior:
                return candidate
        except (UnsafePathError, OSError):
            continue
    return None


def _manual_steps() -> list[str]:
    return [
        "Manual recovery: keep .engkit/backups/ and .engkit/staging/ intact, compare .engkit/generated/ with the",
        f"backup named in {JOURNAL_REL}, restore what you want to keep, then delete {JOURNAL_REL}. See docs/regeneration.md.",
    ]


# --- freshness (used by doctor) ------------------------------------------------

def freshness(project_root: Path, resource_root: Path) -> dict:
    """Read-only freshness and integrity report for the generated bundle."""
    out: dict = {"journal": None, "lock": None}
    try:
        journal = read_journal(project_root)
    except UnsafePathError as exc:
        return {"status": "unsafe", "messages": [str(exc)]}
    if os.path.lexists(project_root / LOCK_REL):
        out["lock"] = describe_lock(project_root)
    if journal is not None:
        out.update(status="incomplete", messages=[
            f"incomplete generation transaction ({JOURNAL_REL}); bundle is unusable",
            "run: engkit project generate --project-dir <root> --recover-generated"])
        return out
    try:
        bundle = read_bundle(project_root)
    except (UnsafePathError, OSError) as exc:
        return {**out, "status": "unsafe", "messages": [str(exc)]}
    if not bundle.exists:
        return {**out, "status": "absent", "messages": [f"no generated context at {GENERATED_REL}"]}
    if bundle.problems:
        return {**out, "status": "modified", "messages": bundle.problems,
                "edited": bundle.edited, "missing": bundle.missing}
    manifest = bundle.manifest
    targets = [t for t in manifest.get("targets", []) if t in PLATFORMS]
    state = inspect_project(project_root, resource_root)
    errors = [d for d in state.resolved.diagnostics + state.pack_resolution.diagnostics if d.level == "error"]
    if errors:
        return {**out, "status": "stale", "messages": ["profile or packs now have errors: " + "; ".join(d.format() for d in errors)]}
    desired = _desired_snapshot(render(state, resource_root, targets))
    current = {p: h for p, h in bundle.snapshot.items() if is_managed(p)}
    if desired == current:
        return {**out, "status": "fresh", "messages": [f"{GENERATED_REL} matches current inputs"]}
    old_inputs = manifest.get("inputs", {})
    new_inputs = dict(state.resolved.inputs)
    explicit = project_root / PROFILE_REL
    if explicit.is_file():
        new_inputs[PROFILE_REL] = fsutil.sha256_file(explicit)
    reasons = []
    added = sorted(set(new_inputs) - set(old_inputs))
    removed = sorted(set(old_inputs) - set(new_inputs))
    changed = sorted(p for p in set(old_inputs) & set(new_inputs) if old_inputs[p] != new_inputs[p])
    if added:
        reasons.append("new inputs: " + ", ".join(added))
    if removed:
        reasons.append("removed inputs: " + ", ".join(removed))
    if changed:
        reasons.append("changed inputs: " + ", ".join(changed))
    old_packs = {(p.get("id"), p.get("version"), p.get("sha256")) for p in manifest.get("packs", [])}
    new_packs = {(p.id, p.version, p.content_hash) for p in state.pack_resolution.packs}
    if old_packs != new_packs:
        reasons.append("selected packs changed")
    if not reasons:
        reasons.append("generator, template or profile resolution changed")
    return {**out, "status": "stale", "messages": reasons}
