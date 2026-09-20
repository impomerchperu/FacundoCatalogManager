# Criterios de éxito del scraping FULL

Fecha de validación del último checkpoint maestro: 2026-09-20  
Branch oficial: `main`

## Objetivo

Una ejecución FULL del catálogo debe ser correcta, completa y segura para sincronizar la base de datos. El rendimiento es una optimización secundaria y nunca debe reducir las garantías de cobertura o persistencia.

## Criterio funcional autorizado

Una ejecución FULL válida cubre las 24 categorías y alcanza simultáneamente los totales publicados por las propias categorías en esa ejecución. El snapshot histórico `534 / 530 / 4` se conserva como referencia diagnóstica, no como contrato rígido del inventario vivo.

La prueba real debe tratar una variación de inventario (altas/bajas/movimientos de productos) como deriva del sitio y comprobar en su lugar que cada categoría se extrae sin gaps respecto de su `expected_count`, que el total encontrado coincide con ese total vigente y que la persistencia mantiene las mismas cantidades observadas.

- `523` apariciones observadas en la última referencia operativa.
- `519` productos únicos observados en la última referencia operativa.
- `4` productos presentes en múltiples categorías.
- `523` relaciones producto-categoría.
- `coverage_complete=1`.
- `coverage_gap=0`.
- `error_count=0`.

Estos números son la referencia operativa actual; `534 / 530 / 4` se conserva como snapshot histórico de diagnóstico.

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

La validación realizada sobre la base real confirmó:

- integridad SQLite: `ok`;
- catálogo: `530` productos;
- relaciones: `534` producto-categoría;
- historiales: `156`;
- detalles de cambios: `52.816`;
- metadatos `initialized=1` y `history_recovery_applied=1`.

En esa base, el FULL más reciente fue `run 34` y coincidió exactamente con `534 / 530 / 4`. Sus ocurrencias estuvieron enlazadas sin faltantes y el catálogo no tuvo productos ni relaciones extra respecto del run.

## Recuperación de red

La recuperación de categorías, paginación, JSF, páginas incompletas, códigos y detalle existe para aumentar la probabilidad de completar el FULL ante fallos transitorios. La cobertura final y la integridad del resultado son las condiciones que determinan si el run es utilizable.

Los contadores HTTP, reintentos y tiempos agregados son métricas de diagnóstico. La instrumentación conserva máximo en vuelo por clase (`category`, `jsf`, `detail`, `other`), percentiles P50/P95/P99 y tiempos agregados por etapa. Los tiempos acumulados de solicitudes concurrentes no deben compararse directamente con el tiempo de pared.

## Rendimiento

La configuración de producción validada es:
El número de workers internos de paginación JSF también está centralizado en `ScrapingConfig`; el valor productivo actual permanece en `2`.


- categoría: `8` workers;
- detalle: `16` workers;
- HTTP: `28` workers;
- JetSmartFilters HTTP: `8` concurrentes.

La evidencia disponible muestra que el coste principal está en red, especialmente en extracción de categorías y enriquecimiento de detalle. El detalle se ha protegido con coalescencia concurrente de futures y pruebas específicas.

La telemetría de enrichment por categoría registra `requested`, `skipped`, `total_seconds`, `submit_seconds` y `wait_seconds` sin modificar la semántica del scraping. Está cubierta por una prueba de contrato específica y permite separar el tiempo de cada categoría de las métricas agregadas.

No existe una cifra única de tiempo de pared que deba tratarse como requisito funcional: los benchmarks dependen del estado del sitio remoto y de la red. Cualquier optimización debe conservar cobertura completa respecto del inventario vivo y ser validada nuevamente. El snapshot `24 / 534 / 530 / 4` sigue siendo diagnóstico, no contrato rígido.

Un benchmark específico de contención de SQLite no es requisito para la corrección actual y queda como optimización futura, no como bloqueo de la funcionalidad validada.

## Deriva del inventario vivo

