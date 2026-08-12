"""Tests for the template parser.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

from pathlib import Path

import pytest

from lucio.errors import TemplateSyntaxError
from lucio.model import BlockOptions, BlockSegment, Command, Style, VerbatimSegment
from lucio.parser import parse_template

SOURCE = "doc.template.md"


def parse(text):
    return parse_template(text, SOURCE)


def only_block(text):
    segments = parse(text)
    assert len(segments) == 1
    assert isinstance(segments[0], BlockSegment)
    return segments[0]


class TestVerbatim:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "plain text\n",
            "no trailing newline",
            "\n\n\n",
            "a line with\ta tab and trailing spaces   \n",
            "<!-- include CONFIGURATION_FILE.md -->\n",
            "text with `inline code` and ``double backticks``\n",
            "```\nplain code\n```\n",
            "```python\nprint('lucio')\n```\n",
            "```bash\necho hi\n```\n",
            "```bash lucioX\necho hi\n```\n",
            "```bash includeX\necho hi\n```\n",
            "```bash run lucio\necho hi\n```\n",
            "```bash foo include\necho hi\n```\n",
            "```lucio\nbody\n```\n",
            "```include\nbody\n```\n",
            "~~~\nbody\n~~~\n",
            "~~~python\nbody\n~~~\n",
            "~~~bash\nbody\n~~~\n",
            " ```bash\nbody\n ```\n",
            "  ```bash\nbody\n```\n",
            "   ```bash\nbody\n   ```\n",
            "    ```bash lucio\n    echo hi\n    ```\n",
            "``` `bash lucio` ```\n",
            "````\n```bash lucio\necho hi\n```\n````\n",
            "~~~\n```bash lucio\necho hi\n```\n~~~\n",
            "`````markdown\n```bash include\ncat FILE.md\n```\n`````\n",
            "```bash include\ncat FILE.md\n```\n",
            "~~~bash include\ncat FILE.md\n~~~\n",
            "```text include\ncat FILE.md\n```\n",
        ],
    )
    def test_passthrough_is_one_verbatim_segment(self, text):
        segments = parse(text)
        assert segments == ([VerbatimSegment(text=text)] if text else [])

    def test_verbatim_text_joins_back_to_the_template(self):
        text = "# Title\n\nSome text.\n\n```bash\necho hi\n```\n\nMore text.\n"
        assert "".join(segment.text for segment in parse(text)) == text


class TestTrigger:
    def test_bare_lucio_uses_the_defaults(self):
        block = only_block("```bash lucio\necho hi\n```\n")
        assert block == BlockSegment(
            body="echo hi\n",
            close_line="```\n",
            fence_char="`",
            fence_length=3,
            indent="",
            language="bash",
            line=1,
            options=BlockOptions(),
        )

    def test_include_reads_a_path(self):
        block = only_block("```bash lucio command=include path=PART.md\n```\n")
        assert block.options == BlockOptions(command=Command.INCLUDE, path=Path("PART.md"))
        assert block.body == ""

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("style=fence", Style.FENCE),
            ("style=language", Style.LANGUAGE),
            ("style=literal", Style.LITERAL),
            ('style="fence"', Style.FENCE),
            ("", Style.LANGUAGE),
        ],
    )
    def test_the_include_style(self, written, expected):
        block = only_block(f"```bash lucio command=include path=P.md {written}\n```\n")
        assert block.options.style is expected

    @pytest.mark.parametrize(
        ("info", "expected"),
        [
            ("bash lucio", BlockOptions()),
            ("bash lucio command=execute", BlockOptions(command=Command.EXECUTE)),
            ('bash lucio command="execute"', BlockOptions(command=Command.EXECUTE)),
            ('bash lucio stdout="true"', BlockOptions(stdout=True)),
            ('bash lucio stdout="false"', BlockOptions(stdout=False)),
            ('bash lucio exit="1"', BlockOptions(expected_exit=1)),
            ('bash lucio exit="any"', BlockOptions(expected_exit=None)),
            ("bash lucio merge=false", BlockOptions(merge=False)),
            ("bash lucio merge=true", BlockOptions(merge=True)),
            ("bash lucio show_source=false", BlockOptions(show_source=False)),
            ("bash lucio show_source=true", BlockOptions(show_source=True)),
            ("bash lucio stdout=false", BlockOptions(stdout=False)),
            ("bash lucio stderr=false", BlockOptions(stderr=False)),
            ("bash lucio exit=any", BlockOptions(expected_exit=None)),
            ("bash lucio exit=0", BlockOptions(expected_exit=0)),
            ("bash lucio exit=1", BlockOptions(expected_exit=1)),
            ("bash lucio exit=7", BlockOptions(expected_exit=7)),
            ("bash lucio exit=255", BlockOptions(expected_exit=255)),
            (
                "bash lucio show_source=false stdout=false stderr=false",
                BlockOptions(show_source=False, stdout=False, stderr=False),
            ),
            (
                "bash lucio command=execute exit=any stdout=false",
                BlockOptions(expected_exit=None, stdout=False),
            ),
            (
                "bash lucio stderr=false show_source=false exit=2",
                BlockOptions(expected_exit=2, show_source=False, stderr=False),
            ),
            (
                "bash lucio merge=false stdout=false",
                BlockOptions(merge=False, stdout=False),
            ),
            (
                "bash lucio command=execute exit=any merge=false show_source=false "
                "stderr=false stdout=false",
                BlockOptions(
                    expected_exit=None,
                    merge=False,
                    show_source=False,
                    stderr=False,
                    stdout=False,
                ),
            ),
        ],
    )
    def test_attributes(self, info, expected):
        assert only_block(f"```{info}\necho hi\n```\n").options == expected

    @pytest.mark.parametrize(
        "written",
        ["PART.md", "docs/PART.md", "/abs/PART.md", "../up/PART.md", "with.dots.PART.md"],
    )
    def test_the_path_is_kept_as_written(self, written):
        block = only_block(f"```bash lucio command=include path={written}\n```\n")
        assert block.options == BlockOptions(command=Command.INCLUDE, path=Path(written))

    @pytest.mark.parametrize(
        "written",
        [
            "/path/with spaces/FILE.md",
            "with spaces.md",
            "it's here.md",
            "  leading and trailing  ",
            "PART.md",
        ],
    )
    def test_a_quoted_path_keeps_what_is_inside_the_quotes(self, written):
        block = only_block(f'```bash lucio command=include path="{written}"\n```\n')
        assert block.options == BlockOptions(command=Command.INCLUDE, path=Path(written))

    @pytest.mark.parametrize("written", ["~/PART.md", "$PARTS/PART.md", "${PARTS}/PART.md"])
    def test_the_path_is_not_expanded_here(self, written):
        # Expanding is the CLI's business; the model records what the template says
        block = only_block(f"```bash lucio command=include path={written}\n```\n")
        assert block.options.path == Path(written)

    def test_a_single_quote_is_an_ordinary_character(self):
        # It does not quote, so the token still ends at the space and the rest is junk
        with pytest.raises(TemplateSyntaxError, match="malformed attribute token 'b.md''"):
            parse("```bash lucio command=include path='a b.md'\n```\n")

    def test_a_quoted_value_may_hold_the_separator_of_another(self):
        block = only_block('```bash lucio command=include path="a=b c.md"\n```\n')
        assert block.options.path == Path("a=b c.md")

    @pytest.mark.parametrize(
        "info",
        [
            "bash lucio",
            " bash lucio",
            "bash  lucio",
            "bash lucio ",
            "\tbash\tlucio\t",
            "  bash   lucio   stdout=false  ",
        ],
    )
    def test_info_string_whitespace_is_tolerated(self, info):
        block = only_block(f"```{info}\necho hi\n```\n")
        assert block.options.command is Command.EXECUTE

    @pytest.mark.parametrize("indent", ["", " ", "  ", "   "])
    def test_indent_is_captured(self, indent):
        block = only_block(f"{indent}```bash lucio\necho hi\n{indent}```\n")
        assert block.indent == indent

    def test_longer_closing_fence_is_kept_verbatim(self):
        block = only_block("````bash lucio\necho hi\n``````   \n")
        assert block.fence_length == 4
        assert block.close_line == "``````   \n"

    def test_body_is_byte_exact(self):
        block = only_block("```bash lucio\n\techo\tx   \n\n  echo y\n```\n")
        assert block.body == "\techo\tx   \n\n  echo y\n"

    def test_empty_body(self):
        assert only_block("```bash lucio\n```\n").body == ""

    def test_body_may_contain_shorter_fences(self):
        block = only_block("````bash lucio\n```\nnested\n```\n````\n")
        assert block.body == "```\nnested\n```\n"

    def test_closing_fence_without_trailing_newline_is_terminated(self):
        assert only_block("```bash lucio\necho hi\n```").close_line == "```\n"

    def test_line_number_is_that_of_the_opening_fence(self):
        text = "# Title\n\nSome text.\n\n```bash lucio\necho hi\n```\n"
        segments = parse(text)
        assert isinstance(segments[1], BlockSegment)
        assert segments[1].line == 5

    def test_line_numbers_after_a_verbatim_fence(self):
        text = "```\nplain\n```\n\n```bash lucio\necho hi\n```\n"
        segments = parse(text)
        assert isinstance(segments[1], BlockSegment)
        assert segments[1].line == 5

    def test_mixed_document_segment_sequence(self):
        text = (
            "# Title\n"
            "\n"
            "```bash lucio\n"
            "echo one\n"
            "```\n"
            "\n"
            "Middle text.\n"
            "\n"
            "```bash lucio command=include path=PART.md\n"
            "```\n"
            "\n"
            "The end.\n"
        )
        segments = parse(text)
        assert [type(segment) for segment in segments] == [
            VerbatimSegment,
            BlockSegment,
            VerbatimSegment,
            BlockSegment,
            VerbatimSegment,
        ]
        assert segments[0].text == "# Title\n\n"
        assert segments[1].options.command is Command.EXECUTE
        assert segments[2].text == "\nMiddle text.\n\n"
        assert segments[3].options.command is Command.INCLUDE
        assert segments[3].line == 9
        assert segments[4].text == "\nThe end.\n"

    def test_two_adjacent_blocks(self):
        text = "```bash lucio\necho one\n```\n```bash lucio\necho two\n```\n"
        segments = parse(text)
        assert [type(segment) for segment in segments] == [BlockSegment, BlockSegment]
        assert [segment.line for segment in segments] == [1, 4]

    def test_block_at_end_without_trailing_newline(self):
        segments = parse("text\n```bash lucio\necho hi\n```")
        assert [type(segment) for segment in segments] == [VerbatimSegment, BlockSegment]


class TestLanguage:
    @pytest.mark.parametrize("language", ["bash", "yaml", "json", "python", "zzz"])
    def test_an_include_carries_any_language(self, language):
        block = only_block(f"```{language} lucio command=include path=P.md\n```\n")
        assert block.language == language

    def test_the_language_reaches_the_segment_of_an_execute_block(self):
        assert only_block("```bash lucio\necho hi\n```\n").language == "bash"

    @pytest.mark.parametrize(
        "info",
        [
            "python lucio",
            "yaml lucio",
            "yaml lucio command=execute",
            "Bash lucio",
            "bash4 lucio",
        ],
    )
    def test_an_execute_block_requires_bash(self, info):
        with pytest.raises(TemplateSyntaxError, match="requires language 'bash'"):
            parse(f"```{info}\necho hi\n```\n")

    @pytest.mark.parametrize("language", ["yaml", "yml", "js", "sh", "YAML"])
    def test_a_known_language_passes_the_check(self, language):
        text = f"```{language} lucio command=include path=P.md\n```\n"
        segments = parse_template(text, SOURCE, check_language=True)
        assert len(segments) == 1

    @pytest.mark.parametrize("language", ["zzz", "yamll", "not-a-language"])
    def test_an_unknown_language_fails_the_check(self, language):
        text = f"```{language} lucio command=include path=P.md\n```\n"
        with pytest.raises(TemplateSyntaxError) as excinfo:
            parse_template(text, SOURCE, check_language=True)
        assert f"unknown language '{language}'" in str(excinfo.value)
        assert excinfo.value.line == 1

    @pytest.mark.parametrize("language", ["yaml", "zzz"])
    def test_no_language_is_checked_by_default(self, language):
        block = only_block(f"```{language} lucio command=include path=P.md\n```\n")
        assert block.language == language

    def test_the_check_does_not_look_at_an_ordinary_fence(self):
        text = "```zzz\nplain\n```\n"
        assert parse_template(text, SOURCE, check_language=True) == [VerbatimSegment(text=text)]


class TestSyntaxErrors:
    @pytest.mark.parametrize(
        ("text", "fragment", "line"),
        [
            ("~~~bash lucio\necho hi\n~~~\n", "must use backticks", 1),
            ("~~~~bash lucio\necho hi\n~~~~\n", "must use backticks", 1),
            ("```python lucio\necho hi\n```\n", "requires language 'bash'", 1),
            ("```bash lucio foo=1\necho hi\n```\n", "unknown attribute 'foo'", 1),
            ("```bash lucio Stdout=true\necho hi\n```\n", "unknown attribute 'Stdout'", 1),
            ("```bash lucio stdout=true stdout=true\necho hi\n```\n", "duplicate attribute", 1),
            ("```bash lucio stdout=true stdout=false\necho hi\n```\n", "duplicate attribute", 1),
            ("```bash lucio merge=true merge=false\necho hi\n```\n", "duplicate attribute", 1),
            ("```bash lucio stdout\necho hi\n```\n", "malformed attribute token 'stdout'", 1),
            ("```bash lucio stdout=\necho hi\n```\n", "malformed attribute token 'stdout='", 1),
            ("```bash lucio =x\necho hi\n```\n", "malformed attribute token '=x'", 1),
            ('```bash lucio path="a b\necho hi\n```\n', "unterminated quote", 1),
            ('```bash lucio command=include path=""\n```\n', "empty value", 1),
            ('```bash lucio command=include path="a"b\n```\n', "stray quote", 1),
            ('```bash lucio command=include path=a"b"\n```\n', "stray quote", 1),
            ('```bash lucio stdout="yes"\necho hi\n```\n', "must be true or false", 1),
            ("```bash lucio stdout=True\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio stdout=False\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio stdout=TRUE\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio stdout=1\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio show_source=FALSE\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio stderr=yes\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio merge=True\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio merge=1\necho hi\n```\n", "must be true or false", 1),
            ("```bash lucio command=run\necho hi\n```\n", "unknown value 'run'", 1),
            ("```bash lucio command=include\n```\n", "requires 'path'", 1),
            (
                "```bash lucio command=include path=P.md stdout=false\n```\n",
                "'stdout' does not apply",
                1,
            ),
            (
                "```bash lucio command=include path=P.md exit=1 merge=false\n```\n",
                "'exit' does not apply",
                1,
            ),
            ("```bash lucio path=P.md\necho hi\n```\n", "'path' requires", 1),
            ("```bash lucio style=fence\necho hi\n```\n", "'style' requires", 1),
            (
                "```bash lucio style=literal show_source=false\necho hi\n```\n",
                "'style' requires",
                1,
            ),
            (
                "```bash lucio command=include path=P.md style=raw\n```\n",
                "unknown value 'raw' for attribute 'style'",
                1,
            ),
            (
                "```bash lucio command=include path=P.md style=Fence\n```\n",
                "unknown value 'Fence'",
                1,
            ),
            (
                "```bash lucio command=include path=P.md style=fence style=literal\n```\n",
                "duplicate attribute",
                1,
            ),
            (
                "```bash lucio command=include path=P.md\necho hi\n```\n",
                "takes no body",
                1,
            ),
            ("```bash lucio exit=256\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=1000\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=-1\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=+1\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=007\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=1.5\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=abc\necho hi\n```\n", "integer 0-255", 1),
            ("```bash lucio exit=Any\necho hi\n```\n", "integer 0-255", 1),
            ("text\n\n```bash lucio\necho hi\n", "unterminated fence", 3),
            ("text\n```\nplain\n", "unterminated fence", 2),
            ("text\n~~~\nplain\n", "unterminated fence", 2),
            ("````bash lucio\necho hi\n```\n", "unterminated fence", 1),
        ],
    )
    def test_error(self, text, fragment, line):
        with pytest.raises(TemplateSyntaxError) as excinfo:
            parse(text)
        assert fragment in str(excinfo.value)
        assert str(excinfo.value).startswith(f"{SOURCE}:{line}: ")
        assert excinfo.value.line == line
        assert excinfo.value.path == SOURCE

    def test_syntax_error_line_of_a_later_block(self):
        text = "```bash lucio\necho hi\n```\n\n```bash lucio exit=999\necho hi\n```\n"
        with pytest.raises(TemplateSyntaxError) as excinfo:
            parse(text)
        assert excinfo.value.line == 5
