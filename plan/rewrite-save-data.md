# Plan: Rewrite `save_data()` in `mplwidget.py`

## Context

EWM15204 tracks a deficiency in the quicknxsv2 "Save XYE data" toolbar button: it only works for 1D errorbar plots. 2D plots (imshow detector maps, pcolormesh off-specular/GISANS) either fail silently or produce unusable output. The `bvacaliuc/ewm15204-triage` branch added `.npz`/`.pkl` export and `import wat` debugging to explore the varied array structures. This plan replaces that triage code with a clean, tested implementation supporting all plot types and three output formats.

## Files to modify

| File | Action |
|------|--------|
| `src/quicknxs/ui/mplwidget.py` | Rewrite `save_data()`, add helper functions, clean up triage artifacts |
| `test/ui/test_mplwidget.py` | Add `TestSaveData` class with ~10 test methods |
| `pyproject.toml` | Remove `wat` dependency if present |

## Step 1: Clean up triage artifacts

- Remove `import wat` (line 158) and all `wat /` debug lines
- Remove `import inspect` (line 9, unused after cleanup — verify first)
- Add `import pickle` to top-level imports
- Keep `centerbins()` helper (used for pcolormesh bin center calculation)

## Step 2: Add plot-type detection function

Add `_detect_plot_type(ax)` as a module-level function after `centerbins()`. Returns one of: `"imshow"`, `"pcolormesh"`, `"errorbar"`, `"line"`, `"empty"`.

Detection order (mirrors existing `toggle_log` pattern at line 240):
1. `len(ax.images) > 0` → `"imshow"`
2. Any QuadMesh in `ax.collections` → `"pcolormesh"`
3. Filter out overlay lines (axvline/axhline) by checking `line.get_transform() != ax.transData` — overlay lines use a blended axes/data transform, data lines use `ax.transData`
4. Count remaining data lines: `len % 3 == 0 and len >= 3` → `"errorbar"`, else if `len > 0` → `"line"`, else → `"empty"`

## Step 3: Add data extraction functions

Four module-level functions, each returns a dict of numpy arrays + metadata:

### `_extract_errorbar_data(ax)` → 1D reflectivity
- Filter data lines (exclude overlays via transform check)
- Iterate in groups of 3: `[data_line, err_lo, err_hi]`
- Extract `x`, `y`, `error = (err_hi_y - err_lo_y) / 2.0`, `label`
- Returns `{'datasets': [...], 'xlabel', 'ylabel', 'title'}`

### `_extract_imshow_data(ax)` → 2D detector maps
- `img = ax.images[0]`
- `data = np.array(img.get_array())` — may need reshape from `img.get_size()`
- `extent = img.get_extent()` → `[xmin, xmax, ymin, ymax]`
- Returns `{'data', 'extent', 'xlabel', 'ylabel', 'title'}`

### `_extract_pcolormesh_data(ax)` → off-specular / GISANS
- Find QuadMesh: `[c for c in ax.collections if c.__class__.__name__ == "QuadMesh"][0]`
- `coords = qm.get_coordinates()` → shape `(ny+1, nx+1, 2)`
- `z = np.array(qm.get_array())` — reshape to `(ny, nx)` if flattened
- `x_edges = coords[0, :, 0]`, `y_edges = coords[:, 0, 1]`
- `x_centers = centerbins(x_edges)`, `y_centers = centerbins(y_edges)`
- Returns `{'x_edges', 'y_edges', 'x_centers', 'y_centers', 'z_data', 'xlabel', 'ylabel', 'title'}`

### `_extract_line_data(ax)` → projection plots
- Filter data lines (exclude overlays)
- Each line: extract `x`, `y`, `label`
- Returns `{'datasets': [...], 'xlabel', 'ylabel', 'title'}`

## Step 4: Add save functions

### `_save_dat(fname, extracted, plot_type)`
Dispatcher that calls the appropriate sub-function:

- **errorbar**: Write datasets separated by two blank lines (gnuplot "index" convention). Header per block: `# Dataset N: label`, `# X  Y  Error`. Body via `np.savetxt(f, block, delimiter='\t')`.
- **line**: Similar, but 2 columns (X, Y) per dataset.
- **imshow**: Header with extent info, then 2D array via `np.savetxt`.
- **pcolormesh**: Header with axis labels + edge arrays, then 2D Z array via `np.savetxt`.

### `_save_npz(fname, extracted, plot_type)`
- Saves all extracted arrays as named keys via `np.savez_compressed`
- Includes `plot_type` key for self-documentation
- For errorbar/line: `x_0`, `y_0`, `error_0`, `label_0`, ... `n_datasets`
- For imshow: `data`, `extent`
- For pcolormesh: `x_edges`, `y_edges`, `x_centers`, `y_centers`, `z_data`

