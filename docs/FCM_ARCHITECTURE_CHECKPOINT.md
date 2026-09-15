# FCM Architecture Checkpoint

Fecha: 2026-09-16  
Branch: `feature/scraping-performance-recovery`

## QUALITY

- [x] Targeted scraping coverage regressions: `8 passed`
- [x] Full suite: `366 passed, 1 skipped, 7 deselected`
- [x] Architecture-boundary tests: `23 passed`
- [x] Ruff: clean (`All checks passed!`)
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Product-code facade removal validated after remaining test consumer migration
- [x] Real FULL re-run after product-code cleanup: `24 / 534 / 530 / 4`
- [x] Scraping session/history transaction and application-state tests: `8 passed`
- [x] HTTP/detail timing audit completed from recent FULL samples

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
- [x] `page_metrics_patch.py` removed after audit consumer migrated to native metrics/audit
- [x] `product_code_patch.py` removed after SKU extraction and authoritative detail-code backfill were verified as native
- [x] Remaining product-code regression test consumer migrated to native `ProductExtractor`

### Compatibility scraping factories

- [x] `factories/scraping_factory.py` audited
- [x] `scrapers/factories/scraping_factory.py` audited
- [x] Production controller confirmed to import the canonical `services.scraping.scraping_factory.ScrapingFactory`
- [x] Compatibility factories confirmed to delegate to the canonical factory rather than implement a second scraping pipeline
- [x] No in-repository production consumer of the compatibility factories identified
- [ ] Do not remove compatibility factories yet: external import compatibility remains an unsupported-but-possible contract

## AUTHORITATIVE FULL REFERENCE

Reference: **latest applied FULL ID 180**

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

### Latest controller FULL — VALIDATED

- `history_id=180`
- `status=SUCCESS`
- `categories_processed=24`
- `expected_category_occurrences=534`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `duplicate_occurrences=4`
- `errors=0`
- `applied_at` populated
- execution time: `121.17s`
- recent valid timing sample: `118.517s` end-to-end
- controller progress callback completed at `48/48`

### History

- `history_id=180` is the latest successful applied execution.
- `history_id=179` remains preserved as an older successful execution with the same coverage result.
- `history_id=178` remains preserved as `ERROR` with `errors=3` and no `applied_at`.

Previous history was therefore preserved rather than deleted or overwritten.

### Catalog after latest FULL

- `products=530`
- `product_categories=534`
- latest FULL classified result: `created=0`, `updated=0`, `unchanged=530`, `deleted=0`

The latest controller FULL reproduced the authoritative `24 / 534 / 530 / 4` result and persisted it as `history_id=180` with no errors.

## HTTP / DETAIL AUDIT

Recent FULL timing samples show the network layer, not SQLite/catalog persistence, is the dominant runtime area.

### Detail cache

- Recent complete samples: `detail_cache requests=288–289`
- `cache_hits=0` in the recent samples
- `cache_size=288–289`
- `skipped=215–245`
- Interpretation: the enrichment phase is performing real detail HTTP requests for the consolidated product set; the detail cache is not reducing these requests within a single FULL sample.

### HTTP metrics

Observed recent samples:

- `requests=356–380`
- category requests: `32–51`
- detail requests: `288–289`
- other requests: `34–40`
- retries: `9–43`
- errors: `6–32`
- terminal errors: `0–4`
- observed `max_concurrency`: `24`, `28`, and one historical sample `32`
- per-request `max_seconds`: approximately `10.4–12.0s`

The `total_seconds` field is an aggregate of request timings and must not be interpreted as wall-clock execution time. Wall-clock FULL timing remains approximately `118–121s` in the validated recent runs.

The successful FULL result demonstrates that transient HTTP errors/retries can coexist with a complete final dataset when the final coverage is `24 / 534 / 530 / 4` and no invalidating errors remain.

### Performance conclusion

- [x] SQLite/catalog persistence is not the observed bottleneck: `catalog_sync` remains sub-second in the timing samples audited previously.
- [x] Detail enrichment is a major network cost because roughly `288–289` detail requests are made per complete FULL sample.
- [x] Category listing/recovery is also a significant network cost and shows variable retries/errors.
- [x] Effective HTTP concurrency is reaching the configured `28` in the current native path in the relevant samples.
- [x] No runtime performance change was made from this audit.
- [ ] Any performance optimization must be isolated, benchmarked, and validated against the authoritative `24 / 534 / 530 / 4` result.

## PROGRESS CONTRACT AUDIT

- [x] Audited `ScrapingRunner.run()` progress mapping
- [x] Confirmed FULL pipeline total is `2 × categories = 48`
- [x] Confirmed category collection currently emits `1..24`
- [x] Confirmed enrichment currently emits no intermediate `25..47` callbacks
- [x] Confirmed runner emits terminal `48/48` after `sync_categories()` returns
- [x] Confirmed this is a progress-reporting semantics issue only; the validated FULL result is unaffected
- [ ] Change progress callbacks only after adding targeted contract tests; no runtime behavior change has been made yet

## TRANSACTION SCOPE AUDIT

- [x] Executed targeted scraping-session transaction/history/application-state tests
- [x] Result: `8 passed`
- [x] Verified rollback/error-history/application-state behavior remains green under current transaction boundaries
- [x] No transaction-boundary runtime change made from this audit
- [x] Current timing evidence does not justify treating SQLite transaction scope as the primary performance bottleneck
- [ ] Consider transaction-scope optimization only after a separate benchmark confirms measurable SQLite contention/latency benefit

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
- [x] Validate targeted coverage regressions after product-code cleanup
- [x] Validate complete local suite after product-code cleanup
- [x] Reconfirm Ruff and Pyright after final test-consumer migration
- [x] Audit compatibility scraping factories and confirm canonical runtime uses the service-level factory
- [x] Re-run a real FULL after product-code cleanup
- [x] Verify latest controller FULL persists `history_id=180` as SUCCESS and applied
- [x] Verify latest catalog remains `530 products / 534 product_categories`
- [x] Audit current progress callback contract without changing scraping behavior
- [x] Execute targeted transaction/history/application-state audit: `8 passed`
- [x] Audit recent HTTP/detail request metrics without changing runtime behavior
- [x] Confirm effective HTTP concurrency reaches the configured worker level in recent samples
- [x] Confirm detail cache behavior is dominated by cache misses in complete FULL samples

### Next cleanup

- [ ] Keep compatibility scraping factories as thin external-compatibility wrappers unless a future audit proves they can be removed safely
- [ ] Add targeted progress-contract tests, then decide whether to emit enrichment progress `25..47` before changing the callback behavior
- [ ] Isolate the next performance experiment to network/category-detail behavior; do not alter FULL safety or persistence boundaries
- [ ] Benchmark/audit transaction scope only if a concrete SQLite contention or latency issue is observed
- [ ] Optimize performance only while preserving `24 / 534 / 530 / 4`
