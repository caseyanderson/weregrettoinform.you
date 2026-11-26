"""End-to-end rendering pipeline."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from weregrettoinform.analyzer import Analyzer
from weregrettoinform.generator import Generator, TextSegment
from weregrettoinform.transformations import blackout, whitespace
from weregrettoinform.transformations.context import (
    TransformContext,
    build_context,
)

TRANSFORMATIONS: dict[
    str,
    Callable[[TransformContext], list[TextSegment]],
] = {
    "blocked": blackout.apply,
    "hidden": whitespace.apply,
}


def render_variants(
    text: str,
    name_forms: Iterable[str],
) -> dict[str, str]:
    analyzed = Analyzer(text).analyze()
    generator = Generator(text, analyzed)
    segments = generator.build_text_segments()
    context = build_context(text, analyzed, segments, name_forms)

    return {
        label: generator.render_html(transform(context))
        for label, transform in TRANSFORMATIONS.items()
    }
