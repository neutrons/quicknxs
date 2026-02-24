#!/usr/bin/env python
"""Utility to display saved .pkl, .npz, or .dat files from save_data().

Usage:
    python show.py [path-to-file]

Supports .dat (gnuplot xyz for pcolormesh, imshow 2D array, columnar for others),
.npz (compressed numpy archive), and .pkl (pickle with full figure).
Preserves logarithmic scales, colormaps, norms, titles, and axis labels.
"""

import re
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm, Normalize

# Register the custom "default" colormap used by quicknxs
_cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
    "default", ["#0000ff", "#00ff00", "#ffff00", "#ff0000", "#bd7efc", "#000000"], N=256
)
if "default" not in matplotlib.colormaps:
    matplotlib.colormaps.register(_cmap, name="default")

filename = sys.argv[1] if len(sys.argv) > 1 else "output.pkl"

plt.ioff()


def show_figure(fig):
    """Create a dummy figure and use its manager to display 'fig'."""
    dummy = plt.figure()
    new_manager = dummy.canvas.manager
    new_manager.canvas.figure = fig
    fig.set_canvas(new_manager.canvas)
    plt.show()


def _parse_dat_header(text):
    """Extract metadata from # comment lines in a .dat file."""
    meta = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        content = line.lstrip("# ").strip()
        m = re.match(
            r"extent: xmin=([\d.e+-]+), xmax=([\d.e+-]+), "
            r"ymin=([\d.e+-]+), ymax=([\d.e+-]+)",
            content,
        )
        if m:
            meta["extent"] = [float(m.group(i)) for i in range(1, 5)]
        for key in ("origin", "shading", "cmap", "norm", "xscale", "yscale"):
            m = re.match(rf"{key}: (\S+)", content)
            if m:
                meta[key] = m.group(1)
        for key in ("norm_vmin", "norm_vmax"):
            m = re.match(rf"{key}: ([\d.e+-]+)", content)
            if m:
                meta[key] = float(m.group(1))
        for key in ("n_surfaces",):
            m = re.match(rf"{key}: (\d+)", content)
            if m:
                meta[key] = int(m.group(1))
        for key in ("xlabel", "ylabel", "title"):
            m = re.match(rf"{key}: (.+)", content)
            if m:
                meta[key] = m.group(1)
        m = re.match(r"Dataset (\d+): (.+)", content)
        if m:
            meta.setdefault("dataset_labels", {})[int(m.group(1))] = m.group(2)
    return meta


def _make_norm(meta):
    """Build a matplotlib Normalize or LogNorm from header metadata."""
    norm_type = meta.get("norm", "Normalize")
    vmin = meta.get("norm_vmin")
    vmax = meta.get("norm_vmax")
    if norm_type == "LogNorm":
        return LogNorm(vmin=vmin, vmax=vmax)
    return Normalize(vmin=vmin, vmax=vmax)


def _apply_labels(ax, meta):
    """Set title, xlabel, ylabel on axes from metadata dict."""
    ax.set_xlabel(meta.get("xlabel", ""))
    ax.set_ylabel(meta.get("ylabel", ""))
    ax.set_title(meta.get("title", ""))


def _apply_scales(ax, meta):
    """Set xscale and yscale from metadata dict."""
    if meta.get("xscale") == "log":
        ax.set_xscale("log")
    if meta.get("yscale") == "log":
        ax.set_yscale("log")


def _is_pcolormesh_dat(meta):
    """Detect pcolormesh format by presence of shading or grid header keys."""
    return "shading" in meta or "grid" in meta


