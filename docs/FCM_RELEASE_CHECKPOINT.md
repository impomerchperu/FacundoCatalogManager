# FCM — Release checkpoint

Fecha de actualización documental: 2026-09-24  
Branch oficial: `main`

## Estado

El baseline funcional permanece cerrado y protegido en `main`. El último estado validado incorpora las optimizaciones de arranque y GUI posteriores al cierre funcional, sin modificar las invariantes de scraping, persistencia ni cobertura.

Último código funcional validado: `57a34711d3ddc0806d5d83685ef98de3a7e0451d` (`fix(test): organize scraping dialog imports`).

## Referencias funcionales

### Snapshot histórico protegido

- 24 categorías.
- 534 apariciones producto-categoría.
- 530 productos únicos.
- 4 productos en múltiples categorías.
- 534 relaciones producto-categoría.

Este snapshot se conserva como referencia histórica y diagnóstico de deriva del inventario vivo.

### Referencia operativa actual

El último FULL productivo completo validado contra el inventario vivo confirmó:

- 24 categorías.
- 523 apariciones producto-categoría.
- 519 productos únicos.
- 4 productos en múltiples categorías.
- 523 relaciones producto-categoría.
- `coverage_complete=1`.
- `coverage_gap=0`.
- `error_count=0`.

La regla operativa es ahora comparar cada FULL con los totales publicados por el sitio en esa ejecución; el snapshot 534/530/4 no bloquea por sí solo una ejecución válida.
- Un FULL incompleto no ejecuta prune destructivo.
- Un FULL fallido o incompleto no sustituye al último FULL válido para recuperación.

## Persistencia e historial

### Referencia histórica protegida

La validación histórica de la base real conserva:

- SQLite `PRAGMA integrity_check = ok`.
- Snapshot de catálogo: `530` productos / `534` relaciones.
- Historial preservado: `156` registros.
- Detalles de cambios preservados: `52,816`.
- Última historia aplicada de ese checkpoint histórico: `history_id=191`.

### Estado operativo más reciente de stock por color

La aplicación dirigida conjunta sobre las 24 categorías actualizó la base real con:

- `history_id=201`.
- `516` productos actualizados.
- `3` sin cambios.
- `0` creados.
- `0` eliminados.
- `523` productos/apariciones verificadas con `color_stock`.
- `523` verificaciones posteriores contra SQLite y `0` inconsistencias.

Este estado corresponde a la aplicación dirigida de stock por color y no reemplaza la referencia histórica de cobertura FULL.

## Runtime validado

- Categorías: `8` workers.
- Detalle: `16` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8`.
- Timeout: `20s`.
- Reintentos máximos: `3`.

El benchmark real de concurrencia más reciente validó `24 / 523 / 519 / 4`, `337` solicitudes HTTP, `0` reintentos, `0` errores HTTP terminales y `83.65s` de pipeline con el patrón `8/16/28`. El FULL real secuencial posterior validó las mismas `24 / 523 / 519 / 4` y las invariantes de stock por color en `335.34s`. Los `534 / 530 / 4` permanecen como snapshot histórico.

## Calidad

Validación del baseline funcional actual sobre `main`:

- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Suite local actual: `488 passed, 10 deselected`.
- Validación estática actual: Ruff limpio y Pyright `0 errors, 0 warnings, 0 informations`.
- E2E real: `1 passed`, cobertura `24 / 523 / 519 / 4`, `0` productos sin `color_stock`, `0` inconsistencias y `0` errores HTTP terminales.
- Benchmark real de concurrencia: `1 passed` en `83.65s`, con `24 / 523 / 519 / 4`, `337` requests y `0` reintentos.

Los cambios funcionales y de documentación posteriores quedaron cubiertos por validaciones locales y por Quality CI. En el último run de Quality asociado a `main`, Ruff, Pyright y Pytest terminaron correctamente; `live-catalog` quedó omitido de forma intencional en el CI rápido.

## GUI y rendimiento de arranque

Hardening de cierre: el cierre de `MainWindow` espera la finalización de los workers de carga/bootstrap de catálogo activos y existe una prueba focal para este contrato.

La fase de rendimiento de escritorio quedó cerrada con las siguientes garantías:

- El catálogo persistido se lee fuera del hilo de la interfaz.
- El bootstrap de reconciliación se ejecuta fuera del hilo de la interfaz.
- La tabla grande se renderiza progresivamente durante la carga inicial.
- La ventana se muestra antes de finalizar esas operaciones.
- Búsqueda, stock y categorías filtran filas ya renderizadas, sin reconstruir las 519+ filas en cada interacción.
- El panel de categorías se refluye de forma síncrona al activar **Filtrar Categorías** para evitar el retraso visual de un ciclo de eventos.
- Validación GUI posterior: la aplicación abrió correctamente y los filtros quedaron operativos.

Estos cambios no modifican el scraping, la persistencia, el modelo de cobertura ni la política de prune.

## Stock por color

La aplicación ya persiste `color_stock` como parte del producto y la columna **Stock** muestra `color → cantidad` cuando existe una asociación demostrable. La extracción usa, en este orden, datos directos de variantes/atributos, nombres de color declarados y los valores de stock de la tarjeta de categoría cuando sus cantidades pueden asociarse sin ambigüedad.

No se reparte artificialmente un stock total entre colores. Cuando el sitio publica nombres de colores pero no publica cantidades por color, se conserva el stock total y no se inventan asociaciones. Cuando la tarjeta publica varias cantidades y la página de detalle permite identificar exactamente el mismo número de colores, el enriquecimiento combina ambas fuentes por orden y conserva la suma como `stock` total.

Quality `#2227` validó los nuevos patrones de etiquetas `Colores disponibles`, `disponible en colores`, `5 colores`, `Color:` y la unión de nombres de detalle con stock múltiple de categoría.

