# FCM Architecture Checkpoint

Fecha: 2026-09-15  
Branch: `feature/scraping-performance-recovery`

## QUALITY

- [x] Targeted scraping coverage regressions: `8 passed`
- [x] Full suite: `370 passed, 1 skipped, 7 deselected`
- [x] Architecture-boundary tests: `23 passed`
- [x] Ruff: clean (`All checks passed!`)
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Product-code facade removal validated after remaining test consumer migration
- [x] Real FULL re-run after product-code cleanup: `24 / 534 / 530 / 4`
- [x] Scraping session/history transaction and application-state tests: `8 passed`
- [x] HTTP/detail timing audit completed from recent FULL samples
- [x] Progress-contract tests added and validated: `8 passed` across runner + progress contract
- [x] Browser retry/backoff telemetry added and validated: `2 passed`

## RUNTIME CONSOLIDATION

- [x] Pagination monkey patch retired
- [x] JSF concurrency monkey patch retired
- [x] Page metrics monkey patch retired
- [x] Price recovery monkey patch retired
- [x] Page coverage recovery monkey patch retired; compatibility facade removed after consumer audit
- [x] Price recovery preserved natively in `ProductCollectionScraper`
- [x] Page metrics preserved natively
- [x] Canonical pagination engine active
- [x] FULL/prune safety preserved natively in canonical sync/coverage policy
- [x] Bootstrap/reconciliation preserved
- [x] `ScrapingConfig` unified
- [x] Workers configurable: category `16`, HTTP `28`, detail `32`
- [x] Product-code extraction and authoritative detail-code backfill preserved natively
- [x] Retry/backoff metrics are now observable without changing retry semantics

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

Reference: **latest applied FULL ID 182**

- 24 categories
- 534 product appearances
- 530 unique products
- 4 multi-category products
- 534 product-category relationships
- complete coverage
- 0 invalidating errors

Lower floors such as `529/525` are not valid substitutes for complete coverage. The latest successful complete real run remains the governing reference.

## POST-CONSOLIDATION REAL FULL — VALIDATED

### Scraping run

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

- `history_id=182`
- `status=SUCCESS`
- `categories_processed=24`
- `expected_category_occurrences=534`
- `products_found=534`
- `products_unique=530`
- `products_multiple_categories=4`
- `duplicate_occurrences=4`
- `errors=0`
- `applied_at` populated
- execution time: `149.375s`
- progress callback completed at `48/48`

### Latest classification

- `created=1`
- `updated=126`
- `unchanged=403`
- `deleted=0`

This classification is recorded for the latest applied FULL. The final catalog remained `530 / 534`, but the run is **not** classified as idempotent because it contained created/updated records.

### History

- `history_id=182` is the latest successful applied execution.
- Previous history remains preserved; failed/incomplete executions are not promoted over a valid complete FULL.
- The recovery rule remains: a historical coverage floor must never override the latest successful complete real run.

### Catalog after latest FULL

- `products=530`
- `product_categories=534`

The latest controller FULL persisted the authoritative `24 / 534 / 530 / 4` result with no invalidating errors.

## HTTP / DETAIL AUDIT

Recent FULL timing samples show the network layer, not SQLite/catalog persistence, is the dominant runtime area.

### Latest complete FULL HTTP sample

- `requests=349`
- category requests: `26`
- detail requests: `289`
- other requests: `34`
- retries: `2`
- errors: `1`
- terminal errors: `0`
- observed `max_concurrency=28`
- `retry_sleep_count=1`
- `retry_sleep_seconds=1.000`
- per-request `max_seconds≈20.422`
- aggregate request `total_seconds≈2301.970`

The `total_seconds` field is an aggregate of individual request timings and must not be interpreted as wall-clock execution time.

The current timeout baseline is `20s`, and the latest complete sample reached approximately `20.4s` on its slowest request. Historical valid wall-clock FULL timing was approximately `118.517s`; the latest controller run at `149.375s` therefore does not yet establish a performance improvement.

