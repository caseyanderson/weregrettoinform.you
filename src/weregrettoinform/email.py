"""Load exported .eml files into structured records."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import TypedDict

from weregrettoinform.structure import extract_message_body

EmailRecord = TypedDict(
    "EmailRecord",
    {
        "source_file": str,
        "subject": str,
        "date": str,
        "from": str,
        "to": str,
        "body": str,
    },
)


def load_eml_files(directory: Path) -> list[EmailRecord]:
    records: list[EmailRecord] = []

    for path in sorted(directory.glob("*.eml")):
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())

        html_parts = [
            part for part in message.walk() if part.get_content_type() == "text/html"
        ]
        html = html_parts[0].get_content() if html_parts else ""

        records.append(
            {
                "source_file": path.name,
                "subject": str(message.get("Subject", "")),
                "date": str(message.get("Date", "")),
                "from": str(message.get("From", "")),
                "to": str(message.get("To", "")),
                "body": extract_message_body(html),
            }
        )

    return records
