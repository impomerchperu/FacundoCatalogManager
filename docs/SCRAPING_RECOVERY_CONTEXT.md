# Scraping recovery context

> **Reference point for future work on `feature/scraping-performance-recovery`.**
> Read this before proposing or applying changes to the scraper/sync pipeline.

## Current validated state

The catalog is currently **working correctly** after the recovery work:

- Branch: `feature/scraping-performance-recovery`
- Latest validated application state: catalog opens correctly from SQLite.
- Full 24-category real synchronization completed successfully.
- A second full 24-category run completed successfully and was idempotent.
- Local focused tests and Ruff are passing.

### Real FULL baseline

First successful 24-category FULL run:

- `history_id=169`
- `status=SUCCESS`
- `categories_processed=24`
- `products_expected=526`
- `expected_category_occurrences=530`
- `products_found=530`
- `products_unique=526`
- `created=526`
- `updated=0`
- `unchanged=0`
- `deleted=0`
- `missing_code=0`
- `duplicate_occurrences=4`
- `coverage_complete=true`
- `errors=0`

Second successful 24-category FULL run:

- `history_id=170`
- `status=SUCCESS`
- `categories_processed=24`
- `products_expected=526`
- `expected_category_occurrences=530`
- `products_found=530`
- `products_unique=526`
- `created=0`
- `updated=0`
- `unchanged=526`
- `deleted=0`
- `missing_code=0`
- `duplicate_occurrences=4`
- `coverage_complete=true`
- `errors=0`
- `download_changes=0`

Database validation after the first FULL run showed **526 products** and no foreign-key violations. The four duplicate category occurrences are legitimate multi-category occurrences, not extra master products.

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
   The valid baseline is 530 category occurrences but 526 unique product codes.

6. **Do not break the already-solved embedded/AJAX category pagination.**
   Multiple product pages can exist under the same category URL through JetSmartFilters/AJAX.

## Real-site pagination facts

Target site: `https://stock.importacionesfacundo.com/`

Relevant category examples:

- Jarros Mug: 19 products.
- Artículos de Antiestrés: 50 products across the AJAX pagination behavior.
- Total catalog baseline: 24 categories, 530 category occurrences, 526 unique product codes.

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

## Current architecture areas to protect

Important production files:

- `services/scraping/category_product_sync_service.py`
- `services/scraping/normalized_category_product_sync_service.py`
- `services/scraping/prune_guard_recovery_patch.py`
- `services/scraping/scraping_runner.py`
- `services/scraping/catalog_sync_service.py`
- `models/scraping/sync_result.py`
- `repositories/scraping/scraping_history_repository.py`
- `scrapers/collectors/full_sync_safety_patch.py`

Important test areas:

- `tests/scraping/test_catalog_sync_service.py`
- `tests/scraping/test_download_history.py`
- `tests/scraping/test_category_product_sync_result.py`
- `tests/scraping/integration/test_category_product_sync_coverage.py`
- pagination/coverage tests under `tests/scraping/`

## History behavior already validated

History is expected to contain only detected changes:

- `NEW`: repository expands the event into product detail fields.
- `UPDATED`: only fields actually changed are recorded.
- `DELETED`: one explicit deletion detail is recorded.
- detail listing is sorted by product code.
- application completion time is retained.
- idempotent FULL run 170 produced zero detail rows.

Do not regress this by recording all product fields for every UPDATE or by generating false changes on unchanged runs.

## Validated local commands

After pulling the current branch:

```powershell
git fetch origin --prune
git switch feature/scraping-performance-recovery
git pull --ff-only origin feature/scraping-performance-recovery

python -m pytest -q `
  tests/scraping/test_catalog_sync_service.py `
  tests/scraping/test_download_history.py `
  tests/scraping/test_category_product_sync_result.py `
  tests/scraping/integration/test_category_product_sync_coverage.py

python -m ruff check .
```

Latest validated result at the time this document was created:

- `26 passed`
- Ruff: `All checks passed!`

## How to continue safely

Before changing scraper/sync code:

1. Read this document and compare the proposed change against the 530-occurrence / 526-unique baseline.
2. Prefer focused unit/integration tests before any expensive real-site run.
3. For real validation, use the smallest targeted category set that can demonstrate the behavior first.
4. Do **not** perform another 24-category real scrape merely to investigate a hypothesis when a deterministic test can prove it.
5. After any production change, re-check coverage, pruning guard, normalized persistence, idempotency, and history behavior.

### Guiding principle

**Do not optimize away or rewrite working recovery logic just because it looks complex. Preserve proven behavior first; change only the smallest necessary surface and prove that the 530/526 baseline remains intact.**
