from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from textwrap import wrap

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageOps

from scrapers.browser import Browser
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader

PRODUCT_CODE = "FB-4047"
PRODUCT_URL = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"


def _candidate_urls(candidates: list[dict]) -> list[dict[str, object]]:
    """Keep ordered, non-generic URLs explicitly located inside product gallery."""
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if (
            not isinstance(candidate, dict)
            or not candidate.get("gallery_container")
            or candidate.get("generic")
        ):
            continue
        url = str(candidate.get("url") or "").strip()
        if not url or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        selected.append(
            {
                "url": url,
                "source": str(candidate.get("source") or ""),
                "sequence": int(candidate.get("sequence") or 0),
            }
        )
    return selected


def _wrap_url(url: str, width: int = 68) -> list[str]:
    return wrap(url, width=width, break_long_words=True, break_on_hyphens=False)


def _write_contact_sheet(
    image_records: list[dict[str, object]],
    output_path: Path,
) -> bool:
    """Create a review sheet from successfully downloaded and decoded images."""
    successful = [
        item
        for item in image_records
        if item.get("status") == "downloaded" and item.get("local_path")
    ]
    if not successful:
        return False

    card_width = 640
    card_height = 460
    columns = 2
    rows = (len(successful) + columns - 1) // columns
    sheet = Image.new("RGB", (card_width * columns, card_height * rows), "white")
    draw = ImageDraw.Draw(sheet)

    for index, record in enumerate(successful):
        x = (index % columns) * card_width
        y = (index // columns) * card_height
        local_path = Path(str(record["local_path"]))
        with Image.open(local_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            original_size = image.size
            image.thumbnail((card_width - 32, 300), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + 16, y + 12))

        label_y = y + 320
        draw.text(
            (x + 16, label_y),
            (
                f'{record["filename"]} | {original_size[0]}x{original_size[1]} '
                f'| SHA-256 {str(record.get("sha256") or "")[:16]}'
            ),
            fill="black",
        )
        label_y += 22
        for line in _wrap_url(str(record["url"]), width=86)[:4]:
            draw.text((x + 16, label_y), line, fill="black")
            label_y += 18

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    return True


def audit(output_dir: Path) -> tuple[dict[str, object], int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "product_code_requested": PRODUCT_CODE,
        "product_url": PRODUCT_URL,
        "validation_method": (
            "Project Browser (no persistent cache configured), ProductExtractor, "
            "ImageDownloader, and decoded raster verification."
        ),
        "page_fetch": "not_started",
        "product_code_extracted": "",
        "product_name_extracted": "",
        "gallery_candidate_count": 0,
        "gallery_candidates": [],
        "image_results": [],
        "contact_sheet": "",
        "http_metrics": {},
        "errors": [],
    }
    errors = report["errors"]
    assert isinstance(errors, list)
    browser = Browser(request_timeout=30, max_retries=2, http_workers=2)

    try:
        html = browser.get(PRODUCT_URL, force_revalidate=True)
        report["page_fetch"] = "success"
        if not html or not str(html).strip():
            raise RuntimeError("La página del producto devolvió HTML vacío.")

        soup = BeautifulSoup(html, "lxml")
        extracted = ProductExtractor().extract(
            soup,
            url=PRODUCT_URL,
            category="Artículos Antiestrés",
        )
        extracted_code = str(getattr(extracted, "code", "") or "").strip().upper()
        extracted_name = str(getattr(extracted, "name", "") or "").strip()
        report["product_code_extracted"] = extracted_code
        report["product_name_extracted"] = extracted_name

        if extracted_code != PRODUCT_CODE:
            raise RuntimeError(
                f"La página solicitada devolvió el código {extracted_code!r}, "
                f"no {PRODUCT_CODE!r}."
            )
        if "foco" not in extracted_name.casefold():
            raise RuntimeError(
                f"El nombre extraído no parece corresponder al foco: {extracted_name!r}."
            )

        candidates = _candidate_urls(
            list(getattr(extracted, "image_candidates", []) or [])
        )
        report["gallery_candidate_count"] = len(candidates)
        report["gallery_candidates"] = candidates
        if not candidates:
            raise RuntimeError(
                "ProductExtractor no encontró imágenes no genéricas dentro "
                "del contenedor oficial de galería."
            )

        downloader = ImageDownloader(
            output_dir=images_dir,
            request_timeout=30,
            max_retries=2,
        )
        image_records: list[dict[str, object]] = []
        for position, candidate in enumerate(candidates, start=1):
            url = str(candidate["url"])
            item: dict[str, object] = {
                "position": position,
                "url": url,
                "source": candidate["source"],
                "status": "download_failed",
            }
            try:
                stored_path = downloader.download_gallery(
                    PRODUCT_CODE,
                    url,
                    position,
                    images_dir,
                )
                local_path = Path(stored_path)
                if not local_path.is_absolute():
                    local_path = Path.cwd() / local_path
                verified = downloader.verify_image_file(local_path)
                with Image.open(local_path) as source:
                    source.verify()
                with Image.open(local_path) as source:
                    width, height = source.size

                item.update(
                    {
                        "status": "downloaded",
                        "filename": local_path.name,
                        "local_path": str(local_path),
                        "format": verified["image_extension"].lstrip(".").upper(),
                        "width": width,
                        "height": height,
                        "sha256": verified["image_hash"],
                        "size_bytes": local_path.stat().st_size,
                        "extension_matches_content": True,
                    }
                )
            except Exception as error:  # noqa: BLE001
                item["error"] = f"{type(error).__name__}: {error}"
                errors.append(
                    {
                        "stage": "image_download_or_validation",
                        "url": url,
                        "error": item["error"],
                    }
                )
            image_records.append(item)

        report["image_results"] = [
            {key: value for key, value in item.items() if key != "local_path"}
            for item in image_records
        ]
        sheet_path = output_dir / "FB-4047_live_gallery_contact_sheet.png"
        if _write_contact_sheet(image_records, sheet_path):
            report["contact_sheet"] = sheet_path.name
        downloaded_count = sum(
            item.get("status") == "downloaded" for item in image_records
        )
        report["downloaded_and_verified_count"] = downloaded_count
        report["http_metrics"] = browser.get_http_metrics()
        if downloaded_count != len(candidates):
            errors.append(
                {
                    "stage": "completeness",
                    "error": (
                        f"Solo se descargaron y verificaron {downloaded_count} "
                        f"de {len(candidates)} imágenes candidatas."
                    ),
                }
            )
        exit_code = 0 if downloaded_count == len(candidates) else 1
    except Exception as error:  # noqa: BLE001
        report["page_fetch"] = (
            "failed" if report["page_fetch"] == "not_started" else report["page_fetch"]
        )
        errors.append(
            {
                "stage": "page_fetch_or_extraction",
                "error": f"{type(error).__name__}: {error}",
            }
        )
        report["http_metrics"] = browser.get_http_metrics()
        exit_code = 1
    finally:
        browser.close()

    report_path = output_dir / "FB-4047_live_gallery_audit.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "report": report_path.name,
                "product_code_extracted": report["product_code_extracted"],
                "product_name_extracted": report["product_name_extracted"],
                "gallery_candidate_count": report["gallery_candidate_count"],
                "downloaded_and_verified_count": report.get(
                    "downloaded_and_verified_count", 0
                ),
                "contact_sheet": report["contact_sheet"],
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Auditoría live de solo lectura de la galería de FB-4047 con "
            "el scraping del proyecto."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    _report, exit_code = audit(args.output_dir)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
