# FCM Architecture Checkpoint

Fecha: 2026-09-14  
Branch: `feature/scraping-performance-recovery`

## QUALITY

- [ ] Full suite post-product-code cleanup: blocked by one stale regression test that still imported the removed facade *(fixed in `9578d92`; local validation pending)*
- [x] Product-code targeted tests: `3 passed` before removal of the remaining stale consumer
- [x] Architecture-boundary tests: `23 passed`
- [x] Ruff: clean on current branch
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Targeted page-coverage compatibility tests: removed with retired facade

## RUNTIME CONSOLIDATION

- [x] Pagination monkey patch retired
- [x] JSF concurrency monkey patch retired
- [x] Page metrics monkey patch retired
- [x] Price recovery monkey patch retired
- [x] Page coverage recovery monkey patch retired; compatibility facade removed after consumer audit
- [x] Price recovery preserved natively in `ProductCollectionScraper`
- [x] Page metrics audit preserved natively
- [x] Canonical pagination engine active
- [x] FULL/prune safety preserved natively in canonical sync/coverage policy
- [x] Bootstrap/reconciliation preserved
- [x] `ScrapingConfig` unified
- [x] Workers configurable: category `16`, HTTP `28`, detail `32`
- [x] Product-code extraction and authoritative detail-code backfill preserved natively

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
- [x] Retired `single_page_fastpath_patch.py` facade removed
- [x] Retired `scraping_compat.py` facade removed
- [x] Obsolete archived `scraping_compat.py` implementation removed
- [x] `category_pagination_patch.py` removed after test consumers migrated to canonical engine
- [x] `jsf_concurrency_patch.py` removed after consumer test migrated to native `CategoryScraper`
- [x] `page_metrics_patch.py` removed after audit consumer migrated to native metrics storage/audit
- [x] `product_code_patch.py` removed after SKU extraction and authoritative detail-code backfill were verified as native
- [x] Remaining product-code regression test consumer migrated to native `ProductExtractor`
- [ ] Compatibility scraping factories: audit direct consumers before deciding whether to remove wrappers

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

### Completed

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
- [x] Revalidate the complete local suite after page-coverage cleanup
- [x] Migrate pagination and JSF-concurrency compatibility test consumers to canonical/native code
- [x] Revalidate the complete local suite after pagination and JSF-concurrency cleanup
- [x] Migrate page-metrics and product-code compatibility tests to native implementation
- [x] Remove `product_code_patch.py`
- [x] Remove remaining `product_code_patch` imports/references from runtime tests
- [x] Preserve native SKU extraction and authoritative detail-code backfill

### Pending validation

- [ ] Re-run `tests/scraping/test_scraping_coverage_regressions.py` after native migration
- [ ] Re-run complete local pytest suite
- [ ] Reconfirm Ruff and Pyright after final test-consumer migration
- [ ] Re-run a real FULL because product-code cleanup touches a scraping-related regression surface

### Next cleanup

- [ ] Audit compatibility scraping factories (`factories/scraping_factory.py`, `scrapers/factories/scraping_factory.py`) and remove only when no supported external imports/tests remain
- [ ] Optimize performance only while preserving `24 / 534 / 530 / 4`
