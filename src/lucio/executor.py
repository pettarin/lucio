"""Performing the command of a block: bash execution, or reading a file to include.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import subprocess
from pathlib import Path

from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    ExitCodeMismatchError,
    IncludeError,
)
from lucio.model import BlockSegment, ExecutionResult


def execute_block(block: BlockSegment, source: str, timeout: float | None) -> ExecutionResult:
    """Run the body of ``block`` in its own bash subprocess and capture its streams.

    The body is passed verbatim, nothing is injected; the working directory and the
    environment of the lucio process are inherited; stdin is /dev/null. A None timeout
    lets the block run for as long as it needs.
    """
    try:
        process = subprocess.run(
            ["bash", "-c", block.body],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        # exc carries the timeout that expired, which cannot be None here
        raise ExecutionTimeoutError(source, block.line, exc.timeout) from exc
    except OSError as exc:
        raise ExecutionError(source, block.line, f"cannot run bash: {exc}") from exc

    expected = block.options.expected_exit
    if expected is not None and process.returncode != expected:
        raise ExitCodeMismatchError(
            source, block.line, expected, process.returncode, process.stderr
        )
    return ExecutionResult(
        exit_code=process.returncode, stderr=process.stderr, stdout=process.stdout
    )


def include_file(path: Path, source: str, line: int) -> ExecutionResult:
    """Read the file an include block names, as the content it contributes.

    No subprocess is involved, so there is nothing to time out and no exit code to
    check; the result carries the file as its stdout for the renderer to paste.
    """
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        raise IncludeError(source, line, str(path), f"not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise IncludeError(source, line, str(path), exc.strerror or str(exc)) from exc
    return ExecutionResult(exit_code=0, stderr="", stdout=text.replace("\r\n", "\n"))
