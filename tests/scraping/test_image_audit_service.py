from pathlib import Path

from services.scraping.image_audit_service import ImageAuditService


def test_image_audit_detects_byte_identical_duplicates(tmp_path):
    root = Path(tmp_path) / "products"
    root.mkdir()
    (root / "P001.webp").write_bytes(b"same")
    (root / "legacy-P001.webp").write_bytes(b"same")
    (root / "P002.webp").write_bytes(b"different")

    report = ImageAuditService(root).audit()

    assert report["files"] == 3
    assert report["unique_hashes"] == 2
    assert report["duplicate_groups"] == 1
    assert report["duplicate_files"] == 1


def test_image_audit_cleanup_only_removes_duplicates(tmp_path):
    root = Path(tmp_path) / "products"
    root.mkdir()
    (root / "P001.webp").write_bytes(b"same")
    (root / "legacy-P001.webp").write_bytes(b"same")
    (root / "P002.webp").write_bytes(b"different")

    report = ImageAuditService(root).remove_duplicates()

    assert report["duplicate_files"] == 0
    assert len(report["removed"]) == 1
    assert (root / "P001.webp").exists()
    assert (root / "P002.webp").exists()
