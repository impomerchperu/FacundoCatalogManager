# Objetivo principal del scraping FULL

El objetivo de `feature/scraping-performance-recovery` es que una ejecución FULL del catálogo sea **correcta, completa y segura para sincronizar la base de datos**, y después optimizar su tiempo sin perder esas garantías.

## Criterio funcional principal

Una ejecución FULL válida debe cubrir las 24 categorías y alcanzar el estado de referencia correcto:

- 534 apariciones de productos por categoría.
- 530 productos únicos.
- 4 productos presentes en múltiples categorías.
- 534 relaciones producto-categoría.
- Cobertura completa.
- Sin errores de scraping que invaliden la ejecución.

El checkpoint real autorizado es **la última ejecución FULL válida y aplicada, actualmente history ID 180**. Las validaciones futuras deben compararse contra el resultado completo:

`534 apariciones / 530 productos únicos / 4 multiproducto`

Los pisos históricos menores, como `529/525`, no son sustitutos válidos de la cobertura completa.

Cuando esas condiciones no se cumplen, el resultado debe tratarse como **incompleto** y no debe ejecutar un prune destructivo sobre el catálogo persistido.

## Persistencia e historial

La ejecución válida debe poder aplicarse a la base de datos conservando el historial existente y registrando la nueva ejecución correctamente.

El historial no debe borrarse ni reconstruirse a partir de una sola ejecución reciente. Las ejecuciones anteriores deben permanecer disponibles y la nueva ejecución debe registrar únicamente sus cambios efectivos.

La ejecución FULL aplicada de referencia dejó:

- `products=530`;
- `product_categories=534`;
- `created=0`;
- `updated=0`;
- `unchanged=530`;
- `deleted=0`.

## Recuperación de red

La recuperación concurrente de categorías fallidas es un mecanismo para aumentar la probabilidad de completar el FULL ante fallos transitorios. No constituye por sí misma el objetivo del proyecto.

Los registros recientes muestran que un FULL completo puede contener reintentos y errores HTTP transitorios durante la extracción, siempre que el resultado final alcance la cobertura autorizada y no queden errores invalidantes. En muestras recientes se observaron aproximadamente `288–289` solicitudes de detalle, `32–51` solicitudes de categoría y `9–43` reintentos; también se observaron errores HTTP durante la ejecución. Estos contadores son métricas de diagnóstico y no invalidan por sí solos un FULL que termine correctamente en `534 / 530 / 4`.

Si una categoría continúa fallando y la cobertura final queda incompleta, la ejecución debe permanecer marcada como incompleta y conservar el error para diagnóstico.

## Rendimiento

El rendimiento es una optimización secundaria: una vez protegida la corrección, se debe reducir el tiempo total del FULL sin alterar los resultados anteriores.

La referencia de rendimiento validada actualmente está en el rango de `118–121s` de extremo a extremo. Los campos agregados de tiempo de solicitudes HTTP no deben compararse directamente con el tiempo de pared porque acumulan tiempos de múltiples solicitudes concurrentes.

La evidencia actual indica que el trabajo dominante está en red, especialmente en:

- listado/extracción de categorías;
- enriquecimiento de detalle por producto.

Los registros recientes muestran `cache_hits=0` y aproximadamente `288–289` solicitudes de detalle por FULL completo, por lo que el cache de detalle no está reduciendo estas solicitudes dentro de una ejecución individual. La concurrencia HTTP observada alcanza `28` en las muestras relevantes, consistente con la configuración canónica actual.

La persistencia del catálogo sigue siendo una fracción pequeña del tiempo total y no existe evidencia actual para tratar SQLite como el cuello de botella principal.

Cualquier optimización de rendimiento debe aislarse, medirse y validarse nuevamente contra `24 / 534 / 530 / 4`.

## Estado de ingeniería actual

La rama cuenta actualmente con:

- Ruff limpio.
- Pyright limpio (`0 errors, 0 warnings, 0 informations`).
- Suite automatizada base: `366 passed, 1 skipped, 7 deselected`.
- `23` pruebas de límites arquitectónicos pasadas.
- Configuración canónica de workers: categoría `16`, HTTP `28`, detalle `32`.
- Guard de FULL que impide prune destructivo cuando la cobertura no está validada.
- Persistencia y recuperación de historial protegidas por pruebas.
- Auditoría de transacciones/historial/estado de aplicación: `8 passed`.
- Auditoría reciente de métricas HTTP y detail-cache completada sin cambios de runtime.
- Tests formales del contrato actual de progreso runner: `8 passed`.
- Limpieza y migración de consumers/patches obsoletos completada donde se demostró ausencia de uso productivo.

