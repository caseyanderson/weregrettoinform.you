"""Structural detection and body extraction for rejection emails."""

from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup
from bs4.element import Tag

GREETING_WORDS = ("hello", "hi", "dear", "hey", "greetings")

SIGNOFF_WORDS = (
    "sincerely",
    "best",
    "regards",
    "kind regards",
    "thank you",
    "thanks",
    "warmly",
    "cheers",
    "yours truly",
)


def contains_name(text: str, name_forms: Iterable[str]) -> bool:
    return any(
        re.search(rf"\b{re.escape(form)}\b", text, re.IGNORECASE) for form in name_forms
    )


def starts_with_greeting(text: str) -> bool:
    stripped = text.strip()
    return any(
        re.match(rf"^{re.escape(word)}\b", stripped, re.IGNORECASE)
        for word in GREETING_WORDS
    )


def starts_with_signoff(text: str) -> bool:
    stripped = text.strip()
    return any(
        re.match(rf"^{re.escape(word)}\b", stripped, re.IGNORECASE)
        for word in SIGNOFF_WORDS
    )


def is_salutation(text: str, name_forms: Iterable[str] = ()) -> bool:
    return bool(text) and (
        starts_with_greeting(text) or contains_name(text, name_forms)
    )


def is_valediction(text: str) -> bool:
    return bool(text.strip()) and starts_with_signoff(text)


def name_spans(text: str, name_forms: Iterable[str]) -> list[tuple[int, int]]:
    spans = []

    for form in name_forms:
        for match in re.finditer(rf"\b{re.escape(form)}\b", text, re.IGNORECASE):
            spans.append((match.start(), match.end()))

    return sorted(set(spans))


def paragraph_text(element: Tag) -> str:
    marker = "\x00BR\x00"

    for br in element.find_all("br"):
        br.replace_with(marker)

    paragraphs = [
        paragraph.strip()
        for paragraph in element.get_text(" ", strip=True).split(marker)
        if paragraph.strip()
    ]

    return "\n\n".join(paragraphs)


def extract_message_body(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    body_tag = soup.body
    if body_tag is None:
        return soup.get_text(" ", strip=True)

    children = body_tag.find_all(recursive=False)
    if not children:
        return soup.get_text(" ", strip=True)

    outer = max(
        children,
        key=lambda child: len(child.get_text(" ", strip=True)),
    )

    parts = [paragraph_text(child) for child in outer.find_all(recursive=False)]

    for part in parts:
        if starts_with_greeting(part):
            return part

    return max(parts, key=len) if parts else outer.get_text(" ", strip=True)
