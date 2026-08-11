"""Tests for the lucio error hierarchy.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import pytest

from lucio.errors import (
    ExecutionError,
    ExecutionTimeoutError,
    ExitCodeMismatchError,
    LucioError,
    TemplateError,
    TemplateSyntaxError,
)


class TestHierarchy:
    @pytest.mark.parametrize(
        ("child", "parent"),
        [
            (ExecutionError, LucioError),
            (ExecutionTimeoutError, ExecutionError),
            (ExitCodeMismatchError, ExecutionError),
            (TemplateError, LucioError),
            (TemplateSyntaxError, TemplateError),
        ],
    )
    def test_is_subclass(self, child, parent):
        assert issubclass(child, parent)

    @pytest.mark.parametrize(
        "error_class", [ExecutionError, ExecutionTimeoutError, ExitCodeMismatchError, LucioError]
    )
    def test_execution_errors_are_not_template_errors(self, error_class):
        assert not issubclass(error_class, TemplateError)

    @pytest.mark.parametrize("error_class", [TemplateError, TemplateSyntaxError])
    def test_template_errors_are_not_execution_errors(self, error_class):
        assert not issubclass(error_class, ExecutionError)

    def test_lucio_error_is_an_exception(self):
        assert issubclass(LucioError, Exception)


class TestLucioError:
    @pytest.mark.parametrize(
        "error_class", [LucioError, ExecutionError, TemplateError, TemplateSyntaxError]
    )
    def test_str_is_prefixed_with_path_and_line(self, error_class):
        error = error_class("doc.template.md", 12, "something went wrong")
        assert str(error) == "doc.template.md:12: something went wrong"

    def test_attributes_are_kept(self):
        error = LucioError("doc.template.md", 12, "something went wrong")
        assert (error.path, error.line, error.message) == (
            "doc.template.md",
            12,
            "something went wrong",
        )

    def test_can_be_raised_and_caught_as_lucio_error(self):
        with pytest.raises(LucioError) as excinfo:
            raise TemplateSyntaxError("doc.template.md", 1, "boom")
        assert str(excinfo.value) == "doc.template.md:1: boom"


class TestExecutionTimeoutError:
    def test_message_names_the_timeout(self):
        error = ExecutionTimeoutError("doc.template.md", 7, 0.5)
        assert str(error) == "doc.template.md:7: block timed out after 0.5 seconds"

    def test_timeout_is_kept(self):
        assert ExecutionTimeoutError("doc.template.md", 7, 0.5).timeout == 0.5


class TestExitCodeMismatchError:
    def test_message_names_expected_actual_and_stderr(self):
        error = ExitCodeMismatchError("doc.template.md", 3, 0, 42, "boom\n")
        assert str(error) == (
            "doc.template.md:3: block exited with 42, expected 0; captured stderr:\nboom\n"
        )

    def test_details_are_kept(self):
        error = ExitCodeMismatchError("doc.template.md", 3, 0, 42, "boom\n")
        assert (error.expected, error.actual, error.stderr) == (0, 42, "boom\n")
