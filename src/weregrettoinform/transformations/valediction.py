"""Valediction detection and fixed-block rules."""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass
from email.utils import parseaddr

from weregrettoinform.analyzer import AnalyzedToken
from weregrettoinform.structure import (
    SIGNOFF_WORDS,
    name_spans,
    starts_with_signoff,
)
from weregrettoinform.transformations.context import TransformContext

SIGNOFF_PARTS = {word.casefold() for phrase in SIGNOFF_WORDS for word in phrase.split()}

SIGNOFF_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(phrase) for phrase in SIGNOFF_WORDS) + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValedictionPlan:
    black_indices: frozenset[int]
    preserve_indices: frozenset[int]
    matched: bool
    start: int | None
    end: int | None
    org_hints: frozenset[str]


def from_hints(raw_from: str) -> tuple[str, str, frozenset[str]]:
    display_name, address = parseaddr(raw_from)
    hints = set()

    for part in display_name.replace(",", " ").split():
        cleaned = part.strip(".,")
        if len(cleaned) > 2:
            hints.add(cleaned.casefold())

    if "@" in address:
        domain = address.rsplit("@", 1)[1]
        label = domain.split(".")[0]
        if len(label) > 2:
            hints.add(label.casefold())

    return display_name, address, frozenset(hints)


def find_valediction_span(text: str) -> tuple[int | None, int | None, str]:
    cursor = 0
    spans: list[tuple[int, int, str]] = []

    for paragraph in text.split("\n\n"):
        start = text.find(paragraph, cursor)
        cursor = start + len(paragraph) + 2
        spans.append((start, start + len(paragraph), paragraph))

    for start, end, paragraph in reversed(spans):
        if start < len(text) * 0.5:
            continue

        if starts_with_signoff(paragraph):
            return start, len(text), text[start:]

    matches = list(SIGNOFF_PATTERN.finditer(text))

    if matches:
        v_start = matches[-1].start()
        if v_start >= len(text) * 0.5:
            return v_start, len(text), text[v_start:]

    return None, None, ""


def plan(
    context: TransformContext,
    analyzed: list[list[AnalyzedToken]],
    text: str,
    record: dict[str, str],
    name_forms: Iterable[str],
) -> ValedictionPlan:
    v_start, v_end, v_text = find_valediction_span(text)

    if v_start is None or v_end is None:
        return ValedictionPlan(
            black_indices=frozenset(),
            preserve_indices=frozenset(),
            matched=False,
            start=None,
            end=None,
            org_hints=frozenset(),
        )

    _display_name, _address, org_hints = from_hints(record.get("from", ""))

    signoff_match = SIGNOFF_PATTERN.search(v_text)
    signoff_absolute_end = v_start + signoff_match.end() if signoff_match else v_start

    signoff_starts = set()
    signoff_symbol_starts = set()
    identity_starts = set()
    all_token_starts = set()

    for sentence in analyzed:
        for token in sentence:
            if not (v_start <= token.start < v_end):
                continue

            all_token_starts.add(token.start)
            lower = token.text.casefold()

            if lower in SIGNOFF_PARTS and token.start < signoff_absolute_end:
                signoff_starts.add(token.start)
            elif (
                token.part_of_speech_group == "symbol"
                and token.start <= signoff_absolute_end
            ):
                signoff_symbol_starts.add(token.start)
            elif token.part_of_speech in {"NNP", "NNPS"} or lower in org_hints:
                identity_starts.add(token.start)

    for span_start, span_end in name_spans(v_text, name_forms):
        absolute_start = v_start + span_start
        absolute_end = v_start + span_end

        for sentence in analyzed:
            for token in sentence:
                if absolute_start <= token.start < absolute_end:
                    identity_starts.add(token.start)

    matched = bool(identity_starts)

    if matched:
        preserve_starts = signoff_starts | signoff_symbol_starts
        obscure_starts = all_token_starts - preserve_starts
    else:
        preserve_starts = set()
        obscure_starts = all_token_starts

    token_index_by_start = {
        segment.token.start: index
        for index, segment in enumerate(context.segments)
        if segment.token is not None
    }

    preserve_indices = {
        token_index_by_start[start]
        for start in preserve_starts
        if start in token_index_by_start
    }

    token_black_indices = {
        token_index_by_start[start]
        for start in obscure_starts
        if start in token_index_by_start
    }

    black_indices = set(token_black_indices)

    if matched:
        ordered = sorted(token_black_indices)

        for left, right in itertools.pairwise(ordered):
            for index in range(left + 1, right):
                segment = context.segments[index]
                if segment.token is None and "\n\n" not in segment.text:
                    black_indices.add(index)
    else:
        for index, (start, _) in enumerate(context.offsets):
            if v_start <= start < v_end:
                black_indices.add(index)

    return ValedictionPlan(
        black_indices=frozenset(black_indices),
        preserve_indices=frozenset(preserve_indices),
        matched=matched,
        start=v_start,
        end=v_end,
        org_hints=org_hints,
    )
