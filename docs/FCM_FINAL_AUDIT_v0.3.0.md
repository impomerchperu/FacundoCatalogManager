# FCM — Auditoría final pre-v0.3.0

Fecha de referencia: 2026-10-02
Rama auditada: `perf/real-image-benchmark`
Base: `main`
Estado: candidata pre-v0.3.0; esta acta no declara una publicación ni modifica `main`.

## 1. Alcance de la auditoría

Esta auditoría cierra la fase de validación de rendimiento y robustez incorporada en `perf/real-image-benchmark`.

La auditoría cubre:

- configuración de concurrencia validada mediante benchmarks reales;
- cobertura FULL del catálogo real;
- recuperación de campos de detalle;
- sincronización real de imágenes;
- comportamiento de paginación JSF;
- delimitación de recuperación de precios;
- cierre correcto del ciclo de benchmark/browser;
- calidad estática y suite de pruebas;
- higiene de artefactos generados;
- revisión del historial documental de v0.2.0;
- estado de la rama y de la PR.

## 2. Referencia funcional

La referencia funcional preservada durante esta fase es:

- 24 categorías;
- 523 apariciones producto-categoría;
- 519 productos únicos;
- 4 productos multi-categoría;
- 523 relaciones producto-categoría;
- cobertura completa;
- stock por color validado para las 24 categorías;
- 0 inconsistencias STOCK/COLOR_STOCK;
- 0 errores HTTP terminales;
- 0 retries.

Los conteos de 519 productos únicos, 4 multi-categoría y 523 relaciones proceden de las validaciones FULL previas. El benchmark final de esta acta vuelve a exigir y confirmar la cobertura de 523/523 apariciones y la unicidad no vacía de códigos mediante sus assertions.

## 3. Configuración validada

La configuración efectiva del benchmark final fue:

```
category_workers          = 12
detail_workers            = 24
http_workers              = 28
category_page_workers     = 1
jsf_http_concurrency      = 8
jsf_page_workers          = 2
image_workers             = 16
thread_sessions           = True
skip_boundary_probe       = True  (solo override controlado del benchmark)
```

`skip_boundary_probe=True` no forma parte de la configuración productiva. Se utilizó exclusivamente para el benchmark controlado porque la cobertura independiente ya coincidía con el total anunciado.

## 4. Validación FULL real final

Comando ejecutado:

```powershell
python -m pytest tools/benchmark_images_real_site.py -q -m real_site -o addopts=""
```

Resultado:

```
1 passed in 75.26s
```

### Cobertura

| Métrica | Resultado |
| --- | ---: |
| Categorías | 24 |
| Apariciones esperadas | 523 |
| Apariciones encontradas | 523 |
| Cards encontradas | 523 |
| Páginas solicitadas | 34 |
| Páginas cargadas | 34 |

No hubo discrepancia entre las apariciones anunciadas y las recolectadas.

### Enrichment y recuperación de detalle

| Métrica | Resultado |
| --- | ---: |
| Detail requests | 8 |
| Detail skipped | 515 |
| Detail cache hits | 0 |
| Detail cache entries | 8 |
| Detail extractor products | 8 |
| Detail extractor none | 0 |
| Detail extractor errors | 0 |

Las solicitudes de detalle se limitaron a productos que requerían recuperación; no se observó una expansión innecesaria del enrichment.

Razones registradas:

- `requested_missing_description=8`
- `requested_missing_fields=8`
- `skipped_complete_color_stock=388`
- `skipped_complete_single_stock=127`

### Imágenes

| Métrica | Resultado |
| --- | ---: |
| Image workers | 16 |
| Image Sync | 24.83 s |
| Pipeline total | 74.61 s |

El benchmark terminó con assertions satisfechas para todos los productos que debían sincronizar imagen y para la cantidad de archivos generados.

### HTTP

| Métrica | Resultado |
| --- | ---: |
| Requests totales | 43 |
| Successes | 43 |
| Errors | 0 |
| Retries | 0 |
| Terminal errors | 0 |
| Máxima concurrencia observada | 12 |
| Límite HTTP global | 28 |

Separación por tipo:

| Tipo | Requests | Tiempo total | Máximo |
| --- | ---: | ---: | ---: |
| Categoría | 25 | 167.13 s | 13.09 s |
| JSF | 10 | 38.61 s | 6.27 s |
| Detalle | 8 | 15.77 s | 2.32 s |

