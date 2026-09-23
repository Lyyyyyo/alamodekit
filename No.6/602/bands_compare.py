#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bands_compare.py
================

Post-processing helper: overlay several ``.bands`` files on a single figure.

It is common to compare phonon dispersions from different calculations — e.g.
harmonic vs anharmonic (SCPH), different exchange-correlation functionals, or
calculated vs experimental. This tool loads any number of ``.bands`` files
and overlays them on one axis, with a legend taken from each file's stem.

The first file's high-symmetry labels and tick positions define the x-axis
ticks; a warning is printed if the other files' q-ranges differ (which would
make the overlay meaningless unless they share the same q-path).

Pure-Python; numpy + matplotlib only.

Usage
-----
    python bands_compare.py harmonic.bands scph.bands --yes
"""
from __future__ import annotations

import os
import sys
import argparse
import numpy as np

# --- Bootstrap: make the toolkit root importable when run as a script. ---
# When this file is executed directly, sys.path[0] is the analyzers folder,
# which does NOT contain the toolkit modules. Add the package root to path
# *before* importing anything toolkit-level. Harmless as a package module.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402
from alamodekit_io import read_bands_file


def load_all(files):
    """Load every .bands file; return list of (q, freqs, ticks, labels, stem)."""
    out = []
    for f in files:
        q, freqs, ticks, labels = read_bands_file(f)
        out.append((q, freqs, ticks, labels, os.path.splitext(os.path.basename(f))[0]))
    return out


def plot_overlay(data, out_base):
    """Overlay every dataset on one axis."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    palette = cfg["plotting"]["colors"]["palette"]
    lw = cfg["plotting"]["lines"].get("linewidth", 1.2)
    fig, ax = plt.subplots(figsize=cfg["plotting"]["figsize"])
    for i, (q, freqs, ticks, labels, stem) in enumerate(data):
        color = palette[i % len(palette)]
        nb = freqs.shape[1]
        for ib in range(nb):
            # Plot every branch in the dataset's colour; only label branch 0.
            ax.plot(q, freqs[:, ib], color=color, linewidth=lw,
                    label=stem if ib == 0 else None)
    # Use the first dataset's ticks for the x-axis labels.
    q0, _, ticks0, labels0, _ = data[0]
    if len(ticks0):
        for x in ticks0:
            ax.axvline(x, color="#cccccc", linewidth=0.8)
        ax.set_xticks(ticks0)
        ax.set_xticklabels([alamodekit_io.substitute_gamma(l) for l in labels0])
    ax.axhline(0, color="#888888", linewidth=0.8, linestyle="--")
    ax.set_xlabel("q-path")
    ax.set_ylabel(r"Frequency (cm$^{-1}$)")
    ax.set_title("Phonon dispersion comparison",
                 fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, out_base + "_bands_compare", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Overlay several .bands files on one figure.")
    parser.add_argument("files", nargs="+", help="Two or more *.bands files")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Draw the overlay figure")
    args = parser.parse_args(argv if argv is not None else None)
    if len(args.files) < 2:
        print("Need at least two .bands files to compare.")
        sys.exit(1)
    for f in args.files:
        if not os.path.isfile(f):
            print(f"Error: file '{f}' not found.")
            sys.exit(1)
    data = load_all(args.files)
    # Sanity check: q-range of each file.
    q0 = data[0][0]
    print("=" * 60)
    print(f"Comparing {len(data)} band files:")
    for q, freqs, _, _, stem in data:
        print(f"  {stem:<20} {len(q):>4d} q-points, {freqs.shape[1]} branches, "
              f"omega in [{freqs.min():.2f}, {freqs.max():.2f}] cm^-1")
    if any(len(d[0]) != len(q0) for d in data):
        print("  WARNING: files have different numbers of q-points; the overlay "
              "may be misleading unless they share the same q-path.")
    print("=" * 60)
    if args.yes:
        plot_overlay(data, os.path.splitext(args.files[0])[0] + "_vs")


if __name__ == "__main__":
    main()
