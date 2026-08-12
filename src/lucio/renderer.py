"""Rendering of parsed segments into the output Markdown document.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import re
from collections.abc import Callable

from lucio.model import BlockSegment, Command, ExecutionResult, Segment, Style, VerbatimSegment

MIN_FENCE_LENGTH = 3

_BACKTICK_RUN_RE = re.compile(r"`+")


def fence_for(content: str) -> str:
    """Return a backtick fence long enough to wrap ``content`` without being closed by it."""
    longest = max((len(run) for run in _BACKTICK_RUN_RE.findall(content)), default=0)
    return "`" * max(MIN_FENCE_LENGTH, longest + 1)


def normalize_stream(text: str) -> str:
    """Return ``text`` ending with exactly one newline, or "" if it holds nothing but newlines."""
    stripped = text.rstrip("\n")
    return f"{stripped}\n" if stripped else ""


def render_block(block: BlockSegment, result: ExecutionResult) -> str:
    """Render one block: one merged fence, a source fence, an output fence, or nothing."""
    if block.options.command is Command.INCLUDE:
        return _render_included(block, normalize_stream(result.stdout))

    options = block.options
    selected = ""
    if options.stdout:
        selected += normalize_stream(result.stdout)
    if options.stderr:
        selected += normalize_stream(result.stderr)

    if options.merge and options.show_source and selected:
        return _render_merged(block, selected)

    parts: list[str] = []
    if options.show_source:
        parts.append(f"{block.indent}{block.fence_char * block.fence_length}{block.language}\n")
        parts.append(block.body)
        parts.append(block.close_line)
    if selected:
        if options.show_source:
            parts.append("\n")
        fence = fence_for(selected)
        parts.append(f"{fence}\n{selected}{fence}\n")
    return "".join(parts)


def render_document(
    segments: list[Segment], runner: Callable[[BlockSegment], ExecutionResult]
) -> str:
    """Render every segment in document order, executing blocks through ``runner``.

    A block that renders to nothing gives up its line, and one blank line around it is
    collapsed, so hidden setup blocks leave no trace in the output.
    """
    out: list[str] = []
    strip_blank = False
    tail = ""

    for segment in segments:
        if isinstance(segment, VerbatimSegment):
            text = segment.text
            if strip_blank and text.startswith("\n"):
                text = text[1:]
            strip_blank = False
            if text:
                out.append(text)
                tail = f"{tail}{text}"[-2:]
            continue

        chunk = render_block(segment, runner(segment))
        if chunk:
            strip_blank = False
            out.append(chunk)
            tail = f"{tail}{chunk}"[-2:]
        elif tail == "" or tail == "\n\n":
            strip_blank = True

    rendered = "".join(out)
    return rendered if rendered == "" else f"{rendered.rstrip('\n')}\n"


def _render_included(block: BlockSegment, content: str) -> str:
    """Wrap the content of an include as its style asks, or paste it as it is.

    An empty file contributes nothing whatever the style, as an execute block whose
    output is empty does; the fence sits at column 0, where the raw paste lands.
    """
    style = block.options.style
    if not content or style is Style.LITERAL:
        return content
    fence = fence_for(content)
    info = block.language if style is Style.LANGUAGE else ""
    return f"{fence}{info}\n{content}{fence}\n"


def _render_merged(block: BlockSegment, selected: str) -> str:
    """Render the source and the captured output as a single fence, a terminal transcript.

    The template fence already wraps the body safely, so only the captured output can force
    a longer fence; when it does not, the closing line of the template is reused verbatim.
    """
    length = max(block.fence_length, len(fence_for(selected)))
    fence = block.fence_char * length
    closing = block.close_line if length == block.fence_length else f"{block.indent}{fence}\n"
    return f"{block.indent}{fence}{block.language}\n{block.body}{selected}{closing}"
