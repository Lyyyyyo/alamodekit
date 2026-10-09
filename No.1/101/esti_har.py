#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esti_har.py
===========

Generate the ALM input file for *fitting* the harmonic (2nd-order) force
constants (101-02). Read ``SPOSCAR`` and emit ``alm2.in`` in
``MODE = optimize`` reading the displacement/force data from ``DFSET_harmonic``.

The user needs ``SPOSCAR`` plus a displacement-force dataset named
``DFSET_harmonic``. All defaults are chosen to make the generated input
immediately runnable; edit PREFIX / DFSET if your files use other names.

Outputs
-------
    alm2.in   ALM input file (PREFIX = Cu by default)
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

from alamode_input import (parse_poscar, write_namelist,
                           cell_block_lines, position_block_lines)


def main(poscar: str = "SPOSCAR", output: str = "alm2.in",
         prefix: str = "Cu", dfset: str = "DFSET_harmonic") -> None:
    """Build the harmonic-fit (optimize) ALM input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)

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
        ('optimize', [f"\tDFSET = {dfset}"]),
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
