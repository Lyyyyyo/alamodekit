#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
softmode_detector.py
====================

Post-processing helper: detect soft modes and imaginary frequencies in a
``.bands`` file.

A phonon dispersion with negative (imaginary) frequencies signals that the
reference structure is not a local minimum of the Born-Oppenheimer surface.
Before trusting any RTA/SCPH result it is therefore essential to scan the
band structure for soft modes (omega < 0). This tool does that and reports:

  * the minimum frequency across the whole path (the "worst" soft mode),
  * how many q-points have at least one imaginary branch,
  * the q-points and branch indices where the worst soft modes occur,
  * an optional dispersion figure with imaginary regions shaded red.

The ``.bands`` format: a 2-line header (labels, tick positions) followed by
rows  q  omega_1  omega_2  ...  omega_N  (cm^-1).

Pure-Python; numpy + matplotlib only.

Usage
-----
    python softmode_detector.py result.bands --yes
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


def analyze(bands_path: str):
    """Return (qpoints, freqs NxNB, labels, ticks) plus the soft-mode report."""
    kpoints, freqs, tick_values, tick_labels = read_bands_file(bands_path)
    q = kpoints
    labels = tick_labels
    ticks = tick_values
    min_freq = float(freqs.min())
    n_imag_q = int(np.sum(np.any(freqs < 0, axis=1)))
    # Indices of the worst soft modes (smallest frequency per q-point).
    worst_branch = freqs.argmin(axis=1)
    worst_vals = freqs[np.arange(len(q)), worst_branch]
    # Top-5 worst (q, branch, value) tuples.
    flat = [(float(freqs[i, j]), int(i), int(j))
            for i in range(len(q)) for j in range(freqs.shape[1])]
    flat.sort()
    worst5 = flat[:5]
    return {"q": q, "freqs": freqs, "labels": labels, "ticks": ticks,
            "min_freq": min_freq, "n_imag_q": n_imag_q,
            "n_q": len(q), "n_branches": freqs.shape[1],
            "worst_branch": worst_branch, "worst_vals": worst_vals,
            "worst5": worst5}


def report(info: dict, path: str):
    print("=" * 60)
    print(f"File: {path}")
    print(f"q-points   : {info['n_q']}")
    print(f"branches   : {info['n_branches']}")
    print("-" * 60)
    mn = info["min_freq"]
    if mn < -0.1:
        print(f"!! SOFT MODES DETECTED: minimum omega = {mn:.3f} cm^-1")
        print(f"   q-points with at least one imaginary branch: "
              f"{info['n_imag_q']} / {info['n_q']}")
        print("   Worst 5 modes (freq, q-index, branch):")
        for v, i, j in info["worst5"]:
            print(f"     {v:9.3f} cm^-1   q#{i:<3d} branch {j}")
    elif mn < 0:
        print(f"Warning: very small negative freq = {mn:.3f} cm^-1 "
              f"(likely numerical noise, |omega| < 0.1 cm^-1).")
        print("         Structure is probably a true minimum.")
    else:
        print(f"OK: no soft modes. Minimum omega = {mn:.3f} cm^-1.")
    print("=" * 60)


def plot(info: dict, out_base: str):
    """Plot the dispersion, shading imaginary (negative) regions red."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    q = info["q"]
    freqs = info["freqs"]
    nb = freqs.shape[1]
    fig, ax = plt.subplots(figsize=cfg["plotting"]["figsize"])
    lw = cfg["plotting"]["lines"].get("linewidth", 1.0)
    for ib in range(nb):
        ax.plot(q, freqs[:, ib], color="#333333", linewidth=lw)
    # Shade regions below zero (imaginary modes).
    ax.axhspan(freqs.min(), 0, color="#d62728", alpha=0.18, zorder=0,
               label="imaginary (soft)")
    ax.axhline(0, color="#888888", linewidth=0.8, linestyle="--")
    # High-symmetry ticks.
    ticks = info["ticks"]
    labels = info["labels"]
    if len(ticks):
        for x in ticks:
            ax.axvline(x, color="#cccccc", linewidth=0.8)
        ax.set_xticks(ticks)
        ax.set_xticklabels([alamodekit_io.substitute_gamma(l) for l in labels])
    ax.set_xlabel("q-path")
    ax.set_ylabel(r"Frequency (cm$^{-1}$)")
    ax.set_title("Phonon dispersion (soft-mode scan)",
                 fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    save_figure(fig, out_base + "_softmode", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Detect soft/imaginary modes in a .bands file.")
    parser.add_argument("file", help="*.bands file from ANPHON")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw the dispersion with soft regions shaded")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    info = analyze(args.file)
    report(info, args.file)
    if args.yes:
        plot(info, os.path.splitext(args.file)[0])


if __name__ == "__main__":
    main()
