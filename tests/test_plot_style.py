#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the centralized matplotlib styling module (plot_style)."""
import numpy as np
import pytest
from matplotlib.colors import LinearSegmentedColormap

import plot_style


# ---------------------------------------------------------------------------
# Custom colormaps.
# ---------------------------------------------------------------------------
def test_velocity_cmap_anchors():
    cmap = plot_style._cmap_yellow_green_blue()
    assert isinstance(cmap, LinearSegmentedColormap)
    assert cmap.name == "velocity"
    assert cmap.N == 256
    assert np.allclose(cmap(0.0)[:3], [1.0, 1.0, 0.0])   # yellow
    # Mid-grid interpolation with N=256 lands a hair off the exact anchor.
    assert np.allclose(cmap(0.5)[:3], [0.0, 1.0, 0.0], atol=0.02)  # green
    assert np.allclose(cmap(1.0)[:3], [0.0, 0.0, 0.5])   # dark blue


def test_gruneisen_cmap_zero_anchor():
    cmap = plot_style._cmap_blue_white_red(0.5)
    assert cmap.N == 2048
    assert np.allclose(cmap(0.0)[:3], [0.0, 0.0, 0.5])   # dark blue
    assert np.allclose(cmap(0.5)[:3], [1.0, 1.0, 1.0], atol=1e-3)  # white at zero
    assert np.allclose(cmap(1.0)[:3], [0.8, 0.0, 0.0])   # dark red


@pytest.mark.parametrize("value,expected", [(0.3, 0.3), (0.7, 0.7)])
def test_gruneisen_zero_fraction_anchor(value, expected):
    cmap = plot_style._cmap_blue_white_red(value)
    # The white anchor must sit at the requested interior position.
    assert np.allclose(cmap(expected)[:3], [1.0, 1.0, 1.0], atol=1e-3)


@pytest.mark.parametrize("value", [2.0, -1.0])
def test_gruneisen_zero_fraction_clamped_builds(value):
    # Out-of-range fractions clamp to [0, 1]; the cmap must still build and
    # keep its blue/red end anchors (the white anchor coincides with an end).
    cmap = plot_style._cmap_blue_white_red(value)
    assert np.allclose(cmap(0.0)[:3], [0.0, 0.0, 0.5])
    assert np.allclose(cmap(1.0)[:3], [0.8, 0.0, 0.0])


# ---------------------------------------------------------------------------
# get_cmap resolution and caching.
# ---------------------------------------------------------------------------
def test_get_cmap_custom_and_standard():
    velocity = plot_style.get_cmap("velocity")
    assert isinstance(velocity, LinearSegmentedColormap)
    assert velocity.name == "velocity"
    gruneisen = plot_style.get_cmap("gruneisen")
    assert gruneisen.name == "gruneisen"
    # A standard matplotlib name passes through.
    assert plot_style.get_cmap("viridis").name == "viridis"


def test_get_cmap_is_cached():
    a = plot_style.get_cmap("velocity")
    b = plot_style.get_cmap("velocity")
    assert a is b


# ---------------------------------------------------------------------------
# rcParams application.
# ---------------------------------------------------------------------------
def test_apply_plot_style_returns_config():
    cfg = plot_style.apply_plot_style()
    assert "plotting" in cfg
    import matplotlib as mpl
    assert mpl.rcParams["xtick.direction"] in ("in", "out", "inout")
