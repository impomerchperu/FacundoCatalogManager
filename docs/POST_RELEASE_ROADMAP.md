# FCM — Post-release roadmap

Fecha: 2026-09-26  
Baseline estable: `v0.1.1`  
Tag: `v0.1.1`  
Commit de release: `4238a9f`  
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
- Producción: 8 workers de categoría / 16 de detalle / 28 HTTP
- Suite local: 534 passed, 10 deselected
- Ruff limpio
- Pyright sin errores, advertencias ni informaciones

## Próxima etapa

### 1. Experiencia de instalación
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

La revisión agrupada del 2026-09-26 confirmó que no existe evidencia suficiente para alterar arbitrariamente los anchos de Imagen, Código, Producto, Detalle o Precios. Los contratos existentes de Categoría y Stock se conservan sin cambios. Como mejora de rendimiento de bajo riesgo, `ProductTable` ahora reutiliza las mediciones de ancho preferido durante los `resizeEvent` y las invalida cuando cambia el contenido, la referencia completa del catálogo o el contenido dinámico del encabezado. La prueba focalizada pasó localmente (`19 passed`) y la suite completa quedó en `534 passed, 10 deselected`; el smoke manual final también fue completado sobre `main`.

### 3. Scraping y rendimiento
- [ ] No modificar todavía la configuración productiva `8 / 16 / 28`.
- [ ] Mantener JSF page workers en `2` y category-page workers en `1`.
- [ ] Si aparece una regresión real de runtime, aislarla primero con benchmark controlado.
- [ ] No aceptar una optimización únicamente por una corrida rápida: debe conservar cobertura, persistencia e historial.
- [ ] Repetir FULL/E2E después de cualquier cambio de runtime que afecte scraping o concurrencia.
- [x] Disponer de un comparador reproducible de artefactos benchmark para revisar configuración, cobertura y deltas de tiempo/HTTP sin interpretar manualmente los resultados.
- [ ] Validar localmente el comparador con la suite y una pareja real de artefactos benchmark.


### 4. Observabilidad y mantenimiento
- [ ] Mantener las métricas de cobertura, retries, tiempos y progreso como evidencia de diagnóstico.
- [ ] Mantener las herramientas destructivas legacy bloqueadas o explícitamente controladas.
- [ ] Revisar periódicamente que la documentación no mezcle snapshots históricos con el baseline vivo.
- [ ] Mantener backup/restore cubierto antes de cambios sobre persistencia.

### 5. Versionado y releases
- [x] Baseline estable `v0.1.1` publicado.
- [x] Tag `v0.1.1` publicado.
- [x] Instalador y SHA256 publicados.
- [ ] Acumular futuros cambios sobre `main` y publicar una nueva versión solo cuando el conjunto de cambios esté validado.
- [ ] Para una futura release, repetir la cadena: tests → validación funcional → Windows Build → artefactos → tag → release.

## Regla de seguridad del desarrollo

Todo cambio que afecte scraping, persistencia, concurrencia, imágenes o reconciliación debe preservar las invariantes del baseline:

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
