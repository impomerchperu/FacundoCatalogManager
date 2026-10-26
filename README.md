# Facundo Catalog Manager

**Referencia de `main` (corte histórico):** `523 / 519 / 4`, cobertura completa y runtime de categorías/detalle/HTTP `8 / 24 / 28`. **Candidata `feat/product-table-layout` (PR #30, aún sin fusionar):** auditoría live del 25/10/2026 con `522 / 518 / 4 / 24` y configuración probada `12 / 24 / 28`. No mezclar bases ni snapshots: cada FULL debe validarse contra los conteos publicados en esa ejecución. La versión del código candidata debe distinguirse del estado de la rama `main`.

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

Una ejecución FULL válida debe cubrir las 24 categorías y alcanzar los totales publicados por las propias categorías en esa ejecución. El snapshot operativo de `main` usado en la validación anterior fue de 523 apariciones, 519 productos únicos, 4 productos en múltiples categorías y 523 relaciones. La auditoría live de la candidata `feat/product-table-layout` del 25/10/2026 obtuvo 522 apariciones, 518 productos únicos, 4 productos multi-categoría y 522 relaciones (`522/518/4/24`). La referencia histórica 534/530/4 es solo evidencia de auditoría e historial; el conteo de cada FULL lo determina el inventario publicado en esa ejecución.

Una ejecución válida debe mantener `coverage_complete=1`, `coverage_gap=0` y cero errores invalidantes. Una ejecución incompleta o inconsistente no debe utilizarse para hacer un prune destructivo del catálogo persistido. La reconciliación de bootstrap selecciona la ejecución FULL exitosa más reciente que además sea consistente con sus métricas y sus ocurrencias reales.

La configuración base que se había validado en `main` era:

- Categorías: `8` workers.
- Detalle: `24` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8` de concurrencia.

El valor de 24 workers de detalle fue seleccionado tras benchmarks controlados en el sitio real frente a 16 workers. La validación anterior de `main` bajo `8 / 24 / 28` confirmó `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, `0` retries y `0` errores HTTP terminales. En la candidata `feat/product-table-layout`, seis ensayos controlados de 8 vs. 12 workers de categoría no mostraron ventaja concluyente con 8 (mejora de mediana aparente 2,04%, menor que la dispersión); por eso se conserva `12 / 24 / 28` en esa rama. Esta diferencia no cambia `main` mientras la PR #30 siga sin fusionarse.

## Stock por color

La sincronización conserva el stock por color cuando el sitio publica una asociación demostrable entre color y cantidad. El catálogo persiste esos datos en `products.color_stock` y la columna **Stock** los muestra como `color → cantidad`.

La garantía está validada sobre las 24 categorías reales: una ejecución FULL reciente confirmó `523/523` apariciones con `color_stock`, `24/24` categorías representadas y `0` inconsistencias entre el stock total y la suma de sus colores. Las pruebas FULL y de concurrencia incluyen estas invariantes para detectar regresiones.

No se distribuye artificialmente un stock total entre colores cuando el sitio no publica cantidades asociables de forma inequívoca.
## Historial

Cada descarga exitosa conserva su historial. Solo una versión queda marcada como actualmente aplicada mediante `applied_at`; las ejecuciones anteriores permanecen consultables.

El detalle de cambios se ordena por código de producto. La UI permite consultar cobertura, categorías, productos en múltiples categorías y cambios de cada ejecución.

## Validación

Última validación local confirmada en `main` antes de las mejoras de la candidata `0.2.0`:

- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Pytest: `582 passed, 10 deselected`.


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
