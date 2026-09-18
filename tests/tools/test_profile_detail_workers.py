import pytest

import tools.profile_detail_workers as profiler


class Category:
    def __init__(self, url):
        self.url = url


def test_positive_int_uses_default(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_WORKERS", raising=False)

    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 32


def test_positive_int_reads_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "28")

    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 28


def test_positive_int_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "0")

    with pytest.raises(ValueError, match="mayor que cero"):
        profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32)


def test_worker_values_default_to_controlled_pair(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_WORKERS", raising=False)

    assert profiler._worker_values() == (24, 28)


def test_worker_values_accepts_explicit_pair(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "16,32")

    assert profiler._worker_values() == (16, 32)


def test_select_category_uses_slug(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_CATEGORY", raising=False)

    categories = [
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/otro/"
        ),
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/"
            "papeles-fotograficos/"
        ),
    ]

    selected = profiler._select_category(categories)

    assert selected.url.endswith("/papeles-fotograficos/")


def test_select_category_accepts_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_CATEGORY", "otro")

    categories = [
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/otro/"
        ),
    ]

    assert profiler._select_category(categories) is categories[0]
