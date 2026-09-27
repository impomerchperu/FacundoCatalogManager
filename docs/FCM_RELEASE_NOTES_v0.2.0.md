# Facundo Catalog Manager v0.2.0 — Release candidate

Estado: **en preparación**  
Versión central: `VERSION = 0.2.0`  
Release publicada anterior: `v0.1.1`  
HEAD candidato actual de `main`: `d543f12`

## Alcance

La versión `0.2.0` consolida el cierre técnico posterior a `v0.1.1` sin alterar el runtime productivo de scraping.

### GUI

- Ajustes finales del historial de descargas.
- Altura de filas con holgura vertical simétrica respecto al marco de selección.
- Nombres de producto envueltos únicamente cuando la columna PRODUCTO no dispone de ancho suficiente.
- Orden natural alfanumérico en CÓDIGO.
- Los cambios son exclusivamente visuales y de interacción.

### Observabilidad y benchmarks

- El comparador rechaza benchmarks sin cobertura válida.
- Se rechaza cobertura incompleta, `coverage_gap` distinto de cero y `coverage_complete=False`.
- Se rechazan errores de cobertura o errores HTTP terminales.
- Se rechazan métricas negativas imposibles.
- La comparación permanece descriptiva y no clasifica una configuración como ganadora o perdedora.

### Distribución Windows

- La preparación de la semilla de Windows queda cubierta con pruebas focalizadas para catálogo, FULL válido, cobertura e imágenes.
- Se elimina la duplicación de pruebas de la semilla y se conserva una única batería de responsabilidad.
- La versión de aplicación queda centralizada en `VERSION`.
- PyInstaller incorpora `VERSION` al bundle.
- La aplicación publica nombre y versión mediante los metadatos estándar de `QApplication`.
- El workflow de calidad utiliza el Pyright fijado por `requirements.txt`.
- Inno Setup ya no contiene un fallback silencioso a una versión antigua.

## Referencia funcional protegida

La referencia viva continúa siendo:

`24 categorías / 523 apariciones / 519 productos únicos / 4 multi-categoría / 523 relaciones`

con:

- `coverage_complete=1`
- `coverage_gap=0`
- 0 errores invalidantes
- runtime productivo `8 / 24 / 28`

La release `v0.1.1` sigue siendo el punto de rollback y no se modifica.

## Evidencia de calidad

Última validación local confirmada antes de estos cambios de release candidate:

- 577 tests aprobados.
- Ruff limpio.
- Pyright sin diagnósticos.

La candidata `v0.2.0` incorpora nuevas pruebas de versionado y consolida la cobertura de semilla Windows; su conteo final queda sujeto a la siguiente validación local completa.

## Cierre de la release candidate

La versión `0.2.0` no se considera publicada hasta completar:

1. suite completa verde;
2. validación funcional correspondiente;
3. Windows Build;
4. validación del bundle/instalador;
5. artefactos y SHA-256;
6. creación del tag `v0.2.0`;
7. publicación de la release de GitHub.

La infraestructura de distribución existente se reutiliza; `v0.1.1` permanece intacta.
