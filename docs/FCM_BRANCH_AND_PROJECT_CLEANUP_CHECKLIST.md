# FCM — Checklist maestro de auditoría, limpieza y consolidación

**Fecha de corte:** 2026-10-25
**Rama predeterminada:** `main`
**Rama de integración de trabajo:** `feat/product-table-layout`
**Propósito:** recuperar una ruta clara hacia `main`, resolver PR apiladas y limpiar el repositorio sin perder funciones, historial, datos ni capacidad de recuperación.

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
- Mientras la PR #30 permanezca abierta, `feat/product-table-layout` es la única rama de integración para el conjunto consolidado. Incorporar allí los ajustes que formen parte de ese conjunto; no abrir otra rama solo para duplicar la auditoría o el checkpoint.
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
