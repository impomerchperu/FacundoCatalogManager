# FCM — Checkpoint de consolidación

## Referencias funcionales

La prioridad sigue siendo conservar la cobertura FULL real antes de optimizar o simplificar el runtime.

### Snapshot histórico

- 24 categorías.
- 534 apariciones producto-categoría.
- 530 productos únicos.
- 4 productos presentes en múltiples categorías.
- 534 relaciones producto-categoría.

### Referencia operativa actual

- 24 categorías.
- 523 apariciones producto-categoría.
- 519 productos únicos.
- 4 productos presentes en múltiples categorías.
- 523 relaciones producto-categoría.
- `coverage_gap=0`.
- 0 errores invalidantes.

La cobertura del inventario vivo es válida cuando cada categoría cumple su `expected_count` vigente y la persistencia reproduce exactamente las cantidades observadas. Un FULL incompleto no puede ejecutar prune destructivo.

El snapshot histórico 534/530/4 permanece únicamente como referencia diagnóstica.

## Evidencia reciente validada localmente

### Checkpoint actual — 2026-09-19

- HEAD documental actual: `1c7ff6ac1a520867102bab5b460418529c279ad0`.
- Último HEAD con cambios de runtime/herramientas: `28becc60b230ec0f43285e999932f4d6b2feee8d`.
- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Batería focal del checkpoint previa: `21 passed in 0.63s`.
- Suite no-real-site: `434 passed, 2 deselected in 7.78s`.
- Git working tree local: limpio después de sincronizar con `origin/feature/scraping-performance-recovery`.
- GitHub Actions Quality `#1913`: `success` en el último runtime validado (`17619e7`).
- `live-catalog`: `skipped` en CI rápido; las validaciones FULL reales se ejecutaron manualmente contra el sitio.
- Se deshabilitaron las rutas de limpieza destructiva directa de catálogo e imágenes; quedan solo como diagnóstico.
- FULL real independiente de cobertura validado: `24 / 523 / 519 / 4`, con `523/523` apariciones, `0` gaps y `0` códigos sin código.



Después de la limpieza segura de esta etapa, la batería local quedó en:

```text
python -m ruff check .
All checks passed!

python -m pyright
0 errors, 0 warnings, 0 informations

python -m pytest tests/scraping/test_full_sync_prune_safety.py tests/scraping/test_product_code_recovery.py -q
8 passed in 0.36s

python -m pytest tests/scraping/real_site/test_full_catalog_scraper.py -q -m real_site
1 passed in 391.61s (0:06:31)

python -m pytest -q --ignore=tests/scraping/real_site
379 passed, 2 deselected in 8.13s
```

El test real de colección se ejecuta de forma secuencial por categoría; por ello sus `391.61s` son una referencia del recolector real y no deben compararse directamente con el wall-clock del pipeline de producción, que utiliza concurrencia por categoría.

La variación respecto de la ejecución real anterior (`371.32s`) no cambia la conclusión funcional: ambas ejecuciones alcanzan el contrato del test. El rendimiento no se considerará mejorado ni empeorado hasta disponer de un benchmark controlado y comparable.

## Etapa aplicada en este checkpoint

### Limpieza segura

- Renombrado `test_full_sync_safety_patch.py` → `test_full_sync_prune_safety.py`.
- Renombrado `test_product_code_patch.py` → `test_product_code_recovery.py`.
- No se modificó la lógica de cobertura, recuperación, reconciliación ni prune.

### Calidad / aceptación

`quality.yml` mantiene el CI normal de Ruff, Pyright y pytest sin `tests/scraping/real_site`.

Además incorpora un job `live-catalog` activable mediante `workflow_dispatch`, para ejecutar de forma controlada el test FULL real sin convertir el sitio externo en una dependencia del CI rápido.

### Ledger de FULL incompleto

- Un FULL crea `scraping_runs` desde el inicio para conservar trazabilidad.
- Si la cobertura no es completa, el run termina en `ERROR` con el motivo.
- Un FULL incompleto no persiste `scraping_product_occurrences` ni ejecuta `prune`.
- La validación de cobertura del servicio normalizado respeta el `mode` explícito recibido por `_persist_normalized` y no depende únicamente del estado privado `_scraping_mode`.
- Los tests del ledger fueron alineados con esta semántica: FULL incompleto se registra, pero no escribe datos del catálogo.

## Estado de esta etapa

