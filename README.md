# Facundo Catalog Manager

**Referencia canónica de `main` (26/10/2026):** PR #30 se integró mediante squash en `085d6a50a7730e0546775d75ff2d105997edb619`. Quality CI #3885 pasó (Ruff, Pyright y Pytest: 1032 aprobadas, 11 deseleccionadas). El último inventario de catálogo registrado, del 25/10/2026 antes de la promoción, fue `522 / 518 / 4 / 24`; no se ha ejecutado un FULL live posterior a la promoción. El runtime de código actual usa categorías/detalle/HTTP `12 / 24 / 28`. No mezclar bases ni snapshots: cada FULL debe validarse contra los conteos publicados por esa ejecución. En FB-4047 está verificado el recurso histórico con SHA-256 fijado, pero cuando el servidor devuelve la plantilla de acceso no se afirma que la galería live actual se haya certificado.

Aplicación de escritorio en Python + PySide6 para mantener el catálogo de Importaciones Facundo, ejecutar sincronizaciones FULL y exportar la información a Excel, PDF y CSV.

## Ejecución

Requiere Python 3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

La aplicación usa `database/catalog.db` como fuente persistente del catálogo. Al iniciar, primero muestra la ventana y después carga el catálogo persistido; el bootstrap y la lectura inicial del catálogo no bloquean el hilo de la interfaz y no inician scraping web. Las ejecuciones de scraping se lanzan desde **Actualizar catálogo**.

La aplicación publica el nombre y la versión mediante los metadatos estándar de `QApplication`; `VERSION` se incorpora también al bundle Windows. Una vez cargadas las filas, la búsqueda y los filtros de stock/categorías actúan sobre las filas existentes sin reconstruir la tabla completa.

## Scraping FULL

Una ejecución FULL válida debe cubrir las 24 categorías y alcanzar los totales publicados por las propias categorías en esa ejecución. El inventario auditado el 25/10/2026 antes de la promoción registró 522 apariciones, 518 productos únicos, 4 productos multi-categoría y 522 relaciones (`522/518/4/24`). El snapshot anterior de `main` de 523/519/4 y la referencia histórica 534/530/4 son evidencia histórica, no objetivos que deban forzarse mezclando bases. El siguiente FULL del código consolidado debe compararse con el inventario que publique el sitio durante esa ejecución.

Una ejecución válida debe mantener `coverage_complete=1`, `coverage_gap=0` y cero errores invalidantes. Una ejecución incompleta o inconsistente no debe utilizarse para hacer un prune destructivo del catálogo persistido. La reconciliación de bootstrap selecciona la ejecución FULL exitosa más reciente que además sea consistente con sus métricas y sus ocurrencias reales.

La configuración actual de código en `main` es:

