# Criterios de éxito del scraping FULL

Fecha de validación del último checkpoint maestro: 2026-09-26  
Branch oficial: `main`

## Objetivo

Una ejecución FULL del catálogo debe ser correcta, completa y segura para sincronizar la base de datos. El rendimiento es una optimización secundaria y nunca debe reducir las garantías de cobertura o persistencia.

## Criterio funcional autorizado

Una ejecución FULL válida cubre las 24 categorías y alcanza simultáneamente los totales publicados por las propias categorías en esa ejecución. La referencia histórica es móvil y se actualiza al último FULL completo, consistente y sin errores que haya sido verificado.

La prueba real debe tratar una variación de inventario (altas/bajas/movimientos de productos) como deriva del sitio y comprobar en su lugar que cada categoría se extrae sin gaps respecto de su `expected_count`, que el total encontrado coincide con ese total vigente y que la persistencia mantiene las mismas cantidades observadas.

- `523` apariciones observadas en la última referencia operativa.
- `519` productos únicos observados en la última referencia operativa.
- `4` productos presentes en múltiples categorías.
- `523` relaciones producto-categoría.
- `coverage_complete=1`.
- `coverage_gap=0`.
- `error_count=0`.

Estos números constituyen la referencia operativa actualmente verificada. Cuando un FULL posterior termina completo, consistente y sin errores, sus totales pasan a ser la nueva referencia.

Los pisos históricos menores, como `529/525`, no sustituyen la cobertura completa.

Cuando una ejecución no cumple estas condiciones, debe tratarse como incompleta y no debe provocar un prune destructivo del catálogo persistido.

## Precedencia y reconciliación

El bootstrap selecciona la ejecución FULL `SUCCESS` más reciente que también sea internamente consistente con sus métricas y con las ocurrencias almacenadas. En esquemas modernos, las métricas disponibles se comparan exactamente con las ocurrencias reales; una ejecución `SUCCESS` con métricas incoherentes no es candidata.

Si existen varias ejecuciones FULL válidas, prevalece la más reciente. Una ejecución FULL fallida o incompleta más reciente no sustituye a una FULL válida anterior.

La reconciliación trabaja por código normalizado, reconstruye `product_categories` desde las ocurrencias del run seleccionado y elimina del catálogo los productos que no estén representados por ese run.

## Persistencia e historial

La base de datos persistente es `database/catalog.db`. El bootstrap no inicia scraping web y no sustituye un catálogo ya inicializado.

El historial no se elimina para reparar el catálogo. Las ejecuciones anteriores permanecen disponibles y cada `SUCCESS` puede marcarse como la versión actualmente aplicada mediante `applied_at`.

Una repetición idéntica sobre la misma SQLite debe ser idempotente: la segunda sincronización no crea ni actualiza productos, clasifica los productos como `unchanged` y no genera filas en `download_changes`. Esta garantía está validada por el test de integración de SQLite y el Quality CI actual.

Las validaciones anteriores de bases reales se conservan solo como archivo de auditoría. No establecen un piso de cobertura ni sustituyen la referencia viva del último FULL verificado.

## Recuperación de red

La recuperación de categorías, paginación, JSF, páginas incompletas, códigos y detalle existe para aumentar la probabilidad de completar el FULL ante fallos transitorios. La cobertura final y la integridad del resultado son las condiciones que determinan si el run es utilizable.

Los contadores HTTP, reintentos y tiempos agregados son métricas de diagnóstico. La instrumentación conserva máximo en vuelo por clase (`category`, `jsf`, `detail`, `other`), percentiles P50/P95/P99 y tiempos agregados por etapa. Los tiempos acumulados de solicitudes concurrentes no deben compararse directamente con el tiempo de pared.

## Rendimiento

La configuración de producción validada es:
El número de workers internos de paginación JSF también está centralizado en `ScrapingConfig`; el valor productivo actual permanece en `2`.


- categoría: `8` workers;
- detalle: `24` workers;
- HTTP: `28` workers;
- JetSmartFilters HTTP: `8` concurrentes.

La evidencia disponible muestra que el coste principal está en red, especialmente en extracción de categorías y enriquecimiento de detalle. El detalle se ha protegido con coalescencia concurrente de futures y pruebas específicas.

La telemetría de enrichment por categoría registra `requested`, `skipped`, `total_seconds`, `submit_seconds` y `wait_seconds` sin modificar la semántica del scraping. Está cubierta por una prueba de contrato específica y permite separar el tiempo de cada categoría de las métricas agregadas.

