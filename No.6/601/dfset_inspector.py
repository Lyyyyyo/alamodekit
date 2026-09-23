#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dfset_inspector.py
==================

Pre-processing helper: sanity-check an ALAMODE DFSET (displacement-force) file.

After extracting forces from DFT (with extract.py / displace.py) and before
fitting force constants with ``alm``, it is useful to verify the training
dataset: how many configurations, how large the displacements are, whether
any force is suspiciously huge, etc.

DFSET format (one line per atom, six numbers per line):
    ux uy uz   fx fy fz
where ``u`` is the displacement (Bohr) and ``f`` is the force (Rydberg/Bohr).
Each configuration spans ``NAT`` consecutive lines. Comment lines (``#``) are
skipped.

This tool reports:
  * number of data lines and (if NAT is given) number of configurations,
  * displacement magnitude  (min/max/mean/std, in both Bohr and Angstrom),
  * force magnitude         (min/max/mean/std, in Ry/Bohr and eV/Angstrom),
  * optional histograms of displacement and force magnitudes.

Pure-Python; numpy + matplotlib only.

Usage
-----
    python dfset_inspector.py DFSET --nat 8 --yes
    python dfset_inspector.py DFSET            # stats only, NAT unknown
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

# Conversion constants.
BOHR_TO_ANG = 0.5291772
RYDBERG_TO_EV = 13.605693
# force: Ry/Bohr -> eV/Angstrom  =  (Ry->eV) / (Bohr->Ang)
RY_BOHR_TO_EV_ANG = RYDBERG_TO_EV / BOHR_TO_ANG


def parse_dfset(path: str) -> np.ndarray:
    """Read all numeric records, return an (M, 6) array.

    Each row is [ux, uy, uz, fx, fy, fz]. Comment lines (starting with #) and
    blank lines are skipped. Rows with a different number of columns are
    skipped with a warning (ALAMODE DFSET rows always have 6 entries).
    """
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            t = s.split()
            if len(t) < 6:
                continue
            try:
                rows.append([float(x) for x in t[:6]])
            except ValueError:
                continue  # non-numeric token -> skip
    if not rows:
        raise ValueError("No data rows found in the DFSET file.")
    return np.array(rows)


def _stats(x: np.ndarray) -> dict:
    return {"min": float(x.min()), "max": float(x.max()),
            "mean": float(x.mean()), "std": float(x.std()),
            "median": float(np.median(x))}


def report(rows: np.ndarray, nat: int | None) -> dict:
    """Print statistics and return a dict of the computed magnitudes."""
    disp = np.linalg.norm(rows[:, 0:3], axis=1)  # Bohr
    force = np.linalg.norm(rows[:, 3:6], axis=1)  # Ry/Bohr
    n_lines = len(rows)
    print("=" * 60)
    print(f"DFSET rows (atoms sampled) : {n_lines}")
    if nat:
        if n_lines % nat != 0:
            print(f"  WARNING: {n_lines} is not divisible by NAT={nat}.")
        nconf = n_lines // nat
        print(f"NAT (atoms per config)     : {nat}")
        print(f"Number of configurations   : {nconf}")
    else:
        print("NAT not given -> configuration count not computed.")
    print("-" * 60)
    ds = _stats(disp)
    print("Displacement magnitude (per atom):")
    print(f"  min={ds['min']:.5f}  max={ds['max']:.5f}  mean={ds['mean']:.5f}"
          f"  std={ds['std']:.5f}  (Bohr)")
    print(f"  -> {ds['min']*BOHR_TO_ANG:.4f} ~ {ds['max']*BOHR_TO_ANG:.4f} Angstrom"
          f"  (mean {ds['mean']*BOHR_TO_ANG:.4f})")
    print(f"  median = {ds['median']:.5f} Bohr")
    print("-" * 60)
    fs = _stats(force)
    print("Force magnitude (per atom):")
    print(f"  min={fs['min']:.4f}  max={fs['max']:.4f}  mean={fs['mean']:.4f}"
          f"  std={fs['std']:.4f}  (Ry/Bohr)")
    print(f"  -> {fs['min']*RY_BOHR_TO_EV_ANG:.3f} ~ {fs['max']*RY_BOHR_TO_EV_ANG:.3f} eV/Angstrom"
          f"  (mean {fs['mean']*RY_BOHR_TO_EV_ANG:.3f})")
    print(f"  median = {fs['median']:.4f} Ry/Bohr")
    # Flag suspiciously large forces (> 5 eV/Angstrom is a lot for a small disp).
    big = np.where(force * RY_BOHR_TO_EV_ANG > 5.0)[0]
    if len(big):
        print("-" * 60)
        print(f"WARNING: {len(big)} atom(s) have |F| > 5 eV/Angstrom "
              f"(max {force[big].max()*RY_BOHR_TO_EV_ANG:.2f}).")
    print("=" * 60)
    return {"disp": disp, "force": force}


def plot_histograms(disp, force, out_base):
    """Draw side-by-side histograms of displacement and force magnitudes."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    lw = cfg["plotting"]["lines"].get("linewidth", 1.2)
    ax1.hist(disp * BOHR_TO_ANG, bins=40, color=cfg["plotting"]["colors"]["palette"][0],
             edgecolor="black", linewidth=lw)
    ax1.set_xlabel("Displacement magnitude (Å)")
    ax1.set_ylabel("Count")
    ax1.set_title("Displacements")
    ax2.hist(force * RY_BOHR_TO_EV_ANG, bins=40,
             color=cfg["plotting"]["colors"]["palette"][1],
             edgecolor="black", linewidth=lw)
    ax2.set_xlabel("Force magnitude (eV/Å)")
    ax2.set_ylabel("Count")
    ax2.set_title("Forces")
    fig.tight_layout()
    save_figure(fig, out_base + "_dfset_histograms", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect an ALAMODE DFSET file.")
    parser.add_argument("file", help="DFSET displacement-force file")
    parser.add_argument("--nat", type=int, default=None,
                        help="Number of atoms per configuration")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw displacement/force histograms")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    rows = parse_dfset(args.file)
    res = report(rows, args.nat)
    if args.yes:
        plot_histograms(res["disp"], res["force"],
                        os.path.splitext(args.file)[0])


if __name__ == "__main__":
    main()
