#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gru_band.py
===========

Combine a ``*.gruneisen`` file with the corresponding ``*.bands`` file and
plot the phonon dispersion coloured by the Gruneisen parameter.

The Gruneisen parameter is a diverging quantity (positive / negative around
zero), so the figure uses a dark-blue -> white (at zero) -> dark-red colormap
whose white anchor is placed exactly at gamma = 0. The colormap, line width,
DPI, colorbar style, axis units and output formats are all read from
``config/settings.yaml``.

Inputs
------
    <prefix>.gruneisen   kpoint + Gruneisen parameter per branch
    <prefix>.bands       kpoint + frequency per branch (also supplies the
                         high-symmetry path header)

Outputs
-------
    phonon_gruneisen_combined.txt          merged k / freq / gamma data
    phonon_gruneisen_projected_dispersion  figure (png/pdf per settings)
"""
from __future__ import annotations

import os
import re

import alamodekit_io
alamodekit_io.ensure_package_root()

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

from alamodekit_io import prompt_prefix
from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_high_sym_line_style,
                        add_colorbar, apply_grid, get_cmap)
from alamodekit_config import get_plotting_config


def read_gruneisen(filename: str):
    """Read ``.gruneisen``: col 0 = k-point, rest = gamma per branch."""
    data = np.atleast_2d(np.loadtxt(filename, skiprows=1))
    return data[:, 0], data[:, 1:]


def read_bands(filename: str):
    """Read ``.bands`` and return k, freq, and merged high-sym ticks."""
    with open(filename, 'r', encoding='utf-8') as handle:
        lines = handle.readlines()
    names, values = alamodekit_io.parse_high_symmetry_header(lines[:2])
    tick_values, tick_labels = alamodekit_io.merge_high_symmetry_points(names, values)
    data = np.atleast_2d(np.loadtxt(lines[3:]))
    return data[:, 0], data[:, 1:], tick_values, tick_labels


def combine_and_save(k_gamma, gamma, k_freq, freq, out_file: str):
    """Validate consistency and save the merged k / freq / gamma table."""
    if len(k_gamma) != len(k_freq):
        raise ValueError("k-point count mismatch between .gruneisen and .bands")
    if gamma.shape[1] != freq.shape[1]:
        raise ValueError("branch count mismatch between .gruneisen and .bands")
    if not np.allclose(k_gamma, k_freq, atol=1e-6):
        print("  Warning: k-point coordinates differ slightly (numerical noise).")

    nk, nb = gamma.shape
    combined = np.zeros((nk * nb, 3))
    row = 0
    for i in range(nk):
        for j in range(nb):
            combined[row] = [k_gamma[i], freq[i, j], gamma[i, j]]
            row += 1
    np.savetxt(out_file, combined, fmt="%.8f  %.8f  %.8f",
               header="k-point  frequency(cm-1)  gruneisen_parameter")
    print(f"Output file saved as: {out_file}")
    print(f"Frequency range: {freq.min():.2f} ~ {freq.max():.2f} cm^-1")
    print(f"Gruneisen range: {gamma.min():.4f} ~ {gamma.max():.4f}")
    return combined, nk, nb


def _segments_with_colors(x, y, c):
    """Build LineCollection segments; each segment coloured by midpoint c."""
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    return segments, (c[:-1] + c[1:]) / 2.0


def plot_gruneisen(combined, nk, nb, tick_values, tick_labels, out_base: str):
    """Draw the Gruneisen-projected dispersion with a 0-anchored colormap."""
    cfg = apply_plot_style()
    k = combined[:, 0].reshape(nk, nb)
    freq = combined[:, 1].reshape(nk, nb)
    gamma = combined[:, 2].reshape(nk, nb)

    all_segments, all_colors = [], []
    for b in range(nb):
        seg, col = _segments_with_colors(k[:, b], freq[:, b], gamma[:, b])
        all_segments.extend(seg)
        all_colors.extend(col)
    all_colors = np.array(all_colors)

    # Range: union of raw points and segment midpoints, extended by 0.5% so
    # boundary values get a real colour instead of the over/under fallback.
    raw_min, raw_max = gamma.min(), gamma.max()
    seg_min, seg_max = all_colors.min(), all_colors.max()
    g_min = min(raw_min, seg_min)
    g_max = max(raw_max, seg_max)
    pad = (g_max - g_min) * 0.005
    g_min -= pad
    g_max += pad
    zero_frac = (0.0 - g_min) / (g_max - g_min)

    # The custom diverging colormap places white exactly at gamma = 0.
    cmap = get_cmap('gruneisen', zero_fraction=zero_frac)

    fig, ax = make_figure()
    lw = get_line_setting('band_linewidth', get_line_setting('linewidth', 1.2))
    alpha = get_line_setting('alpha', 1.0)
    lc = LineCollection(all_segments, cmap=cmap, linewidth=lw, alpha=alpha,
                        antialiased=True)
    lc.set_array(all_colors)
    lc.set_clim(g_min, g_max)
    ax.add_collection(lc)

    for x in tick_values:
        ax.axvline(x=x, **get_high_sym_line_style())
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)
    ax.set_xlim(tick_values[0], tick_values[-1])
    y_min = freq.min() * 1.05 if freq.min() < 0 else 0
    ax.set_ylim(y_min, freq.max() * 1.05)

    units = cfg['plotting']['units']
    ax.set_ylabel(f"Frequency ({units['frequency']})")
    apply_grid(ax)

    # Colorbar with rounded ticks spanning the raw data range.
    sm = ScalarMappable(cmap=cmap, norm=Normalize(vmin=g_min, vmax=g_max))
    sm.set_array([])
    cbar = add_colorbar(sm, ax, label="Gruneisen Parameter")
    if cbar is not None:
        step = 2.0 if (raw_max - raw_min) < 10 else \
               (5.0 if (raw_max - raw_min) < 20 else 10.0)
        start = np.ceil(raw_min / step) * step
        ticks = np.arange(start, raw_max + step, step)
        if ticks.size and not np.isclose(ticks[0], raw_min, atol=0.1):
            ticks = np.insert(ticks, 0, np.round(raw_min, 1))
        if ticks.size and not np.isclose(ticks[-1], raw_max, atol=0.1):
            ticks = np.append(ticks, np.round(raw_max, 1))
        cbar.set_ticks(ticks)

    fig.tight_layout()
    save_figure(fig, out_base, cfg=cfg)
    plt.show()
    plt.close(fig)


def main():
    prefix = prompt_prefix()
    gruneisen_file = f"{prefix}.gruneisen"
    bands_file = f"{prefix}.bands"
    for path in (gruneisen_file, bands_file):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Error: file '{path}' not found.")

    k_gamma, gamma = read_gruneisen(gruneisen_file)
    k_freq, freq, tick_values, tick_labels = read_bands(bands_file)
    out_file = f"{prefix}_gruneisen_combined.txt"
    combined, nk, nb = combine_and_save(k_gamma, gamma, k_freq, freq, out_file)

    if alamodekit_io.ask_yes_no(
            "Plot the Gruneisen-parameter-projected dispersion?"):
        plot_gruneisen(combined, nk, nb, tick_values, tick_labels,
                       f"{prefix}_gruneisen_projected_dispersion")
    print("\nAll operations completed!")


if __name__ == '__main__':
    main()
