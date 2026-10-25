# FCM — Checklist maestro de auditoría, limpieza y consolidación

**Fecha de corte:** 2026-10-25
**Rama predeterminada:** `main`
**Rama de integración de trabajo:** `feat/product-table-layout`
**Propósito:** recuperar una ruta clara hacia `main`, resolver PR apiladas y limpiar el repositorio sin perder funciones, historial, datos ni capacidad de recuperación.

## 1. Diagnóstico confirmado

- [x] Se verificó el estado de las ramas remotas: existen 13 referencias de rama.
- [x] `main` apunta a `47a840f5`, commit que integró la PR #19 el 2026-10-02.
- [x] `feat/product-table-layout` es descendiente directo de `main` y no está detrás. El HEAD de código/pruebas validado por Quality CI es `5ed7a406`; los commits documentales posteriores actualizan el checklist y el plan maestro.
- [x] El usuario validó localmente el código de `b611d17a`: Ruff limpio; Pyright con 0 errores, advertencias e informaciones; 57 pruebas focales aprobadas; suite completa con 983 aprobadas y 11 deseleccionadas. Posteriormente se añadieron dos pruebas de migración; Quality CI pasó en `5ed7a406` con Ruff, Pyright y Pytest en éxito.
- [x] Se confirmó que #25, #26 y #27 se integraron en `feat/product-table-layout`, no directamente en `main`.
- [x] Se comprobó que las ramas fuente de #20, #23 y #24 ya forman parte de la rama de integración; las tres PR se cerraron como supersedidas por la ruta única #30.
- [x] Se comparó el contenido exclusivo de #28/#29 con la implementación actual; se portaron a la rama activa las regresiones FB-4008 y limpieza post-prune SQLite real. Las PR se cerraron como supersedidas por #30, sin borrar sus ramas fuente.
- [x] `database/db_manager.py` administra migraciones versionadas hasta la versión 5 y registra el historial en `schema_migrations`. No existe actualmente una carpeta independiente `database/migrations/`.
- [x] La auditoría histórica de limpieza de 2026-09-27 no basta para dar por limpias las ramas actuales ni las nuevas herramientas y cambios posteriores.

### Estado de PR al 2026-10-25

