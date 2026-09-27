# FCM — Post-release roadmap

Fecha: 2026-09-27  
Baseline estable: `v0.1.1`  
Tag: `v0.1.1`  
Commit de release: `4238a9f`  
Siguiente versión en preparación: `0.2.0`  
Rama de desarrollo: `main`

## Estado

La versión `0.1.1` está publicada y el ciclo principal de estabilización quedó cerrado. El proyecto no tiene actualmente pendientes técnicos bloqueantes ni issues abiertas.

La referencia funcional vigente es:

- 24 categorías
- 523 apariciones
- 519 productos únicos
- 4 productos multi-categoría
- 523 relaciones producto-categoría
- `coverage_complete=1`
- `coverage_gap=0`
- 0 errores invalidantes
- Producción: 8 workers de categoría / 24 de detalle / 28 HTTP
- Última suite local confirmada antes de los cambios de `0.2.0`: 577 passed, 10 deselected
- Ruff limpio
- Pyright sin errores, advertencias ni informaciones

## Próxima etapa

### 1. Experiencia de instalación
- [x] Cubrir con tests focalizados la validación de la semilla SQLite/imágenes usada por el empaquetado Windows.
- [x] Incorporar un icono de aplicación Windows propio y consistente.
- [x] Añadir acceso directo opcional en el Escritorio.
- [x] Mantener el acceso directo del menú Inicio.
- [x] Validar icono, acceso directo e instalación en una nueva revisión del instalador.

La identidad visual, acceso directo del menú Inicio, acceso directo opcional del Escritorio y ciclo de instalación/reinstalación/actualización/desinstalación quedaron validados en Windows para `v0.1.1`. La release `0.1.1` se conserva sin modificaciones.

### 2. Pulido de GUI
- [x] Validar la tipografía base de la tabla y categorías: Segoe UI con 13 px para contenido.
- [x] Validar el espaciado interno de celdas y el contrato de 4 px para contenido de Stock/categorías.
- [x] Validar navegación ↑/↓ de categorías con foco visible, marco negro único y desplazamiento exclusivamente vertical.
- [x] Mantener el renderizado progresivo y los filtros sin reconstrucción masiva de la tabla.
- [x] Revisar de forma agrupada los anchos restantes de columnas de la tabla, aplicando cambios solo donde exista evidencia visual concreta.
- [x] Evitar recalcular las métricas completas de ancho durante cada redimensionamiento de ventana.
- [x] Validar el ajuste de caché con tests locales y completar el smoke manual final.
- [x] Ajustar el historial: marco de selección con holgura vertical simétrica, PRODUCTO envuelto al ancho disponible y CÓDIGO ordenado alfanuméricamente.

El bloque GUI de `main` está cerrado. La evidencia más reciente anterior a la candidata `0.2.0` fue la revisión visual del historial, incluyendo holgura vertical simétrica, wrapping de PRODUCTO al ancho disponible y ordenamiento alfanumérico de CÓDIGO.

### 3. Scraping y rendimiento
- [x] Mantener category workers en `8` y HTTP workers en `28`.
- [x] Mantener JSF page workers en `2` y category-page workers en `1`.
- [x] Comparar `detail_workers=16` vs `24` con dos parejas reales y cobertura completa.
- [x] Validar `detail_workers=24` en el E2E productivo completo, incluyendo SQLite e historial.
- [x] Ejecutar la validación FULL post-cambio con el runtime productivo `8 / 24 / 28`.
- [x] Convertir la regla de evidencia en una validación automática: el comparador rechaza cobertura incompleta y errores HTTP terminales.
- [x] Mantener la regla de no aceptar una optimización únicamente por una corrida rápida: debe conservar cobertura, persistencia e historial.
- [x] Disponer de un comparador reproducible de artefactos benchmark para revisar configuración, cobertura y deltas de tiempo/HTTP sin interpretar manualmente los resultados.
- [x] Ejecutar dos parejas reales `detail_workers=16` vs `24` con cobertura completa y cero errores; `24` redujo el tiempo de pared en ambas parejas.
- [x] Validar `detail_workers=24` en E2E real de extremo a extremo y repetirlo con el default productivo: `24/523/519/4`, DB `519/523`, historial aplicado, `333` requests, `0` retries, `0` errores terminales; última corrida `121.48s`.
- [x] Preparar el E2E productivo real para ejecutar `detail_workers` configurable mediante `FCM_E2E_DETAIL_WORKERS`, tomando ahora el default productivo de `ScrapingConfig` (`24`).
- [x] Repetir el E2E sin override para confirmar que el valor productivo efectivo permanece en `24`.
- [x] Validar localmente el comparador con la suite y dos parejas reales de artefactos benchmark.


### 4. Observabilidad y mantenimiento
- [x] Mantener las métricas de cobertura, retries, tiempos y progreso como evidencia de diagnóstico; el pipeline ya dispone de telemetría y artefactos comparables.
- [x] Mantener las herramientas destructivas legacy bloqueadas o explícitamente controladas.
- [x] Revisar y normalizar la documentación para que el baseline vivo no quede mezclado con snapshots antiguos.
- [x] Mantener backup/restore cubierto antes de cambios sobre persistencia.

### 5. Versionado y releases
- [x] Baseline estable `v0.1.1` publicado.
- [x] Centralizar la versión de aplicación en `VERSION` y propagarla a la aplicación y al bundle Windows.
- [x] Eliminar fallback de versión antigua en Inno Setup.
- [x] Alinear Pyright de CI con `requirements.txt`.
- [x] Tag `v0.1.1` publicado.
- [x] Instalador y SHA256 publicados.
- [ ] Acumular futuros cambios sobre `main` y publicar una nueva versión solo cuando el conjunto de cambios esté validado.
- [ ] Para una futura release, repetir la cadena: tests → validación funcional → Windows Build → artefactos → tag → release.

## Próximo punto de desarrollo

Con la GUI, observabilidad y hardening de distribución cerrados, `main` contiene ahora la preparación técnica de `v0.2.0`: versión centralizada, validación de semilla Windows consolidada y CI alineado. La última suite local confirmada antes de la candidata fue `577 passed, 10 deselected`, con Ruff y Pyright limpios.

## Regla de seguridad del desarrollo

Todo cambio que afecte scraping, persistencia, concurrencia, imágenes o reconciliación debe preservar las invariantes del baseline vivo:

`24 categorías + cobertura completa + 0 errores invalidantes + persistencia consistente + historial correcto`

El tag `v0.1.1` se conserva como punto de rollback y comparación. No se reutiliza ni se mueve.

## Criterio de cierre de una futura versión

Una futura versión se considerará lista cuando:

1. el cambio solicitado esté implementado y cubierto;
2. Ruff y Pyright estén limpios;
3. la suite automatizada esté verde;
4. se valide el comportamiento real afectado;
5. cualquier cambio de scraping/concurrencia conserve la cobertura viva;
6. la documentación refleje el estado real;
7. el artefacto Windows correspondiente haya sido validado;
8. el tag y la release apunten al commit exacto que se pretende publicar.
