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
        for key in ("xlabel", "ylabel", "title"):
            m = re.match(rf"{key}: (.+)", content)
            if m:
                meta[key] = m.group(1)
        # Dataset labels
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
        print(f"Imshow .dat: shape {raw.shape}, extent {extent}, origin {origin}, norm {type(norm).__name__}")
        fig, ax = plt.subplots()
        ax.imshow(raw, extent=extent, origin=origin, aspect="auto", cmap=cmap, norm=norm)
        _apply_labels(ax, meta)
        plt.show()

    elif raw.ndim == 2 and raw.shape[1] == 3:
        data_text = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        blocks = [b.strip() for b in data_text.split("\n\n") if b.strip()]
        if len(blocks) > 1:
            # Pcolormesh xyz
            shading = meta.get("shading", "flat")
            cmap = meta.get("cmap", "default")
            norm = _make_norm(meta)
            grid_m = re.search(r"grid: (\d+) (\d+)", text)
            fig, ax = plt.subplots()
            if shading == "gouraud" and grid_m:
                ny, nx = int(grid_m.group(1)), int(grid_m.group(2))
                X = raw[:, 0].reshape(ny, nx)
                Y = raw[:, 1].reshape(ny, nx)
                Z = raw[:, 2].reshape(ny, nx)
                print(f"Pcolormesh .dat (gouraud): grid {ny}x{nx}, norm {type(norm).__name__}")
                ax.pcolormesh(X, Y, Z, shading="gouraud", cmap=cmap, norm=norm)
            else:
                xs = np.unique(raw[:, 0])
                ys = np.unique(raw[:, 1])
                z = raw[:, 2].reshape(len(xs), len(ys)).T
                print(f"Pcolormesh .dat (flat): {len(xs)}x{len(ys)}, norm {type(norm).__name__}")
                ax.pcolormesh(xs, ys, z, cmap=cmap, norm=norm)
            _apply_labels(ax, meta)
            plt.show()
        else:
            # Errorbar data
            labels = meta.get("dataset_labels", {})
            print(f"Errorbar .dat: {raw.shape[0]} points")
            fig, ax = plt.subplots()
            ax.errorbar(raw[:, 0], raw[:, 1], yerr=raw[:, 2], fmt="o", label=labels.get(0, ""))
            xscale = meta.get("xscale", "linear")
            yscale = meta.get("yscale", "linear")
            if xscale == "log":
                ax.set_xscale("log")
            if yscale == "log":
                ax.set_yscale("log")
            _apply_labels(ax, meta)
            if labels:
                ax.legend()
            plt.show()
    else:
        # Line data
        print(f"Line .dat: shape {raw.shape}")
        fig, ax = plt.subplots()
        ax.plot(raw[:, 0], raw[:, 1])
        xscale = meta.get("xscale", "linear")
        yscale = meta.get("yscale", "linear")
        if xscale == "log":
            ax.set_xscale("log")
        if yscale == "log":
            ax.set_yscale("log")
        _apply_labels(ax, meta)
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
                ax.errorbar(x, y, yerr=npz[f"error_{i}"], fmt="o", label=label)
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
        z = npz["z_data"]
        if shading == "gouraud":
            ax.pcolormesh(npz["x_grid"], npz["y_grid"], z, shading="gouraud", cmap=cmap, norm=norm)
            print(f"  gouraud: x_grid={npz['x_grid'].shape}, norm: {norm_type}")
        else:
            ax.pcolormesh(npz["x_edges"], npz["y_edges"], z, cmap=cmap, norm=norm)
            print(f"  flat: x_edges={npz['x_edges'].shape}, norm: {norm_type}")
        print(f"  z_data shape: {z.shape}")

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
