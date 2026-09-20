# FCM Architecture Checkpoint

Fecha del checkpoint actual: 2026-09-19  
Branch: `feature/scraping-performance-recovery`

## QUALITY

- [x] Targeted scraping coverage regressions validated
- [x] Suite no-real-site actual: `429 passed, 2 deselected`
- [x] Architecture-boundary tests validated
- [x] Ruff: clean (`All checks passed!`)
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Product-code migration/cleanup validated
- [x] Legacy destructive catalog cleanup disabled and covered
- [x] Legacy destructive image duplicate cleanup disabled and covered
- [x] Real FULL validated at `24 / 534 / 530 / 4`
- [x] Bootstrap/reconciliation tests: `15 passed`
- [x] HTTP/detail timing and retry telemetry audited
- [x] Per-category enrichment timing telemetry instrumented and tested
- [x] Progress-contract tests validated
- [x] Detail-cache concurrency tests validated

## RUNTIME CONSOLIDATION

- [x] Pagination compatibility patch retired
- [x] JSF concurrency compatibility patch retired
- [x] Page metrics compatibility patch retired
- [x] Price recovery compatibility patch retired
- [x] Page coverage compatibility facade retired after audit
- [x] Price recovery preserved natively in `ProductCollectionScraper`
- [x] Page metrics preserved natively
- [x] Canonical pagination engine active
- [x] FULL/prune safety preserved natively in canonical sync/coverage policy
- [x] Bootstrap/reconciliation preserved
- [x] `ScrapingConfig` unified
- [x] Production workers validated: category `8`, HTTP `28`, detail baseline benchmarked at `16`
- [x] Product-code extraction and authoritative detail-code backfill preserved natively
- [x] Retry/backoff metrics observable without changing retry semantics

## ARCHITECTURE CLEANUP

- [x] Price recovery consolidated
- [x] Duplicated pagination policy removed from `CategoryScraper`
- [x] `ScrapingConfig` worker propagation completed
- [x] Compatibility/dead-code audit substantially completed
- [x] Legacy DB/model audit completed; recovery tables retained intentionally
- [x] Production FULL validation completed
- [x] `CatalogScraper` production usage audited; no canonical runtime dependency found
- [x] Obsolete scraping facades and patch-only consumers removed after usage audits
- [x] Pagination, JSF-concurrency, page-metrics and product-code test consumers migrated to native APIs
- [x] Canonical service-level scraping factory confirmed in production usage
- [x] Compatibility scraping factories confirmed as thin delegates and retained only for possible external import compatibility

## AUTHORITATIVE FULL REFERENCE

The governing functional reference is the latest successful complete FULL execution. Lower historical floors such as `529/525` are not substitutes for complete coverage.

Validated invariants:

- 24 categories
- 534 product appearances
- 530 unique products
- 4 multi-category products
- 534 product-category relationships
- `coverage_complete=1`
- `coverage_gap=0`
- `error_count=0`

## CURRENT REAL DATABASE VALIDATION

The read-only validation of the local `database/catalog.db` confirmed:

- SQLite `PRAGMA integrity_check`: `ok`
- Latest FULL run: `id=34`
- Run status: `SUCCESS`
- Run metrics: `24 / 534 / 530 / 4`
- `coverage_gap=0`
- `error_count=0`
- Occurrences in latest run: `534`
- Distinct normalized product codes in latest run: `530`
- Categories represented in latest run: `24`
- Occurrences without a product link: `0`
- Product codes missing from `products`: `0`
- Products not represented by latest run: `0`
- Missing product-category relations: `0`
- Extra product-category relations: `0`
- Current catalog: `530` products / `534` product-category relations
- Preserved history: `156` records
- Preserved change details: `52,816` records
- `initialized=1`
- `history_recovery_applied=1`

The latest real history record is `history_id=191`, marked `SUCCESS` and applied, with `24` categories, `534` found occurrences, `530` unique products, `4` multi-category products, `0` errors, and classification `0 created / 0 updated / 530 unchanged / 0 deleted`.

## BOOTSTRAP VALIDATION

The bootstrap/reconciliation implementation is authoritative by actual run validity, not by a manually selected historical coverage floor.

Validation performed:

