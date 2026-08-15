from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite ejecutar el archivo directamente desde la raíz del proyecto:
# ``python tools/audit_images.py``.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from services.scraping.image_audit_service import ImageAuditService

    parser = argparse.ArgumentParser(
        description="Audita y limpia duplicados de imágenes."
    )
    parser.add_argument("--root", default="data/images/products")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Elimina duplicados byte-a-byte.",
    )
    args = parser.parse_args()

    service = ImageAuditService(args.root)
    report = service.remove_duplicates() if args.clean else service.audit()

    print(f"Directorio: {report['root']}")
    print(f"Archivos: {report['files']}")
    print(f"Hashes únicos: {report['unique_hashes']}")
    print(f"Grupos duplicados: {report['duplicate_groups']}")
    print(f"Archivos duplicados: {report['duplicate_files']}")
    for paths in report["duplicates"]:
        print("  - " + " | ".join(paths))
    if args.clean:
        print(f"Eliminados: {len(report['removed'])}")


if __name__ == "__main__":
    main()