La espera de semáforo fue prácticamente nula:

- category semaphore wait: 0.000135 s;
- JSF semaphore wait: 0.000036 s;
- detail semaphore wait: 0.000023 s.

Esto confirma que el límite de concurrencia no fue el cuello de botella del benchmark final.

`collection_discovery_seconds=266.41 s` es la suma de tiempos de discovery de las 24 tareas concurrentes y, por tanto, no representa wall time. El wall time medido para Collection fue 44.00 s.

## 5. Decisiones de concurrencia

### Detail workers

Se validó `detail_workers=24` después de comparar 16 y 24 workers. Un aumento posterior a 28 no mostró una mejora relevante y fue descartado.

### Category workers

Se validó `category_workers=12` mediante pares balanceados con cobertura completa, cero retries y cero errores.

Un perfil posterior mostró:

| Métrica | 12 workers | 16 workers |
| --- | ---: | ---: |
| Profile wall time | 58.01 s | 62.76 s |
| Category HTTP total | 179.97 s | 202.59 s |
| Category HTTP promedio | 7.20 s | 8.10 s |
| Category HTTP máximo | 12.58 s | 15.40 s |
| Retries | 0 | 0 |
| Terminal errors | 0 | 0 |
| Cobertura | completa | completa |

El perfil con 16 workers fue más lento y elevó la latencia HTTP de categoría. Se mantiene 12.

### JSF

Se mantiene:

```
jsf_http_concurrency = 8
jsf_page_workers     = 2
category_page_workers = 1
```

Las repeticiones controladas no produjeron una mejora reproducible al aumentar el paralelismo de páginas.

### ImageSync

Benchmarks FULL previos:

| Image workers | Image Sync |
| ---: | ---: |
| 1 | 301.17 s |
| 8 | 44.43 s |
| 12 | 28.28 s |
| 16 | 20.19 s |

En el par balanceado disponible:

| Image workers | Run balanceado |
| ---: | ---: |
| 8 | 37.73 s |
| 16 | 28.30 s |

Promedios disponibles:

- 8 workers: 41.08 s;
- 16 workers: 24.25 s;
- reducción de ImageSync: 40.98%.

Se mantiene 16 como valor validado.

## 6. Ajustes de robustez incorporados

### Recuperación de precios

La recuperación ya no se dispara simplemente porque una descripción comercial contenga expresiones como `precio ciento`, `precio por caja` u otras frases incidentales.

La detección de recuperación está limitada a estructuras de precio conocidas:

- encabezados `h3/h4`;
- títulos dentro de bloques `.content-precio`.

Se incorporaron pruebas negativas e integración con `ProductCollectionScraper`.

### Paginación

El motor de paginación conserva el boundary probe salvo cuando metadata independiente confirma simultáneamente:

- total esperado alcanzado;
- `found_posts` coincidente;
- número de páginas esperado coincidente.

El benchmark controlado puede desactivar el probe para aislar la medición, sin cambiar el default productivo.

### Ciclo de vida del benchmark

Se eliminó el doble cierre del Browser. `ProductCollectionScraper.close()` ya propaga el cierre hacia el scraper/canal asociado.

### Concurrencia en tests

El test de agotamiento de reintentos JSF ya no exige un orden global de POST cuando las páginas 2 y 3 se ejecutan concurrentemente. Valida el contrato estable de intentos por página.

## 7. Calidad

Validación local confirmada antes del benchmark final:

- suite completa: 619 passed, 10 deselected;
- Ruff: limpio;
- Pyright: 0 errors, 0 warnings, 0 informations;
- test específico de concurrencia: 1 passed;
- tests específicos de auditoría: 32 passed.

El benchmark real posterior a la última sincronización también pasó: 1 passed.

## 8. Higiene del repositorio

El benchmark final escribió su reporte en un archivo temporal bajo `$env:TEMP`, no en `data/`.

Posteriormente se verificó:

- `data/` sin archivos JSON;
- `git status --short` vacío;
- HEAD local sincronizado con `origin/perf/real-image-benchmark`.

El `.gitignore` de la rama excluye `data/**/*.json` para artefactos generados localmente.

No se encontraron JSON de benchmark versionados en la rama auditada.

## 9. Documentación heredada de v0.2.0

