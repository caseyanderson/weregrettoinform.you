"""Shared application helper for transformations."""

from __future__ import annotations

from dataclasses import replace

from weregrettoinform.generator import TextSegment
from weregrettoinform.transformations.context import TransformContext
from weregrettoinform.transformations.selectors import should_preserve


def apply_css_class(
    context: TransformContext,
    css_class: str,
) -> list[TextSegment]:
    return [
        segment
        if should_preserve(segment, start, end, context)
        else replace(segment, css_class=css_class)
        for segment, (start, end) in zip(context.segments, context.offsets)
    ]
