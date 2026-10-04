# FCM — Plan Maestro

Fecha de actualización: 2026-10-04
Branch oficial: `main`
Estado: `main` mantiene el baseline funcional de `v0.2.0`; la siguiente línea de trabajo es el cierre y promoción controlada del conjunto pre-`v0.3.0`, con la PR #20 dedicada al exportador Excel.

## 1. Objetivo del proyecto

Facundo Catalog Manager (FCM) es una aplicación de escritorio Python + PySide6 para mantener el catálogo de Importaciones Facundo con cuatro propiedades centrales:

1. Obtener el inventario publicado por el sitio.
2. Validar que una ejecución FULL sea completa y coherente antes de sustituir el catálogo.
3. Persistir productos, relaciones, historial y cambios de forma transaccional.
4. Presentar y operar el catálogo sin bloquear la interfaz durante las tareas pesadas.

La autoridad funcional se divide de forma explícita:

- El sitio y sus conteos actuales son la autoridad para la cobertura de cada FULL.
- `scraping_runs` conserva la trazabilidad de ejecuciones y respalda recuperación/reconciliación.
- `scraping_history.applied_at` identifica la versión de historial actualmente aplicada.
- `products` es la fuente persistente del catálogo que utiliza la GUI.
- `products.image_path` determina qué archivos de imagen están activos.

## 2. Estado funcional actual

### Cobertura operativa
- 24 categorías.
- 523 apariciones producto-categoría.
- 519 productos únicos.
- 4 productos multi-categoría.
- 523 relaciones producto-categoría.
- `coverage_complete=1`.
- `coverage_gap=0`.
- 0 errores invalidantes.

### Runtime de scraping validado
- Categorías: 12 workers.
- Detalle: 24 workers.
- HTTP: 28 workers.
- JetSmartFilters: 8 solicitudes concurrentes.
- Páginas de categoría: 1 worker.
- Páginas JSF: 2 workers.
- Sesiones HTTP por hilo: activadas en el benchmark validado.
- Timeout: 20 s.
- Reintentos máximos: 3.
- ImageSync: 16 workers en el benchmark final validado.

## 3. Plan por fases

### Fase A — Fundación
- [x] Python + PySide6.
- [x] SQLite.
- [x] Modelo `Product`.
- [x] Repository / Service / Controller.
- [x] CRUD.
- [x] Migraciones.
- [x] Validaciones.

### Fase B — Descubrimiento y scraping
- [x] Descubrimiento de categorías.
- [x] Extracción de productos.
- [x] Paginación.
- [x] JetSmartFilters.
- [x] Recuperación de páginas incompletas.
- [x] Recuperación de códigos/SKU.
- [x] Enriquecimiento de detalle.
- [x] Consolidación.
- [x] Multi-categoría.
- [x] Cobertura por conteos publicados.
- [x] Manejo de errores.
- [x] FULL versus dirigido.

### Fase C — Seguridad de persistencia
- [x] Transacciones.
- [x] Atomicidad.
- [x] Rollback.
- [x] Protección del prune.
- [x] No sustituir catálogo por FULL incompleto.
- [x] No sustituir catálogo por FULL fallido.
- [x] Recuperación del FULL válido más reciente.
- [x] Bootstrap/reconciliación.
- [x] Idempotencia.

### Fase D — Historial
- [x] Registro de ejecuciones.
- [x] Duración.
- [x] Estado.
- [x] Cobertura.
- [x] `applied_at`.
- [x] Cambios `NEW`, `UPDATED`, `DELETED`.
- [x] Detalle por código.
- [x] Versiones aplicadas/no aplicadas.
- [x] Errores.
- [x] Conservación histórica.

### Fase E — Stock por color
- [x] Extracción demostrable de color/cantidad.
- [x] Persistencia `color_stock`.
- [x] Validación contra stock total.
- [x] No inventar distribución.
- [x] Presentación visual.
- [x] Detección de cambios.
- [x] Idempotencia.
- [x] Validación real sobre las 24 categorías.

### Fase F — Imágenes
- [x] Ruta canónica.
- [x] Hash SHA-256.
- [x] Descarga.
- [x] Auditoría.
- [x] Detección de huérfanos.
- [x] Limpieza segura.
- [x] Limpieza posterior a FULL válido.
- [x] Protección frente a ejecuciones no válidas.

### Fase G — GUI funcional
- [x] Ventana principal.
- [x] Tabla.
- [x] Imágenes.
- [x] Categorías.
- [x] Stock.
- [x] Precios.
- [x] Búsqueda.
- [x] Filtro de categorías.
- [x] Filtro de stock.
- [x] Ordenamiento.
- [x] CRUD.
- [x] Excel/PDF/CSV.
- [x] Actualización.
- [x] Historial.
- [x] Progreso y detalle.

