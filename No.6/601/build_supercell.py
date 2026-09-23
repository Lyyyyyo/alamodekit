#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_supercell.py
==================

Pre-processing helper: build a supercell from a VASP POSCAR.

Before running ALAMODE's displacement generation you need a supercell
(SPOSCAR). This tool reads a primitive (or conventional) POSCAR and a
supercell expansion specification, then writes the expanded structure as
``SPOSCAR`` (or a name you choose).

The expansion can be given either as:
  * a diagonal vector, e.g. ``--matrix "2 2 2"``  ->  2x2x2 supercell, or
  * a full 3x3 integer matrix, e.g. ``--matrix "1 1 0  1 -1 0  0 0 2"``
    (rows are the new a', b', c' expressed in the old basis).

Fractional coordinates are remapped into the new cell, keeping the VASP 5+
format (element line + counts). Cartesian coordinates are converted to
fractional first.

Pure-Python; reads/writes text only.

Usage
-----
    python build_supercell.py POSCAR --matrix "2 2 2"
    python build_supercell.py POSCAR --matrix "1 1 0 1 -1 0 0 0 2" -o SPOSCAR
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


def _parse_matrix(spec: str) -> np.ndarray:
    """Parse "2 2 2" (diagonal) or 9 ints (full 3x3) into a (3,3) int array."""
    vals = [int(x) for x in spec.replace(",", " ").split()]
    if len(vals) == 3:
        return np.diag(vals)
    if len(vals) == 9:
        return np.array(vals, dtype=int).reshape(3, 3)
    raise ValueError("Matrix must be 3 ints (diagonal) or 9 ints (full 3x3).")


def build_supercell(poscar_path: str, matrix: np.ndarray) -> dict:
    """Return the supercell structure dict derived from ``poscar_path``."""
    try:  # package-relative (GUI / PyInstaller)
        from .poscar_info import parse_poscar
    except ImportError:  # top-level script
        from poscar_info import parse_poscar  # noqa: E402
    base = parse_poscar(poscar_path)
    a_old = np.array(base["lattice"], dtype=float)
    # New lattice vectors = matrix @ old_lattice (rows of matrix are new basis).
    a_new = matrix @ a_old
    # Volume ratio = |det(matrix)| gives the atom-count multiplier.
    det = int(round(np.linalg.det(matrix)))
    if det == 0:
        raise ValueError("Supercell matrix is singular (det = 0).")

    # Work in fractional coordinates of the OLD cell, then transform to the
    # new cell with the inverse of the supercell matrix.
    inv_old = np.linalg.inv(a_old)
    frac_old = base["positions"] @ inv_old.T
    if base["coord_type"] != "Direct":
        # already converted; otherwise treat as direct already
        pass
    frac_old = frac_old - np.floor(frac_old)

    # Enumerate the integer shifts (n1,n2,n3) spanning the supercell. For a
    # general matrix the safe range is over the bounding box of the matrix.
    n = int(abs(det))
    # Use the column-wise integer search: for diagonal it's just product of
    # diag entries; for general matrix we scan a bounding box and keep points
    # whose new fractional coords land inside the unit cell.
    new_frac_all = []
    bound = int(np.ceil(np.abs(matrix).sum())) + 1
    for n1 in range(-bound, bound + 1):
        for n2 in range(-bound, bound + 1):
            for n3 in range(-bound, bound + 1):
                shift = np.array([n1, n2, n3])
                for f in frac_old:
                    nf = f + shift
                    # Transform to new-cell fractional coords.
                    nf_new = np.linalg.solve(matrix, nf)
                    nf_new = nf_new - np.floor(nf_new)
                    new_frac_all.append(nf_new)
    new_frac = np.array(new_frac_all)
    # Remove duplicates (atoms mapped to the same position by PBC).
    keep = []
    seen = []
    for i, f in enumerate(new_frac):
        is_dup = False
        for s in seen:
            if np.linalg.norm(f - s) < 1e-6:
                is_dup = True
                break
        if not is_dup:
            keep.append(i)
            seen.append(f)
    new_frac = new_frac[keep]
    if len(new_frac) != n * len(frac_old):
        print(f"Warning: expected {n * len(frac_old)} atoms, got {len(new_frac)}."
              f" (This can happen with a non-diagonal matrix.)")

    # Rebuild per-element atom lists and counts in the original order.
    elements = base["elements"]
    counts = base["counts"]
    # Tag each base atom with its element, then tile across shifts.
    base_labels = []
    for el, c in zip(elements, counts):
        base_labels += [el] * c
    # Recompute element ordering for the new list: we enumerated shifts in the
    # same loop order, so the label list is base_labels repeated per shift.
    # But dedup reorders; rebuild labels to match kept atoms.
    labelled = []
    idx = 0
    for n1 in range(-bound, bound + 1):
        for n2 in range(-bound, bound + 1):
            for n3 in range(-bound, bound + 1):
                shift = np.array([n1, n2, n3])
                for f, el in zip(frac_old, base_labels):
                    nf = f + shift
                    nf_new = np.linalg.solve(matrix, nf)
                    nf_new = nf_new - np.floor(nf_new)
                    labelled.append((nf_new, el))
    labelled = [labelled[i] for i in keep]

    # Group by element, preserving the input element order.
    new_elements = []
    new_counts = []
    new_positions = []
    for el in elements:
        sel = [f for f, e in labelled if e == el]
        if sel:
            new_elements.append(el)
            new_counts.append(len(sel))
            new_positions.extend(sel)
    return {"comment": base["comment"],
            "lattice": a_new,
            "elements": new_elements,
            "counts": new_counts,
            "positions": np.array(new_positions),
            "coord_type": "Direct",
            "scale": 1.0}


def write_poscar(info: dict, path: str):
    """Write a structure dict back out in VASP 5+ POSCAR format."""
    lat = info["lattice"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(info.get("comment", "supercell").strip() or "supercell")
        fh.write("\n")
        fh.write("  1.0\n")
        for v in lat:
            fh.write(f"  {v[0]:20.14f}  {v[1]:20.14f}  {v[2]:20.14f}\n")
        fh.write("  " + "  ".join(info["elements"]) + "\n")
        fh.write("  " + "  ".join(str(c) for c in info["counts"]) + "\n")
        fh.write("Selective dynamics\n" if False else "")
        fh.write(info["coord_type"] + "\n")
        for p in info["positions"]:
            fh.write(f"  {p[0]:20.14f}  {p[1]:20.14f}  {p[2]:20.14f}\n")
    print(f"  Wrote supercell with {sum(info['counts'])} atoms -> {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a supercell from a POSCAR.")
    parser.add_argument("file", help="Input POSCAR / CONTCAR")
    parser.add_argument("--matrix", "-m", required=True,
                        help='Expansion: "2 2 2" (diagonal) or 9 ints (3x3 matrix)')
    parser.add_argument("--output", "-o", default="SPOSCAR",
                        help="Output file (default: SPOSCAR)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    matrix = _parse_matrix(args.matrix)
    det = int(round(np.linalg.det(matrix)))
    print(f"Supercell matrix:\n{matrix}")
    print(f"Determinant (atom multiplier): {det}")
    info = build_supercell(args.file, matrix)
    write_poscar(info, args.output)
    print(f"Done. New lattice vectors:")
    for v in info["lattice"]:
        print(f"  [{v[0]:12.6f} {v[1]:12.6f} {v[2]:12.6f}]")


if __name__ == "__main__":
    main()
