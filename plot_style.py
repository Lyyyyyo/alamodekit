#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_style.py
=============

Centralized matplotlib styling for the ALAMODEkit toolkit.

Every plotting subprogram imports the helpers from this module instead of
hard-coding colors, line widths, DPI, etc. This way all figures share a
consistent appearance that is fully controlled by ``config/settings.yaml``.

Typical usage in a subprogram
------------------------------
    import os, sys
    # Make the package root importable when this script runs standalone.
    PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if PKG_ROOT not in sys.path:
        sys.path.insert(0, PKG_ROOT)
    from plot_style import apply_plot_style, save_figure, get_palette, get_cmap

    cfg = apply_plot_style()          # apply global rcParams
    fig, ax = plt.subplots(figsize=cfg['plotting']['figsize'])
    ...
    save_figure(fig, 'my_output')      # writes png/pdf/... per settings
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Make the package root importable when this module itself is imported
# directly (e.g. when a subprogram does `from plot_style import ...`).
_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from alamodekit_config import load_config, get_plotting_config

# Cache for lazily-built custom colormaps.
_CMAP_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Custom colormaps built from the settings.
# ---------------------------------------------------------------------------
def _cmap_yellow_green_blue() -> LinearSegmentedColormap:
    """Yellow (low) -> green (mid) -> dark blue (high)."""
    colors = [(1.0, 1.0, 0.0),   # yellow at the minimum
              (0.0, 1.0, 0.0),   # green at the middle
              (0.0, 0.0, 0.5)]   # dark blue at the maximum
    return LinearSegmentedColormap.from_list('velocity', colors, N=256)


def _cmap_blue_white_red(zero_fraction: float = 0.5) -> LinearSegmentedColormap:
    """Dark blue (low) -> white (at zero) -> dark red (high).

    ``zero_fraction`` is the position of white within the normalized range,
    used so that 0 always maps to white even when the data range is skewed.
    """
    zero_fraction = min(max(float(zero_fraction), 0.0), 1.0)
    colors = [(0.0, (0.0, 0.0, 0.5)),     # dark blue at the minimum
              (zero_fraction, (1.0, 1.0, 1.0)),  # white at zero
              (1.0, (0.8, 0.0, 0.0))]     # dark red at the maximum
    cmap = LinearSegmentedColormap.from_list('gruneisen', colors, N=2048)
    return cmap


# ---------------------------------------------------------------------------
# Public style helpers.
# ---------------------------------------------------------------------------
def apply_plot_style() -> dict:
    """Apply the global matplotlib rcParams defined in settings.yaml.

    Returns
    -------
    dict
        The full configuration dictionary, so callers can read extra values
        (figure size, units, ...) without reloading the config.
    """
    cfg = load_config()
    plot = cfg.get('plotting', {})
    font = plot.get('font', {})
    lines = plot.get('lines', {})
    axes = plot.get('axes', {})

    rc = {
        'font.family': font.get('family', 'Arial'),
        'font.size': font.get('size', 12),
        'axes.labelsize': font.get('label_size', 14),
        'xtick.labelsize': font.get('tick_size', 12),
        'ytick.labelsize': font.get('tick_size', 12),
        'axes.titlesize': font.get('title_size', 16),
        'axes.linewidth': axes.get('linewidth', 1.2),
        'xtick.major.width': axes.get('tick_major_width', 1.2),
        'ytick.major.width': axes.get('tick_major_width', 1.2),
        'xtick.minor.width': axes.get('tick_minor_width', 1.0),
        'ytick.minor.width': axes.get('tick_minor_width', 1.0),
        'xtick.direction': axes.get('tick_direction', 'in'),
        'ytick.direction': axes.get('tick_direction', 'in'),
        'lines.linewidth': lines.get('linewidth', 1.2),
        'lines.antialiased': lines.get('antialiased', True),
        'text.antialiased': True,
    }
    mpl.rcParams.update(rc)
    return cfg


def get_palette() -> list:
    """Return the high-contrast color palette from settings.yaml."""
    return load_config()['plotting']['colors']['palette']


def get_color(name: str = 'primary') -> str:
    """Return a named color from the settings (primary/secondary/...)."""
    return load_config()['plotting']['colors'].get(name, '#1f77b4')


def get_line_setting(name: str, default=None):
    """Return a single line setting (linewidth/band_linewidth/color/alpha)."""
    return load_config()['plotting']['lines'].get(name, default)


