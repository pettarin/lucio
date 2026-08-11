"""lucio - Render Markdown templates by executing embedded bash blocks.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    ExitCodeMismatchError,
    LucioError,
    TemplateError,
    TemplateSyntaxError,
)

__version__ = "0.0.1"
__author__ = "Alberto Pettarin"
__email__ = "alberto@albertopettarin.it"

__all__ = [
    "ExecutionError",
    "ExecutionTimeoutError",
    "ExitCodeMismatchError",
    "LucioError",
    "TemplateError",
    "TemplateSyntaxError",
]
