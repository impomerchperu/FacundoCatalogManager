from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.config import CONF

ROOT = Path.cwd()
DIST_NAME = "FacundoCatalogManager"
SCHEMA = ROOT / "database" / "schema.sql"

CONF["distpath"] = str(ROOT / "dist" / "Windows")
CONF["workpath"] = str(ROOT / "build" / "Windows")
CONF["specpath"] = str(ROOT / "packaging")

analysis = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(SCHEMA), "database")],
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