if filename.endswith(".dat"):
    text = open(filename).read()
    meta = _parse_dat_header(text)
    raw = np.loadtxt(filename)

    if "extent" in meta:
        # Imshow format
        extent = meta["extent"]
        origin = meta.get("origin", "upper")
        cmap = meta.get("cmap", "default")
        norm = _make_norm(meta)
        print(f"Imshow .dat: shape {raw.shape}, origin {origin}, norm {type(norm).__name__}")
        fig, ax = plt.subplots()
        ax.imshow(raw, extent=extent, origin=origin, aspect="auto", cmap=cmap, norm=norm)
        _apply_labels(ax, meta)
        plt.show()

    elif raw.ndim == 2 and raw.shape[1] == 3 and _is_pcolormesh_dat(meta):
        # Pcolormesh xyz — may have multiple surfaces of different sizes.
        # Surfaces are separated by triple-newline (double blank line at end of surface).
        # Within a surface, grid rows are separated by single blank line.
        shading = meta.get("shading", "flat")
        cmap = meta.get("cmap", "default")
        norm = _make_norm(meta)

        # Split data (excluding header) into surfaces by triple-newline
        data_lines = [line for line in text.splitlines() if not line.startswith("#")]
        data_text = "\n".join(data_lines)
        surface_texts = [s.strip() for s in data_text.split("\n\n\n") if s.strip()]

        fig, ax = plt.subplots()
        if shading == "gouraud":
            for si, surf_text in enumerate(surface_texts):
                # Each row-block within a surface is separated by double-newline
                row_blocks = [r.strip() for r in surf_text.split("\n\n") if r.strip()]
                s_ny = len(row_blocks)
                s_nx = len([l for l in row_blocks[0].splitlines() if l.strip()])
                surf_data = np.loadtxt(surf_text.splitlines())
                X = surf_data[:, 0].reshape(s_ny, s_nx)
                Y = surf_data[:, 1].reshape(s_ny, s_nx)
                Z = surf_data[:, 2].reshape(s_ny, s_nx)
                ax.pcolormesh(X, Y, Z, shading="gouraud", cmap=cmap, norm=norm)
                print(f"  Surface {si}: grid {s_ny}x{s_nx}")
            print(f"Pcolormesh .dat (gouraud): {len(surface_texts)} surfaces")
        else:
            xs = np.unique(raw[:, 0])
            ys = np.unique(raw[:, 1])
            z = raw[:, 2].reshape(len(xs), len(ys)).T
            ax.pcolormesh(xs, ys, z, cmap=cmap, norm=norm)
            print(f"Pcolormesh .dat (flat): {len(xs)}x{len(ys)}")
        _apply_labels(ax, meta)
        plt.show()

    elif raw.ndim == 2 and raw.shape[1] == 3:
        # Errorbar data — may have multiple datasets separated by blank lines
        labels = meta.get("dataset_labels", {})
        # Split data by double-blank-line (gnuplot index) separation
        data_lines = [line for line in text.splitlines() if not line.startswith("#")]
        data_text = "\n".join(data_lines)
        blocks = [b.strip() for b in data_text.split("\n\n") if b.strip()]
        fig, ax = plt.subplots()
        for i, block in enumerate(blocks):
            arr = np.loadtxt(block.splitlines())
            label = labels.get(i, f"dataset_{i}")
            ax.errorbar(arr[:, 0], arr[:, 1], yerr=arr[:, 2], fmt="o", label=label, capsize=1)
            print(f"  Dataset {i} ({label}): {arr.shape[0]} points")
        _apply_scales(ax, meta)
        _apply_labels(ax, meta)
        if labels:
            ax.legend()
        plt.show()

    else:
        # Line data — may have multiple datasets
        labels = meta.get("dataset_labels", {})
        data_lines = [line for line in text.splitlines() if not line.startswith("#")]
        data_text = "\n".join(data_lines)
        blocks = [b.strip() for b in data_text.split("\n\n") if b.strip()]
        fig, ax = plt.subplots()
        for i, block in enumerate(blocks):
            arr = np.loadtxt(block.splitlines())
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            label = labels.get(i, f"dataset_{i}")
            ax.plot(arr[:, 0], arr[:, 1], label=label)
        _apply_scales(ax, meta)
        _apply_labels(ax, meta)
        if labels:
            ax.legend()
        plt.show()

