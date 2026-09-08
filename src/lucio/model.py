"""Core data model for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import enum
import re
from dataclasses import dataclass
from pathlib import Path


class Command(enum.Enum):
    """What a block asks lucio to do, as spelled by its ``command`` attribute."""

    EXECUTE = "execute"
    INCLUDE = "include"


class Count(enum.Enum):
    """How many matches a replacement rule rewrites, as spelled by its ``count`` field."""

    ALL = "all"
    FIRST = "first"


class Stream(enum.Enum):
    """A text a replacement rule may rewrite, as spelled in its ``streams`` field.

    ``stdout`` and ``stderr`` are the streams an execute block captures; ``include`` is
    the content of the file an include block reads.
    """

    INCLUDE = "include"
    STDERR = "stderr"
    STDOUT = "stdout"


class Style(enum.Enum):
    """How an include wraps the file it reads, as spelled by its ``style`` attribute."""

    FENCE = "fence"
    LANGUAGE = "language"
    LITERAL = "literal"


@dataclass(frozen=True, slots=True)
class BlockOptions:
    """The attributes of a trigger fence, resolved against their defaults."""

    command: Command = Command.INCLUDE
    expected_exit: int | None = 0
    """The exit code the block must exit with; None means "any exit code is fine"."""
    merge: bool = True
    """Whether the captured output belongs inside the source fence, rather than after it."""
    path: Path | None = None
    """The file an include reads, as written in the template; None for any other command."""
    show_source: bool = True
    stderr: bool = True
    stdout: bool = True
    style: Style = Style.LANGUAGE
    """How an include wraps the file; meaningless for any other command."""


@dataclass(frozen=True, slots=True)
class BlockSegment:
    """A trigger fence, with the template bytes needed to re-emit it verbatim."""

    body: str
    """The body lines exactly as in the template, each ending with "\\n"; "" if empty."""
    close_line: str
    """The closing fence line verbatim, trailing whitespace included, ending with "\\n"."""
    fence_char: str
    fence_length: int
    """The length of the opening backtick run, at least 3."""
    indent: str
    """The 0 to 3 spaces preceding the opening fence."""
    language: str
    """The first token of the info string, copied into the emitted fence."""
    line: int
    """The 1-based line number of the opening fence in the template."""
    options: BlockOptions


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The outcome of running one block body through a shell."""

    exit_code: int
    stderr: str
    stdout: str


@dataclass(frozen=True, slots=True)
class Rule:
    """One replacement rule of a rules file, its target already compiled."""

    count: Count
    identifier: str
    """The key naming the rule in the file, unique within it."""
    replacement: str
    """The replacement text, with the backreferences :func:`re.sub` understands."""
    streams: frozenset[Stream]
    target: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class RuleHit:
    """One rule having rewritten one stream of one block, with how many matches it found."""

    identifier: str
    stream: Stream
    substitutions: int


@dataclass(frozen=True, slots=True)
class VerbatimSegment:
    """Template text that passes through byte-for-byte."""

    text: str


Segment = BlockSegment | VerbatimSegment
