from pathlib import Path

from config.runtime_paths import (
    APP_NAME,
    DATA_DIR,
    PROJECT_ROOT,
    get_bundle_root,
    get_data_dir,
    resolve_data_path,
    to_data_relative_path,
)


def test_non_frozen_data_dir_is_project_root():
    assert get_data_dir(frozen=False) == PROJECT_ROOT


def test_frozen_data_dir_uses_local_app_data(tmp_path: Path):
    assert get_data_dir(
        frozen=True,
        local_app_data=tmp_path,
    ) == tmp_path / APP_NAME


def test_non_frozen_bundle_root_is_project_root():
    assert get_bundle_root(frozen=False) == PROJECT_ROOT


def test_frozen_bundle_root_uses_explicit_bundle_root(tmp_path: Path):
    assert get_bundle_root(
        frozen=True,
        bundle_root=tmp_path,
    ) == tmp_path


def test_frozen_bundle_root_uses_meipass(monkeypatch, tmp_path: Path):
    from config import runtime_paths

    monkeypatch.setattr(
        runtime_paths.sys,
        "_MEIPASS",
        str(tmp_path),
        raising=False,
    )

    assert runtime_paths.get_bundle_root(frozen=True) == tmp_path


def test_frozen_bundle_root_falls_back_to_project_root():
    assert get_bundle_root(frozen=True, bundle_root=None) == PROJECT_ROOT


def test_resolve_data_path_keeps_absolute_paths(tmp_path: Path):
    absolute = tmp_path / "catalog" / "image.webp"
    assert resolve_data_path(absolute) == absolute


def test_resolve_data_path_anchors_relative_paths_to_data_dir():
    assert resolve_data_path("data/images/products/A.webp") == (
        DATA_DIR / "data/images/products/A.webp"
    )


def test_to_data_relative_path_preserves_catalog_shape():
    assert to_data_relative_path(
        DATA_DIR / "data/images/products/A.webp"
    ) == "data/images/products/A.webp"


def test_to_data_relative_path_preserves_external_absolute_paths(
    tmp_path: Path,
):
    external = tmp_path / "external" / "image.webp"
    assert to_data_relative_path(external) == external.as_posix()
