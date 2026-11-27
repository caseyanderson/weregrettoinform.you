"""End-to-end rendering pipeline."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from weregrettoinform.analyzer import Analyzer
from weregrettoinform.generator import Generator, TextSegment
from weregrettoinform.transformations import blackout, both, whitespace
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
    "both": both.apply,
}


def _prepare(
    text: str,
    name_forms: Iterable[str],
    record: dict[str, str] | None,
    both_proportion: int,
) -> tuple[Generator, TransformContext]:
    analyzed = Analyzer(text).analyze()
    generator = Generator(text, analyzed)
    segments = generator.build_text_segments()
    context = build_context(
        text,
        analyzed,
        segments,
        name_forms,
        record=record,
        both_proportion=both_proportion,
    )
    return generator, context


def render_variant(
    text: str,
    name_forms: Iterable[str],
    label: str,
    record: dict[str, str] | None = None,
    both_proportion: int = 50,
) -> str:
    generator, context = _prepare(text, name_forms, record, both_proportion)
    return generator.render_html(TRANSFORMATIONS[label](context))


def render_variants(
    text: str,
    name_forms: Iterable[str],
    record: dict[str, str] | None = None,
    both_proportion: int = 50,
) -> dict[str, str]:
    generator, context = _prepare(text, name_forms, record, both_proportion)

    return {
        label: generator.render_html(transform(context))
        for label, transform in TRANSFORMATIONS.items()
    }
