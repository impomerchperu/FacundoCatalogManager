# FCM — Checklist maestro de auditoría, limpieza y consolidación

**Fecha de actualización:** 2026-10-26
**Rama predeterminada y canónica:** `main`
**Integración consolidada:** PR #30, squash merge `085d6a50a7730e0546775d75ff2d105997edb619`
**Rama de integración temporal:** `feat/product-table-layout` (el árbol es idéntico a `main`; queda pendiente eliminar la referencia tras sincronizar la copia local).
**Propósito:** conservar una sola ruta estable en `main`, retirar ramas ya sustituidas sin perder historial útil ni capacidad de recuperación.

## Estado posterior a la promoción — 2026-10-26

- [x] PR #30 fue fusionada mediante squash en `main`: `085d6a50a7730e0546775d75ff2d105997edb619`.
- [x] El árbol del commit de `main` coincide exactamente con el árbol de la candidata validada `feat/product-table-layout` (`409604fb50f4b522ed56316d843ed31749f18be2)); no se perdió código funcional en el squash.
- [x] Quality CI #3885 en el HEAD de `main`: Ruff y Pyright correctos; Pytest `1032 passed, 11 deselected`.
- [x] El auditor live de FB-4047 reconoce la recuperación segura: categoría resuelta por código, recurso histórico descargado y SHA-256 exacto. `recovery_asset_verified=true`, `current_gallery_verified=false`; la galería actual no se presenta como verificada cuando el endpoint entrega la plantilla de acceso. La prueba live no escribió en SQLite.
- [x] PR #20, #23, #24, #28 y #29 permanecen cerradas como sustituidas; no hay que reabrirlas ni fusionarlas por separado. #25–#27 se integraron antes en la candidata y ya están incluidas en el árbol de `main`.
- [ ] Retirar las ramas de trabajo redundantes una vez sincronizada y validada la copia Windows. Conservar `archive/recovery-catalog-202609` mientras siga pendiente la auditoría de recuperación histórica.
- [ ] Ejecutar en Windows el smoke test de GUI/exportadores y una actualización focalizada de galería de FB-4047; auditar las referencias persistidas y el hash después de la sincronización. No se ha ejecutado una sincronización FULL ni se ha modificado la base de datos local.

> Este estado posterior a la promoción es la referencia actual. Las secciones del checklist fechadas el 25/10 son el plan previo a la fusión y se conservan como historial de decisiones; no deben interpretarse como indicación de que la PR #30 siga abierta.



## 1. Diagnóstico confirmado

- [x] Se verificó el estado de las ramas remotas: existen 13 referencias de rama.
- [x] `main` apunta a `47a840f5`, commit que integró la PR #19 el 2026-10-02.
- [x] `feat/product-table-layout` es descendiente directo de `main` y no está detrás. El HEAD de código/pruebas validado por Quality CI es `19513cda`; los commits documentales posteriores actualizan el checklist y el plan maestro.
- [x] El usuario validó localmente el HEAD `710048b5`: Ruff limpio; Pyright con 0 errores, advertencias e informaciones; 68 pruebas focales aprobadas; suite completa con 986 aprobadas y 11 deseleccionadas. Quality CI también pasó en el HEAD de código/pruebas `19513cda` tras añadir tres regresiones de migración.
- [x] Se confirmó que #25, #26 y #27 se integraron en `feat/product-table-layout`, no directamente en `main`.
- [x] Se comprobó que las ramas fuente de #20, #23 y #24 ya forman parte de la rama de integración; las tres PR se cerraron como supersedidas por la ruta única #30.
- [x] Se comparó el contenido exclusivo de #28/#29 con la implementación actual; se portaron a la rama activa las regresiones FB-4008 y limpieza post-prune SQLite real. Las PR se cerraron como supersedidas por #30, sin borrar sus ramas fuente.
- [x] `database/db_manager.py` administra migraciones versionadas hasta la versión 6 y registra el historial en `schema_migrations`. No existe actualmente una carpeta independiente `database/migrations/`.
- [x] La auditoría histórica de limpieza de 2026-09-27 no basta para dar por limpias las ramas actuales ni las nuevas herramientas y cambios posteriores.

### Estado de PR al 2026-10-25 (histórico, previo a promoción)

| PR | Estado | Tratamiento |
|---|---|---|
| [#30 — Integración consolidada](https://github.com/impomerchperu/FacundoCatalogManager/pull/30) | Única PR abierta; borrador; base `main`, head `feat/product-table-layout` | Ruta única de promoción; baseline vigente `522/518/4/24` y comparación de snapshots verificados; benchmark controlado cerrado con decisión de mantener 12 workers; no fusionar hasta completar revisión neta, galería de `FB-4047` y gates de integración. |
| #20, #23, #24 | Cerradas como supersedidas | Sus ramas fuente están incorporadas como ancestros de la rama de integración; no integrar por rutas paralelas. |
| #28, #29 | Cerradas como supersedidas | Su funcionalidad tiene equivalentes más recientes en la rama de integración; se portaron las dos regresiones faltantes. Mantener los refs por ahora para comparación final. |

La PR #30 contiene un diff neto reportado actualmente en 145 archivos respecto a `main`. GitHub reporta que la rama es mergeable y el estado del diff está limpio; la PR sigue en borrador hasta completar los gates restantes. La cobertura del catálogo `522/518/4/24` está validada y las cifras `523/519` pertenecen al snapshot antiguo de AppData, no constituyen un diferencial pendiente que deba resolverse fusionando bases. El benchmark controlado de workers ya está cerrado; siguen pendientes la revisión completa del diff neto, la inspección visual del archivo exacto de `FB-4047` y los checks de GUI/integración correspondientes. Las referencias de ramas fuente cerradas no han sido borradas.

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
- [x] Ejecutar en el HEAD `710048b5`: Ruff limpio, Pyright sin errores, 68 pruebas focales y suite completa con 986 aprobadas/11 deseleccionadas.
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
- [x] Registrar que la versión actual del esquema es 6, con ledger `schema_migrations` y funciones de migración dentro de `database/db_manager.py`.
- [x] Validar por CI el avance simulado v2→v6, la idempotencia del ledger y la migración de `download_changes` legado sin perder cambios históricos.
- [x] Confirmar que los tests cubren el ledger y el rechazo de una versión de esquema posterior a la soportada.
- [ ] Revisar una por una las migraciones v1–v6 contra el esquema actual, las columnas/tablas resultantes y los datos que deben conservar.
- [ ] Probar el arranque desde una BD vacía y desde copias representativas de los estados anteriores; validar idempotencia de una segunda apertura.
- [x] Añadir pruebas para la migración v2→v6 conservando datos e idempotencia, restaurar `download_changes` legado con FK a historial y conservar nombres de colores heredados; Quality CI pasó en `19513cda`.
- [ ] Probar rollback/recuperación frente a una migración fallida y la ruta de backup/restore sobre copias, sin tocar la BD real.
- [x] La migración v1 y v6 ahora copian el contenido original de `colors` a `legacy_colors` antes de quitar la columna antigua, cuando los valores todavía existen; la regresión valida ambas tablas y confirma que no se infiere stock.
- [x] Auditar en modo solo lectura los archivos `catalog*` localizados en las carpetas del proyecto y `%LOCALAPPDATA%`: todos dieron `integrity=ok`, y ninguno conserva las columnas `colors` o `legacy_colors`.
- [ ] El catálogo del proyecto está en esquema 5 con 518 productos; `%LOCALAPPDATA%\FacundoCatalogManager\database\catalog.db` está en esquema 2 con 519. Comparar los códigos de producto y `color_stock` de ambas bases antes de promover o actualizar datos.
- [ ] No se encontró, entre los archivos localizados, una copia con la columna `colors`. Si es necesario recuperar esos nombres, ampliar la búsqueda a cualquier respaldo externo a las carpetas revisadas antes de concluir que no existe una copia recuperable.
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
- [x] Suite completa del HEAD `710048b5`: 986 aprobadas, 11 deseleccionadas; pruebas focales de base de datos, sincronización y limpieza: 68 aprobadas.
- [x] Volver a ejecutar las comprobaciones focales después de portar las regresiones de #28; el HEAD `710048b5` pasó las comprobaciones locales reportadas.
- [x] Quality CI pasó para el HEAD de código/pruebas `19513cda`: Ruff, Pyright y Pytest en éxito; el job `live-catalog` fue omitido intencionalmente en la PR. Los cambios documentales posteriores no modificaron ese código.
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


## 12. Flujo de trabajo permanente: repositorio único y ramas mínimas

Estas reglas son operativas y prevalecen sobre instrucciones anteriores que pidieran descargar archivos generados manualmente.

### Cambios y archivos

- No pedir al usuario que descargue a mano scripts, documentos o código que pueda incorporarse al repositorio. Editar los archivos directamente en GitHub sobre la rama apropiada, ejecutar los checks disponibles y entregar comandos PowerShell para sincronizar y validar el mismo checkout local.
- El proyecto local canónico es `C:\\Proyectos\\FacundoCatalogManager`. No crear ni mantener una segunda carpeta de proyecto como método de trabajo.
- Versionar herramientas reutilizables de auditoría en `tools/`; no versionar bases de datos reales, backups locales ni informes efímeros. El inventario inicial queda disponible como `tools/audit_cleanup_migration_inventory.py`, que abre SQLite en modo solo lectura y genera el JSON bajo `%TEMP%`.
- La auditoría no autoriza eliminaciones: primero comparar códigos y relaciones, identificar cuál base utiliza realmente la aplicación, verificar backups recuperables, migrar/consolidar y comprobar el resultado; después poner candidatos en cuarentena y borrar únicamente con evidencia.

### Modelo de ramas

- `main` es la única rama estable y la fuente canónica una vez promovida y validada la integración.
- La PR #30 ya está fusionada y `main` es la fuente canónica. No volver a utilizar `feat/product-table-layout` como rama de integración; para trabajo nuevo independiente, crear una rama de alcance acotado desde el HEAD actual de `main` y retirarla después de fusionar y validar.
- Crear una rama de desarrollo/validación únicamente si existe trabajo independiente que realmente se desarrollará en paralelo y que no está ya contenido en la PR #30. Cada rama activa debe tener propósito, alcance, validaciones y ruta de vuelta a `main` explícitos.
- Mantener `archive/recovery-catalog-202609` protegida hasta confirmar qué recuperación aporta y cerrar la reconciliación de datos.
- No borrar ramas históricas por su antigüedad, número de commits o apariencia de divergencia. Después de promover y validar `main`, comparar su contenido exclusivo; retirar únicamente ramas cuya funcionalidad esté demostrablemente integrada y que no tengan valor de recuperación.
- Las PR #20, #23, #24, #28 y #29 ya constan como supersedidas por la ruta única #30; no volver a integrar su contenido en rutas paralelas.

### Sincronización local de la rama de integración

El asistente debe entregar comandos de sincronización que fallen explícitamente ante errores de red/Git, rama incorrecta, cambios locales sin guardar o validaciones fallidas. Usar `git pull --ff-only`; no usar `reset --hard`, force-push ni limpiar el árbol automáticamente.

Plantilla de sincronización y validación local:

```powershell
$ErrorActionPreference = "Stop"
Set-Location "C:\\Proyectos\\FacundoCatalogManager"
$targetBranch = "feat/product-table-layout"

$currentBranch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "Falló git branch." }
if ($currentBranch -ne $targetBranch) {
    throw "Rama actual '$currentBranch'; se esperaba '$targetBranch'. No se cambió de rama automáticamente."
}

