"""Reliable pagination compatibility layer for category archives."""

# ...

    """Fetch every consecutive JSF page until the archive is actually exhausted.

    ``expected_count`` is used to establish a minimum page target, never as a
    hard product limit.  Once real product identities are available, additional
    hidden-page probes are allowed to discover pages omitted by site metadata.
    Synthetic/partial responses are bounded by the measurable page target so
    pagination tests do not perform speculative requests forever.
    """
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)
    seen_products = _product_keys(scraper, first_html)

    published_count = _published_product_count(first_html)
    target_count = max(int(expected_count or 0), published_count)

    try:
        found_posts, declared_pages, jsf_first_html = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        found_posts, declared_pages, jsf_first_html = 0, 0, ""

    target_count = max(target_count, found_posts)
    if jsf_first_html:
        scraper._cache_category_html(category_url, jsf_first_html)
        seen_products.update(_product_keys(scraper, jsf_first_html))

    page = 2
    previous_html = jsf_first_html
    expected_pages = (target_count + 24) // 25 if target_count else 0
    safety_limit = max(declared_pages or 0, expected_pages, 1)
    while page <= safety_limit:
        page_url = scraper._jsf_page_url(category_url, page)
        try:
            found_posts, page_count, rendered_html = scraper._fetch_jsf_page(
                category_url, category_id, page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            break

        target_count = max(target_count, found_posts)
        safety_limit = max(safety_limit, page_count)
        if not rendered_html or rendered_html == previous_html:
            break

        page_keys = _product_keys(scraper, rendered_html)
        had_product_identity = bool(seen_products or page_keys)
        seen_products.update(page_keys)
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        previous_html = rendered_html
        page += 1

        # Real product-bearing responses may have more pages than metadata or
        # count arithmetic says. Keep probing in that case; expected_count and
        # max_num_pages must never truncate a real archive.
        if had_product_identity and page > safety_limit:
            safety_limit = page + scraper.MAX_HIDDEN_PAGE_PROBES

    # Only enforce product-count coverage when rendered pages expose measurable
    # product identities. Synthetic/partial HTML must not cause false failures.
    if target_count and seen_products and len(seen_products) < target_count:
        raise RuntimeError(
            "Cobertura incompleta para "
            f"{category_url}: encontrados={len(seen_products)} esperados={target_count}."
        )
    return pages
