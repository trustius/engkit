"""Command-line interface: argument parsing and output only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engkit import __version__
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
    raw_path = Path(value) if value else Path.cwd()
    try:
        root = raw_path.expanduser().resolve(strict=True)
    except OSError as exc:
        message = f"project directory not found: {raw_path} ({exc.strerror})"
        raise EngkitError(message, EXIT_IO) from None
    if not root.is_dir():
        raise EngkitError(f"project directory is not a directory: {root}", EXIT_IO)
    return root


def _resources() -> Path:
    from engkit.resources import ResourceError, resource_root

    try:
        return resource_root()
    except ResourceError as exc:
        raise EngkitError(str(exc), EXIT_IO) from None


def _usage(message: str) -> EngkitError:
    return EngkitError(message, EXIT_USAGE)


def _catalog(args):
    from engkit import sources
    from engkit.catalog import discover, discover_dir

    if not args.source:
        if args.ref or args.path:
            raise _usage("--ref and --path require --source")
        return discover(_resources())
    with sources.fetch(args.source, args.ref, args.path) as fetched:
        return discover_dir(sources.skills_dir(fetched.root, args.path))


def cmd_list(args) -> int:
    result = _catalog(args)
    if args.json:
        skills = [{"name": skill.name, "description": skill.description} for skill in result.skills]
        issues = [issue.format() for issue in result.issues]
        print(json.dumps({"skills": skills, "issues": issues}, indent=2))
        return EXIT_OK if result.ok else EXIT_FAILURE
    width = max((len(skill.name) for skill in result.skills), default=0)
    for skill in result.skills:
        print(f"{skill.name.ljust(width)}  {skill.description}")
    for issue in result.issues:
        print(issue.format(), file=sys.stderr)
    return EXIT_OK if result.ok else EXIT_FAILURE


def cmd_validate(args) -> int:
    from engkit.validator import validate

    result = validate(_resources(), args.name)
    for issue in result.issues:
        stream = sys.stderr if issue.level == "error" else sys.stdout
        print(issue.format(), file=stream)
    error_count = sum(1 for issue in result.issues if issue.level == "error")
    if error_count:
        print(f"validation failed: {error_count} error(s)", file=sys.stderr)
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
    from engkit import installer

    if args.source:
        if args.name or not args.skill:
            raise _usage("--source needs at least one --skill and no positional NAME")
        names = list(dict.fromkeys(args.skill))
        options = {"yes": args.yes, **_scope(args)}
        results = installer.install_remote(
            args.source, args.ref, args.path, names, args.target, **options
        )
        return _report(results)
    if not args.name or args.skill or args.ref or args.path:
        raise _usage("without --source give exactly one NAME and no --skill/--ref/--path")
    return _report(installer.install(_resources(), args.name, args.target, **_scope(args)))


def cmd_update(args) -> int:
    from engkit import installer

    names = [args.name] if args.name else []
    results = installer.update(_resources(), names, args.target, yes=args.yes, **_scope(args))
    if not results:
        print("nothing to update: no skills in the lock")
    return _report(results)


def cmd_uninstall(args) -> int:
    from engkit import installer

    return _report(installer.uninstall(args.name, args.target, **_scope(args)))


def cmd_doctor(args) -> int:
    from engkit import doctor

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
    from engkit import fsutil, memory

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
    from engkit import memory

    issues = memory.validate(_project_root(args.project_dir))
    for issue in issues:
        stream = sys.stderr if issue.level == "error" else sys.stdout
        print(issue.format(), file=stream)
    error_count = sum(1 for issue in issues if issue.level == "error")
    if error_count:
        print(f"memory validation failed: {error_count} error(s)", file=sys.stderr)
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


def _add_location(parser) -> None:
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--project-dir", help="project root (default: current directory)")
    location.add_argument(
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
    _add_location(parser)
    parser.set_defaults(func=cmd_install)


def _add_update(subparsers) -> None:
    parser = subparsers.add_parser(
        "update", help="update unmodified locked skills", epilog=EXIT_CODES_HELP
    )
    parser.add_argument("name", nargs="?", help="skill name (default: all locked skills)")
    parser.add_argument("--target", default="all", choices=TARGET_CHOICES)
    parser.add_argument("--yes", action="store_true", help="apply updates from git sources")
    _add_location(parser)
    parser.set_defaults(func=cmd_update)


def _add_uninstall(subparsers) -> None:
    parser = subparsers.add_parser("uninstall", help="remove an unmodified locked skill")
    parser.add_argument("name")
    parser.add_argument("--target", required=True, choices=TARGET_CHOICES)
    _add_location(parser)
    parser.set_defaults(func=cmd_uninstall)


def _add_doctor(subparsers) -> None:
    parser = subparsers.add_parser("doctor", help="read-only diagnostics for installed skills")
    parser.add_argument("--target", default="all", choices=TARGET_CHOICES)
    parser.add_argument("--project-dir", help="project root (default: current directory)")
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
    init_parser.add_argument("--project-dir", help="project root (default: current directory)")
    init_parser.set_defaults(func=cmd_memory_init)
    validate_parser = commands.add_parser("validate", help="check memory format (read-only)")
    validate_parser.add_argument("--project-dir", help="project root (default: current directory)")
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
