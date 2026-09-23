#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_analyze_phonons.py
======================

Plotting companion for the ``analyze_phonons`` wrapper.

The ALAMODE ``analyze_phonons`` C++ analyzer prints text results whose layout
depends on the requested ``calc`` mode. This module parses each layout and
produces a publication-quality figure, reading every visual parameter (DPI,
line width, colors, colormap, colorbar style, ...) from ``config/settings.yaml``
via :mod:`plot_style`.

Supported layouts
-----------------
tau          : columns  ik, is, Frequency, Lifetime, |Velocity|, MFP,
               Multiplicity, kappa(3x3)  -> scatter Lifetime vs Frequency
tau_temp     : columns  Temperature, Lifetime, MFP           -> vs Temperature
kappa        : columns  Temperature, kappa(3x3) tensor       -> vs Temperature
cumulative   : columns  L, kappa(3x3)                        -> vs L
cumulative2  : same as cumulative, directional variant       -> vs L
kappa_boundary : columns  Temperature, kappa(3x3)            -> vs Temperature

All plots are saved in the formats listed in settings.yaml (png + pdf by
default) at the configured DPI.
"""
from __future__ import annotations

import os
import sys
import re
import numpy as np
import matplotlib.pyplot as plt

# Make the package root importable when this script runs standalone.
_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from plot_style import (apply_plot_style, save_figure, get_palette,
                        get_color, get_line_setting, add_colorbar,
                        apply_grid, make_figure)

# ---------------------------------------------------------------------------
# Generic text parser.
# ---------------------------------------------------------------------------
_HEADER_COMMENT_RE = re.compile(r'^\s*#')


def parse_columns(path: str) -> tuple:
    """Parse a tab/space-separated result file into a 2-D float array.

    Lines starting with ``#`` are skipped. Returns (data, header_lines)
    where ``header_lines`` is the list of comment lines (useful for titles
    and metadata such as temperature, mode range, etc.).
    """
    header_lines = []
    rows = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            if _HEADER_COMMENT_RE.match(line):
                header_lines.append(line.lstrip('#').strip())
                continue
            tokens = line.split()
            try:
                rows.append([float(tok) for tok in tokens])
            except ValueError:
                # Non-numeric line; treat as a header continuation.
                header_lines.append(line.strip())
    data = np.array(rows, dtype=float) if rows else np.empty((0, 0))
    return data, header_lines


def _extract_kv(headers, key):
    """Pull a value following 'key' from the comment header lines."""
    for line in headers:
        if key in line:
            # Take the first numeric token after the key word.
            idx = line.find(key) + len(key)
            for tok in line[idx:].split():
                try:
                    return float(tok)
                except ValueError:
                    continue
    return None


# ---------------------------------------------------------------------------
# Individual plotting routines.
# ---------------------------------------------------------------------------
def plot_tau(data: np.ndarray, headers, out_path: str, cfg: dict) -> str:
    """Scatter Lifetime (ps) vs Frequency (cm^-1), colored by |v|."""
    if data.size == 0 or data.shape[1] < 5:
        print("  (tau) not enough columns to plot.")
        return ''
    freq = data[:, 2]
    lifetime = data[:, 3]
    velocity = np.abs(data[:, 4])

    fig, ax = make_figure()
    lw = get_line_setting('linewidth', 1.2)
    # Color points by group velocity magnitude using the velocity colormap.
    cmap = __import__('plot_style').get_cmap('velocity')
    sc = ax.scatter(freq, lifetime, c=velocity, cmap=cmap,
                    s=20, alpha=0.8, edgecolors='none')
    units = cfg['plotting']['units']
    ax.set_xlabel(f"Frequency ({units['frequency']})")
    ax.set_ylabel(f"Lifetime ({units['lifetime']})")
    ax.set_yscale('log')
    ax.set_title("Phonon lifetime vs frequency", fontsize=cfg['plotting']['font']['title_size'])
    add_colorbar(sc, ax, label="|Velocity| (m/s)")
    apply_grid(ax)
    fig.tight_layout()
    return _save(fig, out_path, '_tau')


def plot_tau_temp(data: np.ndarray, headers, out_path: str, cfg: dict) -> str:
    """Lifetime & MFP vs temperature for one (k, mode)."""
    if data.size == 0 or data.shape[1] < 3:
        print("  (tau_temp) not enough columns to plot.")
        return ''
    temp = data[:, 0]
    lifetime = data[:, 1]
    mfp = data[:, 2]

    fig, ax = make_figure()
    lw = get_line_setting('linewidth', 1.2)
    primary = get_color('primary')
    secondary = get_color('secondary')
    ax.plot(temp, lifetime, '-o', color=primary, linewidth=lw,
            markersize=4, label="Lifetime")
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel(f"Lifetime ({cfg['plotting']['units']['lifetime']})",
                  color=primary)
    ax.tick_params(axis='y', labelcolor=primary)

    ax2 = ax.twinx()
    ax2.plot(temp, mfp, '-s', color=secondary, linewidth=lw,
             markersize=4, label="MFP")
    ax2.set_ylabel(f"MFP ({cfg['plotting']['units']['length']})",
                   color=secondary)
    ax2.tick_params(axis='y', labelcolor=secondary)

    ax.set_title("Temperature dependence of lifetime / MFP")
    fig.tight_layout()
    return _save(fig, out_path, '_tau_temp')


def _plot_kappa_series(data: np.ndarray, headers, out_path: str, cfg: dict,
                       x_label: str, x_col: int, tag: str, title: str) -> str:
    """Generic helper for kappa / cumulative / kappa_boundary layouts.

    The leading column (x_col) is the abscissa; the next 9 columns are the
    3x3 kappa tensor (xx, xy, xz, yx, yy, yz, zx, zy, zz). We plot the three
    diagonal components (xx, yy, zz) and their average.
    """
    if data.size == 0 or data.shape[1] < x_col + 9:
        print(f"  ({tag}) not enough columns to plot.")
        return ''
    x = data[:, x_col]
    kxx = data[:, x_col + 0]
    kyy = data[:, x_col + 4]
    kzz = data[:, x_col + 8]
    k_avg = (kxx + kyy + kzz) / 3.0

    fig, ax = make_figure()
    lw = get_line_setting('linewidth', 1.2)
    palette = get_palette()
    series = [('k_xx', kxx), ('k_yy', kyy), ('k_zz', kzz), ('average', k_avg)]
    for (label, vals), color in zip(series, palette):
        ax.plot(x, vals, '-', color=color, linewidth=lw, label=label)
    ax.set_xlabel(x_label)
    ax.set_ylabel(f"Thermal conductivity ({cfg['plotting']['units']['conductivity']})")
    ax.set_title(title, fontsize=cfg['plotting']['font']['title_size'])
    ax.legend(frameon=True, loc='best')
    apply_grid(ax)
    fig.tight_layout()
    return _save(fig, out_path, tag)


def plot_kappa(data, headers, out_path, cfg):
    return _plot_kappa_series(data, headers, out_path, cfg,
                              x_label="Temperature (K)", x_col=0,
                              tag='_kappa',
                              title="Thermal conductivity vs temperature")


def plot_cumulative(data, headers, out_path, cfg):
    return _plot_kappa_series(data, headers, out_path, cfg,
                              x_label=f"Sample size L ({cfg['plotting']['units']['length']})",
                              x_col=0, tag='_cumulative',
                              title="Cumulative thermal conductivity")


def plot_cumulative2(data, headers, out_path, cfg):
    return _plot_kappa_series(data, headers, out_path, cfg,
                              x_label=f"Sample size L ({cfg['plotting']['units']['length']})",
                              x_col=0, tag='_cumulative2',
                              title="Cumulative thermal conductivity (directional)")


def plot_kappa_boundary(data, headers, out_path, cfg):
    return _plot_kappa_series(data, headers, out_path, cfg,
                              x_label="Temperature (K)", x_col=0,
                              tag='_kappa_boundary',
                              title="Thermal conductivity with boundary effect")


# ---------------------------------------------------------------------------
# Save helper shared by every routine.
# ---------------------------------------------------------------------------
def _save(fig, out_path: str, tag: str) -> str:
    base = os.path.splitext(out_path)[0] + tag
    written = save_figure(fig, base)
    plt.close(fig)
    return written[0] if written else ''


# ---------------------------------------------------------------------------
# Dispatcher.
# ---------------------------------------------------------------------------
_DISPATCH = {
    'tau': plot_tau,
    'tau_temp': plot_tau_temp,
    'kappa': plot_kappa,
    'cumulative': plot_cumulative,
    'cumulative2': plot_cumulative2,
    'kappa_boundary': plot_kappa_boundary,
}


def plot_result(result_path: str, calc: str) -> str:
    """Parse ``result_path`` and produce the figure matching ``calc``.

    Parameters
    ----------
    result_path : str
        Path to the ``*_<calc>.dat`` file written by the wrapper.
    calc : str
        Calculation mode; selects the appropriate parser/plotter.

    Returns
    -------
    str
        Path of the primary saved figure (empty string on failure).
    """
    if calc not in _DISPATCH:
        print(f"No plotter registered for calc='{calc}'.")
        return ''
    if not os.path.isfile(result_path):
        print(f"Result file not found: {result_path}")
        return ''

    cfg = apply_plot_style()
    data, headers = parse_columns(result_path)
    print(f"Parsed {data.shape[0]} data rows, {data.shape[1]} columns.")
    return _DISPATCH[calc](data, headers, result_path, cfg)


# ---------------------------------------------------------------------------
# Standalone CLI entry point.
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Plot an analyze_phonons result file.")
    parser.add_argument('result', help="Path to the *_<calc>.dat file")
    parser.add_argument('--calc', required=True,
                        choices=list(_DISPATCH.keys()),
                        help="Calculation mode that produced the file")
    args = parser.parse_args()
    plot_result(args.result, args.calc)


if __name__ == '__main__':
    main()
