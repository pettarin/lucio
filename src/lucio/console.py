"""Console logging for the lucio CLI.

The messages of the tool flow through the standard :mod:`logging` machinery, under the
``lucio`` logger: the CLI installs a handler on it that prefixes every message with its
UTC timestamp and its level (``[ERRO]``, ``[WARN]``, ``[INFO]``, ``[DEBU]``)
and prints it to the standard error, colored when the terminal supports it, leaving the
standard output to the rendered document alone.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import logging
from datetime import UTC, datetime
from typing import Any

import click
import colorama

LOGGER = logging.getLogger("lucio.cli")
"""The logger of the CLI, a child of the ``lucio`` logger of the package."""

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
"""The UTC timestamp of a console line, truncated to milliseconds."""

_STYLES: list[tuple[int, str, dict[str, Any]]] = [
    (logging.ERROR, "[ERRO]", {"fg": "red"}),
    (logging.WARNING, "[WARN]", {"fg": "yellow"}),
    (logging.INFO, "[INFO]", {}),
    (logging.DEBUG, "[DEBU]", {"dim": True}),
]
"""The label and the click style of each level, highest first."""


class ConsoleHandler(logging.Handler):
    """Print the log records to the standard error, labelled and colored.

    The styling and the stripping are click's: with ``color`` None the codes reach a
    terminal and not a pipe, with False they are never emitted.
    """

    def __init__(self, color: bool | None = None) -> None:
        """Initialize the handler.

        Args:
            color: Whether to color the messages: None to let click decide from the
                stream, False to never color
        """
        super().__init__()
        self.color = color

    def emit(self, record: logging.LogRecord) -> None:
        """Print a record as a labelled line on the standard error.

        Args:
            record: The record to print
        """
        moment = datetime.fromtimestamp(record.created, UTC)
        stamp = f"{moment.strftime(TIMESTAMP_FORMAT)[:-3]}Z"
        for level, label, style in _STYLES:
            if record.levelno >= level:
                line = f"[{stamp}] {label} {record.getMessage()}"
                if style:
                    click.secho(line, err=True, color=self.color, **style)
                else:
                    # secho would append a reset code even to an unstyled line
                    click.echo(line, err=True, color=self.color)
                return


def debug(message: str) -> None:
    """Log a debug message, visible with --verbose.

    Args:
        message: The message to log
    """
    LOGGER.debug(message)


def error(message: str) -> None:
    """Log an error message.

    Args:
        message: The message to log
    """
    LOGGER.error(message)


def info(message: str) -> None:
    """Log an informational message.

    Args:
        message: The message to log
    """
    LOGGER.info(message)


def setup_console(color: bool, verbose: bool) -> None:
    """Install the console handler on the ``lucio`` logger.

    Repeated calls replace the previous handler, so one process can set the console
    up more than once (the test runner does).

    Args:
        color: Whether to color the messages, when the terminal supports it
        verbose: Whether to show the debug messages
    """
    # Consoles predating native ANSI support (e.g., Windows before 10) need fixing up
    colorama.just_fix_windows_console()
    logger = logging.getLogger("lucio")
    for handler in list(logger.handlers):
        if isinstance(handler, ConsoleHandler):
            logger.removeHandler(handler)
    logger.addHandler(ConsoleHandler(color=None if color else False))
    logger.propagate = False
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
