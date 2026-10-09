#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the shared ALAMODE output parsing helpers (alamodekit_io)."""
import os

import numpy as np
import pytest

import alamodekit_io as io_mod


# ---------------------------------------------------------------------------
# Label helpers.
# ---------------------------------------------------------------------------
def test_strip_numeric_suffix():
    assert io_mod.strip_numeric_suffix("S_0") == "S"
    assert io_mod.strip_numeric_suffix("X_1") == "X"
    assert io_mod.strip_numeric_suffix("Gamma") == "Gamma"
    assert io_mod.strip_numeric_suffix("X") == "X"


def test_substitute_gamma():
    assert io_mod.substitute_gamma("G") == "\u0393"
    assert io_mod.substitute_gamma("X") == "X"
    assert io_mod.substitute_gamma("M") == "M"


# ---------------------------------------------------------------------------
# High-symmetry header parsing and merging.
# ---------------------------------------------------------------------------
def test_parse_high_symmetry_header():
    lines = ["# G X M", "# 0.0 1.0 2.0"]
    names, values = io_mod.parse_high_symmetry_header(lines)
    assert names == ["\u0393", "X", "M"]
    assert values == [0.0, 1.0, 2.0]


def test_merge_collapses_repeated_points():
    # Names arrive from parse_high_symmetry_header, which already maps G -> Γ;
    # merge() itself only collapses shared coordinates.
    names = ["\u0393", "X", "X_1", "M"]
    values = [0.0, 1.0, 1.0, 2.0]
    tick_values, tick_labels = io_mod.merge_high_symmetry_points(names, values)
    assert tick_values == [0.0, 1.0, 2.0]
    assert tick_labels == ["\u0393", "X", "M"]


def test_merge_joins_distinct_labels():
    names = ["X", "Y"]
    values = [1.0, 1.0]
    tick_values, tick_labels = io_mod.merge_high_symmetry_points(names, values)
    assert tick_values == [1.0]
    assert tick_labels == ["X|Y"]


# ---------------------------------------------------------------------------
# Full .bands reader.
# ---------------------------------------------------------------------------
BANDS_TEXT = (
    "# G X\n"
    "# 0.0 1.0\n"
    "\n"
    "0.0 10.0 20.0\n"
    "1.0 30.0 40.0\n"
)


def test_read_bands_file(tmp_path):
    path = tmp_path / "Si.bands"
    path.write_text(BANDS_TEXT, encoding="utf-8")
    kpoints, freqs, tick_values, tick_labels = io_mod.read_bands_file(str(path))
    assert np.allclose(kpoints, [0.0, 1.0])
    assert freqs.shape == (2, 2)
    assert np.allclose(freqs, [[10.0, 20.0], [30.0, 40.0]])
    assert tick_values == [0.0, 1.0]
    assert tick_labels == ["\u0393", "X"]


def test_compound_name_from_filename():
    assert io_mod.compound_name_from_filename("Mg3Sb2.bands") == "Mg3Sb2"
    assert io_mod.compound_name_from_filename("/path/to/Si.dos") == "Si"


# ---------------------------------------------------------------------------
# Bootstrap helper.
# ---------------------------------------------------------------------------
def test_ensure_package_root():
    root = io_mod.ensure_package_root()
    assert os.path.isfile(os.path.join(root, "alamodekit_config.py"))
