#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esti_anhar.py
=============

Generate the ALM input file for fitting anharmonic force constants with a
user-chosen LASSO regularization strength (101-04). Read ``SPOSCAR`` and emit
``alm3.in`` in ``MODE = optimize`` using the adaptive-LASSO model with a
fixed ``L1_ALPHA`` (cross-validation is off).

Interactive parameters
----------------------
NORDER  : highest order (1 harmonic, 2 cubic, 3 quartic, ...)
NBODY   : body orders to consider
CUTOFF3 : 3rd-order cutoff radius (Angstrom)
CUTOFF4 : 4th-order cutoff radius (Angstrom)
L1_ALPHA: LASSO regularization strength (scientific notation accepted)

Outputs
-------
    alm3.in   ALM input file (PREFIX = Cu by default)
"""
from __future__ import annotations

import os
import sys

import alamodekit_io
alamodekit_io.ensure_package_root()

from alamode_input import (parse_poscar, write_namelist, cell_block_lines,
                           position_block_lines, ask_number, ask_int_list)


def main(poscar: str = "SPOSCAR", output: str = "alm3.in",
         prefix: str = "Cu") -> None:
    """Interactively build the anharmonic-fit (L1) ALM input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)

    print("=" * 60)
    print("ALM input generator - L1_ALPHA variant")
    print("=" * 60)
    print("Tip: press Enter to accept the bracketed default value.\n")

    norder = ask_number("Enter NORDER (1 harmonic, 2 cubic, 3 quartic)",
                        default=3, cast=int, validator=lambda v:
                        v >= 1 or print("  -> NORDER must be >= 1."))
    nbody = ask_int_list("Enter NBODY (e.g. 2 3 4)", default=[2, 3, 4])
    cutoff3 = ask_number("Enter 3rd-order cutoff (Angstrom)", default=15.0,
                         cast=float, validator=lambda v:
                         v > 0 or print("  -> must be > 0."))
    cutoff4 = ask_number("Enter 4th-order cutoff (Angstrom)", default=9.0,
                         cast=float, validator=lambda v:
                         v > 0 or print("  -> must be > 0."))
    l1_alpha = ask_number("Enter L1_ALPHA (LASSO regularization)",
                          default=1.0e-5, cast=float, validator=lambda v:
                          v >= 0 or print("  -> L1_ALPHA must be >= 0."))

    print("\n" + "=" * 60)
    print("Parameter confirmation:")
    print(f"  NORDER  = {norder}")
    print(f"  NBODY   = {' '.join(map(str, nbody))}")
    print(f"  cutoff3 = {cutoff3} A")
    print(f"  cutoff4 = {cutoff4} A")
    print(f"  L1_ALPHA= {l1_alpha}")
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
        # CV is removed; L1_ALPHA drives the optimization instead.
        ('optimize', [
            "\tLMODEL = adaptive-lasso",
            "\tDFSET = DFSET_AIMD_random",
            "\tFC2XML = IFC2.xml",
            f"\tL1_ALPHA = {l1_alpha}",
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
