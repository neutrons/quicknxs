#!/usr/bin/env python
"""Utility to display saved .pkl or .npz files from save_data().

Usage:
    python show.py [path-to-file]

Supports both the new dict-based pickle format and the legacy tuple format.
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


if filename.endswith(".npz"):
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
