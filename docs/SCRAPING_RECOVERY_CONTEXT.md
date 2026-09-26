# Scraping recovery context

- [x] P5 — remove duplicated pagination policy from `CategoryScraper` in favor of the canonical pagination engine
- [x] P6 — finish `ScrapingConfig` unification and worker propagation
- [x] P7 — compatibility/dead-code audit substantially completed; compatibility facades retained only where current tests/consumers require them
- [x] P8 — legacy DB/model audit completed; `scraped_products` and `sync_records` retained intentionally because recovery/reconciliation still consumes them
- [x] P9 — real FULL validation across all 24 categories completed

### REMAINING ARCHITECTURE AUDIT

No production dependency remains for the retired recovery facades removed during the scraping cleanup. Canonical pagination and coverage recovery remain active in `category_pagination_engine.py` and the current `CategoryScraper` flow.

The obsolete `missing_code_recovery_patch.py` facade and its facade-only test have also been removed. Missing-code recovery remains natively implemented in `CategoryProductSyncService` and is covered by the current contract test.

## Current operational FULL checkpoint

The current operational real-site reference is the latest validated successful complete FULL/E2E result:

- categories: `24`
- product appearances: `523`
- unique products: `519`
- multi-category products: `4`
- product-category relations: `523`
- `coverage_complete=true`
- `coverage_gap=0`
- `error_count=0`
- production configuration: category `8`, detail `16`, HTTP `28`
- latest production-style E2E: DB `519 / 523`, `337` HTTP requests, `0` retries, `0` terminal errors

Future FULL validation must be governed by the latest successful complete run and the current `expected_count` values published by the live categories, not by a manually chosen historical coverage floor such as 529/525.

### Historical recovery reference

The older `history_id=191` snapshot remains preserved for diagnostics:

- `534` category occurrences
- `530` unique products
- `4` multi-category products
- `534` product-category relations
- `coverage_complete=true`
- `coverage_gap=0`
- `error_count=0`

It is not the current operational catalog baseline.

## Current configuration baseline

- request timeout: `20s`
- max retries: `3`
- category workers: `8`
- shared HTTP workers: `28`
- detail workers: `16`
- HTML parser: `lxml`

The historical run/history 191 remains available for recovery diagnostics. The protected operational baseline is `24 / 523 / 519 / 4`. A real-site production-style E2E under `8 / 16 / 28` validated the full scrape-to-SQLite-to-history path in an isolated SQLite database.

## Latest repository validation

- Local validation on 2026-09-26: Ruff clean
- Local validation: Pyright `0 errors, 0 warnings, 0 informations`
- Local validation: Pytest `507 passed, 10 deselected`
- Quality CI on current release baseline: success
- Architecture-boundary, bootstrap/reconciliation, runner/progress, retry/backoff and image-hashing contracts remain covered

## Performance audit status


The current evidence continues to point to network/category/detail work as the main runtime area rather than SQLite persistence.

Current validated production-style E2E evidence:

- `337` HTTP requests
- category workers: `8`
- detail workers: `16`
- HTTP budget: `28`
- JetSmartFilters HTTP concurrency: `8`
- `0` retries
- `0` terminal HTTP errors
- complete `523/523` collection
- `24 / 523 / 519 / 4`
- DB `519 / 523`
- successful history application

Historical diagnostics remain useful for profiling but are not treated as the current runtime baseline. In particular, older samples with `349` requests, `289` detail requests or `534 / 530` catalog counts are preserved as diagnostic evidence, not current state.

The enrichment/detail timing telemetry is now in place. Controlled live measurements crossed 16 and 24 detail workers and showed no reproducible wall-clock benefit for 24; the production detail-worker default remains `16`.

## Progress contract

The current FULL runner reports category progress `1..24`, enrichment callbacks `25..47`, then emits terminal `48/48` after enrichment/synchronization completes. Tests validate this behavior.

## Persistence and safety

FULL safety remains authoritative: incomplete or failed FULL runs must not perform destructive prune, and an unsuccessful run must not replace a previously valid complete applied state. Historical execution records remain preserved.

## Post-release status

The recovery architecture is considered complete for the current release baseline. There are no open recovery tasks blocking development. Future changes to scraping, persistence, concurrency or reconciliation must preserve the current operational invariants and be revalidated before becoming a new baseline.
