#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_scph.py
===========

Generate the ANPHON input file for a self-consistent phonon (SCPH)
calculation (102-03). Read ``POSCAR-unitcell`` and ``KPATH.in`` and emit
``scph.in`` in ``MODE = SCPH``, including the temperature grid and the
``&scph`` control block.

Interactive parameters (press Enter for defaults)
-------------------------------------------------
TMIN, TMAX, DT              temperature grid
SELF_OFFDIAG, BUBBLE        SCPH switches
MAXITER, MIXALPHA           iteration control
KMESH_INTERPOLATE, KMESH_SCPH  k-point meshes

Outputs
-------
    scph.in   ANPHON input file (PREFIX = Ca by default)
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
                           read_kpath)


def _ask(prompt: str, default: str) -> str:
    """Ask for a token with a default; returns the default on empty input."""
    raw = input(f"{prompt} [default: {default}]: ").strip()
    return raw if raw else default


def main(poscar: str = "POSCAR-unitcell", kpath: str = "KPATH.in",
         output: str = "scph.in", prefix: str = "Ca",
         fcsxml: str = "Ca.xml", fc2xml: str = "A_har.xml") -> None:
    """Build the SCPH ANPHON input file."""
    if not os.path.isfile(poscar):
        print(f"Error: {poscar} not found in the current directory.")
        sys.exit(1)
    if not os.path.isfile(kpath):
        print(f"Error: {kpath} not found in the current directory.")
        sys.exit(1)

    info = parse_poscar(poscar)
    segments = read_kpath(kpath)

    print("\nEnter the following parameters (Enter to accept default):")
    tmin = _ask("TMIN", "0")
    tmax = _ask("TMAX", "1000")
    dt = _ask("DT", "50")
    self_offdiag = _ask("SELF_OFFDIAG", "1")
    bubble = _ask("BUBBLE", "1")
    maxiter = _ask("MAXITER", "500")
    mixalpha = _ask("MIXALPHA", "0.2")
    kmesh_interp = _ask("KMESH_INTERPOLATE", "2 2 2")
    kmesh_scph = _ask("KMESH_SCPH", "2 2 2")

    blocks = [
        ('general', [
            f"\tPREFIX = {prefix}",
            "\tMODE = SCPH",
            f"\tFCSXML = {fcsxml}",
            f"\tFC2XML = {fc2xml}",
            f"\tNKD = {len(info['elements'])}; KD = " + " ".join(info['elements']),
            f"\tTMIN = {tmin}; TMAX = {tmax}; DT = {dt}",
        ]),
        # NOTE: ANPHON has no &interaction namelist; the FC expansion order is
        # carried by FCSXML/FC2XML, not by NORDER (an ALM-only keyword).
        ('cell', cell_block_lines(info['cell'])),
        ('kpoint', ["\t1"] + segments),
        ('scph', [
            f"\tSELF_OFFDIAG = {self_offdiag}",
            f"\tBUBBLE = {bubble}",
            f"\tMAXITER = {maxiter}",
            f"\tMIXALPHA = {mixalpha}",
            f"\tKMESH_INTERPOLATE = {kmesh_interp}",
            f"\tKMESH_SCPH = {kmesh_scph}",
        ]),
        ('analysis', ["\tPRINTVEL = 1"]),
    ]
    write_namelist(output, blocks)

    print("\n" + " done ".center(60, "="))
    print(f"The input file '{output}' has been generated.")
    print("Generated k-path segments:")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}: {seg.strip()}")
    print("\nParameter summary:")
    print(f"  T: TMIN={tmin}, TMAX={tmax}, DT={dt}")
    print(f"  SELF_OFFDIAG={self_offdiag}, BUBBLE={bubble}")
    print(f"  MAXITER={maxiter}, MIXALPHA={mixalpha}")
    print(f"  KMESH_INTERPOLATE={kmesh_interp}, KMESH_SCPH={kmesh_scph}")


if __name__ == '__main__':
    main()
