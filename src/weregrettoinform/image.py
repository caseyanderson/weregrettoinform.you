"""Export rendered HTML variants to Instagram-sized PNGs."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

CANVAS_SIZES = {
    "post": (1080, 1350),
    "story": (1080, 1920),
}

PADDING = 48
VIEWPORT_WIDTH = 1080


@dataclass(frozen=True)
class ExportResult:
    created: list[dict]
    skipped: list[dict]


async def _capture_page(browser, html: str) -> Image.Image:
    page = await browser.new_page(
        viewport={"width": VIEWPORT_WIDTH, "height": 200},
        device_scale_factor=2,
    )
    await page.set_content(html, wait_until="load")
    await page.evaluate("() => document.fonts.ready.then(() => true)")
    data = await page.screenshot(full_page=True)
    await page.close()

    return Image.open(io.BytesIO(data)).convert("RGB")


def _fit_to_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas_w, canvas_h = size
    max_w = canvas_w - 2 * PADDING
    max_h = canvas_h - 2 * PADDING

    scale = min(max_w / image.width, max_h / image.height, 1.0)
    fitted_w = max(1, round(image.width * scale))
    fitted_h = max(1, round(image.height * scale))

    fitted = image.resize((fitted_w, fitted_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(
        fitted,
        ((canvas_w - fitted_w) // 2, (canvas_h - fitted_h) // 2),
    )

    return canvas


def _unique_path(output_dir: Path, stem: str) -> Path:
    path = output_dir / f"{stem}.png"
    suffix = 2

    while path.exists():
        path = output_dir / f"{stem}-{suffix}.png"
        suffix += 1

    return path


def _load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        return []

    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _append_manifest(entries: list[dict], manifest_path: Path) -> None:
    if not entries:
        return

    existing = _load_manifest(manifest_path)
    existing.extend(entries)

    manifest_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _entry_key(entry: dict) -> tuple[str, str, str, str] | None:
    try:
        return (
            entry["source_file"],
            entry["transformation"],
            entry["format"],
            entry["content_sha256"],
        )
    except KeyError:
        return None


async def export_images(
    rendered: dict[str, str],
    record: dict[str, str],
    output_dir: Path,
    manifest_path: Path,
) -> ExportResult:
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    generated_at = now.isoformat()

    known = {}
    for entry in _load_manifest(manifest_path):
        key = _entry_key(entry)
        if key is not None:
            known[key] = entry

    candidates = []
    skipped = []

    for label, html in rendered.items():
        for format_name, (width, height) in CANVAS_SIZES.items():
            content_hash = hashlib.sha256(
                f"{html}|{width}x{height}".encode()
            ).hexdigest()

            key = (
                record["source_file"],
                label,
                format_name,
                content_hash,
            )

            if key in known:
                skipped.append(
                    {
                        "transformation": label,
                        "format": format_name,
                        "content_sha256": content_hash,
                        "existing_output_file": known[key]["output_file"],
                    }
                )
                continue

            candidates.append(
                (
                    label,
                    html,
                    format_name,
                    width,
                    height,
                    content_hash,
                    key,
                )
            )

    created = []

    if candidates:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()

            for (
                label,
                html,
                format_name,
                width,
                height,
                content_hash,
                key,
            ) in candidates:
                source_image = await _capture_page(browser, html)
                final_image = _fit_to_canvas(
                    source_image,
                    (width, height),
                )

                stem = f"email-{label}-{format_name}-{stamp}-{content_hash[:8]}"
                path = _unique_path(output_dir, stem)
                final_image.save(path, format="PNG", optimize=True)

                entry = {
                    "generated_at": generated_at,
                    "source_file": record["source_file"],
                    "subject": record["subject"],
                    "date": record["date"],
                    "from": record["from"],
                    "to": record["to"],
                    "transformation": label,
                    "format": format_name,
                    "canvas": {"width": width, "height": height},
                    "output_file": path.name,
                    "content_sha256": content_hash,
                    "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }

                created.append(entry)
                known[key] = entry

            await browser.close()

    _append_manifest(created, manifest_path)

    return ExportResult(created=created, skipped=skipped)
