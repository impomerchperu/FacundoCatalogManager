# FCM Architecture Checkpoint

Fecha del checkpoint actual: 2026-09-20  
Branch oficial: `main`

## QUALITY

- [x] Targeted scraping coverage regressions validated
- [x] Última Quality CI: run `#2227` sobre `ec5297e` terminó en `success`; la suite de esa ejecución quedó verde (`464 passed, 8 deselected`)
- [x] Architecture-boundary tests validated
- [x] Ruff: clean (`All checks passed!`)
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Product-code migration/cleanup validated
- [x] Image hashing centralized without runtime semantic changes
- [x] Legacy destructive catalog cleanup disabled and covered
- [x] Legacy destructive image duplicate cleanup disabled and covered
- [x] Historical FULL reference preserved at `24 / 534 / 530 / 4`
- [x] Current operational FULL/E2E reference validated at `24 / 523 / 519 / 4`
- [x] Bootstrap/reconciliation tests: `15 passed`
- [x] HTTP/detail timing and retry telemetry audited
- [x] Per-category enrichment timing telemetry instrumented and tested
- [x] Progress-contract tests validated
- [x] Detail-cache concurrency tests validated
- [x] SQLite idempotency validated on consecutive identical catalog syncs

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
- [x] Image hashing duplication audit completed
- [x] Legacy DB/model audit completed; recovery tables retained intentionally
- [x] Production FULL validation completed
- [x] `CatalogScraper` production usage audited; no canonical runtime dependency found
- [x] Obsolete scraping facades and patch-only consumers removed after usage audits
- [x] Pagination, JSF-concurrency, page-metrics and product-code test consumers migrated to native APIs
- [x] Canonical service-level scraping factory confirmed in production usage
- [x] Compatibility scraping factories confirmed as thin delegates and retained only for possible external import compatibility
- [x] Execution authority separated: `scraping_runs` for FULL recovery/reconciliation, `scraping_history.applied_at` for latest applied history

## AUTHORITATIVE FULL REFERENCE

The governing functional reference is the latest successful complete FULL execution against the live inventory. The previous `24 / 534 / 530 / 4` remains a historical diagnostic snapshot.

Current validated invariants:

- 24 categories
- 523 product appearances
- 519 unique products
- 4 multi-category products
- 523 product-category relationships
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

## COLOR STOCK CONTRACT

- [x] `color_stock` remains part of the canonical product model and content hash.
- [x] Category cards map multiple stock values to color labels only when cardinality matches.
- [x] Detail pages support textual color declarations, singular `Color:` labels and WooCommerce variation metadata.
- [x] Detail-only color names remain available for the category/detail enrichment join without replacing an authoritative total-only stock.
- [x] ProductTable renders `color → stock` in the Stock cell while retaining numeric `product.stock` for sorting.
- [x] No artificial distribution of a total stock across multiple colors.

The live site currently demonstrates all of these source patterns: explicit `Colores disponibles` with multiple stocks, color names in detail combined with category stock, and products that list several colors but only one total stock. The extractor therefore treats exact cardinality as the evidence threshold rather than guessing.

## REAL FULL AND E2E VALIDATION

A production-style E2E validation documented in this checkpoint confirmed the current live inventory path:

- 24/24 categories
- 523 occurrences
- 519 unique products
- 4 multi-category products
- 0 missing codes
- complete coverage
- DB products: `519`
- DB relations: `523`
- run occurrences: `523`
- successful history with `applied_at`
- configured workers `8 / 16 / 28`
- terminal HTTP errors: `0`
- HTTP retries: `0`
- 337 HTTP requests
- total E2E wall time: `100.33s`
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

`CategoryProductSyncService` records these values from `ProductCollectionScraper.get_enrichment_metrics(category_name)` after each category enrichment and emits them through the existing timing logger as `stage=category_enrichment_summary`. During the same phase it now emits progress callbacks through the enrichment range `25..47` for a 24-category FULL; `ScrapingRunner` reserves `48/48` as the terminal callback.

The contract is covered by focused unit tests. Quality CI runs `#2135`, `#2186` and `#2201` are historical validation points; the current `main` baseline was subsequently confirmed by Quality run `#2210`.

This instrumentation is diagnostic only. It does not change coverage, product selection, persistence, prune behavior or retry semantics.