- Bootstrap/reconciliation suite: `15 passed`
- Modern FULL metrics are checked for exact consistency when those columns exist.
- A modern `SUCCESS` run with zero/inconsistent metrics is rejected.
- Legacy fixtures without the modern metric columns remain supported using occurrence-count validation.
- Bootstrap smoke on a copy of the real `catalog.db` rebuilt `530` products and `534` relations from the latest valid FULL run.
- The real database was not modified by the smoke test.

## REAL FULL AND E2E VALIDATION

A real FULL validation confirmed:

- 24/24 categories
- 534 occurrences
- 530 unique products
- 4 multi-category products
- 0 missing codes
- no category errors
- no page coverage errors
- complete coverage
- terminal HTTP errors: `0`

A production-style E2E validation also confirmed:

- 24 categories
- 534 occurrences
- 530 unique products
- 4 multi-category products
- DB products: `530`
- DB relations: `534`
- run occurrences: `534`
- successful history with `applied_at`
- configured workers `8 / 16 / 28`
- terminal HTTP errors: `0`
- HTTP retries: `0`
- total E2E wall time: `113.97s`
- SQLite database isolated to a temporary test database

## HTTP / DETAIL AUDIT

Recent complete FULL samples show that network work, especially category extraction and product-detail enrichment, dominates the observed runtime more than SQLite/catalog persistence.

Current production configuration:

- category workers: `8`
- detail workers: `16`
- HTTP workers: `28`
- JetSmartFilters HTTP concurrency: `8`
- request timeout: `20s`
- max retries: `3`

Detail-cache behavior is protected by both single-threaded reuse and concurrent coalescing tests. Complete FULL samples have shown approximately `289` detail requests and `cache_hits=0`; this means the mechanism is correct but does not materially reduce requests when the current consolidated product set has little repeated enrichment work.

HTTP request counts, retry counts, aggregate request durations and wall-clock time must be interpreted separately because concurrent requests overlap.

## ENRICHMENT TELEMETRY

Per-category enrichment now exposes diagnostic timing without changing scraping semantics:

- `requested`
- `skipped`
- `total_seconds`
- `submit_seconds`
- `wait_seconds`

`CategoryProductSyncService` records these values from `ProductCollectionScraper.get_enrichment_metrics(category_name)` after each category enrichment and emits them through the existing timing logger as `stage=category_enrichment_summary`.

The contract is covered by a focused unit test and the complete local suite remains green at `392 passed, 1 skipped, 9 deselected`.

This instrumentation is diagnostic only. It does not change coverage, product selection, persistence, prune behavior or retry semantics.

## PERFORMANCE STATUS

Performance remains secondary to correctness. The current production configuration is `8 / 16 / 28`. A real production-style E2E has now validated the complete scrape-to-SQLite-to-history path under this configuration with `24 / 534 / 530 / 4` and DB `530 / 534`.

No single wall-clock number is treated as a functional requirement because the live site and network are variable. Any runtime optimization must be isolated, benchmarked and followed by another authoritative FULL validation.

The enrichment instrumentation and the crossed 16/24 worker benchmark are complete. Further performance work is optional and should be isolated from the validated release baseline.

SQLite transaction-scope optimization is not currently a correctness blocker. A dedicated contention/latency benchmark is optional and should be triggered only by concrete evidence of SQLite contention.

## PROGRESS CONTRACT AUDIT

- [x] FULL pipeline total is `2 × categories = 48`
- [x] Category collection reports completion across `1..24`
- [x] Enrichment currently does not emit intermediate callbacks `25..47`
- [x] Runner emits terminal `48/48`
- [x] Current progress semantics are covered by tests
- [x] Confirmed progress semantics do not alter coverage or persistence

The current behavior is a UI-reporting choice, not a scraping correctness issue. More granular enrichment progress may be added later as a separate UX change.

## TRANSACTION SCOPE AUDIT

- [x] Atomicity of catalog/history state validated
- [x] Rollback/error-history/application-state behavior validated
- [x] Current transaction scope audited against observed timing
- [x] No evidence that transaction scope is the primary runtime bottleneck
- [x] No transaction-boundary runtime change made

