#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phonon_lifetime.py
==================

Menu entry point for sub-feature 2/202-02 "Process phonon lifetime
calculation results".

This slot in the toolkit was previously empty. It now exposes the
ALAMODE ``analyze_phonons`` analyzer (phonon lifetimes, mean free paths,
mode-resolved and cumulative thermal conductivities) through the dedicated
:mod:`analyze_phonons` wrapper and its plotting companion
:mod:`plot_analyze_phonons`.

Why a thin wrapper?
-------------------
The toolkit's menu system dispatches to a single script per function. To keep
``analyze_phonons`` reusable both interactively (from this entry) and
programmatically, the heavy lifting lives in ``analyze_phonons.py`` and this
file simply imports and runs it.
"""
from __future__ import annotations

import os
import sys

# Make the package root importable so ``analyze_phonons`` resolves.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import analyze_phonons  # noqa: E402  (path adjusted above)


def main():
    """Run the analyze_phonons interactive workflow."""
    analyze_phonons.main()


if __name__ == '__main__':
    main()
