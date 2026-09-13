from scrapers.collectors import missing_code_recovery_patch as recovery_patch


def test_full_sync_prune_guard_recovers_before_delegating(monkeypatch):
    calls = []

    def fake_recover(service, products):
        calls.append(("recover", service, products))
        return 1

    def fake_guard(
        service,
        products,
        category_count,
        *,
        expected_category_occurrences=0,
        expected_products=None,
    ):
        calls.append(
            (
                "guard",
                service,
                products,
                category_count,
                expected_category_occurrences,
                expected_products,
            )
        )
        return True, "complete"

    monkeypatch.setattr(recovery_patch, "_recover_missing_codes", fake_recover)
    monkeypatch.setattr(recovery_patch, "_ORIGINAL_FULL_SYNC_PRUNE_GUARD", fake_guard)

    service = object()
    products = [object()]

    result = recovery_patch._full_sync_prune_guard(
        service,
        products,
        24,
        expected_category_occurrences=534,
        expected_products=530,
    )

    assert result == (True, "complete")
    assert calls == [
        ("recover", service, products),
        ("guard", service, products, 24, 534, 530),
    ]
