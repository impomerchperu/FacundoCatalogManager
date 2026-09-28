# FCM — Auditoría general final para v0.2.0

Fecha: 2026-09-27  
Rama oficial: `main`  
Versión publicada: `0.2.0`  
HEAD de referencia de esta acta: `a95647f`  
Release estable anterior: `v0.1.1` → `4238a9f`

## 1. Gobierno del repositorio

- [x] `main` es la rama por defecto.
- [x] No existen issues abiertas.
- [x] No existen pull requests abiertas.
- [x] La release `v0.1.1` permanece publicada y sin mover.
- [x] El tag `v0.1.1` continúa apuntando al commit de release `4238a9f`.
- [x] No se reutiliza ni modifica el tag histórico.

## 2. Referencia funcional protegida

- [x] 24 categorías.
- [x] 523 apariciones producto-categoría.
- [x] 519 productos únicos.
- [x] 4 productos multi-categoría.
- [x] 523 relaciones producto-categoría.
- [x] `coverage_complete=1`.
- [x] `coverage_gap=0`.
- [x] 0 errores invalidantes.
- [x] Runtime productivo conservado en `8 / 24 / 28`.

Las métricas operativas de release se gobiernan por los conteos publicados por el sitio en cada ejecución FULL; no se utiliza un snapshot histórico como piso de cobertura.

## 3. Scraping y persistencia

- [x] Protección de FULL incompleto y fallido.
- [x] Protección de prune destructivo.
- [x] Recuperación/reconciliación del FULL válido más reciente.
- [x] Idempotencia del sync.
- [x] Historial aplicado y trazabilidad de ejecuciones.
- [x] Stock por color validado en el flujo real.
- [x] Imágenes con allowlist basada en `products.image_path`.
- [x] No se modificó el runtime productivo durante el cierre de `v0.2.0`.

## 4. GUI

- [x] Arranque fuera del hilo UI.
- [x] Renderizado progresivo.
- [x] Filtros sin reconstrucción masiva.
- [x] Navegación de categorías y scroll vertical.
- [x] Contratos visuales de Stock/Categoría.
- [x] Historial con holgura vertical simétrica.
- [x] PRODUCTO ajustado al ancho disponible.
- [x] CÓDIGO con ordenamiento alfanumérico.
- [x] Cambios GUI recientes cubiertos por tests.

## 5. Observabilidad

- [x] Comparador de benchmarks reproducible.
- [x] Rechazo de cobertura incompleta.
- [x] Rechazo de `coverage_gap != 0`.
- [x] Rechazo de `coverage_complete != True`.
- [x] Rechazo de errores de cobertura.
- [x] Rechazo de errores HTTP terminales.
- [x] Rechazo de métricas negativas.
- [x] Sin clasificación artificial de benchmarks como ganadores/perdedores.

## 6. Distribución y versionado

- [x] Versión centralizada en `VERSION`.
- [x] La aplicación publica nombre y versión mediante `QApplication`.
- [x] `VERSION` se incorpora al bundle PyInstaller.
- [x] Build local verifica que la versión del bundle coincida con `VERSION`.
- [x] Windows CI verifica la misma coincidencia.
- [x] Inno Setup ya no tiene fallback silencioso a una versión antigua.
- [x] Windows CI fija Inno Setup `7.1.0`.
- [x] Pyright de CI utiliza la versión fijada por `requirements.txt`.
- [x] Tests de semilla Windows consolidados en un único módulo.
- [x] Tests de versionado y empaquetado incorporados.

## 7. Calidad

Validación final confirmada para `874eba3`:

- Ruff: limpio.
- Pyright: 0 errores, 0 advertencias, 0 informaciones.
- Pytest: 582 passed, 10 deselected.
- Quality CI: `success`.

La validación local y CI quedó cerrada antes de la publicación.

## 8. Limpieza profunda del repositorio

- [x] Retirados 58 artefactos de inspección histórica bajo `tools/inspection/`.
- [x] Retirados scripts diagnósticos ad hoc que dependían de APIs/módulos antiguos o duplicaban verificaciones ya cubiertas por tests.
- [x] Retirado `data/catalog_db_snapshot.json`, que ya no tenía función operativa.
- [x] Retirada la envoltura `tools/audit_images.py`, redundante frente a la auditoría de almacenamiento vigente.
- [x] Consolidadas las pruebas solapadas de `CategoryExtractor` e `ImageValidator` en sus ubicaciones canónicas.
- [x] Retirados documentos de recuperación/checkpoint absorbidos por la documentación vigente.
- [x] Retirado `LICENSE` vacío; no se declara una licencia de código abierto en esta limpieza.
- [x] No se modificó el runtime de scraping ni las invariantes de persistencia/cobertura durante la limpieza.
- [x] Las fábricas y configuraciones de compatibilidad se conservaron deliberadamente.

## 9. Validación de distribución Windows

La candidata `0.2.0` fue validada en Windows sobre el instalador real y el bundle construido localmente:

- instalación limpia: ejecutable presente, versión `0.2.0`, DB persistente y 519 imágenes;
- catálogo persistente: `519` productos, `24` categorías, `523` relaciones;
- última FULL: `SUCCESS`, `24 / 523 / 519 / 4`, `coverage_complete=1`, `coverage_gap=0`, `error_count=0`;
- upgrade real `v0.1.1 → v0.2.0`: `519 / 24 / 523`, `47` runs, `54244` download changes y `519` imágenes preservados;
- desinstalación: binarios eliminados y datos persistentes conservados;
- reinstalación: `0.2.0` restaurado sin pérdida de datos;
- Sandbox sin Python: `python` y `py` no disponibles; GUI ejecutada correctamente;
- Sandbox: DB persistente creada y `519` imágenes persistentes presentes;
- smoke visual/funcional de GUI en Sandbox: correcto.

## 10. Hallazgos no bloqueantes

- Se conservan ramas históricas además de `main`; no se modifican durante esta auditoría porque el cierre funcional se gobierna exclusivamente por `main`.
- La elección de una licencia para el repositorio no se altera automáticamente como parte de esta auditoría.
- Los gates técnicos de Windows, artefactos y validación funcional están cerrados y `v0.2.0` está publicada en GitHub con el tag `v0.2.0` apuntando a `a95647f`.

## 10. Gate final de publicación

El gate de publicación de `v0.2.0` quedó satisfecho: suite verde + Ruff limpio + Pyright limpio + validación funcional + Windows Build + bundle/installer + SHA-256 + tag `v0.2.0` + release de GitHub publicada.

La infraestructura de release de `v0.1.1` se conserva sin modificar su tag ni sus artefactos. El siguiente ciclo de desarrollo parte desde `main` después de `v0.2.0`.
