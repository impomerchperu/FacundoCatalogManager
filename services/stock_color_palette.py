from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock
from typing import Any

from bs4 import Tag

from config.runtime_paths import resolve_data_path

# Indicator values seen in the site's inline CSS on its 24 category pages
# come from `.variaciones-producto[title]` `background-color` declarations.
# Names absent from those swatches retain the curated fallback below.
FALLBACK_STOCK_COLOR_STYLES: dict[str, tuple[str, str]] = {
    "amarillo": ("#fff7d6", "#ffff00"),
    "amarillo fluorescente": ("#f5ffd1", "#efff00"),
    "amarillo flurecente": ("#f5ffd1", "#efff00"),
    "amarillo neon": ("#f5ffd1", "#efff00"),
    "amarillo neón": ("#f5ffd1", "#efff00"),
    "azul": ("#e7f1ff", "#1400f4"),
    "azul claro": ("#e3f1ff", "#1e73be"),
    "azul marino": ("#e1e8f7", "#123b6d"),
    "azul oscuro": ("#dfe7ff", "#1a2fad"),
    "azulino": ("#e3ebff", "#4f64d8"),
    "azulino full": ("#e0e6ff", "#3046ff"),
    "azul full": ("#e0e6ff", "#0057ff"),
    "azul rey": ("#e1eaff", "#1747e5"),
    "azul electrico": ("#e0f0ff", "#0077ff"),
    "azul eléctrico": ("#e0f0ff", "#0077ff"),
    "azul petroleo": ("#e0f2f3", "#006b73"),
    "azul petróleo": ("#e0f2f3", "#006b73"),
    "bamboo": ("#f3ead6", "#ddc690"),
    "black": ("#ececec", "#1a1a1a"),
    "blanco": ("#f6f8fa", "#ffffff"),
    "brillante": ("#eef4fa", "#2d2d2d"),
    "celeste": ("#e7f7ff", "#00bfff"),
    "champagne": ("#fff3df", "#e7cfa1"),
    "crema": ("#fff9e8", "#ffe0ab"),
    "cyan": ("#ddfbff", "#00a9c7"),
    "dorado": ("#fff4cc", "#efb810"),
    "oro": ("#fff4cc", "#efb810"),
    "fucsia": ("#ffe1f1", "#ee038c"),
    "fuchsia": ("#ffe1f1", "#ee038c"),
    "gris": ("#f0f3f6", "#808080"),
    "gris gun": ("#e9edf1", "#2c353a"),
    "gun": ("#e9edf1", "#606a75"),
    "kraft": ("#f2e5d5", "#dd9933"),
    "lila": ("#f0e7ff", "#ddb6e3"),
    "lila pastel": ("#f3edff", "#bfa7db"),
    "magenta": ("#ffe0f5", "#d600a9"),
    "manila": ("#fff4d0", "#ffb442"),
    "marron": ("#f3e8dd", "#804000"),
    "marrón": ("#f3e8dd", "#804000"),
    "mate": ("#e8eaed", "#0a0a0a"),
    "morado": ("#f1e9ff", "#9b51e0"),
    "naranja": ("#fff0df", "#ff4f14"),
    "naranja full": ("#ffe9d2", "#ff7a00"),
    "natural": ("#f3eadc", "#ffecce"),
    "negro": ("#edf0f3", "#0a0a0a"),
    "negro full": ("#e6e7e9", "#111111"),
    "acero inoxidable": ("#f1f3f5", "#dddddd"),
    "pavonado": ("#ffffff", "#e3e4e5"),
    "plateado": ("#f1f3f5", "#bebebe"),
    "plata": ("#f1f3f5", "#bebebe"),
    "silver": ("#f1f3f5", "#bebebe"),
    "satinado": ("#ffffff", "#ffffff"),
    "transparente": ("#ffffff", "#e5e5e5"),
    "trigo": ("#f6eed8", "#ffecce"),
    "rojo": ("#ffe8e8", "#eb5757"),
    "rojo full": ("#ffdddd", "#ff1f1f"),
    "rosado": ("#ffeaf4", "#e66aa8"),
    "verde": ("#e7f6ea", "#008000"),
    "verde claro": ("#eaf8e9", "#4bed4b"),
    "verde oscuro": ("#e6f4ee", "#007c0c"),
    "verde oscuro full": ("#dff2e7", "#006b3c"),
    "verde botella": ("#e1f0e7", "#176b45"),
    "verde militar": ("#e9f0dc", "#66743a"),
    "verde agua": ("#def8f3", "#4bbfae"),
    "menta": ("#e0f8ed", "#4fba8a"),
    "verde limon": ("#efffd9", "#a8d500"),
    "verde limón": ("#efffd9", "#a8d500"),
    "verde petroleo": ("#e0f2ee", "#006b5f"),
    "verde petróleo": ("#e0f2ee", "#006b5f"),
    "yellow": ("#fff5b8", "#f2d21b"),
}
STOCK_COLOR_STYLES: dict[str, tuple[str, str]] = (
    FALLBACK_STOCK_COLOR_STYLES.copy()
)

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_PALETTE_PATH = resolve_data_path("stock_color_palette.json")
_PALETTE_BACKGROUND = "#f8fafc"


