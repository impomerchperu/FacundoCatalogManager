# Download history UI recovery baseline

This document records the historical behavior that must be recovered in the download-history screen. It is based on commits that already implemented and refined the feature; it is not a new design invented for the recovery.

## Current state

The catalog synchronization itself is validated and must remain untouched while restoring the history presentation. The remaining issue is that the current history UI does not expose all of the information and application-state behavior that had previously been implemented.

## Historical evidence

### `530ac24351b5574c99b5e0412182ecb76760b582`

Commit: `Rediseñar desde cero el historial de descargas y su detalle`.

The history window was explicitly presented as **Historial de descargas y versiones del catálogo**.

The main table exposed these columns:

- Fecha de descarga
- Productos
- Nuevos
- Actualizados
- Sin cambios
- Errores
- Estado
- Catálogo
- Detalle

The detail view already existed as a dedicated way to inspect the changes of a download.

### `94c5398233b4efc48c015e63fc511ff333b7cbd2`

Commit: `Mejorar historial aplicado y navegación de detalles`.

The UI added/refined:

- an explicit **Detalle** action per history row;
- an applied-state presentation with a visible applied timestamp;
- a distinct **Catálogo** state/action column;
- the ability to navigate to row-specific details directly;
- visible styling for an applied catalog version.

### `696d7ebbc81230fcba29b3605f16f402b132ac48`

Commit: `Ajustar estados de aplicación y detalle del historial`.

The application policy was refined so history distinguishes between:

- a successful download that can be applied;
- the download currently applied, with its own application date/time;
- an older download that has been superseded and is therefore **No Aplicado**;
- non-successful downloads that are **No aplicable**.

It also preserved the concept that the latest applicable download is the one that can be applied next.

### `5d53c66db4e795b49909fd3919c6fe12a87c434a`

Commit: `Mejorar navegación del detalle de descarga`.

The scraping dialog's detail view was made non-modal so it could remain open independently and be brought to the front without blocking the rest of the application.

### `62d808e0e6da53ad9facd1e299bd2e36e6dce343`

Commit: `Corregir carga visual del historial`.

This corrected the table-item implementation after the history UI refactor. It is part of the known-good historical sequence and should not be treated as obsolete cleanup without evidence.

## What the current recovery must restore/preserve

The current branch has added useful scraping-coverage data, deleted counts, and the new history repository policy. Those additions are valuable and should stay.

However, restoring the history UI must also recover the information that was previously visible:

1. **Download timestamp and duration.** The historical table showed both the execution date and the elapsed duration of the scraping/download operation.
2. **Catalog application state.** The UI distinguished whether a download was applicable, already applied, or superseded, and an applied version showed its own application timestamp.
3. **Per-download detail.** Each history record must provide a direct way to open the complete detail for that specific download.
4. **Detailed change information.** The detail view must expose the detected changes faithfully, without turning unchanged products into fake changes.
5. **Version semantics.** A download is a historical version; applying a later version must not erase the audit state of earlier applications.
6. **Current coverage information.** The newer recovery work already exposes coverage metrics and category information. These must remain and coexist with the restored historical fields.

## Data-layer rules

The UI restoration must not rewrite the validated history data model:

- `NEW` records expand into the stored product fields.
- `UPDATED` records contain only the fields that actually changed.
- `DELETED` records are explicit.
- Change details are ordered by product code.
- Completion/application timestamps remain intact.
- An idempotent run with only unchanged products produces zero detail rows.

## Evidence already validated on the current branch

- FULL history `169`: 526 created, 0 updated, 0 unchanged, 0 deleted.
- FULL history `170`: 0 created, 0 updated, 526 unchanged, 0 deleted, and **0 detail rows**.
- Focused history/catalog/coverage tests: `26 passed`.
- Ruff: `All checks passed!`.
- The desktop application currently opens the catalog correctly from SQLite.

## Recovery rule

Do not replace the historical behavior with a simpler new interpretation. First compare `gui/scraping_history_dialog.py` against the historical commits above, recover missing presentation/state behavior, add deterministic GUI or repository tests for every restored behavior, and only then consider any UI refinements.

Do not run another 24-category real scrape merely to investigate this UI problem; the existing history records and deterministic tests are enough to validate the presentation layer.
