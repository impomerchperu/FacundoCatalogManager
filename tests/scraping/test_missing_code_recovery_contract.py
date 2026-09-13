from types import SimpleNamespace

from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)


def test_full_sync_prune_guard_recovers_before_safety_decisions(monkeypatch):
    calls = []

    service = CategoryProductSyncService(object(), object())
    products = [SimpleNamespace(code="RECOVERED-001")]

    def fake_recover(items):
        calls.append(("recover", items))
        return 1

    def fake_terminal_reason():
        calls.append(("terminal",))

    monkeypatch.setattr(service, "_recover_missing_codes", fake_recover)
    monkeypatch.setattr(service, "_terminal_http_error_reason", fake_terminal_reason)
    service.last_sync_result.category_summary = [
        {
            "category": "Categoria",
            "expected": 1,
            "products": 1,
            "unique_products": 1,
        }
    ]

    result = service._full_sync_prune_guard(
        products,
        1,
        expected_category_occurrences=1,
        expected_products=1,
    )

    assert result == (True, "complete")
    assert calls == [("recover", products), ("terminal",)]
