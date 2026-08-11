"""Line-oriented parser splitting a template into verbatim text and trigger blocks.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import enum
import re
from pathlib import Path

from lucio.errors import TemplateSyntaxError
from lucio.model import BlockOptions, BlockSegment, Command, Segment, VerbatimSegment

ATTRIBUTE_KEYS = frozenset(
    {"command", "exit", "merge", "path", "show_source", "stderr", "stdout"}
)
BOOLEAN_VALUES = {"false": False, "true": True}
COMMAND_VALUES = {command.value: command for command in Command}
EXECUTE_ONLY_KEYS = frozenset({"exit", "merge", "show_source", "stderr", "stdout"})
LANGUAGE = "bash"
TRIGGER = "lucio"

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
                joined = "".join(body)
                if options.command is Command.INCLUDE and joined:
                    raise TemplateSyntaxError(
                        source, open_line, f"'command={Command.INCLUDE.value}' takes no body"
                    )
                segments.append(
                    BlockSegment(
                        body=joined,
                        close_line=line if line.endswith("\n") else f"{line}\n",
                        fence_char=fence_char,
                        fence_length=fence_length,
                        indent=indent,
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

        close_re = re.compile(rf"( {{0,3}}){re.escape(fence[0])}{{{len(fence)},}}[ \t]*")
        open_line = number
        if not _classify_info_string(info, fence[0], source, number):
            state = _State.IN_FENCE_VERBATIM
            verbatim.append(line)
            continue

        if verbatim:
            segments.append(VerbatimSegment(text="".join(verbatim)))
            verbatim = []
        fence_char = fence[0]
        fence_length = len(fence)
        indent = match.group(1)
        options = _parse_attributes(info.split()[2:], source, number)
        state = _State.IN_FENCE_TRIGGER

    if state is not _State.NORMAL:
        raise TemplateSyntaxError(source, open_line, "unterminated fence (opened here)")
    if verbatim:
        segments.append(VerbatimSegment(text="".join(verbatim)))
    return segments


def _check_command_pairing(command: Command, seen: set[str], source: str, line: int) -> None:
    """Reject attributes that the command does not use, and the ones it cannot do without."""
    include = Command.INCLUDE.value
    if command is Command.INCLUDE:
        if "path" not in seen:
            raise TemplateSyntaxError(source, line, f"'command={include}' requires 'path'")
        unusable = sorted(seen & EXECUTE_ONLY_KEYS)
        if unusable:
            raise TemplateSyntaxError(
                source, line, f"'{unusable[0]}' does not apply to 'command={include}'"
            )
    elif "path" in seen:
        raise TemplateSyntaxError(source, line, f"'path' requires 'command={include}'")


def _classify_info_string(info: str, fence_char: str, source: str, line: int) -> bool:
    """Return whether the info string opens a trigger fence rather than an ordinary one."""
    tokens = info.split()
    if len(tokens) < 2 or tokens[1] != TRIGGER:
        return False
    language = tokens[0]
    if language != LANGUAGE:
        raise TemplateSyntaxError(
            source,
            line,
            f"trigger '{TRIGGER}' requires language '{LANGUAGE}', found '{language}'",
        )
    if fence_char != "`":
        raise TemplateSyntaxError(source, line, "trigger fences must use backticks, not tildes")
    return True


def _parse_attributes(attrs: list[str], source: str, line: int) -> BlockOptions:
    """Resolve the ``key=value`` tokens of a lucio trigger against their defaults."""
    command = Command.EXECUTE
    expected_exit: int | None = 0
    merge = True
    path: Path | None = None
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
            command = COMMAND_VALUES[value]
        elif key == "exit":
            expected_exit = _parse_exit(value, source, line)
        elif key == "merge":
            merge = _parse_boolean(key, value, source, line)
        elif key == "path":
            path = Path(value)
        elif key == "show_source":
            show_source = _parse_boolean(key, value, source, line)
        elif key == "stderr":
            stderr = _parse_boolean(key, value, source, line)
        else:
            stdout = _parse_boolean(key, value, source, line)

    _check_command_pairing(command, seen, source, line)
    return BlockOptions(
        command=command,
        expected_exit=expected_exit,
        merge=merge,
        path=path,
        show_source=show_source,
        stderr=stderr,
        stdout=stdout,
    )


def _parse_boolean(key: str, value: str, source: str, line: int) -> bool:
    """Parse a Python-style boolean attribute value, rejecting any other spelling."""
    if value not in BOOLEAN_VALUES:
        raise TemplateSyntaxError(
            source, line, f"attribute '{key}' must be true or false, found '{value}'"
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
