#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
structure_to_vesta.py
======================

Helper: export a crystal structure from a POSCAR to common visualisation
file formats so it can be opened in VESTA, XCRYSDEN, Mercury, OLEX2, etc.

Supported output formats (all public, documented file standards):

  * ``xsf``  — XCRYSDEN structure format (also read by VESTA). Simple and
    robust; the recommended format for quick 3-D checks.
  * ``cif``  — Crystallographic Information File (universal; every visualiser
    reads it). Coordinates are written in fractional form.
  * ``vesta``— VESTA native text format (a minimal but valid subset).

The tool only reads a POSCAR and writes text — no DFT or solver code.

Usage
-----
    python structure_to_vesta.py POSCAR --format xsf
    python structure_to_vesta.py SPOSCAR --format cif -o structure
    python structure_to_vesta.py POSCAR --format all
"""
from __future__ import annotations

import os
import sys
import argparse
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


# --------------------------------------------------------------------------- #
# Self-contained POSCAR parser (no sibling-module dependency).
# --------------------------------------------------------------------------- #
def parse_poscar(path: str) -> dict:
    """Parse a minimal POSCAR/CONTCAR into a dict.

    Keys: title, scale, lattice (3x3), coord_type ('Direct'/'Cartesian'),
    elements (list[str]), counts (list[int]), positions (Nx3 array, in the
    coordinate system given by coord_type).
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    title = lines[0].strip()
    scale = float(lines[1].split()[0])
    # Lattice vectors are lines 2, 3, 4 (0-indexed).
    lattice = np.array([[float(x) for x in lines[i].split()[:3]]
                        for i in range(2, 5)]) * scale
    # After the lattice: either (elements, counts, coord_type) or
    # (counts, coord_type) when element symbols are absent. Detect by trying
    # to parse the next non-empty line as integers.
    idx = 5
    # skip blank lines (some POSCAR variants have them)
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    elements = []
    try:
        counts = [int(x) for x in lines[idx].split()]
    except ValueError:
        # line `idx` carries element symbols
        elements = lines[idx].split()
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        counts = [int(x) for x in lines[idx].split()]
    if not elements:
        elements = [f"El{i+1}" for i in range(len(counts))]
    idx += 1
    # optional 'Selective dynamics' flag
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if lines[idx].strip().lower().startswith("s"):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    coord_type = lines[idx].strip()
    idx += 1
    n = sum(counts)
    positions = []
    for i in range(n):
        parts = lines[idx + i].split()
        # Selective-dynamics lines have 6 columns; take the first 3.
        positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
    positions = np.array(positions)
    return {"title": title, "scale": scale, "lattice": lattice,
            "coord_type": coord_type, "elements": elements,
            "counts": counts, "positions": positions}


def _ensure_frac(info):
    """Return fractional coordinates (Nx3) regardless of the input type."""
    if info["coord_type"].lower().startswith("d"):
        return info["positions"]
    inv = np.linalg.inv(info["lattice"])
    return info["positions"] @ inv.T


def write_xsf(info, path: str):
    """Write an XCRYSDEN .xsf structure file."""
    lat = info["lattice"]
    frac = _ensure_frac(info)
    cart = frac @ lat
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("CRYSTAL\n")
        fh.write("PRIMVEC\n")
        for v in lat:
            fh.write(f"  {v[0]:16.10f}  {v[1]:16.10f}  {v[2]:16.10f}\n")
        fh.write("PRIMCOORD\n")
        fh.write(f"  {sum(info['counts'])} 1\n")
        # Expand per-atom element labels.
        labels = []
        for el, c in zip(info["elements"], info["counts"]):
            labels += [el] * c
        for el, p in zip(labels, cart):
            fh.write(f"{el:<3} {p[0]:16.10f} {p[1]:16.10f} {p[2]:16.10f}\n")
    print(f"  Wrote XSF -> {path}")