### Detail cache

- Latest complete sample: `detail_cache requests=289`
- `cache_hits=0`
- `cache_size=289`

Interpretation: the enrichment phase is still doing real detail HTTP requests for the consolidated product set; the detail cache is not materially reducing requests inside the same FULL sample.

### Performance conclusion

- [x] SQLite/catalog persistence is not the observed bottleneck.
- [x] Detail enrichment is a major network cost because roughly `289` detail requests are made per complete FULL sample.
- [x] Category listing/recovery is also a significant network cost and remains variable under transient retries.
- [x] Effective HTTP concurrency reaches the configured `28` in the current native path.
- [x] Retry/backoff telemetry is now available for benchmark interpretation.
- [x] No runtime optimization has been applied yet after this audit.
- [ ] Any performance optimization must be isolated, benchmarked, and validated against the authoritative `24 / 534 / 530 / 4` result.

## PER-CATEGORY TIMING NEXT STEP

- [x] Native page metrics are already available from `ProductCollectionScraper`.
- [ ] Add explicit per-category timing telemetry around collection/listing.
- [ ] Add explicit per-category timing telemetry around enrichment/detail.
- [ ] Use the telemetry to identify the slowest categories before changing worker/concurrency behavior.
- [ ] Run one isolated performance experiment at a time.
- [ ] Repeat an authoritative FULL after any runtime performance change.

## PROGRESS CONTRACT AUDIT

- [x] Audited `ScrapingRunner.run()` progress mapping
- [x] Confirmed FULL pipeline total is `2 × categories = 48`
- [x] Confirmed category collection currently emits `1..24`
- [x] Confirmed enrichment currently emits no intermediate `25..47` callbacks
- [x] Confirmed runner emits terminal `48/48` after `sync_categories()` returns
- [x] Confirmed this is a progress-reporting semantics issue only; the validated FULL result is unaffected
- [x] Added targeted contract test covering the current `1..N` then terminal `2N/2N` semantics
- [x] Validated runner + progress-contract tests: `8 passed`
- [ ] Decide whether to implement enrichment callbacks `25..47` as a separate UI-contract change

## TRANSACTION SCOPE AUDIT

- [x] Executed targeted scraping-session transaction/history/application-state tests
- [x] Result: `8 passed`
- [x] Verified rollback/error-history/application-state behavior remains green under current transaction boundaries
- [x] Audited the current transaction scope and its relationship to observed FULL timing
- [x] Current timing evidence does not justify treating SQLite transaction scope as the primary performance bottleneck
- [x] No transaction-boundary runtime change made
- [ ] Benchmark transaction scope only if a concrete SQLite contention or latency issue is observed

## MASTER PLAN STATUS

### 1. Corrección funcional

- [x] FULL real de 24 categorías validado
- [x] `534 / 530 / 4` validado como referencia autoritativa
- [x] `coverage_complete=1` y `coverage_gap=0`
- [x] 0 errores invalidantes
- [x] FULL/prune safety preservado

### 2. Recuperación y persistencia

- [x] Recuperación de paginación/JSF/cobertura/detalle/códigos consolidada
- [x] FULL incompleto no puede ejecutar prune destructivo
- [x] FULL fallida más reciente no sustituye una FULL válida anterior
- [x] Historial previo preservado
- [x] `history_id=182` aplicado correctamente
- [x] Catálogo reconciliado: `530 / 534`
- [x] Latest classification recorded: `1 created / 126 updated / 403 unchanged / 0 deleted`

### 3. Consolidación y limpieza

- [x] Implementación canónica única por responsabilidad
- [x] Legacy/patch facades muertos eliminados después de auditoría
- [x] Consumidores de tests migrados a APIs nativas
- [x] Factory canónica de producción confirmada
- [ ] Compatibility factories: conservar por compatibilidad externa potencial