No existe una cifra única de tiempo de pared que deba tratarse como requisito funcional: los benchmarks dependen del estado del sitio remoto y de la red. Cualquier optimización debe conservar cobertura completa respecto del inventario vivo y ser validada nuevamente.

Un benchmark específico de contención de SQLite no es requisito para la corrección actual y queda como optimización futura, no como bloqueo de la funcionalidad validada.

## Auditoría del almacenamiento de imágenes

La ruta canónica del almacenamiento descargado es data/images/products. La tabla products de database/catalog.db es la única fuente de verdad para decidir qué imágenes deben permanecer físicamente en el almacenamiento administrado por la aplicación: únicamente los paths presentes en products.image_path son activos.

data/images puede conservar archivos legacy de ejecuciones anteriores y resources/images contiene recursos históricos versionados. Ninguno de esos archivos se considera activo solo por existir, por tener un hash duplicado o por haber sido usado por una implementación anterior.

- [x] Ruta canónica centralizada en data/images/products.
- [x] ImageNamer, ImageDownloader, ImageRepository e ImageValidator comparten el contrato de almacenamiento.
- [x] Auditoría no destructiva de filesystem + SQLite + SHA-256 implementada.
- [x] Auditoría dinámica de todas las tablas SQLite que contienen image_path.
- [x] Limpieza basada exclusivamente en products.image_path implementada en tools/clean_unused_images.py.
- [x] El scraping FULL ejecuta automáticamente esa limpieza después de un prune FULL válido; un scraping dirigido o incompleto no la ejecuta.
- [x] La limpieza es no destructiva por defecto; --delete es una operación explícita.
- [x] Auditoría real local: 1,037 imágenes encontradas en data/images y data/images/products, 530 referencias activas, 0 referencias activas inexistentes y 0 hash mismatches.
- [x] Auditar adicionalmente resources/images: el directorio no existe en el entorno local, por lo que no contiene archivos adicionales que auditar.
- [x] Limpieza manual inicial ejecutada: se eliminaron 507 archivos no referenciados, liberando 64,009,379 bytes.
- [x] Auditoría posterior: 530 archivos, 530 referencias activas, 0 huérfanos, 0 referencias activas inexistentes y 0 hash mismatches.
- [x] El almacenamiento futuro queda protegido por limpieza automática posterior a un FULL completo.
## Deriva del inventario vivo

La validación real más reciente estableció `523` apariciones esperadas. El criterio de cobertura se basa en la consistencia interna de la ejecución actual y esta referencia se reemplazará automáticamente a nivel de documentación de ingeniería cuando un FULL posterior, completo y sin errores, establezca nuevos totales verificados.

## Resultado del benchmark SQLite

Se ejecutó un benchmark aislado sobre SQLite temporal con 530 productos, WAL, `synchronous=NORMAL` y `busy_timeout=30000ms`.

- 0 errores en los cuatro escenarios.
- Escrituras P95: 0.58–5.70 ms.
- Lecturas P95: <= 0.417 ms.
- Máximo puntual de escritura observado: 16.52 ms.
- No se modificó `database/catalog.db`.
- No se modifica el alcance transaccional ni la configuración SQLite por este resultado.

## Estado de ingeniería validado

El estado actual de `main` fue validado localmente el 2026-09-26 y Quality CI volvió a quedar en `success` sobre el HEAD de release/documentación.

- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Pytest: `542 passed, 10 deselected`.
- Bootstrap/reconciliación: `15 passed`.
- Batería de scraping/runner/cache/progreso: validada.
- Telemetría de enrichment por categoría: instrumentada y cubierta.
- FULL/E2E de producción validado: `24 / 523 / 519 / 4`, DB `519 / 523`, configuración `8 / 24 / 28`, `333` solicitudes HTTP, `0` retries y `0` errores terminales; última corrida `121.48s`.
- La release formal `v0.1.1` está publicada y el tag apunta a `4238a9f`.

## Benchmark de rendimiento actual

La última referencia de benchmark de concurrencia utilizada para decidir el cambio de runtime comparó `8 / 16 / 28` contra `8 / 24 / 28`; la configuración productiva resultante es `8 / 24 / 28`:

