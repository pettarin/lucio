"""Core data model for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import enum
from dataclasses import dataclass


class BlockKind(enum.Enum):
    """The kind of trigger fence a block was opened with."""

    EXECUTE = "lucio"
    INCLUDE = "include"


@dataclass(frozen=True, slots=True)
class BlockOptions:
    """The attributes of a trigger fence, resolved against their defaults."""

    command: str = "execute"
    expected_exit: int | None = 0
    """The exit code the block must exit with; None means "any exit code is fine"."""
    merge: bool = True
    """Whether the captured output belongs inside the source fence, rather than after it."""
    show_source: bool = True
    stderr: bool = True
    stdout: bool = True


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
    kind: BlockKind
    line: int
    """The 1-based line number of the opening fence in the template."""
    options: BlockOptions


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The outcome of running one block body through bash."""

    exit_code: int
    stderr: str
    stdout: str


@dataclass(frozen=True, slots=True)
class VerbatimSegment:
    """Template text that passes through byte-for-byte."""

    text: str


Segment = BlockSegment | VerbatimSegment
