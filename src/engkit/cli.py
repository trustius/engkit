"""Command-line interface: argument parsing and output only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engkit import __version__
from engkit.errors import EXIT_FAILURE, EXIT_IO, EXIT_OK, EXIT_USAGE, EngkitError
from engkit.platforms import PLATFORMS, TARGET_CHOICES

EXIT_CODES_HELP = """exit codes:
  0  success (including 'already installed' and no-op generation)
  1  validation failed, diagnostics reported errors, or the operation was refused
  2  invalid arguments
  3  conflict: destination exists with different content (nothing was changed)
  4  filesystem or permission failure
  5  busy: another operation holds a reservation or lock; retry later
"""


def _project_root(value: str | None) -> Path:
    raw = Path(value) if value else Path.cwd()
    try:
        root = raw.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EngkitError(f"project directory not found: {raw} ({exc.strerror})", EXIT_IO) from None
    if not root.is_dir():
        raise EngkitError(f"project directory is not a directory: {root}", EXIT_IO)
    return root


def _resources() -> Path:
    from engkit.resources import ResourceError, resource_root

    try:
        return resource_root()
    except ResourceError as exc:
        raise EngkitError(str(exc), EXIT_IO) from None


def _print_diags(diags, stream=None) -> None:
    for d in diags:
        print(d.format(), file=stream or sys.stdout)


# --- commands -----------------------------------------------------------------

def cmd_list(args) -> int:
    from engkit.catalog import discover

    result = discover(_resources())
    if args.json:
        print(json.dumps({"skills": [{"name": s.name, "description": s.description} for s in result.skills],
                          "issues": [i.format() for i in result.issues]}, indent=2))
    else:
        width = max((len(s.name) for s in result.skills), default=0)
        for s in result.skills:
            print(f"{s.name.ljust(width)}  {s.description}")
        for issue in result.issues:
            print(issue.format(), file=sys.stderr)
    return EXIT_OK if result.ok else EXIT_FAILURE


def cmd_validate(args) -> int:
    from engkit.validator import validate

    result = validate(_resources(), args.name)
    for issue in result.issues:
        print(issue.format(), file=sys.stderr if issue.level == "error" else sys.stdout)
    errors = sum(1 for i in result.issues if i.level == "error")
    if errors:
        print(f"validation failed: {errors} error(s)", file=sys.stderr)
        return EXIT_FAILURE
    print(f"ok: {len(result.skills)} skill(s) valid")
    return EXIT_OK


def cmd_install(args) -> int:
    from engkit.installer import install

    scope = "user" if args.global_ else "project"
    if args.global_ and args.project_dir:
        raise EngkitError("--global and --project-dir are mutually exclusive", EXIT_USAGE)
    results = install(_resources(), args.name, args.target, scope=scope, project_dir=args.project_dir)
    for r in results:
        print(r.format(), file=sys.stdout if r.exit_code == EXIT_OK else sys.stderr)
    if len(results) > 1:
        print("note: each target is installed independently; there is no cross-platform transaction")
    return max((r.exit_code for r in results), default=EXIT_OK)


def cmd_doctor(args) -> int:
    from engkit import doctor

    report = doctor.run(_resources(), args.target, _project_root(args.project_dir), doctor.home_dir(),
                        check_global=not args.project_only)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for sec in report["sections"]:
            print(f"== {sec['title']}")
            for item in sec["items"]:
                print(f"  {item['level']:<7} {item['message']}")
        print(f"doctor: {report['errors']} error(s), {report['warnings']} warning(s); nothing was modified")
    return EXIT_FAILURE if report["errors"] else EXIT_OK


def cmd_project_inspect(args) -> int:
    from engkit.resolution import inspect_project

    root = _project_root(args.project_dir)
    state = inspect_project(root, _resources())
    diags = state.resolved.diagnostics + state.registry.diagnostics + state.pack_resolution.diagnostics
    data = {
        "project_root": str(root),
        "read_only": True,
        "explicit_profile": state.resolved.explicit_present,
        "profile": state.resolved.profile,
        "provenance": state.resolved.provenance,
        "packs": [{"id": p.id, "version": p.version, "origin": p.origin} for p in state.pack_resolution.packs],
        "inputs": sorted(state.resolved.inputs),
        "diagnostics": [d.as_dict() for d in diags],
    }
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=False))
    else:
        prof = state.resolved.profile
        print(f"project: {prof['project'].get('name')} (mode: {prof['project'].get('mode')}; explicit profile: "
              f"{'yes' if state.resolved.explicit_present else 'no'})")
        for comp in prof["components"]:
            stack = ", ".join(f"{k}={'/'.join(str(x) if isinstance(x, str) else x['id'] for x in v)}"
                              for k, v in comp["stack"].items() if v) or "unknown"
            print(f"- {comp['id']} @ {comp['root']}: {stack}")
            for name, cmd in sorted(comp["commands"].items()):
                print(f"    {name}: {cmd.get('argv') or '-'} [{cmd.get('status')}] (not executed)")
            for note in comp.get("unresolved") or []:
                print(f"    unresolved: {note}")
        if data["packs"]:
            print("packs: " + ", ".join(f"{p['id']}@{p['version']} ({p['origin']})" for p in data["packs"]))
        _print_diags(diags)
        print("inspect is read-only; nothing was written")
    errors = [d for d in diags if d.level == "error"]
    return EXIT_FAILURE if errors else EXIT_OK


def cmd_stack_validate(args) -> int:
    from engkit.define import validate_stack

    root = _project_root(args.project_dir)
    outcome = validate_stack(Path(args.file), root, _resources())
    _print_diags(outcome.diagnostics)
    print(f"stack definition {args.file}: {outcome.status}")
    return outcome.exit_code


def cmd_project_define(args) -> int:
    from engkit.define import define

    root = _project_root(args.project_dir)
    outcome = define(Path(args.stack), root, _resources(), dry_run=args.dry_run)
    _print_diags(outcome.diagnostics)
    for line in outcome.lines:
        print(line)
    print(f"project define: {outcome.status}")
    return outcome.exit_code


def cmd_project_generate(args) -> int:
    from engkit import generation

    root = _project_root(args.project_dir)
    if args.replace_generated and args.recover_generated:
        raise EngkitError("--replace-generated and --recover-generated are mutually exclusive", EXIT_USAGE)
    if args.recover_generated:
        if args.target:
            raise EngkitError("--recover-generated restores the previous bundle; --target does not apply", EXIT_USAGE)
        report = generation.recover(root, dry_run=args.dry_run)
    else:
        targets: list[str] = []
        for t in args.target or []:
            targets.extend(PLATFORMS if t == "all" else [t])
        report = generation.generate(root, _resources(), targets, replace=args.replace_generated, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        stream = sys.stdout if report.exit_code == EXIT_OK else sys.stderr
        for line in report.lines:
            print(line, file=stream)
        print(f"project generate: {report.status}", file=stream)
    return report.exit_code


# --- parser -------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="engkit", description="Portable engineering-workflow skills for Claude Code and Codex (offline, local).",
                epilog=EXIT_CODES_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"engkit {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>", parser_class=_Parser)
    sub.required = True

    s = sub.add_parser("list", help="list canonical skills (read-only)")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("validate", help="validate one or all canonical skills (read-only)")
    s.add_argument("name", nargs="?", help="skill name (default: all)")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("install", help="copy a skill into a project or user skills directory (never overwrites)",
                       epilog=EXIT_CODES_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("name", help="skill name")
    s.add_argument("--target", required=True, choices=TARGET_CHOICES)
    where = s.add_mutually_exclusive_group()
    where.add_argument("--project-dir", help="project root (default: current directory)")
    where.add_argument("--global", dest="global_", action="store_true", help="install into the user's home skills directory")
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("doctor", help="read-only diagnostics for installs, profile, packs and generated context")
    s.add_argument("--target", default="all", choices=TARGET_CHOICES)
    s.add_argument("--project-dir", help="project root (default: current directory)")
    s.add_argument("--project-only", action="store_true", help="skip user-scope (home directory) checks")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_doctor)

    proj = sub.add_parser("project", help="project profile commands").add_subparsers(
        dest="project_command", metavar="<subcommand>", parser_class=_Parser)
    proj.required = True

    s = proj.add_parser("inspect", help="read-only detection report (does not persist a profile)")
    s.add_argument("--project-dir")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_project_inspect)

    s = proj.add_parser("define", help="create .engkit/project.yaml from a stack definition (refuses a different existing profile)")
    s.add_argument("--stack", required=True, help="stack definition file")
    s.add_argument("--project-dir")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_project_define)

    s = proj.add_parser("generate", help="render .engkit/generated/ context and optional platform drafts",
                        epilog=EXIT_CODES_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("--project-dir")
    s.add_argument("--target", action="append", choices=TARGET_CHOICES,
                   help="also render an instruction draft for this platform (repeatable)")
    s.add_argument("--dry-run", action="store_true", help="report the proposed operation; write nothing")
    mode = s.add_mutually_exclusive_group()
    mode.add_argument("--replace-generated", action="store_true",
                      help="replace the generated bundle after a verified backup (never touches profiles, skills, CLAUDE.md or AGENTS.md)")
    mode.add_argument("--recover-generated", action="store_true",
                      help="restore the state before an interrupted generation; does not generate")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_project_generate)

    stack = sub.add_parser("stack", help="stack definition commands").add_subparsers(
        dest="stack_command", metavar="<subcommand>", parser_class=_Parser)
    stack.required = True
    s = stack.add_parser("validate", help="validate a stack definition and its pack references")
    s.add_argument("--file", required=True)
    s.add_argument("--project-dir", help="project whose .engkit/packs registry to use (default: current directory)")
    s.set_defaults(func=cmd_stack_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EngkitError as exc:
        print(f"engkit: error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("engkit: interrupted", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"engkit: error: {exc}", file=sys.stderr)
        return EXIT_IO


if __name__ == "__main__":
    sys.exit(main())
