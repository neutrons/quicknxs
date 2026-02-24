#!/usr/bin/env python
"""Utility to display saved .pkl, .npz, or .dat files from save_data().

Usage:
    python show.py [path-to-file]

Supports .dat (gnuplot xyz for pcolormesh, columnar for others),
.npz (compressed numpy archive), and .pkl (pickle with full figure).
"""

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


if filename.endswith(".dat"):
    # Detect gnuplot xyz format (pcolormesh) vs columnar (errorbar/line/imshow)
    raw = np.loadtxt(filename)
    text = open(filename).read()
    blocks = [b.strip() for b in text.split("\n\n") if b.strip() and not b.strip().startswith("#")]
    if raw.shape[1] == 3 and len(blocks) > 1:
        # Gnuplot xyz: reconstruct 2D grid
        xs = np.unique(raw[:, 0])
        ys = np.unique(raw[:, 1])
        z = raw[:, 2].reshape(len(xs), len(ys)).T
        print(f"Pcolormesh .dat: {len(xs)} x-centers, {len(ys)} y-centers, z shape {z.shape}")
        fig, ax = plt.subplots()
        ax.pcolormesh(xs, ys, z)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        plt.show()
    else:
        print(f"Columnar .dat: shape {raw.shape}")
        fig, ax = plt.subplots()
        if raw.shape[1] >= 3:
            ax.errorbar(raw[:, 0], raw[:, 1], yerr=raw[:, 2], fmt="o")
        else:
            ax.plot(raw[:, 0], raw[:, 1])
        plt.show()

elif filename.endswith(".npz"):
    npz = np.load(filename, allow_pickle=True)
    print(f"Keys: {list(npz.keys())}")
    plot_type = str(npz.get("plot_type", "unknown"))
    print(f"Plot type: {plot_type}")

    if plot_type in ("errorbar", "line"):
        n = int(npz["n_datasets"])
        for i in range(n):
            print(f"  Dataset {i}: x={npz[f'x_{i}'].shape}, y={npz[f'y_{i}'].shape}")
    elif plot_type == "imshow":
        print(f"  data shape: {npz['data'].shape}, extent: {npz['extent']}")
    elif plot_type == "pcolormesh":
        print(f"  z_data shape: {npz['z_data'].shape}")
        print(f"  x_edges: {npz['x_edges'].shape}, y_edges: {npz['y_edges'].shape}")

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