`docs/FCM_FINAL_AUDIT_v0.2.0.md` y `docs/FCM_RELEASE_NOTES_v0.2.0.md` se conservan como documentación histórica de la release publicada.

No se sobreescriben retroactivamente con datos de v0.3.0.

Esta acta es aditiva y separa explícitamente la evidencia de rendimiento/robustez de la publicación histórica de v0.2.0.

## 10. Estado de GitHub

PR auditada:

- PR #17;
- base: `main`;
- head: `perf/real-image-benchmark`;
- estado: abierta;
- mergeable: true;
- fusionada: no;
- diferencia contra `main`: 83 commits por delante, 0 por detrás.

No se reportan checks CI asociados al HEAD auditado. Por ello, el cierre de calidad se fundamenta en la validación local documentada y en el benchmark real reproducido; no se declara un CI verde que no exista.

## 11. Gate de cierre pre-v0.3.0

```
[✅] Rama aislada y sin commits detrás de main
[✅] PR #17 abierta contra main
[✅] Concurrencia validada
[✅] Cobertura FULL 523/523
[✅] 24 categorías
[✅] 34/34 páginas cargadas
[✅] Detail recovery controlado
[✅] ImageSync 16 workers validado
[✅] 43/43 requests HTTP exitosas
[✅] 0 retries
[✅] 0 errores terminales
[✅] Ruff limpio
[✅] Pyright limpio
[✅] 619 tests pasados / 10 deselected
[✅] JSON temporales eliminados
[✅] Worktree limpio
[✅] Documentación v0.2.0 preservada
[✅] Auditoría final documentada
[⬜] Validación final de regresiones sobre el HEAD exacto del acta, si se requiere repetir la suite tras este cambio documental
[⬜] Decisión de promoción a main
[⬜] Publicación/tag v0.3.0
```

La rama no se fusiona como parte de esta acta. La promoción y la publicación permanecen como pasos separados y deliberados.


## 12. Seguimiento posterior — Exportador Excel

Actualización: 2026-10-04

La fase de rendimiento de scraping permanece cerrada con la evidencia documentada en esta auditoría. Posteriormente se trabajó de forma aislada sobre el exportador Excel mediante la PR #20, sin modificar el runtime de scraping ni la política de cobertura.

Estado del HEAD documental actual de la PR #20:

- PR #20 abierta contra `main`;
- base: `47a840f5`;
- head: `a3e3fb97`;
- `mergeable=true`;
- `mergeable_state=clean`;
- check `test`: **success**;
- check `live-catalog`: **skipped** de forma intencional.

El exportador queda temporalmente cerrado en este estado:

- selección de categorías antes de exportar;
- exportación únicamente del subconjunto seleccionado;
- XLSX estándar editable;
- imágenes embebidas con proporción preservada;
- `TwoCellAnchor` con `editAs="twoCell"`;
- margen interno de imagen de 4 px conservado;
- fila 2 de 78 pt;
- encabezado de 44 pt;
- sin tablas estructuradas;
- sin filtros automáticos;
- sin fondos de colores;
- sin COM ni inyección OOXML.

El intento de segmentación/slicer fue descartado después de producir el aviso de reparación de `/xl/worksheets/sheet1.xml` al abrir el XLSX. No forma parte del baseline final de esta iteración.

La última validación local informada antes del experimento temporal de ancho completo fue Ruff limpio, Pyright sin errores, 4 pruebas específicas de Excel pasadas y 626 pruebas de la suite con 10 deselected. El experimento temporal fue revertido y no debe considerarse un cambio funcional pendiente.

Este seguimiento no reabre la auditoría de scraping. Cualquier cambio posterior de exportación debe preservar la separación de responsabilidades: no alterar scraping, persistencia, cobertura ni concurrencia sin ejecutar nuevamente sus gates específicos.

## 13. Gate actualizado de promoción

A partir de este seguimiento, la publicación de `v0.3.0` queda condicionada por tres niveles:

```
Excel estable
    ↓
PR #20 validada + revisión del XLSX real
    ↓
merge controlado a main
    ↓
suite completa + smoke GUI
    ↓
regresión de exportadores
    ↓
build Windows
    ↓
validación del instalador
    ↓
tag/release v0.3.0
```

El hecho de que la PR #20 esté `mergeable` y tenga `test=success` no equivale todavía a una publicación de `v0.3.0`.
