"""Stable exit codes and the error type shared by core modules."""

EXIT_OK = 0
EXIT_FAILURE = 1  # validation failed, diagnostics with errors, generic failure
EXIT_USAGE = 2  # invalid arguments (argparse also uses 2)
EXIT_CONFLICT = 3  # destination exists with different content
EXIT_IO = 4  # filesystem or permission failure
EXIT_BUSY = 5  # another operation holds a reservation/lock; retry later


class EngkitError(Exception):
    """An actionable, user-facing failure with a stable exit code."""

    def __init__(self, message: str, exit_code: int = EXIT_FAILURE):
        super().__init__(message)
        self.exit_code = exit_code
