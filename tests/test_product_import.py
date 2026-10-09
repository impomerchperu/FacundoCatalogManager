from openpyxl import Workbook

from services.product_import import ProductImportService


def test_import_csv_uses_catalog_export_headers(tmp_path):
    path = tmp_path / "producto.csv"
    path.write_text(
        "\ufeffImagen;Código;Producto;Detalle;Categoría;Stock;Stock por color;"
        "Precio muestra;Precio ciento;Precio millar\n"
        "imagenes/fb100.jpg;FB-100;Básket infantil;Anti-estrés;"
        'Artículos / Recreación;15;"Rojo: 10\nAzul: 5";6;23.8;90\n',
        encoding="utf-8",
    )

    product = ProductImportService.import_first_product(path)

    assert product.code == "FB-100"
    assert product.name == "Básket infantil"
    assert product.description == "Anti-estrés"
    assert product.category == "Artículos / Recreación"
    assert product.stock == 15
    assert product.color_stock == {"Rojo": 10, "Azul": 5}
    assert product.price == 6
    assert product.price_sample == 6
    assert product.price_hundred == 23.8
    assert product.price_thousand == 90
    assert product.image_path == "imagenes/fb100.jpg"


def test_import_xlsx_finds_export_header_after_blank_rows(tmp_path):
    path = tmp_path / "producto.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append([None] * 10)
    sheet.append([None] * 10)
    sheet.append(
        [
            "Imagen",
            "Código",
            "Producto",
            "Detalle",
            "Categoría",
            "Stock",
            "Stock por color",
            "Precio muestra",
            "Precio ciento",
            "Precio millar",
        ]
    )
    sheet.append(
        [
            None,
            "FB-101",
            "Abridor",
            "Uso cocina",
            "Cocina, Mesa y Hogar",
            8,
            "Rojo: 8",
            5,
            20,
            70,
        ]
    )
    workbook.save(path)
    workbook.close()

    product = ProductImportService.import_first_product(path)

    assert product.code == "FB-101"
    assert product.name == "Abridor"
    assert product.stock == 8
    assert product.color_stock == {"Rojo": 8}
    assert product.price == 5
    assert product.price_sample == 5
    assert product.price_hundred == 20
    assert product.price_thousand == 70


def test_import_rejects_unsupported_formats(tmp_path):
    path = tmp_path / "producto.pdf"
    path.write_text("no importable", encoding="utf-8")

    try:
        ProductImportService.import_first_product(path)
    except ValueError as error:
        assert "CSV, XLSX o XLSM" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_import_products_reads_all_csv_rows(tmp_path):
    path = tmp_path / "carga_masiva.csv"
    path.write_text(
        "\ufeffCódigo;Producto;Categoría;Stock;Stock por color;Precio muestra;Precio ciento;Precio millar\n"
        ';Producto sin código;Cocina, Mesa y Hogar;4;"Rojo: 3\nAzul: 1";5;20;70\n'
        'FB-102;Segundo producto;Artículos Antiestrés;8;"Verde: 8";6;24;72\n',
        encoding="utf-8",
    )

    products = ProductImportService.import_products(path)

    assert len(products) == 2
    assert products[0].code == ""
    assert products[0].name == "Producto sin código"
    assert products[0].color_stock == {"Rojo": 3, "Azul": 1}
    assert products[0].price_sample == 5
    assert products[0].price_hundred == 20
    assert products[0].price_thousand == 70
    assert products[1].code == "FB-102"


def test_import_products_supports_xlsm(tmp_path):
    path = tmp_path / "carga_masiva.xlsm"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Código", "Producto", "Categoría", "Stock", "Precio"])
    sheet.append(["", "Producto nuevo", "Artículos de Oficina", 3, 9.5])
    workbook.save(path)
    workbook.close()

    products = ProductImportService.import_products(path)

    assert len(products) == 1
    assert products[0].code == ""
    assert products[0].name == "Producto nuevo"
    assert products[0].price == 9.5
