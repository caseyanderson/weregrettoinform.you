"""Blackout-box transformation."""

from __future__ import annotations

from weregrettoinform.generator import TextSegment
from weregrettoinform.transformations.base import apply_css_class
from weregrettoinform.transformations.context import TransformContext

BLACKOUT_CSS_CLASS = "blackout-box"


def apply(context: TransformContext) -> list[TextSegment]:
    return apply_css_class(context, BLACKOUT_CSS_CLASS)
