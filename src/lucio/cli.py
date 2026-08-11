"""Command line interface for lucio.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

from pathlib import Path
from typing import NoReturn

import click

from lucio import __version__
from lucio.errors import ExecutionError, TemplateError
from lucio.executor import execute_block
from lucio.model import BlockSegment, ExecutionResult
from lucio.parser import parse_template
from lucio.renderer import render_document

EXIT_EXECUTION_ERROR = 4
EXIT_TEMPLATE_ERROR = 3
EXIT_WRITE_ERROR = 1


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="lucio")
@click.option(
    "--timeout",
    type=click.FloatRange(min=0, min_open=True),
    default=120.0,
    show_default=True,
    help="Per-block execution timeout, in seconds.",
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
@click.argument("output_file", metavar="OUTPUT", type=click.Path(dir_okay=False, path_type=Path))
def main(input_file: Path, output_file: Path, timeout: float, verbose: bool) -> None:
    """Render the Markdown template INPUT into OUTPUT, executing its lucio bash blocks.

    The template is rendered in memory and written out only once everything succeeded,
    so a failing block leaves OUTPUT untouched.
    """
    if input_file.resolve() == output_file.resolve():
        raise click.UsageError("INPUT and OUTPUT must be different files")

    source = str(input_file)
    text = _read_template(input_file, source)

    def runner(block: BlockSegment) -> ExecutionResult:
        if verbose:
            _log(f"{source}:{block.line}: executing bash {block.kind.value} block")
        result = execute_block(block, source, timeout)
        if verbose:
            _log(f"{source}:{block.line}: exit code {result.exit_code}")
        return result

    try:
        rendered = render_document(parse_template(text, source), runner)
    except TemplateError as exc:
        _fail(str(exc), EXIT_TEMPLATE_ERROR)
    except ExecutionError as exc:
        _fail(str(exc), EXIT_EXECUTION_ERROR)

    try:
        with output_file.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    except OSError as exc:
        _fail(f"{output_file}: {exc}", EXIT_WRITE_ERROR)


def _fail(message: str, code: int) -> NoReturn:
    """Report ``message`` on stderr and terminate with the given exit code."""
    _log(f"error: {message}")
    raise SystemExit(code)


def _log(message: str) -> None:
    """Write one lucio diagnostic line to stderr."""
    click.echo(f"lucio: {message}", err=True)


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


if __name__ == "__main__":  # pragma: no cover
    main()
