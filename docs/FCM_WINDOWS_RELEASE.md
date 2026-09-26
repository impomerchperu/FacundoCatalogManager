# FCM — Release Windows

## Objetivo

Preparar una distribución reproducible de Facundo Catalog Manager para Windows sin almacenar datos modificables dentro del bundle interno de PyInstaller.

## Arquitectura

El ejecutable se construye como **one-dir** con PyInstaller.

El código y los recursos de solo lectura quedan dentro de la instalación. El bundle también contiene una semilla validada del catálogo actual y sus imágenes, preparada durante el build. El almacenamiento persistente de usuario queda en:

`%LOCALAPPDATA%\FacundoCatalogManager\`

Dentro de ese directorio se mantienen:

- `database/catalog.db`
- `data/images/products`
- `logs/fcm.log`

En desarrollo normal, `DATA_DIR` continúa siendo la raíz del proyecto.

## Herramientas

- Python 3.14.
- PyInstaller 6.22.3.
- Inno Setup 7.

PyInstaller 6.15.0 incorporó soporte para Python 3.14; el proyecto fija PyInstaller 6.22.3 en `requirements-build.txt`.

## Versionado

La versión de la aplicación se mantiene en `VERSION` con formato `MAJOR.MINOR.PATCH`. El script de build y el workflow de Windows leen ese archivo; el instalador recibe la misma versión como definición del preprocesador de Inno Setup.

## Semilla inicial

Antes de ejecutar PyInstaller, el build ejecuta `tools/prepare_windows_seed.py`. Esta utilidad valida la base de desarrollo contra la referencia `24 / 523 / 519 / 4`, comprueba la integridad de SQLite y la existencia de las imágenes referenciadas, y genera una copia mediante la API de backup de SQLite para evitar pérdidas de páginas WAL. La semilla resultante se incorpora al bundle en un directorio de solo lectura.

En el primer arranque congelado, `CatalogSeedService` copia la base semilla y `data/images` a `%LOCALAPPDATA%\\FacundoCatalogManager` solo cuando no existe un catálogo útil. Si ya hay productos o historial, no sustituye la información del usuario.

## Build

Desde PowerShell en la raíz del repositorio:

```powershell
.\scripts\build_windows.ps1 -SkipInstaller
```

Genera:

`dist\Windows\FacundoCatalogManager\FacundoCatalogManager.exe`

Para generar también el instalador:

```powershell
.\scripts\build_windows.ps1
```

El instalador generado es:

`dist\Windows\FacundoCatalogManager-0.1.0-setup.exe`

Inno Setup 7 puede instalarse con:

```powershell
winget install --id JRSoftware.InnoSetup.7 -e -s winget -i
```

## Datos de usuario

Cuando la aplicación está congelada, `config.runtime_paths` dirige la base, imágenes y logs a `%LOCALAPPDATA%\FacundoCatalogManager`.

El instalador utiliza esa misma carpeta como destino. De esta forma, el ejecutable puede actualizarse sin reemplazar el catálogo persistido por una copia del bundle.

Las rutas de imagen almacenadas en SQLite conservan el formato relativo `data/images/...`; la GUI las resuelve contra `DATA_DIR`.

## Checklist previo a release

- [x] Ruff.
- [x] Pyright.
- [x] Pytest.
- [x] Build PyInstaller en Windows.
- [ ] Ejecutar bundle en una máquina Windows sin Python instalado.
- [x] Confirmar creación/lectura de `database/catalog.db` en `%LOCALAPPDATA%\FacundoCatalogManager`.
- [ ] Confirmar imágenes en `data/images/products` después de la instalación.
- [x] Confirmar que `_internal` no recibe datos modificables.
- [x] Confirmar arranque y carga del catálogo.
- [x] Confirmar búsqueda y filtros.
- [ ] Confirmar actualización del catálogo.
- [x] Confirmar historial.
- [x] Confirmar Excel/PDF/CSV.
- [x] Confirmar cierre limpio.
- [ ] Ejecutar instalador.
- [ ] Confirmar actualización conservando datos existentes.
- [ ] Confirmar desinstalación sin pérdida involuntaria del catálogo.
- [x] Implementar backup/restauración de `catalog.db` y cubrirlo con pruebas automatizadas.
- [ ] Validar el procedimiento sobre una base real de usuario antes de release.
- [ ] Actualizar versión antes de una release.

## Estado

La arquitectura, el spec de PyInstaller, el instalador y el procedimiento de semilla están en el repositorio. El bundle fue producido y validado funcionalmente en Windows con la referencia `523 / 519 / 4`, `519` productos locales, `519` imágenes, historial persistente y cierre limpio. Todavía falta generar y validar el instalador, probar actualización/desinstalación sobre una instalación real y cerrar la validación del procedimiento backup/restore con una base real.
