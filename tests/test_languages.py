"""Tests for the embedded list of highlight.js language aliases.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import pytest

from lucio.languages import LANGUAGES


class TestLanguages:
    def test_the_table_was_parsed(self):
        # A handful of rows would mean the second column was read wrongly
        assert len(LANGUAGES) > 100

    @pytest.mark.parametrize(
        "language",
        ["bash", "c", "css", "html", "java", "json", "markdown", "python", "xml", "yaml"],
    )
    def test_common_languages_are_there(self, language):
        assert language in LANGUAGES

    @pytest.mark.parametrize("alias", ["js", "md", "py", "sh", "ts", "yml"])
    def test_aliases_are_there_too(self, alias):
        assert alias in LANGUAGES

    @pytest.mark.parametrize("absent", ["", "zzz", "not-a-language", "Language"])
    def test_what_is_not_a_language_is_absent(self, absent):
        assert absent not in LANGUAGES

    def test_every_entry_is_a_bare_lowercase_token(self):
        # Whitespace or an uppercase letter would mean a cell was split wrongly
        assert all(entry and entry == entry.lower().strip() for entry in LANGUAGES)
        assert not any(any(char.isspace() for char in entry) for entry in LANGUAGES)
