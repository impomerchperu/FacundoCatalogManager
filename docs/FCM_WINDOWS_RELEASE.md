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

El instalador generado en esta validación es:

`dist\Windows\FacundoCatalogManager-0.1.0-setup.exe`

Inno Setup 7 puede instalarse con:

```powershell
winget install --id JRSoftware.InnoSetup.7 -e -s winget -i
```

La instalación por usuario puede quedar en:

`%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe`

El script de build contempla esa ruta además de las instalaciones globales.

## Datos de usuario

Cuando la aplicación está congelada, `config.runtime_paths` dirige la base, imágenes y logs a `%LOCALAPPDATA%\FacundoCatalogManager`.

El instalador utiliza una carpeta distinta, `%LOCALAPPDATA%\Programs\FacundoCatalogManager`, para los binarios. De esta forma, el ejecutable puede instalarse, actualizarse o desinstalarse sin reemplazar el catálogo persistido por una copia del bundle.

Las rutas de imagen almacenadas en SQLite conservan el formato relativo `data/images/...`; la GUI las resuelve contra `DATA_DIR`.

## Backup y restauración

La utilidad `tools/catalog_backup.py` permite crear y restaurar copias de `database/catalog.db` mediante la API de backup de SQLite.

La creación del backup:

1. verifica `PRAGMA integrity_check` sobre la base origen;
2. genera una copia mediante `sqlite3.Connection.backup()`;
3. valida la copia antes de sustituir el destino final.

La restauración:

1. verifica la integridad del backup;
2. conserva un backup de seguridad de la base existente, cuando existe;
3. escribe primero a un archivo temporal;
4. valida el temporal;
5. sustituye el destino;
6. elimina posibles archivos WAL/SHM residuales;
7. vuelve a ejecutar `PRAGMA integrity_check`.

La aplicación debe permanecer cerrada durante una restauración operativa.

### Backup

```powershell
python -m tools.catalog_backup backup --output backups\catalog-YYYYMMDD-HHMMSS.bak
```

Para comprobar el archivo antes de usarlo:

```powershell
python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()" .\backups\catalog-YYYYMMDD-HHMMSS.bak
```

Debe mostrar:

```text
ok
```

### Restauración operativa

Cerrar FCM y ejecutar:

```powershell
python -m tools.catalog_backup restore .\backups\catalog-YYYYMMDD-HHMMSS.bak
```

La herramienta conserva un archivo:

`catalog-pre-restore-YYYYMMDD-HHMMSS.bak`

junto a la base restaurada cuando la base destino ya existía.

### Validación real sin modificar la base del usuario

Para validar el flujo con una base real sin reemplazarla, generar el backup desde la base persistente y restaurarlo hacia una ruta temporal separada:

```powershell
$root = "$env:LOCALAPPDATA\FacundoCatalogManager"
$validation = Join-Path $env:TEMP "FCM-backup-validation"
$backup = Join-Path $validation "catalog-real.bak"
$restored = Join-Path $validation "catalog-restored.db"

Remove-Item $validation -Recurse -Force -ErrorAction SilentlyContinue
New-Item $validation -ItemType Directory -Force | Out-Null

python -m tools.catalog_backup backup --database "$root\database\catalog.db" --output $backup

python -m tools.catalog_backup restore $backup --database $restored

python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0]); print('products:', c.execute('SELECT COUNT(*) FROM products').fetchone()[0]); print('categories:', c.execute('SELECT COUNT(*) FROM categories').fetchone()[0]); print('relations:', c.execute('SELECT COUNT(*) FROM product_categories').fetchone()[0]); print('history:', c.execute('SELECT COUNT(*) FROM scraping_history').fetchone()[0]); c.close()" $restored
```

Para esta validación deben coincidir la integridad y los conteos entre la base real y la copia restaurada. Este procedimiento no modifica `%LOCALAPPDATA%\FacundoCatalogManager`.

### Resultado de validación real

El 25 de septiembre de 2026 se ejecutó el procedimiento sobre la base persistente de la instalación Windows:

```text
Base real:
integrity: ok
products: 519
categories: 24
relations: 523
history: 169

Backup:
integrity: ok
13,733,888 bytes

Copia restaurada:
integrity: ok
products: 519
categories: 24
relations: 523
history: 169
13,733,888 bytes
```

La restauración se realizó en `%TEMP%\FCM-backup-validation\catalog-restored.db`, por lo que la base persistente del usuario no fue modificada.

## Checklist previo a release

- [x] Ruff.
- [x] Pyright.
- [x] Pytest.
- [x] Build PyInstaller en Windows.
- [ ] Ejecutar bundle en una máquina Windows sin Python instalado.
- [x] Confirmar creación/lectura de `database/catalog.db` en `%LOCALAPPDATA%\FacundoCatalogManager`.
- [x] Confirmar imágenes en `data/images/products` después de la instalación.
- [x] Confirmar que `_internal` no recibe datos modificables.
- [x] Confirmar arranque y carga del catálogo.
- [x] Confirmar búsqueda y filtros.
- [ ] Confirmar actualización del catálogo con una versión posterior.
- [x] Confirmar historial.
- [x] Confirmar Excel/PDF/CSV.
- [x] Confirmar cierre limpio.
- [x] Ejecutar instalador.
- [x] Confirmar reinstalación conservando datos existentes.
- [x] Confirmar desinstalación sin pérdida involuntaria del catálogo.
- [x] Implementar backup/restauración de `catalog.db` y cubrirlo con pruebas automatizadas.
- [x] Validar backup/restore sobre una base real de usuario mediante el procedimiento aislado anterior.
- [ ] Actualizar versión antes de una release.

## Resultados Windows validados

Instalador:

`dist\Windows\FacundoCatalogManager-0.1.0-setup.exe`

La instalación real confirmó:

- ejecutable presente en `%LOCALAPPDATA%\Programs\FacundoCatalogManager`;
- base persistente creada en `%LOCALAPPDATA%\FacundoCatalogManager\database\catalog.db`;
- `519` imágenes locales;
- SQLite `integrity: ok`;
- `519` productos;
- `24` categorías;
- `523` relaciones;
- `169` registros de historial.

La reinstalación conservó el SHA256 de `catalog.db`, por lo que no sustituyó la base persistente del usuario.

La desinstalación eliminó el programa de instalación y conservó:

- `catalog.db`;
- `519` imágenes;
- historial;
- integridad de SQLite;
- `519 / 24 / 523`.

## Estado

El bundle PyInstaller, la semilla validada, el instalador Inno Setup y el ciclo instalación/reinstalación/desinstalación ya fueron probados en Windows. El catálogo persistente se conserva fuera del directorio de instalación y no se pierde al reinstalar o desinstalar.

El procedimiento de backup/restore también fue validado sobre la base real de la instalación y restaurado hacia una ubicación aislada, conservando integridad y los conteos `519 / 24 / 523 / 169`.

Las pendientes antes de una release formal son: ejecutar el bundle en una máquina sin Python instalado, probar una actualización real entre versiones y definir la versión de release.
