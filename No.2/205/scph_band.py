#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scph_band.py
============

Process an SCPH temperature-dependent phonon band file (``*scph*_bands``)
and plot the dispersion with curves coloured by temperature.

The data file lists, per line: temperature, k-point, then the frequency of
every phonon branch. Curves for different temperatures are overlaid and
coloured using the temperature colormap declared in ``settings.yaml``.

Outputs
-------
    <prefix>_merged_output.txt   merged data table
    <prefix>_phonon_dispersion   figure (png/pdf per settings)
"""
from __future__ import annotations

import os
import sys
import re
import glob

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
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_high_sym_line_style,
                        add_colorbar, apply_grid, get_cmap)
from alamodekit_config import get_plotting_config


def auto_select_file(pattern: str = "*scph*_bands") -> str:
    """Find files matching ``pattern``; auto-pick if unique, else ask."""
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"No file matching '{pattern}' in the current directory.")
    if len(matches) == 1:
        print(f"Auto-selected unique match: {matches[0]}")
        return matches[0]
    print(f"Found {len(matches)} matching files:")
    for i, name in enumerate(matches, 1):
        print(f"  [{i}] {name}")
    while True:
        try:
            choice = int(input("Select a file by number: ")) - 1
            if 0 <= choice < len(matches):
                return matches[choice]
        except ValueError:
            pass
        print(f"  -> enter a number from 1 to {len(matches)}.")


def parse_scph_bands(path: str):
    """Parse the SCPH band file into per-temperature k / freq arrays.

    Returns
    -------
    k_array : np.ndarray (nk,)
    freq_array : np.ndarray (nt, nk, n_bands)
    temps : list[float]
    tick_values, tick_labels : high-symmetry ticks
    """
    with open(path, 'r', encoding='utf-8') as handle:
        lines = handle.readlines()

    # High-symmetry header (G -> Gamma), shared convention with .bands.
    names, values = [], []
    if lines and lines[0].startswith('#'):
        names = re.split(r'\s+', lines[0].strip().lstrip('#').strip())
        names = [n.replace('G', '\u0393') for n in names]
    if len(lines) > 1 and lines[1].startswith('#'):
        values = [float(x) for x in re.split(r'\s+', lines[1].strip().lstrip('#').strip())]
    tick_values, tick_labels = alamodekit_io.merge_high_symmetry_points(names, values)

    # Group data rows by temperature.
    groups: dict = {}
    for line in lines[3:]:
        line = line.strip()
        if not line:
            continue
        tokens = re.split(r'\s+', line)
        try:
            temp = float(tokens[0])
            k = float(tokens[1])
            freqs = [float(x) for x in tokens[2:]]
        except (ValueError, IndexError):
            continue
        groups.setdefault(temp, {'k': [], 'freqs': []})
        groups[temp]['k'].append(k)
        groups[temp]['freqs'].append(freqs)

    temps = sorted(groups.keys())
    k_array = np.array(groups[temps[0]]['k'])
    n_k = len(k_array)
    n_bands = len(groups[temps[0]]['freqs'][0])
    freq_array = np.zeros((len(temps), n_k, n_bands))
    for i, temp in enumerate(temps):
        freq_array[i] = np.array(groups[temp]['freqs'])
    return k_array, freq_array, temps, tick_values, tick_labels


def write_merged_output(path: str, k_array, freq_array, temps) -> str:
    """Write the merged (temperature, k, freq) table for all branches."""
    out_file = f"{os.path.splitext(path)[0]}_merged_output.txt"
    nt, nk, nb = freq_array.shape
    with open(out_file, 'w', encoding='utf-8') as handle:
        header = []
        for temp in temps:
            header += [f"T={temp}K", "k", "freq(cm-1)"]
        handle.write(" ".join(header) + "\n")
        for k in range(nk):
            row = []
            for t in range(nt):
                for b in range(nb):
                    row += [f"{temps[t]:.1f}", f"{k_array[k]:.6f}",
                            f"{freq_array[t, k, b]:.6f}"]
            handle.write(" ".join(row) + "\n")
    return out_file


def plot_scph_bands(path: str, k_array, freq_array, temps,
                    tick_values, tick_labels) -> None:
    """Draw the temperature-coloured dispersion."""
    cfg = apply_plot_style()
    fig, ax = make_figure()
    lw = get_line_setting('band_linewidth', get_line_setting('linewidth', 1.2))
    alpha = get_line_setting('alpha', 0.8)
    cmap = get_cmap('temperature')
    norm = Normalize(vmin=min(temps), vmax=max(temps))
    nt, nk, nb = freq_array.shape

    for b in range(nb):
        for t in range(nt):
            y = freq_array[t, :, b].copy()
            points = np.column_stack([k_array, y]).reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            lc = LineCollection(segments, cmap=cmap, norm=norm,
                                linewidth=lw, alpha=alpha)
            lc.set_array(np.array([temps[t]]))
            ax.add_collection(lc)

    for x in tick_values:
        ax.axvline(x=x, **get_high_sym_line_style())
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)

    units = cfg['plotting']['units']
    ax.set_ylabel(f"Phonon Frequency ({units['frequency']})")
    ax.axhline(y=0, color='black', linewidth=1)
    ax.set_ylim(freq_array.min() - 10, freq_array.max() + 10)
    ax.set_xlim(min(tick_values) if tick_values else k_array.min(),
                max(tick_values) if tick_values else k_array.max())
    apply_grid(ax)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    add_colorbar(sm, ax, label="Temperature (K)")
    fig.tight_layout()
    save_figure(fig, f"{os.path.splitext(path)[0]}_phonon_dispersion", cfg=cfg)
    plt.show()
    plt.close(fig)


def main():
    input_file = auto_select_file()
    k_array, freq_array, temps, tick_values, tick_labels = parse_scph_bands(input_file)
    out_file = write_merged_output(input_file, k_array, freq_array, temps)
    print(f"Data processed: {len(temps)} temperatures, {len(k_array)} k-points, "
          f"{freq_array.shape[2]} branches")
    print(f"Merged data saved to {out_file}")
    plot_scph_bands(input_file, k_array, freq_array, temps, tick_values, tick_labels)
    print("Plotting completed.")


if __name__ == '__main__':
    main()
