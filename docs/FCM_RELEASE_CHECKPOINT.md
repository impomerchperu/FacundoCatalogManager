# FCM — Release checkpoint

Fecha: 2026-09-20  
Branch oficial: `main`

## Estado

El baseline funcional está cerrado y protegido en `main`; la última mejora funcional añade granularidad de progreso durante enrichment sin modificar las invariantes de scraping, persistencia o concurrencia.

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

La validación de la base real documentada conserva:

- SQLite `PRAGMA integrity_check = ok`.
- Último FULL válido: run `34`.
- Catálogo: `530` productos / `534` relaciones.
- Historial preservado: `156` registros.
- Detalles de cambios preservados: `52,816`.
- Última historia aplicada validada: `history_id=191`.
- Clasificación de la última historia aplicada: `0 created / 0 updated / 530 unchanged / 0 deleted`.

## Runtime validado

- Categorías: `8` workers.
- Detalle: `16` workers.
- HTTP: `28` workers.
- JetSmartFilters HTTP: `8`.
- Timeout: `20s`.
- Reintentos máximos: `3`.

El E2E real de producción más reciente validó `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, `337` solicitudes HTTP, `0` reintentos y `0` errores HTTP terminales, con `100.33s` de wall-clock en SQLite aislada. Esta es la referencia operativa actual; los `534 / 530 / 4` permanecen como snapshot histórico.

## Calidad

Validación local del baseline funcional sobre `main` (`280c32f`, antes de los commits documentales posteriores):

- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Suite no-real-site: `454 passed, 8 deselected`.
- E2E real: `1 passed`, cobertura `24 / 523 / 519 / 4`, historial aplicado y `0` errores HTTP terminales.

Los últimos cambios de código solo reorganizaron tres pruebas de imágenes para que sean funciones pytest convencionales, aislaron `ImageSync` del repositorio físico local y corrigieron el comando de suite documentado en README. La validación documentada de la suite no-real-site quedó verde con `437 passed, 8 deselected`; las comprobaciones estáticas también quedaron limpias.

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
6. [x] Quality #2210: success sobre `aa412b1`; el baseline actual mantiene Ruff, Pyright y Pytest verdes (`454 passed, 8 deselected`).
7. [x] FULL real ejecutado y validado: el sitio publicó 523 apariciones esperadas, 11 menos que la referencia histórica 534.
8. [x] Pruebas reales ajustadas para usar los totales publicados por las categorías como fuente de verdad de cobertura, conservando 534/530/4 como referencia histórica.
9. [x] E2E productivo validado: `24 / 523 / 519 / 4`, DB `519 / 523`, historial aplicado, cobertura completa y cero errores HTTP terminales.
10. [x] FULL real independiente de cobertura completado: 24/24 categorías, 523/523 apariciones, 519 únicos, 4 multi-categoría, 0 gaps y 0 códigos sin código.
11. [x] Idempotencia validada sobre la misma SQLite; el resultado quedó incorporado al baseline y posteriormente documentado en commits sin cambios de runtime. Quality CI `#2194` confirmó el baseline en `ef8d9c8`; los commits documentales posteriores no cambiaron código funcional ni runtime.

Hallazgo de idempotencia: las altas iniciales podían quedar sin `content_hash`, mientras que la segunda sincronización calculaba ese hash antes de comparar. Se corrigió la inicialización del hash antes de la clasificación para evitar un `UPDATED` espurio. La idempotencia ya quedó validada en CI con una SQLite persistente compartida por dos sincronizaciones consecutivas; no se requiere otro FULL real para cerrar este punto.

La mejora de progreso ya quedó validada sin requerir otro FULL real. El benchmark aislado de contención/latencia SQLite también quedó ejecutado sin evidencia que justifique cambios transaccionales. Cualquier futura modificación de scraping, persistencia o concurrencia deberá conservar las invariantes actuales y seguir el ciclo benchmark + validación FULL.
