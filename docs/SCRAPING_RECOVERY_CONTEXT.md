# Scraping recovery context

> **Reference point for future work on `feature/scraping-performance-recovery`.**
> Read this before proposing or applying changes to the scraper/sync pipeline.

## FCM architecture checkpoint — 2026-09-14

### BRANCH

- [x] `feature/scraping-performance-recovery`

### QUALITY

- [x] Full automated suite: `378 passed, 1 skipped, 7 deselected`
- [x] Ruff: `All checks passed!`
- [x] Pyright: `0 errors, 0 warnings, 0 informations`
- [x] Focused scraping/recovery coverage retained
- [x] Bootstrap/reconciliation coverage retained
- [x] Architecture-boundary coverage retained

### RUNTIME CONSOLIDATION

- [x] Pagination monkey patch retired
- [x] JSF concurrency monkey patch retired
- [x] Page-metrics monkey patch retired
- [x] Price recovery monkey patch retired
- [x] Price recovery preserved natively in `ProductCollectionScraper`
- [x] Page-metrics audit preserved
- [x] Canonical pagination engine active
- [x] FULL/prune safety preserved
- [x] Bootstrap/reconciliation preserved
- [x] Canonical `ScrapingConfig` worker limits unified and injected
- [x] Browser HTTP concurrency limit injected (`28` by default)
- [x] Category worker limit injected (`16` by default)
- [x] Detail worker limit injected (`32` by default)

### ARCHITECTURE CLEANUP STATUS

- [x] P4b — consolidate price recovery into `ProductCollectionScraper` base behavior
- [x] P5 — remove duplicated pagination policy from `CategoryScraper` in favor of the canonical pagination engine
- [x] P6 — finish `ScrapingConfig` unification and worker propagation
- [x] P7 — compatibility/dead-code audit substantially completed; compatibility facades retained only where current tests/consumers require them
- [x] P8 — legacy DB/model audit completed; `scraped_products` and `sync_records` retained intentionally because recovery/reconciliation still consumes them
- [ ] P9 — real FULL validation across all 24 categories

### REMAINING ARCHITECTURE AUDIT

The main remaining compatibility item requiring explicit evidence before removal is:

- `scrapers/collectors/page_coverage_recovery_patch.py` still exposes an explicit runtime `activate()` monkey-patch path.

Do not remove or invoke that compatibility path as part of the production FULL validation. Audit its actual usages/tests separately after the real FULL has passed.

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
- `errors=0`
- `category_workers=16`
- `http_workers=28`
- `detail_workers=32`

Interpretation:

- 534 product-category appearances/occurrences.
- 530 unique product codes.
- 4 products legitimately appearing in multiple categories.
- 534 product-category relationships.
- Complete coverage means all expected category occurrences are represented and the unique-code count is complete.

This checkpoint supersedes all older 530/526 notes. **Do not accept 529/525 or another manually chosen lower floor as a valid COMPLETE baseline.** The latest independently validated complete FULL result is authoritative.

## Non-negotiable safety rules

1. **Never mutate the catalog on an incomplete FULL scrape.**
   A partial FULL run must not create/update/delete catalog data or normalized category occurrences.

2. **Pruning missing catalog products is allowed only after valid FULL coverage.**
   Missing local codes may be deleted only when the final FULL result proves complete expected coverage and has no blocking errors.

3. **Do not restore the old fallback that creates a product when its code is not detected.**
   Product identity is based on the detected product code.

4. **A recovered terminal HTTP error must not invalidate a FULL result when the final dataset independently proves complete coverage.**
   This is intentional recovery behavior; do not simplify it back to “any terminal HTTP error means incomplete.”

5. **Keep category occurrence coverage separate from unique product coverage.**
   The authoritative baseline is 534 category occurrences and 530 unique product codes, with 4 multi-category products.

6. **Do not break the already-solved embedded/AJAX category pagination.**
   Multiple product pages can exist under the same category URL through JetSmartFilters/AJAX.

## Current validated engineering state

The application is locally green after the recovery and architecture-consolidation work completed so far.

