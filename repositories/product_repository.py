import json
import re
import sqlite3
from typing import cast

from database.db_manager import DBManager
from models.product import Product


class ProductRepository:
    _INVALID_COLOR_MARKERS = (
        "var acss",
        "sourceurl=",
        "sourceurl:",
        "javascript",
        "color_mode",
        "enable_client_color_preference",
    )

    def __init__(self, db: DBManager | None = None) -> None:
        self.db = db or DBManager()

    def create(self, product: Product) -> Product:
        query = """
        INSERT INTO products
        (
            code, name, category, description, price,
            price_sample, price_hundred, price_thousand, stock,
            color_stock, image_url, image_path,
            image_hash, gallery_images, content_hash
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        cursor = self.db.execute_query(
            query,
            (
                product.code,
                product.name,
                product.category,
                product.description,
                product.price,
                product.price_sample,
                product.price_hundred,
                product.price_thousand,
                product.stock,
                json.dumps(
                    self._clean_color_stock(product.color_stock),
                    ensure_ascii=False,
                ),
                product.image_url,
                product.image_path,
                product.image_hash,
                json.dumps(
                    self._clean_gallery_images(product.gallery_images),
                    ensure_ascii=False,
                ),
                product.content_hash,
            ),
        )
        product.product_id = cursor.lastrowid
        return product

    def update(self, product: Product) -> Product:
        query = """
        UPDATE products SET
            code=?, name=?, category=?, description=?, price=?,
            price_sample=?, price_hundred=?, price_thousand=?, stock=?,
            color_stock=?, image_url=?, image_path=?,
            image_hash=?, gallery_images=?, content_hash=?
        WHERE id=?
        """
        self.db.execute_query(
            query,
            (
                product.code,
                product.name,
                product.category,
                product.description,
                product.price,
                product.price_sample,
                product.price_hundred,
                product.price_thousand,
                product.stock,
                json.dumps(
                    self._clean_color_stock(product.color_stock),
                    ensure_ascii=False,
                ),
                product.image_url,
                product.image_path,
                product.image_hash,
                json.dumps(
                    self._clean_gallery_images(product.gallery_images),
                    ensure_ascii=False,
                ),
                product.content_hash,
                product.product_id,
            ),
        )
        return product

    def save(self, product: Product) -> Product:
        existing = self.get_by_code(product.code)
        return self.save_with_existing(product, existing)

    def save_with_existing(
        self,
        product: Product,
        existing: Product | None = None,
    ) -> Product:
        """Persiste un producto reutilizando una búsqueda ya realizada."""
        if existing is not None:
            product.product_id = existing.product_id
            return self.update(product)
        return self.create(product)

    def sync_product_categories(
        self,
        product_id: int,
        category_value: str,
    ) -> None:
        """Synchronize normalized product-category links with its text field."""
        from services.scraping.category_name_normalizer import (
            normalize_category_name,
            split_category_names,
        )

        categories = split_category_names(category_value)
        existing_categories = self.db.fetch_all(
            "SELECT id, name FROM categories"
        )
        self.db.execute_query(
            "DELETE FROM product_categories WHERE product_id=?",
            (product_id,),
        )
        for category in categories:
            row = next(
                (
                    existing
                    for existing in existing_categories
                    if normalize_category_name(str(existing["name"] or ""))
                    == normalize_category_name(category)
                ),
                None,
            )
            if row is None:
                key = (
                    category.casefold()
                    .replace(" ", "-")
                    .replace("/", "-")
                    .replace(",", "")
                )
                canonical_url = f"manual://category/{key}"
                self.db.execute_query(
                    "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
                    (category, canonical_url),
                )
                row = self.db.fetch_one(
                    "SELECT id FROM categories WHERE name=?",
                    (category,),
                )
            if row is None:
                raise RuntimeError(
                    f"No se pudo crear la categoría {category!r}."
                )
            self.db.execute_query(
                "INSERT OR IGNORE INTO product_categories "
                "(product_id, category_id) VALUES (?, ?)",
                (product_id, row["id"]),
            )

    def get_by_code(self, code: str) -> Product | None:
        row = self.db.fetch_one(
            "SELECT * FROM products WHERE code = ? COLLATE NOCASE",
            (code,),
        )
        return self._row_to_product(row) if row else None

    def get(self, code: str) -> Product | None:
        return self.get_by_code(code)

    def get_by_codes(self, codes: list[str]) -> dict[str, Product]:
        """Carga múltiples productos con una sola consulta por lote."""
        normalized = list(
            dict.fromkeys(
                str(code).strip()
                for code in (codes or [])
                if str(code).strip()
            )
        )
        if not normalized:
            return {}

        result: dict[str, Product] = {}
        for start in range(0, len(normalized), 500):
            batch = normalized[start : start + 500]
            placeholders = ", ".join("?" for _ in batch)
            rows = self.db.fetch_all(
                "SELECT * FROM products "
                f"WHERE code COLLATE NOCASE IN ({placeholders})",
                tuple(batch),
            )
            for row in rows:
                product = self._row_to_product(row)
                result[str(product.code).strip().casefold()] = product
        return result

    def next_product_code(self, prefix: str = "FB") -> str:
        """Generate the next unused catalog code for manually created products."""
        normalized_prefix = str(prefix or "FB").strip().upper() or "FB"
        rows = self.db.fetch_all(
            "SELECT code FROM products WHERE code LIKE ? COLLATE NOCASE",
            (f"{normalized_prefix}-%",),
        )
        pattern = re.compile(rf"^{re.escape(normalized_prefix)}-(\d+)$", re.IGNORECASE)
        maximum = 0
        for row in rows:
            match = pattern.fullmatch(str(row["code"] or "").strip())
            if match:
                maximum = max(maximum, int(match.group(1)))
        return f"{normalized_prefix}-{maximum + 1:04d}"

    def get_by_id(self, product_id: int) -> Product | None:
        rows = self.db.fetch_all(
            "SELECT * FROM products WHERE id=?",
            (product_id,),
        )
        return self._row_to_product(rows[0]) if rows else None

    def get_all(self) -> list[Product]:
        rows = self.db.fetch_all(
            "SELECT * FROM products ORDER BY id DESC",
        )
        return [self._row_to_product(row) for row in rows]

    def search(self, text: str) -> list[Product]:
        value = f"%{text}%"
        rows = self.db.fetch_all(
            """
            SELECT * FROM products
            WHERE code LIKE ? OR name LIKE ? OR category LIKE ?
            ORDER BY id DESC
            """,
            (value, value, value),
        )
        return [self._row_to_product(row) for row in rows]

    def delete(self, product_id: int) -> None:
        self.db.execute_query(
            "DELETE FROM products WHERE id=?",
            (product_id,),
        )

    def rename_category(self, category_name: str, new_name: str) -> int:
        """Rename a category while preserving product-category relationships."""
        from services.scraping.category_name_normalizer import (
            normalize_category_name,
            split_category_names,
        )

        old_key = normalize_category_name(category_name)
        new_value = str(new_name or "").strip()
        new_key = normalize_category_name(new_value)
        if not old_key:
            raise ValueError("La categoría actual no es válida.")
        if not new_key:
            raise ValueError("El nuevo nombre de categoría es obligatorio.")
        if old_key == new_key:
            return 0

        rows = self.db.fetch_all("SELECT id, name FROM categories")
        target_ids = [
            int(row["id"])
            for row in rows
            if normalize_category_name(str(row["name"] or "")) == old_key
        ]
        if not target_ids:
            raise ValueError("La categoría seleccionada ya no existe.")

        if any(
            normalize_category_name(str(row["name"] or "")) == new_key
            and int(row["id"]) not in target_ids
            for row in rows
        ):
            raise ValueError("Ya existe una categoría con ese nombre.")

        products = self.db.fetch_all("SELECT id, category FROM products")
        affected = 0

        self.db.begin()
        try:
            for row in products:
                categories = split_category_names(row["category"])
                replaced: list[str] = []
                changed = False
                for category in categories:
                    if normalize_category_name(category) == old_key:
                        replacement = new_value
                        changed = True
                    else:
                        replacement = category
                    if replacement.casefold() not in {
                        value.casefold() for value in replaced
                    }:
                        replaced.append(replacement)
                if changed:
                    self.db.execute_query(
                        "UPDATE products SET category=? WHERE id=?",
                        (", ".join(replaced), row["id"]),
                    )
                    affected += 1

            placeholders = ", ".join("?" for _ in target_ids)
            self.db.execute_query(
                "UPDATE categories SET name=? "
                f"WHERE id IN ({placeholders})",
                (new_value, *target_ids),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return affected

    def delete_category(self, category_name: str) -> int:
        """Quita una categoría de los productos sin borrar su historial."""
        from services.scraping.category_name_normalizer import (
            normalize_category_name,
            split_category_names,
        )

        target = normalize_category_name(category_name)
        if not target:
            return 0

        category_ids = {
            int(row["id"])
            for row in self.db.fetch_all("SELECT id, name FROM categories")
            if normalize_category_name(str(row["name"] or "")) == target
        }
        products = self.db.fetch_all("SELECT id, category FROM products")
        affected = 0

        self.db.begin()
        try:
            if category_ids:
                placeholders = ", ".join("?" for _ in category_ids)
                self.db.execute_query(
                    "DELETE FROM product_categories "
                    f"WHERE category_id IN ({placeholders})",
                    tuple(sorted(category_ids)),
                )

            for row in products:
                current = split_category_names(row["category"])
                remaining = [
                    category
                    for category in current
                    if normalize_category_name(category) != target
                ]
                if len(remaining) == len(current):
                    continue
                next_category = ", ".join(remaining)
                self.db.execute_query(
                    "UPDATE products SET category=? WHERE id=?",
                    (next_category, row["id"]),
                )
                affected += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return affected

    def delete_by_code(self, code: str) -> None:
        """Elimina un producto identificado por su código, ignorando mayúsculas."""
        self.db.execute_query(
            "DELETE FROM products WHERE code = ? COLLATE NOCASE",
            (code,),
        )

    @classmethod
    def _is_valid_color_name(cls, value: str) -> bool:
        if not value or len(value) > 80:
            return False
        folded = value.casefold()
        if folded in {
            "color",
            "colour",
            "colores",
            "seleccionar color",
            "choose an option",
        }:
            return False
        if any(marker in folded for marker in cls._INVALID_COLOR_MARKERS):
            return False
        if any(token in value for token in ("{", "}", ";", "//", "=>")):
            return False
        return not re.fullmatch(r"[\d\s.,:+-]+", value)

    @classmethod
    def _json_dict(cls, value) -> dict[str, int]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        result: dict[str, int] = {}
        for key, stock in parsed.items():
            try:
                normalized = re.sub(r"\s+", " ", str(key)).strip(" .:-|")
                if not cls._is_valid_color_name(normalized):
                    continue
                result[normalized] = max(int(stock), 0)
            except (TypeError, ValueError):
                continue
        return result

    @classmethod
    def _clean_gallery_images(
        cls,
        gallery_images: list[dict[str, object]] | None,
    ) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        seen: set[str] = set()
        for position, image in enumerate(list(gallery_images or []), start=1):
            if not isinstance(image, dict):
                continue
            url = str(image.get("url", "") or "").strip()
            path = str(
                image.get("image_path", image.get("path", "")) or ""
            ).strip()
            identity = url.casefold() if url else path.casefold()
            if not path or not identity or identity in seen:
                continue
            seen.add(identity)
            result.append(
                {
                    "url": url,
                    "image_path": path,
                    "image_hash": str(
                        image.get("image_hash", image.get("hash", "")) or ""
                    ),
                    "position": cls._int_value(
                        image.get("position"),
                        position,
                    ),
                    "source": str(image.get("source", "gallery") or "gallery"),
                }
            )
        return result

    @staticmethod
    def _int_value(value: object, default: int) -> int:
        if value in (None, ""):
            return default
        try:
            return int(cast("str | int | float", value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _json_gallery_images(cls, value) -> list[dict[str, object]]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return cls._clean_gallery_images(parsed)

    @classmethod
    def _clean_color_stock(
        cls,
        color_stock: dict[str, int] | None,
    ) -> dict[str, int]:
        if not color_stock:
            return {}
        return cls._json_dict(json.dumps(color_stock, ensure_ascii=False))

    def _row_to_product(self, row: sqlite3.Row) -> Product:
        color_stock = self._json_dict(row["color_stock"])
        stock = max(int(row["stock"] or 0), 0)
        return Product(
            product_id=row["id"],
            code=row["code"],
            name=row["name"],
            price=row["price"],
            category=row["category"],
            description=row["description"],
            price_sample=row["price_sample"],
            price_hundred=row["price_hundred"],
            price_thousand=row["price_thousand"],
            stock=stock,
            color_stock=color_stock,
            image_url=row["image_url"],
            image_path=row["image_path"],
            image_hash=row["image_hash"],
            gallery_images=self._json_gallery_images(row["gallery_images"]),
            content_hash=row["content_hash"],
        )

