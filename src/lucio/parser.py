"""Line-oriented parser splitting a template into verbatim text and trigger blocks.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import enum
import re

from lucio.errors import TemplateSyntaxError
from lucio.model import BlockKind, BlockOptions, BlockSegment, Segment, VerbatimSegment

ATTRIBUTE_KEYS = frozenset({"command", "exit", "merge", "show_source", "stderr", "stdout"})
BOOLEAN_VALUES = {"False": False, "True": True}
COMMAND_VALUES = frozenset({"execute"})
LANGUAGE = "bash"
TRIGGER_KINDS = {"include": BlockKind.INCLUDE, "lucio": BlockKind.EXECUTE}

_EXIT_RE = re.compile(r"0|[1-9][0-9]{0,2}")
_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_MAX_EXIT = 255


class _State(enum.Enum):
    """The state of the line-oriented scanner."""

    IN_FENCE_TRIGGER = enum.auto()
    IN_FENCE_VERBATIM = enum.auto()
    NORMAL = enum.auto()


def parse_template(text: str, source: str) -> list[Segment]:
    """Split ``text`` into verbatim segments and trigger blocks, in document order.

    No block is executed: the whole template is validated first, so syntax errors
    surface before anything runs.
    """
    segments: list[Segment] = []
    verbatim: list[str] = []
    body: list[str] = []
    close_re: re.Pattern[str] | None = None
    fence_char = ""
    fence_length = 0
    indent = ""
    kind = BlockKind.EXECUTE
    open_line = 0
    options = BlockOptions()
    state = _State.NORMAL

    for number, line in enumerate(_split_lines(text), start=1):
        content = line.removesuffix("\n")

        if state is not _State.NORMAL:
            closes = close_re is not None and close_re.fullmatch(content) is not None
            if state is _State.IN_FENCE_VERBATIM:
                verbatim.append(line)
                if closes:
                    state = _State.NORMAL
            elif closes:
                segments.append(
                    BlockSegment(
                        body="".join(body),
                        close_line=line if line.endswith("\n") else f"{line}\n",
                        fence_char=fence_char,
                        fence_length=fence_length,
                        indent=indent,
                        kind=kind,
                        line=open_line,
                        options=options,
                    )
                )
                body = []
                state = _State.NORMAL
            else:
                body.append(line)
            continue

        match = _FENCE_OPEN_RE.match(content)
        if match is None:
            verbatim.append(line)
            continue

        fence = match.group(2)
        info = match.group(3)
        if fence.startswith("`") and "`" in info:
            # CommonMark: a backtick fence info string cannot contain a backtick
            verbatim.append(line)
            continue

        opened_kind = _classify_info_string(info, fence[0], source, number)
        close_re = re.compile(rf"( {{0,3}}){re.escape(fence[0])}{{{len(fence)},}}[ \t]*")
        open_line = number
        if opened_kind is None:
            state = _State.IN_FENCE_VERBATIM
            verbatim.append(line)
            continue

        if verbatim:
            segments.append(VerbatimSegment(text="".join(verbatim)))
            verbatim = []
        fence_char = fence[0]
        fence_length = len(fence)
        indent = match.group(1)
        kind = opened_kind
        options = (
            _parse_attributes(info.split()[2:], source, number)
            if opened_kind is BlockKind.EXECUTE
            else BlockOptions()
        )
        state = _State.IN_FENCE_TRIGGER

    if state is not _State.NORMAL:
        raise TemplateSyntaxError(source, open_line, "unterminated fence (opened here)")
    if verbatim:
        segments.append(VerbatimSegment(text="".join(verbatim)))
    return segments


def _classify_info_string(info: str, fence_char: str, source: str, line: int) -> BlockKind | None:
    """Return the kind of trigger the info string opens, or None if it is an ordinary fence."""
    tokens = info.split()
    if len(tokens) < 2:
        return None
    language, trigger = tokens[0], tokens[1]
    if trigger not in TRIGGER_KINDS:
        return None
    if language != LANGUAGE:
        raise TemplateSyntaxError(
            source,
            line,
            f"trigger '{trigger}' requires language '{LANGUAGE}', found '{language}'",
        )
    if fence_char != "`":
        raise TemplateSyntaxError(source, line, "trigger fences must use backticks, not tildes")
    kind = TRIGGER_KINDS[trigger]
    if kind is BlockKind.INCLUDE and len(tokens) > 2:
        raise TemplateSyntaxError(source, line, f"'{LANGUAGE} {trigger}' takes no attributes")
    return kind


def _parse_attributes(attrs: list[str], source: str, line: int) -> BlockOptions:
    """Resolve the ``key=value`` tokens of a lucio trigger against their defaults."""
    command = "execute"
    expected_exit: int | None = 0
    merge = True
    show_source = True
    stderr = True
    stdout = True
    seen: set[str] = set()

    for token in attrs:
        key, separator, value = token.partition("=")
        if not separator or not key or not value:
            raise TemplateSyntaxError(
                source, line, f"malformed attribute token '{token}' (expected key=value)"
            )
        if key not in ATTRIBUTE_KEYS:
            raise TemplateSyntaxError(source, line, f"unknown attribute '{key}'")
        if key in seen:
            raise TemplateSyntaxError(source, line, f"duplicate attribute '{key}'")
        seen.add(key)

        if key == "command":
            if value not in COMMAND_VALUES:
                raise TemplateSyntaxError(
                    source, line, f"unknown value '{value}' for attribute 'command'"
                )
            command = value
        elif key == "exit":
            expected_exit = _parse_exit(value, source, line)
        elif key == "merge":
            merge = _parse_boolean(key, value, source, line)
        elif key == "show_source":
            show_source = _parse_boolean(key, value, source, line)
        elif key == "stderr":
            stderr = _parse_boolean(key, value, source, line)
        else:
            stdout = _parse_boolean(key, value, source, line)

    return BlockOptions(
        command=command,
        expected_exit=expected_exit,
        merge=merge,
        show_source=show_source,
        stderr=stderr,
        stdout=stdout,
    )


def _parse_boolean(key: str, value: str, source: str, line: int) -> bool:
    """Parse a Python-style boolean attribute value, rejecting any other spelling."""
    if value not in BOOLEAN_VALUES:
        raise TemplateSyntaxError(
            source, line, f"attribute '{key}' must be True or False, found '{value}'"
        )
    return BOOLEAN_VALUES[value]


def _parse_exit(value: str, source: str, line: int) -> int | None:
    """Parse the ``exit`` attribute value; ``any`` disables the exit-code check."""
    if value == "any":
        return None
    if _EXIT_RE.fullmatch(value) is None or int(value) > _MAX_EXIT:
        raise TemplateSyntaxError(
            source,
            line,
            f"attribute 'exit' must be 'any' or an integer 0-{_MAX_EXIT}, found '{value}'",
        )
    return int(value)


def _split_lines(text: str) -> list[str]:
    """Split on "\\n" only, keeping the newline; a lone "\\r" is never a line break."""
    parts = text.split("\n")
    lines = [f"{part}\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines
