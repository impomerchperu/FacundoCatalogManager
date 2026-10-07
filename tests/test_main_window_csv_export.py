from models.product import Product


def test_main_window_export_csv_uses_controller_products_and_dialog(
    monkeypatch,
    tmp_path,
):
    from exporters.csv_exporter import CSVExporter
    from gui.main_window import MainWindow

    output = tmp_path / "catalogo.csv"
    product = Product(code="FB-100", name="Producto")
    calls = {}

    class Controller:
        def get_products(self):
            calls["products"] = [product]
            return [product]

    monkeypatch.setattr(
        "gui.main_window.QFileDialog.getSaveFileName",
        lambda *args: (str(output), "CSV (*.csv)"),
    )

    def export(products, filename):
        calls["export"] = (products, filename)

    monkeypatch.setattr(CSVExporter, "export", export)

    window = MainWindow.__new__(MainWindow)
    window.controller = Controller()
    window.export_csv()

    assert calls["products"] == [product]
    assert calls["export"] == ([product], str(output))


def test_main_window_excel_dialog_inherits_active_category_and_stock_filters(
    monkeypatch,
    tmp_path,
):
    from PySide6.QtWidgets import QApplication, QLineEdit

    from exporters.excel_exporter import ExcelExporter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    output = tmp_path / "catalogo.xlsx"
    products = [
        Product(
            code="A-100",
            name="Antiestres",
            category="Antiestres",
            stock=5,
        ),
        Product(
            code="A-101",
            name="Escritorio",
            category="Escritorios",
            stock=7,
        ),
        Product(
            code="A-102",
            name="Bolsa",
            category="Bolsas / Mochilas",
            stock=0,
        ),
    ]

    calls = {}
    dialog_ref = {}

    class FakeDialog:
        def __init__(
            self,
            categories,
            products,
            parent,
            *,
            initial_selected_categories,
            stock_only,
            on_export,
        ):
            del parent
            calls["categories"] = set(categories)
            calls["products"] = list(products)
            calls["initial_selected"] = set(initial_selected_categories)
            calls["stock_only"] = stock_only
            calls["on_export"] = on_export
            self.products = list(products)
            self.selected_categories = set(initial_selected_categories)
            self.stock_only = stock_only
            dialog_ref["instance"] = self

        def exec(self):
            self.on_export(
                "excel",
                self.filter_products(
                    self.products,
                    self.selected_categories(),
                    stock_only=self.stock_only,
                ),
            )
            return True

        def selected_categories(self):
            return set(self.selected_categories)

        @staticmethod
        def filter_products(products, categories, *, stock_only=False):
            result = [
                product
                for product in products
                if MainWindow._product_categories(product)
                & {category for category in categories}
            ]
            if stock_only:
                result = [product for product in result if product.stock > 0]
            return result

    monkeypatch.setattr(
        "gui.excel_category_dialog.ExcelCategorySelectionDialog",
        FakeDialog,
    )
    monkeypatch.setattr(
        "gui.main_window.QFileDialog.getSaveFileName",
        lambda *args: (str(output), "Excel (*.xlsx)"),
    )

    exported = {}

    def export(products, filename):
        exported["products"] = list(products)
        exported["filename"] = filename

    monkeypatch.setattr(ExcelExporter, "export", export)

    window = MainWindow.__new__(MainWindow)
    window.all_products = products
    window.selected_categories = {"Antiestres", "Escritorios"}
    window.stock_only = True
    window.search_box = QLineEdit()

    MainWindow.export_catalog(window)

    assert calls["categories"] == {
        "Antiestres",
        "Escritorios",
        "Bolsas / Mochilas",
    }
    assert calls["initial_selected"] == {"Antiestres", "Escritorios"}
    assert calls["stock_only"] is True
    assert callable(calls["on_export"])
    assert [product.code for product in exported["products"]] == [
        "A-100",
        "A-101",
    ]
    assert exported["filename"] == str(output)
    dialog_ref["instance"] = None
    window.search_box.deleteLater()
    app.processEvents()


def test_main_window_export_selected_format_uses_selected_products(
    monkeypatch,
    tmp_path,
):
    from exporters.csv_exporter import CSVExporter
    from gui.main_window import MainWindow

    output = tmp_path / "catalogo.csv"
    products = [Product(code="A-100", name="Producto")]
    calls = {}

    class FakeFileDialog:
        @staticmethod
        def getSaveFileName(*args):
            del args
            return str(output), "CSV (*.csv)"

    monkeypatch.setattr("gui.main_window.QFileDialog", FakeFileDialog)

    def export(selected_products, filename):
        calls["products"] = list(selected_products)
        calls["filename"] = filename

    monkeypatch.setattr(CSVExporter, "export", export)

    window = MainWindow.__new__(MainWindow)

    assert window._export_selected_format("csv", products) is True
    assert calls == {
        "products": products,
        "filename": str(output),
    }
