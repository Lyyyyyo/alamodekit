#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_born.py
===============

Helper: extract the macroscopic dielectric tensor and Born effective charges
from a DFT output file and write a NAC (non-analytic correction) parameter
file in the format expected by either ALAMODE or Phonopy.

Both codes read essentially the same data:

  * the 3x3 dielectric tensor (electronic contribution), and
  * a 3x3 Born effective charge tensor Z* for every atom, in the atom order
    of the input structure.

ALAMODE's BORN file (read by ``load_born`` in dynamical.cpp) is a plain
stream of numbers: 9 dielectric entries (row-major) followed by 9 entries
per atom (row-major Born charge). Phonopy's BORN file uses the same data
laid out as a comment line + 3 dielectric rows + 3 charge rows per atom.

This tool parses VASP OUTCAR or Quantum ESPRESSO output (both of which are
public, documented output formats), reports what it found, and writes the
NAC file in the format(s) you request. It contains no DFT solver source.

Usage
-----
    python extract_born.py --source vasp --outcar OUTCAR --format both
    python extract_born.py --source qe --qeout pw.out --format alamode \\
        --nat 8
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
# VASP OUTCAR parser.
# --------------------------------------------------------------------------- #
def parse_vasp(outcar: str):
    """Parse a VASP OUTCAR for the dielectric tensor and Born charges.

    Returns (dielec 3x3, born list of 3x3, n_atoms). The *last* occurrence of
    each block is used (relevant when several ionic steps are stored).
    """
    with open(outcar, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    # --- Born effective charges: blocks of the form
    #     "Born effective charge matrices"
    #     ion   1
    #        1   xx xy xz
    #        2   yx yy yz
    #        3   zx zy zz
    #     ion   2
    #        ...
    born_blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if "Born effective charge matrices" in lines[i]:
            i += 1
            # skip a dashed separator line if present
            while i < len(lines) and ("---" in lines[i] or not lines[i].strip()):
                i += 1
            block = []
            while i < len(lines):
                ln = lines[i]
                s = ln.strip()
                if s.startswith("ion"):
                    # start of an atom's 3x3 block
                    i += 1
                    rows = []
                    while i < len(lines) and len(rows) < 3:
                        t = lines[i].split()
                        # Each data row starts with an index (1/2/3) then 3 floats.
                        if len(t) >= 4:
                            try:
                                idx = int(t[0])
                                rows.append([float(t[1]), float(t[2]), float(t[3])])
                            except ValueError:
                                break
                        else:
                            break
                        i += 1
                    if len(rows) == 3:
                        block.append(np.array(rows))
                else:
                    break
            if block:
                born_blocks.append(block)
        else:
            i += 1

    if not born_blocks:
        raise ValueError("No 'Born effective charge matrices' block found in OUTCAR. "
                         "Run VASP with LEPSILON=.TRUE. or IBRION=6/7/8.")
    born = born_blocks[-1]  # last (converged) block

    # --- Dielectric tensor: prefer the electronic one
    #     "MACROSCOPIC STATIC DIELECTRIC TENSOR"  (electronic, no IONIC)
    #     "MACROSCOPIC STATIC DIELECTRIC TENSOR IONIC CONTRIBUTION"
    dielec_elec = None
    dielec_ionic = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if "MACROSCOPIC STATIC DIELECTRIC TENSOR" in ln:
            is_ionic = "IONIC" in ln
            # next non-empty lines: a separator, then 3 rows of 3 floats.
            j = i + 1
            while j < len(lines) and ("---" in lines[j] or not lines[j].strip()):
                j += 1
            rows = []
            while j < len(lines) and len(rows) < 3:
                t = lines[j].split()
                if len(t) >= 3:
                    try:
                        rows.append([float(t[0]), float(t[1]), float(t[2])])
                    except ValueError:
                        break
                else:
                    break
                j += 1
            if len(rows) == 3:
                if is_ionic:
                    dielec_ionic = np.array(rows)
                else:
                    dielec_elec = np.array(rows)
            i = j
        else:
            i += 1

    # Default to the total dielectric (electronic + ionic) when both are
    # available; this is what the NAC needs in a DFPT (IBRION=6/7/8) run.
    # In a LEPSILON run only the electronic block exists, which is then used.
    if dielec_elec is not None and dielec_ionic is not None:
        dielec = dielec_elec + dielec_ionic
        total = dielec
    elif dielec_elec is not None:
        dielec = dielec_elec
        total = None
    elif dielec_ionic is not None:
        dielec = dielec_ionic
        total = None
    else:
        raise ValueError("No 'MACROSCOPIC STATIC DIELECTRIC TENSOR' found in OUTCAR.")

    if dielec_ionic is not None and dielec_elec is not None:
        # Report the total as well; some workflows prefer eps_elec + eps_ionic.
        total = dielec_elec + dielec_ionic
    else:
        total = None
    return dielec, born, len(born), dielec_elec, dielec_ionic


# --------------------------------------------------------------------------- #
# Quantum ESPRESSO output parser.
# --------------------------------------------------------------------------- #
def parse_qe(qeout: str, nat: int | None):
    """Parse a QE pw.x output for the dielectric tensor and Born charges.

    QE prints these when ``lepsilon=.true.``:
      * "Dielectric constant in cartesian axis"
      * "Born Effective Charges in cartesian axis (d Force / d E)"
    """
    with open(qeout, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    # Dielectric tensor: lines after the header, 3 rows of 3 floats.
    dielec = None
    for i, ln in enumerate(lines):
        if "Dielectric constant in cartesian axis" in ln:
            rows = []
            j = i + 1
            while j < len(lines) and len(rows) < 3:
                t = lines[j].split()
                if len(t) >= 3:
                    try:
                        rows.append([float(t[0]), float(t[1]), float(t[2])])
                    except ValueError:
                        pass
                j += 1
            if len(rows) == 3:
                dielec = np.array(rows)
                break

    # Born charges: blocks of
    #   "atom   1  ... "  then " ... ex       ( ... )" lines (3 per atom).
    born = []
    for i, ln in enumerate(lines):
        if "Born Effective Charges" in ln:
            j = i + 1
            while j < len(lines) and len(born) < (nat or 9999):
                if lines[j].strip().startswith("atom"):
                    rows = []
                    k = j + 1
                    while k < len(lines) and len(rows) < 3:
                        t = lines[k].replace("(", " ").replace(")", " ").split()
                        # row like:  ex  2.5 (...)
                        if len(t) >= 2:
                            try:
                                rows.append([float(t[1]), float(t[2]), float(t[3])])
                            except (ValueError, IndexError):
                                pass
                        k += 1
                    if len(rows) == 3:
                        born.append(np.array(rows))
                    j = k
                else:
                    j += 1
            break

    if dielec is None:
        raise ValueError("No dielectric tensor found in QE output "
                         "(need lepsilon=.true.).")
    if not born:
        raise ValueError("No Born effective charges found in QE output.")
    if nat and nat != len(born):
        print(f"Warning: --nat={nat} but {len(born)} Born charge blocks found; "
              f"using {len(born)}.")
    return dielec, born, len(born), None, None


# --------------------------------------------------------------------------- #
# Output writers.
# --------------------------------------------------------------------------- #
def write_alamode(dielec, born, path: str):
    """Write the ALAMODE BORN file: 9 dielectric + 9*per-atom numbers."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# ALAMODE BORN file: dielectric tensor (3x3, row-major) "
                 "then Born charges (3x3 per atom, row-major)\n")
        for row in dielec:
            fh.write("  " + "  ".join(f"{v:16.10f}" for v in row) + "\n")
        for z in born:
            for row in z:
                fh.write("  " + "  ".join(f"{v:16.10f}" for v in row) + "\n")
    print(f"  Wrote ALAMODE BORN  -> {path}  ({len(born)} atoms)")


def write_phonopy(dielec, born, path: str):
    """Write the Phonopy BORN file: comment + 3 dielectric rows + 3*per-atom."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Dielectric tensor and Born effective charges "
                 "(from extract_born.py)\n")
        for row in dielec:
            fh.write("  " + "  ".join(f"{v:16.10f}" for v in row) + "\n")
        for z in born:
            for row in z:
                fh.write("  " + "  ".join(f"{v:16.10f}" for v in row) + "\n")
    print(f"  Wrote Phonopy BORN -> {path}  ({len(born)} atoms)")


def report(dielec, born, dielec_elec, dielec_ionic):
    print("=" * 60)
    print("Dielectric tensor (Cartesian):")
    for row in dielec:
        print("  " + "  ".join(f"{v:10.5f}" for v in row))
    if dielec_elec is not None and dielec_ionic is not None:
        print("  (electronic)")
        for row in dielec_elec:
            print("    " + "  ".join(f"{v:9.4f}" for v in row))
        print("  (ionic)")
        for row in dielec_ionic:
            print("    " + "  ".join(f"{v:9.4f}" for v in row))
        print("  (total = electronic + ionic)")
        for row in (dielec_elec + dielec_ionic):
            print("    " + "  ".join(f"{v:9.4f}" for v in row))
    print("-" * 60)
    print(f"Born effective charges: {len(born)} atoms")
    for i, z in enumerate(born):
        print(f"  atom {i+1}:")
        for row in z:
            print("    " + "  ".join(f"{v:9.4f}" for v in row))
    print("=" * 60)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract dielectric tensor + Born charges to a NAC file.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--outcar", help="VASP OUTCAR file")
    g.add_argument("--qeout", help="Quantum ESPRESSO pw.x output file")
    parser.add_argument("--format", default="both",
                        choices=["alamode", "phonopy", "both"],
                        help="Output format (default: both)")
    parser.add_argument("--nat", type=int, default=None,
                        help="Expected number of atoms (QE only, optional)")
    parser.add_argument("--output", "-o", default="BORN",
                        help="Output base name (default: BORN)")
    args = parser.parse_args(argv if argv is not None else None)

    if args.outcar:
        if not os.path.isfile(args.outcar):
            print(f"Error: OUTCAR '{args.outcar}' not found."); sys.exit(1)
        dielec, born, _, de, di = parse_vasp(args.outcar)
    else:
        if not os.path.isfile(args.qeout):
            print(f"Error: QE output '{args.qeout}' not found."); sys.exit(1)
        dielec, born, _, de, di = parse_qe(args.qeout, args.nat)

    report(dielec, born, de, di)
    if args.format in ("alamode", "both"):
        write_alamode(dielec, born, args.output)
    if args.format in ("phonopy", "both"):
        write_phonopy(dielec, born, args.output + "_phonopy")
    print("Done.")


if __name__ == "__main__":
    main()
