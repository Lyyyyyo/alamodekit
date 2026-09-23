#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ase_bridge.py
=============

Helper: optional bridge to the Atomic Simulation Environment (ASE).

ASE is a widely used, open-source (LGPL) Python library for atomistic
simulations. When it is installed, it unlocks a lot of extra analysis that
would otherwise require a lot of code: space-group detection, symmetry
finding, primitive/conventional-cell conversion, neighbour analysis, etc.

This tool is a *soft dependency*: it imports ASE lazily and gives a clear
message if ASE is not available, so the rest of the toolkit still works on
machines without ASE.

Currently it wraps the most commonly useful operations:

  * ``--spacegroup`` : print the space-group number / symbol of a POSCAR,
  * ``--primitive``  : write the primitive cell,
  * ``--conventional``: write the conventional (standardised) cell,
  * ``--neighbours``  : print neighbour shells around each site,
  * ``--reduced``     : write a symmetry-reduced (symmetrised) structure.

Install ASE separately if you want to use this tool:
    pip install ase spglib

Usage
-----
    python ase_bridge.py POSCAR --spacegroup
    python ase_bridge.py POSCAR --primitive -o PRIMCELL
"""
from __future__ import annotations

import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


def _parse_poscar_basic(path):
    """Minimal POSCAR reader used as an spglib-only fallback (no ASE).

    Returns (lattice 3x3, scaled_positions Nx3, atomic_numbers list).
    """
    import numpy as np
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    scale = float(lines[1].split()[0])
    lattice = np.array([[float(x) for x in lines[i].split()[:3]]
                        for i in range(2, 5)]) * scale
    idx = 5
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    elements = []
    try:
        counts = [int(x) for x in lines[idx].split()]
    except ValueError:
        elements = lines[idx].split()
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        counts = [int(x) for x in lines[idx].split()]
    if not elements:
        elements = [f"El{i+1}" for i in range(len(counts))]
    idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if lines[idx].strip().lower().startswith("s"):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    coord_type = lines[idx].strip()
    idx += 1
    n = sum(counts)
    labels = []
    for el, c in zip(elements, counts):
        labels += [el] * c
    pos = []
    for i in range(n):
        parts = lines[idx + i].split()
        pos.append([float(parts[0]), float(parts[1]), float(parts[2])])
    pos = np.array(pos)
    if coord_type.lower().startswith("d"):
        scaled = pos
    else:
        scaled = pos @ np.linalg.inv(lattice).T
    from_els = {"H":1,"He":2,"Li":3,"Be":4,"B":5,"C":6,"N":7,"O":8,"F":9,"Ne":10,
                "Na":11,"Mg":12,"Al":13,"Si":14,"P":15,"S":16,"Cl":17,"Ar":18,
                "K":19,"Ca":20,"Sc":21,"Ti":22,"V":23,"Cr":24,"Mn":25,"Fe":26,
                "Co":27,"Ni":28,"Cu":29,"Zn":30,"Ga":31,"Ge":32,"As":33,"Se":34,
                "Br":35,"Kr":36,"Rb":37,"Sr":38,"Y":39,"Zr":40,"Nb":41,"Mo":42,
                "Tc":43,"Ru":44,"Rh":45,"Pd":46,"Ag":47,"Cd":48,"In":49,"Sn":50,
                "Sb":51,"Te":52,"I":53,"Xe":54,"Cs":55,"Ba":56,"La":57,"Ce":58,
                "Pr":59,"Nd":60,"Pm":61,"Sm":62,"Eu":63,"Gd":64,"Tb":65,"Dy":66,
                "Ho":67,"Er":68,"Tm":69,"Yb":70,"Lu":71,"Hf":72,"Ta":73,"W":74,
                "Re":75,"Os":76,"Ir":77,"Pt":78,"Au":79,"Hg":80,"Tl":81,"Pb":82,
                "Bi":83,"Po":84,"At":85,"Rn":86}
    numbers = [from_els.get(el, 0) for el in labels]
    return lattice, scaled, numbers


def _require_ase():
    """Import and return (ase.io.read module, spglib); exit if unavailable."""
    try:
        from ase.io import read as ase_read
        import spglib
        return ase_read, spglib
    except ImportError as exc:
        print("This tool needs the optional 'ase' and 'spglib' packages.")
        print("Install them with:  pip install ase spglib")
        print(f"(import error: {exc})")
        sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ASE-powered structure analysis (optional dependency).")
    parser.add_argument("file", help="POSCAR / CONTCAR / cif / ... (any ASE format)")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--spacegroup", action="store_true",
                   help="Print the space-group number and symbol")
    g.add_argument("--primitive", action="store_true",
                   help="Write the primitive cell")
    g.add_argument("--conventional", action="store_true",
                   help="Write the conventional standardised cell")
    g.add_argument("--neighbours", action="store_true",
                   help="Print neighbour shells around each site")
    g.add_argument("--reduced", action="store_true",
                   help="Write a symmetry-reduced (symmetrised) structure")
    parser.add_argument("--output", "-o", default="ASE_out",
                        help="Output base name for cell writers")
    parser.add_argument("--cutoff", type=float, default=3.5,
                        help="Neighbour cutoff for --neighbours (Angstrom)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)

    # Try to load the optional ASE first; it supports every input format.
    have_ase = True
    try:
        from ase.io import read as ase_read
    except ImportError:
        have_ase = False
    # spglib is needed for every mode.
    try:
        import spglib
    except ImportError:
        print("This tool needs at least spglib (pip install spglib).")
        print("For non-POSCAR formats also install ase (pip install ase).")
        sys.exit(2)

    if args.spacegroup:
        # space-group detection works with just spglib + a POSCAR reader.
        if have_ase:
            atoms = ase_read(args.file)
            cell = (atoms.get_cell(), atoms.get_scaled_positions(),
                    atoms.get_atomic_numbers())
        else:
            lattice, scaled, numbers = _parse_poscar_basic(args.file)
            cell = (lattice, scaled, numbers)
        sg = spglib.get_spacegroup(cell, symprec=1e-5)
        # spglib >=2 removed get_dataset; use get_symmetry_dataset and
        # get_spacegroup_type_from_symmetry as a version-agnostic fallback.
        ds = None
        if hasattr(spglib, "get_dataset"):
            ds = spglib.get_dataset(cell, symprec=1e-5)
        elif hasattr(spglib, "get_symmetry_dataset"):
            ds = spglib.get_symmetry_dataset(cell, symprec=1e-5)
        print("=" * 50)
        print(f"Space group : {sg}")
        if ds is not None:
            number = getattr(ds, "number", None) or getattr(ds, "spacegroup_number", None)
            intl = (getattr(ds, "international", None)
                    or getattr(ds, "international_symbol", None))
            if intl is None and number is not None and hasattr(spglib, "get_spacegroup_type"):
                try:
                    intl = spglib.get_spacegroup_type(number).international_short
                except Exception:
                    intl = None
            hall = getattr(ds, "hall", None) or getattr(ds, "hall_symbol", None)
            pg = getattr(ds, "pointgroup", None)
            if number is not None:
                print(f"Number      : {number}")
            if intl:
                print(f"Intl tables : {intl}")
            if hall:
                print(f"Hall symbol  : {hall}")
            if pg:
                print(f"Point group  : {pg}")
        if not have_ase:
            print("(via built-in POSCAR reader + spglib; install 'ase' for "
                  "other formats)")
        print("=" * 50)
        return

    # The remaining modes need ASE.
    if not have_ase:
        print("This action needs the optional 'ase' package.")
        print("Install it with:  pip install ase")
        sys.exit(2)
    atoms = ase_read(args.file)

    if args.primitive:
        cell = (atoms.get_cell(), atoms.get_scaled_positions(),
                atoms.get_atomic_numbers())
        lattice, positions, numbers = spglib.find_primitive(cell, symprec=1e-5)
        if lattice is None:
            print("Could not find a primitive cell."); sys.exit(1)
        from ase import Atoms
        prim = Atoms(cell=lattice, scaled_positions=positions, numbers=numbers)
        out = args.output + "_primitive.vasp"
        from ase.io import write
        write(out, prim, format="vasp")
        print(f"  Wrote primitive cell ({len(prim)} atoms) -> {out}")

    elif args.conventional:
        cell = (atoms.get_cell(), atoms.get_scaled_positions(),
                atoms.get_atomic_numbers())
        lattice, positions, numbers = spglib.standardize_cell(
            cell, to_primitive=False, symprec=1e-5)
        if lattice is None:
            print("Could not standardise the cell."); sys.exit(1)
        from ase import Atoms
        conv = Atoms(cell=lattice, scaled_positions=positions, numbers=numbers)
        out = args.output + "_conventional.vasp"
        from ase.io import write
        write(out, conv, format="vasp")
        print(f"  Wrote conventional cell ({len(conv)} atoms) -> {out}")

    elif args.neighbours:
        from ase.neighborlist import neighbor_list
        i, j, d = neighbor_list("ijd", atoms, args.cutoff)
        print("=" * 50)
        print(f"Neighbours within {args.cutoff} Angstrom:")
        sym = atoms.get_chemical_symbols()
        for idx in range(len(atoms)):
            mask = i == idx
            if not mask.any():
                continue
            neigh = sorted(zip(d[mask], j[mask]))
            desc = ", ".join(f"{sym[j]:>2}@{dist:.3f}" for dist, j in neigh)
            print(f"  atom {idx+1:>3} ({sym[idx]:>2}) -> {desc}")
        print("=" * 50)

    elif args.reduced:
        cell = (atoms.get_cell(), atoms.get_scaled_positions(),
                atoms.get_atomic_numbers())
        lattice, positions, numbers = spglib.refine_cell(cell, symprec=1e-5)
        if lattice is None:
            print("Could not refine the cell."); sys.exit(1)
        from ase import Atoms
        refined = Atoms(cell=lattice, scaled_positions=positions, numbers=numbers)
        out = args.output + "_refined.vasp"
        from ase.io import write
        write(out, refined, format="vasp")
        print(f"  Wrote symmetry-refined cell -> {out}")


if __name__ == "__main__":
    main()
