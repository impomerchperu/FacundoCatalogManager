from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import wrap

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageOps

from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader

PRODUCT_CODE = "FB-4047"
PRODUCT_URL = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"
CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/categoria-producto/"
    "articulos-de-antiestres/"
)
CATEGORY_NAME = "Artículos Antiestrés"
SUSPECT_IMAGE_URL = (
    "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
    "MEZCLADOR-CAMION-copia.webp"
)


def _collect_detail_url_from_category(
    browser: Browser,
    report: dict[str, object],
) -> tuple[str, ProductCollectionScraper | None]:
    """Prime the same HTTP session through the project's normal category pipeline."""
    collector: ProductCollectionScraper | None = None
    report["category_url"] = CATEGORY_URL
    report["category_page_status"] = "not_started"
    report["category_products_found"] = 0
    report["category_target_found"] = False
    report["category_match_method"] = ""
    warnings = report["warnings"]
    assert isinstance(warnings, list)

    try:
        category_scraper = ResilientCategoryScraper(browser=browser)
        collector = ProductCollectionScraper(
            category_scraper,
            ProductCardExtractor(),
            CategoryProductExtractor(),
            ProductExtractor(),
            max_workers=1,
            category_page_workers=1,
        )
        collected = collector.collect_category(CATEGORY_URL)
        report["category_page_status"] = "success"
        report["category_products_found"] = len(collected)

        for card, page_url, product in collected:
            detail_url = collector._card_detail_url(card, page_url, product)
            code = str(getattr(product, "code", "") or "").strip().upper()
            if code == PRODUCT_CODE:
                report["category_target_found"] = True
                report["category_match_method"] = "product_code"
                return detail_url or PRODUCT_URL, collector

        # A product card may omit its SKU. The canonical product path is a
        # narrower fallback locator, but the detail page must still validate
        # its SKU and name before its images are trusted.
        for card, page_url, product in collected:
            detail_url = collector._card_detail_url(card, page_url, product)
            if detail_url.rstrip("/").casefold() == PRODUCT_URL.rstrip("/").casefold():
                report["category_target_found"] = True
                report["category_match_method"] = "canonical_product_url"
                return detail_url, collector

    except Exception as error:  # noqa: BLE001
        report["category_page_status"] = "failed"
        warnings.append(
            {
                "stage": "category_scraping",
                "error": f"{type(error).__name__}: {error}",
            }
        )

    return PRODUCT_URL, collector


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



def _identity_product_name(soup, extractor_name: str) -> tuple[str, str]:
    """Prefer a product title over an unrelated distributor-modal heading."""
    selectors = (
        ".single-product .product_title",
        ".product .product_title",
        ".product_title",
        ".single-product .summary h1",
        ".product .summary h1",
        ".summary h1",
        ".single-product .summary h2.brxe-heading",
        ".product .summary h2.brxe-heading",
        ".summary h2.brxe-heading",
        ".single-product .summary h3.brxe-heading",
        ".product .summary h3.brxe-heading",
        ".summary h3.brxe-heading",
        ".single-product .product h1",
        ".single-product .product h2.brxe-heading",
        ".single-product .product h3.brxe-heading",
        ".product h1",
        ".product h2.brxe-heading",
        ".product h3.brxe-heading",
        "main h1",
        "h1",
        "h2.brxe-heading",
        "h3.brxe-heading",
    )
    observed: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for selector in selectors:
        for element in soup.select(selector):
            name = element.get_text(" ", strip=True)
            item = (name, selector)
            if name and item not in seen:
                observed.append(item)
                seen.add(item)

    # SEO metadata may retain the product title even when a modal is the first heading.
    for selector, attribute in (
        ('meta[property="og:title"]', "content"),
        ('meta[name="twitter:title"]', "content"),
    ):
        element = soup.select_one(selector)
        value = str(element.get(attribute, "") or "").strip() if element else ""
        item = (value, selector)
        if value and item not in seen:
            observed.append(item)
            seen.add(item)

    # This audit targets FB-4047, so prefer the title that identifies its product.
    matching = next(
        (item for item in observed if "foco" in item[0].casefold()),
        None,
    )
    if matching is not None:
        return matching
    if observed:
        return observed[0]
    return str(extractor_name or "").strip(), "ProductExtractor fallback"


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


