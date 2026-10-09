#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alamodekit_config.py
====================

Central configuration loader for the ALAMODEkit toolkit.

Purpose
-------
This module is the single entry point every subprogram uses to read the
user-adjustable parameters defined in ``config/settings.yaml``. By routing
all configuration access through this module we guarantee that:

  * users only ever edit one file (``settings.yaml``);
  * every plotting subprogram shares the same appearance; and
  * the ALAMODE binary location is resolved consistently everywhere.

Search order for the settings file
----------------------------------
1. The path stored in the ``ALAMODEKIT_CONFIG`` environment variable.
2. ``./config/settings.yaml`` relative to the current working directory.
3. The bundled copy shipped with the toolkit, i.e. the ``settings.yaml``
   that lives next to this module inside the ``config/`` folder.

Subprograms run as standalone scripts from an arbitrary working directory,
so locating the bundled copy via ``__file__`` keeps the loader robust no
matter where the user launches the toolkit from.

Public API
----------
load_config()              -> dict   : the full parsed configuration.
get_config_value(*keys)    -> value  : nested key lookup with a default.
get_plotting_config()      -> dict   : the ``plotting`` section.
get_alamode_config()       -> dict   : the ``alamode`` section.
get_alamode_bin(name)      -> str    : absolute path to a named binary.
"""
from __future__ import annotations

import os
from typing import Any

# ---------------------------------------------------------------------------
# YAML loading: prefer the C-accelerated loader, fall back to pure Python,
# and finally to a minimal hand-rolled parser so the toolkit still works on
# systems where PyYAML is not installed.
# ---------------------------------------------------------------------------
try:
    from yaml import safe_load as _yaml_load  # type: ignore
    _HAVE_YAML = True
except Exception:  # pragma: no cover - exercised only when PyYAML is absent
    _HAVE_YAML = False


def _fallback_yaml_load(text: str) -> dict:
    """A tiny YAML subset parser (nested mappings + lists + scalars).

    It understands only the constructs used by settings.yaml: comments
    starting with ``#``, ``key: value`` pairs, nested blocks by indentation,
    inline lists ``[a, b]``, block lists with ``- item`` lines, and quoted
    strings. This is intentionally minimal but sufficient for this toolkit.

    Block lists vs. nested mappings are disambiguated with a one-line
    lookahead: a key whose first child line begins with ``-`` becomes a list,
    otherwise it becomes a mapping.
    """
    # Strip a UTF-8 BOM (e.g. settings.yaml saved by Windows Notepad);
    # otherwise it becomes part of the first key and breaks every lookup.
    if text.startswith("\ufeff"):
        text = text[1:]

    def _coerce(raw: str) -> Any:
        raw = raw.strip()
        if (raw.startswith('"') and raw.endswith('"')) or \
           (raw.startswith("'") and raw.endswith("'")):
            return raw[1:-1]
        if raw.startswith('[') and raw.endswith(']'):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [_coerce(part) for part in inner.split(',')]
        low = raw.lower()
        if low in ('true', 'false'):
            return low == 'true'
        if low in ('null', '~', 'none'):
            return None
        try:
            if '.' in raw or 'e' in low:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    # Pre-tokenize every non-empty, non-comment line into (indent, body).
    def _strip_comment(line: str) -> str:
        """Remove a trailing ``#`` comment while respecting quotes."""
        in_single = in_double = False
        for i, ch in enumerate(line):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == '#' and not in_single and not in_double:
                return line[:i]
        return line

    tokens = []
    for line in text.splitlines():
        line = _strip_comment(line)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(' '))
        tokens.append((indent, line.strip()))

    root: dict = {}
    # Stack entries: (indent, container). container is either dict or list.
    stack = [(-1, root)]

    for idx, (indent, body) in enumerate(tokens):
        # Pop until we are back under the right parent.
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if body.startswith('- '):
            # Block-list item. The parent on the stack must be a list.
            if isinstance(parent, list):
                parent.append(_coerce(body[2:]))
            continue

        if ':' in body:
            key, _, val = body.partition(':')
            key = key.strip()
            val = val.strip()
            if val != '':
                parent[key] = _coerce(val)
            else:
                # Decide list vs. map using the next token at deeper indent.
                is_list = False
                if idx + 1 < len(tokens):
                    nxt_indent, nxt_body = tokens[idx + 1]
                    if nxt_indent > indent and nxt_body.startswith('- '):
                        is_list = True
                child = [] if is_list else {}
                parent[key] = child
                stack.append((indent, child))
    return root