| PR | Estado | Tratamiento |
|---|---|---|
| [#30 — Integración consolidada](https://github.com/impomerchperu/FacundoCatalogManager/pull/30) | Única PR abierta; borrador; base `main`, head `feat/product-table-layout` | Ruta única de promoción; no fusionar hasta resolver los bloqueos de cobertura, workers, revisión neta y checks. |
| #20, #23, #24 | Cerradas como supersedidas | Sus ramas fuente están incorporadas como ancestros de la rama de integración; no integrar por rutas paralelas. |
| #28, #29 | Cerradas como supersedidas | Su funcionalidad tiene equivalentes más recientes en la rama de integración; se portaron las dos regresiones faltantes. Mantener los refs por ahora para comparación final. |

La PR #30 contiene un diff neto de 132 archivos respecto a `main`. GitHub reporta que la rama es mergeable y el estado del diff está limpio, pero la PR sigue en borrador por los gates funcionales pendientes. Las referencias de ramas fuente cerradas no han sido borradas.

**Causa de la acumulación:** el trabajo reciente se desarrolló y se fusionó en la rama de integración en lugar de promoverse a la rama predeterminada. Además, varias PR permanecieron abiertas y sus ramas fuente no se retiraron. Las ramas creadas a partir de bases antiguas pueden aparecer divergentes por *squash* o integración de commits; el conteo de commits, por sí solo, no demuestra que falten cambios ni que sea seguro borrar una rama.

## 2. Fase A — Proteger la recuperación

- [ ] Mantener `archive/recovery-catalog-202609` intacta mientras no se haya documentado qué recuperación permite y se hayan contrastado sus commits únicos.
- [ ] Conservar las ramas fuente de las PR abiertas hasta resolver sus dependencias.
- [ ] Registrar HEAD, base común, archivos modificados y propósito de toda rama antes de retirarla.
- [ ] No usar `reset --hard`, force-push, borrado de datos, ni limpieza física de imágenes como método de ordenamiento.
- [ ] Guardar fuera del repositorio los informes generados, backups y datos locales; no versionar bases de datos de producción ni resultados efímeros.

## 3. Fase B — Restablecer una ruta de integración única

- [ ] Revisar el diff neto completo entre `main` y `feat/product-table-layout`, agrupado por GUI, scraping, persistencia, imágenes, exportadores, pruebas y herramientas.
- [ ] Confirmar que las funciones de `main` están preservadas; la relación de commits permite una promoción lineal, pero debe revisarse el contenido y la calidad antes de promover.
- [ ] Elegir una sola promoción controlada a `main` —PR de integración o fast-forward aprobado— sin forzar referencias.
- [ ] Coordinar #20, #23 y #24 como trabajo ya incluido en la rama candidata; evitar integrar el mismo cambio por caminos diferentes.
- [ ] Ejecutar Ruff, Pyright, suite completa y checks disponibles sobre el HEAD exacto que se promoverá.
- [ ] Después de promover, repetir la validación sobre `main` y confirmar que las PR redundantes quedan cerradas o que tienen una razón explícita para permanecer abiertas.
- [ ] No considerar el proyecto integrado solo porque la rama de trabajo esté verde: la prueba local no valida automáticamente el HEAD de `main`.

## 4. Fase C — Cierre técnico de #28 y #29

- [x] Comparar las modificaciones de #28 y #29 contra el HEAD actual en lugar de aplicar commits antiguos de forma mecánica.
- [x] Confirmar que la auditoría activa de imágenes informa errores de referencias JSON inválidas y audita archivos de extensiones desconocidas en el almacén del catálogo.
- [x] Confirmar que la política activa de Detalle distingue campos técnicos, texto comercial y señales de truncamiento.
- [x] Portar una regresión para recuperar el Detalle completo de FB-4008 sin incluir Color como campo técnico.
- [x] Portar una prueba de integración que comprueba con SQLite real que el producto se elimina antes de limpiar sus imágenes primaria y de galería.
- [x] Ejecutar en el HEAD `b611d17a`: Ruff limpio, Pyright sin errores, 57 pruebas focales y suite completa con 983 aprobadas/11 deseleccionadas.
- [x] Comparar la implementación visual de #29: el detector y las pruebas de variantes escaladas ya existen en la rama de integración; esta conserva además las referencias de galería existentes ante una actualización incompleta.
- [ ] Reabrir cualquiera de las PR solo si una revisión posterior identifica una diferencia funcional concreta que no esté cubierta en `feat/product-table-layout`.
- [ ] No modificar el catálogo real ni retirar imágenes canónicas en esta fase; las auditorías reales permanecen no destructivas.
## 5. Fase D — Retirar ramas sin perder trabajo

### Conservar por ahora

- [ ] `main`: rama predeterminada y destino de promoción.
- [ ] `feat/product-table-layout`: mantener hasta completar la promoción y la validación posterior.
- [ ] `archive/recovery-catalog-202609`: conservar como recuperación histórica, sin fusionarla automáticamente.
- [x] PR #28 y #29 cerradas como supersedidas por #30 tras comparar código y pruebas. Mantener los refs remotos hasta completar la promoción a `main` y una última comparación; cerrar las PR no elimina esas ramas.

### Candidatas a retirar después de resolver PR y comparar contenido

- [ ] `feature/current-exporters`: #19 ya se integró en `main`; verificar y retirar la referencia antigua.
- [x] `fix/excel-table-repair`: PR #20 cerrada como supersedida; mantener el ref hasta la promoción a `main` y la limpieza final.
- [x] `feat/image-review-queue` y `feat/image-gallery-robustness`: PR #23/#24 cerradas como supersedidas; sus HEAD ya están incorporados. Mantener refs hasta la limpieza final posterior a la promoción.
- [ ] `fix/detail-alignment-general-rules`: comprobar que no tenga trabajo exclusivo antes de retirarla.
- [ ] `fix/image-sync-consistency`, `test/gallery-duplicate-cleanup` y `fix/image-format-identification`: las PR #25–#27 están fusionadas en la rama de integración, pero hubo divergencia por historial; comparar el cambio funcional antes de retirar sus refs.
- [ ] Tras retirar refs remotas aprobadas, eliminar sus referencias locales; nunca retirar una rama por el mero hecho de estar muchos commits detrás.
- [ ] Objetivo de estructura final: `main`, una rama de trabajo activa mientras haya cambios pendientes y la rama de archivo histórico solo si conserva una recuperación necesaria. Las ramas de PR se mantienen únicamente mientras aporten cambios exclusivos.

## 6. Fase E — Auditoría de migraciones y persistencia SQLite

- [x] Identificar el punto de entrada: `DBManager.initialize_database()` ejecuta `database/schema.sql` y luego las migraciones versionadas.
- [x] Registrar que la versión actual del esquema es 5, con ledger `schema_migrations` y funciones de migración dentro de `database/db_manager.py`.
- [x] Validar por CI el avance simulado v2→v5, la idempotencia del ledger y la migración de `download_changes` legado sin perder cambios históricos.
- [x] Confirmar que los tests cubren el ledger y el rechazo de una versión de esquema posterior a la soportada.
- [ ] Revisar una por una las migraciones v1–v5 contra el esquema actual, las columnas/tablas resultantes y los datos que deben conservar.
- [ ] Probar el arranque desde una BD vacía y desde copias representativas de los estados anteriores; validar idempotencia de una segunda apertura.
- [x] Añadir pruebas para la migración v2→v5 conservando datos e idempotencia, y para restaurar `download_changes` legado con FK a historial; Quality CI pasó en `5ed7a406`.
- [ ] Probar rollback/recuperación frente a una migración fallida y la ruta de backup/restore sobre copias, sin tocar la BD real.
- [ ] Revisar específicamente la migración v1: elimina `colors` de `products` y `scraped_products` sin copia explícita a otro campo. Confirmar con fixtures de datos heredados si el contenido era redundante o debe preservarse; nunca inferir cantidades por color.
- [ ] Aclarar en documentación qué define `schema.sql` y qué cambios pertenecen a cada versión de migración.
- [ ] Decidir si separar las migraciones en un módulo o carpeta dedicada mejora de verdad la mantenibilidad. No mover funciones ni crear estructura vacía antes de tener los tests de compatibilidad.
- [ ] Mantener rechazo explícito de esquemas futuros y no cambiar números/versiones sin una migración y pruebas asociadas.

## 7. Fase F — Consolidación de código, archivos y carpetas

- [ ] Inventariar archivos Python sin referencias, wrappers redundantes, implementaciones duplicadas y rutas de importación alternativas.
- [ ] Buscar duplicidades entre `tools/`, `scripts/`, `services/`, `scrapers/` y los tests; conservar herramientas operativas reproducibles y retirar solo las obsoletas.
- [ ] Revisar pruebas semánticamente solapadas: consolidar fixtures/utilidades comunes sin eliminar casos de regresión.
- [ ] Revisar documentos de checkpoints y planes históricos: mantener una fuente maestra actual y marcar los informes antiguos como históricos en lugar de tratarlos como estado presente.
- [ ] Revisar dependencias declaradas, imports sin uso, archivos generados y reglas de `.gitignore`.
- [ ] Revisar si conviene centralizar contratos compartidos —por ejemplo, modelos de galería, esquema común de exportación y políticas de Detalle— antes de reorganizar módulos.
- [ ] Documentar cada traslado o eliminación con el reemplazo canónico y una prueba que demuestre que el comportamiento queda cubierto.
- [ ] Comparar inventarios de archivos entre `main` y la rama candidata; no asumir que los directorios idénticos en la raíz significan que el contenido interno sea equivalente.

## 8. Fase G — Catálogo, imágenes y operaciones seguras

- [ ] Ejecutar auditoría no destructiva contra la BD local vigente y conservar un informe nuevo, sin sobrescribir informes previos.
- [ ] Verificar que la auditoría de referencias de galería terminó completamente y revisar errores de JSON, referencias faltantes, hashes distintos, archivos legacy y archivos huérfanos.
- [ ] Comparar la vista previa del auditor con la del limpiador; un archivo solo es candidato a eliminación si ambas rutas confirman que no está referenciado.
- [ ] Revisar duplicados visuales y procedencia de imagen; no borrar alternativas visualmente distintas ni aplicar decisiones de revisión a productos con procedencia no coincidente.
- [ ] Ejecutar las reparaciones de Detalle primero en modo de vista previa y después por categoría, registrando backup y resultados antes de aplicar cada lote.
- [ ] Confirmar que las operaciones de limpieza física ocurren solo después de una sincronización válida y del commit de SQLite.
- [ ] Mantener intacto el catálogo real hasta que las auditorías y los resultados de vista previa sean coherentes.

## 9. Fase H — Rendimiento y cobertura de scraping

- [ ] Repetir perfiles comparables de workers por categoría; la configuración actual declara 12, pero una comparación anterior informó mejores tiempos con 8. Resolver la discrepancia con mediciones repetidas antes de cambiar el valor.
- [ ] Mantener detalle, HTTP, JSF y sincronización de imágenes en los valores validados hasta que una prueba controlada aporte evidencia para modificarlos.
- [ ] Reconciliar el total reciente de 522 apariciones por categoría con la referencia operativa histórica de 523 apariciones, 519 productos únicos y 4 productos multi-categoría.
- [ ] Identificar los códigos/categorías concretos que explican cualquier diferencia; no relajar cobertura ni cambiar el total esperado para hacer pasar una auditoría.
- [ ] Separar latencia de HTTP, caché de páginas, extracción, sincronización de imágenes y persistencia SQLite para no atribuir la demora a una única etapa sin evidencia.
- [ ] Repetir FULL real solo cuando cambien scraping, cobertura, persistencia o concurrencia; no es necesario repetirlo por cambios documentales o GUI aislados.

## 10. Fase I — Calidad y criterios de cierre

- [x] Ruff: limpio en el HEAD validado por el usuario.
- [x] Pyright: 0 errores, advertencias e informaciones en el HEAD validado por el usuario.
- [x] Suite completa del HEAD `b611d17a`: 983 aprobadas, 11 deseleccionadas; pruebas focales de sincronización/limpieza: 57 aprobadas.
- [x] Volver a ejecutar las comprobaciones focales después de portar las regresiones de #28; el HEAD `b611d17a` pasó las comprobaciones locales reportadas.
- [x] Quality CI pasó para el HEAD de código/pruebas `5ed7a406`: Ruff, Pyright y Pytest en éxito; el job `live-catalog` fue omitido intencionalmente en la PR. Los cambios documentales posteriores no modificaron ese código.
- [ ] Verificar CI/Actions para el commit exacto de promoción; el estado local verde no sustituye la comprobación del commit de destino.
- [ ] Hacer smoke test de GUI: tabla, categorías, búsqueda, CRUD, stock/color, galería, cola de revisión, historial y actualización.
- [ ] Verificar generación y apertura real de XLSX, CSV y PDF; Excel debe abrir sin reparación y conservar el contrato acordado.
- [ ] Cuando la integración esté aprobada, ejecutar los gates del release Windows: build, bundle/instalador, actualización, desinstalación y backup/restore.
- [ ] Actualizar README, plan maestro, checkpoint de release y notas de versión solo con el estado efectivamente verificado.

## 11. Criterio final de limpieza

La auditoría se cierra cuando:

1. `main` apunta al conjunto funcional validado y la promoción está documentada.
2. Las PR abiertas están fusionadas, cerradas como redundantes o mantienen una razón explícita y cambios exclusivos.
3. Las ramas retiradas tienen su contenido verificado en una rama conservada; el archivo de recuperación permanece protegido.
4. Las migraciones v1–v5 están probadas contra copias de bases representativas y hay backup/restore verificado.
5. La auditoría actual de imágenes termina sin errores de referencias y la vista previa de limpieza coincide; no quedan borrados físicos por investigar.
6. Las discrepancias de cobertura y rendimiento tienen evidencia concreta y no se han ocultado cambiando criterios.
7. Los directorios, módulos, herramientas, pruebas y documentos tienen una ubicación canónica documentada.
8. Ruff, Pyright, suite, smoke GUI y checks del commit de promoción pasan.

**Regla de seguridad:** preservar primero, comparar contenido segundo, validar sustitución tercero y borrar al final. La limpieza no consiste en reducir artificialmente el número de ramas ni en mover archivos sin pruebas.