### Fase H — Rendimiento de GUI
- [x] Mostrar la ventana antes de completar bootstrap.
- [x] Bootstrap fuera del hilo UI.
- [x] Lectura inicial de SQLite fuera del hilo UI.
- [x] Dependencias de uso puntual bajo demanda.
- [x] Renderizado inicial progresivo.
- [x] Evitar reconstrucción completa durante filtros.
- [x] Búsqueda sobre filas existentes.
- [x] Stock sobre filas existentes.
- [x] Categorías sobre filas existentes.
- [x] Aparición inmediata del panel de categorías.
- [x] Tests de startup y workers.
- [x] Prueba explícita de cierre seguro de workers.

### Fase I — Rendimiento de scraping
- [x] Benchmark base.
- [x] Comparación de workers de categoría.
- [x] Comparación de workers de detalle.
- [x] Validación E2E productiva completa con `24` workers de detalle.
- [x] Comparación JSF page workers.
- [x] Diagnóstico de transporte HTTP.
- [x] Telemetría P50/P95/P99.
- [x] Benchmark SQLite.
- [x] Validación de `12 / 24 / 28` para categoría/detalle/HTTP.
- [x] Validación de `1` worker de página de categoría y `2` workers de páginas JSF.
- [x] Validación de `16` image workers para ImageSync.
- [x] No cambiar runtime sin evidencia reproducible.

### Fase J — Calidad
- [x] Ruff.
- [x] Pyright.
- [x] Suite automatizada.
- [x] Tests de recuperación.
- [x] Tests de cobertura.
- [x] Tests de historial.
- [x] Tests de concurrencia.
- [x] Tests de stock por color.
- [x] Tests de GUI.
- [x] Tests de startup.
- [x] Tests de workers.

## 4. Validación actual

La última validación local completa informada durante la línea de trabajo Excel alcanzó:

```
Ruff    → limpio
Pyright → 0 errors
Pytest  → 626 passed, 10 deselected
Excel   → 4 pruebas específicas pasadas
```

El conteo de 626 corresponde al estado estable anterior al experimento temporal de encaje a ancho completo; dicho experimento fue revertido. El estado actual conserva la implementación con margen interno de imagen de 4 px.

La referencia real del catálogo continúa siendo `24 / 523 / 519 / 4`, con cobertura completa e invariantes de stock por color. El benchmark final pre-`v0.3.0` validó además `43/43` requests HTTP exitosas, `0` retries y `0` errores terminales.

La validación real del catálogo permanece gobernada por `24 / 523 / 519 / 4` y por las invariantes de cobertura, persistencia e integridad de stock por color.

## 5. Criterio de aceptación de futuros cambios

Un cambio de scraping, persistencia o concurrencia debe conservar cobertura completa contra los conteos publicados en la ejecución actual, `coverage_complete=1`, `coverage_gap=0`, cero errores invalidantes, protección de prune, integridad de relaciones, integridad de `color_stock` cuando corresponda e idempotencia.

Los cambios exclusivamente de GUI pueden validarse con la suite local y smoke manual cuando no alteren el runtime de scraping o persistencia.

## 6. Estado de cierre técnico

### Hardening
- [x] Contrato/prueba de cierre para `catalog_bootstrap_thread`.
- [x] Contrato/prueba de cierre para `catalog_load_thread`.
- [x] Cierre de aplicación espera la finalización de los workers de catálogo activos.
- [x] Referencias de los workers de catálogo se limpian mediante sus callbacks de finalización.

### Distribución
- [x] Definir empaquetado Windows.
- [x] Producir ejecutable.
- [x] Definir instalador.
- [x] Documentar actualización de versiones.
- [x] Definir backup/restauración de `catalog.db`.
- [x] Preparar checklist de release.
- [x] Validar bundle, instalador, actualización, reinstalación, desinstalación y backup/restore para `v0.1.1`.
- [x] Validar Windows Build CI y su artefacto de smoke de empaquetado.

### Documentación y mantenimiento
- [x] Plan maestro vigente.
- [x] README alineado con el comportamiento actual.
- [x] Criterios operativos de scraping.
- [x] Documentación de release y Windows.
- [x] Auditoría final de release.
- [x] Auditoría de limpieza profunda del repositorio.
- [x] Contextos históricos redundantes consolidados o retirados.

## 7. Regla de estabilidad

No cambiar scraping, concurrencia, persistencia o cobertura por intuición o por una sola medición.

Secuencia:

```
cambio
  ↓
tests
  ↓
benchmark controlado
  ↓
FULL real cuando corresponda
  ↓
validación de DB/historial
  ↓
documentación
  ↓
main
```

## 8. Próximo hito

El hardening de workers, la cobertura FULL, el historial, la distribución y el pulido visual quedaron consolidados. La siguiente acción de release es ejecutar el build Windows de `0.2.0`, validar sus artefactos y completar tag/release.

Mientras tanto, `main` es el baseline funcional de referencia.


### Estado de distribución Windows

