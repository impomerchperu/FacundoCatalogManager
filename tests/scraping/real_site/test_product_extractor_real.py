import re

import pytest
from bs4 import BeautifulSoup

from scrapers.browser import Browser
from scrapers.extractors.product_extractor import ProductExtractor

URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


@pytest.mark.real_site
def test_product_extractor_real_site():
    """Validación manual contra el sitio real; excluida de la suite normal."""
    browser = Browser()
    html = browser.fetch(URL)
    soup = BeautifulSoup(html, "lxml")

    product = ProductExtractor().extract(
        soup,
        url=URL,
        category="Jarros Mug",
    )

    assert product is not None
    print(product)

FB4008_URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/antiestres-cerebro-largo/"
)


@pytest.mark.real_site
def test_product_extractor_real_site_fb4008_technical_detail():
    """Confirma que Detalle sale del resumen técnico real, no de las pestañas."""
    browser = Browser()
    try:
        html = browser.fetch(FB4008_URL)
    finally:
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    product = ProductExtractor().extract(
        soup,
        url=FB4008_URL,
        category="Artículos Antiestrés",
    )

    detail = product["description"]
    assert product["code"] == "FB-4008"
    if not detail:
        technical_detail_dom_diagnostics = []
        material_pattern = re.compile(r"\bMaterial\s*:", re.IGNORECASE)
        for text_node in soup.find_all(string=material_pattern):
            parent = text_node.parent
            if parent is None or parent.name in {"script", "style"}:
                continue
            ancestry = []
            node = parent
            for _ in range(6):
                if node is None:
                    break
                ancestry.append(
                    {
                        "tag": node.name,
                        "id": node.get("id", ""),
                        "class": list(node.get("class", []) or []),
                        "text": node.get_text(" ", strip=True)[:240],
                    }
                )
                node = node.parent
            technical_detail_dom_diagnostics.append(ancestry)
        pytest.fail(
            "No se extrajo Detalle de FB-4008. "
            "Estructura HTML de los nodos Material: "
            f"{technical_detail_dom_diagnostics[:10]!r}"
        )
    assert detail.startswith("Color: Blanco. Material: Poliuretano.")
    assert "Dimensiones: 75*63*48mm." in detail
    assert "Peso Unitario: 23.5 G." in detail
    assert "Peso neto por caja: 5.5 Kg." in detail
    assert "Peso bruto por caja: 6.25 Kg." in detail
    assert "Color: Blanco" in detail
    assert "Información adicional" not in detail
    assert "Valoraciones" not in detail