## PERFORMANCE STATUS

Performance remains secondary to correctness. The current production configuration is `8 / 16 / 28`. A real production-style E2E has now validated the complete scrape-to-SQLite-to-history path under this configuration with `24 / 523 / 519 / 4` and DB `519 / 523`; the historical `24 / 534 / 530 / 4` remains diagnostic.

No single wall-clock number is treated as a functional requirement because the live site and network are variable. Any runtime optimization must be isolated, benchmarked and followed by another authoritative FULL validation.

The enrichment instrumentation, crossed 16/24 worker benchmark, and intermediate progress callbacks are complete. Category concurrency has no justified increase. The initial JSF page-worker measurements were not comparable because the benchmark harness did not propagate the production JSF HTTP concurrency of `8`; the harness was corrected before the final comparison. Under the corrected contract, both PAGE `4` runs preserved `523/523` coverage and `0` terminal errors, but measured `42.85s` and `56.49s`, while PAGE `2` measured `53.43s`. The conflicting PAGE `4` results do not establish a reproducible wall-clock benefit, so the validated production default remains PAGE `2`. The isolated transport diagnostic is now closed: two collection runs with per-thread sessions measured `41.15s` and `52.79s`, while two comparable shared-session controls measured `53.43s` and `43.93s`. All four runs preserved `523/523` collection and `0` terminal errors. The aggregate difference is small relative to the observed run-to-run variability, and the direction is not consistent across paired observations; therefore no reproducible production benefit was established for `FCM_BENCH_THREAD_SESSIONS=1`. Production HTTP transport remains unchanged. The isolated category-page fetch diagnostic is closed. The category-page fetch comparison under the same `8 / 16 / 28` + JSF `8 / 2` contract now has three runs per condition. `PAGE=1`: `42.52s`, `51.15s`, `43.66s` (mean `45.78s`); `PAGE=2`: `45.59s`, `41.14s`, `46.85s` (mean `44.53s`). Every run preserved `523/523` collection and `0` terminal errors. The paired direction is not consistent (`PAGE=2` was slower once and faster twice), and the mean difference is only `1.25s` (`~2.7%`) within substantial run-to-run network variability. Therefore no reproducible production benefit is established and the validated production default remains `SCRAPING_CATEGORY_PAGE_WORKERS=1`. The benchmark diagnostic is closed without a runtime change. Quality CI runs `2093`–`2100` are green, including the stabilized concurrency test. `ProductCollectionScraper` now accepts benchmark-only `category_page_workers`, with production default `1`, and the live benchmark exposes `FCM_BENCH_CATEGORY_PAGE_WORKERS`. The default `1` preserves the pre-diagnostic behavior; values above `1` are not yet validated for production.

SQLite transaction-scope optimization is not currently a correctness blocker. A dedicated contention/latency benchmark is optional and should be triggered only by concrete evidence of SQLite contention.

## PROGRESS CONTRACT AUDIT

- [x] FULL pipeline total is `2 × categories = 48`
- [x] Category collection reports completion across `1..24`
- [x] Enrichment emits intermediate callbacks `25..47`
- [x] Runner emits terminal `48/48`
- [x] Current progress semantics are covered by tests (`13` focused progress/service/runner tests passed)
- [x] Confirmed progress semantics do not alter coverage or persistence

The current behavior is a UI-reporting choice, not a scraping correctness issue. More granular enrichment progress may be added later as a separate UX change.

## TRANSACTION SCOPE AUDIT

- [x] Atomicity of catalog/history state validated
- [x] Rollback/error-history/application-state behavior validated
- [x] Current transaction scope audited against observed timing
- [x] No evidence that transaction scope is the primary runtime bottleneck
- [x] No transaction-boundary runtime change made

El benchmark aislado de contención/latencia SQLite fue ejecutado sobre 530 productos con WAL + synchronous=NORMAL. Los cuatro escenarios terminaron sin errores; las escrituras tuvieron P95 entre 0.58 ms y 5.70 ms, las lecturas P95 <= 0.417 ms y el máximo puntual observado fue 16.52 ms. No existe evidencia suficiente para modificar el alcance transaccional ni la configuración SQLite actual.

## MASTER PLAN STATUS

### 1. Corrección funcional

