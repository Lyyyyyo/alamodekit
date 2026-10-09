#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alm_cv.py
=========

Generate the ALM input file for cross-validation (CV) of anharmonic force
constants (101-03). Read ``SPOSCAR`` and emit ``alm_cv.in`` in
``MODE = optimize`` with the adaptive-LASSO model and CV turned on.

Interactive parameters
----------------------
NORDER  : highest order of force constants (1 harmonic, 2 cubic, 3 quartic)
NBODY   : body orders to consider (e.g. "2 3 4")
CV      : cross-validation folds
CUTOFF3 : 3rd-order cutoff radius (Angstrom)
CUTOFF4 : 4th-order cutoff radius (Angstrom)

Outputs
-------
    alm_cv.in   ALM input file (PREFIX = Cu by default)
"""
from __future__ import annotations

import os
import sys

# --- Bootstrap: make the toolkit root importable when run as a script. ---
# When this file is executed directly, sys.path[0] is this script's own
# folder (No.X/<submenu>/), which does NOT contain the toolkit modules.
# Add the package root (two levels up) to sys.path *before* importing
# anything toolkit-level. Harmless when imported as a package module.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402

from alamode_input import (parse_poscar, write_namelist, cell_block_lines,
                           position_block_lines, ask_number, ask_int_list)


def main(poscar: str = "SPOSCAR", output: str = "alm_cv.in",
         prefix: str = "Cu") -> None:
    """Interactively build the CV ALM input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)

    print("=" * 60)
    print("ALM input generator - CV variant")
    print("=" * 60)
    print("Tip: press Enter to accept the bracketed default value.\n")

    norder = ask_number("Enter NORDER (1 harmonic, 2 cubic, 3 quartic)",
                        default=3, cast=int, validator=lambda v:
                        v >= 1 or print("  -> NORDER must be >= 1."))
    nbody = ask_int_list("Enter NBODY (e.g. 2 3 4)", default=[2, 3, 4])
    cv = ask_number("Enter CV (cross-validation folds)", default=2, cast=int,
                    validator=lambda v: v >= 2 or print("  -> CV must be >= 2."))
    cutoff3 = ask_number("Enter 3rd-order cutoff (Angstrom)", default=15.0,
                         cast=float, validator=lambda v:
                         v > 0 or print("  -> must be > 0."))
    cutoff4 = ask_number("Enter 4th-order cutoff (Angstrom)", default=9.0,
                         cast=float, validator=lambda v:
                         v > 0 or print("  -> must be > 0."))

    print("\n" + "=" * 60)
    print("Parameter confirmation:")
    print(f"  NORDER  = {norder}")
    print(f"  NBODY   = {' '.join(map(str, nbody))}")
    print(f"  CV      = {cv}")
    print(f"  cutoff3 = {cutoff3} A")
    print(f"  cutoff4 = {cutoff4} A")
    print("=" * 60 + "\n")

    info = parse_poscar(poscar)
    nat = sum(info['atom_counts'])
    nkd = len(info['elements'])

    blocks = [
        ('general', [
            f"\tPREFIX = {prefix}",
            "\tMODE = optimize",
            f"\tNAT = {nat}; NKD = {nkd}",
            "\tKD = " + " ".join(info['elements']),
        ]),
        ('interaction', [
            f"\tNORDER = {norder}  # 1: harmonic, 2: cubic, 3: quartic, ..",
            f"\tNBODY = {' '.join(map(str, nbody))}",
        ]),
        ('cell', cell_block_lines(info['cell'])),
        ('cutoff', [f"\t*-* None {cutoff3:.1f} {cutoff4:.1f}"]),
        ('position', position_block_lines(info['positions'])),
        ('optimize', [
            "\tLMODEL = adaptive-lasso",
            "\tDFSET = DFSET_AIMD_random",
            f"\tCV = {cv}  # split DFSET into {cv + 2} sets and run CV",
            "\tFC2XML = IFC2.xml",
            "\tL1_RATIO = 1.0  # LASSO",
            "\tCV_MINALPHA = 1.0e-8",
            "\tCV_MAXALPHA = 0.01",
            "\tCV_NALPHA = 100",
            "\tSTANDARDIZE = 1",
            "\tCONV_TOL = 1.0e-8",
        ]),
    ]
    write_namelist(output, blocks)
    print(f"The input file '{output}' has been generated. "
          "Please remember to adjust the PREFIX value.")


if __name__ == '__main__':
    main()
