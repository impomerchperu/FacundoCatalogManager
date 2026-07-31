from services.scraping.product_diff_service import ProductDiffService


def test_detect_product_changes():

    service = ProductDiffService()

    old = {
        "code": "P001",
        "name": "Mug Azul",
        "price": 20,
        "stock": 5
    }

    new = {
        "code": "P001",
        "name": "Mug Azul",
        "price": 25,
        "stock": 10
    }

    result = service.compare(old, new)

    assert result["changed"] is True
    assert "price" in result["fields"]
    assert "stock" in result["fields"]


def test_detect_no_changes():

    service = ProductDiffService()

    product = {
        "code": "P001",
        "name": "Mug Azul",
        "price": 20,
        "stock": 5
    }

    result = service.compare(product, product)

    assert result["changed"] is False