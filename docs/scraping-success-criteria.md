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

Los contadores HTTP, reintentos y tiempos agregados son métricas de diagnóstico. Los tiempos acumulados de solicitudes concurrentes no deben compararse directamente con el tiempo de pared.

## Rendimiento

La configuración de producción validada es:

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
- Suite no-real-site actual: `437 passed, 2 deselected`.
- Pruebas de bootstrap/reconciliación: `15 passed`.
- Batería scraping/runner/cache/progreso: validada.
- Telemetría de enrichment por categoría: instrumentada y cubierta por prueba.
- FULL/E2E de producción: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, configuración `8 / 16 / 28`, `337` solicitudes HTTP, duración `90.78s`.
- Quality CI #2018: `success` sobre el HEAD documental validado `e45a4a4`.
- Snapshot histórico preservado: `24 / 534 / 530 / 4`.
- Smoke de bootstrap sobre copia de la base real: `530 / 534`, usando el FULL más reciente válido.

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

## Pendientes no bloqueantes

- [x] benchmark específico de contención/latencia SQLite ejecutado sin errores ni latencias que justifiquen cambios de runtime;
- [x] mayor granularidad de callbacks de progreso durante enrichment;
- [x] benchmark de red separado para detalle con comparación cruzada 16/24;
- [x] fábricas de compatibilidad auditadas como delegados finos; se conservan por posible consumo externo.
- [x] validación E2E real de producción después del cambio de concurrencia a 16 workers;

Estos puntos no invalidan el estado funcional validado. Cualquier cambio futuro sobre scraping, persistencia o concurrencia debe volver a comprobar las invariantes de cobertura del inventario vivo. La referencia operativa actual es `24 / 523 / 519 / 4` bajo `8 / 16 / 28`; el snapshot `24 / 534 / 530 / 4` se conserva como diagnóstico histórico.
