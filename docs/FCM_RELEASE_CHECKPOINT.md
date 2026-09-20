# FCM — Release checkpoint

Fecha: 2026-09-19  
Branch: `feature/scraping-performance-recovery`

## Estado

La rama se encuentra en fase de cierre previo a release. El baseline funcional está protegido y las últimas modificaciones de esta etapa son de pruebas y documentación; deben quedar validadas localmente antes de cerrar el release checkpoint.

## Baseline funcional protegido

- 24 categorías.
- 534 apariciones producto-categoría.
- 530 productos únicos.
- 4 productos en múltiples categorías.
- 534 relaciones producto-categoría.
- `coverage_complete=1`.
- `coverage_gap=0`.
- `error_count=0`.
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

El E2E real de producción ya validó `24 / 534 / 530 / 4`, DB `530 / 534`, historial aplicado y cero reintentos HTTP en SQLite aislada, con `113.97s` de wall-clock en esa ejecución concreta.

## Calidad

Validación local reportada para el código anterior a la última normalización de tres tests de imágenes:

- Ruff: limpio.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Suite no-real-site: `431 passed, 2 deselected`.
- Batería focal de imágenes: `10 passed`.

Los últimos cambios de código desde ese resultado solo reorganizan tres pruebas para que sean funciones pytest convencionales y corrigen el comando de suite documentado en README. El estado final debe validarse nuevamente con Ruff, Pyright y la suite no-real-site.

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
python -m pytest -q --ignore=tests/scraping/real_site
```

La prueba FULL real sigue disponible por separado y no forma parte de la suite rápida de CI.

## Pendientes antes de cerrar release

1. Sincronizar el último HEAD remoto.
2. Ejecutar Ruff.
3. Ejecutar Pyright.
4. Ejecutar `python -m pytest -q --ignore=tests/scraping/real_site`.
5. Confirmar `git status --short` vacío.
6. Cuando se abra explícitamente la validación funcional final, repetir FULL real + validación de DB + historial + idempotencia.

No se requiere otro cambio de runtime mientras las invariantes protegidas permanezcan verdes.
