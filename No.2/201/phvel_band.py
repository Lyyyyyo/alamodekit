#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phvel_band.py
=============

Process a phonon group-velocity projection and plot the dispersion coloured
by the magnitude of the group velocity.

Inputs
------
    <prefix>.bands   phonon frequencies along the high-symmetry path
    <prefix>.phvel   group velocities along the same path

Outputs
-------
    <prefix>_vel_projection.txt      merged kpoint/frequency/velocity data
    <prefix>_vel_projection_plot     figure (png/pdf per settings.yaml)

All visual settings (DPI, line width, the yellow->green->blue colormap, the
colorbar, axis units, output formats) come from ``config/settings.yaml``.
"""
from __future__ import annotations

import os

import alamodekit_io
alamodekit_io.ensure_package_root()

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from alamodekit_io import prompt_prefix
from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_high_sym_line_style,
                        add_colorbar, apply_grid, get_cmap)
from alamodekit_config import get_plotting_config


def read_bands_and_phvel(prefix: str):
    """Read the ``.bands`` and ``.phvel`` files for ``prefix``.

    Returns
    -------
    kpoints : np.ndarray (nk,)
    frequencies : np.ndarray (nk, n_modes)
    velocities : np.ndarray (nk, n_modes)
    tick_values : list[float]
    tick_labels : list[str]
    """
    bands_file = f"{prefix}.bands"
    phvel_file = f"{prefix}.phvel"
    for path in (bands_file, phvel_file):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Error: file '{path}' not found.")

    with open(bands_file, 'r', encoding='utf-8') as handle:
        band_lines = handle.readlines()
    with open(phvel_file, 'r', encoding='utf-8') as handle:
        vel_lines = handle.readlines()

    # High-symmetry header is shared with .bands.
    names, values = alamodekit_io.parse_high_symmetry_header(band_lines[:2])
    tick_values, tick_labels = alamodekit_io.merge_high_symmetry_points(names, values)

    band_data = np.atleast_2d(np.loadtxt(band_lines[3:]))
    vel_data = np.atleast_2d(np.loadtxt(vel_lines[1:]))
    if band_data.shape[0] != vel_data.shape[0]:
        raise ValueError("Bands and phvel files have different k-point counts.")

    kpoints = band_data[:, 0]
    frequencies = band_data[:, 1:]
    velocities = vel_data[:, 1:]
    return kpoints, frequencies, velocities, tick_values, tick_labels


def write_merged_data(prefix: str, kpoints, frequencies, velocities) -> str:
    """Write the merged kpoint/frequency/velocity data file."""
    out_file = f"{prefix}_vel_projection.txt"
    n_modes = frequencies.shape[1]
    with open(out_file, 'w', encoding='utf-8') as handle:
        handle.write("# kpoint  frequency(cm-1)  group_velocity(km/s)\n")
        for mode in range(n_modes):
            for k, freq, vel in zip(kpoints, frequencies[:, mode],
                                    velocities[:, mode]):
                handle.write(f"{k} {freq} {vel}\n")
            handle.write("\n")
    print(f"Done! Generated {out_file}")
    return out_file


def plot_velocity_projection(kpoints, frequencies, velocities,
                             tick_values, tick_labels, prefix: str) -> None:
    """Draw the dispersion coloured by group velocity magnitude."""
    cfg = apply_plot_style()
    fig, ax = make_figure()

    lw = get_line_setting('band_linewidth', get_line_setting('linewidth', 1.2))
    alpha = get_line_setting('alpha', 1.0)
    cmap = get_cmap('velocity')

    # Group velocities are non-negative magnitudes (km/s).
    v_all = np.abs(velocities)
    v_min = 0.0
    v_max = float(v_all.max())

    for mode in range(frequencies.shape[1]):
        x = kpoints
        y = frequencies[:, mode]
        c = v_all[:, mode]
        points = np.column_stack((x, y)).reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        lc = LineCollection(segments, cmap=cmap,
                            norm=plt.Normalize(vmin=v_min, vmax=v_max),
                            linewidth=lw, alpha=alpha)
        lc.set_array(c)
        ax.add_collection(lc)

    # High-symmetry guide lines and ticks.
    for x in tick_values:
        ax.axvline(x=x, **get_high_sym_line_style())
    ax.set_xlim(0, max(tick_values) if tick_values else kpoints.max())
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)

    units = cfg['plotting']['units']
    ax.set_ylabel(f"Frequency ({units['frequency']})")
    ax.autoscale(axis='y')
    apply_grid(ax)

    # Colorbar with rounded integer ticks every 1000 km/s.
    step = 1000.0
    ticks = np.arange(v_min, v_max + step, step)
    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=v_min, vmax=v_max))
    sm.set_array([])
    cbar = add_colorbar(sm, ax, label="Group Velocity (km/s)")
    if cbar is not None and ticks.size:
        cbar.set_ticks(ticks)
        cbar.ax.set_yticklabels([f"{int(t)}" for t in ticks])

    fig.tight_layout()
    save_figure(fig, f"{prefix}_vel_projection_plot", cfg=cfg)
    import matplotlib.pyplot as _plt
    _plt.show()
    _plt.close(fig)


def main():
    prefix = prompt_prefix()
    kpoints, frequencies, velocities, tick_values, tick_labels = \
        read_bands_and_phvel(prefix)
    write_merged_data(prefix, kpoints, frequencies, velocities)

    if alamodekit_io.ask_yes_no(
            "Plot the dispersion with group-velocity projection?"):
        plot_velocity_projection(kpoints, frequencies, velocities,
                                 tick_values, tick_labels, prefix)


if __name__ == '__main__':
    main()
