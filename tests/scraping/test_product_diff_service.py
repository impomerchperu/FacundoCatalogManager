from services.scraping.product_diff_service import ProductDiffService


def test_detect_product_changes():

    service = ProductDiffService()

    old = {"code": "P001", "name": "Mug Azul", "price": 20, "stock": 5}

    new = {"code": "P001", "name": "Mug Azul", "price": 25, "stock": 10}

    result = service.compare(old, new)

    assert result["changed"] is True
    assert "price" in result["fields"]
    assert "stock" in result["fields"]


def test_detect_no_changes():

    service = ProductDiffService()

    product = {"code": "P001", "name": "Mug Azul", "price": 20, "stock": 5}

    result = service.compare(product, product)

    assert result["changed"] is False

def test_detect_color_stock_changes():
    service = ProductDiffService()

    old = {
        "code": "P002",
        "name": "Producto",
        "stock": 10,
        "color_stock": {"Rojo": 4, "Azul": 6},
    }
    new = {
        "code": "P002",
        "name": "Producto",
        "stock": 12,
        "color_stock": {"Rojo": 6, "Azul": 6},
    }

    result = service.compare(old, new)

    assert result["changed"] is True
    assert "stock" in result["fields"]
    assert "color_stock" in result["fields"]
    assert result["content_changed"] is True
    assert result["image_changed"] is False
