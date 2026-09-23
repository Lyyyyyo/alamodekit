#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scph_dos.py
===========

Plot the SCPH temperature-dependent total phonon density of states (TDOS).

The data file's first comment line lists the temperatures; each subsequent
row is ``frequency  TDOS(T1)  TDOS(T2) ...``. A high-frequency all-zero tail
is auto-truncated. All visual settings (cmap, DPI, line width, output formats)
come from ``config/settings.yaml``.

Outputs
-------
    <base>_tdos   figure (png/pdf per settings)
"""
from __future__ import annotations

import os
import glob

import alamodekit_io
alamodekit_io.ensure_package_root()

import numpy as np
import matplotlib.pyplot as plt

from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_palette, apply_grid, get_cmap)
from alamodekit_config import get_plotting_config


FILE_PATTERN = "*scph*_dos*"
Y_AXIS_TOP_MARGIN = 0.05


def auto_select_file(pattern: str = FILE_PATTERN) -> str:
    """Find files matching ``pattern``; auto-pick if unique, else ask."""
    matches = sorted(f for f in glob.glob(pattern) if os.path.isfile(f))
    if not matches:
        raise FileNotFoundError(f"No file matching '{pattern}'.")
    if len(matches) == 1:
        print(f"Auto-selected unique match: {matches[0]}")
        return matches[0]
    print(f"Found {len(matches)} matching files:")
    for i, name in enumerate(matches, 1):
        print(f"   {i}. {name}")
    while True:
        try:
            choice = int(input("Select a file by number: ")) - 1
            if 0 <= choice < len(matches):
                return matches[choice]
        except ValueError:
            pass
        print(f"  -> enter a number from 1 to {len(matches)}.")


def read_tdos(path: str):
    """Read the TDOS file; returns frequencies, TDOS array, temperatures."""
    with open(path, 'r', encoding='utf-8') as handle:
        first_line = handle.readline().strip()
    if not first_line.startswith('#'):
        raise ValueError("Data format error: first line must start with '#'.")
    temps = np.array(first_line.replace('#', '').split(), dtype=float)
    data = np.atleast_2d(np.loadtxt(path, skiprows=1))
    expected = len(temps) + 1
    if data.shape[1] != expected:
        raise ValueError(f"Column mismatch: header defines {len(temps)} temps "
                         f"({expected} cols), data has {data.shape[1]} cols.")
    return data[:, 0], data[:, 1:], temps


def truncate_zero_tail(frequency, tdos):
    """Drop the high-frequency tail where TDOS is all zero."""
    non_zero = np.where(~np.all(tdos == 0, axis=1))[0]
    if non_zero.size == 0:
        raise ValueError("All TDOS values are zero; cannot plot.")
    last = non_zero[-1]
    return frequency[:last + 1], tdos[:last + 1]


def plot_tdos(path: str, frequency, tdos, temps) -> None:
    """Draw and save the TDOS curves coloured by temperature."""
    cfg = apply_plot_style()
    fig, ax = make_figure()
    lw = get_line_setting('linewidth', 1.5)
    alpha = get_line_setting('alpha', 1.0)

    # Use the configured sequential colormap (cycle through temperatures).
    cmap = get_cmap('sequential')
    colors = [cmap(i) for i in np.linspace(0, 1, len(temps))]
    for temp, color, col in zip(temps, colors, range(tdos.shape[1])):
        ax.plot(frequency, tdos[:, col], color=color, linewidth=lw,
                alpha=alpha, label=f"{int(temp)} K")

    units = cfg['plotting']['units']
    ax.set_xlabel(f"Frequency ({units['frequency']})")
    ax.set_ylabel("Total Phonon Density of States")
    ax.set_title(f"Phonon TDOS at different temperatures\n"
                 f"{os.path.splitext(path)[0]}",
                 fontsize=cfg['plotting']['font']['title_size'])
    ax.set_xlim(0, frequency.max())
    ax.set_ylim(0, tdos.max() * (1 + Y_AXIS_TOP_MARGIN))
    ax.legend(loc='best', fontsize=10, framealpha=0.9)
    apply_grid(ax)
    fig.tight_layout()
    save_figure(fig, f"{os.path.splitext(path)[0]}_tdos", cfg=cfg)
    plt.show()
    plt.close(fig)


def main():
    data_file = auto_select_file()
    frequency, tdos, temps = read_tdos(data_file)
    print(f"Detected {len(temps)} temperatures: {[int(t) for t in temps]} K")
    print(f"Original data: {len(frequency)} frequency points, "
          f"range {frequency.min():.1f} ~ {frequency.max():.1f} cm^-1")
    frequency, tdos = truncate_zero_tail(frequency, tdos)
    plot_tdos(data_file, frequency, tdos, temps)
    print("Plotting completed.")


if __name__ == '__main__':
    main()