# ---------------------------------------------------------------------------
# Locate the settings file.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_SETTINGS = os.path.join(_HERE, 'config', 'settings.yaml')

# Cached configuration so the file is only parsed once per process.
_CONFIG_CACHE: dict | None = None


def _candidate_paths() -> list:
    """Return the ordered list of candidate settings.yaml locations."""
    paths = []
    env = os.environ.get('ALAMODEKIT_CONFIG')
    if env:
        paths.append(env)
    paths.append(os.path.join(os.getcwd(), 'config', 'settings.yaml'))
    paths.append(os.path.join(os.getcwd(), 'settings.yaml'))
    paths.append(_BUNDLED_SETTINGS)
    return paths


def _load_yaml_file(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as handle:
        text = handle.read()
    if _HAVE_YAML:
        data = _yaml_load(text)
        return data if data is not None else {}
    return _fallback_yaml_load(text)


def load_config(force_reload: bool = False) -> dict:
    """Load and cache the configuration dictionary.

    Parameters
    ----------
    force_reload : bool
        If True, ignore the cache and re-read the settings file.

    Returns
    -------
    dict
        The full configuration tree.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE

    last_error = None
    for path in _candidate_paths():
        if path and os.path.isfile(path):
            try:
                _CONFIG_CACHE = _load_yaml_file(path)
                _CONFIG_CACHE.setdefault('_resolved_settings_path', path)
                return _CONFIG_CACHE
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                continue

    raise FileNotFoundError(
        "Could not locate settings.yaml. Searched:\n  " +
        "\n  ".join(p or '<empty>' for p in _candidate_paths()) +
        ("\n\nLast error: %s" % last_error if last_error else "")
    )


# ---------------------------------------------------------------------------
# Convenience accessors.
# ---------------------------------------------------------------------------
def get_config_value(*keys: str, default: Any = None) -> Any:
    """Fetch a nested configuration value.

    Example
    -------
    >>> get_config_value('plotting', 'lines', 'linewidth', default=1.2)
    1.2
    """
    node = load_config()
    for key in keys:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return default
    return node


def get_plotting_config() -> dict:
    """Return the ``plotting`` section of the configuration."""
    return get_config_value('plotting', default={})


def get_alamode_config() -> dict:
    """Return the ``alamode`` section of the configuration."""
    return get_config_value('alamode', default={})


def get_alamode_bin(name: str) -> str:
    """Return the absolute path to a named ALAMODE executable.

    Parameters
    ----------
    name : str
        Logical name of the binary, e.g. ``"analyze_phonons"``, ``"alm"``.

    Returns
    -------
    str
        Absolute path to the executable, or just the bare name if the
        ``bin_dir`` is empty (so it relies on the system ``PATH``).
    """
    alamode = get_alamode_config()
    bin_dir = alamode.get('bin_dir', '')
    binaries = alamode.get('binaries', {})
    binary_name = binaries.get(name, name)
    if not bin_dir:
        return binary_name
    return os.path.join(os.path.expanduser(bin_dir), binary_name)


def get_settings_path() -> str:
    """Return the file system path of the settings file actually used."""
    return load_config().get('_resolved_settings_path', '')


if __name__ == '__main__':
    # When run directly, print the resolved configuration for inspection.
    cfg = load_config()
    print("Loaded settings from:", get_settings_path())
    import json
    safe = {k: v for k, v in cfg.items() if not k.startswith('_')}
    print(json.dumps(safe, indent=2, default=str))
