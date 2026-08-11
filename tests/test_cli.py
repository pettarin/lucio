"""End-to-end tests for the command line interface, exercised against a real bash.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import os

import pytest
from click.testing import CliRunner

from lucio import __version__
from lucio.cli import main

INPUT = "doc.template.md"
OUTPUT = "doc.md"


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*arguments):
    return CliRunner().invoke(main, list(arguments))


def render(workspace, template, *arguments):
    (workspace / INPUT).write_text(template, encoding="utf-8")
    result = run(*arguments, INPUT, OUTPUT)
    return result, workspace / OUTPUT


class TestOptions:
    def test_version(self):
        result = run("--version")
        assert result.exit_code == 0
        assert result.stdout == f"lucio, version {__version__}\n"

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help(self, flag):
        result = run(flag)
        assert result.exit_code == 0
        assert "INPUT OUTPUT" in result.stdout
        assert "--timeout" in result.stdout
        assert "--verbose" in result.stdout


class TestUsageErrors:
    @pytest.mark.parametrize("arguments", [(), (INPUT,)])
    def test_missing_arguments(self, workspace, arguments):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        assert run(*arguments).exit_code == 2

    def test_nonexistent_input(self, workspace):
        assert run("missing.template.md", OUTPUT).exit_code == 2

    def test_input_is_a_directory(self, workspace):
        assert run(str(workspace), OUTPUT).exit_code == 2

    @pytest.mark.parametrize("output", [INPUT, f"./{INPUT}"])
    def test_input_equals_output(self, workspace, output):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(INPUT, output)
        assert result.exit_code == 2
        assert "must be different" in result.stderr

    def test_input_equals_output_through_an_absolute_path(self, workspace):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(INPUT, str(workspace / INPUT))
        assert result.exit_code == 2

    @pytest.mark.parametrize("timeout", ["0", "-1"])
    def test_non_positive_timeout(self, workspace, timeout):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        assert run("--timeout", timeout, INPUT, OUTPUT).exit_code == 2


class TestRendering:
    def test_exact_output_bytes(self, workspace):
        result, output = render(
            workspace, "# Title\n\n```bash lucio\necho hello\n```\n\nDone.\n"
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n```bash\necho hello\nhello\n```\n\nDone.\n"
        )

    def test_merge_false_keeps_the_source_and_the_output_apart(self, workspace):
        result, output = render(
            workspace, "# Title\n\n```bash lucio merge=False\necho hello\n```\n\nDone.\n"
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n```bash\necho hello\n```\n\n```\nhello\n```\n\nDone.\n"
        )

    def test_trigger_free_template_is_byte_identical(self, workspace):
        template = (
            "# Title\n"
            "\n"
            "Text with\ta tab and trailing spaces   \n"
            "\n"
            "<!-- include OTHER.md -->\n"
            "\n"
            "```\n"
            "plain code\n"
            "```\n"
            "\n"
            "```python\n"
            "print('lucio')\n"
            "```\n"
            "\n"
            "~~~\n"
            "```bash lucio\n"
            "echo hi\n"
            "```\n"
            "~~~\n"
            "\n"
            "   ```bash\n"
            "   indented fence\n"
            "   ```\n"
            "\n"
            "    ```bash lucio\n"
            "    four spaces, not a fence\n"
            "    ```\n"
            "\n"
            "The end.\n"
        )
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_bytes() == template.encode("utf-8")

    def test_crlf_is_normalized_to_lf(self, workspace):
        (workspace / INPUT).write_bytes(b"# Title\r\n\r\n```bash lucio\r\necho hi\r\n```\r\n")
        result = run(INPUT, OUTPUT)
        assert result.exit_code == 0
        assert (workspace / OUTPUT).read_bytes() == b"# Title\n\n```bash\necho hi\nhi\n```\n"

    def test_hidden_block_shares_the_working_directory_with_later_blocks(self, workspace):
        template = (
            "# Title\n"
            "\n"
            "```bash lucio show_source=False stdout=False stderr=False\n"
            "echo spam > side_effect.txt\n"
            "```\n"
            "\n"
            "```bash lucio\n"
            "cat side_effect.txt\n"
            "```\n"
        )
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n```bash\ncat side_effect.txt\nspam\n```\n"
        )
        assert (workspace / "side_effect.txt").exists()

    def test_include_pastes_stdout_raw(self, workspace):
        (workspace / "OTHER.md").write_text("## Included\n\nSome text.\n", encoding="utf-8")
        template = "# Title\n\n```bash include\ncat OTHER.md\n```\n\nThe end.\n"
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n## Included\n\nSome text.\n\nThe end.\n"
        )

    def test_expected_nonzero_exit(self, workspace):
        result, output = render(workspace, "```bash lucio exit=1\nfalse\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\nfalse\n```\n"

    def test_stderr_is_captured_in_the_merged_fence(self, workspace):
        result, output = render(workspace, "```bash lucio\necho oops >&2\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho oops >&2\noops\n```\n"

    def test_backticks_in_the_output_grow_the_fence(self, workspace):
        template = "```bash lucio show_source=False\nprintf '```bash\\nx\\n```\\n'\n```\n"
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "````\n```bash\nx\n```\n````\n"

    def test_backticks_in_the_output_grow_the_merged_fence(self, workspace):
        template = "```bash lucio\nprintf '```bash\\nx\\n```\\n'\n```\n"
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "````bash\nprintf '```bash\\nx\\n```\\n'\n```bash\nx\n```\n````\n"
        )

    def test_output_is_overwritten(self, workspace):
        (workspace / OUTPUT).write_text("stale content\n", encoding="utf-8")
        result, output = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_rendering_twice_is_idempotent(self, workspace):
        template = (
            "```bash lucio show_source=False stdout=False stderr=False\n"
            "rm -f ./generated.txt\n"
            "```\n"
            "\n"
            "```bash lucio\n"
            "echo hi > generated.txt; cat generated.txt\n"
            "```\n"
        )
        first, output = render(workspace, template)
        first_bytes = output.read_bytes()
        second = run(INPUT, OUTPUT)
        assert (first.exit_code, second.exit_code) == (0, 0)
        assert output.read_bytes() == first_bytes

    def test_nothing_is_written_to_stdout(self, workspace):
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.stdout == ""


class TestVerbose:
    def test_each_block_is_logged(self, workspace):
        template = (
            "# Title\n"
            "\n"
            "```bash lucio\n"
            "echo hi\n"
            "```\n"
            "\n"
            "```bash include\n"
            "echo '## Included'\n"
            "```\n"
        )
        result, _ = render(workspace, template, "-v")
        assert result.exit_code == 0
        assert result.stderr == (
            f"lucio: {INPUT}:3: executing bash lucio block\n"
            f"lucio: {INPUT}:3: exit code 0\n"
            f"lucio: {INPUT}:7: executing bash include block\n"
            f"lucio: {INPUT}:7: exit code 0\n"
        )

    def test_exit_code_is_reported(self, workspace):
        result, _ = render(workspace, "```bash lucio exit=any\nexit 3\n```\n", "--verbose")
        assert result.exit_code == 0
        assert f"lucio: {INPUT}:1: exit code 3\n" in result.stderr

    def test_quiet_by_default(self, workspace):
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.stderr == ""


class TestFailures:
    def test_syntax_error_exits_three_and_writes_nothing(self, workspace):
        result, output = render(workspace, "text\n\n```bash lucio exit=999\necho hi\n```\n")
        assert result.exit_code == 3
        assert result.stderr == (
            f"lucio: error: {INPUT}:3: attribute 'exit' must be 'any' or an integer 0-255, "
            "found '999'\n"
        )
        assert not output.exists()

    def test_no_block_runs_when_a_later_block_has_a_syntax_error(self, workspace):
        template = (
            "```bash lucio\n"
            "echo spam > side_effect.txt\n"
            "```\n"
            "\n"
            "```bash lucio bad\n"
            "echo hi\n"
            "```\n"
        )
        result, _ = render(workspace, template)
        assert result.exit_code == 3
        assert not (workspace / "side_effect.txt").exists()

    def test_exit_code_mismatch_exits_four_and_keeps_the_old_output(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, output = render(workspace, "```bash lucio\necho boom >&2\nexit 3\n```\n")
        assert result.exit_code == 4
        assert "block exited with 3, expected 0" in result.stderr
        assert "boom" in result.stderr
        assert output.read_text(encoding="utf-8") == "previous content\n"

    def test_timeout_exits_four(self, workspace):
        result, output = render(workspace, "```bash lucio\nsleep 5\n```\n", "--timeout", "0.2")
        assert result.exit_code == 4
        assert "timed out after 0.2 seconds" in result.stderr
        assert not output.exists()

    def test_undecodable_input_exits_three(self, workspace):
        (workspace / INPUT).write_bytes(b"# Title\n\n\xff\xfe not utf-8\n")
        result = run(INPUT, OUTPUT)
        assert result.exit_code == 3
        assert "not valid UTF-8" in result.stderr
        assert not (workspace / OUTPUT).exists()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
    def test_unreadable_input_is_a_usage_error(self, workspace):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        (workspace / INPUT).chmod(0o000)
        result = run(INPUT, OUTPUT)
        assert result.exit_code == 2

    def test_unexpected_read_failure_exits_three(self, workspace, mocker):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        mocker.patch("pathlib.Path.open", side_effect=OSError("disk on fire"))
        result = run(INPUT, OUTPUT)
        assert result.exit_code == 3
        assert f"lucio: error: {INPUT}: disk on fire" in result.stderr

    def test_unwritable_output_exits_one(self, workspace):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(INPUT, "missing_directory/doc.md")
        assert result.exit_code == 1
        assert "lucio: error: missing_directory/doc.md" in result.stderr
