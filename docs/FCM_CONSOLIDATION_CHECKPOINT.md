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

## Evidencia reciente validada localmente

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
- [x] Ruff limpio en la validación anterior.
- [x] Pyright limpio en la validación anterior.
- [x] Tests anteriores de las dos familias renombradas: 8/8.
- [x] Suite no-real-site anterior: 379/379.
- [x] FULL real de colección anterior: 1/1.
- [x] Referencia funcional 24/534/530/4 preservada por el test real.
- [x] Corrección aplicada a los contratos del nuevo ledger.
- [ ] Reejecutar tests del ledger corregidos.
- [ ] Reejecutar suite no-real-site después de la corrección.
- [ ] No se ha cambiado la concurrencia productiva.
- [ ] No se ha cambiado el comportamiento de prune.

## Próximo orden de trabajo

1. Revalidar la corrección del ledger y, con tests verdes, conservar `scraping_runs` como registro de ejecución sin duplicar todavía autoridad funcional.
2. Auditar los consumidores de `scraping_history` y `scraping_runs` para definir una autoridad única de ejecución aplicada.
3. Medir por categoría y por etapa antes de alterar concurrencia.
4. Revisar el doble rol de consolidación entre `CategoryProductSyncService` y `CatalogSyncService`.
5. Eliminar estados globales JSF y accesos a estado privado solo después de identificar todos sus consumidores y cubrirlos con tests.
6. Revisar migraciones SQLite para introducir versionado explícito.
7. Repetir FULL real y validar otra vez `24 / 534 / 530 / 4`, DB `530 / 534`, historial aplicado e idempotencia.

## Regla de seguridad del plan

Ninguna limpieza, refactor o optimización se considera válida si reduce la cobertura FULL, cambia la precedencia de la última ejecución completa válida, borra historial existente o habilita prune con cobertura no demostrada.

Los archivos locales `data/scraping_category_profile.json` y `data/scraping_detail_profile.json` son artefactos de profiling generados por las pruebas/diagnósticos; no forman parte de esta etapa de código y no deben añadirse al commit salvo decisión explícita posterior.
