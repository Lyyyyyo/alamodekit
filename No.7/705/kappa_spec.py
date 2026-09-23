#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kappa_spec.py
=============

Post-processing helper: analyse and plot the spectral (mode-resolved)
lattice thermal conductivity from an ALAMODE ``.kl_spec`` file.

When ANPHON is run with ``CALC_KAPPASPEC = 1``, it writes a ``.kl_spec`` file
whose layout is::

    # Temperature [K], Frequency [cm^-1], Thermal Conductivity Spectra (xx, yy, zz) [W/mK * cm]

    <for each temperature>
      <for each frequency bin>
          T   freq   kappa_xx   kappa_yy   kappa_zz
      <blank line>

This tool:
  * parses every temperature block,
  * plots kappa_spec(omega) for one or several selected temperatures,
  * computes the cumulative kappa by integrating the spectrum
    (a useful check that the integral reproduces the total kappa),
  * writes a CSV with the selected temperature's spectrum.

Pure-Python; numpy + matplotlib only.

Usage
-----
    python kappa_spec.py result.kl_spec --temps 300,500 --yes
    python kappa_spec.py result.kl_spec                  # all temperatures
"""
from __future__ import annotations

import os
import sys
import argparse
import csv
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


def parse_kl_spec(path: str):
    """Parse a .kl_spec file.

    Returns a dict {temperature -> (freqs Nx1, kappa_spec Nx3)}.
    """
    blocks = {}
    cur_T = None
    freqs, rows = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            s = ln.strip()
            if not s or s.startswith("#"):
                if cur_T is not None and freqs:
                    blocks[cur_T] = (np.array(freqs), np.array(rows))
                    cur_T, freqs, rows = None, [], []
                continue
            t = s.split()
            try:
                vals = [float(x) for x in t]
            except ValueError:
                continue
            if len(vals) < 5:
                continue
            T = round(vals[0], 4)
            if cur_T is None:
                cur_T = T
            elif T != cur_T:
                # New temperature block begins (no blank line in some files).
                blocks[cur_T] = (np.array(freqs), np.array(rows))
                freqs, rows = [], []
                cur_T = T
            freqs.append(vals[1])
            rows.append(vals[2:5])
    if cur_T is not None and freqs:
        blocks[cur_T] = (np.array(freqs), np.array(rows))
    if not blocks:
        raise ValueError(f"No spectral data parsed from {path}")
    return blocks


def average_kappa_spec(kappa3: np.ndarray) -> np.ndarray:
    """Trace-averaged spectral kappa = (kxx + kyy + kzz)/3."""
    return (kappa3[:, 0] + kappa3[:, 1] + kappa3[:, 2]) / 3.0


def write_csv(path, freqs, kappa3, T):
    avg = average_kappa_spec(kappa3)
    out = path + f"_spec_T{T:g}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"# temperature {T} K"])
        w.writerow(["freq_cm-1", "kxx", "kyy", "kzz", "k_avg"])
        for f, row, a in zip(freqs, kappa3, avg):
            w.writerow([f"{f:.4f}"] + [f"{v:.6f}" for v in row] + [f"{a:.6f}"])
    print(f"  Wrote CSV -> {out}")


def plot_spec(blocks, temps, out_base):
    """Plot kappa_spec(omega) for the selected temperatures on one figure."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    palette = cfg["plotting"]["colors"]["palette"]
    lw = cfg["plotting"]["lines"].get("linewidth", 1.5)
    fig, ax = plt.subplots(figsize=cfg["plotting"]["figsize"])
    for i, T in enumerate(temps):
        freqs, kappa3 = blocks[T]
        avg = average_kappa_spec(kappa3)
        ax.plot(freqs, avg, "-", color=palette[i % len(palette)],
                linewidth=lw, label=f"T = {T:g} K")
        # Report the integrated (cumulative) kappa as a cross-check.
        integral = np.trapz(avg, freqs)
        print(f"  T={T:g}K: integral of k_avg = {integral:.4f} W/mK "
              f"(should match the total kappa)")
    ax.set_xlabel("Frequency (cm$^{-1}$)")
    ax.set_ylabel(r"Spectral $\kappa$ (W m$^{-1}$ K$^{-1}$ cm)")
    ax.set_title("Mode-resolved thermal conductivity",
                 fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, out_base + "_kappa_spec", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plot the spectral thermal conductivity (.kl_spec).")
    parser.add_argument("file", help="*.kl_spec file")
    parser.add_argument("--temps", default="",
                        help="Comma-separated temperatures to plot (default: all)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw the kappa(omega) figure")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    blocks = parse_kl_spec(args.file)
    all_temps = sorted(blocks.keys())
    print("=" * 60)
    print(f"File: {args.file}")
    print(f"Temperatures found: {len(all_temps)} -> {all_temps}")
    if args.temps:
        want = [float(x) for x in args.temps.split(",") if x.strip()]
        temps = []
        for w in want:
            # match to the nearest available temperature
            nearest = min(all_temps, key=lambda t: abs(t - w))
            if abs(nearest - w) > 1.0:
                print(f"  Warning: {w}K not found; using nearest {nearest}K.")
            temps.append(nearest)
    else:
        temps = all_temps
    print("-" * 60)
    base = os.path.splitext(args.file)[0]
    for T in temps:
        freqs, kappa3 = blocks[T]
        write_csv(base, freqs, kappa3, T)
    print("=" * 60)
    if args.yes:
        plot_spec(blocks, temps, base)


if __name__ == "__main__":
    main()
