# FCM — Release Windows

## Objetivo

Preparar una distribución reproducible de Facundo Catalog Manager para Windows sin almacenar datos modificables dentro del bundle interno de PyInstaller.

## Arquitectura

El ejecutable se construye como **one-dir** con PyInstaller.

El código y los recursos de solo lectura quedan dentro de la instalación. El almacenamiento persistente de usuario queda en:

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

- [ ] Ruff.
- [ ] Pyright.
- [ ] Pytest.
- [ ] Build PyInstaller en Windows.
- [ ] Ejecutar bundle en una máquina Windows sin Python instalado.
- [ ] Confirmar creación/lectura de `database/catalog.db` en `%LOCALAPPDATA%\FacundoCatalogManager`.
- [ ] Confirmar imágenes en `data/images/products`.
- [ ] Confirmar que `_internal` no recibe datos modificables.
- [ ] Confirmar arranque y carga del catálogo.
- [ ] Confirmar búsqueda y filtros.
- [ ] Confirmar actualización del catálogo.
- [ ] Confirmar historial.
- [ ] Confirmar Excel/PDF/CSV.
- [ ] Confirmar cierre limpio.
- [ ] Ejecutar instalador.
- [ ] Confirmar actualización conservando datos existentes.
- [ ] Confirmar desinstalación sin pérdida involuntaria del catálogo.
- [ ] Definir y probar backup/restauración de `catalog.db`.
- [ ] Actualizar versión antes de una release.

## Estado

La arquitectura, el spec de PyInstaller, el instalador y el script reproducible ya están en el repositorio. La release Windows todavía no está declarada: falta producir y probar el bundle/instalador en Windows y cerrar el procedimiento de backup/restauración.
