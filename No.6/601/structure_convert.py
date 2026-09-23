#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
structure_convert.py
====================

Pre-processing helper: convert a crystal structure between common DFT input
formats.

ALAMODE supports several DFT codes (VASP, Quantum ESPRESSO, xTAPP, LOKI,
OpenMX). The equilibrium structure therefore may arrive in different
formats. This tool converts a structure between the most common ones using
only numpy:

  * VASP POSCAR  <->  Quantum ESPRESSO pw.x input (ATOMIC_POSITIONS)

Both directions are supported; the format is inferred from the input file
when possible, otherwise the ``--from`` flag sets it explicitly.

Pure-Python; reads/writes text only.

Usage
-----
    python structure_convert.py POSCAR --to qe -o prefix.pw.in
    python structure_convert.py prefix.pw.in --to poscar -o POSCAR_new
"""
from __future__ import annotations

import os
import sys
import re
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
# Import parse_poscar / ATOMIC_MASSES in a way that works both when this file
# is run as a top-level script (``python structure_convert.py``) and when it
# is imported as a package module (``analyzers.structure_convert``).
try:  # package-relative import (used by the GUI / pyinstaller)
    from .poscar_info import parse_poscar, ATOMIC_MASSES  # type: ignore
except ImportError:  # top-level script execution
    from poscar_info import parse_poscar, ATOMIC_MASSES  # noqa: E402


def _detect_format(path: str) -> str:
    """Guess 'poscar' or 'qe' from file content."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        head = fh.read(4096)
    low = head.lower()
    if "atomic_positions" in low or "&control" in low or "ibrav" in low:
        return "qe"
    # VASP: line 1 comment, line 2 scale, lines 3-5 three floats each.
    lines = [ln for ln in head.splitlines() if ln.strip()]
    if len(lines) >= 5:
        try:
            float(lines[1].split()[0])
            for i in range(2, 5):
                [float(x) for x in lines[i].split()[:3]]
            return "poscar"
        except (ValueError, IndexError):
            pass
    raise ValueError("Could not detect input format; use --from to set it.")


