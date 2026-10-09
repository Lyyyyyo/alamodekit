#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the shared POSCAR/KPATH/namelist helpers (alamode_input)."""
import alamode_input as in_mod


POSCAR_TEXT = """\
test structure
1.0
3.6 0.0 0.0
0.0 3.6 0.0
0.0 0.0 3.6
Cu O
1 1
Direct
0.0 0.0 0.0
0.5 0.5 0.5
"""


def test_parse_poscar_basic(tmp_path):
    path = tmp_path / "POSCAR"
    path.write_text(POSCAR_TEXT, encoding="utf-8")
    data = in_mod.parse_poscar(str(path))
    assert data["scale"] == 1.0
    assert data["elements"] == ["Cu", "O"]
    assert data["atom_counts"] == [1, 1]
    assert data["positions"] == [
        (1, 0.0, 0.0, 0.0),
        (2, 0.5, 0.5, 0.5),
    ]
    # Unscaled cubic cell.
    assert data["cell"][0] == [3.6, 0.0, 0.0]
    assert data["cell"][2] == [0.0, 0.0, 3.6]


def test_parse_poscar_scale_applied(tmp_path):
    text = POSCAR_TEXT.replace("1.0\n3.6", "2.0\n3.6", 1)
    path = tmp_path / "POSCAR"
    path.write_text(text, encoding="utf-8")
    data = in_mod.parse_poscar(str(path))
    assert data["scale"] == 2.0
    assert data["cell"][0] == [7.2, 0.0, 0.0]


KPATH_TEXT = """\
Reciprocal
0.0 0.0 0.0 GAMMA
0.5 0.0 0.0 X
0.5 0.0 0.0 X
0.5 0.5 0.0 M
"""


def test_read_kpath_segments(tmp_path):
    path = tmp_path / "KPATH.in"
    path.write_text(KPATH_TEXT, encoding="utf-8")
    segments = in_mod.read_kpath(str(path))
    assert len(segments) == 2
    # GAMMA must be rewritten to ALAMODE's 'G'.
    assert segments[0].lstrip().startswith("G 0.0 0.0 0.0 X 0.5 0.0 0.0 51")
    assert segments[1].rstrip().endswith("51")


def test_read_kpath_custom_points(tmp_path):
    path = tmp_path / "KPATH.in"
    path.write_text(KPATH_TEXT, encoding="utf-8")
    segments = in_mod.read_kpath(str(path), n_points_per_segment=21)
    assert segments[0].rstrip().endswith("21")


def test_write_namelist_roundtrip(tmp_path):
    path = tmp_path / "alm.in"
    blocks = [
        ("cell", ["\t1.8897  # factor", "\t1.0 0.0 0.0"]),
        ("kpoint", ["\tG 0.0 0.0 0.0 X 1.0 0.0 0.0 10"]),
    ]
    in_mod.write_namelist(str(path), blocks)
    text = path.read_text(encoding="utf-8")
    assert "&cell\n" in text
    assert "&kpoint\n" in text
    assert text.count("/\n") == 2
    assert "1.8897" in text


def test_cell_block_lines():
    cell = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    lines = in_mod.cell_block_lines(cell)
    assert "Bohr" in lines[0]
    assert len(lines) == 4


def test_position_block_lines():
    positions = [(1, 0.0, 0.0, 0.0), (2, 0.5, 0.5, 0.5)]
    lines = in_mod.position_block_lines(positions)
    assert lines[0].lstrip().startswith("1 ")
    assert lines[1].lstrip().startswith("2 ")
    assert "0.500000" in lines[1]
