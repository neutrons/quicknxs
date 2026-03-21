# Fix ActiveDataRadioButton SEGV

## Branch

`bvacaliuc/fix-active-radio-button-segv` — based on `origin/next` (commit `6161c0d`)

## Status: WIP — needs investigation of 3 test failures before PR

## Problem

A segfault occurs during test `test_change_active_data_tab` (and potentially
in production) when switching data tabs or updating reduction/direct-beam tables.

### Root cause (two interacting bugs)

1. **Premature signal firing**: `ActiveDataRadioButton.initUI()` calls
   `setChecked(True)` which can fire `toggled` during `QButtonGroup.addButton()`.
   The connected handler calls `_get_current_row()`, which returns `-1` because
   the widget hasn't been added to the table yet. Python's negative indexing
   silently accesses the wrong element via `reduction_list[-1]`, corrupting
   the data manager's active state.

2. **Dangling C++ pointer**: `update_reduction_table()` and
   `update_direct_beam_table()` call `setCellWidget()` to replace old widgets.
   Qt deletes the old widget, but its radio button is still registered in the
   `QButtonGroup`. The next group interaction accesses the destroyed C++ object,
   causing the SEGV.

### Files involved

- `src/quicknxs/ui/active_radio_button.py` — widget with radio button + lambda
- `src/quicknxs/interfaces/event_handlers/main_handler.py` — creates widgets,
  manages button groups, calls `setCellWidget`
- `src/quicknxs/interfaces/main_window.py` — `set_active_reduction_data()` and
  `set_active_direct_beam()` called from the radio button's signal handler

### SEGV traceback (from analysis-node22.sns.gov)

```
active_radio_button.py      in <lambda>
main_handler.py:885         in update_reduction_table
main_handler.py:316         in update_tables
main_handler.py:411         in update_info
main_handler.py:221         in file_loaded
main_window.py:180          in file_loaded
main_window.py:515          in current_table_changed
test_main_window.py:324     in test_change_active_data_tab
```

## Fix applied (committed)

1. **Block signals during `setChecked()`** in `initUI()` — prevents premature
   `toggled` emission during construction

2. **Replace inline lambda with `_on_toggled()` method** — guards against
   `row < 0` from `_get_current_row()`, consolidates direct-beam/reduction
   branching

3. **Remove old radio buttons from button groups** before calling
   `setCellWidget()` in both `update_reduction_table()` and
   `update_direct_beam_table()` — prevents dangling C++ pointers

## Test results after fix

- `test_change_active_data_tab`: **PASSES** (was the SEGV trigger)
- Full suite: **4 failed, 210 passed, 3 skipped** on this machine

### Failures needing investigation

3 of the 4 failures are in `test/ui/test_add_non_direct_beam.py`:

| Test | Error |
|------|-------|
| `test_true_direct_beam_displays_intensity_plot` | `IndexError: list index out of range` at `main_handler.py:511` |
| `test_only_one_radio_button_selected_in_reduction_table` | same `IndexError` |
| `test_radio_button_exclusivity_with_dual_table_runs` | same `IndexError` |

The error is `self._data_manager.current_event_files[0]` on an empty list in
`update_file_list()`. This is in `main_handler.py:511`, code NOT touched by this
fix. **Investigation needed**: run these 3 tests on clean `origin/next` (without
the fix) to determine if they are pre-existing failures.

The 4th failure (`test_reduced_file_matches_gui_config[...On_Off.dat]`) is also
in code not touched by this fix and likely pre-existing.

## Remaining work

1. Verify the 3 `test_add_non_direct_beam` failures are pre-existing on `origin/next`
2. If pre-existing, proceed with draft PR as-is
3. If introduced by the fix, investigate whether `_on_toggled` guard (`row < 0`
   early return) is swallowing a signal that previously had a side effect the
   tests depend on
4. Push branch and create draft PR targeting `next`

## Related PRs

- PR #272: `bvacaliuc/skip-tests-without-lfs-data` — conftest guard for missing
  LFS data (separate fix, already open as draft)
