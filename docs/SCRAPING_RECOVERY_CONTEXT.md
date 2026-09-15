# Scraping recovery context

- [x] P5 — remove duplicated pagination policy from `CategoryScraper` in favor of the canonical pagination engine
- [x] P6 — finish `ScrapingConfig` unification and worker propagation
- [x] P7 — compatibility/dead-code audit substantially completed; compatibility facades retained only where current tests/consumers require them
- [x] P8 — legacy DB/model audit completed; `scraped_products` and `sync_records` retained intentionally because recovery/reconciliation still consumes them
- [x] P9 — real FULL validation across all 24 categories completed

### REMAINING ARCHITECTURE AUDIT

No production dependency remains for the retired recovery facades removed during the scraping cleanup. Canonical pagination and coverage recovery remain active in `category_pagination_engine.py` and the current `CategoryScraper` flow.

The obsolete `missing_code_recovery_patch.py` facade and its facade-only test have also been removed. Missing-code recovery remains natively implemented in `CategoryProductSyncService` and is covered by the current contract test.

## Authoritative real FULL checkpoint

The authoritative real-site reference is the latest validated successful FULL run, **scraping_run=23 / history_id=179**.

- `scraping_run=23`
- `history_id=179`
- `status=SUCCESS`
- `mode=full`
- `categories_requested=24`
- `expected_category_occurrences=534`
- `actual_category_occurrences=534`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `duplicate_occurrences=4`
- `coverage_complete=true`
- `coverage_gap=0`
- `error_count=0`
- `applied_at` populated

The preceding `history_id=178` was an unsuccessful run with 3 errors and was not applied. Future FULL validation must be governed by the latest successful complete run, not by a manually chosen historical coverage floor such as 529/525.

## Latest repository validation

After removing obsolete facade-only tests, the branch validated cleanly with:

- `366 passed, 1 skipped, 7 deselected`
- Ruff: clean
- Pyright: `0 errors, 0 warnings, 0 informations`
