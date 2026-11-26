"""Visibility rules shared by all text transformations."""

from __future__ import annotations

from weregrettoinform.generator import TextSegment
from weregrettoinform.structure import name_spans
from weregrettoinform.transformations.context import TransformContext


def is_salutation_segment(
    context: TransformContext,
    start: int,
    end: int,
) -> bool:
    if not context.salutation:
        return False

    spans = name_spans(context.salutation, context.name_forms)

    return end <= len(context.salutation) and not any(
        start >= span_start and end <= span_end for span_start, span_end in spans
    )


def is_negative_segment(
    segment: TextSegment,
    context: TransformContext,
) -> bool:
    return segment.token is not None and segment.token.start in context.negative_starts


def should_preserve(
    segment: TextSegment,
    start: int,
    end: int,
    context: TransformContext,
) -> bool:
    return is_salutation_segment(context, start, end) or is_negative_segment(
        segment, context
    )