- [x] FULL real de 24 categorías
- [x] `523 / 519 / 4` as current live operational reference; `534 / 530 / 4` preserved as historical diagnostic snapshot
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

### AUTHORITY MODEL AUDIT

- [x] `scraping_runs` is the recovery/reconciliation authority for the latest valid FULL.
- [x] `scraping_history.applied_at` is the latest applied-history marker and is not used as the FULL recovery selector.
- [x] `scraping_run_history` provides the explicit bridge between modern technical runs and history records.
- [x] Directed runs may be applied without becoming the FULL recovery baseline.

This distinction is intentional and avoids allowing a partial/directed application to silently replace the complete FULL reference used by bootstrap.

### CURRENT ENGINEERING CHECKPOINT

Current checkpoint is maintained on `main`.
The current release baseline is the merged recovery result; the enrichment progress contract and its tests are included in `main`. The last runtime hash fix remains `60ab60f93a4403652d23ae2e2ce5c18b5650ba6d`.

Última validación local del código funcional del checkpoint actual:

- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`
- Full no-real-site suite: `454 passed, 8 deselected`
- Git working tree: clean
- GitHub Actions Quality run `#2213`: success on `6e9739f`

The older focused-checkpoint and live-catalog references above remain historical evidence for the earlier audit checkpoint.

The audit also hardened two legacy maintenance tools so they cannot perform direct destructive deletion, and the catalog sync now initializes `content_hash` before classification so an identical second run remains idempotent:

- `tools/clean_catalog.py` remains diagnostic-only; `apply=True` is rejected.
- `services/scraping/image_audit_service.py` remains diagnostic-only; physical duplicate removal is rejected.
- `tools/audit_images.py --clean` is now treated as obsolete and rejected.

The independent FULL coverage validation and production-style E2E both confirmed the live operational reference `24 / 523 / 519 / 4`. The SQLite idempotency regression was then validated by the Quality CI, with Ruff, Pyright and Pytest green.

### 3. Consolidación y limpieza

- [x] Single canonical implementation per responsibility
- [x] Dead legacy facades/patches removed after audit
- [x] Test consumers migrated to native APIs
- [x] Canonical production factory confirmed
- [x] Compatibility factories retained only as thin external-compatibility wrappers

### 4. Calidad

- [x] Última Quality CI: `#2213` sobre `6e9739f` terminó en `success`; la validación local del baseline funcional quedó en `454 passed, 8 deselected`
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
- [x] Intermediate enrichment callbacks `25..47` implemented and covered by tests

### 6. SQLite transactions

- [x] Atomicity validated
- [x] Rollback validated
- [x] Error-history/application-state validated
- [x] Scope audited against observed timing
- [x] Benchmark aislado de contención/latencia SQLite ejecutado; no se justificó cambio de runtime

### 7. Performance

- [x] Stage timings audited
- [x] HTTP/detail audited
- [x] SQLite not identified as primary bottleneck
- [x] Category/detail identified as major network cost
- [x] Shared HTTP budget configured at `28`; observed peak `16` explained by upstream stage parallelism
- [x] Retry/backoff telemetry available
- [x] Category/HTTP workers `8 / 28` remain validated
- [x] Detail workers `16` selected after crossed live benchmark against `24`
- [x] Authoritative real-site scrape validated under production `8 / 16 / 28`
- [x] Per-category enrichment timing telemetry instrumented and tested
- [x] Benchmark: isolate detail worker behavior with crossed live runs
- [x] Final production E2E: revalidate coverage and persistence under `8 / 16 / 28`
- [x] Baseline concurrency benchmark `8 / 16 / 28` re-run with live coverage contract
- [x] HTTP diagnostics expose max in-flight by request class and P50/P95/P99 by stage
- [x] JSF page workers centralized in `ScrapingConfig` with production default `2`
- [x] Category worker comparison closed: `8` remains the validated production value; `12/16` showed no reproducible improvement
- [x] JSF page-worker comparison closed under `JSF HTTP=8`: PAGE `4` = `42.85s` and `56.49s`; PAGE `2` = `53.43s`; all runs had complete `523/523` collection and `0` terminal errors
- [x] No reproducible benefit established for PAGE `4`; production default remains PAGE `2`
- [x] Transport/session diagnostic closed: per-thread sessions `41.15s` and `52.79s`; shared-session controls `53.43s` and `43.93s`; all runs complete `523/523` with `0` terminal errors
- [x] No reproducible production benefit established for per-thread sessions; production HTTP transport remains unchanged
- [x] Benchmark-only category-page worker control added with production default `1`
- [x] Unit coverage added for parallel category-page loading; the test now measures actual overlap and preserves result order
- [x] Validate the stabilized category-page concurrency test in the local suite and Quality CI
- [x] Close the category-page worker comparison under the current `8 / 16 / 28` + JSF `8 / 2` contract after repeat controls; `PAGE=1` mean `45.78s` vs `PAGE=2` mean `44.53s`, no reproducible benefit
- [x] Explain HTTP max-in-flight `16` versus configured limit `28`
- [x] No runtime performance change was applied after the controlled diagnostics; the existing authoritative FULL remains the active release reference

