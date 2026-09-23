#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alamodekit_io.py
================

Shared I/O and parsing helpers for ALAMODEkit subprograms.

ALAMODE produces a family of text files (``.bands``, ``.dos``, ``.gruneisen``,
``.phvel``, ``.result``, ...) that share common conventions: a two-line
``#``-prefixed header describing the high-symmetry path, followed by a data
block. Rather than have every subprogram re-implement the same parsing and
high-symmetry-point merging logic, this module centralizes it so that all
scripts behave identically and stay short and readable.
"""
from __future__ import annotations

import os
import re
import numpy as np
from typing import List, Tuple

# Mapping from the symbol "G" (used by ALAMODE) to the Greek capital gamma.
_GAMMA_SUBSTITUTION = {'G': '\u0393'}

# Trailing "_<digits>" suffix used by ALAMODE to disambiguate repeated
# points on the path, e.g. "S_0", "X_1". We strip it for display.
_SUFFIX_RE = re.compile(r'_\d+$')


def ensure_package_root() -> str:
    """Insert the toolkit package root onto sys.path and return it.

    Every subprogram calls this at the very top so that
    ``import alamodekit_config`` / ``import plot_style`` resolve regardless
    of the directory the script was launched from.
    """
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    # Subprograms live two levels deep: <root>/No.X/<submenu>/script.py
    # but this helper lives at <root>/alamodekit_io.py. Try a few parents.
    for parent in (here, os.path.join(here, '..', '..'),
                   os.path.join(here, '..')):
        root = os.path.abspath(parent)
        if os.path.isfile(os.path.join(root, 'alamodekit_config.py')):
            if root not in sys.path:
                sys.path.insert(0, root)
            return root
    # Fall back to importing from the same directory as this file.
    if here not in sys.path:
        sys.path.insert(0, here)
    return here


def strip_numeric_suffix(name: str) -> str:
    """Remove a trailing ``_<digits>`` suffix, e.g. ``S_0`` -> ``S``."""
    return _SUFFIX_RE.sub('', name)


def substitute_gamma(name: str) -> str:
    """Replace the symbol ``G`` with the Greek capital gamma ``\u0393``.

    Used when pretty-printing high-symmetry point labels on axes.
    """
    if name == 'G':
        return _GAMMA_SUBSTITUTION['G']
    return name


def parse_high_symmetry_header(lines: List[str]) -> Tuple[List[str], List[float]]:
    """Extract high-symmetry point names and values from a ``.bands`` header.

    ALAMODE ``.bands`` files start with two comment lines::

        # G X M ...
        # 0.0 1.2 2.5 ...

    Returns
    -------
    (names, values) : (list[str], list[float])
        The raw names (with ``G`` converted to ``Γ``) and their positions.
    """
    def _tokens(line: str):
        line = line.lstrip('#').strip()
        return line.split()

    names = _tokens(lines[0])
    names = [_GAMMA_SUBSTITUTION.get(n, n) for n in names]
    values = [float(x) for x in _tokens(lines[1])]
    return names, values


def merge_high_symmetry_points(names: List[str], values: List[float]
                               ) -> Tuple[List[float], List[str]]:
    """Merge high-symmetry points that share the same path coordinate.

    Adjacent points with identical values (e.g. the end of one segment and
    the start of the next, or repeated labels) are collapsed into a single
    tick whose label joins the unique base names with ``|`` (e.g. ``X|Y``).
    Numeric suffixes are stripped first, so ``S|S_0`` becomes ``S``.

    Returns
    -------
    (tick_values, tick_labels) : (list[float], list[str])
        Sorted unique positions and their merged labels.
    """
    bucket: dict = {}
    for name, value in zip(names, values):
        key = round(value, 8)
        bucket.setdefault(key, [])
        base = strip_numeric_suffix(name)
        if base not in bucket[key]:
            bucket[key].append(base)

    tick_values = sorted(bucket.keys())
    tick_labels = ['|'.join(bucket[v]) for v in tick_values]
    return tick_values, tick_labels


def read_bands_file(path: str) -> Tuple[np.ndarray, np.ndarray,
                                        List[float], List[str]]:
    """Read an ALAMODE ``.bands`` file.

    Returns
    -------
    kpoints : np.ndarray, shape (nk,)
    frequencies : np.ndarray, shape (nk, n_modes)
    tick_values : list[float]
    tick_labels : list[str]
    """
    with open(path, 'r', encoding='utf-8') as handle:
        lines = handle.readlines()
    names, values = parse_high_symmetry_header(lines[:2])
    tick_values, tick_labels = merge_high_symmetry_points(names, values)
    data = np.loadtxt(lines[3:]) if len(lines) > 3 else np.empty((0, 0))
    # tolist() handles the single-row edge case from np.loadtxt.
    data = np.atleast_2d(data)
    kpoints = data[:, 0]
    frequencies = data[:, 1:]
    return kpoints, frequencies, tick_values, tick_labels


def compound_name_from_filename(path: str) -> str:
    """Return the compound name derived from a file's base name.

    Example
    -------
    >>> compound_name_from_filename('Mg3Sb2.bands')
    'Mg3Sb2'
    """
    return os.path.splitext(os.path.basename(path))[0]


def prompt_prefix(prompt: str = "Prefix for processing files") -> str:
    """Interactively ask for a non-empty prefix, validating the input."""
    while True:
        prefix = input(f"{prompt}: ").strip()
        if prefix:
            return prefix
        print("  -> Error: prefix cannot be empty; please try again.")


def ask_yes_no(prompt: str, default: str = 'n') -> bool:
    """Ask a yes/no question, returning a bool. ``default`` is used on Enter."""
    while True:
        raw = input(f"{prompt} (y/n) [{default}]: ").strip().lower()
        if raw == '':
            return default == 'y'
        if raw in ('y', 'yes'):
            return True
        if raw in ('n', 'no'):
            return False
        print("  -> please answer with 'y' or 'n'.")