- Categorías: `12` workers.
- Detalle: `24` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8` de concurrencia.
- JetSmartFilters page workers: `2`.
- Sincronización de imágenes: `16` workers.

El valor de 24 workers de detalle se seleccionó tras benchmarks controlados en el sitio real. Los ensayos de categorías no demostraron una mejora reproducible al bajar de 12 a 8 workers; por eso se conserva `12 / 24 / 28`. La cobertura histórica de catálogo no se considera una validación FULL del código posterior a la promoción.

## Stock por color

La sincronización conserva el stock por color cuando el sitio publica una asociación demostrable entre color y cantidad. El catálogo persiste esos datos en `products.color_stock` y la columna **Stock** los muestra como `color → cantidad`.

La validación previa de stock por color confirmó `523/523` apariciones con `color_stock`, `24/24` categorías y `0` inconsistencias en ese inventario histórico. La auditoría del 25/10 registró después `522/518/4/24`. No se ha ejecutado un FULL live con el código consolidado en `main`; las invariantes de stock por color siguen cubiertas por las pruebas automatizadas y deben comprobarse en el próximo FULL controlado.

No se distribuye artificialmente un stock total entre colores cuando el sitio no publica cantidades asociables de forma inequívoca.
## Historial

Cada descarga exitosa conserva su historial. Solo una versión queda marcada como actualmente aplicada mediante `applied_at`; las ejecuciones anteriores permanecen consultables.

El detalle de cambios se ordena por código de producto. La UI permite consultar cobertura, categorías, productos en múltiples categorías y cambios de cada ejecución.

## Validación

Validación de calidad del `main` consolidado (`085d6a50`, Quality CI #3885, 26/10/2026):

- Ruff: éxito.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Pytest: `1032 passed, 11 deselected`.
- El trabajo `live-fb4047-gallery` se ejecuta como comprobación de recuperación si el detalle está restringido; su informe distingue `recovery_asset_verified=true` de `current_gallery_verified=false`.
- El trabajo `live-catalog` fue omitido; esto no equivale a una prueba FULL contra el sitio después de la promoción.


Comprobaciones estáticas:

```powershell
python -m ruff check .
python -m pyright
```

Suite automatizada completa, excluyendo las pruebas contra el sitio real mediante el marcador `real_site`:

```powershell
python -m pytest -q
```

Para ejecutar únicamente las pruebas contra el sitio real:

```powershell
python -m pytest -m real_site -q
```

Validación FULL real:

```powershell
python -m pytest tests/scraping/real_site/test_full_catalog_scraper.py -m real_site -q -s
```

El workflow de GitHub Actions ejecuta Ruff, Pyright y Pytest automáticamente. La validación FULL real está disponible mediante ejecución manual del workflow.

## Estructura principal

- `app.py`: punto de entrada de la aplicación.
- `gui/`: interfaz PySide6.
- `services/`: lógica de negocio, bootstrap y scraping.
- `scrapers/`: extracción y recuperación del sitio.
- `repositories/`: persistencia del scraping e historial.
- `database/`: SQLite, esquema y migraciones.
- `tests/`: pruebas unitarias, integración y pruebas opcionales contra el sitio real.
- `docs/`: criterios operativos, releases y auditorías vigentes.

## Estado validado de la rama

El baseline documentado de `main` cubre scraping, persistencia y bootstrap con snapshot `523 / 519 / 4`, cobertura completa e historial persistente bajo `8 / 24 / 28`. La candidata `feat/product-table-layout` tiene auditoría live completa `522 / 518 / 4 / 24`; el benchmark aconseja conservar `12 / 24 / 28` en la rama candidata. La PR #30 permanece en borrador y no se ha fusionado, por lo que estos resultados no deben presentarse como el estado ya desplegado de `main`.

La referencia funcional es móvil: cada FULL completo, consistente y sin errores sustituye la referencia anterior con los conteos publicados por el sitio. Las invariantes de cobertura deben preservarse en toda optimización posterior.


## Distribución Windows

La distribución Windows usa PyInstaller en modo **one-dir** e Inno Setup 7 para el instalador. El código y los recursos de solo lectura permanecen en el bundle; la aplicación guarda `database/catalog.db`, `data/images` y `logs` en `%LOCALAPPDATA%\FacundoCatalogManager` cuando está congelada.

Build reproducible desde PowerShell:

```powershell
.\scripts\build_windows.ps1 -SkipInstaller
```

Para generar también el instalador:

```powershell
.\scripts\build_windows.ps1
```

La release publicada validada es `0.1.1`; la versión en preparación para la siguiente release es `0.2.0`. El instalador usa el icono de aplicación de `resources/facundo.ico`, lo incorpora al ejecutable PyInstaller y mantiene el acceso directo del menú Inicio. Durante la instalación puede crearse también un acceso directo en el Escritorio. El ejecutable, el instalador y los artefactos de build no se incorporan al repositorio. Antes de PyInstaller, `tools/prepare_windows_seed.py` valida la base `523 / 519 / 4`, comprueba las imágenes referenciadas y crea una copia SQLite consistente para el bundle.

El checklist de validación está en `docs/FCM_WINDOWS_RELEASE.md`. La release formal publicada es `v0.1.1`; la candidata `0.2.0` aún requiere Build Windows, validación del instalador y publicación formal.


## Backup y restauración

La utilidad `tools/catalog_backup.py` permite crear y restaurar copias de `database/catalog.db` mediante la API de backup de SQLite. La restauración conserva primero una copia de seguridad del catálogo existente y valida la integridad antes y después de sustituir la base.

Ejemplos:

```powershell
python -m tools.catalog_backup backup --output backups\catalog.bak
python -m tools.catalog_backup restore backups\catalog.bak
```

La aplicación debe permanecer cerrada durante una restauración operativa. La herramienta no reemplaza el procedimiento de validación de release sobre una instalación Windows.
