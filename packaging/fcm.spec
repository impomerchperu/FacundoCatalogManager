from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.config import CONF

ROOT = Path.cwd()
DIST_NAME = "FacundoCatalogManager"
SCHEMA = ROOT / "database" / "schema.sql"
APP_ICON = ROOT / "resources" / "facundo.ico"
SEED_ROOT = ROOT / "build" / "WindowsSeed"
SEED_DATABASE = SEED_ROOT / "database" / "catalog.db"
SEED_IMAGES = SEED_ROOT / "data" / "images"

if not SCHEMA.is_file():
    raise RuntimeError(f"No se encontró el esquema SQLite: {SCHEMA}")
if not APP_ICON.is_file():
    raise RuntimeError(f"No se encontró el icono de la aplicación: {APP_ICON}")
if not SEED_DATABASE.is_file():
    raise RuntimeError(
        f"No se encontró la base semilla preparada: {SEED_DATABASE}"
    )
if not SEED_IMAGES.is_dir():
    raise RuntimeError(
        f"No se encontró el directorio de imágenes semilla: {SEED_IMAGES}"
    )

DIST_PATH = ROOT / "dist" / "Windows"
WORK_PATH = ROOT / "build" / "Windows"

DIST_PATH.mkdir(parents=True, exist_ok=True)
WORK_PATH.mkdir(parents=True, exist_ok=True)

CONF["distpath"] = str(DIST_PATH)
CONF["workpath"] = str(WORK_PATH)
CONF["specpath"] = str(ROOT / "packaging")

analysis = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(SCHEMA), "database"),
        (str(APP_ICON), "resources"),
        (str(SEED_DATABASE), "seed/database"),
        (str(SEED_IMAGES), "seed/data/images"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name=DIST_NAME,
    icon=str(APP_ICON),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name=DIST_NAME,
)