def get_high_sym_line_style() -> dict:
    """Return matplotlib kwargs for the high-symmetry-point guide lines."""
    colors = load_config()['plotting']['colors']
    return {
        'color': colors.get('high_sym_line', 'gray'),
        'linewidth': colors.get('high_sym_linewidth', 0.8),
        'linestyle': colors.get('high_sym_linestyle', '--'),
        'alpha': colors.get('high_sym_alpha', 0.6),
    }


def get_cmap(name: str, zero_fraction: Optional[float] = None):
    """Return a colormap by logical name, resolving custom colormaps.

    Parameters
    ----------
    name : str
        Logical name declared in settings.yaml under plotting.colormaps,
        e.g. ``"velocity"``, ``"gruneisen"``, ``"temperature"``.
    zero_fraction : float, optional
        For the Gruneisen diverging colormap, the normalized position of
        the white (zero) anchor.
    """
    cm_cfg = load_config()['plotting'].get('colormaps', {})
    key = cm_cfg.get(name, name)

    cache_key = (key, zero_fraction)
    if cache_key in _CMAP_CACHE:
        return _CMAP_CACHE[cache_key]

    if key == 'custom_yellow_green_blue':
        cmap = _cmap_yellow_green_blue()
    elif key == 'custom_blue_white_red':
        cmap = _cmap_blue_white_red(zero_fraction if zero_fraction is not None else 0.5)
    else:
        cmap = plt.get_cmap(key)

    _CMAP_CACHE[cache_key] = cmap
    return cmap


def make_figure(figsize: Optional[Tuple[float, float]] = None):
    """Create a figure using the configured default size and style.

    Always call :func:`apply_plot_style` first so rcParams are set.
    """
    cfg = load_config()
    size = figsize or tuple(cfg['plotting'].get('figsize', [8, 6]))
    fig, ax = plt.subplots(figsize=size)
    return fig, ax


def apply_grid(ax) -> None:
    """Apply the grid style from settings to an Axes, if enabled."""
    grid = load_config()['plotting'].get('grid', {})
    if grid.get('enabled', False):
        ax.grid(alpha=grid.get('alpha', 0.3),
                linestyle=grid.get('linestyle', '--'))


def add_colorbar(mappable, ax, label: str = '', orientation: Optional[str] = None):
    """Attach a colorbar to ``ax`` using the configured colorbar style.

    Parameters
    ----------
    mappable : ScalarMappable or LineCollection
        The object that carries the color mapping.
    ax : matplotlib Axes
        The axes the colorbar should be attached to.
    label : str
        Colorbar label text.
    orientation : str, optional
        "vertical" or "horizontal"; defaults to the configured value.
    """
    cfg = load_config()
    cb_cfg = cfg['plotting'].get('colorbar', {})
    if not cb_cfg.get('enabled', True):
        return None
    orientation = orientation or cb_cfg.get('orientation', 'vertical')
    cbar = plt.colorbar(mappable, ax=ax, orientation=orientation)
    cbar.set_label(label, fontsize=cb_cfg.get('label_size', 12))
    cbar.ax.tick_params(labelsize=cb_cfg.get('tick_size', 10))
    return cbar


def save_figure(fig, basename: str, cfg: Optional[dict] = None) -> list:
    """Save a figure in every format declared in settings.yaml.

    Parameters
    ----------
    fig : matplotlib Figure
        The figure to save.
    basename : str
        Output path without extension (e.g. ``"SnSeS_phonon_dispersion"``).
    cfg : dict, optional
        Pre-loaded configuration; reloaded if omitted.

    Returns
    -------
    list of str
        The paths of the files actually written.
    """
    cfg = cfg or load_config()
    plot = cfg['plotting']
    dpi = plot.get('dpi', 600)
    formats = plot.get('save_formats', ['png'])
    written = []
    for fmt in formats:
        out_path = f"{basename}.{fmt.lstrip('.')}"
        fig.savefig(out_path, dpi=dpi, bbox_inches='tight',
                    pad_inches=0.05, facecolor='white')
        written.append(out_path)
        print(f"  Saved: {out_path}")
    return written


if __name__ == '__main__':
    # Quick self-test: print the resolved style summary.
    cfg = apply_plot_style()
    print("Palette:", get_palette())
    print("Default color:", get_color('primary'))
    print("Custom velocity cmap:", get_cmap('velocity'))
    print("Custom gruneisen cmap:", get_cmap('gruneisen'))
