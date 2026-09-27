# FCM — Auditoría general final para v0.2.0

Fecha: 2026-09-27  
Rama oficial: `main`  
Versión en preparación: `0.2.0`  
HEAD candidato actual de `main`: `d543f12`  
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

El snapshot histórico `534 / 530 / 4` permanece como diagnóstico. El archivo `data/catalog_db_snapshot.json` también queda identificado explícitamente como snapshot histórico y no como fuente operativa.

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

Última validación local confirmada antes de la candidata:

- Ruff: limpio.
- Pyright: 0 errores, 0 advertencias, 0 informaciones.
- Pytest: 577 passed, 10 deselected.

La candidata `v0.2.0` añadió nuevas pruebas de versión y endurecimiento del empaquetado. El conteo final debe ser confirmado con una nueva ejecución local completa antes de publicar.

## 8. Hallazgos no bloqueantes

- Se conservan ramas históricas además de `main`; no se modifican durante esta auditoría porque el cierre funcional se gobierna exclusivamente por `main`.
- La elección de una licencia para el repositorio no se altera automáticamente como parte de esta auditoría.
- La release formal `v0.2.0` aún no se considera publicada hasta completar la validación Windows, artefactos, tag y release de GitHub.

## 9. Gate final de publicación

La publicación de `v0.2.0` queda condicionada a:

`suite verde + Ruff limpio + Pyright limpio + validación funcional + Windows Build + bundle/installer + SHA-256 + tag v0.2.0 + release GitHub`

La infraestructura de release de `v0.1.1` se reutiliza sin modificar su tag ni sus artefactos.