- `24` categorías.
- `523` apariciones esperadas y encontradas.
- `519` productos únicos.
- `4` multi-categoría.
- collection wall: `46.78s`.
- enrichment wall: `49.20s`.
- pipeline wall: `98.39s`.
- `333` solicitudes HTTP.
- máximo observado en vuelo: `16`.
- `274` solicitudes de detalle.
- `249` productos omitieron detalle.
- `0` espera del semáforo de detalle.
- `0` reintentos y `0` errores terminales.

La última corrida controlada con `24` workers de detalle, manteniendo `8` workers de categoría, `28` HTTP y JSF `8 / 2`, verificó `523/523`, `519` únicos, `4` multi-categoría, `0` reintentos y `0` errores terminales, con collection `47.55s`, enrichment `46.90s` y pipeline `96.49s`. El E2E productivo posterior, ya con `24` workers de detalle, confirmó `523/523`, persistencia DB `519/523`, historial aplicado, `333` requests, `0` retries y `0` errores terminales en `100.25s`.

Los requests más lentos del muestreo fueron páginas de categoría, aproximadamente entre `8.19s` y `9.52s`. La evidencia del código explica el máximo global de `16`: no representa saturación del semáforo de `28`, sino la capacidad de los productores aguas arriba. Con `8` workers de categoría y `2` workers JSF por categoría, la paginación JSF puede generar hasta `8 × 2 = 16` requests; el enrichment también tiene `16` workers de detalle.

### Instrumentación del benchmark controlado

Referencia real adicional del 2026-09-20: el baseline `8 / 2 / 16 / 28` volvió a completar `523/523`, `519` únicos y `4` multi-categoría, sin reintentos ni errores terminales; observó collection `54.64s`, enrichment `48.61s` y pipeline `105.32s`, con P50/P95/P99 de categoría `6.988/9.799/10.026s`, JSF `4.802/7.413/7.578s` y detalle `2.531/4.072/4.985s`. El intento controlado con `12` workers de categoría terminó con `KeyboardInterrupt` antes de producir resultado; queda como experimento no concluyente y no justifica cambiar el runtime.

La comparación controlada de colección confirmó que `12` workers produjo `55.40s` y `56.12s` en dos corridas, mientras `16` workers produjo `59.40s`; por ello no hay evidencia para aumentar `SCRAPING_CATEGORY_WORKERS` desde `8`. Las dos corridas preliminares del experimento `JSF_PAGE_WORKERS=4` (47.42s y 54.68s) no son comparables con producción porque el harness no propagaba `jsf_http_concurrency` y el scraper quedaba accidentalmente limitado a `4` concurrentes JSF, aunque producción usa `8`. El benchmark se corrigió para recibir explícitamente ambos parámetros. La primera comparación válida, con `JSF HTTP=8`, mantuvo cobertura `523/523` y `0` errores: `JSF PAGE=4` produjo `42.85s` de collection wall, frente a `53.43s` con `JSF PAGE=2`, una diferencia de `10.58s` (`~19.8%`). Una repetición con el mismo contrato volvió a completar `523/523` y `0` errores, pero `PAGE=4` produjo `56.49s`, frente a `53.43s` de `PAGE=2`. Además, la corrida lenta de `PAGE=4` volvió a presentar latencia de categoría comparable o incluso menor (P95 `9.531s`), lo que refuerza que el wall-clock está dominado por la variabilidad concurrente de la red y no permite atribuir la primera mejora a los page-workers. Por tanto, `PAGE=4` no muestra un beneficio reproducible y no justifica cambiar el default productivo de `2`.

El benchmark real admite `FCM_BENCH_OUTPUT_JSON` para persistir, además de la salida de consola, un artefacto JSON opcional con esquema `1`. El archivo se escribe de forma atómica solo después de completar las invariantes del benchmark; contiene configuración, cobertura, tiempos, métricas HTTP y métricas de detalle. No cambia el runtime productivo y permite comparar corridas fuera de la consola.

El benchmark real admite `FCM_BENCH_COLLECTION_ONLY=1` para ejecutar únicamente la colección y reportar su wall-clock, requests de categoría, máximo en vuelo por clase, percentiles P50/P95/P99 y tiempos agregados de categoría/JSF. También admite `FCM_BENCH_THREAD_SESSIONS=1` para aislar el efecto de usar una sesión HTTP por hilo durante la fase concurrente de colección; esta opción es solo diagnóstica y no cambia el runtime de producción por defecto. También admite `FCM_BENCH_CATEGORY_PAGE_WORKERS` para controlar de forma aislada el número de descargas de páginas HTML por categoría; el valor por defecto es `1`, por lo que el benchmark conserva el comportamiento productivo actual y solo los valores mayores de `1` prueban paralelismo adicional. El benchmark imprime la finalización de cada categoría y de cada enrichment, de modo que una ejecución interrumpida identifica el último trabajo que no completó.