- [x] Sincronización local con la rama remota.
- [x] Ruff limpio en el checkpoint actual.
- [x] Pyright limpio en el checkpoint actual.
- [x] Batería focal de esta auditoría de hashing: 10/10; batería general previa 21/21.
- [x] Suite no-real-site actual: 434/434 (2 deselected).
- [x] Snapshot histórico FULL: 24/534/530/4.
- [x] Referencia operativa actual FULL/E2E: 24/523/519/4.
- [x] Idempotencia validada en la misma SQLite: segunda ejecución idéntica clasifica todos los productos como `unchanged` y no genera `download_changes`.
- [x] Correcciones del ledger y trazabilidad run/history validadas.
- [x] No se ha cambiado la concurrencia productiva.
- [x] No se ha cambiado el comportamiento funcional de prune; además se bloquearon herramientas legacy de borrado directo.
- [x] Limpieza destructiva directa de imágenes bloqueada.
- [x] Quality CI: success (#1966) sobre la corrección de idempotencia, con Ruff, Pyright y Pytest verdes.

## Estado maestro actual

La etapa funcional principal continúa cerrada y protegida. El trabajo posterior es de auditoría/limpieza y debe preservar la cobertura completa relativa al inventario vivo. El snapshot histórico 534/530/4 permanece como referencia diagnóstica.

### Cerrado

- Cobertura FULL histórica `24 / 534 / 530 / 4`.
- Cobertura FULL/E2E operativa actual `24 / 523 / 519 / 4`.
- Persistencia histórica validada en `530 / 534`.
- `coverage_complete=1`, `coverage_gap=0`, `error_count=0`.
- Recuperación y precedencia de FULL válido.
- Ledger SQLite v2.
- Enlace técnico `scraping_run_history`.
- Cierre determinista de recursos.
- Configuración productiva `8 / 16 / 28`.
- Consolidación de paginación/JSF/métricas/código.
- Auditoría y bloqueo de herramientas legacy destructivas.
- Calidad local, idempotencia sobre la misma SQLite y Quality CI verdes.

### En revisión

- Auditoría residual de utilidades de imágenes sin dependencia canónica demostrada (`ImageNamer`, `ImageValidator`, `ImageSyncAdapter`): revisadas y conservadas por contratos propios; no se encontró justificación segura para eliminarlas.
- Mejoras opcionales de granularidad de progreso UI.
- Benchmark específico de contención/latencia SQLite solo si aparece evidencia concreta.

### Auditorías cerradas en este avance

- Fábricas de compatibilidad: ambas son delegados finos al factory canónico; se conservan por compatibilidad potencial y no existe una implementación paralela.
- Autoridad de ejecución: `scraping_runs` gobierna recuperación/reconciliación del último FULL válido; `scraping_history.applied_at` representa la última aplicación de historial y puede corresponder a una ejecución dirigida. `scraping_run_history` mantiene el vínculo entre ambos.
- No se requiere modificación de runtime por estas auditorías.

### No ejecutar en esta fase

- Nuevo FULL real solo para repetir la cobertura ya validada; la referencia operativa `24 / 523 / 519 / 4` ya fue confirmada dos veces.
- Cambios de extracción, paginación o límites de concurrencia sin benchmark + FULL posterior.

## Modelo de autoridad persistente

El modelo actual usa dos conceptos deliberadamente separados:

1. `scraping_runs`: fuente técnica para decidir qué FULL completo y consistente puede reconstruir el catálogo.
2. `scraping_history`: bitácora de ejecuciones/aplicaciones y detalle de cambios; `applied_at` identifica la versión de historial actualmente aplicada.
3. `scraping_run_history`: vínculo explícito cuando una ejecución moderna tiene una correspondencia demostrable con su historial.

Una ejecución dirigida puede quedar aplicada en historial sin convertirse por ello en la base de recuperación FULL. Mantener esta separación evita que una actualización parcial sustituya silenciosamente la referencia completa del catálogo.

## Próximo orden de trabajo

1. Mantener bajo observación las utilidades de imágenes conservadas por compatibilidad; no hay cambio funcional pendiente en hashing.
2. Mantener la compatibilidad de factories mientras pueda existir consumo externo y ampliar cobertura de contrato solo cuando aporte valor.
3. Revisar opcionalmente progreso UI de enrichment y contención SQLite, siempre fuera del baseline funcional.
4. Mantener el checkpoint de release; no quedan validaciones funcionales bloqueantes en esta etapa.

## Regla de seguridad del plan

Ninguna limpieza, refactor o optimización se considera válida si reduce la cobertura FULL, cambia la precedencia de la última ejecución completa válida, borra historial existente o habilita prune con cobertura no demostrada.

Los archivos locales `data/scraping_category_profile.json` y `data/scraping_detail_profile.json` son artefactos de profiling generados por las pruebas/diagnósticos; no forman parte de esta etapa de código y no deben añadirse al commit salvo decisión explícita posterior.