La infraestructura de distribución está implementada en `main`: rutas persistentes para instalaciones congeladas, `VERSION`, spec de PyInstaller, instalador Inno Setup, script PowerShell, workflow manual de Windows y herramientas de backup/restauración. La producción física del bundle/instalador y su validación sobre Windows ya fueron completadas y validadas para `v0.1.1`.


## 9. Estado actual de exportadores y promoción

### Excel

La PR #19 ya fue integrada en `main` y dejó alineados los exportadores con el contrato actual del catálogo. La PR #20, actualmente abierta contra `main`, contiene el rediseño estable del exportador Excel y la selección de categorías.

Estado documentado del exportador en la rama activa:

- [x] selección de categorías antes de exportar;
- [x] exportar únicamente productos de las categorías seleccionadas;
- [x] XLSX estándar y editable mediante `openpyxl`;
- [x] imágenes embebidas;
- [x] imágenes con `TwoCellAnchor` y `editAs="twoCell"`;
- [x] proporción de imagen preservada;
- [x] margen interno de 4 px conservado como estado visual estable;
- [x] fila 2 con 78 pt;
- [x] encabezados en 44 pt, centrados y en negrita;
- [x] alineaciones y formato monetario actuales;
- [x] sin `Table`;
- [x] sin filtros automáticos;
- [x] sin fondos de colores;
- [x] sin COM ni inyección OOXML;
- [x] intento de slicer/segmentación descartado tras producir reparación de `/xl/worksheets/sheet1.xml`;
- [x] pruebas específicas del exportador: 4 passed en la última validación informada.

El bloque Excel se considera cerrado temporalmente. Nuevas mejoras visuales o de filtrado deben ser una nueva iteración aislada y no deben reabrir este baseline sin evidencia.

La PR #20 no modifica scraping, persistencia, cobertura ni concurrencia; por ello su aceptación no requiere repetir el benchmark FULL real, salvo que una futura modificación salga de ese alcance.

### Estado de PR

- PR #20: abierta;
- base: `main`;
- head: `fix/excel-table-repair`;
- mergeable: true;
- estado de merge actual: limpio;
- check `test` fue success en `a3e3fb97`; los commits documentales posteriores (`5895f870` y `ca782a65`) generan nuevos workflows Quality sobre sus respectivos HEAD y deben validarse por separado;
- `live-catalog`: skipped intencionalmente.

La promoción a `main` no se considera completada hasta cerrar la validación local y revisar el diff completo de la PR.

### Gate de promoción

Antes de fusionar cualquier cambio pre-`v0.3.0`:

1. sincronizar la rama local exactamente con su remoto;
2. ejecutar Ruff y Pyright;
3. ejecutar la prueba focal de Excel y la suite completa;
4. revisar que `git status --short` esté limpio;
5. verificar apertura del XLSX real sin advertencias de reparación;
6. confirmar que la selección de categorías exporta exactamente el subconjunto esperado;
7. revisar el estado de los checks de GitHub;
8. solo después decidir merge a `main`.

La validación FULL real no debe repetirse por cambios puramente de Excel que no toquen scraping, persistencia, cobertura ni runtime; el benchmark real sigue siendo obligatorio para futuros cambios de esas áreas.

## 10. Ruta hacia v0.3.0

El camino de cierre queda deliberadamente separado en capas:

### Capa 1 — Integración funcional
- [ ] cerrar y fusionar PR #20 cuando la validación local y el artefacto Excel sean aceptados;
- [ ] confirmar que `main` conserva el baseline de scraping, persistencia, stock por color e imágenes;
- [ ] ejecutar suite completa sobre el HEAD resultante de `main`.

### Capa 2 — Regresión operativa
- [ ] smoke test GUI completo sobre el HEAD integrado;
- [ ] verificar actualización, historial, filtros de categorías y exportadores;
- [ ] confirmar apertura real de Excel, PDF y CSV generados;
- [ ] verificar que la selección de categorías no altera el catálogo persistido.

### Capa 3 — Release
- [ ] actualizar versión de desarrollo/release según el criterio de `v0.3.0`;
- [ ] actualizar notas de release y auditoría final;
- [ ] ejecutar build Windows;
- [ ] validar bundle e instalador;
- [ ] validar instalación/actualización/desinstalación;
- [ ] validar backup/restore de `catalog.db`;
- [ ] publicar tag y release `v0.3.0`.

Estos gates deben mantenerse separados: un cambio de exportación no debe desbloquear por sí solo la publicación sin la regresión de release correspondiente.

## 11. Regla para continuar

La fase Excel queda cerrada temporalmente. La siguiente iteración debe avanzar por validación e integración, no por nuevas modificaciones de diseño, salvo que aparezca un defecto reproducible.

Para scraping, persistencia, concurrencia o cobertura, mantener siempre:

```
cambio
  ↓
tests
  ↓
benchmark controlado
  ↓
FULL real
  ↓
validación DB/historial
  ↓
documentación
  ↓
main
```
