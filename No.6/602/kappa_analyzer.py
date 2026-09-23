#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kappa_analyzer.py
=================

Post-processing helper: analyse ALAMODE lattice thermal-conductivity files.

ANPHON's RTA / SCPH calculations write the thermal-conductivity tensor to a
``.kl`` file with the layout::

    # Temperature [K], Thermal Conductivity (xx, xy, xz, yx, yy, yz, zx, zy, zz) [W/mK]
    # (optional comment lines starting with #)
       0.00   ...9 values...
     100.00   ...9 values...

This tool:
  * parses one or more ``.kl`` files,
  * computes the trace-averaged kappa  k_avg = (kxx + kyy + kzz) / 3,
  * plots kappa(T) for each file on one figure (for comparison),
  * writes a tidy CSV with T, the 9 components and the average.

Pure-Python; numpy + matplotlib only.

Usage
-----
    python kappa_analyzer.py result.kl --yes
    python kappa_analyzer.py T300.kl T500.kl --yes     # compare several runs
"""
from __future__ import annotations

import os
import sys
import argparse
import csv
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


def parse_kl(path: str):
    """Parse a .kl file. Returns (temperatures Nx1, kappa Nx9, label)."""
    temps, rows = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            t = s.split()
            try:
                vals = [float(x) for x in t]
            except ValueError:
                continue
            if len(vals) < 10:
                continue
            temps.append(vals[0])
            rows.append(vals[1:10])
    if not temps:
        raise ValueError(f"No data rows parsed from {path}")
    label = os.path.splitext(os.path.basename(path))[0]
    return np.array(temps), np.array(rows), label


def average_kappa(kappa9: np.ndarray) -> np.ndarray:
    """Trace-averaged kappa = (kxx + kyy + kzz)/3 (columns 0,4,8)."""
    return (kappa9[:, 0] + kappa9[:, 4] + kappa9[:, 8]) / 3.0


def write_csv(path, temps, kappa9, label):
    """Write T, 9 components and the average to a CSV file."""
    avg = average_kappa(kappa9)
    out = path + "_kappa.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["# source", label])
        w.writerow(["T(K)", "kxx", "kxy", "kxz", "kyx", "kyy", "kyz",
                    "kzx", "kzy", "kzz", "k_avg"])
        for T, row, a in zip(temps, kappa9, avg):
            w.writerow([f"{T:.2f}"] + [f"{v:.6f}" for v in row] + [f"{a:.6f}"])
    print(f"  Wrote CSV -> {out}")
    return out


def plot_kappa(files, out_base):
    """Plot kappa_avg(T) for every parsed file on one figure."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    palette = cfg["plotting"]["colors"]["palette"]
    lw = cfg["plotting"]["lines"].get("linewidth", 1.5)
    fig, ax = plt.subplots(figsize=cfg["plotting"]["figsize"])
    for i, (temps, kappa9, label) in enumerate(files):
        avg = average_kappa(kappa9)
        ax.plot(temps, avg, "-o", color=palette[i % len(palette)],
                linewidth=lw, markersize=4, label=label)
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel(r"Thermal conductivity $\kappa_{avg}$ (W/mK)")
    n = len(files)
    title = "Lattice thermal conductivity" if n == 1 else \
        f"Comparison of {n} runs"
    ax.set_title(title, fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, out_base + "_kappa", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyse ALAMODE .kl thermal-conductivity file(s).")
    parser.add_argument("files", nargs="+", help="One or more *.kl files")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw the kappa(T) figure")
    args = parser.parse_args(argv if argv is not None else None)
    parsed = []
    for f in args.files:
        if not os.path.isfile(f):
            print(f"Error: file '{f}' not found.")
            sys.exit(1)
        temps, kappa9, label = parse_kl(f)
        avg = average_kappa(kappa9)
        print("=" * 60)
        print(f"File: {f}  ({label})")
        print(f"  Temperatures : {temps.min():.1f} ~ {temps.max():.1f} K "
              f"({len(temps)} points)")
        print(f"  k_avg at T={temps[-1]:.0f}K : {avg[-1]:.4f} W/mK")
        print(f"  k_avg range  : {avg.min():.4f} ~ {avg.max():.4f} W/mK")
        write_csv(os.path.splitext(f)[0], temps, kappa9, label)
        parsed.append((temps, kappa9, label))
    print("=" * 60)
    if args.yes:
        # Use the first file's stem as the figure base name.
        plot_kappa(parsed, os.path.splitext(args.files[0])[0])


if __name__ == "__main__":
    main()
