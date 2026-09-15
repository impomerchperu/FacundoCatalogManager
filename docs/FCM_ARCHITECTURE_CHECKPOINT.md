# FCM Architecture Checkpoint

Fecha: 2026-09-14  
Branch: `feature/scraping-performance-recovery`

## QUALITY

- [x] Full suite: `368 passed, 1 skipped, 7 deselected` *(validated after page-coverage facade removal)*
- [x] Ruff: clean
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Targeted page-coverage compatibility tests: removed with retired facade

## RUNTIME CONSOLIDATION

- [x] Pagination monkey patch retired
- [x] JSF concurrency monkey patch retired
- [x] Page metrics monkey patch retired
- [x] Price recovery monkey patch retired
- [x] Page coverage recovery monkey patch retired; compatibility facade removed after consumer audit
- [x] Price recovery preserved natively in `ProductCollectionScraper`
- [x] Page metrics audit preserved
- [x] Canonical pagination engine active
- [x] FULL/prune safety preserved natively in canonical sync/coverage policy
- [x] Bootstrap/reconciliation preserved
- [x] `ScrapingConfig` unified
- [x] Workers configurable: category `16`, HTTP `28`, detail `32`

## ARCHITECTURE CLEANUP

- [x] P4b — price recovery consolidated
- [x] P5 — duplicated pagination policy removed from `CategoryScraper`
- [x] P6 — `ScrapingConfig` worker propagation completed
- [x] P7 — compatibility/dead-code audit substantially completed
- [x] P8 — legacy DB/model audit completed; recovery tables retained intentionally
- [x] P9 — real FULL validation completed
- [x] `CatalogScraper` production usage audited; no canonical runtime dependency found
- [x] `scrapers/collectors/catalog_scraper.py` removed after usage audit
- [x] `scrapers/collectors/category_page_recovery.py` removed after usage audit
- [x] CatalogScraper-only legacy tests removed
- [x] Unused `jsf_request_recovery_patch.py` removed
- [x] Obsolete `test_jsf_request_recovery.py` removed
- [x] Unused `price_detail_recovery_patch.py` removed
- [x] Remaining compatibility facades audited for known consumers
- [x] Unused `full_sync_safety_patch.py` removed; canonical FULL/prune safety tests remain active
- [x] `page_coverage_recovery_patch.py` audited: production usage absent; facade and all facade-only tests removed
- [x] Stale page-coverage recovery documentation removed

## AUTHORITATIVE FULL REFERENCE

Reference: **FULL ID 177**

- 24 categories
- 534 product appearances
- 530 unique products
- 4 multi-category products
- 534 product-category relationships
- complete coverage
- 0 invalidating errors

Lower floors such as `529/525` are not valid substitutes for complete coverage.

## POST-CONSOLIDATION REAL FULL — VALIDATED

### Scraping run

- `scraping_run=23`
- `mode=full`
- `status=SUCCESS`
- `categories_requested=24`
- `expected_category_occurrences=534`
- `actual_category_occurrences=534`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `duplicate_occurrences=4`
- `coverage_complete=1`
- `coverage_gap=0`
- `error_count=0`

### History

- `history_id=179`
- `status=SUCCESS`
- `categories_processed=24`
- `products_expected=530`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `duplicate_occurrences=4`
- `errors=0`
- `applied_at` populated

The previous `history_id=178` remains as `ERROR` with `errors=3` and no `applied_at`. Previous history was therefore preserved rather than deleted or overwritten.

### Catalog after FULL

- `products=530`
- `product_categories=534`
- `created=0`
- `updated=0`
- `unchanged=530`
- `deleted=0`

The run reproduced the authoritative `24 / 534 / 530 / 4` result and produced no false catalog changes.

## CHECKLIST

- [x] Run real FULL across all 24 categories
- [x] Verify 24 categories
- [x] Verify 534 appearances
- [x] Verify 530 unique products
- [x] Verify 4 multi-category products
- [x] Verify 534 product-category relationships
- [x] Verify `coverage_complete=true`
- [x] Verify `coverage_gap=0`
- [x] Verify zero invalidating errors
- [x] Verify catalog/database reconciliation: 530 / 534
- [x] Verify previous history remains intact
- [x] Verify new history entry is SUCCESS and applied
- [x] Verify idempotent classification: 530 unchanged, 0 created, 0 updated, 0 deleted
- [x] Audit actual usage of `scrapers/collectors/catalog_scraper.py`
- [x] Confirm `CatalogScraper` and `category_page_recovery.py` are legacy-only
- [x] Remove only proven-dead legacy code and its tests
- [x] Audit `jsf_request_recovery_patch.py` and remove its obsolete test consumer
- [x] Audit `price_detail_recovery_patch.py` and remove it as unused
- [x] Audit `full_sync_safety_patch.py` and remove it as an unused facade
- [x] Audit `page_coverage_recovery_patch.py` and remove it with all facade-only tests
- [x] Revalidate the complete local suite after the page-coverage cleanup

## NEXT

- [ ] Audit remaining compatibility facades only where consumer evidence is still incomplete
- [ ] Keep compatibility facades only where tests or supported external imports require them
- [ ] Re-run a real FULL when a cleanup change can affect scraping/coverage/sync/persistence
- [ ] Optimize performance only while preserving `24 / 534 / 530 / 4`
