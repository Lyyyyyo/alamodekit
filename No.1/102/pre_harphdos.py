#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_harphdos.py
===============

Generate the ANPHON input file for the harmonic phonon *density of states*
calculation (102-02). Read ``POSCAR-unitcell`` and emit ``phdos.in`` in
``MODE = phonons`` using a uniform q-point mesh.

Interactive parameters
----------------------
KPMODE : k-point mesh mode (recommended 2 = uniform mesh)
KMESH  : 3 integers giving the mesh density, e.g. "20 20 20"

Outputs
-------
    phdos.in   ANPHON input file (PREFIX = Ca by default)
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
                           ask_number, ask_int_list)


def main(poscar: str = "POSCAR-unitcell", output: str = "phdos.in",
         prefix: str = "Ca", fcsxml: str = "Ca.xml") -> None:
    """Build the harmonic phonon-DOS ANPHON input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)

    info = parse_poscar(poscar)

    # Uniform-mesh k-point settings (KPMODE = 2 is the recommended uniform mode).
    kpmode = ask_number("Enter KPMODE (recommended 2 = uniform mesh)",
                        default=2, cast=int)
    kmesh = ask_int_list("Enter k-mesh (3 integers, e.g. 20 20 20)",
                         length=3)

    blocks = [
        ('general', [
            f"\tPREFIX = {prefix}",
            "\tMODE = phonons",
            f"\tFCSXML = {fcsxml}",
            f"\tNKD = {len(info['elements'])}; KD = " + " ".join(info['elements']),
        ]),
        # NOTE: ANPHON has no &interaction namelist; the FC expansion order is
        # carried by FCSXML/FC2XML, not by NORDER (an ALM-only keyword).
        ('cell', cell_block_lines(info['cell'])),
        ('kpoint', [
            f"\t{kpmode}  # KPMODE = {kpmode}: uniform mesh mode",
            "\t" + " ".join(map(str, kmesh)),
        ]),
        ('analysis', ["\tPRINTVEL = 1"]),
    ]
    write_namelist(output, blocks)
    print(f"The input file '{output}' has been generated. "
          "Please modify the prefix and FCSXML.")
    print(f"K-path settings: KPMODE = {kpmode}, KMESH = {kmesh[0]} {kmesh[1]} {kmesh[2]}")


if __name__ == '__main__':
    main()
