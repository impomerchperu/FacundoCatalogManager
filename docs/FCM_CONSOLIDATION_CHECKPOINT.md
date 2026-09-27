# FCM — Checkpoint de consolidación

Fecha de alineación: 2026-09-27
Branch oficial: `main`
Último estado de código funcional antes de la candidata `v0.2.0`: `4a7a956f574626610e3ce80a50059b1dc28fd4da`.

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

### Checkpoint actual — 2026-09-20

- HEAD de código del checkpoint histórico previo a la mejora de progreso: `2e8bd7190a89da308a739dd3b84b1a3dc74b9d95`.
- HEAD funcional del checkpoint histórico del 2026-09-20: `12fc62e96da0fe7f35a751cde911e681f8f8328a`.
- Los commits posteriores a `2e8bd71` incorporan el contrato de progreso de enrichment y su cobertura de pruebas.
- Cambio funcional de runtime de este cierre: `60ab60f93a4403652d23ae2e2ce5c18b5650ba6d` (idempotencia por `content_hash`).
- Ruff: `All checks passed!`.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Batería focal del checkpoint previa: `21 passed in 0.63s`.
- Suite no-real-site más reciente: `454 passed, 8 deselected in 9.95s`.
- Git working tree local: limpio después de sincronizar con `origin/main`.
- GitHub Actions Quality `#2018`: `success` sobre `e45a4a4`, con Ruff, Pyright y Pytest verdes.
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
454 passed, 8 deselected in 9.95s
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
- [x] Pulido de la UI de historial: filas con holgura simétrica para el marco de selección, nombres de PRODUCTO ajustados al ancho disponible y orden alfanumérico natural de CÓDIGO.
- [x] El comparador de benchmarks exige cobertura encontrada igual a esperada y rechaza coverage_gap, error_count o errores HTTP terminales distintos de cero cuando están presentes.
- [ ] Quality CI posterior a estos cambios: pendiente de cierre sobre los últimos commits; no se considera verde hasta completar la ejecución automatizada.

- [x] Sincronización local con la rama remota.
- [x] Ruff limpio en el checkpoint actual.
- [x] Pyright limpio en el checkpoint actual.
- [x] Batería focal de esta auditoría de hashing: 10/10; batería general previa 21/21.
- [x] Suite no-real-site actual: 454/454 (8 deselected).
- [x] Snapshot histórico FULL: 24/534/530/4.
- [x] Referencia operativa actual FULL/E2E: 24/523/519/4.
- [x] Idempotencia validada en la misma SQLite: segunda ejecución idéntica clasifica todos los productos como `unchanged` y no genera `download_changes`.
- [x] Correcciones del ledger y trazabilidad run/history validadas.
- [x] La concurrencia productiva de detalle fue actualizada a `24` después de benchmark cruzado y dos E2E completos.
- [x] No se ha cambiado el comportamiento funcional de prune; además se bloquearon herramientas legacy de borrado directo.
- [x] Limpieza destructiva directa de imágenes bloqueada.
- [x] Quality CI: success (`#2227` sobre `ec5297e`); Ruff, Pyright y Pytest permanecen verdes y `live-catalog` quedó `skipped` de forma intencional.

## Estado maestro actual

La etapa funcional principal continúa cerrada y protegida en `main`. El benchmark de contención/latencia SQLite pendiente ya fue ejecutado y no produjo evidencia que justifique modificar el runtime. El snapshot histórico 534/530/4 permanece como referencia diagnóstica.

### Cerrado

- Cobertura FULL histórica `24 / 534 / 530 / 4`.
- Cobertura FULL/E2E operativa actual `24 / 523 / 519 / 4`.
- Persistencia histórica validada en `530 / 534`.
- `coverage_complete=1`, `coverage_gap=0`, `error_count=0`.
- Recuperación y precedencia de FULL válido.
- Ledger SQLite v2.
- Enlace técnico `scraping_run_history`.
- Cierre determinista de recursos.
- Configuración productiva `8 / 24 / 28`.
- Consolidación de paginación/JSF/métricas/código.
- Auditoría y bloqueo de herramientas legacy destructivas.
- Calidad local, idempotencia sobre la misma SQLite, granularidad de progreso de enrichment, cambio a `24` workers y Quality CI verdes.

