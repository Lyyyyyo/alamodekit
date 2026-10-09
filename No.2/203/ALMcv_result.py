#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALMcv_result.py
===============

Analyze an ALAMODE ``*.cvscore`` cross-validation result file.

Two capabilities are provided:

1. ``extract_min_alpha(filename)`` -> float
   Locate the ``# Minimum CVSCORE at alpha = X`` annotation that ALAMODE
   appends to the file and return the optimal regularization strength ``X``.

2. ``plot_cv_curve(filename)``
   Parse the full CVSCORE-vs-alpha table and draw the curve, highlighting
   the minimum. All visual settings come from ``config/settings.yaml``.

Usage
-----
    python ALMcv_result.py XXX.cvscore
"""
from __future__ import annotations

import os
import re
import sys
import argparse

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

from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_line_setting, get_color, apply_grid)
from alamodekit_config import get_plotting_config

# Annotation written by ALMODE at the end of the .cvscore file.
_MIN_PATTERN = re.compile(r'#\s*Minimum CVSCORE at alpha\s*=\s*([\d.+-eE]+)')


def extract_min_alpha(filename: str) -> float:
    """Return the alpha value at the minimum CVSCORE.

    Scans from the end of the file for the annotation line and parses the
    floating-point alpha value from it.

    Raises
    ------
    FileNotFoundError
        If ``filename`` does not exist.
    ValueError
        If the annotation line cannot be found or parsed.
    """
    with open(filename, 'r', encoding='utf-8') as handle:
        text = handle.read()

    # Search the whole text; the annotation is near the end.
    matches = _MIN_PATTERN.findall(text)
    if not matches:
        raise ValueError(
            f"Could not find '# Minimum CVSCORE at alpha = ...' in {filename}.\n"
            "Expected format: # Minimum CVSCORE at alpha = <number>")
    return float(matches[-1])


def parse_cv_table(filename: str):
    """Parse the numeric CVSCORE table.

    Returns
    -------
    alphas : np.ndarray
    cvscores : np.ndarray
    """
    alphas, scores = [], []
    with open(filename, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            tokens = line.split()
            # Each row: alpha  cvscore  [extra columns]. Take the first two.
            if len(tokens) >= 2:
                try:
                    alphas.append(float(tokens[0]))
                    scores.append(float(tokens[1]))
                except ValueError:
                    continue
    return np.array(alphas), np.array(scores)


def plot_cv_curve(filename: str) -> str:
    """Plot CVSCORE versus alpha with the minimum highlighted.

    Returns the path of the saved figure (empty string if no data).
    """
    alphas, scores = parse_cv_table(filename)
    if alphas.size == 0:
        print("No numeric CV table found; skipping the plot.")
        return ''

    cfg = apply_plot_style()
    min_alpha = extract_min_alpha(filename)
    min_score = float(np.interp(min_alpha, alphas, scores)) if alphas.size else 0.0

    fig, ax = make_figure()
    lw = get_line_setting('linewidth', 1.5)
    color = get_color('primary')
    accent = get_color('secondary')
    ax.plot(alphas, scores, '-o', color=color, linewidth=lw, markersize=4,
            label="CV score")
    ax.axvline(min_alpha, color=accent, linestyle='--', linewidth=1.0,
               label=f"min at alpha={min_alpha:.3e}")
    ax.scatter([min_alpha], [min_score], color=accent, s=60, zorder=5)
    ax.set_xscale('log')
    ax.set_xlabel("Regularization strength alpha")
    ax.set_ylabel("CV score")
    ax.set_title(f"Cross-validation curve\n{os.path.basename(filename)}",
                 fontsize=cfg['plotting']['font']['title_size'])
    ax.legend(loc='best', fontsize=10)
    apply_grid(ax)
    fig.tight_layout()
    base = os.path.splitext(filename)[0] + "_cv_curve"
    written = save_figure(fig, base, cfg=cfg)
    plt.show()
    plt.close(fig)
    return written[0] if written else ''


def main():
    parser = argparse.ArgumentParser(
        description="Extract the minimum-CVSCORE alpha and plot the CV curve.")
    parser.add_argument('file', help="Path to a .cvscore file")
    args = parser.parse_args()
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)

    alpha = extract_min_alpha(args.file)
    print(f"Alpha value for Minimum CVSCORE: {alpha}")

    try:
        plot_cv_curve(args.file)
    except Exception as exc:
        print(f"(Plotting failed: {exc})")


if __name__ == '__main__':
    main()
