"""Tests for the document renderer.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import pytest

from lucio.model import (
    BlockOptions,
    BlockSegment,
    Command,
    ExecutionResult,
    Style,
    VerbatimSegment,
)
from lucio.renderer import fence_for, normalize_stream, render_block, render_document


def make_block(
    body="echo hi\n",
    close_line="```\n",
    command=Command.EXECUTE,
    fence_length=3,
    indent="",
    language="bash",
    line=1,
    **options,
):
    return BlockSegment(
        body=body,
        close_line=close_line,
        fence_char="`",
        fence_length=fence_length,
        indent=indent,
        language=language,
        line=line,
        options=BlockOptions(command=command, **options),
    )


def make_result(stdout="", stderr="", exit_code=0):
    return ExecutionResult(exit_code=exit_code, stderr=stderr, stdout=stdout)


def constant_runner(result=None):
    return lambda block: result if result is not None else make_result()


class TestFenceFor:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("", "```"),
            ("plain output\n", "```"),
            ("a `b` c\n", "```"),
            ("``\n", "```"),
            ("```\n", "````"),
            ("```bash\necho hi\n```\n", "````"),
            ("`````\n", "``````"),
            ("text ```` text\n", "`````"),
            ("one `\ntwo ``\nthree ```\n", "````"),
            ("`" * 10, "`" * 11),
        ],
    )
    def test_fence_length(self, content, expected):
        assert fence_for(content) == expected


class TestNormalizeStream:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("", ""),
            ("\n", ""),
            ("\n\n", ""),
            ("x", "x\n"),
            ("x\n", "x\n"),
            ("x\n\n\n", "x\n"),
            ("a\nb", "a\nb\n"),
            ("a\n\nb\n\n", "a\n\nb\n"),
            ("  ", "  \n"),
        ],
    )
    def test_normalization(self, text, expected):
        assert normalize_stream(text) == expected


class TestRenderBlockExecute:
    """The two-fence rendering, selected with merge=False."""

    def test_source_and_both_streams(self):
        rendered = render_block(
            make_block(merge=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\n```\n\n```\nout\nerr\n```\n"

    def test_source_only_when_streams_are_empty(self):
        assert render_block(make_block(), make_result()) == "```bash\necho hi\n```\n"

    def test_output_only(self):
        rendered = render_block(make_block(show_source=False), make_result(stdout="out\n"))
        assert rendered == "```\nout\n```\n"

    def test_stdout_only(self):
        rendered = render_block(
            make_block(merge=False, stderr=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\n```\n\n```\nout\n```\n"

    def test_stderr_only(self):
        rendered = render_block(
            make_block(merge=False, stdout=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\n```\n\n```\nerr\n```\n"

    def test_stdout_comes_before_stderr(self):
        rendered = render_block(
            make_block(show_source=False), make_result(stdout="1\n2\n", stderr="3\n")
        )
        assert rendered == "```\n1\n2\n3\n```\n"

    def test_all_toggles_off_renders_nothing(self):
        rendered = render_block(
            make_block(show_source=False, stdout=False, stderr=False),
            make_result(stdout="out\n", stderr="err\n"),
        )
        assert rendered == ""

    def test_streams_off_and_source_shown(self):
        rendered = render_block(
            make_block(stdout=False, stderr=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\n```\n"

    def test_empty_stream_produces_no_output_fence(self):
        rendered = render_block(make_block(show_source=False), make_result(stdout="\n\n"))
        assert rendered == ""

    def test_streams_are_normalized(self):
        rendered = render_block(
            make_block(show_source=False), make_result(stdout="out\n\n\n", stderr="err")
        )
        assert rendered == "```\nout\nerr\n```\n"

    def test_source_is_emitted_byte_for_byte(self):
        block = make_block(body="\techo\tx   \n\n", close_line="```   \n")
        assert render_block(block, make_result()) == "```bash\n\techo\tx   \n\n```   \n"

    def test_source_fence_keeps_its_length_and_indent(self):
        block = make_block(
            body="```\nnested\n```\n",
            close_line="  ``````\n",
            fence_length=4,
            indent="  ",
            merge=False,
        )
        rendered = render_block(block, make_result(stdout="out\n"))
        assert rendered == "  ````bash\n```\nnested\n```\n  ``````\n\n```\nout\n```\n"

    def test_output_fence_is_at_column_zero_for_an_indented_source(self):
        block = make_block(indent="   ", close_line="   ```\n", merge=False)
        rendered = render_block(block, make_result(stdout="out\n"))
        assert rendered == "   ```bash\necho hi\n   ```\n\n```\nout\n```\n"

    def test_output_fence_grows_around_backticks(self):
        rendered = render_block(
            make_block(show_source=False), make_result(stdout="```bash\necho hi\n```\n")
        )
        assert rendered == "````\n```bash\necho hi\n```\n````\n"

    def test_empty_body_is_kept(self):
        assert render_block(make_block(body=""), make_result()) == "```bash\n```\n"


class TestRenderBlockMerged:
    """The single-fence rendering, which is the default."""

    def test_source_and_stdout_share_one_fence(self):
        assert render_block(make_block(), make_result(stdout="out\n")) == (
            "```bash\necho hi\nout\n```\n"
        )

    def test_stdout_comes_before_stderr(self):
        rendered = render_block(make_block(), make_result(stdout="out\n", stderr="err\n"))
        assert rendered == "```bash\necho hi\nout\nerr\n```\n"

    def test_streams_are_normalized(self):
        rendered = render_block(make_block(), make_result(stdout="out\n\n\n", stderr="err"))
        assert rendered == "```bash\necho hi\nout\nerr\n```\n"

    def test_excluded_stream_stays_out(self):
        rendered = render_block(
            make_block(stderr=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\nout\n```\n"

    def test_empty_output_leaves_the_source_fence_alone(self):
        block = make_block(close_line="```   \n")
        assert render_block(block, make_result()) == "```bash\necho hi\n```   \n"

    def test_streams_off_leave_the_source_fence_alone(self):
        rendered = render_block(
            make_block(stdout=False, stderr=False), make_result(stdout="out\n", stderr="err\n")
        )
        assert rendered == "```bash\necho hi\n```\n"

    def test_hidden_source_has_nothing_to_merge_into(self):
        rendered = render_block(make_block(show_source=False), make_result(stdout="out\n"))
        assert rendered == "```\nout\n```\n"

    def test_empty_body(self):
        assert render_block(make_block(body=""), make_result(stdout="out\n")) == (
            "```bash\nout\n```\n"
        )

    def test_fence_grows_when_the_output_holds_a_fence(self):
        rendered = render_block(make_block(), make_result(stdout="```\nnested\n```\n"))
        assert rendered == "````bash\necho hi\n```\nnested\n```\n````\n"

    def test_fence_grows_past_the_template_fence(self):
        block = make_block(body="```\nnested\n```\n", close_line="````\n", fence_length=4)
        rendered = render_block(block, make_result(stdout="`````\n"))
        assert rendered == "``````bash\n```\nnested\n```\n`````\n``````\n"

    def test_longer_template_fence_is_kept_with_its_closing_line(self):
        block = make_block(
            body="```\nnested\n```\n", close_line="``````   \n", fence_length=4
        )
        rendered = render_block(block, make_result(stdout="out\n"))
        assert rendered == "````bash\n```\nnested\n```\nout\n``````   \n"

    def test_indented_source_keeps_its_closing_line(self):
        block = make_block(indent="  ", close_line="  ```\n")
        rendered = render_block(block, make_result(stdout="out\n"))
        assert rendered == "  ```bash\necho hi\nout\n  ```\n"

    def test_indented_source_that_grows_keeps_its_indent(self):
        block = make_block(indent="  ", close_line="  ```\n")
        rendered = render_block(block, make_result(stdout="```\nx\n```\n"))
        assert rendered == "  ````bash\necho hi\n```\nx\n```\n  ````\n"


class TestRenderBlockInclude:
    def test_the_default_style_fences_with_the_language(self):
        block = make_block(body="", command=Command.INCLUDE)
        assert render_block(block, make_result(stdout="text\n")) == "```bash\ntext\n```\n"

    def test_the_language_is_the_one_of_the_trigger_fence(self):
        block = make_block(body="", command=Command.INCLUDE, language="yaml")
        assert render_block(block, make_result(stdout="key: 1\n")) == "```yaml\nkey: 1\n```\n"

    def test_the_fence_style_drops_the_language(self):
        block = make_block(body="", command=Command.INCLUDE, language="yaml", style=Style.FENCE)
        assert render_block(block, make_result(stdout="key: 1\n")) == "```\nkey: 1\n```\n"

    def test_the_literal_style_pastes_the_file_raw(self):
        block = make_block(body="", command=Command.INCLUDE, style=Style.LITERAL)
        rendered = render_block(block, make_result(stdout="# Title\n\nSome text.\n"))
        assert rendered == "# Title\n\nSome text.\n"

    def test_the_fence_grows_around_backticks(self):
        block = make_block(body="", command=Command.INCLUDE, language="md")
        rendered = render_block(block, make_result(stdout="```\nnested\n```\n"))
        assert rendered == "````md\n```\nnested\n```\n````\n"

    def test_the_fence_sits_at_column_zero(self):
        block = make_block(body="", command=Command.INCLUDE, indent="  ")
        assert render_block(block, make_result(stdout="text\n")) == "```bash\ntext\n```\n"

    @pytest.mark.parametrize(
        ("style", "expected"),
        [
            (Style.FENCE, "```\ntext\n```\n"),
            (Style.LANGUAGE, "```bash\ntext\n```\n"),
            (Style.LITERAL, "text\n"),
        ],
    )
    def test_stdout_is_normalized(self, style, expected):
        block = make_block(body="", command=Command.INCLUDE, style=style)
        assert render_block(block, make_result(stdout="text\n\n\n")) == expected

    @pytest.mark.parametrize("style", list(Style))
    def test_empty_stdout_renders_nothing(self, style):
        block = make_block(body="", command=Command.INCLUDE, style=style)
        assert render_block(block, make_result(stdout="\n")) == ""

    def test_source_and_stderr_are_ignored(self):
        block = make_block(command=Command.INCLUDE, style=Style.LITERAL)
        assert render_block(block, make_result(stdout="text\n", stderr="warning\n")) == "text\n"


class TestRenderDocument:
    def test_empty_document(self):
        assert render_document([], constant_runner()) == ""

    def test_verbatim_only(self):
        segments = [VerbatimSegment(text="# Title\n\nSome text.\n")]
        assert render_document(segments, constant_runner()) == "# Title\n\nSome text.\n"

    def test_missing_trailing_newline_is_added(self):
        assert render_document([VerbatimSegment(text="text")], constant_runner()) == "text\n"

    def test_extra_trailing_newlines_are_collapsed(self):
        segments = [VerbatimSegment(text="text\n\n\n")]
        assert render_document(segments, constant_runner()) == "text\n"

    def test_visible_block_occupies_the_template_slot(self):
        segments = [
            VerbatimSegment(text="before\n\n"),
            make_block(),
            VerbatimSegment(text="\nafter\n"),
        ]
        rendered = render_document(segments, constant_runner(make_result(stdout="out\n")))
        assert rendered == "before\n\n```bash\necho hi\nout\n```\n\nafter\n"

    def test_unmerged_block_occupies_the_template_slot(self):
        segments = [
            VerbatimSegment(text="before\n\n"),
            make_block(merge=False),
            VerbatimSegment(text="\nafter\n"),
        ]
        rendered = render_document(segments, constant_runner(make_result(stdout="out\n")))
        assert rendered == "before\n\n```bash\necho hi\n```\n\n```\nout\n```\n\nafter\n"

    def test_output_fence_may_abut_the_next_verbatim_line(self):
        segments = [make_block(show_source=False), VerbatimSegment(text="after\n")]
        rendered = render_document(segments, constant_runner(make_result(stdout="out\n")))
        assert rendered == "```\nout\n```\nafter\n"

    @pytest.mark.parametrize(
        ("segments", "expected"),
        [
            pytest.param(
                ["text\n\n", None, "\ntext\n"],
                "text\n\ntext\n",
                id="blank-hidden-blank-collapses-to-one-blank",
            ),
            pytest.param(["text\n", None, "text\n"], "text\ntext\n", id="no-blank-around"),
            pytest.param(["text\n\n", None, "text\n"], "text\n\ntext\n", id="blank-before-only"),
            pytest.param(["text\n", None, "\ntext\n"], "text\n\ntext\n", id="blank-after-only"),
            pytest.param([None, "\ntext\n"], "text\n", id="hidden-at-the-very-top"),
            pytest.param([None, "text\n"], "text\n", id="hidden-at-the-very-top-no-blank"),
            pytest.param(["text\n", None], "text\n", id="hidden-at-the-very-end"),
            pytest.param(["text\n\n", None], "text\n", id="hidden-at-the-very-end-after-blank"),
            pytest.param(
                ["text\n\n", None, None, "\ntext\n"],
                "text\n\ntext\n",
                id="two-adjacent-hidden-blocks",
            ),
            pytest.param(
                ["text\n\n", None, "\n", None, "\ntext\n"],
                "text\n\ntext\n",
                id="hidden-blank-hidden",
            ),
            pytest.param([None], "", id="hidden-only"),
            pytest.param(
                ["text\n\n\n", None, "\ntext\n"],
                "text\n\n\ntext\n",
                id="only-one-blank-is-swallowed",
            ),
        ],
    )
    def test_hidden_block_blank_collapse(self, segments, expected):
        hidden = make_block(show_source=False, stdout=False, stderr=False)
        built = [hidden if item is None else VerbatimSegment(text=item) for item in segments]
        assert render_document(built, constant_runner(make_result(stdout="out\n"))) == expected

    def test_blocks_run_in_document_order(self):
        executed = []

        def runner(block):
            executed.append(block.line)
            return make_result()

        segments = [make_block(line=1), VerbatimSegment(text="x\n"), make_block(line=9)]
        render_document(segments, runner)
        assert executed == [1, 9]

    def test_runner_exceptions_propagate(self):
        def runner(block):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            render_document([make_block()], runner)

    def test_a_failing_block_stops_the_document(self):
        executed = []

        def runner(block):
            executed.append(block.line)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            render_document([make_block(line=1), make_block(line=5)], runner)
        assert executed == [1]

    def test_include_output_is_pasted_between_verbatim_segments(self):
        segments = [
            VerbatimSegment(text="before\n\n"),
            make_block(command=Command.INCLUDE, style=Style.LITERAL),
            VerbatimSegment(text="\nafter\n"),
        ]
        rendered = render_document(segments, constant_runner(make_result(stdout="# Included\n")))
        assert rendered == "before\n\n# Included\n\nafter\n"

    def test_empty_include_collapses_like_a_hidden_block(self):
        segments = [
            VerbatimSegment(text="before\n\n"),
            make_block(command=Command.INCLUDE),
            VerbatimSegment(text="\nafter\n"),
        ]
        assert render_document(segments, constant_runner()) == "before\n\nafter\n"
