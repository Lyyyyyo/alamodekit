#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest shared bootstrap for ALAMODEkit.

Makes the toolkit root importable regardless of where pytest is invoked from,
and forces a headless matplotlib backend before any toolkit module imports it.
"""
import os
import sys

# Headless backend must be set before matplotlib is imported.
os.environ.setdefault("MPLBACKEND", "Agg")

_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, _TOOLKIT_ROOT)
