# Plan: Phase 2 - Replace Shared Reentrancy With Local Render Blocking

Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
Frontend Phase 2.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Remove reliance on the broad `auto_change_active` guard from the direct-beam and
reduction table update paths. Programmatic rendering should suppress only the widget
signals it causes, and only for the duration of that render operation.

Phase 2 should make update ordering explicit:

1. A user action enters through an existing slot or thin forwarding method.
2. The model/session state is mutated.
3. View models are built from current state.
4. The view renders those models while blocking the specific Qt signals being
   triggered by programmatic widget updates.

## Inputs From Phase 1

Phase 2 assumes Phase 1 has produced:

- Direct-beam and reduction row view models with opaque entry IDs.
- Read-only builders that can create row models from the current `DataManager`.
- Focused view classes with render methods and user-action hooks.
- Characterization tests around duplicate run numbers and copied `NexusData`
  instances.
- The Phase 1A identity contract defining when table code may compare by entry ID,
  run number, file path, object identity, or reduced-file `DB_ID`.

The live application may still use the legacy `DataManager`, `MainHandler`, and
`Configuration` classes.

## Scope

In scope:

- Direct-beam table rendering.
- Reduction/data table rendering.
- Direct-beam table cell edit handling.
- Reduction table cell edit handling.
- Run overview/configuration render methods only where they participate in the same
  reentrant update chains.
- Tests proving that programmatic renders do not trigger user-edit handlers.

Not in scope:

- Extracting presenters.
- Splitting `DataManager`.
- Replacing the legacy `Configuration` object.
- Moving file I/O to the backend.
- Rewriting plotting logic beyond invoking existing refresh hooks.

## Current Problem

`auto_change_active` acts as a shared global reentrancy flag. It is used to stop
programmatic widget updates from being treated as user edits. This works, but it
couples unrelated render operations and makes ordering difficult to reason about.

It is especially risky now that one source run can appear as multiple mutable session
entries. A guard that only says "an automatic change is active" does not say which
entry is rendering, which table owns the change, or whether a same-run entry should
also be updated.

## Target Pattern

Each render method should own its own signal blocking:

```python
def show_direct_beam_rows(self, rows: tuple[DirectBeamRowModel, ...]) -> None:
    table = self.ui.directBeamTable
    table.blockSignals(True)
    try:
        self._render_direct_beam_rows(table, rows)
    finally:
        table.blockSignals(False)
```

For multiple widgets, prefer a small context manager:

```python
@contextmanager
def block_widget_signals(*widgets):
    previous = [widget.blockSignals(True) for widget in widgets]
    try:
        yield
    finally:
        for widget, was_blocked in zip(widgets, previous):
            widget.blockSignals(was_blocked)
```

Preserve prior blocked state instead of assuming it was `False`.

## Implementation Steps

### Step 1: Inventory `auto_change_active`

List every use of `auto_change_active` in `MainWindow`, `MainHandler`, and related
handlers.

Classify each use as:

- Table render guard.
- Configuration render guard.
- File-list selection guard.
- Cross-section button guard.
- General workflow guard.

Only migrate table and closely related render guards in Phase 2. Leave unrelated
guards with comments that they are intentionally out of scope.

### Step 2: Implement Local Signal Blocking

Add a small helper for blocking widget signals. Keep it in a UI-facing module, not in
model or backend code.

Rules:

- Use it only in render methods.
- Preserve each widget's previous blocked state.
- Keep mutation logic outside the blocked section.
- Do not call model/reduction code while signals are blocked.
- Rendering a table must not mutate the underlying session except through an
  explicit selected-entry synchronization step.

### Step 3: Make Table Render Methods Consume Row Models

Update `MainWindow.show_direct_beam_rows()` and
`MainWindow.show_reduction_rows()` so they render their row-model arguments instead
of delegating wholesale to existing `update_tables()` behavior.

The display methods should:

- Rebuild rows from view models.
- Store the opaque entry ID in a hidden column, item data role, or table-owned mapping.
- Display run number as a label only.
- Preserve current selection when the same entry ID still exists.
- Use local signal blocking around programmatic row/cell changes.

### Step 4: Convert Direct-Beam Table Edits

For the direct-beam table edit path:

1. Read the edited row's entry ID from the table mapping.
2. Resolve that entry to the current direct-beam list entry.
3. Mutate only that entry's configuration.
4. Rebuild direct-beam row models.
5. Rebuild affected reduction row models if direct-beam-dependent values change.
6. Render through `show_direct_beam_rows()` and `show_reduction_rows()`.
7. Trigger existing plot refreshes.

Do not look up the row by run number when the operation is editing mutable row state.

### Step 5: Convert Reduction Table Edits

For the data/reduction table edit path:

1. Read the edited row's entry ID.
2. Resolve that entry to the current reduction list entry.
3. Mutate only that entry's run-specific parameters.
4. Recalculate only the affected reflectivity path where current behavior allows it.
5. Rebuild and render affected row models.
6. Trigger existing plot refreshes.

Direct-beam matching may still use run metadata, but the table edit itself should
target an entry ID.

### Step 6: Remove Migrated `auto_change_active` Uses

After direct-beam and reduction table render paths block their own signals, remove
the guard checks from those migrated paths.

Do not remove the flag globally until all remaining uses are classified and migrated.

### Step 7: Add Tests

Add tests for:

- Programmatic `show_direct_beam_rows()` does not invoke direct-beam edit handling.
- Programmatic `show_reduction_rows()` does not invoke reduction edit handling.
- Editing one direct-beam row does not mutate another direct-beam row with the same
  run number.
- Editing one reduction row does not mutate another reduction row with the same run
  number.
- Selection preservation uses entry ID, not row number or run number.
- Signal-blocking helper restores prior blocked state after exceptions.

Use focused Qt tests for signal behavior and plain unit tests for row-model identity.

## Acceptance Criteria

- Direct-beam and reduction table render methods use local signal blocking.
- The migrated table edit paths do not depend on `auto_change_active`.
- Row mutation uses entry identity, not run number.
- Duplicate-run-number characterization tests pass.
- Existing direct-beam/data-run workflows still behave the same from the user's
  perspective.
- Remaining `auto_change_active` uses are documented and deferred to later presenter
  extraction or view-render cleanup.

## Relationship To Other Plans

- Phase 1 provides row models, entry IDs, and builder tests.
- Phase 3 uses the cleaned mutation/render pattern when extracting presenters.
- Phase 4 moves entry identity ownership out of adapters and into session services.
- The frontend configuration/job phase applies the same local-render principle to
  configuration widgets and job progress UI.
