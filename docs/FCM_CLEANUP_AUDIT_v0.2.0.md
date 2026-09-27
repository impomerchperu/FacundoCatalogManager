# FCM — Auditoría de limpieza profunda del repositorio v0.2.0

Fecha: 2026-09-27  
Rama oficial: `main`  
Baseline auditado: `33a33d3`  
Versión: `0.2.0`

## 1. Objetivo

Dejar el repositorio con una superficie técnica mínima y mantenible, retirando residuos de investigación, documentación superada, snapshots no operativos, scripts rotos o ad hoc y estructuras que ya no representan la arquitectura vigente.

La regla aplicada fue:

- `eliminar` cuando el activo no aporta valor actual;
- `consolidar` cuando existen casos de prueba o documentos que cubren la misma responsabilidad;
- `conservar` cuando existe uso operativo, compatibilidad explícita o valor de diagnóstico reproducible.

## 2. Inventario previo

El árbol `main` contenía 391 archivos versionados y 38 directorios.

Hallazgos principales:

- 58 archivos dentro de `tools/inspection/`, incluidos diagnósticos históricos y un subarchivo `archive/`.
- 4 scripts `tools/inspect_*` fuera del conjunto de herramientas mantenidas.
- 2 scripts Python ad hoc bajo `scripts/`.
- 1 envoltura redundante de auditoría de imágenes: `tools/audit_images.py`.
- 5 documentos de contexto/checkpoint ya absorbidos por documentación vigente.
- 1 snapshot de catálogo de 264 KB sin función operativa.
- 1 `LICENSE` vacío.
- 2 ubicaciones de tests semánticamente solapadas que podían consolidarse sin perder cobertura.
- `scripts/__init__.py` quedó innecesario al retirar los scripts Python del directorio.

## 3. Acciones aplicadas

### Retirado

- `tools/inspection/**` completo.
- `tools/inspect_category_products.py`.
- `tools/inspect_category_scraping_service.py`.
- `tools/inspect_real_catalog_sync.py`.
- `tools/inspect_real_scraping.py`.
- `scripts/inspect_multi_category.py`.
- `scripts/run_scraping_test.py`.
- `scripts/__init__.py`.
- `tools/audit_images.py`.
- `data/catalog_db_snapshot.json`.
- `LICENSE` vacío.
- `docs/FCM_ARCHITECTURE_CHECKPOINT.md`.
- `docs/FCM_CONSOLIDATION_CHECKPOINT.md`.
- `docs/HISTORY_UI_RECOVERY.md`.
- `docs/POST_RELEASE_ROADMAP.md`.
- `docs/SCRAPING_RECOVERY_CONTEXT.md`.
- `tests/test_category_extractor.py`.
- `tests/scraping/unit/test_image_validator.py`.

### Consolidado

- Los 7 casos de `CategoryExtractor` quedan en `tests/scraping/test_category_extractor.py`.
- Los 7 casos de `ImageValidator` quedan en `tests/scraping/test_image_validator.py`.

No se eliminó ningún caso de prueba; solo se movió a su ubicación canónica.

## 4. Conservado deliberadamente

No se eliminaron:

- `tools/catalog_backup.py`: operación explícita de backup/restore.
- `tools/clean_catalog.py`: diagnóstico seguro de residuos legacy.
- `tools/clean_unused_images.py`: mantenimiento físico basado en allowlist de DB.
- `tools/audit_image_storage.py`: auditoría cruzada de filesystem + SQLite + hashes.
- Herramientas de benchmark y profiling: aportan evidencia reproducible para futuras decisiones de rendimiento.
- Fábricas/configuraciones de compatibilidad: siguen formando parte de la frontera de compatibilidad auditada.
- Pruebas de recuperación, concurrencia, cobertura, GUI, historial y distribución: representan invariantes activas.
- Documentación de criterios operativos, release, Windows y auditorías: necesaria para operar y publicar.

## 5. Duplicados y obsolescencia

La inspección de blobs no encontró archivos no vacíos duplicados byte-a-byte.

Los nombres repetidos `scraping_config.py` y `scraping_factory.py` corresponden a capas distintas. Las fábricas externas son fachadas de compatibilidad deliberadas; no se fusionan porque hacerlo cambiaría una frontera pública sin beneficio funcional demostrado.

Las pruebas con nombres similares tampoco eran duplicados exactos: cubrían casos distintos. Las únicas consolidaciones aplicadas fueron las dos parejas donde la misma unidad funcional estaba repartida en ubicaciones diferentes.

## 6. Documentación final

La documentación operativa queda reducida a:

- `docs/FCM_MASTER_PLAN.md`
- `docs/scraping-success-criteria.md`
- `docs/FCM_RELEASE_CHECKPOINT.md`
- `docs/FCM_WINDOWS_RELEASE.md`
- `docs/FCM_RELEASE_NOTES_v0.2.0.md`
- `docs/FCM_FINAL_AUDIT_v0.2.0.md`
- `docs/FCM_CLEANUP_AUDIT_v0.2.0.md`

Los documentos retirados no se pierden como historial de ingeniería: siguen disponibles mediante el historial de Git.

## 7. Resultado

Antes de la limpieza: 391 archivos versionados.

Se retiraron 75 rutas y se incorporó esta acta, dejando 317 archivos versionados.

La limpieza no modifica:

- runtime productivo: `8 / 24 / 28`;
- referencia funcional: `24 / 523 / 519 / 4`;
- `coverage_complete=1`;
- `coverage_gap=0`;
- cero errores invalidantes.

## 8. Higiene del historial Git

El repositorio mantiene referencias históricas fuera del árbol de código:

- `main` es la rama operativa.
- Existen ramas históricas de desarrollo, auditoría y pruebas temporales; no forman parte del contenido distribuido de la versión.
- Existe un tag `v1.0.0` que apunta a un commit anterior al actual ciclo de releases.
- La release oficial de referencia sigue siendo `v0.1.1`, cuyo tag permanece apuntando al commit de release validado.
- Estas referencias no se eliminan automáticamente porque borrar refs es una operación destructiva de historial. La limpieza del código no depende de ellas.

Cuando se decida purgar refs históricas, debe hacerse explícitamente después de comprobar que no se necesite rollback ni trazabilidad.

## 9. Gate de cierre

El cierre requiere confirmar localmente:

`python -m pytest -q`  
`python -m ruff check .`  
`python -m pyright`  
`git status --short`

La suite debe conservar los 582 tests ejecutados y 10 deselected.

## 10. Regla permanente

No incorporar al repositorio:

- snapshots locales sin función operativa;
- dumps HTML o resultados generados;
- scripts de investigación de una sola vez;
- documentación que solo repita un checkpoint ya absorbido.

Antes de retirar una compatibilidad, un test o una herramienta, verificar uso actual y migrar primero cualquier consumidor existente.
