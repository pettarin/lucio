"""Execution of block bodies through bash, including the expected-exit policy.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import subprocess

from lucio.errors import ExecutionError, ExecutionTimeoutError, ExitCodeMismatchError
from lucio.model import BlockSegment, ExecutionResult


def execute_block(block: BlockSegment, source: str, timeout: float) -> ExecutionResult:
    """Run the body of ``block`` in its own bash subprocess and capture its streams.

    The body is passed verbatim, nothing is injected; the working directory and the
    environment of the lucio process are inherited; stdin is /dev/null.
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
        raise ExecutionTimeoutError(source, block.line, timeout) from exc
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