- Branch: `feature/scraping-performance-recovery`
- Latest validated code commit: `44ffa17952d0e512863fa295bbb7ad0671bbe52e`
- Latest documentation checkpoint commit: this update
- Latest local validation: `378 passed, 1 skipped, 7 deselected`
- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`
- No real-site FULL has been run after the latest architecture-consolidation checkpoint.

## Production construction path

The canonical production path is:

`ScrapingController.run_full_scraping()` → `ScrapingSession.execute_all()` → `ScrapingRunner.run_all()` → canonical normalized scraping/sync pipeline.

`run_all()` discovers the categories through `CategoryService`. When all discovered categories remain selected, the runner executes them as a FULL run; when a category filter is active, the run is treated as directed rather than FULL.

The FULL validation must therefore use the application’s real full-catalog entry point, not a handcrafted subset of categories.

## Real-site pagination facts

Target site: `https://stock.importacionesfacundo.com/`

Known JetSmartFilters/AJAX characteristics:

- `action=jet_smart_filters`
- provider: `bricks-query-loop/querydesk`
- `element_id=95dc8a`
- `orderby=menu_order ASC`
- `posts_per_page=25`
- `disable_query_merge=true`
- `post_status=publish`
- response pagination can expose `found_posts` and `max_num_pages`
- different AJAX pages can use the **same category URL**

Do not replace this behavior with a simplistic “one HTML page = one category page” assumption.

## History behavior already validated

History is expected to contain only detected changes:

- `NEW`: repository expands the event into product detail fields.
- `UPDATED`: only fields actually changed are recorded.
- `DELETED`: one explicit deletion detail is recorded.
- detail listing is sorted by product code.
- application completion time is retained.
- idempotent FULL behavior must continue to produce zero false detail rows when nothing changed.

The bootstrap/reconciliation path must preserve prior history and must never treat an incomplete latest scrape as authoritative catalog state.

## Checklist — before and after the next real FULL

- [x] Pull latest branch and verify working tree.
- [x] Ruff clean.
- [x] Pyright clean.
- [x] Full automated test suite green.
- [x] Canonical worker configuration injected and covered by tests.
- [x] Pagination/recovery architecture protected by tests.
- [x] Bootstrap/history/prune safety protected by tests.
- [x] P4b/P5/P6 architecture consolidation complete.
- [x] P7 compatibility/dead-code audit substantially complete.
- [x] P8 legacy DB/model audit complete; legacy recovery tables retained intentionally.
- [x] Authoritative FULL target recorded as `24 / 534 / 530 / 4`.
- [ ] Run the next real FULL across all 24 categories.
- [ ] Verify `categories_processed=24`.
- [ ] Verify `products_found=534`, `products_unique=530`, `products_multiple_categories=4`.
- [ ] Verify `expected_category_occurrences=534` and `duplicate_occurrences=4`.
- [ ] Verify `coverage_complete=true` and zero invalidating errors.
- [ ] Verify no unsafe prune occurs when coverage is incomplete.
- [ ] Verify catalog/database reconciliation matches the complete FULL result.
- [ ] Verify all prior history remains intact.
- [ ] Verify the new history entry is `SUCCESS` and records only effective changes.
- [ ] Verify a subsequent identical FULL is idempotent and produces no false changes.
- [ ] Only after the above, continue removing remaining compatibility/runtime patch code where proven safe.

## Validated local commands

```powershell
git fetch origin --prune
git switch feature/scraping-performance-recovery
git pull --ff-only origin feature/scraping-performance-recovery

python -m ruff check .
python -m pyright
python -m pytest -q
```

## How to continue safely

Before changing scraper/sync code:

1. Read this document and compare every change against the authoritative 24-category / 534-occurrence / 530-unique / 4-multi-category FULL baseline.
2. Prefer focused unit/integration tests before any expensive real-site run.
3. For real validation, do not substitute a category subset for the decisive FULL validation.
4. The decisive production validation is a **FULL run across all 24 categories** through the canonical application entry point.
5. Do not treat a lower historical floor as evidence of complete coverage.
6. After the FULL, validate database reconciliation, history preservation, and idempotency before further cleanup.

### Guiding principle

**Preserve proven coverage and safety first. The 24-category FULL result is valid only when the actual run proves complete coverage; lower manually selected floors are not substitutes.**