### 4. Calidad

- [x] Full suite: `370 passed, 1 skipped, 7 deselected`
- [x] Architecture boundaries: `23 passed`
- [x] Ruff limpio
- [x] Pyright limpio
- [x] Runner + progress contract: `8 passed`
- [x] Retry/backoff metrics: `2 passed`

### 5. Progreso UI

- [x] Semántica actual `1..24`, luego `48/48`, documentada
- [x] Confirmado que no afecta cobertura ni persistencia
- [x] Tests formales del contrato de progreso
- [ ] Decidir, con tests, si se implementa progreso intermedio `25..47`

### 6. Transacciones SQLite

- [x] Atomicidad funcional validada
- [x] Rollback validado
- [x] Error-history/application-state validados
- [x] Alcance actual auditado frente al timing observado
- [ ] Benchmark de contención/latencia solo si aparece evidencia concreta
- [ ] Optimización del scope transaccional solo con evidencia cuantitativa

### 7. Rendimiento final

- [x] Separación de tiempos por etapa auditada
- [x] HTTP/detail auditado
- [x] Confirmado que SQLite no domina el tiempo total
- [x] Identificado que category/detail concentran el coste de red
- [x] Confirmada concurrencia HTTP efectiva hasta `28`
- [x] Integrada telemetría de retry/backoff
- [ ] Añadir tiempos explícitos por categoría para listing/collection
- [ ] Añadir tiempos explícitos por categoría para enrichment/detail
- [ ] Aislar siguiente experimento de rendimiento en network/category/detail
- [ ] Ejecutar benchmark comparativo
- [ ] Repetir FULL real después de cualquier cambio de runtime
- [ ] Confirmar nuevamente `24 / 534 / 530 / 4`
- [ ] Confirmar nuevamente DB `530 / 534`
- [ ] Confirmar historial aplicado y registrar clasificación real; exigir idempotencia solo cuando la ejecución realmente sea idempotente

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
- [x] Verify latest applied FULL is `history_id=182`
- [x] Record latest classification: `1 created, 126 updated, 403 unchanged, 0 deleted`
- [x] Confirm the latest run is not idempotent despite preserving 530 / 534 final counts
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
- [x] Verify latest controller FULL persists `history_id=182` as SUCCESS and applied
- [x] Verify latest catalog remains `530 products / 534 product_categories`
- [x] Audit current progress callback contract without changing scraping behavior
- [x] Execute targeted transaction/history/application-state audit: `8 passed`
- [x] Audit recent HTTP/detail request metrics without changing runtime behavior
- [x] Confirm effective HTTP concurrency reaches the configured worker level in recent samples
- [x] Confirm detail cache behavior is dominated by cache misses in complete FULL samples
- [x] Validate retry/backoff metrics without changing retry semantics
- [x] Consolidate the master state of correction, recovery, architecture cleanup, quality, transaction audit, progress audit, and performance audit
- [x] Add targeted progress-contract tests and validate them with runner tests: `8 passed`

### Next cleanup

- [ ] Keep compatibility scraping factories as thin external-compatibility wrappers unless a future audit proves they can be removed safely
- [ ] Decide whether the current UI contract is sufficient or whether enrichment progress `25..47` provides enough value to justify runtime callbacks
- [ ] Add per-category collection/listing timing telemetry without changing scraping behavior
- [ ] Add per-category enrichment/detail timing telemetry without changing scraping behavior
- [ ] Isolate the next performance experiment to network/category-detail behavior; do not alter FULL safety or persistence boundaries
- [ ] Benchmark/audit transaction scope only if a concrete SQLite contention or latency issue is observed
- [ ] Repeat a real FULL after any scraping/runtime performance change and require `24 / 534 / 530 / 4`, complete coverage, DB `530 / 534`, and an applied history entry
- [ ] Close the master plan only after the progress decision, any necessary transaction benchmark, and final performance validation are complete
