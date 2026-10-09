#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the configuration loader and its pure-Python YAML fallback."""
import pytest

import alamodekit_config as cfg_mod


# ---------------------------------------------------------------------------
# Fallback YAML subset parser.
# ---------------------------------------------------------------------------
FALLBACK_SAMPLE = """\
# top-level comment
alamode:
  bin_dir: /home/x/build   # trailing comment
  binaries:
    alm: alm
    nbin: 3
plotting:
  dpi: 600
  ratio: 1.5
  enabled: true
  disabled: false
  empty: null
  inline: [a, b, c]
  block:
    - one
    - two
  quoted: "hello # not a comment"
"""


def test_fallback_nested_mappings():
    data = cfg_mod._fallback_yaml_load(FALLBACK_SAMPLE)
    assert data["alamode"]["bin_dir"] == "/home/x/build"
    assert data["alamode"]["binaries"]["alm"] == "alm"
    assert data["alamode"]["binaries"]["nbin"] == 3


def test_fallback_scalar_coercion():
    data = cfg_mod._fallback_yaml_load(FALLBACK_SAMPLE)
    plot = data["plotting"]
    assert plot["dpi"] == 600 and isinstance(plot["dpi"], int)
    assert plot["ratio"] == 1.5 and isinstance(plot["ratio"], float)
    assert plot["enabled"] is True
    assert plot["disabled"] is False
    assert plot["empty"] is None


def test_fallback_lists_and_quoted_comment():
    data = cfg_mod._fallback_yaml_load(FALLBACK_SAMPLE)
    plot = data["plotting"]
    assert plot["inline"] == ["a", "b", "c"]
    assert plot["block"] == ["one", "two"]
    # The '#' inside quotes must not be treated as a comment.
    assert plot["quoted"] == "hello # not a comment"


def test_fallback_empty_input():
    assert cfg_mod._fallback_yaml_load("") == {}
    assert cfg_mod._fallback_yaml_load("# only a comment\n") == {}


def test_fallback_strips_bom():
    # A UTF-8 BOM (Windows Notepad) must not become part of the first key.
    data = cfg_mod._fallback_yaml_load("\ufeffalamode:\n  bin_dir: /x\n")
    assert "alamode" in data
    assert data["alamode"]["bin_dir"] == "/x"


# ---------------------------------------------------------------------------
# Candidate search order.
# ---------------------------------------------------------------------------
def test_candidate_paths_order(monkeypatch):
    monkeypatch.setenv("ALAMODEKIT_CONFIG", "/tmp/custom.yaml")
    paths = cfg_mod._candidate_paths()
    assert paths[0] == "/tmp/custom.yaml"
    assert paths[-1] == cfg_mod._BUNDLED_SETTINGS
    assert len(paths) == 4


def test_candidate_paths_without_env(monkeypatch):
    monkeypatch.delenv("ALAMODEKIT_CONFIG", raising=False)
    paths = cfg_mod._candidate_paths()
    assert len(paths) == 3
    assert cfg_mod._BUNDLED_SETTINGS in paths


# ---------------------------------------------------------------------------
# Full load via a temporary settings file + nested accessors.
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "alamode:\n  bin_dir: /opt/alamode/build\n"
        "plotting:\n  dpi: 300\n"
        "  colors:\n    primary: \"#abcdef\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALAMODEKIT_CONFIG", str(path))
    cfg_mod.load_config(force_reload=True)
    yield path
    # Restore: env var is removed automatically by monkeypatch; force a
    # reload so later tests do not see the cached temporary config.
    cfg_mod.load_config(force_reload=True)


def test_load_and_resolved_path(temp_settings):
    assert cfg_mod.get_settings_path() == str(temp_settings)


def test_get_config_value_nested(temp_settings):
    assert cfg_mod.get_config_value("alamode", "bin_dir") == "/opt/alamode/build"
    assert cfg_mod.get_config_value("plotting", "dpi") == 300
    assert cfg_mod.get_config_value("plotting", "colors", "primary") == "#abcdef"


def test_get_config_value_default(temp_settings):
    assert cfg_mod.get_config_value("nope", default=42) == 42
    assert cfg_mod.get_config_value("plotting", "missing", default="x") == "x"


def test_get_alamode_bin(temp_settings):
    alm = cfg_mod.get_alamode_bin("alm")
    assert alm.replace("\\", "/").endswith("/opt/alamode/build/alm")
    # Unknown binary name falls back to the logical name.
    assert cfg_mod.get_alamode_bin("mystery").replace("\\", "/") == \
        "/opt/alamode/build/mystery"


def test_get_alamode_bin_empty_dir(monkeypatch, tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("alamode:\n  bin_dir: \"\"\n", encoding="utf-8")
    monkeypatch.setenv("ALAMODEKIT_CONFIG", str(path))
    cfg_mod.load_config(force_reload=True)
    try:
        assert cfg_mod.get_alamode_bin("alm") == "alm"
    finally:
        monkeypatch.delenv("ALAMODEKIT_CONFIG", raising=False)
        cfg_mod.load_config(force_reload=True)
