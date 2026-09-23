#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_hardos.py
==============

Plot the harmonic phonon density of states (DOS) from an ALAMODE ``*.dos``
file. All styling (colors, line width, DPI, formats, axis units) is taken
from ``config/settings.yaml`` via :mod:`plot_style`.

Usage
-----
    python plot_hardos.py SnSeS.dos
"""
from __future__ import annotations

import os
import sys

import alamodekit_io
alamodekit_io.ensure_package_root()

import numpy as np
import matplotlib.pyplot as plt

from alamodekit_io import compound_name_from_filename
from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_color, apply_grid)
from alamodekit_config import get_plotting_config


def plot_phonon_dos(input_file: str) -> None:
    """Read ``input_file`` and draw/save the phonon DOS curve.

    Parameters
    ----------
    input_file : str
        Path to a ``*.dos`` file. The first three lines are comment lines
        (header); column 1 is frequency, column 2 is the total DOS.
    """
    if not os.path.isfile(input_file):
        print(f"Error: file '{input_file}' does not exist.")
        sys.exit(1)

    cfg = apply_plot_style()
    compound = compound_name_from_filename(input_file)

    # The .dos file: 3 header lines, then (frequency, DOS) columns.
    try:
        data = np.loadtxt(input_file, skiprows=3)
    except Exception as exc:
        print(f"Error while reading '{input_file}': {exc}")
        sys.exit(1)
    if data.ndim == 1:
        data = data.reshape(1, -1)

    frequency = data[:, 0]
    dos = data[:, 1]

    fig, ax = make_figure()
    color = get_color('primary')
    lw = get_line_setting('linewidth', 2.0)
    alpha = get_line_setting('alpha', 1.0)
    ax.plot(frequency, dos, color=color, linewidth=lw, alpha=alpha,
            label=compound)

    # Restrict the x-axis to the range that actually contains DOS data.
    nonzero = np.where(dos > 0)[0]
    if nonzero.size:
        max_freq = frequency[nonzero[-1]] + 10.0
    else:
        max_freq = 1000.0
    ax.set_xlim(0, max_freq)
    ax.set_ylim(bottom=0)

    units = cfg['plotting']['units']
    ax.set_xlabel(f"Energy ({units['frequency']})")
    ax.legend(frameon=True, loc='upper right')
    ax.set_title(f"Phonon Density of States of {compound}",
                 fontsize=cfg['plotting']['font']['title_size'])
    apply_grid(ax)
    fig.tight_layout()

    out_base = f"{compound}_phonon_DOS"
    save_figure(fig, out_base, cfg=cfg)
    plt.show()
    plt.close(fig)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <file.dos>")
        print(f"Example: python {os.path.basename(__file__)} SnSeS.dos")
        sys.exit(1)
    plot_phonon_dos(sys.argv[1])


if __name__ == '__main__':
    main()