elif filename.endswith(".npz"):
    npz = np.load(filename, allow_pickle=True)
    print(f"Keys: {list(npz.keys())}")
    plot_type = str(npz.get("plot_type", "unknown"))
    print(f"Plot type: {plot_type}")

    fig, ax = plt.subplots()

    if plot_type in ("errorbar", "line"):
        n = int(npz["n_datasets"])
        for i in range(n):
            x, y = npz[f"x_{i}"], npz[f"y_{i}"]
            label = str(npz.get(f"label_{i}", f"dataset_{i}"))
            if f"error_{i}" in npz:
                ax.errorbar(x, y, yerr=npz[f"error_{i}"], fmt="o", label=label, capsize=1)
            else:
                ax.plot(x, y, label=label)
            print(f"  Dataset {i} ({label}): x={x.shape}, y={y.shape}")
        xscale = str(npz.get("xscale", "linear"))
        yscale = str(npz.get("yscale", "linear"))
        if xscale == "log":
            ax.set_xscale("log")
        if yscale == "log":
            ax.set_yscale("log")
        ax.legend()

    elif plot_type == "imshow":
        origin = str(npz.get("origin", "upper"))
        cmap = str(npz.get("cmap", "default"))
        norm_type = str(npz.get("norm", "Normalize"))
        vmin = float(npz["norm_vmin"]) if "norm_vmin" in npz else None
        vmax = float(npz["norm_vmax"]) if "norm_vmax" in npz else None
        norm = LogNorm(vmin=vmin, vmax=vmax) if norm_type == "LogNorm" else Normalize(vmin=vmin, vmax=vmax)
        ax.imshow(npz["data"], extent=npz["extent"], origin=origin, aspect="auto", cmap=cmap, norm=norm)
        print(f"  data shape: {npz['data'].shape}, origin: {origin}, norm: {norm_type}")

    elif plot_type == "pcolormesh":
        shading = str(npz.get("shading", "flat"))
        cmap = str(npz.get("cmap", "default"))
        norm_type = str(npz.get("norm", "Normalize"))
        vmin = float(npz["norm_vmin"]) if "norm_vmin" in npz else None
        vmax = float(npz["norm_vmax"]) if "norm_vmax" in npz else None
        norm = LogNorm(vmin=vmin, vmax=vmax) if norm_type == "LogNorm" else Normalize(vmin=vmin, vmax=vmax)
        n_surfaces = int(npz.get("n_surfaces", 1))
        for i in range(n_surfaces):
            z = npz[f"z_data_{i}"]
            if shading == "gouraud":
                ax.pcolormesh(npz[f"x_grid_{i}"], npz[f"y_grid_{i}"], z, shading="gouraud", cmap=cmap, norm=norm)
            else:
                ax.pcolormesh(npz[f"x_edges_{i}"], npz[f"y_edges_{i}"], z, cmap=cmap, norm=norm)
            print(f"  Surface {i}: z_data={z.shape}")
        print(f"  {n_surfaces} surface(s), shading: {shading}, norm: {norm_type}")

    ax.set_xlabel(str(npz.get("xlabel", "")))
    ax.set_ylabel(str(npz.get("ylabel", "")))
    ax.set_title(str(npz.get("title", "")))
    plt.show()

else:
    import pickle

    with open(filename, "rb") as f:
        pkl = pickle.load(f)

    if isinstance(pkl, dict) and "figure" in pkl:
        print(f"Plot type: {pkl['plot_type']}")
        fig = pkl["figure"]
    elif isinstance(pkl, tuple) and len(pkl) >= 3:
        print("Legacy pickle format (tuple)")
        fig = pkl[2]
    else:
        print(f"Unknown pickle structure: {type(pkl)}")
        sys.exit(1)

    show_figure(fig)
