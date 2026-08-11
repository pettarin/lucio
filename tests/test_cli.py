"""End-to-end tests for the command line interface, exercised against a real bash.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import os
import re

import pytest
from click.testing import CliRunner

from lucio import __version__
from lucio.cli import main

INPUT = "doc.template.md"
OUTPUT = "doc.md"
STDOUT = "-"

_STAMP = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\] ", re.MULTILINE)


def unstamped(text):
    """Return console output without its timestamps, asserting every line carried one."""
    lines = text.splitlines(keepends=True)
    assert all(_STAMP.match(line) for line in lines), text
    return _STAMP.sub("", text)


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
        assert "INPUT [OUTPUT]" in result.stdout
        assert "-O, --overwrite-files" in result.stdout
        assert "--timeout" in result.stdout
        assert "--verbose" in result.stdout


class TestUsageErrors:
    def test_missing_arguments(self, workspace):
        assert run().exit_code == 2

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

    def test_output_is_overwritten_when_allowed(self, workspace):
        (workspace / OUTPUT).write_text("stale content\n", encoding="utf-8")
        result, output = render(workspace, "```bash lucio\necho hi\n```\n", "--overwrite-files")
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
        second = run("--overwrite-files", INPUT, OUTPUT)
        assert (first.exit_code, second.exit_code) == (0, 0)
        assert output.read_bytes() == first_bytes

    def test_nothing_is_written_to_stdout(self, workspace):
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.stdout == ""


class TestStandardOutput:
    def test_rendered_document_goes_to_stdout(self, workspace):
        (workspace / INPUT).write_text(
            "# Title\n\n```bash lucio\necho hello\n```\n", encoding="utf-8"
        )
        result = run(INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "# Title\n\n```bash\necho hello\nhello\n```\n"
        assert unstamped(result.stderr) == f'[INFO] Rendered "{INPUT}" on the standard output\n'

    def test_no_file_is_written(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        assert run(INPUT, STDOUT).exit_code == 0
        assert [path.name for path in workspace.iterdir()] == [INPUT]

    def test_diagnostics_stay_out_of_the_document(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run("-v", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert unstamped(result.stderr) == (
            f"[DEBU] {INPUT}:1: executing bash lucio block\n"
            f"[DEBU] {INPUT}:1: exit code 0\n"
            f'[INFO] Rendered "{INPUT}" on the standard output\n'
        )

    def test_nothing_is_printed_when_a_block_fails(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\nexit 3\n```\n", encoding="utf-8")
        result = run(INPUT, STDOUT)
        assert result.exit_code == 4
        assert result.stdout == ""

    def test_nothing_is_printed_on_a_syntax_error(self, workspace):
        (workspace / INPUT).write_text("```bash lucio exit=999\necho hi\n```\n", encoding="utf-8")
        result = run(INPUT, STDOUT)
        assert result.exit_code == 3
        assert result.stdout == ""

    def test_overwrite_files_is_harmless_without_a_file(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run("--overwrite-files", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"

    def test_an_existing_file_named_dash_is_not_touched(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        (workspace / STDOUT).write_text("not the output\n", encoding="utf-8")
        result = run(INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert (workspace / STDOUT).read_text(encoding="utf-8") == "not the output\n"


class TestDerivedOutput:
    def test_template_input_renders_into_its_md_sibling(self, workspace):
        (workspace / INPUT).write_text(
            "# Title\n\n```bash lucio\necho hello\n```\n", encoding="utf-8"
        )
        result = run(INPUT)
        assert result.exit_code == 0
        assert result.stdout == ""
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == (
            "# Title\n\n```bash\necho hello\nhello\n```\n"
        )

    def test_the_sibling_stays_in_the_directory_of_the_input(self, workspace):
        (workspace / "docs").mkdir()
        (workspace / "docs" / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run(f"docs/{INPUT}")
        assert result.exit_code == 0
        assert (workspace / "docs" / OUTPUT).exists()
        assert not (workspace / OUTPUT).exists()

    def test_a_bare_template_suffix_derives_a_bare_md(self, workspace):
        (workspace / ".template.md").write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run(".template.md")
        assert result.exit_code == 0
        assert (workspace / ".md").read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    @pytest.mark.parametrize("name", ["notes.md", "notes.template.txt", "notes.md.template"])
    def test_any_other_input_still_goes_to_stdout(self, workspace, name):
        (workspace / name).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run(name)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert [path.name for path in workspace.iterdir()] == [name]

    def test_a_dash_output_beats_the_derived_name(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run(INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert not (workspace / OUTPUT).exists()

    def test_an_explicit_output_beats_the_derived_name(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        result = run(INPUT, "elsewhere.md")
        assert result.exit_code == 0
        assert (workspace / "elsewhere.md").exists()
        assert not (workspace / OUTPUT).exists()


class TestOverwriteGuard:
    def test_existing_output_is_refused(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, output = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )
        assert output.read_text(encoding="utf-8") == "previous content\n"

    def test_no_block_runs_when_the_output_is_refused(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        template = "```bash lucio\necho spam > side_effect.txt\n```\n"
        result, _ = render(workspace, template)
        assert result.exit_code == 1
        assert not (workspace / "side_effect.txt").exists()

    def test_an_empty_existing_output_is_refused_too(self, workspace):
        (workspace / OUTPUT).touch()
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.exit_code == 1

    def test_an_existing_derived_output_is_refused(self, workspace):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result = run(INPUT)
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "previous content\n"

    def test_no_block_runs_when_the_derived_output_is_refused(self, workspace):
        (workspace / INPUT).write_text(
            "```bash lucio\necho spam > side_effect.txt\n```\n", encoding="utf-8"
        )
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        assert run(INPUT).exit_code == 1
        assert not (workspace / "side_effect.txt").exists()

    @pytest.mark.parametrize("flag", ["-O", "--overwrite-files"])
    def test_the_flag_frees_the_derived_output(self, workspace, flag):
        (workspace / INPUT).write_text("```bash lucio\necho hi\n```\n", encoding="utf-8")
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result = run(flag, INPUT)
        assert result.exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_a_missing_output_needs_no_flag(self, workspace):
        result, output = render(workspace, "```bash lucio\necho hi\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_the_flag_is_harmless_when_the_output_is_missing(self, workspace):
        result, output = render(workspace, "```bash lucio\necho hi\n```\n", "--overwrite-files")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"


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
        assert unstamped(result.stderr) == (
            f"[DEBU] {INPUT}:3: executing bash lucio block\n"
            f"[DEBU] {INPUT}:3: exit code 0\n"
            f"[DEBU] {INPUT}:7: executing bash include block\n"
            f"[DEBU] {INPUT}:7: exit code 0\n"
            f'[INFO] Rendered "{INPUT}" into "{OUTPUT}"\n'
        )

    def test_exit_code_is_reported(self, workspace):
        result, _ = render(workspace, "```bash lucio exit=any\nexit 3\n```\n", "--verbose")
        assert result.exit_code == 0
        assert f"[DEBU] {INPUT}:1: exit code 3\n" in unstamped(result.stderr)

    def test_only_the_summary_shows_by_default(self, workspace):
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert unstamped(result.stderr) == f'[INFO] Rendered "{INPUT}" into "{OUTPUT}"\n'

    def test_the_debug_lines_need_verbose(self, workspace):
        result, _ = render(workspace, "```bash lucio\necho hi\n```\n")
        assert "[DEBU]" not in result.stderr


class TestFailures:
    def test_syntax_error_exits_three_and_writes_nothing(self, workspace):
        result, output = render(workspace, "text\n\n```bash lucio exit=999\necho hi\n```\n")
        assert result.exit_code == 3
        assert unstamped(result.stderr) == (
            f"[ERRO] {INPUT}:3: attribute 'exit' must be 'any' or an integer 0-255, "
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
        result, output = render(
            workspace, "```bash lucio\necho boom >&2\nexit 3\n```\n", "--overwrite-files"
        )
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
        assert f"[ERRO] {INPUT}: disk on fire" in unstamped(result.stderr)

    def test_unwritable_output_exits_one(self, workspace):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(INPUT, "missing_directory/doc.md")
        assert result.exit_code == 1
        assert "[ERRO] missing_directory/doc.md" in unstamped(result.stderr)
