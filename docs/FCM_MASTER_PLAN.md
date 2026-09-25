# FCM — Plan Maestro

Fecha: 2026-09-24
Branch oficial: `main`
HEAD actual: `4bee4fe7`

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

### Snapshot histórico protegido
- 24 categorías.
- 534 apariciones.
- 530 productos únicos.
- 4 multi-categoría.
- 534 relaciones.

Este snapshot es diagnóstico e histórico. No bloquea una ejecución válida cuando los conteos publicados actualmente por el sitio han cambiado.

### Runtime de scraping validado
- Categorías: 8 workers.
- Detalle: 16 workers.
- HTTP: 28 workers.
- JetSmartFilters: 8.
- Timeout: 20 s.
- Reintentos máximos: 3.

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
- [x] Comparación JSF page workers.
- [x] Diagnóstico de transporte HTTP.
- [x] Telemetría P50/P95/P99.
- [x] Benchmark SQLite.
- [x] Mantener `8 / 16 / 28` como runtime productivo.
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

Estado local validado por el usuario en `main` el 2026-09-24:

```
Ruff    → All checks passed!
Pyright → 0 errors, 0 warnings, 0 informations
Pytest  → 487 passed, 10 deselected
```

La validación real del catálogo permanece gobernada por `24 / 523 / 519 / 4` y por las invariantes de cobertura, persistencia e integridad de stock por color.

## 5. Criterio de aceptación de futuros cambios

Un cambio de scraping, persistencia o concurrencia debe conservar cobertura completa contra los conteos publicados en la ejecución actual, `coverage_complete=1`, `coverage_gap=0`, cero errores invalidantes, protección de prune, integridad de relaciones, integridad de `color_stock` cuando corresponda e idempotencia.

Los cambios exclusivamente de GUI pueden validarse con la suite local y smoke manual cuando no alteren el runtime de scraping o persistencia.

## 6. Pendientes reales

### Hardening
- [x] Contrato/prueba de cierre para `catalog_bootstrap_thread`.
- [x] Contrato/prueba de cierre para `catalog_load_thread`.
- [x] Cierre de aplicación espera la finalización de los workers de catálogo activos.
- [x] Referencias de los workers de catálogo se limpian mediante sus callbacks de finalización.

### Distribución
- [ ] Definir empaquetado Windows.
- [ ] Producir ejecutable.
- [ ] Definir instalador.
- [ ] Documentar actualización de versiones.
- [ ] Definir backup/restauración de `catalog.db`.
- [ ] Preparar checklist de release.

### Documentación
- [x] Plan maestro.
- [x] README alineado con el comportamiento actual.
- [x] Release checkpoint alineado.
- [x] Architecture checkpoint alineado.
- [ ] Mantener estos documentos actualizados ante cambios estructurales.

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

El hardening de los workers de catálogo quedó completado. El siguiente hito técnico es preparar el empaquetado Windows y su checklist de release.

Mientras tanto, `main` es el baseline funcional de referencia.
