"""End-to-end tests for the command line interface, exercised against a real bash.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import os
import re
import time

import pytest
from click.testing import CliRunner

from lucio import __version__
from lucio.cli import _remaining_timeout, _use_pager, main
from lucio.errors import TotalTimeoutError

ECHO_HI = "```bash lucio command=execute\necho hi\n```\n"
"""The simplest template there is: one execute block printing one line."""
INPUT = "doc.template.md"
OUTPUT = "doc.md"
STDOUT = "-"

_STAMP = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\] ", re.MULTILINE)


def unstamped(text):
    """Return console output without its timestamps, asserting every line carried one."""
    lines = text.splitlines(keepends=True)
    assert all(_STAMP.match(line) for line in lines), text
    return _STAMP.sub("", text)


def settings(
    workspace,
    output=OUTPUT,
    block="60.0 seconds",
    check=False,
    omit=True,
    overwrite=False,
    pager=False,
    remove=False,
    total="300.0 seconds",
):
    """Return the settings lines that -v prints before anything is executed.

    The defaults describe a run through render(), which passes -E, hence omit=True.
    """
    destination = "standard output" if output is None else f'"{(workspace / output).resolve()}"'
    return (
        f'[DEBU] Input file: "{(workspace / INPUT).resolve()}"\n'
        f"[DEBU] Output file: {destination}\n"
        f"[DEBU] Check language: {check}\n"
        f"[DEBU] Omit do-not-edit comment: {omit}\n"
        f"[DEBU] Overwrite files: {overwrite}\n"
        f"[DEBU] Pager: {pager}\n"
        f"[DEBU] Remove do-not-edit comment on include: {remove}\n"
        f"[DEBU] Block timeout: {block}\n"
        f"[DEBU] Total timeout: {total}\n"
    )


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*arguments):
    return CliRunner().invoke(main, list(arguments))


def render(workspace, template, *arguments):
    """Render a template into OUTPUT, without the do-not-edit comment.

    The comment is suppressed so the assertions stay about the rendered document;
    TestEditComment covers the comment itself.
    """
    (workspace / INPUT).write_text(template, encoding="utf-8")
    result = run("-E", *arguments, INPUT, OUTPUT)
    return result, workspace / OUTPUT


class TestOptions:
    @pytest.mark.parametrize("flag", ["-V", "--version"])
    def test_version(self, flag):
        result = run(flag)
        assert result.exit_code == 0
        assert result.stdout == f"lucio, version {__version__}\n"

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help(self, flag):
        result = run(flag)
        assert result.exit_code == 0
        # The help is wrapped to the terminal width, so match on the unwrapped text
        unwrapped = " ".join(result.stdout.split())
        assert "INPUT [OUTPUT]" in unwrapped
        assert "-D, --do-not-color" in unwrapped
        assert "-E, --omit-do-not-edit-comment" in unwrapped
        assert "-O, --overwrite-files" in unwrapped
        assert "-P, --pager" in unwrapped
        assert "-R, --remove-do-not-edit-comment-on-include" in unwrapped
        assert "-b, --block-timeout FLOAT" in unwrapped
        assert "-1 for no timeout. [default: 60.0]" in unwrapped
        assert "-t, --total-timeout FLOAT" in unwrapped
        assert "-1 for no timeout. [default: 300.0]" in unwrapped
        assert "-v, --verbose" in unwrapped
        assert "-V, --version" in unwrapped

    def test_the_console_is_colored_by_default(self, workspace, mocker):
        console = mocker.patch("lucio.cli.setup_console")
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        assert run(INPUT, STDOUT).exit_code == 0
        console.assert_called_once_with(color=True, verbose=False)

    @pytest.mark.parametrize("flag", ["-D", "--do-not-color"])
    def test_the_flag_turns_the_color_off(self, workspace, mocker, flag):
        console = mocker.patch("lucio.cli.setup_console")
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        assert run(flag, INPUT, STDOUT).exit_code == 0
        console.assert_called_once_with(color=False, verbose=False)


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

    @pytest.mark.parametrize("option", ["--no-pager", "-G", "--color", "--no-color", "--timeout"])
    def test_the_removed_spellings(self, workspace, option):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(option, INPUT, OUTPUT)
        assert result.exit_code == 2
        assert "No such option" in result.stderr

    @pytest.mark.parametrize("option", ["-b", "--block-timeout"])
    @pytest.mark.parametrize("timeout", ["0", "-2", "-0.5"])
    def test_non_positive_timeout(self, workspace, option, timeout):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run(option, timeout, INPUT, OUTPUT)
        assert result.exit_code == 2
        assert "must be positive, or -1 for no timeout" in result.stderr


class TestRendering:
    def test_exact_output_bytes(self, workspace):
        result, output = render(
            workspace, "# Title\n\n```bash lucio command=execute\necho hello\n```\n\nDone.\n"
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n```bash\necho hello\nhello\n```\n\nDone.\n"
        )

    def test_merge_false_keeps_the_source_and_the_output_apart(self, workspace):
        result, output = render(
            workspace,
            "# Title\n\n```bash lucio command=execute merge=false\necho hello\n```\n\nDone.\n",
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
        (workspace / INPUT).write_bytes(
            b"# Title\r\n\r\n```bash lucio command=execute\r\necho hi\r\n```\r\n"
        )
        result = run("-E", INPUT, OUTPUT)
        assert result.exit_code == 0
        assert (workspace / OUTPUT).read_bytes() == b"# Title\n\n```bash\necho hi\nhi\n```\n"

    def test_hidden_block_shares_the_working_directory_with_later_blocks(self, workspace):
        template = (
            "# Title\n"
            "\n"
            "```bash lucio command=execute show_source=false stdout=false stderr=false\n"
            "echo spam > side_effect.txt\n"
            "```\n"
            "\n"
            "```bash lucio command=execute\n"
            "cat side_effect.txt\n"
            "```\n"
        )
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n```bash\ncat side_effect.txt\nspam\n```\n"
        )
        assert (workspace / "side_effect.txt").exists()

    def test_include_pastes_the_file_raw(self, workspace):
        (workspace / "OTHER.md").write_text("## Included\n\nSome text.\n", encoding="utf-8")
        template = (
            "# Title\n\n```bash lucio command=include path=OTHER.md style=literal\n"
            "```\n\nThe end.\n"
        )
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "# Title\n\n## Included\n\nSome text.\n\nThe end.\n"
        )

    def test_expected_nonzero_exit(self, workspace):
        result, output = render(workspace, "```bash lucio command=execute exit=1\nfalse\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\nfalse\n```\n"

    def test_stderr_is_captured_in_the_merged_fence(self, workspace):
        result, output = render(workspace, "```bash lucio command=execute\necho oops >&2\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho oops >&2\noops\n```\n"

    def test_backticks_in_the_output_grow_the_fence(self, workspace):
        template = (
            "```bash lucio command=execute show_source=false\n"
            "printf '```bash\\nx\\n```\\n'\n```\n"
        )
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "````\n```bash\nx\n```\n````\n"

    def test_backticks_in_the_output_grow_the_merged_fence(self, workspace):
        template = "```bash lucio command=execute\nprintf '```bash\\nx\\n```\\n'\n```\n"
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            "````bash\nprintf '```bash\\nx\\n```\\n'\n```bash\nx\n```\n````\n"
        )

    def test_output_is_overwritten_when_allowed(self, workspace):
        (workspace / OUTPUT).write_text("stale content\n", encoding="utf-8")
        result, output = render(workspace, ECHO_HI, "--overwrite-files")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_rendering_twice_is_idempotent(self, workspace):
        template = (
            "```bash lucio command=execute show_source=false stdout=false stderr=false\n"
            "rm -f ./generated.txt\n"
            "```\n"
            "\n"
            "```bash lucio command=execute\n"
            "echo hi > generated.txt; cat generated.txt\n"
            "```\n"
        )
        first, output = render(workspace, template)
        first_bytes = output.read_bytes()
        second = run("-E", "--overwrite-files", INPUT, OUTPUT)
        assert (first.exit_code, second.exit_code) == (0, 0)
        assert output.read_bytes() == first_bytes

    def test_nothing_is_written_to_stdout(self, workspace):
        result, _ = render(workspace, ECHO_HI)
        assert result.stdout == ""


class TestStandardOutput:
    def test_rendered_document_goes_to_stdout(self, workspace):
        (workspace / INPUT).write_text(
            "# Title\n\n```bash lucio command=execute\necho hello\n```\n", encoding="utf-8"
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "# Title\n\n```bash\necho hello\nhello\n```\n"
        assert unstamped(result.stderr) == (
            f'[INFO] Rendering "{INPUT}" on the standard output...\n'
            f'[INFO] Rendering "{INPUT}" on the standard output... done\n'
        )

    def test_no_file_is_written(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        assert run("-E", INPUT, STDOUT).exit_code == 0
        assert [path.name for path in workspace.iterdir()] == [INPUT]

    def test_diagnostics_stay_out_of_the_document(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", "-v", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert unstamped(result.stderr) == (
            settings(workspace, output=None)
            + f'[INFO] Rendering "{INPUT}" on the standard output...\n'
            + f"[DEBU] {INPUT}:1: executing bash block\n"
            + f"[DEBU] {INPUT}:1: exit code 0\n"
            + f'[INFO] Rendering "{INPUT}" on the standard output... done\n'
        )

    def test_nothing_is_printed_when_a_block_fails(self, workspace):
        (workspace / INPUT).write_text(
            "```bash lucio command=execute\nexit 3\n```\n", encoding="utf-8"
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 4
        assert result.stdout == ""

    def test_nothing_is_printed_on_a_syntax_error(self, workspace):
        (workspace / INPUT).write_text(
            "```bash lucio command=execute exit=999\necho hi\n```\n", encoding="utf-8"
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 3
        assert result.stdout == ""

    def test_overwrite_files_is_harmless_without_a_file(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", "--overwrite-files", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"

    def test_an_existing_file_named_dash_is_not_touched(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        (workspace / STDOUT).write_text("not the output\n", encoding="utf-8")
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert (workspace / STDOUT).read_text(encoding="utf-8") == "not the output\n"


class TestEditComment:
    TEMPLATE = "# Title\n\n```bash lucio command=execute\necho hi\n```\n"
    DOCUMENT = "# Title\n\n```bash\necho hi\nhi\n```\n"

    def test_the_document_opens_with_the_comment(self, workspace):
        (workspace / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        result = run(INPUT)
        assert result.exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == (
            f"<!-- This file {OUTPUT} has been rendered by CLI tool 'lucio'. "
            f"Do not edit this file, but rather its template {INPUT} . -->\n"
            f"\n{self.DOCUMENT}"
        )

    def test_stdout_gets_the_wording_without_an_output_name(self, workspace):
        (workspace / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        result = run(INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == (
            "<!-- This file has been rendered by CLI tool 'lucio'. "
            f"Do not edit this file, but rather its template {INPUT} . -->\n"
            f"\n{self.DOCUMENT}"
        )

    @pytest.mark.parametrize("flag", ["-E", "--omit-do-not-edit-comment"])
    def test_the_flag_omits_it(self, workspace, flag):
        (workspace / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        result = run(flag, INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.DOCUMENT

    def test_the_flag_omits_it_for_a_file_too(self, workspace):
        (workspace / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        assert run("-E", INPUT).exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == self.DOCUMENT

    def test_a_derived_tmd_destination_is_named(self, workspace):
        (workspace / "doc.tmd").write_text(self.TEMPLATE, encoding="utf-8")
        assert run("doc.tmd").exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8").startswith(
            f"<!-- This file {OUTPUT} has been rendered by CLI tool 'lucio'. "
            "Do not edit this file, but rather its template doc.tmd . -->\n\n"
        )

    def test_the_names_carry_no_directory(self, workspace):
        (workspace / "docs").mkdir()
        (workspace / "docs" / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        assert run(f"docs/{INPUT}").exit_code == 0
        first = (workspace / "docs" / OUTPUT).read_text(encoding="utf-8").splitlines()[0]
        assert "docs/" not in first
        assert f"This file {OUTPUT} has been rendered" in first
        assert f"but rather its template {INPUT} ." in first

    def test_an_empty_document_stays_an_empty_file(self, workspace):
        (workspace / INPUT).write_text(
            "```bash lucio command=execute show_source=false stdout=false stderr=false\n"
            "true\n```\n",
            encoding="utf-8",
        )
        assert run(INPUT).exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == ""

    def test_the_settings_report_the_flag(self, workspace):
        (workspace / INPUT).write_text(self.TEMPLATE, encoding="utf-8")
        plain = unstamped(run("-v", INPUT).stderr)
        assert "[DEBU] Omit do-not-edit comment: False\n" in plain
        omitted = unstamped(run("-v", "-E", "-O", INPUT).stderr)
        assert "[DEBU] Omit do-not-edit comment: True\n" in omitted


class TestPager:
    def test_the_document_goes_through_the_pager_on_a_terminal(self, workspace, mocker):
        mocker.patch("lucio.cli._use_pager", return_value=True)
        paged = mocker.patch("lucio.cli.click.echo_via_pager")
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", "--pager", INPUT, STDOUT)
        assert result.exit_code == 0
        paged.assert_called_once_with("```bash\necho hi\nhi\n```\n")
        assert result.stdout == ""

    @pytest.mark.parametrize("flag", ["-P", "--pager"])
    def test_both_spellings_page(self, workspace, mocker, flag):
        mocker.patch("lucio.cli._use_pager", return_value=True)
        paged = mocker.patch("lucio.cli.click.echo_via_pager")
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        assert run("-E", flag, INPUT, STDOUT).exit_code == 0
        paged.assert_called_once()

    def test_a_redirected_document_is_never_paged(self, workspace, mocker):
        paged = mocker.patch("lucio.cli.click.echo_via_pager")
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", "--pager", INPUT, STDOUT)
        assert result.exit_code == 0
        paged.assert_not_called()
        assert result.stdout == "```bash\necho hi\nhi\n```\n"

    def test_a_file_destination_is_never_paged(self, workspace, mocker):
        mocker.patch("lucio.cli._use_pager", return_value=True)
        paged = mocker.patch("lucio.cli.click.echo_via_pager")
        result, output = render(workspace, ECHO_HI)
        assert result.exit_code == 0
        paged.assert_not_called()
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_the_default_does_not_page(self, workspace, mocker):
        mocker.patch("lucio.cli.sys.stdout.isatty", return_value=True)
        paged = mocker.patch("lucio.cli.click.echo_via_pager")
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        assert run("-E", INPUT, STDOUT).exit_code == 0
        paged.assert_not_called()

    @pytest.mark.parametrize(
        ("pager", "terminal", "expected"),
        [(True, True, True), (True, False, False), (False, True, False), (False, False, False)],
    )
    def test_the_pager_needs_both_the_flag_and_a_terminal(self, mocker, pager, terminal, expected):
        mocker.patch("lucio.cli.sys.stdout").isatty.return_value = terminal
        assert _use_pager(pager) is expected


class TestDerivedOutput:
    @pytest.mark.parametrize("name", ["doc.template.md", "doc.tmd"])
    def test_template_input_renders_into_its_md_sibling(self, workspace, name):
        (workspace / name).write_text(
            "# Title\n\n```bash lucio command=execute\necho hello\n```\n", encoding="utf-8"
        )
        result = run("-E", name)
        assert result.exit_code == 0
        assert result.stdout == ""
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == (
            "# Title\n\n```bash\necho hello\nhello\n```\n"
        )

    def test_the_sibling_stays_in_the_directory_of_the_input(self, workspace):
        (workspace / "docs").mkdir()
        (workspace / "docs" / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", f"docs/{INPUT}")
        assert result.exit_code == 0
        assert (workspace / "docs" / OUTPUT).exists()
        assert not (workspace / OUTPUT).exists()

    @pytest.mark.parametrize("name", [".template.md", ".tmd"])
    def test_a_bare_template_suffix_derives_a_bare_md(self, workspace, name):
        (workspace / name).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", name)
        assert result.exit_code == 0
        assert (workspace / ".md").read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    @pytest.mark.parametrize(
        "name",
        [
            "notes.md",
            "notes.template.txt",
            "notes.md.template",
            "notes.tmd.md",
            "notes.tmdx",
            "notes.tm",
        ],
    )
    def test_any_other_input_still_goes_to_stdout(self, workspace, name):
        (workspace / name).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", name)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert [path.name for path in workspace.iterdir()] == [name]

    def test_a_dash_output_beats_the_derived_name(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == "```bash\necho hi\nhi\n```\n"
        assert not (workspace / OUTPUT).exists()

    def test_an_explicit_output_beats_the_derived_name(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", INPUT, "elsewhere.md")
        assert result.exit_code == 0
        assert (workspace / "elsewhere.md").exists()
        assert not (workspace / OUTPUT).exists()


class TestOverwriteGuard:
    def test_existing_output_is_refused(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, output = render(workspace, ECHO_HI)
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )
        assert output.read_text(encoding="utf-8") == "previous content\n"

    def test_no_block_runs_when_the_output_is_refused(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        template = "```bash lucio command=execute\necho spam > side_effect.txt\n```\n"
        result, _ = render(workspace, template)
        assert result.exit_code == 1
        assert not (workspace / "side_effect.txt").exists()

    def test_an_empty_existing_output_is_refused_too(self, workspace):
        (workspace / OUTPUT).touch()
        result, _ = render(workspace, ECHO_HI)
        assert result.exit_code == 1

    def test_an_existing_derived_output_is_refused(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result = run("-E", INPUT)
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "previous content\n"

    def test_an_output_derived_from_a_tmd_input_is_refused_too(self, workspace):
        (workspace / "doc.tmd").write_text(ECHO_HI, encoding="utf-8")
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result = run("-E", "doc.tmd")
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "previous content\n"
        assert run("-E", "-O", "doc.tmd").exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_no_block_runs_when_the_derived_output_is_refused(self, workspace):
        (workspace / INPUT).write_text(
            "```bash lucio command=execute\necho spam > side_effect.txt\n```\n", encoding="utf-8"
        )
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        assert run(INPUT).exit_code == 1
        assert not (workspace / "side_effect.txt").exists()

    @pytest.mark.parametrize("flag", ["-O", "--overwrite-files"])
    def test_the_flag_frees_the_derived_output(self, workspace, flag):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result = run("-E", flag, INPUT)
        assert result.exit_code == 0
        assert (workspace / OUTPUT).read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_a_missing_output_needs_no_flag(self, workspace):
        result, output = render(workspace, ECHO_HI)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_the_flag_is_harmless_when_the_output_is_missing(self, workspace):
        result, output = render(workspace, ECHO_HI, "--overwrite-files")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"


class TestVerbose:
    def test_each_block_is_logged(self, workspace):
        template = (
            "# Title\n"
            "\n"
            "```bash lucio command=execute\n"
            "echo hi\n"
            "```\n"
            "\n"
            "```bash lucio command=include path=OTHER.md\n"
            "```\n"
        )
        (workspace / "OTHER.md").write_text("## Included\n", encoding="utf-8")
        result, _ = render(workspace, template, "-v")
        assert result.exit_code == 0
        assert unstamped(result.stderr) == (
            settings(workspace)
            + f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"...\n'
            + f"[DEBU] {INPUT}:3: executing bash block\n"
            + f"[DEBU] {INPUT}:3: exit code 0\n"
            + '[DEBU] doc.template.md:7: including "OTHER.md"\n'
            + f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"... done\n'
        )

    @pytest.mark.parametrize(
        ("attributes", "body", "reported"),
        [
            ("exit=1", "false", "exit code 1 (permitted by exit=1)"),
            ("exit=any", "exit 3", "exit code 3 (permitted by exit=any)"),
            ("exit=255", "exit 255", "exit code 255 (permitted by exit=255)"),
            ("exit=any", "exit 1", "exit code 1 (permitted by exit=any)"),
            ("", "echo hi", "exit code 0"),
            ("exit=0", "echo hi", "exit code 0"),
            ("exit=any", "echo hi", "exit code 0"),
        ],
    )
    def test_exit_code_is_reported(self, workspace, attributes, body, reported):
        template = f"```bash lucio command=execute {attributes}\n{body}\n```\n"
        result, _ = render(workspace, template, "--verbose")
        assert result.exit_code == 0
        assert f"[DEBU] {INPUT}:1: {reported}\n" in unstamped(result.stderr)

    @pytest.mark.parametrize("attributes", ["", "exit=0", "exit=any"])
    def test_a_zero_exit_code_is_never_annotated(self, workspace, attributes):
        template = f"```bash lucio command=execute {attributes}\necho hi\n```\n"
        result, _ = render(workspace, template, "--verbose")
        assert result.exit_code == 0
        assert "permitted by" not in result.stderr

    def test_the_settings_open_the_log(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v")
        assert result.exit_code == 0
        assert unstamped(result.stderr).startswith(settings(workspace))

    def test_the_settings_report_an_explicit_output(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", "-v", INPUT, "elsewhere.md")
        assert result.exit_code == 0
        assert unstamped(result.stderr).startswith(settings(workspace, output="elsewhere.md"))

    def test_the_settings_report_the_check_language_flag(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v", "-L")
        assert result.exit_code == 0
        assert unstamped(result.stderr).startswith(settings(workspace, check=True))

    def test_the_settings_report_the_pager_flag(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v", "-P")
        assert result.exit_code == 0
        assert "[DEBU] Pager: True\n" in unstamped(result.stderr)

    def test_the_settings_report_the_overwrite_flag(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v", "-O")
        assert result.exit_code == 0
        assert "[DEBU] Overwrite files: True\n" in unstamped(result.stderr)

    def test_the_settings_report_a_disabled_timeout(self, workspace):
        template = ECHO_HI
        result, _ = render(workspace, template, "-v", "--block-timeout", "-1")
        assert result.exit_code == 0
        assert "[DEBU] Block timeout: none\n" in unstamped(result.stderr)

    def test_the_settings_report_a_custom_timeout(self, workspace):
        template = ECHO_HI
        result, _ = render(workspace, template, "-v", "--block-timeout", "0.5")
        assert result.exit_code == 0
        assert "[DEBU] Block timeout: 0.5 seconds\n" in unstamped(result.stderr)

    def test_the_settings_precede_a_refusal_to_overwrite(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, _ = render(workspace, ECHO_HI, "-v")
        assert result.exit_code == 1
        assert unstamped(result.stderr) == (
            settings(workspace)
            + f"[ERRO] {OUTPUT}: file exists (use --overwrite-files to overwrite)\n"
        )

    def test_only_the_summary_shows_by_default(self, workspace):
        result, _ = render(workspace, ECHO_HI)
        assert unstamped(result.stderr) == (
            f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"...\n'
            f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"... done\n'
        )

    def test_the_summary_is_a_pair(self, workspace):
        result, _ = render(workspace, ECHO_HI)
        assert result.exit_code == 0
        opening = f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"...'
        assert unstamped(result.stderr) == f"{opening}\n{opening} done\n"

    def test_a_failing_run_never_says_done(self, workspace):
        result, output = render(workspace, "```bash lucio command=execute\nexit 3\n```\n")
        assert result.exit_code == 4
        # Not unstamped(): the mismatch message carries the captured stderr over lines
        assert f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"...\n' in result.stderr
        assert "done" not in result.stderr
        assert not output.exists()

    def test_a_refused_run_says_neither(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, _ = render(workspace, ECHO_HI)
        assert result.exit_code == 1
        assert "Rendering" not in result.stderr

    def test_the_pair_names_the_standard_output(self, workspace):
        (workspace / INPUT).write_text(ECHO_HI, encoding="utf-8")
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        opening = f'[INFO] Rendering "{INPUT}" on the standard output...'
        assert unstamped(result.stderr) == f"{opening}\n{opening} done\n"

    def test_the_debug_lines_need_verbose(self, workspace):
        result, _ = render(workspace, ECHO_HI)
        assert "[DEBU]" not in result.stderr


class TestFailures:
    def test_syntax_error_exits_three_and_writes_nothing(self, workspace):
        result, output = render(
            workspace, "text\n\n```bash lucio command=execute exit=999\necho hi\n```\n"
        )
        assert result.exit_code == 3
        assert unstamped(result.stderr) == (
            f'[INFO] Rendering "{INPUT}" into "{OUTPUT}"...\n'
            f"[ERRO] {INPUT}:3: attribute 'exit' must be 'any' or an integer 0-255, "
            "found '999'\n"
        )
        assert not output.exists()

    def test_no_block_runs_when_a_later_block_has_a_syntax_error(self, workspace):
        template = (
            "```bash lucio command=execute\n"
            "echo spam > side_effect.txt\n"
            "```\n"
            "\n"
            "```bash lucio command=execute bad\n"
            "echo hi\n"
            "```\n"
        )
        result, _ = render(workspace, template)
        assert result.exit_code == 3
        assert not (workspace / "side_effect.txt").exists()

    def test_exit_code_mismatch_exits_four_and_keeps_the_old_output(self, workspace):
        (workspace / OUTPUT).write_text("previous content\n", encoding="utf-8")
        result, output = render(
            workspace,
            "```bash lucio command=execute\necho boom >&2\nexit 3\n```\n",
            "--overwrite-files",
        )
        assert result.exit_code == 4
        assert "block exited with 3, expected 0" in result.stderr
        assert "boom" in result.stderr
        assert output.read_text(encoding="utf-8") == "previous content\n"

    def test_timeout_exits_four(self, workspace):
        template = "```bash lucio command=execute\nsleep 5\n```\n"
        result, output = render(workspace, template, "--block-timeout", "0.2")
        assert result.exit_code == 4
        assert "timed out after 0.2 seconds" in result.stderr
        assert not output.exists()

    @pytest.mark.parametrize("option", ["-b", "--block-timeout"])
    def test_no_timeout_lets_a_slow_block_finish(self, workspace, option):
        result, output = render(
            workspace, "```bash lucio command=execute\nsleep 0.3\n```\n", option, "-1"
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\nsleep 0.3\n```\n"

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


class TestInclude:
    INCLUDING = "# Guide\n\n```bash lucio command=include path=PART.md style=literal\n```\n\nEnd.\n"
    PART = "## Part\n\nIncluded text.\n"
    RENDERED = "# Guide\n\n## Part\n\nIncluded text.\n\nEnd.\n"

    def test_the_path_is_relative_to_the_template(self, workspace):
        (workspace / "docs").mkdir()
        (workspace / "docs" / INPUT).write_text(self.INCLUDING, encoding="utf-8")
        (workspace / "docs" / "PART.md").write_text(self.PART, encoding="utf-8")
        # A sibling of the template, not of the working directory
        result = run("-E", f"docs/{INPUT}", STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    def test_a_file_beside_the_working_directory_is_not_found(self, workspace):
        (workspace / "docs").mkdir()
        (workspace / "docs" / INPUT).write_text(self.INCLUDING, encoding="utf-8")
        (workspace / "PART.md").write_text(self.PART, encoding="utf-8")
        result = run(f"docs/{INPUT}", STDOUT)
        assert result.exit_code == 4
        assert "cannot include" in result.stderr

    def test_an_absolute_path_is_taken_as_is(self, workspace):
        (workspace / "elsewhere").mkdir()
        (workspace / "elsewhere" / "PART.md").write_text(self.PART, encoding="utf-8")
        template = (
            "# Guide\n\n```bash lucio command=include "
            f"path={workspace / 'elsewhere' / 'PART.md'} style=literal\n```\n\nEnd.\n"
        )
        (workspace / INPUT).write_text(template, encoding="utf-8")
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    def test_a_quoted_path_may_contain_spaces(self, workspace):
        (workspace / "with spaces").mkdir()
        (workspace / "with spaces" / "PART.md").write_text(self.PART, encoding="utf-8")
        (workspace / INPUT).write_text(
            '# Guide\n\n```bash lucio command=include path="with spaces/PART.md" '
            "style=literal\n```\n\nEnd.\n",
            encoding="utf-8",
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    def test_a_leading_tilde_is_the_home_directory(self, workspace, monkeypatch):
        home = workspace / "home"
        home.mkdir()
        (home / "PART.md").write_text(self.PART, encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))
        (workspace / INPUT).write_text(
            "# Guide\n\n```bash lucio command=include path=~/PART.md style=literal\n```\n\nEnd.\n",
            encoding="utf-8",
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    @pytest.mark.parametrize("written", ["$PARTS/PART.md", "${PARTS}/PART.md"])
    def test_a_variable_is_expanded(self, workspace, monkeypatch, written):
        parts = workspace / "parts"
        parts.mkdir()
        (parts / "PART.md").write_text(self.PART, encoding="utf-8")
        monkeypatch.setenv("PARTS", str(parts))
        (workspace / INPUT).write_text(
            f"# Guide\n\n```bash lucio command=include path={written} style=literal\n```\n\nEnd.\n",
            encoding="utf-8",
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    def test_a_quoted_value_expands_too(self, workspace, monkeypatch):
        parts = workspace / "parts" / "with spaces"
        parts.mkdir(parents=True)
        (parts / "PART.md").write_text(self.PART, encoding="utf-8")
        monkeypatch.setenv("PARTS", str(workspace / "parts"))
        (workspace / INPUT).write_text(
            '# Guide\n\n```bash lucio command=include path="$PARTS/with spaces/PART.md" '
            'style=literal\n```\n\nEnd.\n',
            encoding="utf-8",
        )
        result = run("-E", INPUT, STDOUT)
        assert result.exit_code == 0
        assert result.stdout == self.RENDERED

    def test_an_unset_variable_exits_four(self, workspace, monkeypatch):
        monkeypatch.delenv("NOPE", raising=False)
        template = "```bash lucio command=include path=$NOPE/PART.md style=literal\n```\n"
        result, output = render(workspace, template)
        assert result.exit_code == 4
        assert "environment variable 'NOPE' is not set" in result.stderr
        assert '"$NOPE/PART.md"' in result.stderr
        assert not output.exists()

    @pytest.mark.parametrize("written", ["price$.md", "${BAD-NAME}.md"])
    def test_what_is_not_a_reference_stays_literal(self, workspace, written):
        template = f"```bash lucio command=include path={written} style=literal\n```\n"
        result, _ = render(workspace, template)
        assert result.exit_code == 4
        # Read as written, so it fails on the file rather than on a variable
        assert "No such file" in result.stderr

    def test_the_verbose_line_shows_the_expanded_path(self, workspace, monkeypatch):
        parts = workspace / "parts"
        parts.mkdir()
        (parts / "PART.md").write_text(self.PART, encoding="utf-8")
        monkeypatch.setenv("PARTS", str(parts))
        template = "```bash lucio command=include path=$PARTS/PART.md style=literal\n```\n"
        result, _ = render(workspace, template, "-v")
        assert result.exit_code == 0
        assert f'including "{parts / "PART.md"}"' in result.stderr

    def test_a_missing_file_exits_four_and_writes_nothing(self, workspace):
        result, output = render(workspace, self.INCLUDING)
        assert result.exit_code == 4
        assert 'cannot include "PART.md"' in result.stderr
        assert not output.exists()

    def test_the_old_trigger_is_an_ordinary_fence(self, workspace):
        template = "# Guide\n\n```bash include\ncat PART.md\n```\n"
        result, output = render(workspace, template)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == template

    def test_an_included_file_is_not_rendered_in_turn(self, workspace):
        part = "```bash lucio\necho nope\n```\n"
        (workspace / "PART.md").write_text(part, encoding="utf-8")
        result, output = render(workspace, self.INCLUDING)
        assert result.exit_code == 0
        # Pasted byte for byte: a trigger fence inside it stays text
        assert output.read_text(encoding="utf-8") == f"# Guide\n\n{part}\nEnd.\n"


class TestIncludeStyle:
    CONFIG = "key: value\nlist:\n  - one\n"

    def include(self, workspace, language, attributes="", part=None):
        (workspace / "PART.yaml").write_text(
            self.CONFIG if part is None else part, encoding="utf-8"
        )
        info = f"{language} lucio command=include path=PART.yaml {attributes}".rstrip()
        return render(workspace, f"# Guide\n\n```{info}\n```\n\nEnd.\n")

    def test_an_include_does_not_have_to_name_its_command(self, workspace):
        (workspace / "PART.yaml").write_text(self.CONFIG, encoding="utf-8")
        result, output = render(workspace, "# Guide\n\n```yaml lucio path=PART.yaml\n```\n")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == f"# Guide\n\n```yaml\n{self.CONFIG}```\n"

    def test_the_language_of_the_fence_wraps_the_file(self, workspace):
        result, output = self.include(workspace, "yaml")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            f"# Guide\n\n```yaml\n{self.CONFIG}```\n\nEnd.\n"
        )

    def test_the_language_style_says_the_default_out_loud(self, workspace):
        result, output = self.include(workspace, "yaml", "style=language")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            f"# Guide\n\n```yaml\n{self.CONFIG}```\n\nEnd.\n"
        )

    def test_the_fence_style_drops_the_language(self, workspace):
        result, output = self.include(workspace, "yaml", "style=fence")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            f"# Guide\n\n```\n{self.CONFIG}```\n\nEnd.\n"
        )

    def test_the_literal_style_pastes_the_file(self, workspace):
        result, output = self.include(workspace, "yaml", "style=literal")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == f"# Guide\n\n{self.CONFIG}\nEnd.\n"

    def test_the_fence_grows_around_a_fence_in_the_file(self, workspace):
        part = "```yaml\nkey: value\n```\n"
        result, output = self.include(workspace, "markdown", part=part)
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == (
            f"# Guide\n\n````markdown\n{part}````\n\nEnd.\n"
        )

    @pytest.mark.parametrize("style", ["fence", "language", "literal"])
    def test_an_empty_file_contributes_nothing(self, workspace, style):
        result, output = self.include(workspace, "yaml", f"style={style}", part="")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "# Guide\n\nEnd.\n"


class TestCheckLanguage:
    def template(self, language):
        return f"```{language} lucio command=include path=PART.md\n```\n"

    def test_an_unknown_language_exits_three_and_writes_nothing(self, workspace):
        result, output = render(workspace, self.template("zzz"), "-L")
        assert result.exit_code == 3
        assert f"{INPUT}:1: unknown language 'zzz'" in result.stderr
        assert not output.exists()

    @pytest.mark.parametrize("language", ["yaml", "yml", "md"])
    def test_a_known_language_is_accepted(self, workspace, language):
        (workspace / "PART.md").write_text("text\n", encoding="utf-8")
        result, output = render(workspace, self.template(language), "--check-language")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == f"```{language}\ntext\n```\n"

    def test_no_language_is_checked_without_the_option(self, workspace):
        (workspace / "PART.md").write_text("text\n", encoding="utf-8")
        result, output = render(workspace, self.template("zzz"))
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```zzz\ntext\n```\n"


class TestRemoveEditCommentOnInclude:
    BANNER = (
        "<!-- This file PART.md has been rendered by CLI tool 'lucio'. "
        "Do not edit this file, but rather its template PART.template.md . -->"
    )
    INCLUDING = "# Guide\n\n```bash lucio command=include path=PART.md style=literal\n```\n\nEnd.\n"

    def include(self, workspace, part, *arguments):
        (workspace / "PART.md").write_text(part, encoding="utf-8")
        (workspace / INPUT).write_text(self.INCLUDING, encoding="utf-8")
        result = run("-E", *arguments, INPUT, STDOUT)
        assert result.exit_code == 0
        return result.stdout

    def test_the_banner_and_its_blank_line_go(self, workspace):
        rendered = self.include(workspace, f"{self.BANNER}\n\n## Part\n", "-R")
        assert rendered == "# Guide\n\n## Part\n\nEnd.\n"

    @pytest.mark.parametrize("flag", ["-R", "--remove-do-not-edit-comment-on-include"])
    def test_both_spellings_strip(self, workspace, flag):
        rendered = self.include(workspace, f"{self.BANNER}\n\n## Part\n", flag)
        assert self.BANNER not in rendered

    def test_the_banner_stays_by_default(self, workspace):
        rendered = self.include(workspace, f"{self.BANNER}\n\n## Part\n")
        assert rendered == f"# Guide\n\n{self.BANNER}\n\n## Part\n\nEnd.\n"

    def test_the_standard_output_wording_is_recognized(self, workspace):
        banner = (
            "<!-- This file has been rendered by CLI tool 'lucio'. "
            "Do not edit this file, but rather its template PART.template.md . -->"
        )
        rendered = self.include(workspace, f"{banner}\n\n## Part\n", "-R")
        assert rendered == "# Guide\n\n## Part\n\nEnd.\n"

    def test_without_a_blank_line_only_the_comment_goes(self, workspace):
        rendered = self.include(workspace, f"{self.BANNER}\n## Part\n", "-R")
        assert rendered == "# Guide\n\n## Part\n\nEnd.\n"

    def test_a_file_that_is_only_the_banner_contributes_nothing(self, workspace):
        rendered = self.include(workspace, f"{self.BANNER}\n", "-R")
        assert rendered == "# Guide\n\nEnd.\n"

    @pytest.mark.parametrize(
        "first",
        [
            "<!-- markdownlint-disable -->",
            "<!-- Copyright 2026 Alberto Pettarin -->",
            "<!-- Generated by some-other-tool. Do not edit. -->",
            "## Part",
        ],
    )
    def test_anyone_elses_first_line_survives(self, workspace, first):
        rendered = self.include(workspace, f"{first}\n\nText.\n", "-R")
        assert rendered == f"# Guide\n\n{first}\n\nText.\n\nEnd.\n"

    def test_only_the_first_line_is_considered(self, workspace):
        part = f"## Part\n\n{self.BANNER}\n"
        rendered = self.include(workspace, part, "-R")
        assert self.BANNER in rendered

    def test_it_leaves_the_comment_of_the_run_alone(self, workspace):
        (workspace / "PART.md").write_text(f"{self.BANNER}\n\n## Part\n", encoding="utf-8")
        (workspace / INPUT).write_text(self.INCLUDING, encoding="utf-8")
        result = run("-R", INPUT, STDOUT)
        assert result.exit_code == 0
        # The run writes its own comment, naming this template, and strips the included one
        assert result.stdout.startswith(
            f'<!-- This file has been rendered by CLI tool \'lucio\'. Do not edit this file, '
            f"but rather its template {INPUT} . -->\n\n"
        )
        assert self.BANNER not in result.stdout

    def test_it_is_a_no_op_without_an_include(self, workspace):
        result, output = render(workspace, ECHO_HI, "-R")
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") == "```bash\necho hi\nhi\n```\n"

    def test_the_settings_report_the_flag(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v", "-R")
        assert result.exit_code == 0
        assert "[DEBU] Remove do-not-edit comment on include: True\n" in unstamped(result.stderr)


class TestTotalTimeout:
    SLEEP = "```bash lucio command=execute\nsleep 0.4\n```\n"
    SLOW = f"{SLEEP}\n{SLEEP}"

    def test_the_budget_stops_the_run(self, workspace):
        result, output = render(workspace, self.SLOW, "-t", "0.5")
        assert result.exit_code == 4
        assert "total timeout of 0.5 seconds exceeded" in result.stderr
        assert not output.exists()

    def test_the_total_is_reported_rather_than_the_block(self, workspace):
        result, _ = render(workspace, self.SLOW, "-t", "0.5", "-b", "60")
        assert result.exit_code == 4
        assert "total timeout" in result.stderr
        assert "block timed out" not in result.stderr

    def test_the_run_does_not_outlast_the_budget(self, workspace):
        started = time.monotonic()
        result, _ = render(workspace, self.SLOW, "-t", "0.5", "-b", "-1")
        assert result.exit_code == 4
        # Two 0.4s blocks would take 0.8s; the budget must cut the second one short
        assert time.monotonic() - started < 0.8

    @pytest.mark.parametrize("option", ["-t", "--total-timeout"])
    def test_it_can_be_disabled(self, workspace, option):
        result, output = render(workspace, self.SLOW, option, "-1")
        assert result.exit_code == 0
        assert output.exists()

    def test_a_generous_budget_is_invisible(self, workspace):
        result, output = render(workspace, self.SLOW, "-t", "60")
        assert result.exit_code == 0
        assert output.exists()

    @pytest.mark.parametrize("timeout", ["0", "-2", "-0.5"])
    def test_non_positive_values_are_usage_errors(self, workspace, timeout):
        (workspace / INPUT).write_text("text\n", encoding="utf-8")
        result = run("-t", timeout, INPUT, OUTPUT)
        assert result.exit_code == 2
        assert "must be positive, or -1 for no timeout" in result.stderr

    def test_a_spent_budget_stops_the_next_block(self):
        # Reaching this end to end would need a block to finish exactly on the deadline
        with pytest.raises(TotalTimeoutError) as excinfo:
            _remaining_timeout(60.0, time.monotonic() - 1, INPUT, 3, 5.0)
        assert str(excinfo.value) == f"{INPUT}:3: total timeout of 5.0 seconds exceeded"

    @pytest.mark.parametrize(
        ("block_timeout", "deadline_in", "expected"),
        [
            (60.0, None, 60.0),
            (None, None, None),
            (0.5, 60.0, 0.5),
            (None, 60.0, 60.0),
        ],
    )
    def test_the_ceiling_is_the_smaller_of_the_two(self, block_timeout, deadline_in, expected):
        deadline = None if deadline_in is None else time.monotonic() + deadline_in
        allowed = _remaining_timeout(block_timeout, deadline, INPUT, 1, deadline_in)
        if expected is None:
            assert allowed is None
        else:
            assert allowed == pytest.approx(expected, abs=0.1)

    def test_the_settings_report_both_timeouts(self, workspace):
        result, _ = render(workspace, ECHO_HI, "-v", "-t", "-1")
        assert result.exit_code == 0
        stderr = unstamped(result.stderr)
        assert "[DEBU] Block timeout: 60.0 seconds\n" in stderr
        assert "[DEBU] Total timeout: none\n" in stderr
