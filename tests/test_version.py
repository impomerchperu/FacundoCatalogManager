from pathlib import Path

import pytest

from core.version import load_app_version


def test_load_app_version_reads_semver_file(tmp_path: Path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4\n", encoding="utf-8")

    assert load_app_version(version_file) == "2.3.4"


@pytest.mark.parametrize("value", ["", "2.3", "v2.3.4", "2.3.4-beta"])
def test_load_app_version_rejects_invalid_version(tmp_path: Path, value: str):
    version_file = tmp_path / "VERSION"
    version_file.write_text(value, encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"MAJOR\.MINOR\.PATCH"):
        load_app_version(version_file)


def test_load_app_version_rejects_missing_file(tmp_path: Path):
    with pytest.raises(RuntimeError, match="No se pudo leer"):
        load_app_version(tmp_path / "VERSION")