def parse_qe(path: str) -> dict:
    """Parse a Quantum ESPRESSO pw.x input into a structure dict."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    def find(pattern, default=""):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default
    # ibrav must be 0 (CELL_PARAMETERS given explicitly).
    ibrav = find(r"ibrav\s*=\s*(\S+)", "0")
    if ibrav != "0":
        raise ValueError("Only ibrav = 0 (CELL_PARAMETERS) is supported.")
    # CELL_PARAMETERS block: optional alat, then 3 lattice vectors (in Bohr or
    # alat units depending on the first token).
    m = re.search(r"CELL_PARAMETERS\s*(\S*)\s*\n(.*?)\n\s*(?:ATOMIC|ATOMIC_SPECIES|K_POINTS|\Z)",
                  text, re.IGNORECASE | re.DOTALL)
    if not m:
        raise ValueError("CELL_PARAMETERS block not found.")
    units = m.group(1).strip().lower()
    rows = [ln.split() for ln in m.group(2).splitlines() if ln.strip()]
    lattice = np.array([[float(x) for x in r[:3]] for r in rows[:3]])
    # Convert to Angstrom. QE bohr = 0.5291772 Angstrom.
    if units in ("", "bohr"):
        lattice = lattice * 0.5291772
    elif units == "angstrom":
        pass
    elif units == "alat":
        # alat is in Bohr; the celldm(1) would define it. Rare here; assume Bohr.
        lattice = lattice * 0.5291772
    # ATOMIC_POSITIONS: detect units.
    m = re.search(r"ATOMIC_POSITIONS\s*\(?\s*(\w*)\s*\)?\s*\n(.*?)(?:K_POINTS|\Z)",
                  text, re.IGNORECASE | re.DOTALL)
    pos_units = (m.group(1).strip().lower() if m and m.group(1) else "alat")
    atoms = []
    if m:
        for ln in m.group(2).splitlines():
            t = ln.split()
            if len(t) >= 4 and t[0][0].isalpha():
                atoms.append((t[0], [float(x) for x in t[1:4]]))
    if not atoms:
        raise ValueError("ATOMIC_POSITIONS block not found or empty.")
    # Group atoms by element preserving order, then collect positions.
    elements, counts, positions = [], [], []
    current = None
    for el, p in atoms:
        if el != current:
            elements.append(el)
            counts.append(1)
            current = el
        else:
            counts[-1] += 1
        positions.append(p)
    # QE 'crystal' means fractional; 'alat'/'bohr'/'angstrom' are Cartesian.
    coord_type = "Direct" if pos_units in ("crystal",) else "Cartesian"
    return {"comment": "from QE input", "scale": 1.0,
            "lattice": lattice, "elements": elements, "counts": counts,
            "coord_type": coord_type, "positions": np.array(positions)}


def write_poscar(info: dict, path: str):
    """Write a structure dict as a VASP 5+ POSCAR (fractional coords)."""
    inv = np.linalg.inv(info["lattice"])
    frac = info["positions"] @ inv.T
    frac = frac - np.floor(frac)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write((info.get("comment") or "converted").strip() + "\n")
        fh.write("  1.0\n")
        for v in info["lattice"]:
            fh.write(f"  {v[0]:20.14f}  {v[1]:20.14f}  {v[2]:20.14f}\n")
        fh.write("  " + "  ".join(info["elements"]) + "\n")
        fh.write("  " + "  ".join(str(c) for c in info["counts"]) + "\n")
        fh.write("Direct\n")
        for p in frac:
            fh.write(f"  {p[0]:20.14f}  {p[1]:20.14f}  {p[2]:20.14f}\n")
    print(f"  Wrote POSCAR -> {path}")


def write_qe(info: dict, path: str, prefix: str = "alamode"):
    """Write a structure dict as a minimal QE pw.x input (Angstrom)."""
    inv = np.linalg.inv(info["lattice"])
    # Cartesian positions in Angstrom for the &system ATOMIC_POSITIONS angstrom.
    cart = info["positions"] @ info["lattice"] if info["coord_type"] == "Direct" \
        else info["positions"]
    masses = [ATOMIC_MASSES.get(e, 0.0) for e in info["elements"]]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("&CONTROL\n  prefix = '" + prefix + "',\n  calculation = 'scf',\n/\n")
        fh.write("&SYSTEM\n  ibrav = 0,\n  nat = " + str(sum(info["counts"])) + ",\n")
        fh.write("  ntyp = " + str(len(info["elements"])) + ",\n  ecutwfc = 60.0,\n/\n")
        fh.write("&ELECTRONS\n  conv_thr = 1.0d-8,\n/\n")
        fh.write("ATOMIC_SPECIES\n")
        for el, m in zip(info["elements"], masses):
            fh.write(f"  {el:<3} {m:.4f} {el}.UPF\n")
        fh.write("ATOMIC_POSITIONS angstrom\n")
        i = 0
        for el, c in zip(info["elements"], info["counts"]):
            for _ in range(c):
                p = cart[i]
                fh.write(f"  {el:<3} {p[0]:16.10f} {p[1]:16.10f} {p[2]:16.10f}\n")
                i += 1
        fh.write("CELL_PARAMETERS angstrom\n")
        for v in info["lattice"]:
            fh.write(f"  {v[0]:16.10f} {v[1]:16.10f} {v[2]:16.10f}\n")
        fh.write("K_POINTS automatic\n  4 4 4 0 0 0\n")
    print(f"  Wrote QE pw.in -> {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert between POSCAR and QE pw.in.")
    parser.add_argument("file", help="Input structure file")
    parser.add_argument("--from", dest="from_fmt", default=None,
                        choices=["poscar", "qe"], help="Input format (auto-detected)")
    parser.add_argument("--to", dest="to_fmt", required=True,
                        choices=["poscar", "qe"], help="Output format")
    parser.add_argument("--output", "-o", default=None, help="Output file")
    parser.add_argument("--prefix", default="alamode", help="QE prefix (qe output)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    src_fmt = args.from_fmt or _detect_format(args.file)
    print(f"Input format: {src_fmt}")
    if src_fmt == "poscar":
        info = parse_poscar(args.file)
    else:
        info = parse_qe(args.file)
    out = args.output or ("converted.pw.in" if args.to_fmt == "qe" else "POSCAR_new")
    if args.to_fmt == "poscar":
        write_poscar(info, out)
    else:
        write_qe(info, out, prefix=args.prefix)
    print("Done.")


if __name__ == "__main__":
    main()
