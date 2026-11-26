"""Command-line runner for the email rendering pipeline."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from weregrettoinform.email import load_eml_files
from weregrettoinform.identity import load_name_forms
from weregrettoinform.image import export_images
from weregrettoinform.pipeline import render_variants


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found")


def select_record(records: list[dict], query: str) -> dict:
    matches = [
        record
        for record in records
        if query.casefold() in record["source_file"].casefold()
    ]

    if not matches:
        available = "\n".join(f"  {record['source_file']}" for record in records)
        raise SystemExit(f"No email matches {query!r}.\nAvailable emails:\n{available}")

    if len(matches) > 1:
        ambiguous = "\n".join(f"  {record['source_file']}" for record in matches)
        raise SystemExit(
            f"More than one email matches {query!r}. "
            f"Use more of the filename:\n{ambiguous}"
        )

    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render one rejection email as blocked or whitespace art.",
    )
    parser.add_argument(
        "--email",
        help="Full or partial source .eml filename",
    )
    parser.add_argument(
        "--transform",
        choices=("blocked", "whitespace"),
        help="Transformation to render",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available source emails",
    )

    args = parser.parse_args()

    repo_root = find_repo_root(Path.cwd())
    records = load_eml_files(repo_root / "data/raw/emails")

    if args.list:
        for record in records:
            print(record["source_file"])
        return

    if not args.email:
        parser.error("--email is required unless --list is used")
    if not args.transform:
        parser.error("--transform is required unless --list is used")

    record = select_record(records, args.email)
    name_forms = load_name_forms(repo_root / "data/raw/identity.json")

    internal_label = "blocked" if args.transform == "blocked" else "hidden"
    all_rendered = render_variants(record["body"], name_forms)
    rendered = {internal_label: all_rendered[internal_label]}

    result = asyncio.run(
        export_images(
            rendered,
            record,
            repo_root / "output",
            repo_root / "data/processed/image-manifest.json",
        )
    )

    for entry in result.created:
        print(
            "created",
            args.transform,
            entry["format"],
            entry["output_file"],
            f"html={entry['html_file']}",
        )

    for entry in result.skipped:
        print(
            "skipped",
            args.transform,
            entry["format"],
            entry["existing_output_file"],
            f"html={entry['html_file']}",
        )


if __name__ == "__main__":
    main()
