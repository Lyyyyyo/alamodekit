#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
poscar_info.py
==============

Pre-processing helper: inspect a VASP POSCAR / CONTCAR structure.

ALAMODE's harmonic workflow starts from an equilibrium structure. This tool
parses a POSCAR/CONTCAR and reports everything you typically want to verify
before running displace/alm:

  * comment line, scaling factor
  * lattice vectors (and whether the cell is cubic/tetragonal/...)
  * cell volume and crystal density (using a built-in mass table)
  * number and types of atoms, total mass
  * nearest-neighbour distances per element pair (quick sanity check)

It can also draw a 3-D ball-and-stick preview of the structure with matplotlib
so you can visually confirm the cell before launching calculations.

This is a pure-Python tool: it only reads a text file and uses numpy /
matplotlib. It does not call ALAMODE.

Usage
-----
    python poscar_info.py POSCAR
    python poscar_info.py SPOSCAR --yes            # also draw the 3D preview
"""
from __future__ import annotations

import os
import sys

# --- Bootstrap: make the toolkit root importable when run as a script. ---
# When this file is executed directly (``python analyzers/poscar_info.py``),
# ``sys.path[0]`` is the ``analyzers`` folder, which does NOT contain the
# toolkit modules. We therefore add the parent directory (the package root)
# to ``sys.path`` *before* importing anything toolkit-level. This is harmless
# when the file is imported as a package module instead.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402 (after path bootstrap)
alamodekit_io.ensure_package_root()  # noqa: E402
import argparse  # noqa: E402
import numpy as np

# Compact atomic-mass table (u) for the first ~96 elements. Used only to compute
# the crystal density; missing entries fall back to 0.0 (reported as unknown).
ATOMIC_MASSES = {
    "H": 1.008, "He": 4.0026, "Li": 6.94, "Be": 9.0122, "B": 10.81, "C": 12.011,
    "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180, "Na": 22.990, "Mg": 24.305,
    "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06, "Cl": 35.45, "Ar": 39.948,
    "K": 39.098, "Ca": 40.078, "Sc": 44.956, "Ti": 47.867, "V": 50.942, "Cr": 51.996,
    "Mn": 54.938, "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224, "Nb": 92.906, "Mo": 95.95,
    "Tc": 98.0, "Ru": 101.07, "Rh": 102.91, "Pd": 106.42, "Ag": 107.87, "Cd": 112.41,
    "In": 114.82, "Sn": 118.71, "Sb": 121.76, "Te": 127.60, "I": 126.90, "Xe": 131.29,
    "Cs": 132.91, "Ba": 137.33, "La": 138.91, "Ce": 140.12, "Pr": 140.91, "Nd": 144.24,
    "Pm": 145.0, "Sm": 150.36, "Eu": 151.96, "Gd": 157.25, "Tb": 158.93, "Dy": 162.50,
    "Ho": 164.93, "Er": 167.26, "Tm": 168.93, "Yb": 173.05, "Lu": 174.97, "Hf": 178.49,
    "Ta": 180.95, "W": 183.84, "Re": 186.21, "Os": 190.23, "Ir": 192.22, "Pt": 195.08,
    "Au": 196.97, "Hg": 200.59, "Tl": 204.38, "Pb": 207.2, "Bi": 208.98, "Po": 209.0,
    "At": 210.0, "Rn": 222.0, "Fr": 223.0, "Ra": 226.0, "Ac": 227.0, "Th": 232.04,
    "Pa": 231.04, "U": 238.03, "Np": 237.0, "Pu": 244.0, "Am": 243.0, "Cm": 247.0,
}


def parse_poscar(path: str):
    """Parse a POSCAR/CONTCAR file.

    Returns
    -------
    dict with keys: comment, scale, lattice (3x3), elements (list),
    counts (list), coord_type ('Direct'/'Cartesian'), positions (Nx3).
    """
    with open(path, "r", encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh]
    comment = lines[0]
    scale = float(lines[1].split()[0])
    lattice = np.array([[float(x) for x in lines[2 + i].split()[:3]]
                        for i in range(3)])
    # The 7th line may hold element symbols (VASP 5+) or be a count line (VASP 4).
    idx = 5
    elements = []
    if lines[5].split() and lines[5].split()[0].isalpha():
        elements = lines[5].split()
        idx = 6
    counts = [int(x) for x in lines[idx].split()]
    if not elements:
        elements = [f"X{i+1}" for i in range(len(counts))]
    coord_line = lines[idx + 1].strip()
    coord_type = "Direct" if coord_line[0].lower() in "ds" else "Cartesian"
    n = sum(counts)
    positions = np.array([[float(x) for x in lines[idx + 2 + i].split()[:3]]
                          for i in range(n)])
    if scale < 0:
        # Negative scale means the cell is defined by total volume.
        raise ValueError("Negative (volume) scaling factor is not supported here.")
    return {"comment": comment, "scale": scale, "lattice": lattice * scale,
            "elements": elements, "counts": counts,
            "coord_type": coord_type, "positions": positions}


def _lattice_metrics(lattice: np.ndarray):
    """Return lengths |a|,|b|,|c| and angles alpha,beta,gamma (degrees)."""
    a, b, c = lattice
    la, lb, lc = np.linalg.norm(a), np.linalg.norm(b), np.linalg.norm(c)
    def ang(u, v):
        cos = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
        return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
    alpha = ang(b, c)
    beta = ang(a, c)
    gamma = ang(a, b)
    return la, lb, lc, alpha, beta, gamma


def _classify(la, lb, lc, alpha, beta, gamma):
    """A very small crystal-system classifier (tolerant)."""
    def close(x, y, tol=1.0):
        return abs(x - y) <= tol
    right = all(close(a, 90.0, 1.5) for a in (alpha, beta, gamma))
    if right and close(la, lb) and close(lb, lc):
        return "cubic"
    if right and close(la, lb) and not close(lb, lc):
        return "tetragonal"
    if right:
        return "orthorhombic"
    if close(alpha, 90) and close(beta, 90) and close(gamma, 120):
        return "hexagonal / trigonal"
    if close(alpha, beta) and close(beta, gamma):
        return "rhombohedral"
    if close(alpha, 90) and close(gamma, 90):
        return "monoclinic"
    return "triclinic"


def nearest_neighbour_distances(lattice, positions, elements, counts,
                                coord_type="Direct", cutoff=8.0):
    """Compute shortest distance per element pair within ``cutoff`` (Angstrom).

    Distances are computed with the minimum-image convention, so periodic
    boundary conditions are respected. ``positions`` may be Cartesian
    (``coord_type='Cartesian'``) or fractional (``coord_type='Direct'``);
    in the Cartesian case they are first converted to fractional coords.
    """
    labels = []
    for el, c in zip(elements, counts):
        labels += [el] * c
    if coord_type and coord_type.lower().startswith("c"):
        # Cartesian -> fractional.
        inv = np.linalg.inv(lattice)
        frac = positions @ inv.T
    else:
        frac = positions.copy()
    frac = frac - np.floor(frac)
    pair_min = {}
    n = len(positions)
    for i in range(n):
        for j in range(i + 1, n):
            d = frac[i] - frac[j]
            d = d - np.round(d)  # minimum image
            dist = np.linalg.norm(d @ lattice)
            if dist > cutoff:
                continue
            key = tuple(sorted((labels[i], labels[j])))
            if key not in pair_min or dist < pair_min[key]:
                pair_min[key] = dist
    return pair_min


def report(path: str) -> dict:
    """Print a human-readable report for ``path`` and return the parsed dict."""
    info = parse_poscar(path)
    lat = info["lattice"]
    la, lb, lc, al, be, ga = _lattice_metrics(lat)
    volume = np.linalg.det(lat)
    masses = [ATOMIC_MASSES.get(e, 0.0) for e in info["elements"]]
    counts = info["counts"]
    total_mass = sum(m * c for m, c in zip(masses, counts))
    # 1 u = 1.66054e-27 kg ; volume in Angstrom^3 = 1e-30 m^3.
    density = (total_mass * 1.66054e-27) / (volume * 1e-30) if volume > 0 else 0.0

    print("=" * 60)
    print(f"Structure file : {os.path.basename(path)}")
    print(f"Comment        : {info['comment'].strip()}")
    print("-" * 60)
    print(f"Scaling factor : {info['scale']}")
    print(f"Cell vectors (Angstrom):")
    for i, v in enumerate(lat, 1):
        print(f"  a{i} = [{v[0]:12.6f} {v[1]:12.6f} {v[2]:12.6f}]")
    print(f"|a|,|b|,|c|    : {la:.4f}  {lb:.4f}  {lc:.4f} Angstrom")
    print(f"alpha,beta,gamma: {al:.3f}  {be:.3f}  {ga:.3f} deg")
    print(f"Volume         : {volume:.4f} Angstrom^3")
    print(f"Crystal system : {_classify(la, lb, lc, al, be, ga)}")
    print("-" * 60)
    print("Atoms:")
    for el, c, m in zip(info["elements"], counts, masses):
        print(f"  {el:<4} x{c:<4}  (mass {m:.3f} u)")
    print(f"Total mass     : {total_mass:.4f} u")
    print(f"Density        : {density:.4f} g/cm^3"
          + ("" if all(masses) else "  (some masses unknown -> density partial)"))
    print(f"Coord. type    : {info['coord_type']}")
    print("-" * 60)
    nn = nearest_neighbour_distances(lat, info["positions"],
                                     info["elements"], counts,
                                     coord_type=info["coord_type"])
    if nn:
        print("Shortest pair distances (Angstrom, PBC):")
        for pair, d in sorted(nn.items()):
            print(f"  {pair[0]}-{pair[1]:>2}: {d:.4f}")
    else:
        print("(no neighbour pair found within the cutoff)")
    print("=" * 60)
    return info


def preview_3d(info: dict, out_base: str):
    """Draw a 3-D ball-and-stick preview of the cell and its atoms."""
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3d)
    cfg = apply_plot_style()
    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(111, projection="3d")
    lat = info["lattice"]
    pos = info["positions"]
    if info["coord_type"] == "Direct":
        pos = pos @ lat
    # Draw the unit-cell box.
    origin = np.zeros(3)
    corners = np.array([origin,
                        lat[0], lat[1], lat[2],
                        lat[0] + lat[1], lat[0] + lat[2], lat[1] + lat[2],
                        lat[0] + lat[1] + lat[2]])
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4), (2, 6),
             (3, 5), (3, 6), (4, 7), (5, 7), (6, 7)]
    for a, b in edges:
        ax.plot(*zip(corners[a], corners[b]), color="#444444", linewidth=1.0)
    # Element -> colour from the config palette.
    palette = cfg["plotting"]["colors"]["palette"]
    el_color = {}
    for i, el in enumerate(info["elements"]):
        el_color[el] = palette[i % len(palette)]
    labels = []
    for el, c in zip(info["elements"], info["counts"]):
        labels += [el] * c
    for el in el_color:
        sel = pos[np.array(labels) == el]
        ax.scatter(sel[:, 0], sel[:, 1], sel[:, 2],
                   s=120, color=el_color[el], label=el, edgecolors="black",
                   depthshade=True)
    ax.set_xlabel("x (Å)"); ax.set_ylabel("y (Å)"); ax.set_zlabel("z (Å)")
    ax.set_title(f"Structure preview\n{os.path.basename(info.get('_path',''))}",
                 fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    save_figure(fig, out_base + "_structure_preview", cfg=cfg)
    plt.show()
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect a POSCAR/CONTCAR structure.")
    parser.add_argument("file", help="POSCAR / CONTCAR / SPOSCAR file")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw the 3-D structure preview")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    info = report(args.file)
    info["_path"] = args.file
    if args.yes:
        preview_3d(info, os.path.splitext(args.file)[0])


if __name__ == "__main__":
    main()
