# Download history UI recovery baseline

This document records the historical behavior that was compared against the current download-history screen. It is based on commits that already implemented and refined the feature; it is not a new design invented for the recovery.

## Current state

The catalog synchronization and persistence model remain validated and were not changed by this UI recovery.

The current history dialog now preserves the information relevant to the active architecture:

- download date/time and duration;
- current application state derived from `scraping_history.applied_at`;
- direct per-download detail;
- detected changes only, ordered by product code;
- coverage, category and multi-category information.

The status presentation is now explicit:

- `SUCCESS + applied_at`: **APLICADO** with the application date/time;
- `SUCCESS + applied_at = NULL`: **NO APLICADO**, meaning a successful historical version was superseded by a later automatic application;
- non-successful execution: **ERROR**.

The current runtime automatically applies a successful synchronization. The old manual **Aplicar** action from the historical `CatalogLoadRepository` implementation is not restored because that repository/snapshot model no longer exists in the current architecture. Reintroducing it without persistent catalog snapshots would create a second application model and weaken the current authority rules.

## Historical evidence

### `530ac24351b5574c99b5e0412182ecb76760b582`

Commit: `Rediseñar desde cero el historial de descargas y su detalle`.

The history window was explicitly presented as **Historial de descargas y versiones del catálogo** and exposed download statistics, status and a dedicated detail action.

### `94c5398233b4efc48c015e63fc511ff333b7cbd2`

Commit: `Mejorar historial aplicado y navegación de detalles`.

The UI added/refined an applied-state presentation with a visible applied timestamp, a dedicated detail action and visible styling for the applied catalog version.

### `696d7ebbc81230fcba29b3605f16f402b132ac48a`

Commit: `Ajustar estados de aplicación y detalle del historial`.

The historical behavior distinguished successful versions, the currently applied version, superseded successful versions and failed/non-applicable executions.

### `5d53c66db4e795b49909fd3919c6fe12a87c434a`

Commit: `Mejorar navegación del detalle de descarga`.

The detail view was made non-modal so it could remain open independently.

### `62d808e0e6da53ad9facd1e299bd2e36e6dce343`

Commit: `Corregir carga visual del historial`.

This corrected the table-item implementation after the history UI refactor.

## What the recovery preserves

1. **Download timestamp and duration.** The current table shows execution date/time and elapsed duration.
2. **Application state.** The current row state reflects the persisted `applied_at` marker instead of treating every successful row as currently applied.
3. **Per-download detail.** Each row exposes a direct **Ver detalle** action and double-click navigation.
4. **Detailed change information.** The detail view reads the persisted `download_changes` rows and does not manufacture changes for unchanged products.
5. **Version semantics.** A later successful automatic application clears the previous current marker while leaving the older history record and its details intact.
6. **Coverage information.** The newer coverage, category and multi-category information remains in the detail view.

## Data-layer rules

The UI restoration does not rewrite the validated history data model:

- `NEW` records expand into stored product fields.
- `UPDATED` records contain only fields that actually changed.
- `DELETED` records are explicit.
- Change details are ordered by product code.
- Completion/application timestamps remain intact.
- An idempotent run with only unchanged products produces zero detail rows.

## Validation

Focused history/catalog/coverage tests remain part of the validated suite.

For the UI-state recovery, `tests/scraping/test_history_application_state.py` now covers:

- applied successful version with timestamp;
- superseded successful version without `applied_at`;
- failed execution;
- existing history-column and responsive-width behavior.

No new 24-category real scrape is required for this presentation-layer change because the scraping, persistence and coverage runtime were not modified.

## Recovery rule

Keep the current data model as the single persistence authority. UI changes should derive application state from the persisted history marker and should not reintroduce a parallel catalog-load/snapshot mechanism without a separate architectural decision.
