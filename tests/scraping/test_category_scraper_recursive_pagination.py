from scrapers.collectors.category_scraper import CategoryScraper


def test_category_scraper_discovers_pagination_embedded_on_intermediate_page():
    category_url = "https://example.test/categoria-producto/jarros-mug/"
    page_two = f"{category_url}page/2/"
    page_three = f"{category_url}page/3/"

    class FakeBrowser:
        def __init__(self):
            self.calls = []

        def get(self, url):
            self.calls.append(url)
            if url == category_url:
                return (
                    '<div class="jet-filters-pagination__item" data-value="2">'
                    '<div class="jet-filters-pagination__link">2</div>'
                    '</div>'
                )
            if url == page_two:
                return (
                    '<div class="jet-filters-pagination__item" data-value="3">'
                    '<div class="jet-filters-pagination__link">3</div>'
                    '</div>'
                )
            return ""

    browser = FakeBrowser()
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url)

    assert pages == [category_url, page_two, page_three]
    assert page_two in browser.calls
    assert page_three in browser.calls


def test_category_scraper_reuses_discovered_page_html_from_cache():
    category_url = "https://example.test/categoria-producto/jarros-mug/"
    page_two = f"{category_url}page/2/"

    class FakeBrowser:
        def __init__(self):
            self.calls = []

        def get(self, url):
            self.calls.append(url)
            if url == category_url:
                return (
                    '<div class="jet-filters-pagination__item" data-value="2">'
                    '<div class="jet-filters-pagination__link">2</div>'
                    '</div>'
                )
            return ""

    browser = FakeBrowser()
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url)
    assert pages == [category_url, page_two]

    # get_category_pages ya dejó la página descubierta en el cache de una sola
    # lectura para que ProductCollectionScraper no tenga que volver a pedirla.
    assert browser.calls.count(page_two) == 1
    assert scraper.get_html(page_two) == ""
    assert browser.calls.count(page_two) == 1