La validación real más reciente observó `523` apariciones esperadas frente al snapshot histórico `534`. Esto no demuestra por sí mismo una regresión del scraper: `expected_count` se obtiene del sitio y puede cambiar legítimamente. El criterio de cobertura se basa ahora en la consistencia interna de la ejecución actual; el baseline histórico permanece visible para detectar desviaciones, no para bloquear el test por sí solo.

## Resultado del benchmark SQLite

Se ejecutó un benchmark aislado sobre SQLite temporal con 530 productos, WAL, `synchronous=NORMAL` y `busy_timeout=30000ms`.

- 0 errores en los cuatro escenarios.
- Escrituras P95: 0.58–5.70 ms.
- Lecturas P95: <= 0.417 ms.
- Máximo puntual de escritura observado: 16.52 ms.
- No se modificó `database/catalog.db`.
- No se modifica el alcance transaccional ni la configuración SQLite por este resultado.

## Estado de ingeniería validado

- Ruff: limpio.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Suite no-real-site actual: `439 passed, 8 deselected`.
- Pruebas de bootstrap/reconciliación: `15 passed`.
- Batería scraping/runner/cache/progreso: validada.
- Telemetría de enrichment por categoría: instrumentada y cubierta por prueba.
- FULL/E2E de producción: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, configuración `8 / 16 / 28`, `337` solicitudes HTTP, duración `90.78s`.
- Quality CI reciente sobre `main`: ejecuciones `2032`–`2036` completadas en `success`; la revisión posterior del benchmark está siendo procesada por CI.
- Snapshot histórico preservado: `24 / 534 / 530 / 4`.
- Smoke de bootstrap sobre copia de la base real: `530 / 534`, usando el FULL más reciente válido.

## Benchmark de rendimiento actual

La ejecución real más reciente del benchmark de concurrencia, sin modificar producción, usó `8` workers de categoría, `16` de detalle y `28` HTTP:

- `24` categorías.
- `523` apariciones esperadas y encontradas.
- `519` productos únicos.
- `4` multi-categoría.
- collection wall: `51.60s`.
- enrichment wall: `43.50s`.
- pipeline wall: `97.31s`.
- `337` solicitudes HTTP.
- máximo observado en vuelo: `16`.
- `278` solicitudes de detalle.
- `245` productos omitieron detalle.
- `0` espera del semáforo de detalle.
- `0` reintentos y `0` errores terminales.

Los requests más lentos del muestreo fueron páginas de categoría, aproximadamente entre `8.19s` y `9.52s`. La evidencia del código explica el máximo global de `16`: no representa saturación del semáforo de `28`, sino la capacidad de los productores aguas arriba. Con `8` workers de categoría y `2` workers JSF por categoría, la paginación JSF puede generar hasta `8 × 2 = 16` requests; el enrichment también tiene `16` workers de detalle.

### Instrumentación del benchmark controlado

Referencia real adicional del 2026-09-20: el baseline `8 / 2 / 16 / 28` volvió a completar `523/523`, `519` únicos y `4` multi-categoría, sin reintentos ni errores terminales; observó collection `54.64s`, enrichment `48.61s` y pipeline `105.32s`, con P50/P95/P99 de categoría `6.988/9.799/10.026s`, JSF `4.802/7.413/7.578s` y detalle `2.531/4.072/4.985s`. El intento controlado con `12` workers de categoría terminó con `KeyboardInterrupt` antes de producir resultado; queda como experimento no concluyente y no justifica cambiar el runtime.