## IMAGE STORAGE AUDIT POSITION

- ImageHash is the canonical file SHA-256 implementation.
- ImageDownloader.hash_file() and ImageAuditService delegate to it.
- ImageNamer is aligned with the canonical download path data/images/products and rejects unsupported URL extensions.
- ImageValidator shares the canonical image-extension set, including GIF.
- ImageRepository prefers the file extension represented by the current product image URL, preventing an older variant from being selected accidentally.
- tools/audit_image_storage.py provides a non-destructive filesystem/SQLite/SHA-256 audit.
- products.image_path is the sole active allowlist for stored catalog images.
- tools/clean_unused_images.py removes only image files not referenced by products.image_path; it is dry-run by default and requires --delete for physical removal.
- The production FULL sync invokes the same cleanup automatically after a validated prune; directed and incomplete runs never invoke it.
- The cleanup roots default to data/images and resources/images, so historical images outside the current catalog are treated as removable local storage.
- The cleanup tool never removes a path present in products.image_path, even when it appears in a duplicate/hash group.
- Quality CI previously validated the image-storage audit changes with 446 passed, 8 deselected.
- [x] Real local audit completed for database/catalog.db, data/images and data/images/products.
- [x] Current catalog image references are complete: 530/530 files present, 0 missing active references, 0 hash mismatches.
- [x] Initial local cleanup executed: 507 unreferenced files removed, 64,009,379 bytes freed.
- [x] Post-cleanup audit confirms 530 active image files, 0 active orphans, 0 missing active references and 0 hash mismatches.
## LIVE INVENTORY DRIFT

Las validaciones reales documentadas en este checkpoint confirmaron `523` apariciones esperadas, `519` productos únicos y `4` multi-categoría en 24/24 categorías, con cobertura completa. El total publicado por las categorías en cada ejecución es ahora la fuente de verdad de cobertura; `534 / 530 / 4` permanece como referencia histórica.

## RELEASE POSITION

## GUI OPERATIONAL SMOKE TEST

El smoke test manual de la aplicación sobre el baseline actual fue completado el 2026-09-20. Se confirmó el arranque de `app.py`, la carga del catálogo persistido desde `database/catalog.db` sin iniciar scraping automáticamente, la disponibilidad y navegación de la tabla, búsqueda/filtros, los accesos a **Actualizar catálogo** y **Historial**, y la ejecución completa del flujo de actualización desde la GUI. El resultado final, detalle e historial fueron revisados sin incidencias visibles.

La validación manual confirma el contrato operativo de la GUI sobre el baseline existente; no implica cambios de runtime ni sustituye las pruebas automatizadas o el E2E real.

The correction, recovery, persistence, reconciliation, coverage, performance diagnostics and automated quality work remain validated on `main`. The live functional reference remains `24 / 523 / 519 / 4`, with complete coverage, DB `519 / 523`, applied history and production-style E2E evidence. The historical `24 / 534 / 530 / 4` snapshot remains diagnostic. Image storage now follows a DB-backed allowlist: products.image_path is the sole active reference, resources/images historical assets have been removed from the repository, and local generated files outside that allowlist are cleaned explicitly with tools/clean_unused_images.py. No queda pendiente una acción de release para la auditoría de imágenes: la verificación local ya confirmó la ruta canónica activa, cero referencias activas inexistentes y cero archivos huérfanos; el reporte JSON generado durante la auditoría se mantiene fuera del repositorio.
