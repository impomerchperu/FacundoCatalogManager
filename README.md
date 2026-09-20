# Facundo Catalog Manager

Aplicación de escritorio en Python + PySide6 para mantener el catálogo de Importaciones Facundo, ejecutar sincronizaciones FULL y exportar la información a Excel, PDF y CSV.

## Ejecución

Requiere Python 3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

La aplicación usa `database/catalog.db` como fuente persistente del catálogo. Al iniciar, primero muestra la ventana y después carga el catálogo persistido; el bootstrap no inicia scraping web. Las ejecuciones de scraping se lanzan desde **Actualizar catálogo**.

## Scraping FULL

Una ejecución FULL válida debe cubrir las 24 categorías y alcanzar los totales publicados por las propias categorías en esa ejecución. La referencia operativa actual es 523 apariciones, 519 productos únicos, 4 productos presentes en múltiples categorías y 523 relaciones producto-categoría. El snapshot histórico 534/530/4 se conserva como referencia diagnóstica del inventario anterior, no como requisito rígido del inventario vivo.

Una ejecución válida debe mantener `coverage_complete=1`, `coverage_gap=0` y cero errores invalidantes. Una ejecución incompleta o inconsistente no debe utilizarse para hacer un prune destructivo del catálogo persistido. La reconciliación de bootstrap selecciona la ejecución FULL exitosa más reciente que además sea consistente con sus métricas y sus ocurrencias reales.

La configuración de producción actual es:

- Categorías: `8` workers.
- Detalle: `16` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8` de concurrencia.

El valor de 16 workers de detalle fue seleccionado tras benchmarks en el sitio real con corridas cruzadas frente a 24 workers. La validación E2E de producción bajo esta configuración ya está completada: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado y duración de `90.78s` en SQLite aislada.

## Historial

Cada descarga exitosa conserva su historial. Solo una versión queda marcada como actualmente aplicada mediante `applied_at`; las ejecuciones anteriores permanecen consultables.

El detalle de cambios se ordena por código de producto. La UI permite consultar cobertura, categorías, productos en múltiples categorías y cambios de cada ejecución.

## Validación

Comprobaciones estáticas:

```powershell
python -m ruff check .
python -m pyright
```

Suite automatizada completa, excluyendo las pruebas contra el sitio real:

```powershell
python -m pytest -q --ignore=tests/scraping/real_site
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
