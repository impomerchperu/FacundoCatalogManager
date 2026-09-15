- [x] P5 — remove duplicated pagination policy from `CategoryScraper` in favor of the canonical pagination engine
- [x] P6 — finish `ScrapingConfig` unification and worker propagation
- [x] P7 — compatibility/dead-code audit substantially completed; compatibility facades retained only where current tests/consumers require them
- [x] P8 — legacy DB/model audit completed; `scraped_products` and `sync_records` retained intentionally because recovery/reconciliation still consumes them
- [ ] P9 — real FULL validation across all 24 categories

### REMAINING ARCHITECTURE AUDIT

No production dependency remains for the retired page-coverage recovery facade. `scrapers/collectors/page_coverage_recovery_patch.py` and its facade-only tests have been removed after consumer audit. Canonical pagination and coverage recovery remain active in `category_pagination_engine.py` and the current `CategoryScraper` flow.

## Authoritative real FULL checkpoint

The authoritative real-site reference remains **FULL run ID 177** and must be used for future validation.

- `history_id=177`
- `categories_processed=24`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `expected_category_occurrences=534`
- `duplicate_occurrences=4`
- `coverage_complete=true`