### Validación real de stock por color y tabla de productos

El 2026-09-20 se validó de extremo a extremo una categoría real (`Bolsas / Mochilas`) sobre una SQLite temporal, sin modificar `database/catalog.db`. La prueba confirmó:

- extracción de al menos un producto con múltiples colores y stock explícito por color;
- persistencia exacta de `products.color_stock` y del `stock` total como suma de sus cantidades;
- lectura posterior mediante `ProductRepository`;
- representación del mismo `color → cantidad` en la columna **Stock** de `ProductTable`;
- historial de la ejecución en estado `SUCCESS` con `applied_at`.

Resultado local: `1 passed in 6.86s`, con Ruff limpio y Pyright `0 errors, 0 warnings, 0 informations`. La aplicación completa sobre las 24 categorías confirmó posteriormente `523` productos/apariciones con `color_stock`.

### Aplicación real dirigida sobre `database/catalog.db`

El 2026-09-20 se ejecutó una sincronización dirigida de la categoría real `Bolsas / Mochilas` contra la base de producción local `database/catalog.db`, con respaldo previo de la base y sin prune FULL. La ejecución terminó en `SUCCESS` y creó la historia aplicada `history_id=200`.

Se confirmaron 3 productos con stock explícito por color:

- `FB-6001`: stock `13395`; Azul `4002`, Gris `3415`, Negro `4000`, Rojo `1978`.
- `FB-6002`: stock `2693`; Azul `528`, Gris `124`, Negro `1686`, Rojo `355`.
- `FB-6005`: stock `1356`; Azul `330`, Negro `4`, Rojo `1022`.

La lectura independiente posterior desde SQLite confirmó exactamente esos valores y `3` productos con `color_stock` no vacío en la base real. La verificación integrada del utilitario también releyó `FB-6005` mediante `ProductRepository` después del commit y confirmó coincidencia exacta.

Esta aplicación dirigida es una validación puntual del mecanismo de persistencia; no sustituye ni altera la referencia de cobertura FULL `24 / 523 / 519 / 4`.

### Aplicación completa de stock por color sobre las 24 categorías

El 2026-09-20 se ejecutó una sincronización dirigida conjunta sobre las 24 categorías reales contra `database/catalog.db`, sin habilitar prune FULL. El resultado fue:

- `24/24` categorías procesadas.
- `523/523` apariciones esperadas y encontradas.
- `519` productos únicos.
- `516` actualizados y `3` sin cambios.
- `0` creados y `0` eliminados.
- historia aplicada `history_id=201`.
- `523` apariciones con `color_stock`.
- `24/24` categorías con productos con stock por color.
- `523` verificaciones posteriores contra SQLite.
- `0` inconsistencias entre extracción y persistencia.

Este resultado demuestra que el objetivo de stock por color quedó aplicado al flujo real del catálogo completo. La ausencia de `color_stock` en una ejecución futura sigue siendo válida únicamente cuando el origen no publique cantidades por color de forma demostrable; no se generan asociaciones artificiales.

## Arquitectura

- `ImageHash` es la implementación canónica de SHA-256 para archivos de imagen.
- `ImageDownloader.hash_file()` delega en `ImageHash`.
- `ImageAuditService` delega en `ImageHash`.
- `ContentHash` y `ProductHashService` permanecen separados porque sus contratos no son equivalentes.
- Las fábricas de compatibilidad son delegados finos hacia la fábrica canónica.
- Las herramientas legacy de limpieza destructiva están bloqueadas.
- No se modificó la extracción, paginación, concurrencia, SQLite, recuperación ni prune durante la auditoría de imágenes.

## Documentación operativa

El README ahora documenta explícitamente:

```powershell
python -m pytest -q
```

Las pruebas contra el sitio real se excluyen mediante el marcador `real_site`.

La prueba FULL real sigue disponible por separado y no forma parte de la suite rápida de CI.

## Cierre previo a release

La recuperación visual del historial quedó cerrada en `main`: `APLICADO` con fecha/hora de aplicación, `NO APLICADO` para versiones exitosas superadas y `ERROR` para ejecuciones fallidas. La prueba focal quedó en `9 passed` y Quality `#2210` terminó en `success`.

## Smoke test manual de GUI

