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