### En revisión
- Validación automática final de los últimos cambios de GUI y del guard de benchmarks; la implementación está en `main`, pero el último pipeline todavía está en ejecución.

- Auditoría residual de utilidades de imágenes sin dependencia canónica demostrada (`ImageNamer`, `ImageValidator`, `ImageSyncAdapter`): revisadas y conservadas por contratos propios; no se encontró justificación segura para eliminarlas.
- Granularidad de progreso UI: callbacks intermedios `25..47` implementados y cubiertos por pruebas; el runner conserva el cierre `48/48`.
- Benchmark específico de contención/latencia SQLite solo si aparece evidencia concreta.

### Auditorías cerradas en este avance
- Pulido final de la tabla de historial: el marco de selección queda contenido con holgura vertical simétrica, PRODUCTO se envuelve únicamente cuando el ancho disponible no alcanza y CÓDIGO se presenta en orden alfanumérico natural.
- Observabilidad de benchmarks reforzada: las comparaciones ya no aceptan una corrida con cobertura incompleta ni errores HTTP terminales, evitando comparar rendimiento de ejecuciones que no cumplen el contrato funcional.

- Stock por color: extracción de etiquetas de color ampliada, asociación segura de cantidades y representación `color → stock` en la columna Stock. Se conserva el stock total cuando no existe evidencia suficiente para dividirlo.

- Recuperación de la UI de historial cerrada: estado `APLICADO` con timestamp, `NO APLICADO` para versiones superadas y `ERROR` para ejecuciones fallidas; prueba focal `9 passed` y Quality `#2210` verde.

- Fábricas de compatibilidad: ambas son delegados finos al factory canónico; se conservan por compatibilidad potencial y no existe una implementación paralela.
- Autoridad de ejecución: `scraping_runs` gobierna recuperación/reconciliación del último FULL válido; `scraping_history.applied_at` representa la última aplicación de historial y puede corresponder a una ejecución dirigida. `scraping_run_history` mantiene el vínculo entre ambos.
- La mejora de progreso se incorporó sin alterar cobertura, persistencia, prune, concurrencia ni semántica de scraping.

### Próximo punto de desarrollo

El siguiente bloque después de cerrar el pipeline de calidad actual es **Observabilidad y mantenimiento operativo**: conservar métricas de cobertura, retries, tiempos y progreso como evidencia reutilizable y mantener las herramientas destructivas legacy bloqueadas. No se prevé cambiar scraping, concurrencia o persistencia sin evidencia reproducible.

### No ejecutar en esta fase

- No repetir FULL únicamente para demostrar nuevamente la misma cobertura, salvo que cambie el inventario vivo o exista evidencia de regresión.
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
3. Mantener bajo observación la granularidad de progreso UI ya incorporada y revisar contención SQLite solo si aparece evidencia concreta.
4. Mantener el checkpoint de release; no quedan validaciones funcionales bloqueantes en esta etapa.

## Regla de seguridad del plan

Ninguna limpieza, refactor o optimización se considera válida si reduce la cobertura FULL, cambia la precedencia de la última ejecución completa válida, borra historial existente o habilita prune con cobertura no demostrada.

Los archivos locales `data/scraping_category_profile.json` y `data/scraping_detail_profile.json` son artefactos de profiling generados por las pruebas/diagnósticos; no forman parte de esta etapa de código y no deben añadirse al commit salvo decisión explícita posterior.
\n\n## CURRENT MAIN VALIDATION — 2026-09-27

La última validación local confirmada antes de la candidata quedó completamente verde en `4a7a956`:

- `tests/test_scraping_history_dialog.py`: **18 passed**.
- `tests/tools/test_compare_benchmark_reports.py`: **16 passed**.
- Ruff: **All checks passed!**
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Suite completa: **577 passed, 10 deselected**.

Esta sección representa el estado actual de `main`; las cifras anteriores del documento permanecen como evidencia histórica del momento en que fueron ejecutadas.

La preparación de la semilla Windows cuenta además con **5 pruebas focalizadas** y no modifica el runtime productivo ni la validación física ya realizada para `v0.1.1`.

