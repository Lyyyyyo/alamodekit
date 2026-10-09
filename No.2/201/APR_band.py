#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APR_band.py
===========

Process an ALAMODE atom-projected-resolved (APR) phonon band and plot the
dispersion coloured by the element-projected character of each mode.

Workflow
--------
1. Split ``<prefix>.bands`` into per-branch blocks and store as
   ``<prefix>.rebands``.
2. Read ``<prefix>.band.apr`` (columns: kpoint, mode, atom, APR) and pivot
   so each atom gets a column.
3. Merge the per-atom APR columns by element (user-supplied element order
   and atom counts) and normalise to a per-mode, per-k-point element ratio.
4. Draw the dispersion as a LineCollection whose segment colour is the
   element-weighted mix; render an adaptive color scale (2..6 elements).

All visual settings come from ``config/settings.yaml`` via :mod:`plot_style`:
the element palette, line width, DPI, output formats and axis units.
"""
from __future__ import annotations

import os
import sys
import re
from io import StringIO

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
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from matplotlib.path import Path

from alamodekit_io import prompt_prefix
from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_high_sym_line_style,
                        get_palette, apply_grid)
from alamodekit_config import get_plotting_config


# ---------------------------------------------------------------------------
# Step 1 + 2: data preparation.
# ---------------------------------------------------------------------------
def prepare_rebands(prefix: str) -> None:
    """Split ``<prefix>.bands`` into per-branch blocks -> ``.rebands``."""
    with open(f"{prefix}.bands", 'r', encoding='utf-8') as handle:
        lines = handle.readlines()
    header, data = lines[:3], lines[3:]
    n_cols = len(data[0].split())
    new_lines = []
    for col in range(1, n_cols):
        for line in data:
            tokens = line.split()
            new_lines.append(f"{tokens[0]} {tokens[col]}")
        new_lines.append("")
    with open(f"{prefix}.rebands", 'w', encoding='utf-8') as handle:
        handle.writelines(header)
        handle.write("\n".join(new_lines))


def load_apr_data(prefix: str):
    """Load ``.rebands`` (k, freq) and the pivoted ``.band.apr`` table."""
    with open(f"{prefix}.band.apr", 'r', encoding='utf-8') as handle:
        rows = [ln.split() for ln in handle if ln.strip() and not ln.startswith('#')]
    df = pd.DataFrame(rows, columns=['kpoint', 'mode', 'atom', 'APR'])
    df['kpoint'] = df['kpoint'].astype(int)
    df['mode'] = df['mode'].astype(int)
    df['APR'] = df['APR'].astype(float)
    grouped = (df.sort_values(['mode', 'kpoint'])
                 .groupby(['mode', 'kpoint'])['APR']
                 .apply(lambda s: s.reset_index(drop=True))
                 .unstack().add_prefix('APR_').reset_index())

    with open(f"{prefix}.rebands", 'r', encoding='utf-8') as handle:
        reb = [ln for ln in handle.readlines()
               if not ln.startswith('#') or ln.strip() == '\n']
    bands_df = pd.read_csv(StringIO(''.join(reb)), sep=' ', header=None)
    merged = pd.concat([bands_df, grouped], axis=1)
    return merged, grouped


def write_merged_table(merged, prefix: str) -> str:
    """Insert a blank row between successive modes and dump the table."""
    empty = pd.DataFrame([np.nan] * len(merged.columns)).T
    empty.columns = merged.columns
    result = pd.DataFrame(columns=merged.columns)
    for _, group in merged.groupby('mode'):
        result = pd.concat([result, group, empty], ignore_index=True)
    out_file = f"{prefix}_APR_projection.txt"
    result.to_csv(out_file, sep='\t', index=False, header=False)
    print(f"Data processing completed! Output file: {out_file}")
    return out_file


# ---------------------------------------------------------------------------
# Step 3: element information and ratio computation.
# ---------------------------------------------------------------------------
def ask_elements(n_atoms_total: int):
    """Prompt for element names and per-element atom counts."""
    while True:
        raw = input("\nEnter element order and atom counts "
                    "(e.g. Mo Te In 6 6 2): ").strip()
        parts = raw.split()
        if len(parts) % 2 != 0:
            print("  -> Error: element names and counts must come in pairs.")
            continue
        n = len(parts) // 2
        elements = parts[:n]
        counts = list(map(int, parts[n:]))
        if sum(counts) != n_atoms_total:
            print(f"  -> Error: data has {n_atoms_total} atoms, "
                  f"you entered {sum(counts)}.")
            continue
        return elements, counts


def compute_element_ratios(grouped, elements, counts):
    """Sum per-atom APR columns by element and normalise each row to 1."""
    ratios = []
    start = 2  # APR columns start after mode + kpoint.
    for count in counts:
        end = start + count
        ratios.append(grouped.iloc[:, start:end].sum(axis=1).values)
        start = end
    ratios = np.array(ratios).T
    total = ratios.sum(axis=1, keepdims=True)
    total[total == 0] = 1.0
    return ratios / total


# ---------------------------------------------------------------------------
# Step 4: figure (coloured dispersion + adaptive element scale).
# ---------------------------------------------------------------------------
def build_segments(merged, elem_ratios, elem_colors, elements):
    """Build LineCollection segments and per-segment element-mixed colours."""
    segments, colors = [], []
    for _, mode_data in merged.groupby('mode'):
        mode_data = mode_data.dropna()
        if len(mode_data) < 2:
            continue
        x = mode_data.iloc[:, 0].values
        y = mode_data.iloc[:, 1].values
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        seg = np.concatenate([points[:-1], points[1:]], axis=1)
        segments.extend(seg)
        idx = mode_data.index.values
        for i in range(len(seg)):
            avg = (elem_ratios[idx[i]] + elem_ratios[idx[i + 1]]) / 2.0
            color = np.zeros(3)
            for j, elem in enumerate(elements):
                color += avg[j] * np.array(elem_colors[elem])[:3]
            colors.append(color)
    return segments, colors


def draw_element_scale(cbar_ax, elements, elem_colors):
    """Draw the adaptive element color scale (supports 2..6 elements)."""
    cbar_ax.axis('off')
    n = len(elements)

    def _label(elem, x, y, ha, va):
        cbar_ax.text(x, y, elem, ha=ha, va=va,
                     color=elem_colors[elem], fontweight='bold', fontsize=12)

    if n == 2:
        xs = np.linspace(0, 1, 200)
        for i in range(len(xs) - 1):
            t = (xs[i] + xs[i + 1]) / 2
            col = (1 - t) * np.array(elem_colors[elements[0]][:3]) \
                  + t * np.array(elem_colors[elements[1]][:3])
            cbar_ax.fill_between([xs[i], xs[i + 1]], 0, 1, color=col, alpha=0.7)
        _label(elements[0], 0, -0.5, 'center', 'top')
        _label(elements[1], 1, -0.5, 'center', 'top')
        return

    if n == 3:
        vertices = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2]])
        cbar_ax.add_patch(Polygon(vertices, fill=False, edgecolor='black', linewidth=1.2))
        x = np.linspace(0, 1, 100); y = np.linspace(0, np.sqrt(3) / 2, 100)
        X, Y = np.meshgrid(x, y)
        mask = (Y <= np.sqrt(3) * X) & (Y <= -np.sqrt(3) * (X - 1))
        Xm, Ym = X[mask], Y[mask]
        r1 = np.maximum(1 - Xm - Ym / np.sqrt(3), 0)
        r2 = np.maximum(Xm - Ym / np.sqrt(3), 0)
        r3 = np.maximum(2 * Ym / np.sqrt(3), 0)
        cols = (r1[:, None] * np.array(elem_colors[elements[0]][:3])
                + r2[:, None] * np.array(elem_colors[elements[1]][:3])
                + r3[:, None] * np.array(elem_colors[elements[2]][:3]))
        cbar_ax.scatter(Xm, Ym, c=cols, s=2, edgecolors='none', alpha=0.7)
        _label(elements[0], 0, -0.08, 'center', 'top')
        _label(elements[1], 1, -0.08, 'center', 'top')
        _label(elements[2], 0.5, np.sqrt(3) / 2 + 0.08, 'center', 'bottom')
        return

    # n in {4, 5, 6}: regular polygon with inverse-distance-weighted vertices.
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if n == 5:
        angles = angles - np.pi / 2
    vertices = np.column_stack([0.5 + 0.45 * np.cos(angles),
                                0.5 + 0.45 * np.sin(angles)])
    cbar_ax.add_patch(Polygon(vertices, fill=False, edgecolor='black', linewidth=1.2))
    x = np.linspace(0, 1, 120); y = np.linspace(0, 1, 120)
    X, Y = np.meshgrid(x, y)
    mask = Path(vertices).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(X.shape)
    Xm, Ym = X[mask], Y[mask]
    r = np.zeros((len(Xm), n))
    for i in range(n):
        d = np.sqrt((Xm - vertices[i, 0]) ** 2 + (Ym - vertices[i, 1]) ** 2)
        d[d < 1e-6] = 1e-6
        r[:, i] = 1.0 / d ** 2
    r /= r.sum(axis=1, keepdims=True)
    cols = np.zeros((len(Xm), 3))
    for i in range(n):
        cols += r[:, i:i + 1] * np.array(elem_colors[elements[i]][:3])
    cbar_ax.scatter(Xm, Ym, c=cols, s=1.5, edgecolors='none', alpha=0.7)
    offsets = {4: [(0, -.08), (1, -.08), (1, 1.08), (0, 1.08)],
               5: [(0, .12), (.12, .04), (.08, -.1), (-.08, -.1), (-.12, .04)],
               6: [(.12, 0), (.06, .1), (-.06, .1), (-.12, 0), (-.06, -.1), (.06, -.1)]}
    for i, (dx, dy) in enumerate(offsets.get(n, [])):
        _label(elements[i], vertices[i, 0] + dx, vertices[i, 1] + dy, 'center', 'center')


def plot_apr_dispersion(merged, elem_ratios, elements, counts,
                        tick_values, tick_labels, prefix: str) -> None:
    """Draw and save the element-projected dispersion."""
    cfg = apply_plot_style()
    palette = get_palette()
    elem_colors = {elem: palette[i] for i, elem in enumerate(elements)}
    print("\nElement color mapping:")
    for elem, col in elem_colors.items():
        print(f"  {elem}: {col}")

    segments, seg_colors = build_segments(merged, elem_ratios,
                                          elem_colors, elements)

    fig, ax = make_figure()
    lw = get_line_setting('band_linewidth', get_line_setting('linewidth', 2.0))
    alpha = get_line_setting('alpha', 0.9)
    lc = LineCollection(segments, colors=seg_colors, linewidth=lw, alpha=alpha)
    ax.add_collection(lc)

    for x in tick_values:
        ax.axvline(x=x, **get_high_sym_line_style())
    ax.set_xlim(0, max(tick_values) if tick_values else 1)
    freq = merged.iloc[:, 1].values
    ax.set_ylim(freq.min() * 1.05, freq.max() * 1.05)
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)

    units = cfg['plotting']['units']
    ax.set_ylabel(f"Frequency ({units['frequency']})")
    apply_grid(ax)

    # Adaptive color scale (supports 2..6 elements; warned otherwise).
    n = len(elements)
    if 2 <= n <= 6:
        print(f"\nGenerating color scale for {n} elements...")
        box = [0.72, 0.68, 0.22, 0.22] if n <= 4 else [0.70, 0.65, 0.26, 0.26]
        cbar_ax = ax.inset_axes(box)
        draw_element_scale(cbar_ax, elements, elem_colors)
    else:
        print(f"\nWarning: color scale for {n} elements is not supported "
              f"(this script supports 2..6 elements).")

    fig.tight_layout()
    save_figure(fig, f"{prefix}_element_projection_phonon", cfg=cfg)
    plt.show()
    plt.close(fig)


def main():
    prefix = prompt_prefix()
    prepare_rebands(prefix)
    merged, grouped = load_apr_data(prefix)
    write_merged_table(merged, prefix)

    # Plot the element-projected phonon dispersion automatically.
    # High-symmetry ticks from the .bands header.
    with open(f"{prefix}.bands", 'r', encoding='utf-8') as handle:
        head = handle.readlines()[:2]
    names, values = alamodekit_io.parse_high_symmetry_header(head)
    tick_values, tick_labels = alamodekit_io.merge_high_symmetry_points(names, values)

    n_atoms = len(grouped.columns) - 2
    elements, counts = ask_elements(n_atoms)
    print("\nElement information:")
    for elem, count in zip(elements, counts):
        print(f"  {elem}: {count} atoms")

    ratios = compute_element_ratios(grouped, elements, counts)
    plot_apr_dispersion(merged, ratios, elements, counts,
                        tick_values, tick_labels, prefix)


if __name__ == '__main__':
    main()
