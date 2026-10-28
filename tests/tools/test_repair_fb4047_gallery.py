from types import SimpleNamespace

from tests.scraping.image_test_utils import image_bytes
from tools.repair_fb4047_gallery import (
    _candidate_coverage,
    _gallery_urls,
    _unique_gallery_candidates,
)


def test_unique_gallery_candidates_keeps_order_and_excludes_non_gallery_and_generic():
    product = SimpleNamespace(
        image_candidates=[
            {"url": "https://site.test/main.webp", "gallery_container": True},
            {"url": "https://site.test/main.webp", "gallery_container": True},
            {
                "url": "https://site.test/logo.webp",
                "gallery_container": True,
                "generic": True,
            },
            {"url": "https://site.test/card.webp", "gallery": True},
            {"url": "https://site.test/second.webp", "gallery_container": True},
        ]
    )

    candidates = _unique_gallery_candidates(product)

    assert [item["url"] for item in candidates] == [
        "https://site.test/main.webp",
        "https://site.test/second.webp",
    ]


def test_candidate_coverage_reports_all_live_gallery_urls_as_stored():
    source_urls = [
        "https://site.test/main.webp",
        "https://site.test/second.webp",
        "https://site.test/third.webp",
    ]
    gallery = [{"url": url, "image_path": f"data/images/{index}.webp"}
               for index, url in enumerate(source_urls, start=1)]

    result = _candidate_coverage(source_urls, gallery)

    assert result == {
        "candidate_count": 3,
        "stored_gallery_count": 3,
        "missing_urls": [],
        "all_candidates_stored": True,
    }
    assert _gallery_urls(gallery) == source_urls


def test_candidate_coverage_does_not_accept_a_partial_gallery():
    source_urls = [
        "https://site.test/main.webp",
        "https://site.test/second.webp",
        "https://site.test/third.webp",
    ]
    gallery = [{"url": source_urls[0]}, {"url": source_urls[1]}]

    result = _candidate_coverage(source_urls, gallery)

    assert result["all_candidates_stored"] is False
    assert result["missing_urls"] == [source_urls[2]]


def test_verify_gallery_files_decodes_image_and_checks_saved_hash(tmp_path):
    from scrapers.images.image_downloader import ImageDownloader
    from tools.repair_fb4047_gallery import _verify_gallery_files

    image_path = tmp_path / "FB-4047-01.webp"
    image_path.write_bytes(image_bytes("WEBP", (21, 31, 41)))
    image_hash = ImageDownloader.hash_file(image_path)

    result = _verify_gallery_files([
        {
            "position": 1,
            "url": "https://site.test/main.webp",
            "image_path": str(image_path),
            "image_hash": image_hash,
        }
    ])

    assert len(result) == 1
    assert result[0]["hash_matches_record"] is True
    assert result[0]["sha256"] == image_hash


def test_verify_gallery_files_rejects_hash_mismatch(tmp_path):
    import pytest

    from tools.repair_fb4047_gallery import _verify_gallery_files

    image_path = tmp_path / "FB-4047-01.webp"
    image_path.write_bytes(image_bytes("WEBP", (22, 32, 42)))

    with pytest.raises(RuntimeError, match="SHA-256 no coincide"):
        _verify_gallery_files([
            {
                "position": 1,
                "url": "https://site.test/main.webp",
                "image_path": str(image_path),
                "image_hash": "0" * 64,
            }
        ])
