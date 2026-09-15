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

El checkpoint real autorizado es **FULL ID 177**. Las validaciones futuras deben compararse contra ese resultado completo, no contra un piso histórico menor.

Cuando esas condiciones no se cumplen, el resultado debe tratarse como **incompleto** y no debe ejecutar un prune destructivo sobre el catálogo persistido.

## Persistencia e historial

La ejecución válida debe poder aplicarse a la base de datos conservando el historial existente y registrando la nueva ejecución correctamente.

El historial no debe borrarse ni reconstruirse a partir de una sola ejecución reciente. Las ejecuciones anteriores deben permanecer disponibles y la nueva ejecución debe registrar únicamente sus cambios efectivos.

## Rendimiento

El rendimiento es una optimización secundaria: una vez protegida la corrección, se debe reducir el tiempo total del FULL sin alterar los resultados anteriores.

La referencia de rendimiento histórica ya alcanzada es aproximadamente `2:17`; cualquier mejora de tiempo solo es aceptable si mantiene los criterios funcionales, de persistencia y de cobertura `534 / 530 / 4`.

## Recuperación de red

La recuperación concurrente de categorías fallidas es un mecanismo para aumentar la probabilidad de completar el FULL ante fallos transitorios. No constituye por sí misma el objetivo del proyecto.

Si una categoría continúa fallando y la cobertura final queda incompleta, la ejecución debe permanecer marcada como incompleta y conservar el error para diagnóstico. Un error terminal recuperado no debe invalidar por sí solo una cobertura completa demostrada por los datos finales.

## Estado de ingeniería previo al siguiente FULL real

La rama cuenta actualmente con:

- Ruff limpio.
- Pyright limpio (`0 errors, 0 warnings, 0 informations`).
- Suite automatizada: `378 passed, 1 skipped, 7 deselected`.
- Configuración canónica de workers para categorías, HTTP y detalle.
- Guard de FULL que impide prune destructivo cuando la cobertura no está validada.
- Persistencia y recuperación de historial protegidas por pruebas.

## Próxima validación obligatoria

La prueba decisiva pendiente es una ejecución FULL real de las **24 categorías** después del último checkpoint de arquitectura.

El resultado debe compararse contra:

`534 apariciones / 530 productos únicos / 4 multiproducto`

y debe comprobarse además que:

- `coverage_complete=true`;
- no existan errores invalidantes;
- la reconciliación de base de datos solo se aplique cuando la cobertura sea completa;
- el historial previo permanezca intacto;
- una ejecución FULL posterior e idéntica sea idempotente y no genere cambios falsos.
