from types import SimpleNamespace

from scrapers.collectors import missing_code_recovery_patch


def test_recover_missing_code_uses_authoritative_detail_sku():
    product = SimpleNamespace(
        code="",
        url="https://stock.importacionesfacundo.com/producto/software-ikiosk-estandar-foto/",
    )

    class Browser:
        def get(self, url):
            assert url.endswith("software-ikiosk-estandar-foto/")
            return """
            <html><body>
                <span class='sku'>IKIOSK-ESTANDAR</span>
            </body></html>
            """

    recovered = missing_code_recovery_patch._recover_one(
        product,
        Browser(),
        missing_code_recovery_patch.ProductExtractor(),
    )

    assert recovered is True
    assert product.code == "IKIOSK-ESTANDAR"


def test_recover_missing_code_ignores_products_without_detail_url():
    product = SimpleNamespace(code="", url="https://stock.importacionesfacundo.com/tienda/")

    class Browser:
        def get(self, _url):
            raise AssertionError("No debe solicitar una URL que no sea de producto")

    recovered = missing_code_recovery_patch._recover_one(
        product,
        Browser(),
        missing_code_recovery_patch.ProductExtractor(),
    )

    assert recovered is False
    assert product.code == ""