def write_cif(info, path: str):
    """Write a CIF (Crystallographic Information File)."""
    lat = info["lattice"]
    a = np.linalg.norm(lat[0])
    b = np.linalg.norm(lat[1])
    c = np.linalg.norm(lat[2])
    def ang(u, v):
        cos = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
        return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
    alpha = ang(lat[1], lat[2])
    beta = ang(lat[0], lat[2])
    gamma = ang(lat[0], lat[1])
    frac = _ensure_frac(info)
    name = os.path.splitext(os.path.basename(info.get("_path", "structure")))[0]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"data_{name}\n")
        fh.write("_audit_creation_date  2026-01-01\n")
        fh.write("_symmetry_space_group_name_H-M   'P 1'\n")
        fh.write("_symmetry_Int_Tables_number   1\n")
        fh.write(f"_cell_length_a   {a:.8f}\n")
        fh.write(f"_cell_length_b   {b:.8f}\n")
        fh.write(f"_cell_length_c   {c:.8f}\n")
        fh.write(f"_cell_angle_alpha   {alpha:.6f}\n")
        fh.write(f"_cell_angle_beta   {beta:.6f}\n")
        fh.write(f"_cell_angle_gamma   {gamma:.6f}\n")
        fh.write("loop_\n _symmetry_equiv_pos_site_id\n _symmetry_equiv_pos_as_xyz\n")
        fh.write("  1  'x, y, z'\n")
        fh.write("loop_\n")
        fh.write(" _atom_site_label\n")
        fh.write(" _atom_site_type_symbol\n")
        fh.write(" _atom_site_fract_x\n")
        fh.write(" _atom_site_fract_y\n")
        fh.write(" _atom_site_fract_z\n")
        labels = []
        for el, c in zip(info["elements"], info["counts"]):
            labels += [el] * c
        idx = {}
        for i, (el, p) in enumerate(zip(labels, frac)):
            idx[el] = idx.get(el, 0) + 1
            fh.write(f"{el}{idx[el]} {el} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}\n")
    print(f"  Wrote CIF -> {path}")


def write_vesta(info, path: str):
    """Write a minimal but valid VESTA native (.vesta) structure file."""
    lat = info["lattice"]
    frac = _ensure_frac(info)
    labels = []
    for el, c in zip(info["elements"], info["counts"]):
        labels += [el] * c
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#VESTA_FORMAT 1.0\n")
        fh.write("CRYSTAL\n")
        fh.write("GROUP\n")
        fh.write("   1\n")
        fh.write("CELLP\n")
        for v in lat:
            fh.write(f"  {v[0]:16.10f}  {v[1]:16.10f}  {v[2]:16.10f}\n")
        fh.write("STRUCT\n")
        for i, (el, p) in enumerate(zip(labels, frac), 1):
            fh.write(f"  {i} {el} {p[0]:10.6f} {p[1]:10.6f} {p[2]:10.6f} 1.0 0\n")
        fh.write("END\n")
    print(f"  Wrote VESTA -> {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export a POSCAR to XSF / CIF / VESTA format.")
    parser.add_argument("file", help="POSCAR / CONTCAR / SPOSCAR")
    parser.add_argument("--format", default="xsf",
                        choices=["xsf", "cif", "vesta", "all"],
                        help="Output format (default: xsf)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output base name (default: <input stem>)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    if parse_poscar is None:
        print("Error: parse_poscar is unavailable.")
        sys.exit(1)
    info = parse_poscar(args.file)
    info["_path"] = args.file
    base = args.output or os.path.splitext(os.path.basename(args.file))[0]
    fmts = ["xsf", "cif", "vesta"] if args.format == "all" else [args.format]
    for fmt in fmts:
        out = f"{base}.{fmt}"
        {"xsf": write_xsf, "cif": write_cif, "vesta": write_vesta}[fmt](info, out)
    print("Done.")


if __name__ == "__main__":
    main()
