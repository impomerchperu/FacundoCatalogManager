# FCM — Checkpoint de rendimiento pre-v0.3.0

Fecha de referencia: 2026-10-01
Rama: `perf/real-image-benchmark`
Estado: checkpoint de trabajo; `main` permanece sin modificar por esta fase.

## 1. Referencia funcional

La validación real FULL mantiene:

- 24 categorías.
- 523 apariciones producto-categoría.
- 519 productos únicos.
- 4 productos multi-categoría.
- 523 relaciones producto-categoría.
- Cobertura completa.
- 0 errores HTTP terminales.
- 0 retries.
- 519/519 productos con imagen en los benchmarks FULL de imágenes.

## 2. Concurrencia de scraping validada

Configuración mantenida para los benchmarks:

- `category_workers=12`.
- `detail_workers=24`.
- `http_workers=28`.
- `jsf_http_concurrency=8`.
- `jsf_page_workers=2`.
- `category_page_workers=1`.
- `thread_sessions=True`.
- Boundary probe desactivado únicamente para el benchmark controlado.

### Detail workers

Los benchmarks previos validaron 24 workers después de comparar 16 y 24. El salto posterior de 24 a 28 no mostró una mejora relevante y se descartó.

### Category workers

El paso de 8 a 12 fue validado mediante cuatro pares balanceados y preservó la cobertura completa sin retries ni errores.

Un profiling posterior comparó directamente 16 contra 12:

| Métrica | category_workers=12 | category_workers=16 |
| --- | ---: | ---: |
| Profile wall time | 58.01 s | 62.76 s |
| Category HTTP total | 179.97 s | 202.59 s |
| Category HTTP promedio | 7.20 s | 8.10 s |
| Category HTTP máximo | 12.58 s | 15.40 s |
| HTTP retries | 0 | 0 |
| HTTP terminal errors | 0 | 0 |
| Cobertura | completa | completa |

La ejecución con 16 workers aumentó el tiempo de perfil en 8.2% y elevó la latencia media de las requests de categoría. Se mantiene 12 como configuración validada.

### JSF

`jsf_page_workers=2` y `jsf_http_concurrency=8` se mantienen porque las repeticiones controladas no mostraron un beneficio reproducible al aumentar el paralelismo de páginas.

## 3. ImageSync

Se realizaron benchmarks FULL sobre las 519 imágenes:

| Image workers | Image Sync |
| ---: | ---: |
| 1 | 301.17 s |
| 8 | 44.43 s |
| 12 | 28.28 s |
| 16 | 20.19 s |

Además, el par balanceado 8/16 produjo:

| Image workers | Run balanceado |
| ---: | ---: |
| 8 | 37.73 s |
| 16 | 28.30 s |

Promedio de los dos runs disponibles por configuración:

- 8 workers: 41.08 s.
- 16 workers: 24.25 s.
- Reducción de ImageSync: 40.98%.

Todas las ejecuciones mantuvieron 523/523 de cobertura, 519/519 imágenes, 0 retries y 0 errores HTTP terminales.

## 4. Validación del default real

Con `FCM_IMAGE_BENCH_WORKERS` eliminado del entorno, el benchmark tomó el valor del código:

`SCRAPING_IMAGE_WORKERS=16`

Resultado FULL:

- Collection: 30.70 s.
- Enrichment: 4.61 s.
- Image Sync: 26.93 s.
- Total: 67.34 s.
- 523/523 apariciones.
- 519/519 imágenes.
- 0 retries.
- 0 errores HTTP terminales.

Esto confirma que el default del código y el runner de benchmark usan la misma fuente de verdad.

## 5. Estado del cuello de botella

ImageSync fue el cuello principal durante la fase inicial. Con 16 workers su coste bajó hasta 26.93 s en el FULL de confirmación del default.

El perfil de categorías muestra ahora que collection está dominado por latencia de las requests de categoría. No se observó espera de semáforo:

- Category semaphore wait: 0.000 s.
- JSF semaphore wait: 0.000 s.
- Detail semaphore wait: 0.000 s.

Por tanto, no queda justificación experimental para seguir aumentando category workers por encima de 12.

## 6. Estado de configuración de esta rama

Valores actuales candidatos:

```
SCRAPING_CATEGORY_WORKERS = 12
SCRAPING_MAX_WORKERS = 24
SCRAPING_HTTP_WORKERS = 28
SCRAPING_CATEGORY_PAGE_WORKERS = 1
SCRAPING_JSF_HTTP_CONCURRENCY = 8
SCRAPING_JSF_PAGE_WORKERS = 2
SCRAPING_IMAGE_WORKERS = 16
```

Estos valores pertenecen a la rama de benchmark y todavía no se han promovido a `main`.

## 7. Próximos gates

1. Ejecutar validación local completa después de los cambios de documentación/configuración.
2. Consolidar los artefactos JSON definitivos.
3. Repetir FULL final únicamente si se implementa una optimización adicional.
4. Revisar el diff completo de la rama frente a `main`.
5. Completar auditoría pre-v0.3.0.
6. Promover a `main` solamente después del cierre de todos los gates.

