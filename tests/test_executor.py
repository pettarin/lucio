"""Tests for the bash executor, exercised against a real bash.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import subprocess
from pathlib import Path

import pytest

from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    ExitCodeMismatchError,
    IncludeError,
)
from lucio.executor import execute_block, include_file
from lucio.model import BlockOptions, BlockSegment

SOURCE = "doc.template.md"


def make_block(body, expected_exit=0, line=1):
    return BlockSegment(
        body=body,
        close_line="```\n",
        fence_char="`",
        fence_length=3,
        indent="",
        line=line,
        options=BlockOptions(expected_exit=expected_exit),
    )


def run(body, expected_exit=0, timeout=10.0):
    return execute_block(make_block(body, expected_exit=expected_exit), SOURCE, timeout)


class TestCapture:
    def test_stdout(self):
        result = run("echo hi\n")
        assert (result.exit_code, result.stdout, result.stderr) == (0, "hi\n", "")

    def test_stderr(self):
        result = run("echo oops >&2\n")
        assert (result.exit_code, result.stdout, result.stderr) == (0, "", "oops\n")

    def test_streams_are_captured_separately(self):
        result = run("echo out\necho err >&2\n")
        assert (result.stdout, result.stderr) == ("out\n", "err\n")

    def test_empty_body_succeeds(self):
        result = run("")
        assert (result.exit_code, result.stdout, result.stderr) == (0, "", "")

    def test_output_without_trailing_newline_is_kept_as_is(self):
        assert run("printf 'no newline'\n").stdout == "no newline"

    def test_invalid_utf8_is_replaced(self):
        assert run("printf '\\xff'\n").stdout == "\ufffd"



class TestProcess:
    def test_body_runs_as_one_process(self):
        assert run("X=42\necho $X\n").stdout == "42\n"

    def test_nothing_is_injected_into_the_body(self):
        assert run("echo $#\n").stdout == "0\n"

    def test_stdin_is_devnull(self):
        result = run("read x\n", expected_exit=None)
        assert result.exit_code != 0

    def test_cwd_is_inherited(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert run("pwd\n").stdout == f"{Path.cwd()}\n"

    def test_environment_is_inherited(self, monkeypatch):
        monkeypatch.setenv("LUCIO_TEST_VARIABLE", "spam")
        assert run("echo $LUCIO_TEST_VARIABLE\n").stdout == "spam\n"

    def test_blocks_do_not_share_shell_state(self):
        run("X=42\n")
        assert run("echo [$X]\n").stdout == "[]\n"


class TestExitPolicy:
    def test_expected_zero_passes(self):
        assert run("true\n").exit_code == 0

    def test_expected_nonzero_passes(self):
        assert run("exit 1\n", expected_exit=1).exit_code == 1

    @pytest.mark.parametrize("code", [0, 1, 7, 42])
    def test_any_exit_code_is_accepted(self, code):
        assert run(f"exit {code}\n", expected_exit=None).exit_code == code

    def test_mismatch_raises(self):
        with pytest.raises(ExitCodeMismatchError) as excinfo:
            execute_block(make_block("echo boom >&2\nexit 3\n", line=12), SOURCE, 10.0)
        error = excinfo.value
        assert (error.path, error.line, error.expected, error.actual) == (SOURCE, 12, 0, 3)
        assert error.stderr == "boom\n"
        assert str(error) == (
            f"{SOURCE}:12: block exited with 3, expected 0; captured stderr:\nboom\n"
        )

    def test_mismatch_against_a_nonzero_expectation(self):
        with pytest.raises(ExitCodeMismatchError) as excinfo:
            execute_block(make_block("true\n", expected_exit=1), SOURCE, 10.0)
        assert (excinfo.value.expected, excinfo.value.actual) == (1, 0)


class TestNoTimeout:
    def test_a_block_runs_without_a_ceiling(self):
        assert run("sleep 0.3\necho done\n", timeout=None).stdout == "done\n"

    def test_none_reaches_the_subprocess(self, mocker):
        completed = mocker.patch(
            "lucio.executor.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )
        execute_block(make_block("echo hi\n"), SOURCE, None)
        assert completed.call_args.kwargs["timeout"] is None


class TestFailures:
    def test_timeout(self):
        with pytest.raises(ExecutionTimeoutError) as excinfo:
            execute_block(make_block("sleep 5\n", line=4), SOURCE, 0.1)
        assert excinfo.value.timeout == 0.1
        assert str(excinfo.value) == f"{SOURCE}:4: block timed out after 0.1 seconds"

    def test_bash_cannot_be_spawned(self, mocker):
        mocker.patch(
            "lucio.executor.subprocess.run",
            side_effect=FileNotFoundError(2, "No such file or directory", "bash"),
        )
        with pytest.raises(ExecutionError) as excinfo:
            execute_block(make_block("echo hi\n", line=2), SOURCE, 10.0)
        assert "cannot run bash" in str(excinfo.value)
        assert excinfo.value.line == 2

    def test_other_os_errors_are_reported_too(self, mocker):
        mocker.patch("lucio.executor.subprocess.run", side_effect=PermissionError("denied"))
        with pytest.raises(ExecutionError, match="cannot run bash"):
            execute_block(make_block("echo hi\n"), SOURCE, 10.0)

    def test_timeout_error_is_not_masked_as_an_os_error(self, mocker):
        mocker.patch(
            "lucio.executor.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=1.5),
        )
        with pytest.raises(ExecutionTimeoutError):
            execute_block(make_block("sleep 5\n"), SOURCE, 1.5)


class TestIncludeFile:
    def test_it_reads_the_file(self, tmp_path):
        (tmp_path / "PART.md").write_text("## Part\n\nText.\n", encoding="utf-8")
        result = include_file(tmp_path / "PART.md", SOURCE, 1)
        assert (result.exit_code, result.stderr) == (0, "")
        assert result.stdout == "## Part\n\nText.\n"

    def test_crlf_is_normalized(self, tmp_path):
        (tmp_path / "PART.md").write_bytes(b"one\r\ntwo\r\n")
        assert include_file(tmp_path / "PART.md", SOURCE, 1).stdout == "one\ntwo\n"

    def test_an_empty_file_reads_as_nothing(self, tmp_path):
        (tmp_path / "PART.md").touch()
        assert include_file(tmp_path / "PART.md", SOURCE, 1).stdout == ""

    def test_a_missing_file_raises(self, tmp_path):
        with pytest.raises(IncludeError) as excinfo:
            include_file(tmp_path / "NOPE.md", SOURCE, 4)
        assert excinfo.value.line == 4
        assert "cannot include" in str(excinfo.value)
        assert "No such file" in str(excinfo.value)

    def test_a_directory_raises(self, tmp_path):
        with pytest.raises(IncludeError, match="cannot include"):
            include_file(tmp_path, SOURCE, 1)

    def test_undecodable_bytes_raise(self, tmp_path):
        (tmp_path / "PART.md").write_bytes(b"\xff\xfe not utf-8\n")
        with pytest.raises(IncludeError, match="not valid UTF-8"):
            include_file(tmp_path / "PART.md", SOURCE, 1)

    def test_it_is_an_execution_error(self, tmp_path):
        with pytest.raises(ExecutionError):
            include_file(tmp_path / "NOPE.md", SOURCE, 1)
