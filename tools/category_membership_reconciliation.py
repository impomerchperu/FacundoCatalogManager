from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, NoReturn
from urllib.parse import urlsplit

from database.db_manager import DBManager
from repositories.product_repository import ProductRepository
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)
from services.scraping.product_hash_service import ProductHashService


def _code_identity(value: object) -> str:
    return re.sub(r"[\s-]+", "", str(value or "").strip().upper()).casefold()


def _category_url_key(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if (
        parts.scheme not in {"http", "https"}
        or (parts.hostname or "").casefold() != "stock.importacionesfacundo.com"
        or not parts.netloc
    ):
        return ""
    return (parts.scheme + "://" + parts.netloc + parts.path).rstrip("/").casefold()


def _raise_reconciliation_error(message: str) -> NoReturn:
    raise RuntimeError(message)


def _category_keys(value: object) -> set[str]:
    return {
        key
        for name in split_category_names(value)
        if (key := normalize_category_name(canonical_category_name(name)))
    }


def _relation_snapshot(
    db: DBManager,
    live_categories_by_url: dict[str, str],
) -> tuple[dict[int, set[str]], dict[int, list[str]]]:
    """Read normalized memberships, resolving renamed labels by canonical URL."""
    keys_by_product: dict[int, set[str]] = defaultdict(set)
    names_by_product: dict[int, list[str]] = defaultdict(list)
    rows = db.fetch_all(
        """
        SELECT pc.product_id, pc.category_id, c.name, c.canonical_url
        FROM product_categories AS pc
        JOIN categories AS c ON c.id = pc.category_id
        """
    )
    for row in rows:
        product_id = int(row["product_id"])
        category_key = live_categories_by_url.get(
            _category_url_key(row["canonical_url"]),
            normalize_category_name(
                canonical_category_name(str(row["name"] or ""))
            ),
        )
        if not category_key:
            continue
        keys_by_product[product_id].add(category_key)
        category_name = str(row["name"] or "").strip()
        if category_name and category_name not in names_by_product[product_id]:
            names_by_product[product_id].append(category_name)
    return dict(keys_by_product), dict(names_by_product)


def audit_live_category_memberships(  # noqa: PLR0912
    db: DBManager,
    repository: ProductRepository,
    categories: list[Any],
    *,
    collection_scraper: Any,
) -> tuple[dict[str, object], dict[str, list[Any]]]:
    """Build authoritative product-to-category membership from every live category.

    No catalog writes occur here. Membership changes are proposed only when every
    discovered category has a positive published count and its complete set of
    uniquely identified product cards has been collected.
    """
    category_names_by_key: dict[str, str] = {}
    category_urls_by_key: dict[str, str] = {}
    live_memberships: dict[str, dict[str, str]] = defaultdict(dict)
    live_product_names: dict[str, str] = {}
    live_product_codes: dict[str, str] = {}
    live_raw_by_category: dict[str, list[Any]] = {}
    coverage_issues: list[str] = []
    category_scans: list[dict[str, object]] = []
    occurrences = 0
    fetch_errors = 0

    if not categories:
        coverage_issues.append("No se descubrieron categorías live.")

    for category in categories:
        name = canonical_category_name(getattr(category, "name", ""))
        key = normalize_category_name(name)
        url_key = _category_url_key(getattr(category, "url", ""))
        expected_count = max(
            int(getattr(category, "expected_count", 0) or 0),
            0,
        )
        if not key or not url_key:
            coverage_issues.append(
                f"Categoría sin nombre o URL canónica identificable: {name!r}."
            )
            continue
        if key in category_names_by_key:
            coverage_issues.append(
                f"Categoría duplicada en el listado live: {name}."
            )
            continue
        category_names_by_key[key] = name
        category_urls_by_key[key] = url_key

        if expected_count <= 0:
            coverage_issues.append(
                f"La categoría {name} no publica un total verificable."
            )
            continue

        try:
            raw_products = collection_scraper.collect_category(category)
        except Exception as error:  # noqa: BLE001
            fetch_errors += 1
            coverage_issues.append(
                f"{name}: {type(error).__name__}: {error}"
            )
            continue

        live_raw_by_category[key] = raw_products
        actual_count = len(raw_products)
        occurrences += actual_count
        seen_in_category: set[str] = set()
        unidentified = 0
        duplicate_codes: set[str] = set()

        for item in raw_products:
            if not isinstance(item, tuple) or len(item) != 3:
                unidentified += 1
                continue
            _card, _page_url, source_product = item
            code = str(getattr(source_product, "code", "") or "").strip().upper()
            identity = _code_identity(code)
            if not identity:
                unidentified += 1
                continue
            if identity in seen_in_category:
                duplicate_codes.add(code)
                continue
            seen_in_category.add(identity)
            live_memberships[identity][key] = name
            live_product_codes.setdefault(identity, code)
            live_product_names.setdefault(
                identity,
                str(getattr(source_product, "name", "") or "").strip(),
            )

        if actual_count != expected_count:
            coverage_issues.append(
                f"{name}: el sitio publica {expected_count} productos, "
                f"pero se extrajeron {actual_count} tarjetas."
            )
        if unidentified:
            coverage_issues.append(
                f"{name}: {unidentified} tarjetas no tienen un código "
                "de producto identificable."
            )
        if duplicate_codes:
            coverage_issues.append(
                f"{name}: códigos duplicados en las tarjetas live: "
                + ", ".join(sorted(duplicate_codes, key=str.casefold))
                + "."
            )

        category_scans.append(
            {
                "category": name,
                "expected": expected_count,
                "actual": actual_count,
                "unique_codes": len(seen_in_category),
                "coverage_verified": (
                    actual_count == expected_count
                    and unidentified == 0
                    and not duplicate_codes
                ),
            }
        )

    live_by_url = {
        url: key for key, url in category_urls_by_key.items()
    }
    products = sorted(
        repository.get_all(),
        key=lambda product: str(product.code).casefold(),
    )
    products_by_identity: dict[str, Any] = {}
    duplicate_database_codes: set[str] = set()
    for product in products:
        identity = _code_identity(product.code)
        if not identity:
            coverage_issues.append(
                f"Producto local sin código identificable (id={product.product_id})."
            )
            continue
        if identity in products_by_identity:
            duplicate_database_codes.add(str(product.code))
            continue
        products_by_identity[identity] = product

    if duplicate_database_codes:
        coverage_issues.append(
            "Hay códigos locales ambiguos después de normalizarlos: "
            + ", ".join(sorted(duplicate_database_codes, key=str.casefold))
            + "."
        )

    text_categories_by_product = {
        int(product.product_id): _category_keys(product.category)
        for product in products
        if product.product_id is not None
    }
    relation_keys_by_product, relation_names_by_product = _relation_snapshot(
        db,
        live_by_url,
    )
    relation_ids_by_product: dict[int, list[int]] = defaultdict(list)
    for row in db.fetch_all(
        "SELECT product_id, category_id FROM product_categories"
    ):
        relation_ids_by_product[int(row["product_id"])].append(
            int(row["category_id"])
        )

    changed_items: list[dict[str, object]] = []
    database_multi_category_products: list[dict[str, object]] = []
    unchanged_products = 0
    products_without_live_category_membership: list[dict[str, object]] = []
    products_with_source_membership = 0
    memberships_to_add = 0
    memberships_to_remove = 0

    if not coverage_issues:
        for identity, product in products_by_identity.items():
            source_membership = live_memberships.get(identity, {})
            current_categories = sorted(
                {
                    *[
                        canonical_category_name(name)
                        for name in split_category_names(product.category)
                    ],
                    *relation_names_by_product.get(
                        int(product.product_id or 0),
                        [],
                    ),
                },
                key=str.casefold,
            )
            if source_membership:
                products_with_source_membership += 1
            else:
                products_without_live_category_membership.append(
                    {
                        "code": product.code,
                        "current_categories": current_categories,
                    }
                )

            source_keys = set(source_membership)
            source_categories = list(source_membership.values())
            product_id = int(product.product_id)
            old_text_keys = text_categories_by_product.get(product_id, set())
            old_relation_keys = relation_keys_by_product.get(product_id, set())
            old_relation_ids = sorted(
                relation_ids_by_product.get(product_id, [])
            )
            has_duplicate_or_unmapped_relations = (
                len(old_relation_ids) != len(old_relation_keys)
            )
            old_union = old_text_keys | old_relation_keys
            added = [
                name
                for key, name in source_membership.items()
                if key not in old_union
            ]
            old_names_by_key: dict[str, str] = {}
            for name in split_category_names(product.category):
                canonical = canonical_category_name(name)
                key = normalize_category_name(canonical)
                if key:
                    old_names_by_key.setdefault(key, canonical)
            for key, names in relation_names_by_product.items():
                if key == product_id:
                    for name in names:
                        canonical = canonical_category_name(name)
                        category_key = normalize_category_name(canonical)
                        if category_key:
                            old_names_by_key.setdefault(category_key, canonical)
            removed = [
                name
                for key, name in old_names_by_key.items()
                if key not in source_keys
            ]
            missing_from_category_text = [
                name
                for key, name in source_membership.items()
                if key not in old_text_keys
            ]
            missing_from_category_relation = [
                name
                for key, name in source_membership.items()
                if key not in old_relation_keys
            ]
            stale_from_category_text = [
                name
                for key, name in old_names_by_key.items()
                if key not in source_keys and key in old_text_keys
            ]
            stale_from_category_relation = [
                name
                for name in relation_names_by_product.get(product_id, [])
                if normalize_category_name(canonical_category_name(name))
                not in source_keys
            ]
            if len(old_names_by_key) > 1:
                database_multi_category_products.append(
                    {
                        "code": product.code,
                        "name": product.name,
                        "database_categories": sorted(
                            old_names_by_key.values(),
                            key=str.casefold,
                        ),
                        "source_categories": source_categories,
                    }
                )
            if (
                old_text_keys != source_keys
                or old_relation_keys != source_keys
                or has_duplicate_or_unmapped_relations
            ):
                changed_items.append(
                    {
                        "code": product.code,
                        "product_id": product_id,
                        "status": "would_update",
                        "old_category_text": str(product.category or ""),
                        "old_categories_text": sorted(
                            old_names_by_key.values(),
                            key=str.casefold,
                        ),
                        "old_categories_relation": sorted(
                            relation_names_by_product.get(product_id, []),
                            key=str.casefold,
                        ),
                        "old_category_text_keys": sorted(old_text_keys),
                        "old_category_relation_keys": sorted(old_relation_keys),
                        "old_category_relation_ids": old_relation_ids,
                        "has_duplicate_or_unmapped_relations": (
                            has_duplicate_or_unmapped_relations
                        ),
                        "source_categories": source_categories,
                        "source_category_keys": sorted(source_keys),
                        "added_categories": added,
                        "removed_categories": removed,
                        "missing_from_category_text": missing_from_category_text,
                        "missing_from_category_relation": (
                            missing_from_category_relation
                        ),
                        "stale_from_category_text": stale_from_category_text,
                        "stale_from_category_relation": (
                            stale_from_category_relation
                        ),
                        "reason": (
                            "El código no aparece en ninguna categoría live; "
                            "se retirarán sus pertenencias sin borrar el producto."
                            if not source_membership
                            else (
                                "La pertenencia se ajustará al conjunto completo de "
                                "categorías donde aparece el código en las páginas live."
                            )
                        ),
                    }
                )
                memberships_to_add += len(added)
                memberships_to_remove += len(removed)
            else:
                unchanged_products += 1

    live_products_not_in_database = [
        {
            "code": live_product_codes.get(identity, identity),
            "categories": list(memberships.values()),
        }
        for identity, memberships in live_memberships.items()
        if identity not in products_by_identity
    ]

    multi_category_products = []
    for identity, memberships in live_memberships.items():
        if len(memberships) <= 1:
            continue
        product = products_by_identity.get(identity)
        multi_category_products.append(
            {
                "code": (
                    str(product.code)
                    if product is not None
                    else live_product_codes.get(identity, identity)
                ),
                "name": (
                    str(product.name)
                    if product is not None
                    else live_product_names.get(identity, "")
                ),
                "categories": list(memberships.values()),
                "in_database": product is not None,
            }
        )
    multi_category_products.sort(
        key=lambda item: str(item["code"]).casefold()
    )

    coverage_verified = not coverage_issues and len(category_scans) == len(categories)
    report: dict[str, object] = {
        "mode": "live_category_membership_audit",
        "coverage_verified": coverage_verified,
        "coverage_issues": coverage_issues,
        "fetch_errors": fetch_errors,
        "categories_scanned": len(category_scans),
        "category_scans": category_scans,
        "category_occurrences": occurrences,
        "catalog_products": len(products),
        "products_with_source_membership": products_with_source_membership,
        "products_without_live_category_membership": (
            products_without_live_category_membership
        ),
        "live_products_not_in_database": live_products_not_in_database,
        "database_multi_category_products": database_multi_category_products,
        "live_multi_category_products": multi_category_products,
        "products_with_membership_changes": len(changed_items),
        "memberships_to_add": memberships_to_add,
        "memberships_to_remove": memberships_to_remove,
        "unchanged_products": unchanged_products,
        "items": changed_items,
        "applied": False,
        "updated_products": 0,
    }
    return report, live_raw_by_category


def _ensure_live_category_rows(
    db: DBManager,
    categories: list[Any],
) -> dict[str, int]:
    """Resolve live categories to stable database IDs without duplicating names."""
    now = datetime.now(timezone.utc).isoformat()
    rows = db.fetch_all("SELECT id, name, canonical_url FROM categories")
    ids_by_url = {
        _category_url_key(row["canonical_url"]): int(row["id"])
        for row in rows
        if _category_url_key(row["canonical_url"])
    }
    rows_by_name: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        key = normalize_category_name(
            canonical_category_name(str(row["name"] or ""))
        )
        if key:
            rows_by_name[key].append(row)

    category_ids: dict[str, int] = {}
    for category in categories:
        name = canonical_category_name(getattr(category, "name", ""))
        key = normalize_category_name(name)
        url = _category_url_key(getattr(category, "url", ""))
        expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
        if not key or not url:
            raise RuntimeError(
                f"No se puede persistir la categoría live {name!r}."
            )

        category_id = ids_by_url.get(url)
        if category_id is None:
            same_name = rows_by_name.get(key, [])
            if len(same_name) > 1:
                raise RuntimeError(
                    f"La categoría {name!r} tiene varias filas locales ambiguas."
                )
            if same_name:
                category_id = int(same_name[0]["id"])
                db.execute_query(
                    """
                    UPDATE categories
                    SET name=?, canonical_url=?, expected_count=?,
                        last_scraped_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (name, url, expected, now, now, category_id),
                )
            else:
                db.execute_query(
                    """
                    INSERT INTO categories
                        (name, canonical_url, expected_count, last_scraped_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, url, expected, now, now),
                )
                row = db.fetch_one(
                    "SELECT id FROM categories WHERE canonical_url=?",
                    (url,),
                )
                if row is None:
                    raise RuntimeError(
                        f"No se pudo crear la categoría {name!r}."
                    )
                category_id = int(row["id"])
        else:
            db.execute_query(
                """
                UPDATE categories
                SET name=?, expected_count=?, last_scraped_at=?, updated_at=?
                WHERE id=?
                """,
                (name, expected, now, now, category_id),
            )

        category_ids[key] = category_id

    return category_ids


def apply_live_category_membership_reconciliation(  # noqa: PLR0912
    db: DBManager,
    repository: ProductRepository,
    audit_report: dict[str, object],
    categories: list[Any],
) -> dict[str, int]:
    """Apply a complete, prevalidated membership plan in one SQLite transaction."""
    if audit_report.get("coverage_verified") is not True:
        raise ValueError(
            "No se pueden reconciliar categorías sin cobertura live completa."
        )

    raw_items = audit_report.get("items", [])
    if not isinstance(raw_items, list):
        raise TypeError("El informe de categorías no contiene una lista válida.")

    pending = [
        item
        for item in raw_items
        if isinstance(item, dict)
        and item.get("status") == "would_update"
    ]
    if not pending:
        audit_report["applied"] = True
        audit_report["updated_products"] = 0
        audit_report["memberships_added"] = 0
        audit_report["memberships_removed"] = 0
        return {
            "updated_products": 0,
            "memberships_added": 0,
            "memberships_removed": 0,
        }

    db.begin()
    try:
        category_ids = _ensure_live_category_rows(db, categories)
        hash_service = ProductHashService()
        now = datetime.now(timezone.utc).isoformat()
        memberships_added = 0
        memberships_removed = 0

        for item in pending:
            code = str(item.get("code") or "")
            current = repository.get_by_code(code)
            expected_id = int(item.get("product_id") or 0)
            if (
                current is None
                or current.product_id != expected_id
                or str(current.category or "") != str(
                    item.get("old_category_text") or ""
                )
            ):
                _raise_reconciliation_error(
                    f"{code}: el producto cambió desde la auditoría; "
                    "se revirtió la reconciliación completa."
                )

            current_relation_ids = sorted(
                int(row["category_id"])
                for row in db.fetch_all(
                    "SELECT category_id FROM product_categories WHERE product_id=?",
                    (expected_id,),
                )
            )
            if current_relation_ids != list(
                item.get("old_category_relation_ids") or []
            ):
                _raise_reconciliation_error(
                    f"{code}: cambiaron las relaciones de categoría desde la "
                    "auditoría; se revirtió la reconciliación completa."
                )

            source_categories = [
                canonical_category_name(str(name))
                for name in item.get("source_categories", [])
                if normalize_category_name(canonical_category_name(str(name)))
            ]
            source_keys = {
                normalize_category_name(name) for name in source_categories
            }
            desired_ids = {
                category_ids[key]
                for key in source_keys
                if key in category_ids
            }
            if len(desired_ids) != len(source_keys):
                _raise_reconciliation_error(
                    f"{code}: falta resolver una categoría live en la base de datos."
                )

            current.category = ", ".join(source_categories)
            new_hash = hash_service.generate(current)
            db.execute_query(
                "UPDATE products SET category=?, content_hash=? WHERE id=?",
                (current.category, new_hash, expected_id),
            )

            existing_ids = {
                int(row["category_id"])
                for row in db.fetch_all(
                    "SELECT category_id FROM product_categories WHERE product_id=?",
                    (expected_id,),
                )
            }
            to_remove = existing_ids - desired_ids
            for category_id in to_remove:
                db.execute_query(
                    "DELETE FROM product_categories "
                    "WHERE product_id=? AND category_id=?",
                    (expected_id, category_id),
                )
            for category_id in desired_ids:
                db.execute_query(
                    """
                    INSERT INTO product_categories
                        (product_id, category_id, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id, category_id) DO UPDATE SET
                        last_seen_at=excluded.last_seen_at
                    """,
                    (expected_id, category_id, now, now),
                )

            stored_product = repository.get_by_code(code)
            stored_relation_ids = {
                int(row["category_id"])
                for row in db.fetch_all(
                    "SELECT category_id FROM product_categories WHERE product_id=?",
                    (expected_id,),
                )
            }
            if (
                stored_product is None
                or _category_keys(stored_product.category) != source_keys
                or stored_relation_ids != desired_ids
            ):
                _raise_reconciliation_error(
                    f"{code}: la verificación posterior de categorías no coincide "
                    "con la fuente live; se revirtió la reconciliación completa."
                )

            memberships_added += int(item.get("memberships_added") or len(
                item.get("added_categories") or []
            ))
            memberships_removed += int(item.get("memberships_removed") or len(
                item.get("removed_categories") or []
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise

    for item in pending:
        item["status"] = "updated"

    updated_products = len(pending)
    audit_report["applied"] = True
    audit_report["updated_products"] = updated_products
    audit_report["memberships_added"] = memberships_added
    audit_report["memberships_removed"] = memberships_removed
    for item in pending:
        item["status"] = "updated"
    return {
        "updated_products": updated_products,
        "memberships_added": memberships_added,
        "memberships_removed": memberships_removed,
    }
