param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Version = (Get-Content "VERSION" -Raw).Trim()
if ($Version -notmatch "^\d+\.\d+\.\d+$") {
    throw "VERSION debe usar el formato MAJOR.MINOR.PATCH."
}

Write-Host "== Facundo Catalog Manager / Windows build $Version =="

$PythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $PythonVersion -ne "3.14") {
    throw "Python 3.14 debe estar disponible en PATH."
}

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron instalar las dependencias del proyecto."
}

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo instalar la dependencia de build."
}

Remove-Item -Recurse -Force "build\Windows" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist\Windows" -ErrorAction SilentlyContinue

python -m tools.prepare_windows_seed --output "build\WindowsSeed"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo preparar la semilla validada del catálogo Windows."
}

python -m PyInstaller --clean --noconfirm packaging\fcm.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no pudo generar el bundle Windows."
}

$BundleExe = Join-Path $RepoRoot "dist\Windows\FacundoCatalogManager\FacundoCatalogManager.exe"
if (-not (Test-Path $BundleExe)) {
    throw "No se encontró el ejecutable esperado: $BundleExe"
}

Write-Host "Bundle generado: $BundleExe"

if ($SkipInstaller) {
    Write-Host "Instalador omitido por -SkipInstaller."
    exit 0
}

$IsccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe"
)

$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    $Command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($Command) {
        $Iscc = $Command.Source
    }
}

if (-not $Iscc) {
    throw "No se encontró Inno Setup 7. Instálalo con: winget install --id JRSoftware.InnoSetup.7 -e -s winget -i"
}

Write-Host "Inno Setup encontrado: $Iscc"

& $Iscc "/DFCM_VERSION=$Version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup no pudo generar el instalador."
}

$Installer = Join-Path $RepoRoot "dist\Windows\FacundoCatalogManager-$Version-setup.exe"
if (-not (Test-Path $Installer)) {
    throw "No se encontró el instalador esperado: $Installer"
}

Write-Host "Instalador generado: $Installer"
