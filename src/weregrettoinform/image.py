"""Export rendered HTML variants to Instagram-sized PNGs."""

from __future__ import annotations

import hashlib
import io
import json
import re
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

HTML_NAME_RE = re.compile(
    r"^email-(?P<label>[a-z]+)-(?P<stamp>\d{8}T\d{6})-"
    r"(?P<hash>[0-9a-f]{8})\.html$"
)
PNG_NAME_RE = re.compile(
    r"^email-(?P<label>[a-z]+)-(?P<format>post|story)-"
    r"(?P<stamp>\d{8}T\d{6})-(?P<hash>[0-9a-f]{8})\.png$"
)


@dataclass(frozen=True)
class ExportResult:
    created: list[dict]
    skipped: list[dict]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _find_html(output_dir: Path, label: str, html_hash8: str) -> Path | None:
    matches = sorted(output_dir.glob(f"email-{label}-*-{html_hash8}.html"))

    for path in matches:
        match = HTML_NAME_RE.match(path.name)
        if match and match.group("hash") == html_hash8:
            return path

    return None


def _find_png(
    output_dir: Path,
    label: str,
    format_name: str,
    html_hash8: str,
) -> Path | None:
    matches = sorted(output_dir.glob(f"email-{label}-{format_name}-*-{html_hash8}.png"))

    for path in matches:
        match = PNG_NAME_RE.match(path.name)
        if match and match.group("hash") == html_hash8:
            return path

    return None


def _stamp_from_png(path: Path) -> str:
    match = PNG_NAME_RE.match(path.name)
    if match is None:
        raise ValueError(f"Unrecognized PNG filename: {path.name}")
    return match.group("stamp")


def _ensure_html(
    output_dir: Path,
    label: str,
    stamp: str,
    html_hash8: str,
    html: str,
) -> Path:
    existing = _find_html(output_dir, label, html_hash8)
    if existing is not None:
        return existing

    path = output_dir / f"email-{label}-{stamp}-{html_hash8}.html"
    path.write_text(html, encoding="utf-8", newline="\n")

    return path


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


def _write_manifest(entries: list[dict], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
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


def _entry_stamp(entry: dict, fallback: str) -> str:
    stamp = entry.get("run_stamp")
    if isinstance(stamp, str):
        return stamp

    output_file = entry.get("output_file")
    if isinstance(output_file, str):
        match = PNG_NAME_RE.match(output_file)
        if match is not None:
            return match.group("stamp")

    return fallback


def _manifest_entry(
    record: dict[str, str],
    label: str,
    format_name: str,
    canvas: tuple[int, int],
    png_path: Path,
    html_path: Path,
    html_sha256: str,
    content_hash: str,
    stamp: str,
    generated_at: str,
) -> dict:
    width, height = canvas

    return {
        "generated_at": generated_at,
        "run_stamp": stamp,
        "source_file": record["source_file"],
        "subject": record["subject"],
        "date": record["date"],
        "from": record["from"],
        "to": record["to"],
        "transformation": label,
        "format": format_name,
        "canvas": {"width": width, "height": height},
        "html_file": html_path.name,
        "html_sha256": html_sha256,
        "content_sha256": content_hash,
        "output_file": png_path.name,
        "png_sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
    }


async def export_images(
    rendered: dict[str, str],
    record: dict[str, str],
    output_dir: Path,
    manifest_path: Path,
) -> ExportResult:
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    generated_at = now.isoformat()

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries = _load_manifest(manifest_path)

    known = {}
    for entry in manifest_entries:
        key = _entry_key(entry)
        if key is not None:
            known[key] = entry

    candidates = []
    created = []
    skipped = []
    new_entries = []
    replaced_keys = set()

    for label, html in rendered.items():
        html_sha256 = _sha256_text(html)
        html_hash8 = html_sha256[:8]

        for format_name, canvas in CANVAS_SIZES.items():
            width, height = canvas
            content_hash = _sha256_text(f"{html}|{width}x{height}")
            key = (
                record["source_file"],
                label,
                format_name,
                content_hash,
            )
            known_entry = known.get(key)

            if known_entry is not None:
                output_name = known_entry.get("output_file")
                html_name = known_entry.get("html_file")
                output_exists = (
                    isinstance(output_name, str)
                    and (output_dir / output_name).is_file()
                )

                if output_exists:
                    if (
                        isinstance(html_name, str)
                        and (output_dir / html_name).is_file()
                    ):
                        html_path = output_dir / html_name
                    else:
                        entry_stamp = _entry_stamp(known_entry, stamp)
                        html_path = _ensure_html(
                            output_dir,
                            label,
                            entry_stamp,
                            html_hash8,
                            html,
                        )

                    skipped.append(
                        {
                            "transformation": label,
                            "format": format_name,
                            "content_sha256": content_hash,
                            "existing_output_file": output_name,
                            "html_file": html_path.name,
                        }
                    )
                    continue

                replaced_keys.add(key)

            orphan = _find_png(output_dir, label, format_name, html_hash8)

            if orphan is not None:
                orphan_stamp = _stamp_from_png(orphan)
                html_path = _ensure_html(
                    output_dir,
                    label,
                    orphan_stamp,
                    html_hash8,
                    html,
                )
                adopted_at = datetime.fromtimestamp(
                    orphan.stat().st_mtime,
                    UTC,
                ).isoformat()
                entry = _manifest_entry(
                    record,
                    label,
                    format_name,
                    canvas,
                    orphan,
                    html_path,
                    html_sha256,
                    content_hash,
                    orphan_stamp,
                    adopted_at,
                )
                new_entries.append(entry)
                known[key] = entry
                skipped.append(
                    {
                        "transformation": label,
                        "format": format_name,
                        "content_sha256": content_hash,
                        "existing_output_file": orphan.name,
                        "html_file": html_path.name,
                    }
                )
                continue

            candidates.append(
                (
                    label,
                    html,
                    format_name,
                    canvas,
                    content_hash,
                    html_sha256,
                    html_hash8,
                    key,
                )
            )

    if candidates:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()

            for (
                label,
                html,
                format_name,
                canvas,
                content_hash,
                html_sha256,
                html_hash8,
                key,
            ) in candidates:
                source_image = await _capture_page(browser, html)
                final_image = _fit_to_canvas(source_image, canvas)

                stem = f"email-{label}-{format_name}-{stamp}-{html_hash8}"
                png_path = _unique_path(output_dir, stem)
                final_image.save(png_path, format="PNG", optimize=True)

                html_path = _ensure_html(
                    output_dir,
                    label,
                    stamp,
                    html_hash8,
                    html,
                )
                entry = _manifest_entry(
                    record,
                    label,
                    format_name,
                    canvas,
                    png_path,
                    html_path,
                    html_sha256,
                    content_hash,
                    stamp,
                    generated_at,
                )
                new_entries.append(entry)
                created.append(entry)
                known[key] = entry

            await browser.close()

    kept_entries = [
        entry for entry in manifest_entries if _entry_key(entry) not in replaced_keys
    ]
    _write_manifest(kept_entries + new_entries, manifest_path)

    return ExportResult(created=created, skipped=skipped)