def _normalize_color_name(color: object) -> str:
    return " ".join(str(color or "").strip().casefold().split())


def _apply_published_colors(colors: dict[str, str]) -> None:
    """Overlay source CSS colors while preserving existing cell backgrounds."""
    for name, indicator in colors.items():
        normalized = _normalize_color_name(name)
        value = str(indicator or "").strip().lower()
        if not normalized or not _HEX_COLOR_PATTERN.fullmatch(value):
            continue
        existing = STOCK_COLOR_STYLES.get(normalized)
        background = existing[0] if existing else _PALETTE_BACKGROUND
        STOCK_COLOR_STYLES[normalized] = (background, value)


def _read_palette(path: Path) -> dict[str, str]:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    return {
        str(name).strip(): str(value).strip().lower()
        for name, value in stored.items()
        if str(name).strip()
        and isinstance(value, str)
        and _HEX_COLOR_PATTERN.fullmatch(value.strip())
    }


_apply_published_colors(_read_palette(_PALETTE_PATH))


class StockColorPaletteSyncService:
    """Collect published swatch CSS during category-page scraping and persist it."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else _PALETTE_PATH
        self._capture: dict[str, tuple[str, str]] = {}
        self._lock = Lock()

    def begin_run(self) -> None:
        with self._lock:
            self._capture.clear()

    def observe_category_page(self, soup: Any) -> None:
        """Read each site's inline swatch declaration once per fetched page."""
        if not hasattr(soup, "select"):
            return
        observed: dict[str, tuple[str, str]] = {}
        for node in soup.select(".variaciones-producto[title][style]"):
            if not isinstance(node, Tag):
                continue
            name = str(node.get("title") or "").strip()
            normalized = _normalize_color_name(name)
            value = self._background_color(node.get("style"))
            if normalized and value:
                observed[normalized] = (name, value)
        if observed:
            with self._lock:
                self._capture.update(observed)

    @staticmethod
    def _background_color(style: object) -> str:
        for declaration in str(style or "").split(";"):
            property_name, separator, value = declaration.partition(":")
            if (
                separator
                and property_name.strip().casefold() == "background-color"
            ):
                normalized = value.strip().lower()
                return (
                    normalized
                    if _HEX_COLOR_PATTERN.fullmatch(normalized)
                    else ""
                )
        return ""

    def finish_run(self) -> int:
        """Merge observed colors into a JSON sidecar; SQLite is not involved."""
        with self._lock:
            observed = dict(self._capture)
            self._capture.clear()
        if not observed:
            return 0

        persisted = _read_palette(self.path)
        merged = {
            _normalize_color_name(name): (name, color)
            for name, color in persisted.items()
        }
        merged.update(observed)
        serialized = {name: color for name, color in merged.values()}
        if persisted != serialized:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary_path.write_text(
                json.dumps(serialized, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        _apply_published_colors(serialized)
        return len(observed)


def known_stock_color_style(color: str) -> tuple[str, str] | None:
    normalized = _normalize_color_name(color)
    return STOCK_COLOR_STYLES.get(normalized)
