#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
displace_har.py
===============

Generate the ALM input file for *suggesting* harmonic displacement patterns
(101-01). Read ``SPOSCAR`` and emit ``alm.in`` in ``MODE = suggest`` with
``NORDER = 1`` so ALM proposes the displacement directions for the harmonic
force-constant fit.

The user only needs ``SPOSCAR`` present; all remaining defaults are written
so that the generated input works out of the box (edit PREFIX / cutoff if
needed).

Outputs
-------
    alm.in   ALM input file (PREFIX = Cu by default)
"""
from __future__ import annotations

import os
import sys

# Resolve the toolkit root so the shared helpers import correctly.
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

from alamode_input import (parse_poscar, write_namelist,
                           cell_block_lines, position_block_lines)


def main(poscar: str = "SPOSCAR", output: str = "alm.in",
         prefix: str = "Cu") -> None:
    """Build the harmonic-suggest ALM input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)

    info = parse_poscar(poscar)
    nat = sum(info['atom_counts'])
    nkd = len(info['elements'])

    blocks = [
        ('general', [
            f"\tPREFIX = {prefix}",
            "\tMODE = suggest",
            f"\tNAT = {nat}; NKD = {nkd}",
            "\tKD = " + " ".join(info['elements']),
        ]),
        ('interaction', ["\tNORDER = 1"]),
        ('cell', cell_block_lines(info['cell'])),
        ('cutoff', ["\t*-* None"]),
        ('position', position_block_lines(info['positions'])),
    ]
    write_namelist(output, blocks)
    print(f"The input file '{output}' has been generated. "
          "Please modify the prefix and cutoff value if needed.")


if __name__ == '__main__':
    main()
