# FCM — Plan Maestro

Fecha de actualización: 2026-10-25
Rama predeterminada/de promoción: `main` (`47a840f5`, corte de auditoría)
Rama de integración activa: `feat/product-table-layout` (HEAD de código/pruebas validado por CI: `19513cda`; commits posteriores solo documentales)
Estado: `main` sigue en el commit que integró la PR #19 el 2026-10-02. La rama de integración es descendiente directo de `main` y no está detrás. El usuario confirmó localmente en `b611d17a` Ruff limpio, Pyright sin errores/advertencias/informaciones, 57 pruebas focales aprobadas y 983 pruebas aprobadas con 11 deseleccionadas. Después se añadieron tres regresiones de migraciones SQLite y una migración v6 para preservar nombres de color heredados sin inventar stock; GitHub Quality CI pasó para `19513cda` (Ruff, Pyright y Pytest en éxito; `live-catalog` omitido intencionalmente). Esta validación no debe confundirse con una validación del HEAD de `main`.

La PR de promoción es la [#30](https://github.com/impomerchperu/FacundoCatalogManager/pull/30), abierta en borrador contra `main`. Las PR #20, #23, #24, #28 y #29 se cerraron como supersedidas después de comparar contenido y consolidar una sola ruta de integración. Sus referencias de rama no se borraron. La PR #30 permanece sin fusionar hasta cerrar los bloqueos de cobertura, rendimiento y auditoría de base local y completar la revisión del diff neto. GitHub reporta el diff limpio; Quality CI pasó en el HEAD de código/pruebas `19513cda` y nuevamente en el HEAD documental `0536819e`. Las referencias antiguas de ramas siguen conservadas.

El checklist maestro actualizado de ramas, migraciones SQLite, consolidación de archivos/carpetas, imágenes, cobertura y promoción a `main` está en [FCM_BRANCH_AND_PROJECT_CLEANUP_CHECKLIST.md](FCM_BRANCH_AND_PROJECT_CLEANUP_CHECKLIST.md). Sus hallazgos y gates de cierre prevalecen sobre las referencias históricas de estado que queden en secciones anteriores de este documento.

**Mitigación de migración:** el esquema v6 copia el contenido heredado de `colors` a `legacy_colors` antes de quitar la columna antigua, si los valores aún existen, y no convierte los nombres en cantidades de stock. **Pendiente de auditoría local:** si la base persistente ya fue migrada por una versión anterior que eliminaba `colors` sin copia, comprobar si hay un backup anterior que permita recuperarlos; esa información no puede reconstruirse a partir de la base ya migrada.

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
- Categorías: 12 workers en la configuración actual. La auditoría nueva debe reconciliar este valor con una comparación previa que informó mejor tiempo con 8; no se cambiará la concurrencia sin repetir mediciones controladas.
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

La siguiente prioridad es restablecer una ruta de promoción controlada desde `feat/product-table-layout` hacia `main`, resolver PR apiladas y completar la limpieza segura de ramas, migraciones, archivos y herramientas conforme al checklist maestro de auditoría.

Mientras tanto, `main` es el baseline funcional de referencia.


### Estado de distribución Windows

La infraestructura de distribución está implementada en `main`: rutas persistentes para instalaciones congeladas, `VERSION`, spec de PyInstaller, instalador Inno Setup, script PowerShell, workflow manual de Windows y herramientas de backup/restauración. La producción física del bundle/instalador y su validación sobre Windows ya fueron completadas y validadas para `v0.1.1`.


## 9. Estado actual de exportadores y promoción

### Excel

La PR #19 ya fue integrada en `main` y dejó alineados los exportadores con el contrato actual del catálogo. El contenido del rediseño Excel de la antigua PR #20 está incluido en la rama de integración; esa PR fue cerrada como supersedida por la ruta única de promoción #30.

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

El contenido original de la PR #20 era un cambio aislado del exportador y no requería repetir el benchmark FULL real. Al cerrarse como supersedida, su promoción queda incluida en la ruta consolidada #30, que sí requiere resolver los gates comunes de integración.

### Estado de PR

- PR #20: cerrada como supersedida por #30; no fusionada separadamente.
- La ruta vigente de promoción es PR #30, borrador desde `feat/product-table-layout` hacia `main`.
- Validación local de `b611d17a`: Ruff limpio, Pyright sin errores/advertencias/informaciones, 57 pruebas focales y 983 pruebas de suite (11 deseleccionadas).
- Quality CI para el HEAD de código/pruebas `19513cda`: Ruff, Pyright y Pytest en éxito; `live-catalog` skipped por diseño.
- Bloqueos: reconciliar 522 vs 523 apariciones del catálogo, repetir perfiles comparables 12 vs 8 workers de categoría, determinar si la base local ya perdió nombres de `colors` por migraciones anteriores y completar la revisión del diff neto.

La promoción a `main` no se considera completada hasta cerrar estos gates y validar el HEAD resultante de `main`.
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
- [ ] completar los gates de PR #30 y promover el conjunto consolidado a `main` solo después de resolver cobertura, rendimiento, revisión neta y CI.
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


### Validación manual Excel cerrada

El 2026-10-04 se completó satisfactoriamente el smoke funcional real del exportador Excel. Se verificaron selección individual y múltiple de categorías, cancelación sin exportación, apertura sin reparación de XLSX, imágenes visibles y proporcionales, anclaje/redimensionamiento con celdas, ausencia de filtros/tablas/fondos y exactitud de encabezados, precios, COLOR y STOCK.

El gate funcional del exportador queda **cerrado** y su contenido está incluido en la rama de integración. La promoción se realizará mediante PR #30 junto con el resto del conjunto validado; no se requieren más cambios de diseño en Excel salvo defecto reproducible.
