#!/usr/bin/env python
"""Utility to display saved .pkl, .npz, or .dat files from save_data().

Usage:
    python show.py [path-to-file]

Supports .dat (gnuplot xyz for pcolormesh, imshow 2D array, columnar for others),
.npz (compressed numpy archive), and .pkl (pickle with full figure).
"""

import re
import sys

import matplotlib.pyplot as plt
import numpy as np

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
        # extent line
        m = re.match(
            r"extent: xmin=([\d.e+-]+), xmax=([\d.e+-]+), "
            r"ymin=([\d.e+-]+), ymax=([\d.e+-]+)",
            content,
        )
        if m:
            meta["extent"] = [float(m.group(i)) for i in range(1, 5)]
        # origin line
        m = re.match(r"origin: (\w+)", content)
        if m:
            meta["origin"] = m.group(1)
        # shading line
        m = re.match(r"shading: (\w+)", content)
        if m:
            meta["shading"] = m.group(1)
        # xlabel / ylabel
        m = re.match(r"xlabel: (.+)", content)
        if m:
            meta["xlabel"] = m.group(1)
        m = re.match(r"ylabel: (.+)", content)
        if m:
            meta["ylabel"] = m.group(1)
        m = re.match(r"title: (.+)", content)
        if m:
            meta["title"] = m.group(1)
    return meta


if filename.endswith(".dat"):
    text = open(filename).read()
    meta = _parse_dat_header(text)
    raw = np.loadtxt(filename)

    if "extent" in meta:
        # Imshow format: 2D array with extent header
        extent = meta["extent"]
        origin = meta.get("origin", "upper")
        print(f"Imshow .dat: shape {raw.shape}, extent {extent}, origin {origin}")
        fig, ax = plt.subplots()
        ax.imshow(raw, extent=extent, origin=origin, aspect="auto")
        ax.set_xlabel(meta.get("xlabel", ""))
        ax.set_ylabel(meta.get("ylabel", ""))
        ax.set_title(meta.get("title", ""))
        plt.show()

    elif raw.ndim == 2 and raw.shape[1] == 3:
        # Check for gnuplot xyz blocks (blank-line separated)
        data_text = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
        blocks = [b.strip() for b in data_text.split("\n\n") if b.strip()]
        if len(blocks) > 1:
            # Gnuplot xyz: reconstruct pcolormesh
            shading = meta.get("shading", "flat")
            # Parse grid dimensions from header
            grid_m = re.search(r"grid: (\d+) (\d+)", text)
            fig, ax = plt.subplots()
            if shading == "gouraud" and grid_m:
                ny, nx = int(grid_m.group(1)), int(grid_m.group(2))
                X = raw[:, 0].reshape(ny, nx)
                Y = raw[:, 1].reshape(ny, nx)
                Z = raw[:, 2].reshape(ny, nx)
                print(f"Pcolormesh .dat (gouraud): grid {ny}x{nx}")
                ax.pcolormesh(X, Y, Z, shading="gouraud")
            else:
                xs = np.unique(raw[:, 0])
                ys = np.unique(raw[:, 1])
                z = raw[:, 2].reshape(len(xs), len(ys)).T
                print(f"Pcolormesh .dat (flat): {len(xs)} x-centers, {len(ys)} y-centers")
                ax.pcolormesh(xs, ys, z)
            ax.set_xlabel(meta.get("xlabel", "X"))
            ax.set_ylabel(meta.get("ylabel", "Y"))
            ax.set_title(meta.get("title", ""))
            plt.show()
        else:
            # 3-column errorbar data
            print(f"Errorbar .dat: {raw.shape[0]} points")
            fig, ax = plt.subplots()
            ax.errorbar(raw[:, 0], raw[:, 1], yerr=raw[:, 2], fmt="o")
            plt.show()
    else:
        # 2-column line data
        print(f"Line .dat: shape {raw.shape}")
        fig, ax = plt.subplots()
        ax.plot(raw[:, 0], raw[:, 1])
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
        ax.legend()

    elif plot_type == "imshow":
        origin = str(npz.get("origin", "upper"))
        ax.imshow(npz["data"], extent=npz["extent"], origin=origin, aspect="auto")
        print(f"  data shape: {npz['data'].shape}, extent: {npz['extent']}, origin: {origin}")

    elif plot_type == "pcolormesh":
        shading = str(npz.get("shading", "flat"))
        z = npz["z_data"]
        if shading == "gouraud":
            ax.pcolormesh(npz["x_grid"], npz["y_grid"], z, shading="gouraud")
            print(f"  gouraud: x_grid={npz['x_grid'].shape}, y_grid={npz['y_grid'].shape}")
        else:
            ax.pcolormesh(npz["x_edges"], npz["y_edges"], z)
            print(f"  flat: x_edges={npz['x_edges'].shape}, y_edges={npz['y_edges'].shape}")
        print(f"  z_data shape: {z.shape}")

    ax.set_xlabel(str(npz.get("xlabel", "")))
    ax.set_ylabel(str(npz.get("ylabel", "")))
    ax.set_title(str(npz.get("title", "")))
    plt.show()

else:
    import pickle

    with open(filename, "rb") as f:
        pkl = pickle.load(f)

    # New format: dict with 'figure', 'plot_type', 'data' keys
    # Legacy format: tuple (ax, data_to_save, figure)
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