A SQLite contention benchmark remains optional and non-blocking unless a concrete contention or latency issue appears.

## MASTER PLAN STATUS

### 1. Corrección funcional

- [x] FULL real de 24 categorías
- [x] `534 / 530 / 4` as authoritative reference
- [x] `coverage_complete=1`
- [x] `coverage_gap=0`
- [x] zero invalidating errors
- [x] FULL/prune safety
- [x] latest-valid-FULL precedence in bootstrap reconciliation

### 2. Recuperación y persistencia

- [x] Pagination/JSF/coverage/detail/code recovery consolidated
- [x] Incomplete FULL cannot trigger destructive prune
- [x] Failed newer FULL cannot replace a valid complete FULL
- [x] Historical records preserved
- [x] Latest real applied history validated as `191`
- [x] Catalog reconciled to `530 / 534`
- [x] Modern run-metric consistency guard validated
- [x] Bootstrap smoke validated on a copy of the real DB

### CURRENT ENGINEERING CHECKPOINT

Current head: `28becc60b230ec0f43285e999932f4d6b2feee8d` (`style(tests): normalize image audit imports`).

Local validation after synchronization:

- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`
- Focused checkpoint tests: `21 passed in 0.63s`
- Full no-real-site suite: `429 passed, 2 deselected in 6.40s`
- Git working tree: clean
- GitHub Actions Quality run `#1867`: success
- CI `live-catalog`: skipped as intended for this audit checkpoint

The audit also hardened two legacy maintenance tools so they cannot perform direct destructive deletion:

- `tools/clean_catalog.py` remains diagnostic-only; `apply=True` is rejected.
- `services/scraping/image_audit_service.py` remains diagnostic-only; physical duplicate removal is rejected.
- `tools/audit_images.py --clean` is now treated as obsolete and rejected.

No real scraping was executed in this checkpoint, so the protected authoritative FULL reference remains the previously validated `24 / 534 / 530 / 4` under production `8 / 16 / 28`.

### 3. Consolidación y limpieza

- [x] Single canonical implementation per responsibility
- [x] Dead legacy facades/patches removed after audit
- [x] Test consumers migrated to native APIs
- [x] Canonical production factory confirmed
- [x] Compatibility factories retained only as thin external-compatibility wrappers

### 4. Calidad

- [x] Suite no-real-site actual: `429 passed, 2 deselected`
- [x] Ruff clean
- [x] Pyright clean
- [x] Bootstrap/reconciliation: `15 passed`
- [x] Detail-cache concurrency coverage
- [x] Runner/progress contract coverage
- [x] Enrichment telemetry contract coverage
- [x] Real FULL validated
- [x] Production E2E validated

### 5. Progreso UI

- [x] Current `1..24`, then `48/48`, semantics documented and tested
- [x] Confirmed no effect on coverage/persistence
- [ ] Optional UX improvement: intermediate enrichment callbacks `25..47`

### 6. SQLite transactions

- [x] Atomicity validated
- [x] Rollback validated
- [x] Error-history/application-state validated
- [x] Scope audited against observed timing
- [ ] Optional contention/latency benchmark if evidence appears

### 7. Performance

- [x] Stage timings audited
- [x] HTTP/detail audited
- [x] SQLite not identified as primary bottleneck
- [x] Category/detail identified as major network cost
- [x] HTTP concurrency validated to configured `28`
- [x] Retry/backoff telemetry available
- [x] Category/HTTP workers `8 / 28` remain validated
- [x] Detail workers `16` selected after crossed live benchmark against `24`
- [x] Authoritative real-site scrape validated under production `8 / 16 / 28`
- [x] Per-category enrichment timing telemetry instrumented and tested
- [x] Benchmark: isolate detail worker behavior with crossed live runs
- [x] Final production E2E: revalidate coverage and persistence under `8 / 16 / 28`
- [ ] Re-run authoritative FULL after any runtime performance change

## RELEASE POSITION

The correction, recovery, persistence, reconciliation, coverage, quality and production E2E work for `feature/scraping-performance-recovery` is validated. Future changes should be treated as incremental improvements and must preserve the authoritative `24 / 534 / 530 / 4` result, complete coverage, DB `530 / 534`, applied history and the green automated suite.
