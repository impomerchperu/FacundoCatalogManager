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
- Suite local: 507 passed, 10 deselected
- Ruff limpio
- Pyright sin errores, advertencias ni informaciones

## Próxima etapa

### 1. Experiencia de instalación
- [ ] Incorporar un icono de aplicación Windows propio y consistente.
- [ ] Añadir acceso directo opcional en el Escritorio.
- [ ] Mantener el acceso directo del menú Inicio.
- [ ] Validar icono, acceso directo e instalación en una nueva revisión del instalador.

Estos cambios pertenecen a una futura versión y no modifican la release `0.1.1`.

### 2. Pulido de GUI
- [ ] Revisar de forma agrupada tipografía, espaciados y anchos de columnas.
- [ ] Revisar la presentación de Stock y categorías sin alterar los contratos funcionales ya validados.
- [ ] Mantener el renderizado progresivo y los filtros sin reconstrucción masiva de la tabla.
- [ ] Validar cada ajuste visual con tests y smoke manual cuando corresponda.

### 3. Scraping y rendimiento
- [ ] No modificar todavía la configuración productiva `8 / 16 / 28`.
- [ ] Mantener JSF page workers en `2` y category-page workers en `1`.
- [ ] Si aparece una regresión real de runtime, aislarla primero con benchmark controlado.
- [ ] No aceptar una optimización únicamente por una corrida rápida: debe conservar cobertura, persistencia e historial.
- [ ] Repetir FULL/E2E después de cualquier cambio de runtime que afecte scraping o concurrencia.

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
