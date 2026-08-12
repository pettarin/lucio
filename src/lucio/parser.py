"""Line-oriented parser splitting a template into verbatim text and trigger blocks.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import enum
import re
from pathlib import Path

from lucio.errors import TemplateSyntaxError
from lucio.languages import LANGUAGES
from lucio.model import BlockOptions, BlockSegment, Command, Segment, Style, VerbatimSegment

ATTRIBUTE_KEYS = frozenset(
    {"command", "exit", "merge", "path", "show_source", "stderr", "stdout", "style"}
)
BOOLEAN_VALUES = {"false": False, "true": True}
COMMAND_VALUES = {command.value: command for command in Command}
EXECUTE_ONLY_KEYS = frozenset({"exit", "merge", "show_source", "stderr", "stdout"})
INCLUDE_ONLY_KEYS = frozenset({"path", "style"})
QUOTE = '"'
SHELLS = ("bash", "sh", "zsh")
"""The languages an execute block may carry, each the name of the shell running its body."""
STYLE_VALUES = {style.value: style for style in Style}
TRIGGER = "lucio"

_EXIT_RE = re.compile(r"0|[1-9][0-9]{0,2}")
_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_MAX_EXIT = 255
_SHELL_LIST = f"{', '.join(repr(shell) for shell in SHELLS[:-1])} or {SHELLS[-1]!r}"


class _State(enum.Enum):
    """The state of the line-oriented scanner."""

    IN_FENCE_TRIGGER = enum.auto()
    IN_FENCE_VERBATIM = enum.auto()
    NORMAL = enum.auto()


def parse_template(text: str, source: str, check_language: bool = False) -> list[Segment]:
    """Split ``text`` into verbatim segments and trigger blocks, in document order.

    No block is executed: the whole template is validated first, so syntax errors
    surface before anything runs. With ``check_language``, the language of a trigger
    fence must be one highlight.js knows.
    """
    segments: list[Segment] = []
    verbatim: list[str] = []
    body: list[str] = []
    close_re: re.Pattern[str] | None = None
    fence_char = ""
    fence_length = 0
    indent = ""
    language = ""
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
                        language=language,
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
        tokens = _split_info(info, source, number)
        fence_char = fence[0]
        fence_length = len(fence)
        indent = match.group(1)
        language = tokens[0]
        if check_language and language.lower() not in LANGUAGES:
            raise TemplateSyntaxError(source, number, f"unknown language '{language}'")
        options = _parse_attributes(tokens[2:], source, number)
        _check_language_pairing(options.command, language, source, number)
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
        return
    unusable = sorted(seen & INCLUDE_ONLY_KEYS)
    if unusable:
        raise TemplateSyntaxError(source, line, f"'{unusable[0]}' requires 'command={include}'")


def _check_language_pairing(command: Command, language: str, source: str, line: int) -> None:
    """Reject a language the command cannot carry; only an include takes any of them.

    The language of an execute block names the shell its body is run by, so it must be
    one lucio can spawn; an include never runs anything and takes them all.
    """
    if command is Command.EXECUTE and language not in SHELLS:
        raise TemplateSyntaxError(
            source,
            line,
            f"trigger '{TRIGGER}' requires language {_SHELL_LIST}, found '{language}'",
        )


def _classify_info_string(info: str, fence_char: str, source: str, line: int) -> bool:
    """Return whether the info string opens a trigger fence rather than an ordinary one.

    Any language opens one; which of them a command may carry is settled later, once
    the attributes have been read.
    """
    tokens = _split_info(info, source, line)
    if len(tokens) < 2 or tokens[1] != TRIGGER:
        return False
    if fence_char != "`":
        raise TemplateSyntaxError(source, line, "trigger fences must use backticks, not tildes")
    return True


def _parse_attributes(attrs: list[str], source: str, line: int) -> BlockOptions:
    """Resolve the ``key=value`` tokens of a lucio trigger against their defaults."""
    command = Command.INCLUDE
    expected_exit: int | None = 0
    merge = True
    path: Path | None = None
    show_source = True
    stderr = True
    stdout = True
    style = Style.LANGUAGE
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
        value = _unquote(value, token, source, line)

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
        elif key == "stdout":
            stdout = _parse_boolean(key, value, source, line)
        else:
            if value not in STYLE_VALUES:
                raise TemplateSyntaxError(
                    source, line, f"unknown value '{value}' for attribute 'style'"
                )
            style = STYLE_VALUES[value]

    _check_command_pairing(command, seen, source, line)
    return BlockOptions(
        command=command,
        expected_exit=expected_exit,
        merge=merge,
        path=path,
        show_source=show_source,
        stderr=stderr,
        stdout=stdout,
        style=style,
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


def _split_info(info: str, source: str, line: int) -> list[str]:
    """Split an info string on whitespace, keeping a double-quoted run in one token.

    The quotes are left in the token, so the ``key=value`` split is unaffected and the
    value can be unquoted where it is validated.
    """
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    for char in info:
        if char == QUOTE:
            quoted = not quoted
            current.append(char)
        elif char.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if quoted:
        raise TemplateSyntaxError(source, line, "unterminated quote in the info string")
    if current:
        tokens.append("".join(current))
    return tokens


def _split_lines(text: str) -> list[str]:
    """Split on "\\n" only, keeping the newline; a lone "\\r" is never a line break."""
    parts = text.split("\n")
    lines = [f"{part}\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _unquote(value: str, token: str, source: str, line: int) -> str:
    """Return a value with its wrapping quotes removed, rejecting a stray one.

    Quoting is lexical: what comes out is validated exactly as an unquoted value is,
    so ``stdout="true"`` and ``stdout=true`` mean the same thing.
    """
    if value.startswith(QUOTE) and value.endswith(QUOTE) and len(value) > 1:
        unquoted = value[1:-1]
        if not unquoted:
            raise TemplateSyntaxError(source, line, f"empty value in attribute token '{token}'")
        return unquoted
    if QUOTE in value:
        raise TemplateSyntaxError(source, line, f"stray quote in attribute token '{token}'")
    return value
