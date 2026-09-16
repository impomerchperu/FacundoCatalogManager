# FCM — Checkpoint de consolidación

## Referencia funcional protegida

La prioridad sigue siendo conservar la cobertura FULL real antes de optimizar o simplificar el runtime.

- 24 categorías.
- 534 apariciones producto-categoría.
- 530 productos únicos.
- 4 productos presentes en múltiples categorías.
- 534 relaciones producto-categoría.
- `coverage_gap=0`.
- 0 errores invalidantes.
- Un FULL incompleto no puede ejecutar prune destructivo.

Los pisos históricos menores no sustituyen esta referencia.

## Evidencia reciente

El test real de colección:

```text
python -m pytest tests/scraping/real_site/test_full_catalog_scraper.py -q -m real_site
1 passed in 371.32s (0:06:11)
```

Ese tiempo corresponde al test de colección real ejecutado de forma secuencial por categoría; no debe compararse directamente con el wall-clock del pipeline de producción, que usa concurrencia por categoría.

## Etapa aplicada en este checkpoint

### Limpieza segura

- Renombrado `test_full_sync_safety_patch.py` → `test_full_sync_prune_safety.py`.
- Renombrado `test_product_code_patch.py` → `test_product_code_recovery.py`.
- No se modificó la lógica de cobertura, recuperación, reconciliación ni prune.

### Calidad / aceptación

`quality.yml` mantiene el CI normal de Ruff, Pyright y pytest sin `tests/scraping/real_site`.

Además incorpora un job `live-catalog` activable mediante `workflow_dispatch`. Ese job ejecuta únicamente el test FULL real y funciona como aceptación externa controlada de la cobertura del sitio.

## Próximo orden de trabajo

1. Auditar y consolidar los dos libros de ejecución (`scraping_runs` / `scraping_history`) sin perder el historial existente.
2. Medir por categoría y por etapa antes de alterar concurrencia.
3. Revisar el doble rol de consolidación entre `CategoryProductSyncService` y `CatalogSyncService`.
4. Eliminar estados globales JSF y accesos a estado privado solo después de identificar todos sus consumidores y cubrirlos con tests.
5. Revisar migraciones SQLite para introducir versionado explícito.
6. Repetir FULL real y validar otra vez `24 / 534 / 530 / 4`, DB `530 / 534`, historial aplicado e idempotencia.

## Regla de seguridad del plan

Ninguna limpieza, refactor o optimización se considera válida si reduce la cobertura FULL, cambia la precedencia de la última ejecución completa válida, borra historial existente o habilita prune con cobertura no demostrada.