$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Falló git status." }
if ($dirty.Count -gt 0) {
    $dirty
    throw "Hay cambios locales sin guardar. No se sincronizó para evitar perderlos."
}

git fetch origin
if ($LASTEXITCODE -ne 0) { throw "Falló git fetch origin." }

git pull --ff-only origin $targetBranch
if ($LASTEXITCODE -ne 0) { throw "Falló git pull --ff-only." }

git diff --check "origin/main...HEAD"
if ($LASTEXITCODE -ne 0) { throw "Falló git diff --check respecto a main." }

python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Falló Ruff." }

python -m pyright
if ($LASTEXITCODE -ne 0) { throw "Falló Pyright." }

python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Falló la suite completa." }

git status --short
if ($LASTEXITCODE -ne 0) { throw "Falló la comprobación final del estado Git." }
```

El paso a `main` solo ocurre después de cerrar los gates funcionales documentados en esta checklist, aprobar la PR de integración y validar el HEAD resultante de `main`.

## Actualización de ejecución — 2026-10-25

### Validaciones locales registradas
- [x] Sincronización fast-forward de feat/product-table-layout hasta 0e931ec7.
- [x] git diff --check origin/main...HEAD.
- [x] python -m ruff check .
- [x] python -m pyright: 0 errores, 0 advertencias, 0 informaciones.
- [x] python -m pytest -q: 986 aprobadas, 11 omitidas, 19,19 s.
- Nota: estas validaciones ocurrieron antes de añadir tools/audit_catalog_consolidation.py y su nueva prueba; volver a ejecutar validaciones después de sincronizar esos cambios.

### Inventario local de solo lectura
- [x] Inventario ejecutado; no modificó bases de datos ni archivos.
- [x] Informe creado en %TEMP%\fcm_cleanup_migration_inventory_20261025_164817.json en el equipo local.
- [x] El inventario encontró 51 candidatos de base de datos entre el proyecto y LOCALAPPDATA.
- [x] Todos los candidatos mostrados informaron integridad SQLite ok.
- [x] Árbol del proyecto: 1.587 archivos / 1.269,784 MiB; database/: 149 archivos / 1.139,266 MiB; data/: 1.056 archivos / 125,945 MiB.
- [x] Árbol de %LOCALAPPDATA%\FacundoCatalogManager: 612 archivos / 100,737 MiB.

### Diferencias que requieren conciliación
| Métrica | Proyecto | %LOCALAPPDATA% |
|---|---:|---:|
| Productos | 518 | 519 |
| Categorías | 24 | 24 |
| Relaciones producto-categoría | 545 | 523 |
| Apariciones históricas de productos | 39.954 | 20.597 |
| Historial de scraping | 218 | 170 |
| source_page_cache | 518 | No está presente |
| Versión de esquema registrada | 6 | 2 |

- config.runtime_paths usa PROJECT_ROOT/database/catalog.db en modo desarrollo y %LOCALAPPDATA%\FacundoCatalogManager\database\catalog.db en modo congelado/instalado. Son ubicaciones de datos distintas según el modo de ejecución, no dos copias del código fuente. Antes de unificarlas hay que decidir expresamente la política deseada para desarrollo frente a instalación.
- [ ] Ejecutar tools/audit_catalog_consolidation.py para comparar códigos de producto, campos compartidos, stock por color, imágenes y relaciones de categoría entre las dos bases principales.
- [ ] Revisar las diferencias de producto y categoría y decidir la política de migración sin sobrescribir automáticamente ninguna base.
- [ ] Clasificar las 51 bases candidatas por contenido lógico y uso. Los conteos e integridad correctos no demuestran por sí solos que un respaldo se pueda borrar.
- [ ] Identificar el producto adicional de %LOCALAPPDATA% y las diferencias en relaciones antes de la consolidación.
- [ ] Solo después de identificar la base canónica y probar recuperación, poner residuos en cuarentena y eliminar únicamente lo demostrado como redundante.

### Regla de seguridad
No se ha eliminado, sobrescrito ni migrado ninguna base, imagen, archivo o rama. El próximo cambio de datos requiere un plan de migración explícito, copia de seguridad recuperable, comparación previa y auditoría posterior.

## Actualizacion de comparacion de catalogos — 2026-10-25

### Resultado confirmado
- [x] La validacion anterior de la rama paso: Ruff correcto, Pyright 0 errores y suite 989 passed, 11 deselected.
- [x] La auditoria comparativa se ejecuto con ambas bases en modo SQLite de solo lectura; integridad ok en ambas.
- [x] No se modifico ninguna base, imagen o archivo de origen durante la comparacion.
- [x] Catalogo del proyecto: esquema 6, 518 productos, 545 relaciones producto-categoria.
- [x] Catalogo de LOCALAPPDATA: esquema 2, 519 productos, 523 relaciones producto-categoria.
- [x] Codigos compartidos: 514.
- [x] Exclusivos del proyecto: FB-3024, FB-4047, FB-4048, TPSTCB.
- [x] Exclusivos de LOCALAPPDATA: FB-2111, FB-4042, FB-4043, ST-210, TPSTCB-01.
- [x] Codigos con relaciones de categoria distintas: 10.

### Conteo de campos distintos en productos compartidos
| Campo | Productos distintos |
|---|---:|
| image_path | 514 |
| content_hash | 496 |
| description | 487 |
| color_stock | 272 |
| stock | 272 |
| image_hash | 25 |
| image_url | 8 |
| price, price_hundred, price_sample, price_thousand | 7 en cada campo |
| name | 4 |

Estos conteos significan que el valor almacenado difiere entre bases; no significan automaticamente que el proyecto sea correcto en cada campo. En particular, no asumir que image_path indica imagen incorrecta: pueden diferir rutas relativas y absolutas. La discrepancia de stock/color_stock requiere inspeccionar valores y contrastarlos con la fuente del catalogo.

### Proxima tarea publicada
- [x] tools/audit_catalog_consolidation.py genera muestras de diferencias por campo y por relacion de categoria en consola, ademas de guardarlas en JSON.
- [ ] Sincronizar el commit que añade las muestras en consola; volver a ejecutar Ruff, Pyright, pruebas especificas y suite completa.
- [ ] Inspeccionar las muestras y clasificar discrepancias en diferencias de formato, datos historicos validos y errores reales.
- [ ] Redactar el plan de migracion antes de modificar la base instalada o consolidar los datos.
- [ ] No borrar aun ninguna de las 51 bases candidatas. Primero comprobar referencias, recuperabilidad y contenido exclusivo.

### Politica provisional de fuente canonica
database/catalog.db del proyecto es la referencia tecnica provisional por su esquema mas reciente e historial de scraping mas completo. La base de LOCALAPPDATA tiene cinco codigos exclusivos y un producto neto adicional, por lo que debe seguir preservandose hasta resolver las diferencias. La consolidacion debe importar selectivamente los datos validos; no consiste en copiar una base completa sobre la otra.

## Siguiente iteracion de conciliacion — 2026-10-25

La comparacion validada localmente reporto 989 pruebas aprobadas y 11 omitidas, antes de los cambios de diagnostico añadidos en esta iteracion.

Hallazgos para resolver antes de migrar:
- Stock y color_stock difieren para 272 productos compartidos. No sumar cantidades ni escoger maximos; comparar frescura de los datos y validar contra una fuente confiable.
- Las diferencias brutas de descripcion incluyen saltos de linea y espacios, pero hay ejemplos con contenido tecnico real distinto (por ejemplo, 861-A4 pierde la etiqueta Color: Blanco en el proyecto respecto de LOCALAPPDATA).
- Varios image_url de LOCALAPPDATA apuntan a placeholders aunque el proyecto tiene URLs especificas; verificar los archivos persistidos antes de promover imagenes.
- FB-1908 tiene 23 relaciones de categoria en el proyecto y ninguna en LOCALAPPDATA. Tratar como anomalia prioritaria y revisar el historial/origen de esas relaciones antes de modificarlo.
- TPSTCB y TPSTCB-01 son codigos distintos en las bases; revisar nombre, detalle, precios e imagen antes de decidir si representan productos diferentes o un cambio de codigo.

Cambios diagnosticos en la rama pendientes de validar localmente:
- La auditoria comparativa incluye las ultimas marcas temporales de scraping_runs y scraping_history.
- Incluye los datos esenciales de los productos exclusivos de cada base para identificar si deben importarse, actualizarse o investigarse.
- Separa las diferencias de descripcion que se explican solo por espacios/saltos de linea de las diferencias de contenido despues de normalizar espacios.
- Se añadieron pruebas para la normalizacion del texto y frescura de las fuentes; volver a ejecutar Ruff, Pyright, las pruebas especificas y la suite completa.

Criterio de cierre de esta fase: no migrar ni borrar hasta que los codigos exclusivos, las relaciones anomalas, las descripciones tecnicas y las diferencias de stock tengan una decision documentada. A continuacion, generar un plan transaccional de migracion con copia recuperable y pruebas de igualdad post-migracion.

## Politica de autoridad temporal y codigos posiblemente renovados — 2026-10-25

### Regla confirmada para la conciliacion
- [x] Priorizar la captura completa mas reciente para representar el estado actual del catalogo: PROJECT tiene scraping aplicado hasta 2026-10-24; LOCALAPPDATA se queda en 2026-09-26.
- [x] Para el stock actual, usar el valor de la captura reciente del proyecto, no el mayor valor ni una suma entre bases. La reduccion es coherente con una captura mas nueva; no combinar snapshots de fechas distintas.
- [x] Para campos que recibieron los ajustes de calidad buscados, preservar la version reciente del proyecto como principal. Usar los datos antiguos como referencia de recuperacion, no para revertir automaticamente esos ajustes.
- [x] Mantener excepciones explicitas para anomalias verificadas en la base reciente: por ejemplo, FB-1908 con relaciones de categoria anormalmente extensas y productos con URLs/galerias de imagen que parecen ajenas. La fecha mas reciente no valida automaticamente una relacion o imagen evidentemente inconsistente.

### Codigos exclusivos: no asumir que son productos nuevos
La auditoria encontro coincidencias de nombre e image_hash entre codigos exclusivos de ambos snapshots:
- FB-4047 (reciente) y FB-4042 (antiguo): Foco Antiestres; misma imagen; stock 212 frente a 414.
- FB-4048 (reciente) y FB-4043 (antiguo): Pelota Mundo Mano Antiestres; misma imagen y stock 487.
- TPSTCB (reciente) y TPSTCB-01 (antiguo): Taza Enamel 12 oz; misma imagen, stock y color_stock.
- FB-3024 (reciente) y ST-210 (antiguo): Maquina Doble Estacion Freesub; misma imagen, pero la descripcion indica especificaciones diferentes (560 W frente a 280 W). Requiere comprobacion de origen antes de decidir si es una renovacion de codigo o una asociacion incorrecta.

Estas coincidencias son candidatos de codigo renovado, no una autorizacion para combinar ni borrar registros. La base antigua debe mantenerse intacta hasta resolverlos. FB-2111 solo aparece en LOCALAPPDATA; no se debe reimportar sin confirmar que sigue vigente en la fuente actual.

### Diagnostico adicional publicado
- [x] La auditoria informa las marcas temporales de scraping para valorar la frescura.
- [x] La auditoria clasifica diferencias de descripcion explicables por espacios/saltos de linea frente a diferencias de contenido tras normalizar espacios.
- [x] La auditoria informa productos exclusivos con sus campos esenciales y detecta candidatos de codigo renovado mediante nombre normalizado + SHA-256 exacto de imagen.
- [ ] Validar los cambios diagnosticos con Ruff, Pyright y suite completa.
- [ ] Inspeccionar los candidatos y sus valores con la captura actual, incluida la cache HTML cuando corresponda.
- [ ] Preparar migracion selectiva desde el snapshot reciente a una ubicacion de datos canonica, conservando una copia recuperable antes de cambios.
- [ ] Clasificar y limpiar los 51 archivos de base de datos solo despues de comparar contenido, referencias y capacidad de restauracion.

La politica de migracion es: snapshot reciente del proyecto como autoridad para valores actuales de catalogo; datos antiguos solo como recuperacion o para completar elementos cuya vigencia sea confirmada independientemente. Nunca sumar stock entre snapshots ni reemplazar campos recientes solo porque la base antigua contenga un valor distinto.


## Validacion de conciliacion y evidencia de fuente — 2026-10-25

### Validacion local del HEAD sincronizado

- [x] El usuario sincronizo por fast-forward `feat/product-table-layout` de `c91b843f` a `50558ab1`; `git diff --check origin/main...HEAD` paso.
- [x] Ruff: `All checks passed!`.
- [x] Pyright: 0 errores, 0 advertencias, 0 informaciones.
- [x] Pruebas de `tests/tools/test_audit_catalog_consolidation.py`: 4 aprobadas.
- [x] Suite completa: 990 aprobadas, 11 deseleccionadas.
- [x] `tools/audit_catalog_consolidation.py` termino con ambas bases abiertas en modo solo lectura. No modifico bases, imagenes ni archivos de origen.
- [x] La base del proyecto reporta esquema 6, 518 productos y 545 relaciones; LOCALAPPDATA reporta esquema 2, 519 productos y 523 relaciones. La captura aplicada mas reciente del proyecto es 2026-10-24; la de LOCALAPPDATA es 2026-09-26.
- [x] La nueva salida identifica cuatro pares candidatos a cambio de codigo usando nombre normalizado y hash SHA-256 exacto. La regla sigue siendo de deteccion para revision, nunca de merge automatico.

### Evidencia contrastada con las fichas oficiales

- [x] [Maquina Doble Estacion Freesub — ficha oficial](https://stock.importacionesfacundo.com/producto/maquina-doble-estacion-freesub/) muestra SKU `FB-3024` y detalle total de 560 W; en la descripcion funcional explica dos estaciones de 280 W cada una. Esto reconcilia el valor antiguo de 280 W por estacion con el total de 560 W, aunque no autoriza combinar automaticamente `FB-3024` con `ST-210`.
- [x] [Taza Enamel 12 oz — ficha oficial](https://stock.importacionesfacundo.com/producto/taza-enamel-12-oz/) muestra SKU `TPSTCB`, y sus medidas, capacidad, medida de impresion y material coinciden con la ficha reciente del proyecto. Esto respalda `TPSTCB` como codigo actual frente al candidato antiguo `TPSTCB-01`; preservar el registro historico hasta completar la conciliacion.
- [x] Los resultados publicos de [Nuevos Productos](https://stock.importacionesfacundo.com/categoria-producto/nuevos-productos/) y [Articulos de Oficina](https://stock.importacionesfacundo.com/categoria-producto/articulos-de-oficina/) muestran `FB-1908` como Tarjeta de PVC CR80. El catalogo del proyecto actualmente asocia este codigo a 23 categorias, lo que permanece como anomalia prioritaria y no debe aceptarse ni repararse por conjetura.
- [ ] Comprobar en la cache HTML local del producto `FB-1908` que categorias declara la pagina del producto y contrastarlas con `product_categories`; no inferir que las dos listas publicas localizadas constituyen necesariamente el conjunto completo.
- [ ] Auditar las imagenes alternativas de `FB-4047`: la galeria guardada incluye `FOCO-AMARILLO.webp` y `MEZCLADOR-CAMION-copia.webp`. La segunda parece ajena al producto y debe verificarse visualmente/procedencia antes de reparar; no borrar archivos de imagen en esta fase.
- [ ] Revisar los candidatos restantes `FB-4047` ↔ `FB-4042` y `FB-4048` ↔ `FB-4043` por codigo vigente y galeria. La coincidencia de nombre e imagen identifica una posible renovacion, no basta por si sola para fusionar registros.

### Regla para discrepancias con paginas publicas

Las fichas y resultados web pueden proceder de paginas cacheadas con fecha anterior a la ultima captura local. Los campos de identificacion y detalle se usan como evidencia auxiliar; sus cantidades de stock no reemplazan la captura aplicada del 2026-10-24 sin una observacion mas reciente y verificable. No recuperar cantidades antiguas, no sumar snapshots y no sustituir el stock reciente por un numero mayor solo porque aparezca en una pagina historica.

### Siguiente paso seguro

Generar una auditoria no destructiva de `source_page_cache` para extraer, desde el HTML almacenado en la BD del proyecto, los enlaces de categoria del producto y contrastarlos con sus relaciones normalizadas. Ejecutar despues una revision focal de las galerias de `FB-1908`, `FB-4047` y de los pares candidatos. Solo con esa evidencia decidir las correcciones; aplicar por lote transaccional y categoria con respaldo recuperable y auditoria posterior.


## Auditoria de evidencia HTML en caché — validacion de herramienta, 2026-10-25

- [x] Se incorporo `tools/audit_product_source_evidence.py` para comparar de forma no destructiva los enlaces de categoria almacenados en el HTML de producto contra las relaciones de `product_categories`.
- [x] La herramienta usa `source_page_cache` de `database/catalog.db`, descomprime los HTML guardados y busca categorias declaradas en bloques acotados de WooCommerce (`.posted_in` o bloque etiquetado `Categorías:`). Los enlaces encontrados solo en el menu global se muestran como candidatos no autoritativos y no se utilizan para concluir discrepancias.
- [x] El informe incluye fecha de captura/verificacion, estado de la caché, relaciones actuales, enlaces declarados por la ficha y galería guardada; no realiza peticiones web, no actualiza SQLite y escribe el JSON solo en `%TEMP%`.
- [x] Se añadieron cuatro pruebas de regresion para extraccion de categorias acotada, comparacion con relaciones, lectura de solo lectura y ausencia de producto/cache.
- [x] CI de GitHub Actions pasó en `a8f0d5f1`: Ruff limpio, Pyright 0 errores/advertencias/informaciones y 994 pruebas aprobadas con 11 deseleccionadas. El job `live-catalog` se omitió intencionalmente.
- [ ] Ejecutar la nueva herramienta sobre la base del proyecto en el equipo Windows y revisar el informe generado. La herramienta puede informar datos pero no los corrige.
- [ ] Priorizar el bloque `PRODUCT_SOURCE_EVIDENCE` para `FB-1908`: validar si la ficha en caché sustenta la lista actual de 23 categorias.
- [ ] Revisar el HTML cacheado y la galeria de `FB-4047`; las URLs de la galeria almacenada incluyen `FOCO-AMARILLO.webp` y `MEZCLADOR-CAMION-copia.webp`. No borrar imagenes ni modificar la galeria hasta confirmar procedencia.
- [ ] Comparar tambien `FB-3024`, `FB-4048` y `TPSTCB` con la ficha cacheada para cerrar la conciliacion de SKU/detalle; no sustituir stock mas reciente por valores de paginas posiblemente historicas.

Comando de ejecución local despues de sincronizar la rama:

```powershell
python tools/audit_product_source_evidence.py
```

Este comando abre la base de datos del proyecto en modo solo lectura. El informe JSON se guarda en `%TEMP%`; no se toca la base instalada de LOCALAPPDATA y no se modifica ni elimina ninguna imagen. Se debe compartir solo la salida `PRODUCT_SOURCE_EVIDENCE` de los códigos indicados o las secciones de relaciones discrepantes, no es necesario pegar todo el informe.


### Seguimiento a la primera ejecucion de evidencia — 2026-10-25

- [x] La ejecucion local reporto integridad SQLite `ok` para ambas bases; el proyecto conserva 518 productos/545 relaciones y LOCALAPPDATA 519 productos/523 relaciones. Los conteos de campos no cambian la politica: no fusionar snapshots ni sumar stock.
- [x] El primer informe de evidencia mostró seis registros solicitados, pero no encontro URLs asociadas en `scraped_products`; por ello no llego a comparar las paginas cacheadas. Este resultado se registro como limitacion de cobertura de la herramienta, no como prueba de que no existan paginas en caché.
- [x] La herramienta se amplio para localizar pagina de producto directamente en `source_page_cache` por SKU dentro de selectores explicitos (`p.brxe-heading`, `span.sku`, `[sku]`, `[data-sku]`, `.sku`). Si no hay SKU, solo acepta como fallback un titulo exacto que corresponda a una unica pagina cacheada; coincidencias ambiguas no se seleccionan.
- [x] La salida de galeria elimina duplicados de URL al mostrar la imagen principal y las alternativas, sin modificar `gallery_images` de la base de datos.
- [x] CI aprobado para el codigo actualizado en `71698ad8`: Ruff limpio, Pyright sin errores, 995 pruebas aprobadas y 11 deseleccionadas.
- [ ] Volver a ejecutar el auditor para obtener la comparacion contra HTML real de `FB-1908`, `FB-4047` y los otros SKU objetivo.
- [ ] Si no se encuentra una pagina por SKU ni por titulo exacto unico, consultar el informe completo en `%TEMP%` y revisar de forma puntual si existe otro identificador de producto en la cache. No inferir relaciones a partir del menu global de otra pagina.


## Resultado de evidencia del catálogo y auditoría de ocurrencias — 2026-10-25

### Resultado del auditor de páginas cacheadas

- [x] El usuario ejecutó `tools/audit_product_source_evidence.py`; ambas bases siguen con integridad `ok`, sin modificaciones.
- [x] El HTML cacheado de `FB-1908` fue encontrado con coincidencia de SKU explícito y captura del 2026-10-24. Su bloque taxonómico de ficha declara `Artículos de Oficina` y `Nuevos Productos`; la segunda categoría no forma parte de las 24 categorías maestras monitorizadas.
- [x] El producto tiene 24 relaciones `product_categories` en la base del proyecto. Esto es una anomalía que debe comprobarse, pero el bloque de taxonomía de la ficha no enumera necesariamente todas las categorías en cuyos listados aparece el SKU. La implementación `category_product_sync_service._record_category_occurrence` registra ocurrencias de listado por categoría; por ello no se deben borrar 23 relaciones solo por ausencia en la taxonomía de la ficha.
- [x] La página cacheada de `FB-4047` declara una única categoría, `Artículos Antiestrés`, que coincide con su relación actual de listado. El detalle técnico también coincide con los campos guardados.
- [x] La galería almacenada de `FB-4047` contiene la imagen principal `SFPU-38.webp`, más `FOCO-AMARILLO.webp` y `MEZCLADOR-CAMION-copia.webp`. El nombre de la segunda alternativa es sospechoso, pero el nombre de archivo por sí solo no demuestra el contenido visual ni autoriza a borrar la referencia.
- [x] La auditoría de páginas cacheadas se amplió para comparar las imágenes de la galería detectadas en el HTML localmente guardado contra las URL de galería almacenadas. La herramienta no realiza solicitudes de red, no corrige la galería y marca diferencias como candidatas a revisión.
- [x] Las páginas públicas actuales también muestran `FB-1908` en [Artículos de Oficina](https://stock.importacionesfacundo.com/categoria-producto/articulos-de-oficina/) y [Nuevos Productos](https://stock.importacionesfacundo.com/categoria-producto/nuevos-productos/). Los fragmentos de esas dos listas mostraron stocks distintos (447100 y 434200), por lo que no se toma el valor de una lista aislada como autorización para cambiar el stock aplicado del proyecto.

### Auditoría en vivo de pertenencia a categorías

- [x] Se añadió `tools/audit_category_memberships_live_readonly.py` para recolectar solo páginas de listado de las 24 categorías monitorizadas, sin solicitar páginas de detalle de producto.
- [x] El auditor compara para los SKU seleccionados las categorías donde aparecen las tarjetas live con sus relaciones actuales en `product_categories`. Comprueba los conteos esperados por categoría y las tarjetas sin código.
- [x] Si hay una discrepancia de conteos, faltan categorías o quedan tarjetas sin código, el resultado se marca `INCONCLUSIVE_INCOMPLETE_LIVE_COVERAGE`; las relaciones no son aptas para limpieza. Incluso con cobertura completa, el resultado solo es `REVIEW_ONLY_COVERAGE_VERIFIED` y no modifica la base.
- [x] CI del HEAD `8ed6814a`: Ruff limpio, Pyright 0 errores/advertencias/informaciones y 999 pruebas aprobadas con 11 deseleccionadas.
- [x] Auditor de ocurrencias ejecutado en el equipo local con cobertura completa: 24/24 categorías, 522/522 tarjetas y 0 tarjetas sin código. `FB-1908` aparece únicamente en `Artículos de Oficina` entre las categorías monitorizadas.
- [x] Revisadas las URL de galería de `FB-4047`: la fuente cacheada incluye las tres imágenes guardadas y no se encontraron diferencias de URL. La corrección visual de `MEZCLADOR-CAMION-copia.webp` sigue abierta.
- [x] Stock sin cambios. Tras validar cobertura, se corrigieron localmente solo las relaciones de `FB-1908` (23 retiradas; una relación conservada) con copia de seguridad y comprobación posterior. No se borraron ni cambiaron archivos de imagen.

Comandos después de sincronizar la rama actual (usa el bloque de PowerShell compartido al cierre de esta tarea; el objetivo debe ser el HEAD remoto más reciente, no un SHA histórico):

```powershell
python tools/audit_product_source_evidence.py
python tools/audit_category_memberships_live_readonly.py --codes FB-1908 FB-4047 FB-4048 FB-3024 TPSTCB
```

El primer comando lee la caché local. El segundo descarga únicamente las páginas de listado monitorizadas para observar las ocurrencias por categoría y lee la base en modo SQLite de solo lectura; no enriquece productos desde sus páginas de detalle y no ejecuta sincronización ni reparaciones.

## Cierre verificado de auditoría de ocurrencias — 2026-10-25

Este resultado actualiza y reemplaza las tareas pendientes de la sección de evidencia de catálogo que antecede.

- Auditoría live: `integrity=ok`, 24/24 categorías, 522/522 tarjetas, 0 tarjetas sin código.
- `FB-1908`: la relación maestra final local es únicamente `Artículos de Oficina`; la auditoría posterior no informó relaciones extra ni faltantes.
- `FB-4047`, `FB-4048`, `FB-3024` y `TPSTCB`: relaciones de DB coincidentes con sus listados reales.
- Respaldo transaccional íntegro: `%TEMP%\\fcm_catalog_before_category_repair_20261025_183001_627168.db`.
- Informe posterior: `%TEMP%\\fcm_live_category_membership_audit_20261025_183037.json`.
- Calidad de código verificada en la rama `feat/product-table-layout`, HEAD `77e026bcf893b2b4715c31a9e413d33bebf3f889`: Ruff limpio, Pyright 0 errores, Pytest 1005 passed / 11 deselected; CI verde.

Actualización posterior: el diferencial `522/523` apariciones y `518/519` productos no es un bloqueo pendiente del catálogo vigente. La captura del proyecto coincide con la auditoría live completa en `522/518/4/24`; las cifras `523/519` pertenecen a AppData, snapshot del 26/09/2026. No modificar el stock de `FB-1908` basándose en listados con existencias contradictorias. La revisión visual de la galería de `FB-4047` y los demás gates de promoción siguen abiertos.

## Baseline vigente del catálogo y cierre de comparación de snapshots — 2026-10-25

Este estado reemplaza las notas históricas del checklist que marcaban 522/523 apariciones y 518/519 productos como un diferencial global sin resolver.

- [x] Se acepta como baseline vigente **522 apariciones / 518 productos únicos / 4 productos multi-categoría / 24 categorías**.
- [x] Auditoría live de solo lectura completa: 24/24 categorías, 522/522 tarjetas esperadas, 0 tarjetas sin código e integridad `ok`.
- [x] `database/catalog.db`: esquema 6, 518 productos y 522 relaciones; última captura aplicada 2026-10-24.
- [x] `%LOCALAPPDATA%\FacundoCatalogManager\database\catalog.db`: esquema 2, 519 productos y 523 relaciones; última captura aplicada 2026-09-26. Es un snapshot antiguo, no una fuente de filas a incorporar al catálogo vigente.
- [x] Solo en proyecto: `FB-3024`, `FB-4047`, `FB-4048`, `TPSTCB`. Candidatos de código anterior en AppData: `ST-210`, `FB-4042`, `FB-4043`, `TPSTCB-01`. La coincidencia de nombre e imagen SHA-256 y la presencia de los códigos actuales en la auditoría live respalda mantener los códigos recientes; no hacer merge automático.
- [x] `FB-2111` solo aparece en AppData y no aparece entre las tarjetas de las 24 categorías auditadas. No reimportar salvo evidencia nueva de publicación.
- [x] La comparación fue de solo lectura: ninguna base, existencias, detalle o imagen fue modificada.

**Política de datos:** el snapshot del proyecto del 24/10/2026 es el catálogo objetivo actual. No mezclar snapshots, sumar cantidades, restaurar stocks antiguos ni importar automáticamente productos exclusivos de AppData. Las diferencias de detalle, stock/color_stock e imágenes deben tratarse como historial entre capturas; los cambios futuros requieren evidencia de fuente actual.

**Pendientes separados de la cobertura:** revisión completa del diff neto para PR #30 y verificación visual del archivo local `MEZCLADOR-CAMION-copia.webp` en la galería de `FB-4047`. El benchmark de workers está completado; se conserva `category_workers=12` porque la mejora aparente de 8 workers (2,04 %) quedó dentro de la variabilidad observada.


## Benchmark de workers de categoría — ejecución cerrada, 2026-10-25

- [x] Baseline de origen validado en modo de solo lectura: `integrity=ok`, esquema v6, 518 productos, 522 relaciones, 24 categorías.
- [x] Ejecutados seis ensayos balanceados `12, 8, 8, 12, 12, 8`, con copia SQLite independiente por ensayo y descarga de imágenes desactivada.
- [x] Todos los ensayos fueron válidos: 24 categorías, 522 apariciones esperadas/colectadas/enriquecidas, 130 solicitudes por corrida, cero reintentos y cero errores.
- [x] Tiempos de perfil (s): 12 workers = 62.220 / 82.435 / 81.885; 8 workers = 66.980 / 80.215 / 84.198.
- [x] Medianas: 12 workers = **81.885 s**; 8 workers = **80.215 s**. Mejora aparente con 8 workers = **2.04%** (1.670 s); medianas del total medido = 84.384 s con 12 y 82.722 s con 8 (~1.97% de mejora).
- [x] Variación observada: rango de 20.215 s con 12 workers y 17.218 s con 8. Esa dispersión es muy superior a la diferencia de medianas y los rangos se superponen.
- [x] Informe principal conservado en `%TEMP%\fcm_category_worker_benchmark_20261025_192020_19676\summary.json`.
- [x] **Decisión: mantener `category_workers=12` en producción.** La mejora aparente de 8 workers no es concluyente frente a la variabilidad observada; no modificar la configuración basándose en estas seis corridas.
- [x] Las bases SQLite temporales se eliminaron al finalizar; la DB original se utilizó en solo lectura para crear la semilla. No se aplicaron cambios de producto, stock ni imágenes.
- [ ] Revisar el diff neto de la PR #30 y validar visualmente `MEZCLADOR-CAMION-copia.webp` de `FB-4047` antes de decidir la promoción.

No se ejecutó sincronización FULL ni descarga de imágenes durante este benchmark. La PR #30 permanece abierta en borrador y sin fusionar.


## Estado actualizado de sincronización y promoción — 2026-10-25

- [x] Benchmark categoría: seis ensayos válidos; `category_workers=12` se mantiene porque la mejora aparente con 8 fue 2,04 % y menor que la variabilidad de las corridas.
- [x] CI del commit documental `19b419fd002a070c7c83cfeba36c10308b6ffade` completó con éxito (Ruff, Pyright y Pytest; `live-catalog` omitido por diseño). Los cambios documentales realizados después deben validarse de nuevo en CI.
- [ ] Sincronizar la copia local solo tras comprobar el HEAD remoto actual de la rama; verificar rama, estado de trabajo limpio y ancestry antes de `git pull --ff-only`.
- [ ] Revisar por áreas el diff neto de la PR #30 (145 archivos reportados por GitHub); no usar únicamente el conteo de commits como criterio de integridad.
- [ ] Inspeccionar el archivo local `data/images/products/FB-4047/FB-4047-03.webp` y confirmar si corresponde a un camión mezclador o al foco antiestrés. La búsqueda web por el nombre sospechoso sugiere posible contaminación, pero la imagen exacta no está versionada; no borrar ni cambiar referencias de la base sin inspección y respaldo.
- [ ] Completar los checks de GUI/release que correspondan. No fusionar la PR #30 únicamente porque CI esté verde.
