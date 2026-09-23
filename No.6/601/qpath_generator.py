#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qpath_generator.py
===================

Pre-processing helper: generate a high-symmetry q-point path for band
structure calculations.

ALAMODE's ANPHON reads the band path from the ``&kpath`` block of the input
file (or ``QPOINTS`` / ``KPMESH``-style data). This tool builds such a path
for the common Bravais-lattice crystal systems and writes it out:

  * a plain text segment list (k-point coords + labels) ready to paste into
    an ANPHON ``&kpath`` block, and
  * a small figure sketching the path inside the (reciprocal) Brillouin zone.

The standard paths follow the Setyawan-Curtarolo convention for the lattice
system you select. You can also give a fully custom path with
``--custom "G 0 0 0 | X 0.5 0 0 | ...``.

Pure-Python; numpy + matplotlib only.

Usage
-----
    python qpath_generator.py --system cubic -o bandpath.txt --yes
    python qpath_generator.py --custom "G 0 0 0, X 0.5 0 0, M 0.5 0.5 0" --yes
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


# Standard high-symmetry paths (Setyawan-Curtarolo) in fractional reciprocal
# coords. Each entry is a list of (label, kx, ky, kz) waypoints.
STANDARD_PATHS = {
    "cubic": [("G", 0, 0, 0), ("X", 0.5, 0, 0), ("M", 0.5, 0.5, 0),
              ("G", 0, 0, 0), ("R", 0.5, 0.5, 0.5), ("M", 0.5, 0.5, 0),
              ("X", 0.5, 0, 0), ("R", 0.5, 0.5, 0.5)],
    "tetragonal": [("G", 0, 0, 0), ("X", 0.5, 0, 0), ("M", 0.5, 0.5, 0),
                   ("G", 0, 0, 0), ("Z", 0, 0, 0.5), ("R", 0.5, 0, 0.5),
                   ("A", 0.5, 0.5, 0.5), ("Z", 0, 0, 0.5),
                   ("A", 0.5, 0.5, 0.5), ("M", 0.5, 0.5, 0),
                   ("R", 0.5, 0, 0.5), ("X", 0.5, 0, 0)],
    "orthorhombic": [("G", 0, 0, 0), ("X", 0.5, 0, 0), ("S", 0.5, 0.5, 0),
                     ("Y", 0, 0.5, 0), ("G", 0, 0, 0), ("Z", 0, 0, 0.5),
                     ("U", 0.5, 0, 0.5), ("T", 0.5, 0.5, 0.5),
                     ("R", 0, 0.5, 0.5), ("Z", 0, 0, 0.5)],
    "hexagonal": [("G", 0, 0, 0), ("M", 0.5, 0, 0), ("K", 1.0/3.0, 1.0/3.0, 0),
                   ("G", 0, 0, 0), ("A", 0, 0, 0.5), ("H", 1.0/3.0, 1.0/3.0, 0.5),
                   ("K", 0.5, 0, 0.5), ("H", 1.0/3.0, 1.0/3.0, 0.5),
                   ("M", 0.5, 0, 0.5), ("L", 0.5, 0, 0.5), ("A", 0, 0, 0.5)],
    "monoclinic": [("G", 0, 0, 0), ("X", 0.5, 0, 0), ("D", 0.5, 0, 0.5),
                    ("Z", 0, 0, 0.5), ("G", 0, 0, 0), ("Y", 0, 0.5, 0),
                    ("E", 0, 0.5, 0.5), ("Z", 0, 0, 0.5)],
}


def _parse_custom(spec: str):
    """Parse "G 0 0 0, X 0.5 0 0, M 0.5 0.5 0" into waypoints."""
    waypoints = []
    for part in spec.split("|"):
        part = part.strip().strip(",")
        if not part:
            continue
        t = part.split()
        if len(t) != 4:
            raise ValueError(f"Bad waypoint '{part}' (need 'label x y z').")
        waypoints.append((t[0], float(t[1]), float(t[2]), float(t[3])))
    if len(waypoints) < 2:
        raise ValueError("A path needs at least two waypoints.")
    return waypoints


def build_path(waypoints, n_per_segment=40):
    """Linearly interpolate ``n_per_segment`` points between consecutive
    waypoints. Returns (kpoints Nx3, cumulative distance, tick indices)."""
    pts, dists, ticks = [], [], []
    cum = 0.0
    for i in range(len(waypoints) - 1):
        a = np.array(waypoints[i][1:])
        b = np.array(waypoints[i + 1][1:])
        seg_len = np.linalg.norm(b - a)
        ticks.append((cum, waypoints[i][0]))
        for j in range(n_per_segment):
            f = j / n_per_segment
            pts.append(a + f * (b - a))
            dists.append(cum + f * seg_len)
        cum += seg_len
    pts.append(np.array(waypoints[-1][1:]))
    dists.append(cum)
    ticks.append((cum, waypoints[-1][0]))
    return np.array(pts), np.array(dists), ticks


def write_path(waypoints, n_per_segment, path):
    """Write the path as an ANPHON &kpath-compatible segment list."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# High-symmetry q-path (fractional reciprocal coords)\n")
        fh.write("# Paste the lines below into the &kpath block of an ANPHON input.\n")
        fh.write("&kpath\n")
        fh.write(f"  Nk = {n_per_segment},\n")
        for label, kx, ky, kz in waypoints:
            fh.write(f"  {kx: .6f} {ky: .6f} {kz: .6f}  # {label}\n")
        fh.write("/\n")
    print(f"  Wrote {len(waypoints)}-point path -> {path}")


def plot_path(waypoints, n_per_segment, out_base):
    """Sketch the path: cumulative-distance axis labelled by high-sym points."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    kpts, dists, ticks = build_path(waypoints, n_per_segment)
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(dists, np.zeros_like(dists), color=cfg["plotting"]["colors"]["palette"][0],
            linewidth=2)
    tick_pos = [t[0] for t in ticks]
    tick_lbl = [alamodekit_io.substitute_gamma(t[1]) for t in ticks]
    for x in tick_pos:
        ax.axvline(x, color="#888888", linewidth=0.8, linestyle="--")
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_lbl)
    ax.set_yticks([])
    ax.set_xlabel("q-path (cumulative distance)")
    ax.set_title("High-symmetry q-point path", fontsize=cfg["plotting"]["font"]["title_size"])
    ax.set_xlim(dists.min(), dists.max())
    fig.tight_layout()
    save_figure(fig, out_base + "_qpath", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a high-symmetry q-path.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--system", choices=list(STANDARD_PATHS),
                   help="Standard path for a crystal system")
    g.add_argument("--custom", help='Custom path: "G 0 0 0, X 0.5 0 0, ..."')
    parser.add_argument("--n", type=int, default=40, help="Points per segment")
    parser.add_argument("--output", "-o", default="bandpath.txt", help="Output text file")
    parser.add_argument("--yes", "-y", action="store_true", help="Also draw the path figure")
    args = parser.parse_args(argv if argv is not None else None)
    waypoints = STANDARD_PATHS[args.system] if args.system \
        else _parse_custom(args.custom)
    write_path(waypoints, args.n, args.output)
    print("Path waypoints:")
    for w in waypoints:
        print(f"  {w[0]:>3}  {w[1]: .4f} {w[2]: .4f} {w[3]: .4f}")
    if args.yes:
        plot_path(waypoints, args.n, os.path.splitext(args.output)[0])


if __name__ == "__main__":
    main()