### `_save_pkl(fname, figure, extracted, plot_type)`
- `pickle.dump({'figure': figure, 'plot_type': plot_type, 'data': extracted}, f, protocol=4)`
- Preserves full matplotlib figure for reconstruction via `test/show.py`

## Step 5: Rewrite `save_data()` method

Replace the entire current method (lines 157-226) with:

```python
def save_data(self):
    """Save the current plot data to file (.dat, .npz, or .pkl)."""
    ax = self.canvas.ax
    try:
        plot_type = _detect_plot_type(ax)
        if plot_type == "empty":
            raise ValueError("No data to save: the plot is empty.")

        # Extract data
        extractor = {
            "errorbar": _extract_errorbar_data,
            "imshow": _extract_imshow_data,
            "pcolormesh": _extract_pcolormesh_data,
            "line": _extract_line_data,
        }
        extracted = extractor[plot_type](ax)

        # File dialog with format filters
        filters = "ASCII data (*.dat);;Numpy archive (*.npz);;Pickle (*.pkl)"
        fname, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save plot data", "", filters
        )
        if not fname:
            return

        # Determine format from extension, fall back to filter
        _, ext = os.path.splitext(fname)
        ext = ext.lower()
        if ext not in ('.dat', '.npz', '.pkl'):
            # Append extension from selected filter
            for candidate in ('.dat', '.npz', '.pkl'):
                if f'*{candidate}' in selected_filter:
                    fname += candidate
                    ext = candidate
                    break
            else:
                raise ValueError(f"Unknown file format: {ext or '(none)'}")

        # Save
        if ext == '.dat':
            _save_dat(fname, extracted, plot_type)
        elif ext == '.npz':
            _save_npz(fname, extracted, plot_type)
        elif ext == '.pkl':
            _save_pkl(fname, self.canvas.figure, extracted, plot_type)

        logging.info(f"Saved {plot_type} data to {fname}")

    except Exception as e:
        logging.error(f"Error saving data: {e}")
        QtWidgets.QMessageBox.critical(
            self, "Error saving data", str(e),
            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.NoButton,
        )
```

## Step 6: Add tests

New `TestSaveData` class in `test/ui/test_mplwidget.py`. Each test creates an `MPLWidget` directly (no MainWindow needed for unit tests), populates it with known data, mocks `QFileDialog.getSaveFileName`, calls `save_data()`, and verifies output.

### Test cases

| # | Test | Plot type | Format | Validates |
|---|------|-----------|--------|-----------|
| 1 | `test_detect_plot_type_*` | all | — | `_detect_plot_type()` returns correct string for each setup |
| 2 | `test_save_errorbar_dat` | errorbar | .dat | Column values match input X/Y/E |
| 3 | `test_save_errorbar_npz` | errorbar | .npz | Array keys and values match |
| 4 | `test_save_errorbar_pkl` | errorbar | .pkl | Round-trip dict structure, figure type |
| 5 | `test_save_imshow_dat` | imshow | .dat | Header has extent, body matches 2D array |
| 6 | `test_save_imshow_npz` | imshow | .npz | `data` and `extent` arrays correct |
| 7 | `test_save_pcolormesh_npz` | pcolormesh | .npz | Edge, center, Z arrays correct |
| 8 | `test_save_line_dat` | line | .dat | X/Y columns match |
| 9 | `test_save_empty_plot_error` | empty | — | QMessageBox.critical called |
| 10 | `test_save_imshow_with_overlays` | imshow+axvline | .npz | Overlay lines ignored, imshow data saved |

### Mock pattern
```python
monkeypatch.setattr(
    QtWidgets.QFileDialog, "getSaveFileName",
    staticmethod(lambda *a, **kw: (str(tmp_path / "out.dat"), "ASCII data (*.dat)"))
)
```

## Step 7: Cleanup and validate

1. Remove `wat>=0.7.0,<0.8` from `pyproject.toml` `[project.dependencies]` if present
2. Run `pixi run test -vv -k test_mplwidget` to validate new + existing tests pass
3. Run pre-commit (ruff lint + format) to ensure style compliance
4. Verify `test/show.py` still works with new `.pkl` format (dict wrapper instead of tuple)

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| `get_array()` returns flattened array for some matplotlib versions | Check shape and reshape using `get_coordinates()` dimensions |
| Transform comparison `!= ax.transData` might not work if matplotlib creates a copy | Fall back: also accept `CompositeGenericTransform` class name |
| Projection plots have 1 data line + N overlay lines — `len % 3 != 0` | Correctly classified as `"line"` type, not `"errorbar"` |
| Tests require Qt display | `pytest-xvfb` already in dev dependencies handles this |
| `pixi` environment may not be available on dev machine | Tests can be written and committed; CI validates on push |
