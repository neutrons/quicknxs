# Plan: Fix data extraction and round-trip verification for save_data()

## Context

Real-world `.dat` files exported from quicknxsv2 plots reveal multiple bugs that
prevent correct round-trip reconstruction. Issues were found by examining files in
`/SNS/REF_M/IPTS-32745/shared/autoreduce/`. The `test/show.py` utility cannot
reproduce the original plots because: (1) pcolormesh extraction is wrong for
gouraud-shaded plots (all off-specular and GISANS), (2) imshow extraction is
missing `origin` metadata needed for correct orientation, and (3) `test/show.py`
cannot properly interpret imshow `.dat` files.

## Bugs found

### Bug 1: Gouraud pcolormesh — wrong coordinate extraction (CRITICAL)

**File:** `src/quicknxs/ui/mplwidget.py` — `_extract_pcolormesh_data()`

All off-specular and GISANS plots use `shading="gouraud"`, which means the
coordinate arrays passed to pcolormesh are **2D node grids**, not 1D edge arrays.

- `get_coordinates()` returns `(ny, nx, 2)` where `ny, nx` match `z_data.shape`
- `get_array()` returns `(ny, nx)` — same shape as the coordinate grid
- Current code does `ny, nx = coords.shape[0]-1, coords.shape[1]-1` — **WRONG for gouraud**
- `centerbins()` on node positions produces midpoints (length n-1) — **WRONG for gouraud**

**Result:** z_data is (287, 68) but we write only 286×67 = 19,162 of 19,516 points. Data is silently lost and coordinates are shifted to incorrect midpoints.

**Fix:** Detect whether the data is gouraud (z_data shape matches coords shape without -1). For gouraud, use coordinates directly as node positions instead of computing centers from edges.

### Bug 2: Imshow — missing `origin` metadata (HIGH)

**File:** `src/quicknxs/ui/mplwidget.py` — `_extract_imshow_data()`

- XY plots use `origin="lower"` (row 0 = bottom)
- XToF plots use default `origin="upper"` (row 0 = top)
- `get_array()` returns data in input order regardless of origin
- Without storing `origin`, reconstruction with `imshow()` uses the wrong default

**Fix:** Capture `img.origin` in the extracted dict. Write it in `.dat` header. Pass it to `show.py` reconstruction.

### Bug 3: `test/show.py` — cannot interpret imshow `.dat` files

For imshow `.dat` files (256×304 or 304×84 columns), show.py falls into the
`ax.plot()` path because `raw.shape[1] != 3`. It needs a dedicated imshow
detection path.

**Fix:** Detect imshow format from the header (contains `extent:` line). Parse extent from header, reconstruct with `ax.imshow(data, extent=extent, origin=origin)`.

### Bug 4: pcolormesh `.dat` header says "x_edges/y_edges" for gouraud data

For gouraud data, these are node positions, not edges. The header metadata
should reflect what the coordinates actually are.

## Files to modify

| File | Changes |
|------|---------|
| `src/quicknxs/ui/mplwidget.py` | Fix `_extract_pcolormesh_data`, `_extract_imshow_data`, `_save_dat_imshow`, `_save_dat_pcolormesh`, `_save_npz` |
| `test/ui/test_mplwidget.py` | Add gouraud pcolormesh tests, imshow origin tests, round-trip tests |
| `test/show.py` | Add imshow .dat interpretation, fix pcolormesh reconstruction |

## Implementation

### Step 1: Fix `_extract_pcolormesh_data` in mplwidget.py

```python
def _extract_pcolormesh_data(ax):
    qm = next(c for c in ax.collections if c.__class__.__name__ == "QuadMesh")
    coords = qm.get_coordinates()  # (ny_coords, nx_coords, 2)
    z_data = np.array(qm.get_array(), dtype=float)

    # Detect gouraud vs flat shading:
    # gouraud: z_data.shape == (coords.shape[0], coords.shape[1])
    # flat:    z_data.shape == (coords.shape[0]-1, coords.shape[1]-1)
    is_gouraud = (z_data.shape[0] == coords.shape[0] and z_data.shape[1] == coords.shape[1])

    x_coords_1d = coords[0, :, 0]
    y_coords_1d = coords[:, 0, 1]

    if is_gouraud:
        # Coordinates are node positions — use directly
        result = {
            "x_nodes": x_coords_1d,
            "y_nodes": y_coords_1d,
            "z_data": z_data,
            "shading": "gouraud",
        }
    else:
        # Coordinates are bin edges — compute centers
        result = {
            "x_edges": x_coords_1d,
            "y_edges": y_coords_1d,
            "x_centers": centerbins(x_coords_1d),
            "y_centers": centerbins(y_coords_1d),
            "z_data": z_data,
            "shading": "flat",
        }

    result.update({
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    })
    return result
```

