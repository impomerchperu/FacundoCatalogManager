# Facundo Catalog Manager

**Referencia funcional actual:** catálogo vivo validado en `main` con `523 / 519 / 4`, cobertura completa y suite automatizada en verde. El bloque de release Windows incorpora una semilla validada de catálogo e imágenes generada durante el build.

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

La carga inicial de catálogos grandes utiliza renderizado progresivo. Una vez cargadas las filas, la búsqueda y los filtros de stock/categorías actúan sobre las filas existentes sin reconstruir la tabla completa.

## Scraping FULL

Una ejecución FULL válida debe cubrir las 24 categorías y alcanzar los totales publicados por las propias categorías en esa ejecución. La referencia operativa actual es 523 apariciones, 519 productos únicos, 4 productos presentes en múltiples categorías y 523 relaciones producto-categoría. El snapshot histórico 534/530/4 se conserva como referencia diagnóstica del inventario anterior, no como requisito rígido del inventario vivo.

Una ejecución válida debe mantener `coverage_complete=1`, `coverage_gap=0` y cero errores invalidantes. Una ejecución incompleta o inconsistente no debe utilizarse para hacer un prune destructivo del catálogo persistido. La reconciliación de bootstrap selecciona la ejecución FULL exitosa más reciente que además sea consistente con sus métricas y sus ocurrencias reales.

La configuración de producción actual es:

- Categorías: `8` workers.
- Detalle: `16` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8` de concurrencia.

El valor de 16 workers de detalle fue seleccionado tras benchmarks en el sitio real con corridas cruzadas frente a 24 workers. La validación E2E de producción bajo esta configuración ya está completada: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado y benchmark productivo de `83.65s` con `0` retries y `0` errores HTTP terminales.

## Stock por color

La sincronización conserva el stock por color cuando el sitio publica una asociación demostrable entre color y cantidad. El catálogo persiste esos datos en `products.color_stock` y la columna **Stock** los muestra como `color → cantidad`.

La garantía está validada sobre las 24 categorías reales: una ejecución FULL reciente confirmó `523/523` apariciones con `color_stock`, `24/24` categorías representadas y `0` inconsistencias entre el stock total y la suma de sus colores. Las pruebas FULL y de concurrencia incluyen estas invariantes para detectar regresiones.

No se distribuye artificialmente un stock total entre colores cuando el sitio no publica cantidades asociables de forma inequívoca.
## Historial

Cada descarga exitosa conserva su historial. Solo una versión queda marcada como actualmente aplicada mediante `applied_at`; las ejecuciones anteriores permanecen consultables.

El detalle de cambios se ordena por código de producto. La UI permite consultar cobertura, categorías, productos en múltiples categorías y cambios de cada ejecución.

## Validación

Estado local validado en `main` el 2026-09-25:

- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Pytest: `507 passed, 10 deselected`.


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
- `docs/`: criterios de cobertura, arquitectura y recuperación.

## Estado validado de la rama

El baseline validado en `main` cubre el flujo completo de scraping, persistencia y bootstrap con referencia operativa viva `523 / 519 / 4`, cobertura completa, catálogo reconciliado `519 / 523`, historial persistente, E2E de producción bajo `8 / 16 / 28` y suite automatizada en verde.

El snapshot histórico `534 / 530 / 4` se conserva como referencia diagnóstica. Las optimizaciones de rendimiento posteriores deben conservar siempre las invariantes de cobertura del inventario vivo antes de considerarse válidas.


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

La versión inicial del instalador es `0.1.0`. El ejecutable, el instalador y los artefactos de build no se incorporan al repositorio. Antes de PyInstaller, `tools/prepare_windows_seed.py` valida la base `523 / 519 / 4`, comprueba las imágenes referenciadas y crea una copia SQLite consistente para el bundle.

El checklist de validación está en `docs/FCM_WINDOWS_RELEASE.md`.


## Backup y restauración

La utilidad `tools/catalog_backup.py` permite crear y restaurar copias de `database/catalog.db` mediante la API de backup de SQLite. La restauración conserva primero una copia de seguridad del catálogo existente y valida la integridad antes y después de sustituir la base.

Ejemplos:

```powershell
python -m tools.catalog_backup backup --output backups\catalog.bak
python -m tools.catalog_backup restore backups\catalog.bak
```

La aplicación debe permanecer cerrada durante una restauración operativa. La herramienta no reemplaza el procedimiento de validación de release sobre una instalación Windows.
