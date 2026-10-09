#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_harband.py
===============

Plot the harmonic phonon dispersion from an ALAMODE ``*.bands`` file.

This is the refactored version of the toolkit's band plotter. All visual
parameters (figure size, DPI, line width, colors, high-symmetry guide line
style, output formats, axis units, ...) are read from ``config/settings.yaml``
through :mod:`plot_style`, so the figure appearance is consistent across the
whole toolkit and fully user-adjustable without editing code.

Usage
-----
    python plot_harband.py                # auto-detect a single .bands file
    python plot_harband.py SnSeS.bands    # explicit file
"""
from __future__ import annotations

import os
import sys

# --- Make the toolkit package importable when run as a standalone script. --
# --- Bootstrap: make the toolkit root importable when run as a script. ---
# When this file is executed directly, sys.path[0] is this script's own
# folder (No.X/<submenu>/), which does NOT contain the toolkit modules.
# Add the package root (two levels up) to sys.path *before* importing
# anything toolkit-level. Harmless when imported as a package module.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402

import numpy as np
import matplotlib.pyplot as plt

from alamodekit_io import (read_bands_file, compound_name_from_filename)
from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_color, get_high_sym_line_style,
                        apply_grid)
from alamodekit_config import get_plotting_config


def plot_phonon_dispersion(filename: str) -> bool:
    """Read ``filename`` and draw/save the harmonic phonon dispersion.

    Parameters
    ----------
    filename : str
        Path to a ``*.bands`` file produced by ANPHON.

    Returns
    -------
    bool
        True if the figure was produced, False on read/parse failure.
    """
    if not os.path.isfile(filename):
        print(f"Error: file '{filename}' not found.")
        return False

    cfg = apply_plot_style()
    try:
        kpoints, frequencies, tick_values, tick_labels = read_bands_file(filename)
    except Exception as exc:
        print(f"Error while parsing '{filename}': {exc}")
        return False

    if frequencies.size == 0:
        print("Error: no valid phonon data found in the file.")
        return False

    # Compound name (used only for the saved-file prefix / title).
    compound = compound_name_from_filename(filename)

    fig, ax = make_figure()
    color = get_color('primary')
    lw = get_line_setting('band_linewidth', get_line_setting('linewidth', 1.5))
    alpha = get_line_setting('alpha', 1.0)

    # One curve per phonon branch.
    for branch in range(frequencies.shape[1]):
        ax.plot(kpoints, frequencies[:, branch], color=color,
                linewidth=lw, alpha=alpha)

    # High-symmetry-point vertical guide lines.
    for x in tick_values:
        ax.axvline(x=x, **get_high_sym_line_style())

    # Axis ranges and ticks.
    ax.set_xlim(0, max(tick_values) if tick_values else kpoints.max())
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)

    y_min, y_max = frequencies.min(), frequencies.max()
    pad = (y_max - y_min) * 0.05 if y_max > y_min else 1.0
    ax.set_ylim(y_min - pad, y_max + pad)

    units = cfg['plotting']['units']
    ax.set_ylabel(f"Frequency ({units['frequency']})")
    ax.set_title(f"{compound} harmonic",
                 fontsize=cfg['plotting']['font']['title_size'])
    apply_grid(ax)
    fig.tight_layout()

    out_base = f"{os.path.splitext(filename)[0]}_phonon_dispersion"
    save_figure(fig, out_base, cfg=cfg)
    plt.show()
    plt.close(fig)
    return True


def find_bands_files() -> list:
    """Return all ``*.bands`` files in the current directory, sorted."""
    return sorted(f for f in os.listdir('.')
                  if f.endswith('.bands') and os.path.isfile(f))


def select_file(bands_files: list) -> str:
    """Let the user pick one file from ``bands_files`` by index."""
    print("\nFound the following .bands files:")
    for idx, name in enumerate(bands_files, 1):
        print(f"   {idx}. {name}")
    while True:
        raw = input("\nSelect a file by number (q to quit): ").strip().lower()
        if raw == 'q':
            return ''
        try:
            choice = int(raw) - 1
            if 0 <= choice < len(bands_files):
                return bands_files[choice]
        except ValueError:
            pass
        print(f"  -> enter a number from 1 to {len(bands_files)}.")


def main():
    bands_files = find_bands_files()
    if not bands_files:
        print("No .bands file found in the current directory.")
        if len(sys.argv) == 2:
            print(f"Trying the command-line argument: {sys.argv[1]}")
            plot_phonon_dispersion(sys.argv[1])
        else:
            print(f"Usage: python {os.path.basename(__file__)} <file.bands>")
        return

    # A single file is plotted directly; multiple files prompt for a choice.
    if len(bands_files) == 1:
        selected = bands_files[0]
        print(f"\nSingle .bands file detected, plotting: {selected}")
    else:
        selected = select_file(bands_files)
    if selected:
        plot_phonon_dispersion(selected)


if __name__ == '__main__':
    main()