def audit(output_dir: Path) -> tuple[dict[str, object], int]:  # noqa: PLR0912
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "product_code_requested": PRODUCT_CODE,
        "product_url": PRODUCT_URL,
        "validation_method": (
            "Project ProductCollectionScraper category-to-detail route on one "
            "Browser session, ProductExtractor, ImageDownloader, and decoded "
            "raster verification. No persistent cache or database sync."
        ),
        "warnings": [],
        "page_fetch": "not_started",
        "product_code_extracted": "",
        "product_name_extracted": "",
        "product_name_extractor_value": "",
        "product_name_identity_source": "",
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
    collector: ProductCollectionScraper | None = None

    try:
        detail_url, collector = _collect_detail_url_from_category(browser, report)
        report["product_url"] = detail_url
        html = browser.get(detail_url, force_revalidate=True)
        report["page_fetch"] = "success"
        if not html or not str(html).strip():
            raise RuntimeError("La página del producto devolvió HTML vacío.")  # noqa: TRY301

        soup = BeautifulSoup(html, "lxml")
        extracted = ProductExtractor().extract(
            soup,
            url=detail_url,
            category=CATEGORY_NAME,
        )
        extracted_code = str(getattr(extracted, "code", "") or "").strip().upper()
        extracted_name = str(getattr(extracted, "name", "") or "").strip()
        identity_name, identity_name_source = _identity_product_name(
            soup,
            extracted_name,
        )
        report["product_code_extracted"] = extracted_code
        report["product_name_extracted"] = identity_name
        report["product_name_extractor_value"] = extracted_name
        report["product_name_identity_source"] = identity_name_source

        if extracted_code != PRODUCT_CODE:
            raise RuntimeError(  # noqa: TRY301
                f"La página solicitada devolvió el código {extracted_code!r}, "
                f"no {PRODUCT_CODE!r}."
            )

        page_identity_valid = "foco" in identity_name.casefold()
        report["page_identity_valid"] = page_identity_valid
        if page_identity_valid:
            candidates = _candidate_urls(
                list(getattr(extracted, "image_candidates", []) or [])
            )
            if not candidates:
                errors.append(
                    {
                        "stage": "gallery_extraction",
                        "error": (
                            "La ficha fue identificada por código y nombre, pero "
                            "ProductExtractor no encontró imágenes no genéricas "
                            "dentro del contenedor oficial de galería."
                        ),
                    }
                )
        else:
            # A gateway/login template can contain the requested SKU in metadata
            # while exposing no authentic product name or gallery. Do not treat
            # any images from that response as authoritative product candidates.
            candidates = []
            report["page_fetch"] = "unexpected_template"
            errors.append(
                {
                    "stage": "page_identity",
                    "error": (
                        "La respuesta contiene el código esperado, pero el título "
                        f"identificado es {identity_name!r} (fuente: "
                        f"{identity_name_source}); no se considera una ficha válida."
                    ),
                }
            )

        report["gallery_candidate_count"] = len(candidates)
        report["gallery_candidates"] = candidates

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
        contact_sheet_records = list(image_records)
        diagnostic_record: dict[str, object] | None = None
        if not page_identity_valid or not candidates:
            # This download is only to inspect the bytes of the previously
            # flagged URL. It is explicitly not evidence that the current page
            # includes it in the product gallery.
            diagnostic_dir = images_dir / "diagnostic-only"
            diagnostic_record = {
                "position": "diagnostic-only",
                "url": SUSPECT_IMAGE_URL,
                "source": "historical-suspect-url; not verified as a current gallery member",
                "status": "download_failed",
                "evidence_type": "diagnostic_only_not_gallery_membership",
            }
            try:
                stored_path = downloader.download_gallery(
                    PRODUCT_CODE,
                    SUSPECT_IMAGE_URL,
                    1,
                    diagnostic_dir,
                )
                local_path = Path(stored_path)
                if not local_path.is_absolute():
                    local_path = Path.cwd() / local_path
                verified = downloader.verify_image_file(local_path)
                with Image.open(local_path) as source:
                    source.verify()
                with Image.open(local_path) as source:
                    width, height = source.size
                diagnostic_record.update(
                    {
                        "status": "downloaded",
                        "filename": (
                            "DIAGNOSTIC ONLY — NOT PROVEN TO BE A GALLERY IMAGE"
                        ),
                        "actual_filename": local_path.name,
                        "local_path": str(local_path),
                        "format": verified["image_extension"].lstrip(".").upper(),
                        "width": width,
                        "height": height,
                        "sha256": verified["image_hash"],
                        "size_bytes": local_path.stat().st_size,
                        "extension_matches_content": True,
                    }
                )
                contact_sheet_records.append(diagnostic_record)
            except Exception as error:  # noqa: BLE001
                diagnostic_record["error"] = f"{type(error).__name__}: {error}"
                errors.append(
                    {
                        "stage": "diagnostic_asset_download",
                        "url": SUSPECT_IMAGE_URL,
                        "error": diagnostic_record["error"],
                    }
                )
            report["diagnostic_asset_result"] = {
                key: value
                for key, value in diagnostic_record.items()
                if key != "local_path"
            }

        sheet_path = output_dir / "FB-4047_live_gallery_contact_sheet.png"
        if _write_contact_sheet(contact_sheet_records, sheet_path):
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
                        f"de {len(candidates)} imágenes candidatas de la ficha."
                    ),
                }
            )
        exit_code = (
            0
            if page_identity_valid and candidates and downloaded_count == len(candidates)
            else 1
        )
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
        if collector is not None:
            collector.close()
        else:
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
                "product_name_extractor_value": report["product_name_extractor_value"],
                "product_name_identity_source": report["product_name_identity_source"],
                "gallery_candidate_count": report["gallery_candidate_count"],
                "downloaded_and_verified_count": report.get(
                    "downloaded_and_verified_count", 0
                ),
                "contact_sheet": report["contact_sheet"],
                "category_page_status": report["category_page_status"],
                "category_products_found": report["category_products_found"],
                "category_target_found": report["category_target_found"],
                "warnings": report["warnings"],
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
