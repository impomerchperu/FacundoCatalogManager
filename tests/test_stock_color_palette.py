import json

from bs4 import BeautifulSoup

from services.stock_color_palette import (
    STOCK_COLOR_STYLES,
    StockColorPaletteSyncService,
    known_stock_color_style,
)


def test_palette_sync_reads_published_css_once_and_persists_json(tmp_path, monkeypatch):
    key = "test source orange"
    monkeypatch.setitem(STOCK_COLOR_STYLES, key, ("#ffffff", "#000000"))
    sync = StockColorPaletteSyncService(tmp_path / "stock_color_palette.json")
    sync.begin_run()
    sync.observe_category_page(BeautifulSoup(
        """
        <div class="variaciones-producto" title="Test Source Orange"
             style="border: 1px solid black; background-color: #FfB442"></div>
        <div class="variaciones-producto" title="Ignored"
             style="color: red"></div>
        <div class="variaciones-producto" title="Invalid"
             style="background-color: url(javascript:bad)"></div>
        """,
        "html.parser",
    ))

    assert sync.finish_run() == 1
    persisted = json.loads(
        (tmp_path / "stock_color_palette.json").read_text(encoding="utf-8"),
    )
    assert persisted == {"Test Source Orange": "#ffb442"}
    assert known_stock_color_style("test source orange") == (
        "#ffffff",
        "#ffb442",
    )


def test_palette_sync_merges_across_pages_and_keeps_previous_values(tmp_path):
    path = tmp_path / "stock_color_palette.json"
    path.write_text('{"Existing": "#123456"}\n', encoding="utf-8")
    sync = StockColorPaletteSyncService(path)
    sync.begin_run()
    for name, color in (("New One", "#aabbcc"), ("New Two", "#112233")):
        sync.observe_category_page(BeautifulSoup(
            f'<i class="variaciones-producto" title="{name}" '
            f'style="background-color:{color}"></i>',
            "html.parser",
        ))

    assert sync.finish_run() == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "Existing": "#123456",
        "New One": "#aabbcc",
        "New Two": "#112233",
    }


def test_palette_sync_does_not_replace_saved_values_when_no_swatches(tmp_path):
    path = tmp_path / "stock_color_palette.json"
    original = '{"Existing": "#123456"}\n'
    path.write_text(original, encoding="utf-8")
    sync = StockColorPaletteSyncService(path)
    sync.begin_run()

    assert sync.finish_run() == 0
    assert path.read_text(encoding="utf-8") == original