### Step 2: Fix `_save_dat_pcolormesh`

Update to handle both gouraud (use node positions directly) and flat (use centers):

```python
def _save_dat_pcolormesh(fname, extracted):
    z_data = extracted["z_data"]
    shading = extracted.get("shading", "flat")

    if shading == "gouraud":
        x_vals = extracted["x_nodes"]
        y_vals = extracted["y_nodes"]
        coord_label = "x_nodes", "y_nodes"
    else:
        x_vals = extracted["x_centers"]
        y_vals = extracted["y_centers"]
        coord_label = "x_centers (from edges)", "y_centers (from edges)"

    with open(fname, "w") as f:
        # Header
        f.write(f"# title: {extracted['title']}\n")
        f.write(f"# xlabel: {extracted['xlabel']}\n")
        f.write(f"# ylabel: {extracted['ylabel']}\n")
        f.write(f"# shading: {shading}\n")
        if shading == "flat":
            f.write(f"# x_edges ({len(extracted['x_edges'])}): ...\n")
            f.write(f"# y_edges ({len(extracted['y_edges'])}): ...\n")
        f.write(f"# z_data shape: {z_data.shape}\n")
        f.write(f"# {extracted['xlabel']}\t{extracted['ylabel']}\tZ\n")

        # gnuplot xyz body
        for ix, xc in enumerate(x_vals):
            for iy, yc in enumerate(y_vals):
                f.write(f"{xc:.6g}\t{yc:.6g}\t{z_data[iy, ix]:.6g}\n")
            if ix < len(x_vals) - 1:
                f.write("\n")
```

### Step 3: Fix `_save_npz` for pcolormesh

Update to save the correct coordinate keys based on shading type. Include `shading` key.

### Step 4: Fix `_extract_imshow_data`

Add `origin` to the extracted data:

```python
def _extract_imshow_data(ax):
    img = ax.images[0]
    return {
        "data": np.array(img.get_array(), dtype=float),
        "extent": np.array(img.get_extent()),
        "origin": img.origin,
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    }
```

### Step 5: Fix `_save_dat_imshow`

Add `origin` to the header:

```python
def _save_dat_imshow(fname, extracted):
    header = (
        f"extent: xmin={extracted['extent'][0]}, xmax={extracted['extent'][1]}, "
        f"ymin={extracted['extent'][2]}, ymax={extracted['extent'][3]}\n"
        f"origin: {extracted['origin']}\n"
        f"{extracted['xlabel']} vs {extracted['ylabel']}"
    )
    np.savetxt(fname, extracted["data"], header=header, delimiter="\t")
```

### Step 6: Fix `_save_npz` for imshow

Add `origin` key to the npz output.

### Step 7: Update `test/show.py`

Add proper handling for:
1. **imshow `.dat`**: Detect from `extent:` header line. Parse extent and origin. Use `ax.imshow()`.
2. **pcolormesh `.dat`**: Detect `shading:` header line to choose `pcolormesh(..., shading=...)` or plain scatter.
3. **npz files**: Handle both `x_nodes`/`y_nodes` (gouraud) and `x_edges`/`y_edges`/`x_centers`/`y_centers` (flat).

### Step 8: Add comprehensive round-trip tests

New tests in `test/ui/test_mplwidget.py`:

| Test | What it verifies |
|------|-----------------|
| `test_detect_pcolormesh_gouraud` | Detection works with 2D grid input |
| `test_save_pcolormesh_gouraud_dat` | Gouraud xyz output: all z_data points present, x/y are node positions |
| `test_save_pcolormesh_gouraud_npz` | NPZ contains x_nodes, y_nodes, shading="gouraud" |
| `test_roundtrip_pcolormesh_gouraud` | Write .dat, read back, verify z_data matches original |
| `test_roundtrip_pcolormesh_flat` | Write .dat, read back, verify z_data matches original |
| `test_save_imshow_with_origin_lower` | .dat header contains `origin: lower` |
| `test_save_imshow_with_origin_upper` | .dat header contains `origin: upper` |
| `test_roundtrip_imshow_dat` | Write .dat, read back with extent+origin, verify array matches |
| `test_roundtrip_errorbar_dat` | Write .dat, read back, verify X/Y/E match |
| `test_roundtrip_line_dat` | Write .dat, read back, verify X/Y match |
| `test_roundtrip_all_npz` | For each plot type: write .npz, load, verify all arrays |

Round-trip tests use a helper function that mirrors `show.py` logic to parse
the `.dat` format back into arrays, then asserts `allclose` against the
original data.

## Verification

1. `pixi run test -vv -k test_mplwidget` — all tests pass
2. `pixi run pre-commit run --files ...` — ruff clean
3. Manual: re-export off-specular .dat, verify 287×68 data points present
4. Manual: run `test/show.py` on exported files, compare with UI