El diagnóstico de páginas de categoría del 2026-09-20 quedó cerrado bajo el contrato `8 / 16 / 28` + JSF `8 / 2` con tres corridas por condición. `PAGE=1`: `42.52s`, `51.15s`, `43.66s` (media `45.78s`); `PAGE=2`: `45.59s`, `41.14s`, `46.85s` (media `44.53s`). Todas mantuvieron `523/523` y `0` errores terminales. La dirección por pareja no fue consistente y la diferencia media fue de solo `1.25s` (`~2.7%`) frente a una variabilidad de red mucho mayor. No se establece un beneficio reproducible para producción; se conserva `SCRAPING_CATEGORY_PAGE_WORKERS=1` y no se modifica el runtime. Quality CI runs `2093`–`2100` finalizaron en `success`, incluyendo la prueba de concurrencia.

El diagnóstico de transporte del 2026-09-20 quedó cerrado con cuatro corridas bajo el mismo contrato `8` workers de categoría, `16` de detalle, `28` HTTP y JSF `8/2`. Las sesiones por hilo produjeron `41.15s` y `52.79s`; los controles con sesión compartida produjeron `53.43s` y `43.93s`. Las cuatro ejecuciones completaron `523/523` y `0` errores terminales. La variación entre corridas supera la diferencia observada entre condiciones, por lo que no se estableció un beneficio reproducible atribuible al transporte por hilo y no se modifica el runtime de producción.

### Próximo desarrollo controlado

- [x] Benchmark productivo base `8 / 16 / 28` con cobertura viva `523 / 519 / 4`.
- [x] Comparación de workers de categoría cerrada: `8` conserva el valor validado; `12/16` no mostraron mejora reproducible.
- [x] Comparación JSF cerrada: con `JSF HTTP=8`, las corridas `PAGE=4` midieron `42.85s` y `56.49s`, mientras `PAGE=2` midió `53.43s`; todas conservaron `523/523` y `0` errores.
- [x] No se identificó beneficio reproducible de `PAGE=4`; se conserva `SCRAPING_JSF_PAGE_WORKERS=2` como default productivo validado.
- [x] Diagnóstico de sesiones HTTP por hilo cerrado: TRUE `41.15s` y `52.79s`; FALSE `53.43s` y `43.93s`; cuatro corridas con `523/523` y `0` errores.
- [x] No se estableció beneficio reproducible de sesiones por hilo; producción conserva el transporte HTTP actual.
- [x] Control benchmark-only para paralelismo de páginas de categoría añadido con default `1`; la prueba verifica concurrencia real y conservación del orden lógico del resultado.
- [x] Validar localmente el ajuste de la prueba tras eliminar la asunción de orden de llamadas concurrentes; Quality CI posterior confirmó el estado en verde.
- [x] Cerrar la comparación de `FCM_BENCH_CATEGORY_PAGE_WORKERS` bajo `8 / 16 / 28` + JSF `8 / 2`: tres corridas por condición, cobertura completa y `0` errores; no se estableció beneficio reproducible
- [x] Determinar por qué el máximo HTTP en vuelo del benchmark queda en `16` pese al límite configurado de `28`: lo limita la paralelización aguas arriba, no el semáforo global.
- [x] Separar el coste de requests de categoría, JSF y detalle por percentiles y por etapa mediante telemetría de P50/P95/P99, máximos en vuelo por clase y tiempos agregados.
- [x] Los diagnósticos controlados justificaron elevar detail workers a `24`: ambas parejas reales redujeron el wall-clock y mantuvieron cobertura completa y cero errores.
- [x] El E2E productivo completo con `24` workers validó scraping, SQLite, relaciones, run metrics e historial.
- [x] Ejecutar y repetir la validación FULL de referencia con el runtime productivo `8 / 24 / 28`; ambas ejecuciones mantuvieron cobertura completa, persistencia consistente, historial aplicado, `0` retries y `0` errores terminales.

## Progreso de UI

### Smoke operativo de GUI

