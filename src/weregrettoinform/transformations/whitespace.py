"""Invisible-whitespace transformation."""

from __future__ import annotations

from weregrettoinform.generator import TextSegment
from weregrettoinform.transformations.base import apply_css_class
from weregrettoinform.transformations.context import TransformContext

WHITESPACE_CSS_CLASS = "whitespace"


def apply(context: TransformContext) -> list[TextSegment]:
    return apply_css_class(context, WHITESPACE_CSS_CLASS)
