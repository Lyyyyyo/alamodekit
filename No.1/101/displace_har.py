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
import alamodekit_io
alamodekit_io.ensure_package_root()

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
