from __future__ import annotations

import argparse
import sys

from pathlib import Path

# Permite ejecutar el archivo directamente desde la raíz del proyecto:
# `python tools/audit_images.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR
    from services.scraping.image_audit_service import ImageAuditService

    parser = argparse.ArgumentParser(
        description="Audita duplicados de imágenes sin borrar archivos."
    )
    parser.add_argument(
        "--root",
        default=IMAGE_PRODUCTS_DIR.as_posix(),
        help="Directorio de imágenes a auditar.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Obsoleto: la limpieza física está deshabilitada.",
    )
    args = parser.parse_args()

    service = ImageAuditService(args.root)
    if args.clean:
        raise RuntimeError(
            "La limpieza destructiva de imágenes está deshabilitada; "
            "use la sincronización normalizada del catálogo."
        )

    report = service.audit()

    print(f"Directorio: {report['root']}")
    print(f"Archivos: {report['files']}")
    print(f"Hashes únicos: {report['unique_hashes']}")
    print(f"Grupos duplicados: {report['duplicate_groups']}")
    print(f"Archivos duplicados: {report['duplicate_files']}")
    for paths in report["duplicates"]:
        print("  - " + " | ".join(paths))


if __name__ == "__main__":
    main()
