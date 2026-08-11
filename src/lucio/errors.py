"""Error hierarchy for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""


class LucioError(Exception):
    """Base class for all lucio errors, located at a template path and line."""

    def __init__(self, path: str, line: int, message: str) -> None:
        super().__init__(f"{path}:{line}: {message}")
        self.line = line
        self.message = message
        self.path = path

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


class ExecutionError(LucioError):
    """A block could not be executed, or its execution violated the expected exit policy."""


class TemplateError(LucioError):
    """A template could not be processed."""


class ExecutionTimeoutError(ExecutionError):
    """A block did not terminate within the allotted time."""

    def __init__(self, path: str, line: int, timeout: float) -> None:
        super().__init__(path, line, f"block timed out after {timeout} seconds")
        self.timeout = timeout


class ExitCodeMismatchError(ExecutionError):
    """A block exited with a code other than the expected one."""

    def __init__(self, path: str, line: int, expected: int, actual: int, stderr: str) -> None:
        super().__init__(
            path,
            line,
            f"block exited with {actual}, expected {expected}; captured stderr:\n{stderr}",
        )
        self.actual = actual
        self.expected = expected
        self.stderr = stderr


class TemplateSyntaxError(TemplateError):
    """A template violates the lucio fence or attribute grammar."""


class TotalTimeoutError(ExecutionError):
    """The run as a whole outlasted its budget."""

    def __init__(self, path: str, line: int, timeout: float) -> None:
        super().__init__(path, line, f"total timeout of {timeout} seconds exceeded")
        self.timeout = timeout
