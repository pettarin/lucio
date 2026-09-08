"""Tests for the replacement rules: their lookup, their loading, and their application.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import re
from pathlib import Path

import pytest

from lucio.errors import RulesError
from lucio.model import Command, Count, ExecutionResult, Rule, RuleHit, Stream
from lucio.rules import RULES_FILE_NAMES, apply_rules, find_rules_file, load_rules

EXAMPLE = Path(__file__).parent.parent / "res" / "lucio.rules.yaml"
"""The example rules file shipped with the repository."""
RULES = "rules.yaml"


def rule(target, replacement, streams=("stdout",), count="all", identifier="r"):
    return Rule(
        count=Count(count),
        identifier=identifier,
        replacement=replacement,
        streams=frozenset(Stream(stream) for stream in streams),
        target=re.compile(target),
    )


def entry(**overrides):
    """Return the YAML text of one valid rule, with any field overridden or removed."""
    fields = {
        "id": "r",
        "type": "re",
        "streams": "[stdout]",
        "target": "foo",
        "replacement": "bar",
        "count": "all",
    }
    fields.update(overrides)
    lines = [f"    {key}: {value}" for key, value in fields.items() if value is not None]
    return "rules:\n  - " + "\n".join(lines)[4:] + "\n"


def load(tmp_path, text):
    path = tmp_path / RULES
    path.write_text(text, encoding="utf-8")
    return load_rules(path)


def failing(tmp_path, text):
    with pytest.raises(RulesError) as info:
        load(tmp_path, text)
    assert info.value.path == str(tmp_path / RULES)
    return info.value.message


class TestFindRulesFile:
    def test_nothing_without_a_file(self, tmp_path):
        assert find_rules_file(tmp_path) is None

    @pytest.mark.parametrize("name", RULES_FILE_NAMES)
    def test_either_name_is_found(self, tmp_path, name):
        (tmp_path / name).write_text("rules: []\n", encoding="utf-8")
        assert find_rules_file(tmp_path) == tmp_path / name

    def test_the_undotted_name_wins(self, tmp_path):
        for name in RULES_FILE_NAMES:
            (tmp_path / name).write_text("rules: []\n", encoding="utf-8")
        assert find_rules_file(tmp_path) == tmp_path / RULES_FILE_NAMES[0]

    def test_a_directory_is_not_a_rules_file(self, tmp_path):
        (tmp_path / RULES_FILE_NAMES[0]).mkdir()
        (tmp_path / RULES_FILE_NAMES[1]).write_text("rules: []\n", encoding="utf-8")
        assert find_rules_file(tmp_path) == tmp_path / RULES_FILE_NAMES[1]


class TestLoadRules:
    def test_the_shipped_example_loads_in_file_order(self):
        rules = load_rules(EXAMPLE)
        assert [r.identifier for r in rules] == ["rule_1", "rule_2", "rule_3", "rule_4"]
        assert rules[0] == rule("foo", "baz", ["stderr"], "first", "rule_1")
        assert rules[2].streams == frozenset({Stream.STDERR, Stream.STDOUT})
        assert rules[3] == rule("ba([^z\n]*)", "bazbazbaz", ["include"], "first", "rule_4")

    def test_an_empty_list_holds_no_rules(self, tmp_path):
        assert load(tmp_path, "rules: []\n") == []

    def test_a_repeated_stream_counts_once(self, tmp_path):
        (loaded,) = load(tmp_path, entry(streams="[stdout, stdout]"))
        assert loaded.streams == frozenset({Stream.STDOUT})

    def test_the_target_is_compiled(self, tmp_path):
        (loaded,) = load(tmp_path, entry(target='"a(b)"'))
        assert loaded.target.pattern == "a(b)"
        assert loaded.target.groups == 1

    def test_a_missing_file(self, tmp_path):
        with pytest.raises(RulesError, match=r"No such file") as info:
            load_rules(tmp_path / RULES)
        assert str(info.value) == f"{tmp_path / RULES}: No such file or directory"

    def test_an_undecodable_file(self, tmp_path):
        (tmp_path / RULES).write_bytes(b"rules: [\xff]\n")
        with pytest.raises(RulesError, match=r"not valid UTF-8"):
            load_rules(tmp_path / RULES)

    def test_invalid_yaml(self, tmp_path):
        assert failing(tmp_path, "rules: [\n").startswith("not valid YAML: ")

    @pytest.mark.parametrize("text", ["", "[]\n", "other: 1\n", "rules: []\nother: 1\n"])
    def test_the_document_must_hold_the_rules_key_alone(self, tmp_path, text):
        message = failing(tmp_path, text)
        assert message == "the document must be a mapping with the single key 'rules'"

    @pytest.mark.parametrize("text", ["rules:\n", "rules: 1\n", "rules: {}\n"])
    def test_the_rules_must_be_a_list(self, tmp_path, text):
        assert failing(tmp_path, text) == "'rules' must be a list of rules"

    def test_a_rule_must_be_a_mapping(self, tmp_path):
        assert failing(tmp_path, "rules: [1]\n") == "rule 1: must be a mapping"

    def test_a_missing_field_is_named(self, tmp_path):
        assert failing(tmp_path, entry(count=None)) == "rule 1 ('r'): missing 'count'"

    def test_every_missing_field_is_named(self, tmp_path):
        message = failing(tmp_path, entry(id=None, target=None))
        assert message == "rule 1: missing 'id', 'target'"

    def test_an_unknown_field_is_named(self, tmp_path):
        assert failing(tmp_path, entry(extra=1)) == "rule 1 ('r'): unknown 'extra'"

    def test_the_id_must_be_a_string(self, tmp_path):
        assert failing(tmp_path, entry(id=1)) == "rule 1: 'id' must be a string, got 1"

    def test_a_duplicate_id(self, tmp_path):
        assert failing(tmp_path, entry() + entry()[7:]) == "rule 2: duplicate id 'r'"

    @pytest.mark.parametrize("kind", ["str", "1", "[re]"])
    def test_the_type_must_be_re(self, tmp_path, kind):
        message = failing(tmp_path, entry(type=kind))
        assert message.startswith("rule 1 ('r'): 'type' must be 're', got ")

    @pytest.mark.parametrize("count", ["none", "1", "[all]"])
    def test_the_count_must_be_first_or_all(self, tmp_path, count):
        message = failing(tmp_path, entry(count=count))
        assert message.startswith("rule 1 ('r'): 'count' must be one of 'all', 'first', got ")

    @pytest.mark.parametrize("streams", ["stdout", "[]", "1"])
    def test_the_streams_must_be_a_non_empty_list(self, tmp_path, streams):
        assert failing(tmp_path, entry(streams=streams)) == (
            "rule 1 ('r'): 'streams' must be a non-empty list"
        )

    def test_an_unknown_stream_is_named(self, tmp_path):
        assert failing(tmp_path, entry(streams="[stdout, stdin]")) == (
            "rule 1 ('r'): 'streams' must be one of 'include', 'stderr', 'stdout', got 'stdin'"
        )

    @pytest.mark.parametrize("field", ["target", "replacement"])
    def test_target_and_replacement_must_be_strings(self, tmp_path, field):
        message = failing(tmp_path, entry(**{field: 1}))
        assert message == f"rule 1 ('r'): '{field}' must be a string, got 1"

    def test_an_invalid_regex_is_reported(self, tmp_path):
        message = failing(tmp_path, entry(target='"("'))
        assert message.startswith("rule 1 ('r'): 'target' is not a valid regex: ")

    def test_a_backreference_to_a_missing_group_is_reported(self, tmp_path):
        message = failing(tmp_path, entry(target='"(a)"', replacement='"\\\\2"'))
        assert message.startswith("rule 1 ('r'): 'replacement' is not valid: ")

    def test_a_backreference_to_an_existing_group_is_accepted(self, tmp_path):
        (loaded,) = load(tmp_path, entry(target='"(a)"', replacement='"\\\\1\\\\1"'))
        assert loaded.replacement == "\\1\\1"


class TestApplyRules:
    def apply(self, rules, stdout="", stderr="", command=Command.EXECUTE):
        """Return the rewritten result alone; TestRuleHits covers the hits."""
        result = ExecutionResult(exit_code=0, stderr=stderr, stdout=stdout)
        rewritten, _ = apply_rules(rules, result, command)
        return rewritten

    def test_no_rules_leave_the_result_alone(self):
        result = ExecutionResult(exit_code=3, stderr="err\n", stdout="out\n")
        assert apply_rules([], result, Command.EXECUTE) == (result, [])

    def test_stdout_and_stderr_are_rewritten_by_their_own_rules(self):
        rules = [rule("foo", "out", ["stdout"]), rule("foo", "err", ["stderr"])]
        result = self.apply(rules, stdout="foo\n", stderr="foo\n")
        assert (result.stdout, result.stderr) == ("out\n", "err\n")

    def test_one_rule_may_name_both_streams(self):
        result = self.apply([rule("o", "0", ["stdout", "stderr"])], stdout="foo\n", stderr="bo\n")
        assert (result.stdout, result.stderr) == ("f00\n", "b0\n")

    def test_the_exit_code_is_kept(self):
        result = ExecutionResult(exit_code=7, stderr="", stdout="foo\n")
        rewritten, _ = apply_rules([rule("foo", "bar")], result, Command.EXECUTE)
        assert rewritten.exit_code == 7

    def test_first_rewrites_one_match_and_all_rewrites_every_match(self):
        first = self.apply([rule("o", "0", count="first")], stdout="foo boo\n").stdout
        every = self.apply([rule("o", "0", count="all")], stdout="foo boo\n").stdout
        assert (first, every) == ("f0o boo\n", "f00 b00\n")

    def test_rules_apply_in_order_each_seeing_the_previous_result(self):
        forward = [rule("a", "b"), rule("b", "c")]
        backward = [rule("b", "c"), rule("a", "b")]
        assert self.apply(forward, stdout="a\n").stdout == "c\n"
        assert self.apply(backward, stdout="a\n").stdout == "b\n"

    def test_the_shipped_example_on_the_streams(self):
        result = self.apply(load_rules(EXAMPLE), stdout="foo bar\n", stderr="foo\n")
        assert (result.stdout, result.stderr) == ("bazbaz\n", "bazbazz\n")

    def test_backreferences_work_in_the_replacement(self):
        result = self.apply([rule(r"(\w+)=(\w+)", r"\2=\1")], stdout="a=b\n")
        assert result.stdout == "b=a\n"

    def test_the_regex_spans_lines(self):
        result = self.apply([rule(r"(?m)^\d+ ", "")], stdout="1 a\n2 b\n")
        assert result.stdout == "a\nb\n"

    def test_include_content_follows_only_the_include_stream(self):
        rules = [rule("foo", "out", ["stdout"]), rule("foo", "inc", ["include"])]
        assert self.apply(rules, stdout="foo\n", command=Command.INCLUDE).stdout == "inc\n"
        assert self.apply(rules, stdout="foo\n").stdout == "out\n"

    def test_the_stderr_of_an_include_is_never_touched(self):
        rules = [rule("", "x", ["stderr", "include"])]
        result = self.apply(rules, stdout="a", stderr="", command=Command.INCLUDE)
        assert (result.stdout, result.stderr) == ("xax", "")


class TestRuleHits:
    def hits(self, rules, stdout="", stderr="", command=Command.EXECUTE):
        result = ExecutionResult(exit_code=0, stderr=stderr, stdout=stdout)
        _, hits = apply_rules(rules, result, command)
        return hits

    def test_a_rule_that_finds_nothing_is_not_a_hit(self):
        assert self.hits([rule("foo", "bar")], stdout="baz\n") == []

    def test_a_hit_counts_the_substitutions(self):
        hits = self.hits([rule("o", "0", identifier="zero")], stdout="foo boo\n")
        assert hits == [RuleHit("zero", Stream.STDOUT, 4)]

    def test_first_counts_one_substitution(self):
        hits = self.hits([rule("o", "0", count="first")], stdout="foo boo\n")
        assert hits == [RuleHit("r", Stream.STDOUT, 1)]

    def test_hits_come_in_application_order_stdout_first(self):
        rules = [
            rule("a", "b", ["stderr", "stdout"], identifier="one"),
            rule("b", "c", identifier="two"),
        ]
        assert self.hits(rules, stdout="a\n", stderr="a\n") == [
            RuleHit("one", Stream.STDOUT, 1),
            RuleHit("two", Stream.STDOUT, 1),
            RuleHit("one", Stream.STDERR, 1),
        ]

    def test_a_rule_naming_a_stream_the_block_lacks_is_no_hit(self):
        rules = [rule("a", "b", ["stderr"]), rule("a", "b", ["include"])]
        assert self.hits(rules, stdout="a\n") == []

    def test_an_include_hit_names_the_include_stream(self):
        rules = [rule("a", "b", ["include", "stdout"])]
        assert self.hits(rules, stdout="a", command=Command.INCLUDE) == [
            RuleHit("r", Stream.INCLUDE, 1)
        ]
