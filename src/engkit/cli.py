"""Command-line interface: argument parsing and output only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engkit import (
    __version__,
    catalog,
    doctor,
    fsutil,
    installer,
    memory,
    resources,
    sources,
    validator,
)
from engkit.errors import EXIT_FAILURE, EXIT_IO, EXIT_OK, EXIT_USAGE, EngkitError
from engkit.platforms import TARGET_CHOICES

EXIT_CODES_HELP = """exit codes:
  0  success (including 'already installed')
  1  validation failed, diagnostics reported errors, or the operation was refused
  2  invalid arguments
  3  conflict: destination exists with different content (nothing was changed)
  4  filesystem or permission failure
  5  busy: another operation holds a reservation; retry later
"""


def _project_root(value: str | None) -> Path:
    try:
        return installer.resolve_root("project", value, None)
    except OSError as exc:
        raise EngkitError(
            f"project directory unusable: {value or 'cwd'} ({exc})", EXIT_IO
        ) from None


def _resources() -> Path:
    try:
        return resources.resource_root()
    except resources.ResourceError as exc:
        raise EngkitError(str(exc), EXIT_IO) from None


def _usage(message: str) -> EngkitError:
    return EngkitError(message, EXIT_USAGE)


def _checked_name(name: str) -> str:
    problem = validator.validate_name(name)
    if problem:
        raise _usage(f"invalid skill name {name!r}: {problem}")
    return name


def _print_issues(issues, label: str) -> int:
    """Print issues (errors to stderr); return the error count."""
    for issue in issues:
        stream = sys.stderr if issue.level == "error" else sys.stdout
        print(issue.format(), file=stream)
    error_count = sum(1 for issue in issues if issue.level == "error")
    if error_count:
        print(f"{label} failed: {error_count} error(s)", file=sys.stderr)
    return error_count


def cmd_list(args) -> int:
    if args.source:
        with sources.fetch(args.source, args.ref, args.path) as fetched:
            result = catalog.discover_dir(sources.skills_dir(fetched.root, args.path))
    elif args.ref or args.path:
        raise _usage("--ref and --path require --source")
    else:
        result = catalog.discover(_resources())
    if args.json:
        skills = [{"name": skill.name, "description": skill.description} for skill in result.skills]
        issues = [issue.format() for issue in result.issues]
        print(json.dumps({"skills": skills, "issues": issues}, indent=2))
        return EXIT_OK if result.ok else EXIT_FAILURE
    width = max((len(skill.name) for skill in result.skills), default=0)
    for skill in result.skills:
        print(fsutil.printable(f"{skill.name.ljust(width)}  {skill.description}"))
    for issue in result.issues:
        print(issue.format(), file=sys.stderr)
    return EXIT_OK if result.ok else EXIT_FAILURE


def cmd_validate(args) -> int:
    result = validator.validate(_resources(), args.name)
    if _print_issues(result.issues, "validation"):
        return EXIT_FAILURE
    print(f"ok: {len(result.skills)} skill(s) valid")
    return EXIT_OK


def _scope(args) -> dict:
    scope = "user" if args.global_ else "project"
    return {"scope": scope, "project_dir": args.project_dir}


def _report(results) -> int:
    for result in results:
        stream = sys.stdout if result.exit_code == EXIT_OK else sys.stderr
        print(result.format(), file=stream)
    if len(results) > 1:
        print("note: each target is installed independently (no cross-platform transaction)")
    return max((result.exit_code for result in results), default=EXIT_OK)


def cmd_install(args) -> int:
    if not args.source:
        if args.skill or args.ref or args.path or args.yes:
            raise _usage("--skill, --ref, --path and --yes require --source")
        if not args.name:
            raise _usage("give a built-in NAME, or use --source with --skill")
        name = _checked_name(args.name)
        return _report(installer.install(_resources(), name, args.target, **_scope(args)))
    if args.name or not args.skill:
        raise _usage("--source needs at least one --skill and no positional NAME")
    names = [_checked_name(name) for name in dict.fromkeys(args.skill)]
    options = {"yes": args.yes, **_scope(args)}
    results = installer.install_remote(
        args.source, args.ref, args.path, names, args.target, **options
    )
    return _report(results)


def cmd_update(args) -> int:
    names = [_checked_name(args.name)] if args.name else []
    results = installer.update(_resources(), names, args.target, yes=args.yes, **_scope(args))
    if not results:
        print("nothing to update: no skills in the lock")
    return _report(results)


def cmd_uninstall(args) -> int:
    name = _checked_name(args.name)
    return _report(installer.uninstall(name, args.target, **_scope(args)))


def cmd_doctor(args) -> int:
    report = doctor.run(
        _resources(),
        args.target,
        _project_root(args.project_dir),
        doctor.home_dir(),
        check_global=not args.project_only,
    )
    if args.json:
        print(json.dumps(report, indent=2))
        return EXIT_FAILURE if report["errors"] else EXIT_OK
    for section in report["sections"]:
        print(f"== {section['title']}")
        for item in section["items"]:
            print(f"  {item['level']:<7} {item['message']}")
    summary = f"doctor: {report['errors']} error(s), {report['warnings']} warning(s)"
    print(f"{summary}; nothing was modified")
    return EXIT_FAILURE if report["errors"] else EXIT_OK


def cmd_memory_init(args) -> int:
    root = _project_root(args.project_dir)
    try:
        result = memory.init(root)
    except fsutil.UnsafePathError as exc:
        raise EngkitError(f"refusing to create memory: {exc}", EXIT_FAILURE) from None
    for path in result.created:
        print(f"created {path}")
    for path in result.existing:
        print(f"kept existing {path}")
    print("engkit does not edit CLAUDE.md or AGENTS.md. To load memory, add yourself:")
    print(f"  CLAUDE.md: {memory.CLAUDE_SNIPPET.strip()}")
    print(f"  AGENTS.md: {memory.AGENTS_SNIPPET.strip()}")
    return EXIT_OK


def cmd_memory_validate(args) -> int:
    if _print_issues(memory.validate(_project_root(args.project_dir)), "memory validation"):
        return EXIT_FAILURE
    print("ok: memory is valid")
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _add_source(parser) -> None:
    parser.add_argument("--source", help="git URL (https://, ssh://, file:// or user@host:path)")
    parser.add_argument("--ref", help="branch, tag or commit of --source (default: HEAD)")
    parser.add_argument("--path", help="directory of skills inside --source")


def _add_project_dir(parser, allow_global: bool = False) -> None:
    group = parser.add_mutually_exclusive_group() if allow_global else parser
    group.add_argument("--project-dir", help="project root (default: current directory)")
    if allow_global:
        group.add_argument(
            "--global", dest="global_", action="store_true", help="use the user's home directory"
        )


def _add_list(subparsers) -> None:
    parser = subparsers.add_parser("list", help="list skills (built-in or from --source)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    _add_source(parser)
    parser.set_defaults(func=cmd_list)


def _add_validate(subparsers) -> None:
    parser = subparsers.add_parser("validate", help="validate one or all canonical skills")
    parser.add_argument("name", nargs="?", help="skill name (default: all)")
    parser.set_defaults(func=cmd_validate)


def _add_install(subparsers) -> None:
    parser = subparsers.add_parser(
        "install",
        help="copy a skill into a project or user skills directory (never overwrites)",
        epilog=EXIT_CODES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", nargs="?", help="built-in skill name (without --source)")
    parser.add_argument("--target", required=True, choices=TARGET_CHOICES)
    _add_source(parser)
    parser.add_argument("--skill", action="append", help="skill to install from --source")
    parser.add_argument("--yes", action="store_true", help="install from --source (else preview)")
    _add_project_dir(parser, allow_global=True)
    parser.set_defaults(func=cmd_install)


def _add_update(subparsers) -> None:
    parser = subparsers.add_parser(
        "update", help="update unmodified locked skills", epilog=EXIT_CODES_HELP
    )
    parser.add_argument("name", nargs="?", help="skill name (default: all locked skills)")
    parser.add_argument("--target", default="all", choices=TARGET_CHOICES)
    parser.add_argument("--yes", action="store_true", help="apply updates from git sources")
    _add_project_dir(parser, allow_global=True)
    parser.set_defaults(func=cmd_update)


def _add_uninstall(subparsers) -> None:
    parser = subparsers.add_parser("uninstall", help="remove an unmodified locked skill")
    parser.add_argument("name")
    parser.add_argument("--target", required=True, choices=TARGET_CHOICES)
    _add_project_dir(parser, allow_global=True)
    parser.set_defaults(func=cmd_uninstall)


def _add_doctor(subparsers) -> None:
    parser = subparsers.add_parser("doctor", help="read-only diagnostics for installed skills")
    parser.add_argument("--target", default="all", choices=TARGET_CHOICES)
    _add_project_dir(parser)
    parser.add_argument(
        "--project-only", action="store_true", help="skip user-scope (home directory) checks"
    )
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_doctor)


def _add_memory(subparsers) -> None:
    memory_parser = subparsers.add_parser("memory", help="project memory in .engkit/memory/")
    commands = memory_parser.add_subparsers(
        dest="memory_command", metavar="<subcommand>", parser_class=_Parser
    )
    commands.required = True
    init_parser = commands.add_parser("init", help="create .engkit/memory/ (never overwrites)")
    _add_project_dir(init_parser)
    init_parser.set_defaults(func=cmd_memory_init)
    validate_parser = commands.add_parser("validate", help="check memory format (read-only)")
    _add_project_dir(validate_parser)
    validate_parser.set_defaults(func=cmd_memory_validate)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="engkit",
        description="Portable engineering-workflow skills for Claude Code and Codex.",
        epilog=EXIT_CODES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"engkit {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_Parser)
    subparsers.required = True
    _add_list(subparsers)
    _add_validate(subparsers)
    _add_install(subparsers)
    _add_update(subparsers)
    _add_uninstall(subparsers)
    _add_doctor(subparsers)
    _add_memory(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except EngkitError as exc:
        print(f"engkit: error: {fsutil.printable(str(exc))}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("engkit: interrupted", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"engkit: error: {exc}", file=sys.stderr)
        return EXIT_IO


if __name__ == "__main__":
    sys.exit(main())
