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

The authoritative real-site reference is the latest validated successful FULL run, **history_id=182**.

- `history_id=191`
- `mode=full`
- `status=SUCCESS`
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
- latest applied FULL classification: `created=0`, `updated=0`, `unchanged=530`, `deleted=0`.
- final catalog: `530 products / 534 product_categories`.
- latest history record is consistent with the protected master checkpoint and reports `0` errors.

Future FULL validation must be governed by the latest successful complete run, not by a manually chosen historical coverage floor such as 529/525.

## Current configuration baseline

- request timeout: `20s`
- max retries: `3`
- category workers: `8`
- shared HTTP workers: `28`
- detail workers: `16`
- HTML parser: `lxml`

Run/history 191 remains the latest applied history reference; the protected coverage baseline is the latest valid FULL at `24 / 534 / 530 / 4`. A newer real-site production-style E2E under `8 / 16 / 28` has now validated the full scrape-to-SQLite-to-history path in an isolated SQLite database.

## Latest repository validation

- No-real-site suite at the checkpoint: `431 passed, 2 deselected`
- Architecture-boundary tests: `23 passed`
- Targeted scraping coverage regressions: `8 passed`
- Transaction/history/application-state tests: `8 passed`
- Runner/progress contract tests: `8 passed`
- Retry/backoff metrics: `2 passed`
- Ruff: clean
- Pyright: `0 errors, 0 warnings, 0 informations`
- Image hashing focused audit: `10 passed`

## Performance audit status

The current evidence continues to point to network/category/detail work as the main runtime area rather than SQLite persistence.

Latest complete FULL HTTP sample:

- `requests=349`
- category requests: `26`
- detail requests: `289`
- other requests: `34`
- retries: `2`
- errors: `1`
- terminal errors: `0`
- `max_concurrency=28`
- retry sleep count: `1`
- retry sleep seconds: `1.000`
- slowest observed request: approximately `20.422s`
- aggregate request timing: approximately `2301.970s` (not wall-clock)

The detail cache showed `289` requests, `0` hits, and `289` cached entries in the latest complete sample. This indicates that the current enrichment phase is still dominated by real detail HTTP work within a FULL run.

The enrichment/detail timing telemetry is now in place. Controlled live measurements crossed 16 and 24 detail workers and showed comparable wall time, with 16 workers materially reducing aggregate detail HTTP work. The production detail-worker default is now `16`. A real production-style E2E under `8 / 16 / 28` completed in `113.97s` with `24 / 534 / 530 / 4`, `530 / 534` persisted records, successful history application, and zero HTTP retries.

## Progress contract

The current FULL runner reports category progress `1..24`, then emits terminal `48/48` after enrichment/synchronization completes. Tests validate this behavior. Intermediate enrichment callbacks `25..47` remain an optional UI-contract change and have not been introduced.

## Persistence and safety

FULL safety remains authoritative: incomplete or failed FULL runs must not perform destructive prune, and an unsuccessful run must not replace a previously valid complete applied state. Historical execution records remain preserved.