El 2026-09-20 se realizó y confirmó el smoke test manual del flujo de escritorio sobre `main`: arranque desde `app.py`, carga de `database/catalog.db` sin scraping automático, navegación de catálogo, búsqueda/filtros, apertura de **Actualizar catálogo** y **Historial**, ejecución FULL desde la GUI, progreso/tiempo durante la ejecución, resumen final, detalle e historial aplicado. No se observaron incidencias visibles.

Esta comprobación es complementaria a la suite automatizada y al E2E real; no modifica los criterios de cobertura ni la configuración productiva.

El pipeline FULL mantiene 48 pasos lógicos. La colección emite progreso por finalización de categorías (`1..24`), el enrichment emite callbacks intermedios (`25..47`) y el runner finaliza en `48/48`.

Esta semántica está cubierta por pruebas y no afecta cobertura ni persistencia. La granularidad de progreso durante enrichment queda implementada y validada como una mejora de UX contenida.

## Checklist maestro

### Corrección funcional

- [x] FULL real de 24 categorías.
- [x] Cobertura completa contra `expected_count` vigente de cada categoría.
- [x] Referencia operativa actual: 523 apariciones / 519 productos únicos / 4 multi-categoría / 523 relaciones.
- [x] Referencia viva verificada: `523 / 519 / 4`; se reemplaza cuando un FULL posterior, completo, consistente y sin errores queda verificado.
- [x] cobertura completa.
- [x] `coverage_gap=0`.
- [x] 0 errores invalidantes.
- [x] protección FULL/prune.
- [x] reconciliación desde el FULL válido más reciente.

### Recuperación y persistencia

- [x] paginación.
- [x] JSF.
- [x] páginas incompletas.
- [x] códigos/SKU.
- [x] detalle.
- [x] cobertura.
- [x] FULL incompleto.
- [x] FULL fallido.
- [x] precedencia SUCCESS vs ERROR.
- [x] atomicidad y rollback.
- [x] recuperación histórica.
- [x] relaciones normalizadas.
- [x] historial previo preservado.
- [x] idempotencia de segunda ejecución sobre la misma SQLite.

### Consolidación arquitectónica

- [x] motores de paginación, JSF y métricas consolidados.
- [x] recuperación de precio/cobertura/código integrada en las implementaciones canónicas.
- [x] `ScrapingConfig` y workers centralizados.
- [x] factory canónica de producción validada.
- [x] patches/fachadas obsoletos retirados tras auditoría.

### Calidad

- [x] Ruff.
- [x] Pyright.
- [x] suite completa en verde.
- [x] pruebas de límites arquitectónicos.
- [x] pruebas de bootstrap/reconciliación.
- [x] pruebas de cache concurrente.
- [x] pruebas de progreso runner.
- [x] pruebas de progreso de enrichment y ejecución paralela.
- [x] prueba de contrato de telemetría de enrichment.
- [x] FULL real posterior a la consolidación.

### UI / operación

- [x] carga inicial desde `catalog.db`.
- [x] bootstrap sin scraping automático.
- [x] historial persistente.
- [x] detalle de cambios ordenado por código.
- [x] indicador de versión actualmente aplicada.
- [x] filtros de catálogo y stock.

## Estado posterior a release

No existen pendientes técnicos bloqueantes en el baseline validado. La configuración productiva queda establecida en `8 / 24 / 28` + JSF `2` + category-page `1`; el cambio de concurrencia quedó cerrado con E2E post-cambio repetido.

Cualquier optimización futura de red, scraping, persistencia o concurrencia se tratará como un cambio nuevo: benchmark controlado, validación de cobertura/persistencia y actualización del checkpoint antes de considerarlo parte del baseline.

## Auditorías no bloqueantes cerradas

- [x] benchmark específico de contención/latencia SQLite ejecutado sin errores ni latencias que justifiquen cambios de runtime;
- [x] mayor granularidad de callbacks de progreso durante enrichment;
- [x] benchmark de red separado para detalle con comparación cruzada 16/24;
- [x] fábricas de compatibilidad auditadas como delegados finos; se conservan por posible consumo externo.
- [x] validación E2E real de producción con 24 workers de detalle;

Estos puntos no invalidan el estado funcional validado. Cualquier cambio futuro sobre scraping, persistencia o concurrencia debe volver a comprobar las invariantes de cobertura del inventario vivo. La referencia operativa actual es `24 / 523 / 519 / 4` bajo `8 / 24 / 28`; esta referencia debe actualizarse después de cada FULL completo, consistente y sin errores verificado.
