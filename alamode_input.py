#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alamode_input.py
================

Shared helpers for the ALM/ANPHON input-file generators (No.1 scripts).

All No.1 subprograms parse a VASP POSCAR/SPOSCAR, optionally read a
``KPATH.in`` high-symmetry path, and emit an ALAMODE ``.in`` file built from
Fortran namelists. Centralising that logic here keeps the generators short
and their behaviour consistent.

Public API
----------
parse_poscar(path)        -> dict with keys: scale, cell, elements,
                             atom_counts, positions (scaled by scale)
read_kpath(path)          -> list of namelist-ready "label kx ky kz ..."
                             segment strings (one line per path segment)
write_namelist(path, blocks)
                          -> write a .in file from an ordered dict of
                             namelist -> [text lines]
ask_number(prompt, default, cast, validator)
                          -> interactive numeric input with validation
"""
from __future__ import annotations

import os
from typing import Callable, List, Optional, Dict, Union

BOHR_PER_ANGSTROM = 1.8897259886  # conversion factor written into &cell


def parse_poscar(path: str) -> dict:
    """Parse a VASP POSCAR/SPOSCAR and return crystal + atomic info.

    The returned dictionary contains:

    * ``scale`` (float)            universal scaling factor
    * ``cell`` (list[list[float]]) 3x3 lattice vectors, already scaled
    * ``elements`` (list[str])     element symbols
    * ``atom_counts`` (list[int])  atoms per element
    * ``positions`` (list[tuple])  ``(kind_index, x, y, z)`` per atom, where
                                   kind_index is 1-based
    """
    with open(path, 'r', encoding='utf-8') as handle:
        lines = handle.readlines()

    # Line 0: comment; line 1: scale; lines 2-4: lattice vectors.
    scale = float(lines[1].strip())
    cell = [[float(x) for x in lines[i].split()] for i in (2, 3, 4)]
    for row in cell:
        for j in range(3):
            row[j] *= scale

    # Line 5: element names; line 6: atom counts per element.
    elements = lines[5].split()
    atom_counts = [int(x) for x in lines[6].split()]

    # Skip the "selective dynamics"/"direct" flag line (line 7).
    # Atom coordinates start at line 8.
    positions: List[tuple] = []
    line_idx = 8
    for kind_index, count in enumerate(atom_counts, start=1):
        for _ in range(count):
            coords = [float(x) for x in lines[line_idx].split()[:3]]
            positions.append((kind_index, *coords))
            line_idx += 1

    return {
        'scale': scale,
        'cell': cell,
        'elements': elements,
        'atom_counts': atom_counts,
        'positions': positions,
    }


def read_kpath(path: str, n_points_per_segment: int = 51) -> List[str]:
    """Read a phonopy-style ``KPATH.in`` and emit ALAMODE k-segment lines.

    The input is the standard ``Line-Mode`` / ``Reciprocal`` format where
    pairs of (label + 3 coords) lines define each segment. ``GAMMA`` is
    rewritten as ``G`` (ALAMODE's convention) and each segment line ends
    with the number of points along it.

    Returns
    -------
    list[str]
        One string per segment, ready to be written inside ``&kpoint``.
    """
    with open(path, 'r', encoding='utf-8') as handle:
        lines = [ln.strip() for ln in handle if ln.strip()]

    reading = False
    buffer = []
    segments: List[str] = []
    for line in lines:
        if line in ('Line-Mode', 'Reciprocal'):
            reading = True
            continue
        if not reading:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        buffer.append(parts)
        if len(buffer) == 2:
            p1, p2 = buffer
            label1 = 'G' if p1[3] == 'GAMMA' else p1[3]
            label2 = 'G' if p2[3] == 'GAMMA' else p2[3]
            segments.append(
                f"\t{label1} {p1[0]} {p1[1]} {p1[2]} "
                f"{label2} {p2[0]} {p2[1]} {p2[2]} {n_points_per_segment}")
            buffer = []
    if buffer:
        print("Warning: an odd number of high-symmetry points was found.")
    return segments


def write_namelist(path: str, blocks: "List[tuple]") -> None:
    """Write a Fortran-namelist ALAMODE ``.in`` file.

    Parameters
    ----------
    path : str
        Output file path.
    blocks : list of (namelist, body_lines)
        Ordered ``(name, lines)`` tuples, where ``lines`` is a list of
        text lines already containing leading tabs / comments. A blank
        line is inserted between successive namelists.
    """
    with open(path, 'w', encoding='utf-8') as handle:
        for name, body in blocks:
            handle.write(f"&{name}\n")
            for line in body:
                handle.write(line if line.endswith('\n') else line + '\n')
            handle.write("/\n\n")


def cell_block_lines(cell: List[List[float]]) -> List[str]:
    """Return the body of the ``&cell`` namelist for ``cell``."""
    lines = [f"\t{BOHR_PER_ANGSTROM}  # factor in Bohr unit"]
    for row in cell:
        lines.append("\t" + " ".join(f"{x:.16f}" for x in row))
    return lines


def position_block_lines(positions: List[tuple]) -> List[str]:
    """Return the body of the ``&position`` namelist."""
    return [" " + f"{kind} " + " ".join(f"{c:.16f}" for c in coords)
            for kind, *coords in positions]


def ask_number(prompt: str, default: Optional[Union[int, float]] = None,
               cast: type = float,
               validator: Optional[Callable] = None) -> Union[int, float]:
    """Interactively ask for a number with validation and a default.

    Parameters
    ----------
    prompt : str
        Question shown to the user.
    default : int or float, optional
        Value used when the user just presses Enter.
    cast : type
        ``int`` or ``float``.
    validator : callable, optional
        Receives the parsed value, returns True to accept it.
    """
    suffix = f" [default: {default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            if default is not None:
                return default
            print("  -> error: a value is required.")
            continue
        try:
            value = cast(raw)
        except ValueError:
            print(f"  -> error: please enter a valid {cast.__name__}.")
            continue
        if validator and not validator(value):
            continue
        return value


def ask_int_list(prompt: str, default: Optional[List[int]] = None,
                 length: Optional[int] = None) -> List[int]:
    """Ask for a whitespace-separated list of integers."""
    suffix = f" [default: {default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return list(default)
        try:
            values = list(map(int, raw.split()))
        except ValueError:
            print("  -> error: please enter space-separated integers.")
            continue
        if length is not None and len(values) != length:
            print(f"  -> error: exactly {length} integers are required.")
            continue
        return values
