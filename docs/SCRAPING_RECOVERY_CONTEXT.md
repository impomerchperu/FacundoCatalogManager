# Scraping recovery context

> **Reference point for future work on `feature/scraping-performance-recovery`.**
> Read this before proposing or applying changes to the scraper/sync pipeline.

## Current validated state

The application is locally green after the recovery and architecture-consolidation work completed so far.

- Branch: `feature/scraping-performance-recovery`
- Latest validated commit: `44ffa17952d0e512863fa295bbb7ad0671bbe52e`
- Latest local validation: `378 passed, 1 skipped, 7 deselected`
- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`
- No real-site FULL has been run after the latest architecture-consolidation checkpoint.

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

This checkpoint supersedes the older 530/526 reference that appears in historical notes. **Do not accept 529/525 or another manually chosen lower floor as a valid COMPLETE baseline.** The latest independently validated complete FULL result is authoritative.

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

## Current architecture checkpoint

Completed and locally validated consolidation areas:

- canonical scraping configuration with explicit category, HTTP, and detail worker limits;
- `Browser` HTTP concurrency injection with bounded semaphore;
- category worker injection through the normalized sync pipeline;
- canonical pagination engine used by `CategoryScraper`;
- native JSF concurrency control;
- native page-metrics collection and audit path;
- native price-detail recovery behavior;
- compatibility facades retained only where tests/legacy consumers still require them;
- canonical factory as the production construction path;
- bootstrap/reconciliation safety around the latest successful FULL run;
- FULL prune guard preventing destructive reconciliation on incomplete coverage;
- history recording that preserves the existing history and records only detected changes;
- legacy `scraped_products` / `sync_records` tables intentionally retained because recovery/reconciliation still consumes them.

One compatibility area remains under audit and must not be removed without evidence from usages/tests:

- `scrapers/collectors/page_coverage_recovery_patch.py` still contains an explicit runtime patch activation path.

Other retired patch modules are facades/no-op activators and should not be reintroduced as runtime monkey patches.

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

## Checklist before the next production/full validation

- [x] Pull latest branch and verify working tree.
- [x] Ruff clean.
- [x] Pyright clean.
- [x] Full automated test suite green.
- [x] Canonical worker configuration injected and covered by tests.
- [x] Pagination/recovery architecture protected by tests.
- [x] Bootstrap/history/prune safety protected by tests.
- [x] Authoritative FULL target recorded as `534 / 530 / 4`.
- [ ] Run the next real FULL across all 24 categories.
- [ ] Verify `products_found=534`, `products_unique=530`, `products_multiple_categories=4` and `coverage_complete=true`.
- [ ] Verify zero invalidating errors and no unsafe prune.
- [ ] Verify catalog/database reconciliation matches the complete FULL result.
- [ ] Verify history retains prior executions and records the new run correctly.
- [ ] Verify a subsequent idempotent FULL still produces no false changes.
- [ ] Only after the above, continue removing legacy compatibility/runtime patch code where proven safe.

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

1. Read this document and compare the proposed change against the authoritative 534-occurrence / 530-unique / 4-multi-category FULL baseline.
2. Prefer focused unit/integration tests before any expensive real-site run.
3. For real validation, use the smallest targeted category set that can demonstrate a code-path behavior first.
4. The decisive production validation is a **FULL run across all 24 categories**.
5. Do not treat a lower historical floor as evidence of complete coverage.
6. After any production change, re-check coverage, pruning guard, normalized persistence, idempotency, and history behavior.

### Guiding principle

**Preserve proven coverage and safety first. The 24-category FULL result is only valid when the actual run proves complete coverage; lower manually selected floors are not substitutes.**
