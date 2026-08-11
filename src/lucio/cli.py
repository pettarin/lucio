"""Command line interface for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

from pathlib import Path
from typing import NoReturn

import click

from lucio import __version__
from lucio.console import debug, error, info, setup_console
from lucio.errors import ExecutionError, TemplateError
from lucio.executor import execute_block
from lucio.model import BlockSegment, ExecutionResult
from lucio.parser import parse_template
from lucio.renderer import render_document

EXIT_EXECUTION_ERROR = 4
EXIT_TEMPLATE_ERROR = 3
EXIT_WRITE_ERROR = 1
NO_TIMEOUT = -1.0
OUTPUT_SUFFIX = ".md"
STDOUT_PATH = "-"
TEMPLATE_SUFFIXES = (".template.md", ".tmd")


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
@click.version_option(version=__version__, prog_name="lucio")
@click.option(
    "--color/--no-color",
    default=True,
    show_default=True,
    help="Color the messages of the tool (when the terminal supports it).",
)
@click.option(
    "--timeout",
    type=float,
    default=60.0,
    show_default=True,
    callback=_validate_timeout,
    help="Per-block execution timeout, in seconds; -1 for no timeout.",
)
@click.option(
    "-O",
    "--overwrite-files",
    is_flag=True,
    default=False,
    help="Overwrite OUTPUT if it already exists.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Log each executed block and its exit code to stderr.",
)
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
    color: bool,
    overwrite_files: bool,
    timeout: float | None,
    verbose: bool,
) -> None:
    """Render the Markdown template INPUT into OUTPUT, executing its lucio blocks.

    Without OUTPUT, an INPUT named NAME.template.md or NAME.tmd is rendered into
    NAME.md, and any other INPUT is printed on stdout. An OUTPUT of "-" always means
    stdout, and the diagnostics of the tool always go to stderr, so the two never mix.

    The template is rendered in memory and written out only once everything succeeded,
    so a failing block leaves OUTPUT untouched.
    """
    setup_console(color=color, verbose=verbose)
    destination = _resolve_output(input_file, output_file)
    _log_settings(input_file, destination, overwrite_files, timeout)
    if destination is not None:
        if input_file.resolve() == destination.resolve():
            raise click.UsageError("INPUT and OUTPUT must be different files")
        if not overwrite_files and destination.exists():
            _fail(
                f"{destination}: file exists (use --overwrite-files to overwrite)",
                EXIT_WRITE_ERROR,
            )

    source = str(input_file)
    text = _read_template(input_file, source)

    def runner(block: BlockSegment) -> ExecutionResult:
        debug(f"{source}:{block.line}: executing bash {block.kind.value} block")
        result = execute_block(block, source, timeout)
        permitted = _permitted_by(block, result.exit_code)
        debug(f"{source}:{block.line}: exit code {result.exit_code}{permitted}")
        return result

    try:
        rendered = render_document(parse_template(text, source), runner)
    except TemplateError as exc:
        _fail(str(exc), EXIT_TEMPLATE_ERROR)
    except ExecutionError as exc:
        _fail(str(exc), EXIT_EXECUTION_ERROR)

    try:
        if destination is None:
            click.echo(rendered, nl=False)
        else:
            with destination.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
    except OSError as exc:
        _fail(f"{destination or 'stdout'}: {exc}", EXIT_WRITE_ERROR)

    if destination is None:
        info(f'Rendered "{source}" on the standard output')
    else:
        info(f'Rendered "{source}" into "{destination}"')


def _fail(message: str, code: int) -> NoReturn:
    """Report ``message`` on stderr and terminate with the given exit code."""
    error(message)
    raise SystemExit(code)


def _log_settings(
    input_file: Path, destination: Path | None, overwrite_files: bool, timeout: float | None
) -> None:
    """Log the settings of the run, one per line, before anything is read or executed."""
    debug(f'Input file: "{input_file.resolve()}"')
    if destination is None:
        debug("Output file: standard output")
    else:
        debug(f'Output file: "{destination.resolve()}"')
    debug(f"Overwrite files: {overwrite_files}")
    debug("Block timeout: none" if timeout is None else f"Block timeout: {timeout} seconds")


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


def _resolve_output(input_file: Path, output_file: Path | None) -> Path | None:
    """Return the file to render into, or None to print the document on stdout."""
    if output_file is not None:
        return None if str(output_file) == STDOUT_PATH else output_file
    name = input_file.name
    for suffix in TEMPLATE_SUFFIXES:
        if name.endswith(suffix):
            return input_file.with_name(f"{name[: -len(suffix)]}{OUTPUT_SUFFIX}")
    return None


if __name__ == "__main__":  # pragma: no cover
    main()
