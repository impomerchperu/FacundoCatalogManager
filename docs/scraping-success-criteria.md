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

Cuando esas condiciones no se cumplen, el resultado debe tratarse como **incompleto** y no debe ejecutar un prune destructivo sobre el catálogo persistido.

## Persistencia e historial

La ejecución válida debe poder aplicarse a la base de datos conservando el historial existente y registrando la nueva ejecución correctamente. La referencia conocida de una ejecución completa es `scraping_run #19 SUCCESS` y su historial aplicado es `#172 SUCCESS`.

El historial no debe borrarse ni reconstruirse a partir de una sola ejecución reciente.

## Rendimiento

El rendimiento es una optimización secundaria: una vez protegida la corrección, se debe reducir el tiempo total del FULL sin alterar los resultados anteriores.

La referencia de rendimiento ya alcanzada es aproximadamente `2:17`; una mejora de tiempo solo es aceptable si mantiene los criterios funcionales y de persistencia anteriores.

## Recuperación de red

La recuperación concurrente de categorías fallidas es un mecanismo para aumentar la probabilidad de completar el FULL ante fallos transitorios. No constituye por sí misma el objetivo del proyecto.

Si una categoría continúa fallando después de los intentos de recuperación, la ejecución debe permanecer marcada como incompleta y conservar el error para diagnóstico.

## Próxima validación obligatoria

Después de la validación local, la prueba decisiva es una ejecución FULL real de las 24 categorías. El resultado debe compararse contra `534 / 530 / 4`, no contra un piso histórico menor.
