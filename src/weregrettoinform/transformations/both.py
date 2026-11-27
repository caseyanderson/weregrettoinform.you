"""Random run-based mix of blocked and invisible body text."""

from __future__ import annotations

import random
from dataclasses import replace

from weregrettoinform.generator import TextSegment
from weregrettoinform.transformations.blackout import BLACKOUT_CSS_CLASS
from weregrettoinform.transformations.body_runs import (
    build_body_runs,
    salutation_name_indices,
)
from weregrettoinform.transformations.context import TransformContext
from weregrettoinform.transformations.valediction import plan as valediction_plan
from weregrettoinform.transformations.whitespace import WHITESPACE_CSS_CLASS


def apply(context: TransformContext) -> list[TextSegment]:
    proportion = max(0, min(100, context.both_proportion))
    probability = proportion / 100

    valediction = valediction_plan(
        context,
        context.analyzed,
        context.text,
        context.record,
        context.name_forms,
    )

    updated = list(context.segments)
    runs = build_body_runs(
        context,
        context.analyzed,
        context.text,
        valediction.start,
        valediction.end,
    )

    for run_number, run in enumerate(runs):
        if probability <= 0:
            mode = WHITESPACE_CSS_CLASS
        elif probability >= 1 or run_number == 0:
            mode = BLACKOUT_CSS_CLASS
        else:
            mode = (
                BLACKOUT_CSS_CLASS
                if random.random() < probability
                else WHITESPACE_CSS_CLASS
            )

        for index in run:
            updated[index] = replace(context.segments[index], css_class=mode)

    for index in salutation_name_indices(context, context.text):
        updated[index] = replace(context.segments[index], css_class=BLACKOUT_CSS_CLASS)

    for index in valediction.black_indices:
        updated[index] = replace(context.segments[index], css_class=BLACKOUT_CSS_CLASS)

    for index in valediction.preserve_indices:
        updated[index] = replace(context.segments[index], css_class="")

    return updated
