"""lucio - Render Markdown templates by executing embedded shell or code blocks.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import logging

from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    ExitCodeMismatchError,
    IncludeError,
    LucioError,
    TemplateError,
    TemplateSyntaxError,
    TotalTimeoutError,
)

# The package logs under the "lucio" logger; without a handler of the user's (the
# CLI installs its own), the records go nowhere, silently
logging.getLogger("lucio").addHandler(logging.NullHandler())

__version__ = "0.0.4"
__author__ = "Alberto Pettarin"
__email__ = "alberto@albertopettarin.it"

__all__ = [
    "ExecutionError",
    "ExecutionTimeoutError",
    "ExitCodeMismatchError",
    "IncludeError",
    "LucioError",
    "TemplateError",
    "TemplateSyntaxError",
    "TotalTimeoutError",
]
