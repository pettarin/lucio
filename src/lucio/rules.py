"""Replacement rules: loading them from a YAML file, and applying them to a block result.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import re
from dataclasses import replace
from pathlib import Path

import yaml

from lucio.errors import RulesError
from lucio.model import Command, Count, ExecutionResult, Rule, RuleHit, Stream

COUNT_VALUES = {count.value: count for count in Count}
FIELD_KEYS = frozenset({"count", "id", "replacement", "streams", "target", "type"})
"""The fields of a rule, all required."""
RULE_TYPES = frozenset({"re"})
RULES_FILE_NAMES = ("lucio.rules.yaml", ".lucio.rules.yaml")
"""The names a rules file is looked up by in the working directory, in order of precedence."""
STREAM_VALUES = {stream.value: stream for stream in Stream}
TOP_KEY = "rules"

_SUBSTITUTIONS = {Count.ALL: 0, Count.FIRST: 1}
"""The ``count`` argument of :meth:`re.Pattern.sub` for each spelling, 0 meaning all."""


def apply_rules(
    rules: list[Rule], result: ExecutionResult, command: Command
) -> tuple[ExecutionResult, list[RuleHit]]:
    """Return ``result`` with every rule applied, in order, to the streams it names.

    An execute block exposes its captured stdout and stderr; an include block exposes
    the content of its file, which the result carries as stdout, under the ``include``
    stream, so a rule for stdout never touches an included file and vice versa. The
    hits say which rules found something, in the order they were applied.
    """
    hits: list[RuleHit] = []
    if command is Command.INCLUDE:
        stdout = _rewrite(rules, Stream.INCLUDE, result.stdout, hits)
        return replace(result, stdout=stdout), hits
    stdout = _rewrite(rules, Stream.STDOUT, result.stdout, hits)
    stderr = _rewrite(rules, Stream.STDERR, result.stderr, hits)
    return replace(result, stderr=stderr, stdout=stdout), hits


def find_rules_file(directory: Path) -> Path | None:
    """Return the rules file found in ``directory`` by its conventional name, if any."""
    for name in RULES_FILE_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def load_rules(path: Path) -> list[Rule]:
    """Read and validate the rules file at ``path``, returning its rules in file order.

    The whole file is validated before any rule is returned, the replacements included,
    so a malformed rule surfaces before any block is executed.
    """
    source = str(path)
    try:
        with path.open(encoding="utf-8") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        raise RulesError(source, f"not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise RulesError(source, exc.strerror or str(exc)) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(source, f"not valid YAML: {exc}") from exc

    if not isinstance(document, dict) or set(document) != {TOP_KEY}:
        raise RulesError(source, f"the document must be a mapping with the single key '{TOP_KEY}'")
    entries = document[TOP_KEY]
    if not isinstance(entries, list):
        raise RulesError(source, f"'{TOP_KEY}' must be a list of rules")

    rules: list[Rule] = []
    seen: set[str] = set()
    for position, entry in enumerate(entries, start=1):
        rule = _parse_rule(entry, position, source)
        if rule.identifier in seen:
            raise RulesError(source, f"rule {position}: duplicate id '{rule.identifier}'")
        seen.add(rule.identifier)
        rules.append(rule)
    return rules


def _parse_rule(entry: object, position: int, source: str) -> Rule:
    """Validate one entry of the rules list, returning the rule it spells."""
    where = f"rule {position}"
    if not isinstance(entry, dict):
        raise RulesError(source, f"{where}: must be a mapping")
    if "id" in entry:
        identifier = _text(entry["id"], "id", where, source)
        where = f"rule {position} ('{identifier}')"
    missing = sorted(FIELD_KEYS - set(entry))
    if missing:
        raise RulesError(source, f"{where}: missing {_listed(missing)}")
    unknown = sorted(str(key) for key in entry if key not in FIELD_KEYS)
    if unknown:
        raise RulesError(source, f"{where}: unknown {_listed(unknown)}")

    kind = entry["type"]
    if not isinstance(kind, str) or kind not in RULE_TYPES:
        raise RulesError(source, f"{where}: 'type' must be 're', got {kind!r}")
    count = _pick(entry["count"], COUNT_VALUES, "count", where, source)
    streams = entry["streams"]
    if not isinstance(streams, list) or not streams:
        raise RulesError(source, f"{where}: 'streams' must be a non-empty list")
    selected = frozenset(
        _pick(stream, STREAM_VALUES, "streams", where, source) for stream in streams
    )
    target = _text(entry["target"], "target", where, source)
    replacement = _text(entry["replacement"], "replacement", where, source)
    try:
        pattern = re.compile(target)
    except re.error as exc:
        raise RulesError(source, f"{where}: 'target' is not a valid regex: {exc}") from exc
    try:
        # The template is parsed whether or not anything matches, so this checks the
        # backreferences against the groups of the target
        pattern.sub(replacement, "")
    except re.error as exc:
        raise RulesError(source, f"{where}: 'replacement' is not valid: {exc}") from exc
    return Rule(
        count=count,
        identifier=identifier,
        replacement=replacement,
        streams=selected,
        target=pattern,
    )


def _listed(keys: list[str]) -> str:
    """Return the keys quoted and comma-separated, for a message."""
    return ", ".join(repr(key) for key in keys)


def _pick[T](value: object, choices: dict[str, T], field: str, where: str, source: str) -> T:
    """Return the member of ``choices`` spelled by ``value``, or fail naming the spellings."""
    if isinstance(value, str) and value in choices:
        return choices[value]
    spellings = _listed(sorted(choices))
    raise RulesError(source, f"{where}: '{field}' must be one of {spellings}, got {value!r}")


def _rewrite(rules: list[Rule], stream: Stream, text: str, hits: list[RuleHit]) -> str:
    """Return ``text`` with every rule naming ``stream`` applied to it, in order.

    A rule that found something is appended to ``hits``; one that found nothing is not.
    """
    for rule in rules:
        if stream not in rule.streams:
            continue
        text, substitutions = rule.target.subn(
            rule.replacement, text, count=_SUBSTITUTIONS[rule.count]
        )
        if substitutions:
            hits.append(RuleHit(rule.identifier, stream, substitutions))
    return text


def _text(value: object, field: str, where: str, source: str) -> str:
    """Return ``value`` if it is a string, or fail naming the field."""
    if not isinstance(value, str):
        raise RulesError(source, f"{where}: '{field}' must be a string, got {value!r}")
    return value
