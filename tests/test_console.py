"""Tests for the console logging of the lucio CLI.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import logging
import re

import click
import pytest
from click.testing import CliRunner

from lucio.console import ConsoleHandler, debug, error, info, setup_console

_STAMP = re.compile(r"^(?P<prefix>\x1b\[\d+m)?\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\] ")
"""The UTC timestamp opening every console line, after any color code."""


def _warn(message):
    """Log a warning, a level the CLI has no caller for but the handler still labels."""
    logging.getLogger("lucio.cli").warning(message)


def _unstamped(line: str) -> str:
    """Return a console line without its timestamp, asserting it carried one."""
    match = _STAMP.match(line)
    assert match is not None, line
    return (match.group("prefix") or "") + line[match.end() :]


@pytest.fixture(autouse=True)
def restore_console():
    """Leave the lucio logger as the other tests expect it."""
    yield
    setup_console(color=True, verbose=False)


def _run(handler_color: bool | None, action) -> str:
    """Run an action with a console of the given color mode, capturing the output."""
    logger = logging.getLogger("lucio")
    level = logger.level
    handlers = list(logger.handlers)
    for previous in handlers:
        logger.removeHandler(previous)
    logger.addHandler(ConsoleHandler(color=handler_color))
    logger.setLevel(logging.DEBUG)

    @click.command()
    def emit() -> None:
        action()

    try:
        return CliRunner().invoke(emit).output
    finally:
        logger.handlers.clear()
        for previous in handlers:
            logger.addHandler(previous)
        logger.setLevel(level)


class TestConsoleHandler:
    """Test cases for the ConsoleHandler labels and colors."""

    def test_the_labels(self):
        """Each level gets its label."""
        output = _run(
            False,
            lambda: (debug("d"), info("i"), _warn("w"), error("e")),
        )

        assert [_unstamped(line) for line in output.splitlines()] == [
            "[DEBU] d",
            "[INFO] i",
            "[WARN] w",
            "[ERRO] e",
        ]

    def test_critical_is_an_error(self):
        """A level above ERROR still gets the error label."""
        output = _run(False, lambda: logging.getLogger("lucio.cli").critical("boom"))

        assert _unstamped(output.strip()) == "[ERRO] boom"

    def test_the_colors_when_forced(self):
        """With color forced on, the styled levels carry ANSI codes."""
        output = _run(
            True,
            lambda: (debug("d"), info("i"), _warn("w"), error("e")),
        )

        lines = [_unstamped(line) for line in output.splitlines()]

        assert lines[0] == "\x1b[2m[DEBU] d\x1b[0m"
        # An informational message stays in the default color
        assert lines[1] == "[INFO] i"
        assert lines[2] == "\x1b[33m[WARN] w\x1b[0m"
        assert lines[3] == "\x1b[31m[ERRO] e\x1b[0m"

    def test_the_timestamp_opens_the_line(self):
        """Every line starts with a millisecond UTC stamp."""
        output = _run(False, lambda: info("stamped"))

        assert re.fullmatch(
            r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\] \[INFO\] stamped",
            output.strip(),
        )

    def test_no_colors_when_disabled(self):
        """With color off, no ANSI code is emitted."""
        output = _run(False, lambda: (info("i"), error("e")))

        assert "\x1b" not in output


class TestSetupConsole:
    """Test cases for the setup of the console."""

    def test_the_default_level_hides_debug(self):
        """Without --verbose the debug messages are hidden."""
        setup_console(color=False, verbose=False)

        @click.command()
        def emit() -> None:
            debug("hidden")
            info("shown")

        output = CliRunner().invoke(emit).output

        assert _unstamped(output.strip()) == "[INFO] shown"

    def test_verbose_shows_debug(self):
        """With --verbose the debug messages appear."""
        setup_console(color=False, verbose=True)

        @click.command()
        def emit() -> None:
            debug("shown")

        assert _unstamped(CliRunner().invoke(emit).output.strip()) == "[DEBU] shown"

    def test_repeated_setup_does_not_duplicate_handlers(self):
        """Setting the console up again replaces the handler instead of stacking it."""
        setup_console(color=False, verbose=False)
        setup_console(color=False, verbose=False)

        logger = logging.getLogger("lucio")
        console_handlers = [
            handler for handler in logger.handlers if isinstance(handler, ConsoleHandler)
        ]

        assert len(console_handlers) == 1

        @click.command()
        def emit() -> None:
            info("once")

        assert _unstamped(CliRunner().invoke(emit).output.strip()) == "[INFO] once"

    def test_the_package_logger_has_a_null_handler(self):
        """The lucio logger carries a NullHandler for the library users."""
        assert any(
            isinstance(handler, logging.NullHandler)
            for handler in logging.getLogger("lucio").handlers
        )