## Checklist general maestro

### A. Corrección funcional

- [x] FULL real de 24 categorías.
- [x] 534 apariciones.
- [x] 530 productos únicos.
- [x] 4 productos multiproducto.
- [x] 534 relaciones producto-categoría.
- [x] Cobertura completa.
- [x] `coverage_gap=0`.
- [x] 0 errores invalidantes.
- [x] FULL/prune safety.
- [x] Reconciliación correcta.

### B. Recuperación y persistencia

- [x] Recuperación de paginación.
- [x] Recuperación JSF.
- [x] Recuperación de páginas incompletas.
- [x] Recuperación de códigos/SKU.
- [x] Recuperación de detalle.
- [x] Recuperación de cobertura.
- [x] Manejo de FULL incompleto.
- [x] Manejo de FULL fallido.
- [x] Precedencia de FULL válida frente a FULL fallida más reciente.
- [x] Atomicidad de catálogo + historial.
- [x] Rollback.
- [x] `history_id=180` aplicado.
- [x] Historial previo preservado.
- [x] Catálogo reconciliado en `530 / 534`.

### C. Consolidación arquitectónica

- [x] Pagination consolidada.
- [x] JSF consolidado.
- [x] Metrics consolidado.
- [x] Price recovery consolidado.
- [x] Coverage recovery consolidado.
- [x] Full/prune safety consolidado.
- [x] Product-code consolidado.
- [x] `ScrapingConfig` consolidada.
- [x] Workers consolidados.
- [x] Factory canónica de producción confirmada.
- [x] Facades/patches muertos eliminados después de auditoría.
- [x] Consumers de tests migrados a APIs nativas.
- [ ] Compatibility factories conservadas por posible compatibilidad externa.

### D. Historial / DB / transacciones

- [x] Atomicidad funcional.
- [x] Rollback.
- [x] Aplicación de history.
- [x] Precedencia SUCCESS vs ERROR.
- [x] Reconstrucción/reconciliación de catálogo.
- [x] Relaciones categoría-producto.
- [x] Auditoría del alcance transaccional actual frente al timing observado.
- [ ] Benchmark de contención/latencia SQLite.
- [ ] Cambiar boundaries transaccionales solo con evidencia cuantitativa.

### E. Calidad

- [x] Tests base: `366 passed, 1 skipped, 7 deselected`.
- [x] Architecture boundaries: `23 passed`.
- [x] Ruff clean.
- [x] Pyright clean.
- [x] Real FULL post-cleanup.
- [x] Runner + progress contract tests: `8 passed`.

### F. Progreso UI

- [x] Pipeline FULL definido como `48` pasos lógicos.
- [x] Colección actual emite `1..24`.
- [x] Enrichment actualmente no emite callbacks intermedios `25..47`.
- [x] Runner termina en `48/48`.
- [x] Confirmado que esto no afecta cobertura ni persistencia.
- [x] Tests formales del contrato actual ejecutados y verdes.
- [ ] Decidir con esos tests si se implementan callbacks `25..47`.

### G. Rendimiento

- [x] Tiempos por etapa auditados.
- [x] HTTP/detail auditado.
- [x] Confirmado que SQLite/catalog sync no domina el tiempo total.
- [x] Confirmado que category/detail concentran el coste de red observado.
- [x] Concurrencia HTTP efectiva hasta `28` en muestras relevantes.
- [x] Detail-cache con `0` hits en los FULL completos auditados.
- [x] Sin cambios de runtime realizados desde esta auditoría.
- [ ] Aislar el siguiente experimento en red/category/detail.
- [ ] Ejecutar benchmark comparativo.
- [ ] Repetir FULL real después de cualquier cambio.
- [ ] Confirmar nuevamente `24 / 534 / 530 / 4`.
- [ ] Confirmar nuevamente DB `530 / 534`.
- [ ] Confirmar historial aplicado e idempotencia.

## Criterio para cerrar el plan

El plan maestro no debe declararse cerrado hasta completar, como mínimo:

1. decisión sobre la semántica final del progreso y, en caso de cambio, su implementación y validación;
2. cualquier decisión sobre scope transaccional respaldada por medición si se decide optimizarlo;
3. un experimento de rendimiento aislado sobre red/category/detail;
4. un FULL real posterior que vuelva a demostrar `24 / 534 / 530 / 4`, cobertura completa, DB `530 / 534`, historial aplicado e idempotencia.

Mientras esos puntos sigan pendientes, la parte crítica de corrección, recuperación, consolidación, persistencia e integridad del catálogo permanece validada y no debe modificarse sin una razón concreta.
