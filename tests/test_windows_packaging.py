from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = PROJECT_ROOT / "packaging" / "installer.iss"
BUILD_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_windows.ps1"
SPEC_PATH = PROJECT_ROOT / "packaging" / "fcm.spec"
ICON_PATH = PROJECT_ROOT / "resources" / "facundo.ico"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_installer_uses_facundo_icon_and_persistent_install_paths():
    content = _read(INSTALLER_PATH)

    assert ICON_PATH.is_file()
    assert 'SetupIconFile=..\\resources\\facundo.ico' in content
    assert 'UninstallDisplayIcon={app}\\{#MyAppExeName}' in content
    assert r"DefaultDirName={localappdata}\Programs\FacundoCatalogManager" in content
    assert r'Source: "..\dist\Windows\FacundoCatalogManager\*"' in content


def test_windows_installer_keeps_start_menu_and_optional_desktop_shortcut():
    content = _read(INSTALLER_PATH)

    assert (
        'Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio";'
        in content
    )
    assert (
        'Name: "{autoprograms}\\{#MyAppName}"; '
        'Filename: "{app}\\{#MyAppExeName}"; WorkingDir: "{app}"'
        in content
    )
    assert (
        'Name: "{autodesktop}\\{#MyAppName}"; '
        'Filename: "{app}\\{#MyAppExeName}"; WorkingDir: "{app}"; '
        'Tasks: desktopicon'
        in content
    )


def test_windows_build_passes_version_to_inno_setup_and_validates_outputs():
    content = _read(BUILD_SCRIPT_PATH)

    assert '& $Iscc "/DFCM_VERSION=$Version" "packaging\\installer.iss"' in content
    assert (
        '$Installer = Join-Path $RepoRoot '
        '"dist\\Windows\\FacundoCatalogManager-$Version-setup.exe"'
        in content
    )
    assert 'if (-not (Test-Path $BundleExe))' in content
    assert 'if (-not (Test-Path $Installer))' in content


def test_windows_spec_embeds_application_icon():
    content = _read(SPEC_PATH)

    assert 'APP_ICON = ROOT / "resources" / "facundo.ico"' in content
    assert 'icon=str(APP_ICON)' in content
    assert '(str(APP_ICON), "resources")' in content
