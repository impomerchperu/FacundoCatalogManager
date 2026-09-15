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
- Suite automatizada: `366 passed, 1 skipped, 7 deselected`.
- Configuración canónica de workers para categorías, HTTP y detalle.
- Guard de FULL que impide prune destructivo cuando la cobertura no está validada.
- Persistencia y recuperación de historial protegidas por pruebas.
- Auditoría de transacciones/historial/estado de aplicación: `8 passed`.
- Auditoría reciente de métricas HTTP y detail-cache completada sin cambios de runtime.

## Checklist general

### Cobertura y corrección

- [x] FULL de las 24 categorías validado.
- [x] 534 apariciones verificadas.
- [x] 530 productos únicos verificados.
- [x] 4 productos multiproducto verificados.
- [x] 534 relaciones producto-categoría verificadas.
- [x] `coverage_complete=true` verificado.
- [x] `coverage_gap=0` verificado.
- [x] 0 errores invalidantes en la ejecución FULL aplicada de referencia.

### Persistencia e historial

- [x] Catálogo reconciliado en `530 / 534`.
- [x] FULL válido aplicado a la base de datos.
- [x] Historial previo preservado.
- [x] Última ejecución válida registrada como `history_id=180`.
- [x] `applied_at` presente para la ejecución aplicada.
- [x] Reconciliación idempotente validada: `0 created / 0 updated / 530 unchanged / 0 deleted`.
- [x] Pruebas de rollback, error-history y application-state: `8 passed`.

### Calidad de ingeniería

- [x] Full suite: `366 passed, 1 skipped, 7 deselected`.
- [x] Pyright: `0 errors, 0 warnings, 0 informations`.
- [x] Ruff: clean.
- [x] Runtime usa `services.scraping.scraping_factory.ScrapingFactory` como fábrica canónica.
- [x] Workers canónicos preservados: categoría `16`, HTTP `28`, detalle `32`.
- [x] Limpieza de facades/patches obsoletos completada donde se demostró ausencia de uso.

### Auditoría de rendimiento

- [x] Separación de tiempos de categoría, detalle, imágenes, mapping y persistencia auditada.
- [x] Confirmado que SQLite/catalog sync no domina el tiempo total.
- [x] Confirmado que el enriquecimiento de detalle representa una parte importante del tráfico HTTP.
- [x] Confirmado que el cache de detalle registra `0` hits en los FULL completos auditados.
- [x] Confirmado que la concurrencia HTTP efectiva alcanza `28` en muestras recientes.
- [x] Confirmado que reintentos/errores transitorios aparecen en la telemetría sin impedir un FULL válido cuando la cobertura final es completa.

## Próximos pasos controlados

- [ ] Mantener las fábricas de compatibilidad mientras exista posible contrato externo no documentado.
- [ ] Añadir y ejecutar pruebas específicas del contrato de progreso antes de cambiar los callbacks `25..47`.
- [ ] Realizar el siguiente experimento de rendimiento sobre red/categoría/detalle, aislado y reversible.
- [ ] No modificar transacciones SQLite salvo que un benchmark demuestre una ganancia medible o exista evidencia concreta de contención.
- [ ] Repetir FULL real después de cualquier cambio de scraping y exigir nuevamente `24 / 534 / 530 / 4`, cobertura completa y ausencia de errores invalidantes.