- [x] Arranque real mediante `python app.py`.
- [x] Catálogo cargado desde `database/catalog.db` sin scraping automático.
- [x] Tabla, navegación y búsqueda/filtros operativos.
- [x] Botones **Actualizar catálogo** y **Historial** disponibles.
- [x] Flujo FULL ejecutado desde la GUI.
- [x] Progreso y tiempo transcurrido observados durante la ejecución.
- [x] Resumen final de la actualización revisado.
- [x] Detalle de la ejecución revisado.
- [x] Historial revisado y ejecución aplicada confirmada.
- [x] Sin incidencias visibles durante el smoke test.

Esta validación manual se completó el 2026-09-20 sobre `main` y no modificó el runtime.

1. [x] Sincronizar el último HEAD remoto.
2. [x] Ejecutar Ruff.
3. [x] Ejecutar Pyright.
4. [x] Ejecutar `python -m pytest -q`.
5. [x] Confirmar `git status --short` vacío.
6. [x] Quality #2213: success sobre `6e9739f`; el job `test` ejecutó correctamente Ruff, Pyright y Pytest. `live-catalog` quedó `skipped` de forma intencional.
7. [x] FULL real ejecutado y validado: el sitio publicó 523 apariciones esperadas, 11 menos que la referencia histórica 534.
8. [x] Pruebas reales ajustadas para usar los totales publicados por las categorías como fuente de verdad de cobertura, conservando 534/530/4 como referencia histórica.
9. [x] E2E productivo validado: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, cobertura completa y cero errores HTTP terminales.
10. [x] FULL real independiente de cobertura completado: 24/24 categorías, 523/523 apariciones, 519 únicos, 4 multi-categoría, 0 gaps y 0 códigos sin código.
11. [x] Idempotencia validada sobre la misma SQLite; el resultado quedó incorporado al baseline y posteriormente documentado en commits sin cambios de runtime. Quality CI `#2194` confirmó el baseline en `ef8d9c8`; los commits documentales posteriores no cambiaron código funcional ni runtime.
12. [x] Stock por color aplicado a la base real mediante sincronización dirigida de `Bolsas / Mochilas`; historia `200`, 3 productos con `color_stock` y verificación independiente posterior desde SQLite.
13. [x] Pyright y suite completa local posteriores a la aplicación real: `0 errors, 0 warnings, 0 informations`; `470 passed, 10 deselected`.
14. [x] Stock por color aplicado a las 24 categorías reales mediante sincronización dirigida conjunta: `24/24` categorías, `523/523` apariciones, `519` productos únicos, `0` errores, `0` eliminados, `523` apariciones con `color_stock`, `24/24` categorías con productos con stock por color, `523` verificaciones SQLite y `0` inconsistencias; historia `201`.
15. [x] La cobertura FULL real y el benchmark de concurrencia quedan protegidos por invariantes explícitas de `color_stock`: ningún producto extraído puede perder `color_stock`, el `stock` debe coincidir con la suma por color y las 24 categorías deben quedar representadas; Ruff, Pyright y la suite local posterior terminaron correctamente (`473 passed, 10 deselected`).
16. [x] Regresiones locales específicas de `color_stock` añadidas para detectar cambios de cantidades, reportarlos como `Stock por color` y preservar idempotencia cuando los valores no cambian; Ruff y Pyright limpios y suite local en `473 passed, 10 deselected`.
17. [x] FULL real posterior a las invariantes de `color_stock`: `1 passed`, `24/24` categorías, `523/523` apariciones, `519` únicos, `0` productos sin `color_stock`, `0` inconsistencias `stock/color_stock`, `24` categorías con stock por color, `0` errores y `0` gaps. Duración observada: `335.34s`.
18. [x] Benchmark real de concurrencia posterior a la protección de `color_stock`: `1 passed` en `83.65s`, `24/24` categorías, `523/523` apariciones, `519` únicos, `0` productos sin `color_stock`, `0` inconsistencias, `0` retries y `0` errores HTTP terminales, con `8` workers de categoría, `16` de detalle y `28` HTTP.
19. [x] Retirados los utilitarios temporales de aplicación manual de `color_stock`; el comportamiento soportado queda exclusivamente en el pipeline normal de scraping, persistencia y GUI, ya validado para las 24 categorías.

Hallazgo de idempotencia: las altas iniciales podían quedar sin `content_hash`, mientras que la segunda sincronización calculaba ese hash antes de comparar. Se corrigió la inicialización del hash antes de la clasificación para evitar un `UPDATED` espurio. La idempotencia ya quedó validada en CI con una SQLite persistente compartida por dos sincronizaciones consecutivas; no se requiere otro FULL real para cerrar este punto.

La mejora de progreso ya quedó validada sin requerir otro FULL real. El benchmark aislado de contención/latencia SQLite también quedó ejecutado sin evidencia que justifique cambios transaccionales. Cualquier futura modificación de scraping, persistencia o concurrencia deberá conservar las invariantes actuales y seguir el ciclo benchmark + validación FULL.
