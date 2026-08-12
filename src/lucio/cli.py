"""Command line interface for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import click

from lucio import __version__
from lucio.console import debug, error, info, setup_console
from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    IncludeError,
    TemplateError,
    TotalTimeoutError,
)
from lucio.executor import execute_block, include_file
from lucio.model import BlockSegment, Command, ExecutionResult
from lucio.parser import parse_template
from lucio.renderer import render_document

EDIT_COMMENT_RE = re.compile(r"^<!--.*has been rendered by CLI tool 'lucio'.*-->$")
EXIT_EXECUTION_ERROR = 4
EXIT_TEMPLATE_ERROR = 3
EXIT_WRITE_ERROR = 1
NO_TIMEOUT = -1.0
OUTPUT_SUFFIX = ".md"
STDOUT_PATH = "-"
TEMPLATE_SUFFIXES = (".template.md", ".tmd")
VARIABLE_RE = re.compile(r"\$(\w+)|\$\{(\w+)\}")


# Defined before the command, which references it as the callback of --timeout
def _validate_timeout(
    ctx: click.Context, param: click.Parameter, value: float
) -> float | None:
    """Return the seconds a block may run for, or None for no timeout at all."""
    del ctx, param
    if value == NO_TIMEOUT:
        return None
    if value <= 0:
        raise click.BadParameter(f"must be positive, or {NO_TIMEOUT:g} for no timeout")
    return value


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-b",
    "--block-timeout",
    type=float,
    default=60.0,
    show_default=True,
    callback=_validate_timeout,
    help="Timeout for one block, in seconds; -1 for no timeout.",
)
@click.option(
    "-D",
    "--do-not-color",
    is_flag=True,
    default=False,
    help="Do not color the messages of the tool.",
)
@click.option(
    "-E",
    "--omit-do-not-edit-comment",
    is_flag=True,
    default=False,
    help="Do not open the rendered document with the do-not-edit comment.",
)
@click.option(
    "-L",
    "--check-language",
    is_flag=True,
    default=False,
    help="Reject a fence whose language highlight.js does not know.",
)
@click.option(
    "-O",
    "--overwrite-files",
    is_flag=True,
    default=False,
    help="Overwrite OUTPUT if it already exists.",
)
@click.option(
    "-P",
    "--pager",
    is_flag=True,
    default=False,
    help="Print the data output through a pager (when on a terminal).",
)
@click.option(
    "-R",
    "--remove-do-not-edit-comment-on-include",
    is_flag=True,
    default=False,
    help="Strip the do-not-edit comment from an included file.",
)
@click.option(
    "-t",
    "--total-timeout",
    type=float,
    default=300.0,
    show_default=True,
    callback=_validate_timeout,
    help="Timeout for the whole run, in seconds; -1 for no timeout.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Log each executed block and its exit code to stderr.",
)
@click.version_option(__version__, "-V", "--version", prog_name="lucio")
@click.argument(
    "input_file", metavar="INPUT", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.argument(
    "output_file",
    metavar="[OUTPUT]",
    required=False,
    type=click.Path(allow_dash=True, dir_okay=False, path_type=Path),
)
def main(
    input_file: Path,
    output_file: Path | None,
    block_timeout: float | None,
    check_language: bool,
    do_not_color: bool,
    omit_do_not_edit_comment: bool,
    overwrite_files: bool,
    pager: bool,
    remove_do_not_edit_comment_on_include: bool,
    total_timeout: float | None,
    verbose: bool,
) -> None:
    """Render the Markdown template INPUT into OUTPUT, executing its lucio blocks.

    Without OUTPUT, an INPUT named NAME.template.md or NAME.tmd is rendered into
    NAME.md, and any other INPUT is printed on stdout. An OUTPUT of "-" always means
    stdout, and the diagnostics of the tool always go to stderr, so the two never mix.

    The rendered document opens with a comment naming the template it came from,
    unless -E is given.

    The template is rendered in memory and written out only once everything succeeded,
    so a failing block leaves OUTPUT untouched.
    """
    setup_console(color=not do_not_color, verbose=verbose)
    deadline = None if total_timeout is None else time.monotonic() + total_timeout
    destination = _resolve_output(input_file, output_file)
    _log_settings(
        input_file,
        destination,
        block_timeout,
        check_language,
        omit_do_not_edit_comment,
        overwrite_files,
        pager,
        remove_do_not_edit_comment_on_include,
        total_timeout,
    )
    if destination is not None:
        if input_file.resolve() == destination.resolve():
            raise click.UsageError("INPUT and OUTPUT must be different files")
        if not overwrite_files and destination.exists():
            _fail(
                f"{destination}: file exists (use --overwrite-files to overwrite)",
                EXIT_WRITE_ERROR,
            )

    source = str(input_file)
    rendering = (
        f'Rendering "{source}" on the standard output'
        if destination is None
        else f'Rendering "{source}" into "{destination}"'
    )
    info(f"{rendering}...")
    text = _read_template(input_file, source)

    def runner(block: BlockSegment) -> ExecutionResult:
        if block.options.command is Command.INCLUDE:
            # A relative path is the template's, not the working directory's
            written = _expand_path(block.options.path or Path(), source, block.line)
            included = input_file.parent / written
            debug(f'{source}:{block.line}: including "{included}"')
            result = include_file(included, source, block.line)
            if remove_do_not_edit_comment_on_include:
                result = replace(result, stdout=_without_edit_comment(result.stdout))
            return result

        debug(f"{source}:{block.line}: executing {block.language} block")
        allowed = _remaining_timeout(block_timeout, deadline, source, block.line, total_timeout)
        try:
            result = execute_block(block, source, allowed)
        except ExecutionTimeoutError:
            # The budget, not the block ceiling, is what cut this block short
            if allowed != block_timeout:
                raise TotalTimeoutError(source, block.line, total_timeout or 0.0) from None
            raise
        permitted = _permitted_by(block, result.exit_code)
        debug(f"{source}:{block.line}: exit code {result.exit_code}{permitted}")
        return result

    try:
        segments = parse_template(text, source, check_language=check_language)
        rendered = render_document(segments, runner)
    except TemplateError as exc:
        _fail(str(exc), EXIT_TEMPLATE_ERROR)
    except ExecutionError as exc:
        _fail(str(exc), EXIT_EXECUTION_ERROR)

    if rendered and not omit_do_not_edit_comment:
        rendered = f"{_edit_comment(input_file, destination)}{rendered}"

    try:
        if destination is None:
            if _use_pager(pager):
                click.echo_via_pager(rendered)
            else:
                click.echo(rendered, nl=False)
        else:
            with destination.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
    except OSError as exc:
        _fail(f"{destination or 'stdout'}: {exc}", EXIT_WRITE_ERROR)

    info(f"{rendering}... done")


def _edit_comment(input_file: Path, destination: Path | None) -> str:
    """Return the do-not-edit comment for the document, with its trailing blank line.

    Printed on stdout there is no rendered file to name, so the comment says only
    which template to edit instead.
    """
    subject = "This file" if destination is None else f"This file {destination.name}"
    return (
        f"<!-- {subject} has been rendered by CLI tool 'lucio'. "
        f"Do not edit this file, but rather its template {input_file.name} . -->\n\n"
    )


def _expand_path(path: Path, source: str, line: int) -> Path:
    """Return the path with a leading ~ and any environment variable expanded.

    The names are checked first, since os.path.expandvars leaves an unset variable
    standing rather than reporting it; ~ expands before them, so only a written one
    counts and the rule stays one pass.
    """
    written = str(path)
    for match in VARIABLE_RE.finditer(written):
        name = match.group(1) or match.group(2)
        if name not in os.environ:
            raise IncludeError(source, line, written, f"environment variable '{name}' is not set")
    return Path(os.path.expandvars(os.path.expanduser(written)))


def _fail(message: str, code: int) -> NoReturn:
    """Report ``message`` on stderr and terminate with the given exit code."""
    error(message)
    raise SystemExit(code)


def _log_settings(
    input_file: Path,
    destination: Path | None,
    block_timeout: float | None,
    check_language: bool,
    omit_do_not_edit_comment: bool,
    overwrite_files: bool,
    pager: bool,
    remove_do_not_edit_comment_on_include: bool,
    total_timeout: float | None,
) -> None:
    """Log the settings of the run, one per line, before anything is read or executed."""
    debug(f'Input file: "{input_file.resolve()}"')
    if destination is None:
        debug("Output file: standard output")
    else:
        debug(f'Output file: "{destination.resolve()}"')
    debug(f"Check language: {check_language}")
    debug(f"Omit do-not-edit comment: {omit_do_not_edit_comment}")
    debug(f"Overwrite files: {overwrite_files}")
    debug(f"Pager: {pager}")
    debug(f"Remove do-not-edit comment on include: {remove_do_not_edit_comment_on_include}")
    debug(_timeout_setting("Block timeout", block_timeout))
    debug(_timeout_setting("Total timeout", total_timeout))


def _permitted_by(block: BlockSegment, exit_code: int) -> str:
    """Return the attribute that permitted a non-zero exit code, as the template spells it.

    A non-zero code only ever reaches the log when it was permitted: the executor aborts
    the run otherwise.
    """
    if exit_code == 0:
        return ""
    expected = block.options.expected_exit
    return f" (permitted by exit={'any' if expected is None else expected})"


def _read_template(input_file: Path, source: str) -> str:
    """Read the template as strict UTF-8, normalizing CRLF line endings to LF."""
    try:
        with input_file.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        _fail(f"{source}: not valid UTF-8: {exc}", EXIT_TEMPLATE_ERROR)
    except OSError as exc:
        _fail(f"{source}: {exc}", EXIT_TEMPLATE_ERROR)
    return text.replace("\r\n", "\n")


def _remaining_timeout(
    block_timeout: float | None,
    deadline: float | None,
    source: str,
    line: int,
    total_timeout: float | None,
) -> float | None:
    """Return the seconds this block may run for, raising once the budget is spent.

    A block never outlives the deadline of the run, so the total is a real bound and
    not merely a check between one block and the next.
    """
    if deadline is None:
        return block_timeout
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TotalTimeoutError(source, line, total_timeout or 0.0)
    return remaining if block_timeout is None else min(block_timeout, remaining)


def _resolve_output(input_file: Path, output_file: Path | None) -> Path | None:
    """Return the file to render into, or None to print the document on stdout."""
    if output_file is not None:
        return None if str(output_file) == STDOUT_PATH else output_file
    name = input_file.name
    for suffix in TEMPLATE_SUFFIXES:
        if name.endswith(suffix):
            return input_file.with_name(f"{name[: -len(suffix)]}{OUTPUT_SUFFIX}")
    return None


def _timeout_setting(label: str, timeout: float | None) -> str:
    """Return the settings line for a timeout, which may be disabled."""
    return f"{label}: none" if timeout is None else f"{label}: {timeout} seconds"


def _use_pager(pager: bool) -> bool:
    """Return whether the document should go through a pager.

    click pages only on a terminal too, but appends a newline when it does not, so
    deciding here is what keeps a redirected document byte-identical.
    """
    return pager and sys.stdout.isatty()


def _without_edit_comment(text: str) -> str:
    """Return an included file without the do-not-edit comment lucio would have written.

    Only the first line is considered, and the blank line below it goes too, mirroring
    the pair `_edit_comment` emits. A comment of anyone else's is left alone.
    """
    first, separator, rest = text.partition("\n")
    if not separator or EDIT_COMMENT_RE.match(first) is None:
        return text
    return rest[1:] if rest.startswith("\n") else rest


if __name__ == "__main__":  # pragma: no cover
    main()
