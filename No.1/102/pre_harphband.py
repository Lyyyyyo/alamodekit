#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_harphband.py
================

Generate the ANPHON input file for the harmonic phonon *band* calculation
(102-01). Read ``POSCAR-unitcell`` and ``KPATH.in`` and emit ``phband.in``
in ``MODE = phonons`` with the high-symmetry path expanded by ALAMODE.

Outputs
-------
    phband.in   ANPHON input file (PREFIX = Ca by default)
"""
from __future__ import annotations

import os
import sys

import alamodekit_io
alamodekit_io.ensure_package_root()

from alamode_input import (parse_poscar, write_namelist, cell_block_lines,
                           read_kpath)


def main(poscar: str = "POSCAR-unitcell", kpath: str = "KPATH.in",
         output: str = "phband.in", prefix: str = "Ca",
         fcsxml: str = "Ca.xml") -> None:
    """Build the harmonic phonon-band ANPHON input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)
    if not os.path.isfile(kpath):
        print(f"Error: {kpath} not found in the current directory.")
        sys.exit(1)

    info = parse_poscar(poscar)
    segments = read_kpath(kpath)

    print("Generated k-path segments:")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}: {seg.strip()}")

    blocks = [
        ('general', [
            f"\tPREFIX = {prefix}",
            "\tMODE = phonons",
            f"\tFCSXML = {fcsxml}",
            f"\tNKD = {len(info['elements'])}; KD = " + " ".join(info['elements']),
        ]),
        ('interaction', ["\tNORDER = 1"]),
        ('cell', cell_block_lines(info['cell'])),
        ('kpoint', ["\t1"] + segments),
        ('analysis', ["\tPRINTVEL = 1"]),
    ]
    write_namelist(output, blocks)
    print(f"The input file '{output}' has been generated. "
          "Please modify the prefix and FCSXML.")


if __name__ == '__main__':
    main()
