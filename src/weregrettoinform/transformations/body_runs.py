"""Body run selection shared by run-based transformations."""

from __future__ import annotations

from weregrettoinform.analyzer import AnalyzedToken
from weregrettoinform.generator import TextSegment
from weregrettoinform.structure import name_spans
from weregrettoinform.transformations.context import TransformContext
from weregrettoinform.transformations.selectors import should_preserve


def salutation_name_indices(
    context: TransformContext,
    text: str,
) -> frozenset[int]:
    if not context.salutation:
        return frozenset()

    salutation_start = text.find(context.salutation)
    if salutation_start == -1:
        return frozenset()

    spans = name_spans(context.salutation, context.name_forms)
    indices = set()

    for index, (start, end) in enumerate(context.offsets):
        for span_start, span_end in spans:
            if (
                salutation_start + span_start <= start
                and end <= salutation_start + span_end
            ):
                indices.add(index)

    return frozenset(indices)


def merge_short_runs(
    runs: list[list[int]],
    segments: list[TextSegment],
    min_stripped_length: int = 2,
) -> list[list[int]]:
    merged: list[list[int]] = []

    for run in runs:
        run_text = "".join(segments[index].text for index in run)

        if merged and len(run_text.strip()) < min_stripped_length:
            merged[-1].extend(run)
        else:
            merged.append(list(run))

    return merged


def build_body_runs(
    context: TransformContext,
    analyzed: list[list[AnalyzedToken]],
    text: str,
    valediction_start: int | None,
    valediction_end: int | None,
) -> list[list[int]]:
    salutation_end = len(context.salutation)
    salutation_indices = salutation_name_indices(context, text)

    sentence_ranges = [
        (sentence[0].start, sentence[-1].end) for sentence in analyzed if sentence
    ]

    def sentence_index_for(start: int) -> int | None:
        for index, (sentence_start, sentence_end) in enumerate(sentence_ranges):
            if sentence_start <= start < sentence_end:
                return index
        return None

    runs: list[list[int]] = []
    current: list[int] = []
    current_sentence: int | None = None

    def flush() -> None:
        nonlocal current, current_sentence
        if current:
            runs.append(current)
            current = []
            current_sentence = None

    for index, (segment, (start, end)) in enumerate(
        zip(context.segments, context.offsets)
    ):
        sentence_index = sentence_index_for(start)

        if sentence_index is None:
            flush()
            continue

        if start < salutation_end or index in salutation_indices:
            flush()
            continue

        if (
            valediction_start is not None
            and valediction_end is not None
            and valediction_start <= start < valediction_end
        ):
            flush()
            continue

        if should_preserve(segment, start, end, context):
            flush()
            continue

        if segment.token is None and "\n\n" in segment.text:
            flush()
            continue

        if current and sentence_index != current_sentence:
            flush()

        current.append(index)
        current_sentence = sentence_index

    flush()
    return merge_short_runs(runs, context.segments)
