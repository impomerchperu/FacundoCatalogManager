# Facundo Catalog Manager

**Estado verificado de `main` (15/11/2026):** PR #62 se integró en `314d2ace10ce5adf10cc7240275cfd9577f267eb`. Quality CI #4135 pasó Ruff, Pyright y Pytest (`1129 passed`, `11 deselected`); `live-catalog` se omitió. Una actualización FULL ejecutada desde `app.py` quedó registrada como historial `254`: 24 categorías, 521 apariciones, 518 productos únicos, 3 productos en varias categorías, cobertura completa y 0 errores; actualizó 295 productos y dejó 223 sin cambios. La sincronización guardó 44 colores publicados en `stock_color_palette.json`. Estos conteos describen esa corrida; el criterio de cobertura compara cada ejecución con los totales que publica el sitio en ese momento.

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

Una ejecución FULL válida debe cubrir las categorías descubiertas y alcanzar los totales publicados por esas categorías durante la ejecución. La corrida más reciente registrada en la BD original fue `521 / 518 / 3 / 24` (apariciones / únicos / multi-categoría / categorías), sin brechas. Las cifras anteriores `522/518/4` y `523/519/4` son snapshots históricos, no objetivos fijos. No mezclar bases ni forzar conteos históricos: valida cada FULL contra las métricas de esa misma corrida.

Una ejecución válida debe mantener `coverage_complete=1`, `coverage_gap=0` y cero errores invalidantes. Una ejecución incompleta o inconsistente no debe utilizarse para hacer un prune destructivo del catálogo persistido. La reconciliación de bootstrap selecciona la ejecución FULL exitosa más reciente que además sea consistente con sus métricas y sus ocurrencias reales.

La configuración de concurrencia consolidada en `main` es:

- Categorías: `12` workers.
- Detalle: `24` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8` de concurrencia.
- JetSmartFilters page workers: `2`.
- Sincronización de imágenes: `16` workers.
- Páginas de galería: `12` workers; en 16 fichas reales, 12 promedió 5,88 s frente a 7,46 s con 8 y 6,09 s con 16, con los 16 códigos y 17 candidatos de galería conservados, sin errores ni reintentos.
- Archivos de galería ya canónicos: se omite el escaneo repetido de imágenes hermanas; en 64 productos/112 referencias, a 12 workers bajó de 3,90 s a 0,81 s y conservó todos los hashes.
- Extracción de imágenes desde páginas de detalle: en 518 páginas cacheadas, el extractor específico mantuvo los mismos candidatos que el extractor completo (0 diferencias) y bajó ese componente de 28,15 s a 1,35 s.
- Validación de imágenes durante una corrida: reutiliza verificaciones por archivo sin conservar resultados entre corridas. En la BD local, 518 productos y 1.050 archivos válidos, la normalización de catálogo bajó de 26,04 s a 2,10 s; no cambió productos en memoria ni archivos.

El valor de 24 workers de detalle se seleccionó tras benchmarks controlados en el sitio real. Los ensayos de categorías no demostraron una mejora reproducible al bajar de 12 a 8 workers; por eso se conserva `12 / 24 / 28`. La corrida FULL previa al último conjunto de optimizaciones, historial `256`, tardó 168,82 s. Con el diff actual, la FULL `257` terminó en 118,68 s: **50,14 s menos (29,7 %)**, con 24 categorías, 521 apariciones, 518 productos únicos, cobertura completa, cero errores y 518 productos sin cambios. `gallery_sync` bajó de 54,88 s a 13,43 s y `catalog_sync` de 26,63 s a 2,68 s. El mayor trabajo pendiente es la latencia variable del sitio: en #257 hubo 35 solicitudes HTTP, 14 duraron al menos 10 s y la más lenta tardó 21,17 s; no se aumenta la concurrencia de categorías sin un benchmark controlado que demuestre una mejora estable.

## Stock por color

La sincronización conserva el stock por color cuando el sitio publica una asociación demostrable entre color y cantidad. El catálogo persiste esos datos en `products.color_stock` y la columna **Stock** los muestra como `color → cantidad`.

La validación histórica confirmó `523/523` apariciones con `color_stock` y 0 inconsistencias. La corrida FULL del 15/11 cubrió la extracción actual (`521/518/3/24`) y capturó una vez por ejecución 44 tonos y sus códigos CSS publicados. La auditoría de todas las asociaciones producto-color-stock continúa separada de la comprobación de cobertura general.

No se distribuye artificialmente un stock total entre colores cuando el sitio no publica cantidades asociables de forma inequívoca.
## Historial

Cada descarga exitosa conserva su historial. Solo una versión queda marcada como actualmente aplicada mediante `applied_at`; las ejecuciones anteriores permanecen consultables.

El detalle de cambios se ordena por código de producto. La UI permite consultar cobertura, categorías, productos en múltiples categorías y cambios de cada ejecución.

## Validación

Validación de calidad de la PR #62 antes de integrarse (`Quality CI #4135`, 15/11/2026):

- Ruff: éxito.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Pytest: `1129 passed, 11 deselected`.
- El trabajo `live-fb4047-gallery` se ejecuta como comprobación de recuperación si el detalle está restringido; su informe distingue `recovery_asset_verified=true` de `current_gallery_verified=false`.
- `live-catalog` se omitió en CI; la corrida FULL desde la aplicación se verificó por separado en la BD original y quedó en el historial `254`.


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

`main` incluye la extracción de Detalle desde una única fuente visual. La última corrida FULL registrada verificó cobertura completa, conteos consistentes e historial aplicado. La referencia funcional es móvil: cada FULL completo y consistente sustituye la anterior con los conteos publicados por el sitio. Las invariantes de cobertura deben preservarse en toda optimización posterior.


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

La release publicada validada es `0.1.1`; la versión en preparación para la siguiente release es `0.2.0`. El instalador usa el icono de aplicación de `resources/facundo.ico`, lo incorpora al ejecutable PyInstaller y mantiene el acceso directo del menú Inicio. Durante la instalación puede crearse también un acceso directo en el Escritorio. El ejecutable, el instalador y los artefactos de build no se incorporan al repositorio. Antes de PyInstaller, `tools/prepare_windows_seed.py` comprueba que la última corrida FULL exitosa concuerde con la cobertura, relaciones y productos de la BD, valida las imágenes referenciadas y crea una copia SQLite consistente para el bundle.

El checklist de validación está en `docs/FCM_WINDOWS_RELEASE.md`. La release formal publicada es `v0.1.1`; la candidata `0.2.0` aún requiere Build Windows, validación del instalador y publicación formal.


## Backup y restauración

La utilidad `tools/catalog_backup.py` permite crear y restaurar copias de `database/catalog.db` mediante la API de backup de SQLite. La restauración conserva primero una copia de seguridad del catálogo existente y valida la integridad antes y después de sustituir la base.

Ejemplos:

```powershell
python -m tools.catalog_backup backup --output backups\catalog.bak
python -m tools.catalog_backup restore backups\catalog.bak
```

La aplicación debe permanecer cerrada durante una restauración operativa. La herramienta no reemplaza el procedimiento de validación de release sobre una instalación Windows.
