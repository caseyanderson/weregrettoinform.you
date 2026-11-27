"""Shared context for email transformations."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from nltk.sentiment.vader import SentimentIntensityAnalyzer

from weregrettoinform.analyzer import AnalyzedToken
from weregrettoinform.generator import TextSegment
from weregrettoinform.structure import GREETING_WORDS


@dataclass(frozen=True)
class TransformContext:
    segments: list[TextSegment]
    offsets: list[tuple[int, int]]
    salutation: str
    name_forms: frozenset[str]
    negative_starts: frozenset[int]
    text: str = ""
    analyzed: list[list[AnalyzedToken]] = field(default_factory=list)
    record: dict[str, str] = field(default_factory=dict)
    both_proportion: int = 50


def find_salutation(text: str) -> str:
    pattern = r"\b(?:" + "|".join(re.escape(word) for word in GREETING_WORDS) + r")\b"
    match = re.match(rf"^{pattern}[^\n,]*[,]?", text, re.IGNORECASE)
    return match.group(0) if match else ""


def segment_offsets(segments: list[TextSegment]) -> list[tuple[int, int]]:
    offsets = []
    cursor = 0

    for segment in segments:
        offsets.append((cursor, cursor + len(segment.text)))
        cursor += len(segment.text)

    return offsets


def negative_token_starts(
    analyzed_sentences: list[list[AnalyzedToken]],
    lexicon: dict[str, float] | None = None,
) -> frozenset[int]:
    if lexicon is None:
        lexicon = SentimentIntensityAnalyzer().lexicon

    return frozenset(
        token.start
        for sentence in analyzed_sentences
        for token in sentence
        if lexicon.get(token.text.lower(), 0) < 0
    )


def build_context(
    text: str,
    analyzed_sentences: list[list[AnalyzedToken]],
    segments: list[TextSegment],
    name_forms: Iterable[str],
    record: dict[str, str] | None = None,
    both_proportion: int = 50,
) -> TransformContext:
    return TransformContext(
        segments=segments,
        offsets=segment_offsets(segments),
        salutation=find_salutation(text),
        name_forms=frozenset(name_forms),
        negative_starts=negative_token_starts(analyzed_sentences),
        text=text,
        analyzed=analyzed_sentences,
        record=dict(record) if record is not None else {},
        both_proportion=both_proportion,
    )