La comparación controlada de colección confirmó que `12` workers produjo `55.40s` y `56.12s` en dos corridas, mientras `16` workers produjo `59.40s`; por ello no hay evidencia para aumentar `SCRAPING_CATEGORY_WORKERS` desde `8`. Las dos corridas preliminares del experimento `JSF_PAGE_WORKERS=4` (47.42s y 54.68s) no son comparables con producción porque el harness no propagaba `jsf_http_concurrency` y el scraper quedaba accidentalmente limitado a `4` concurrentes JSF, aunque producción usa `8`. El benchmark se corrigió para recibir explícitamente ambos parámetros. La primera comparación válida, con `JSF HTTP=8`, mantuvo cobertura `523/523` y `0` errores: `JSF PAGE=4` produjo `42.85s` de collection wall, frente a `53.43s` con `JSF PAGE=2`, una diferencia de `10.58s` (`~19.8%`). Una repetición con el mismo contrato volvió a completar `523/523` y `0` errores, pero `PAGE=4` produjo `56.49s`, frente a `53.43s` de `PAGE=2`. Además, la corrida lenta de `PAGE=4` volvió a presentar latencia de categoría comparable o incluso menor (P95 `9.531s`), lo que refuerza que el wall-clock está dominado por la variabilidad concurrente de la red y no permite atribuir la primera mejora a los page-workers. Por tanto, `PAGE=4` no muestra un beneficio reproducible y no justifica cambiar el default productivo de `2`.

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
- [x] Validar localmente el ajuste de la prueba tras eliminar la asunción de orden de llamadas concurrentes; queda pendiente la confirmación equivalente en Quality CI.
- [x] Cerrar la comparación de `FCM_BENCH_CATEGORY_PAGE_WORKERS` bajo `8 / 16 / 28` + JSF `8 / 2`: tres corridas por condición, cobertura completa y `0` errores; no se estableció beneficio reproducible
- [x] Determinar por qué el máximo HTTP en vuelo del benchmark queda en `16` pese al límite configurado de `28`: lo limita la paralelización aguas arriba, no el semáforo global.
- [x] Separar el coste de requests de categoría, JSF y detalle por percentiles y por etapa mediante telemetría de P50/P95/P99, máximos en vuelo por clase y tiempos agregados.
- [ ] Solo después de identificar una oportunidad concreta y reproducible, aplicar un cambio de runtime.
- [ ] Reejecutar benchmark y FULL real después de cualquier cambio de runtime.
- [ ] Revalidar persistencia, historial, cobertura y prune en un E2E productivo posterior.

## Progreso de UI

El pipeline FULL mantiene 48 pasos lógicos. La colección emite progreso por finalización de categorías (`1..24`), el enrichment emite callbacks intermedios (`25..47`) y el runner finaliza en `48/48`.

Esta semántica está cubierta por pruebas y no afecta cobertura ni persistencia. La granularidad de progreso durante enrichment queda implementada y validada como una mejora de UX contenida.

## Checklist maestro

### Corrección funcional

- [x] FULL real de 24 categorías.
- [x] Cobertura completa contra `expected_count` vigente de cada categoría.
- [x] Referencia operativa actual: 523 apariciones / 519 productos únicos / 4 multi-categoría / 523 relaciones.
- [x] Snapshot histórico 534/530/4 preservado como diagnóstico.
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

## Pendientes de rendimiento

El baseline funcional permanece protegido. El desarrollo activo continúa únicamente en diagnóstico y optimización controlada de red/categorías; no se modifica todavía la configuración productiva `8 / 16 / 28`.

## Pendientes no bloqueantes

- [x] benchmark específico de contención/latencia SQLite ejecutado sin errores ni latencias que justifiquen cambios de runtime;
- [x] mayor granularidad de callbacks de progreso durante enrichment;
- [x] benchmark de red separado para detalle con comparación cruzada 16/24;
- [x] fábricas de compatibilidad auditadas como delegados finos; se conservan por posible consumo externo.
- [x] validación E2E real de producción después del cambio de concurrencia a 16 workers;

Estos puntos no invalidan el estado funcional validado. Cualquier cambio futuro sobre scraping, persistencia o concurrencia debe volver a comprobar las invariantes de cobertura del inventario vivo. La referencia operativa actual es `24 / 523 / 519 / 4` bajo `8 / 16 / 28`; el snapshot `24 / 534 / 530 / 4` se conserva como diagnóstico histórico.
