#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_phonons.py
==================

ALAMODEkit wrapper around the ALAMODE ``analyze_phonons`` C++ analyzer.

This script is the toolkit's interface (sub-feature 2/202-03 "Phonon lifetime
and thermal conductivity analysis") to the command-line analyzer shipped with
ALAMODE. It reproduces the behaviour of the upstream ``analyze_phonons.py``
driver but is rewritten to:

  * live inside the ALAMODEkit menu hierarchy;
  * resolve the ALAMODE binaries from ``config/settings.yaml``;
  * expose a clean, documented Python API; and
  * hand the produced result files over to the companion plotting script.

What the underlying C++ program computes
-----------------------------------------
Given a ``*.result`` file produced by ANPHON's RTA calculation, the analyzer
can print several quantities:

  calc = "tau"          phonon lifetimes / MFPs / mode-resolved kappa
                        at a single temperature
  calc = "tau_temp"     temperature dependence of the lifetime for one
                        (kpoint, mode) pair
  calc = "kappa"        temperature dependence of the total thermal
                        conductivity tensor
  calc = "cumulative"   cumulative thermal conductivity vs. sample size
                        (isotropic)
  calc = "cumulative2"  cumulative thermal conductivity along chosen
                        xyz directions
  calc = "kappa_boundary"  thermal conductivity including a finite-size
                        (boundary) correction

The C++ executable is invoked as::

    analyze_phonons  <result_file>  <calc>  <average_gamma>  [... calc-specific args ...]

Usage within ALAMODEkit
-----------------------
Run interactively; the script will prompt for every required option. The raw
text result is written to ``<prefix>_<calc>.dat`` for later plotting.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from typing import List, Optional

# Make the package root importable when this script runs standalone.
_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from alamodekit_config import get_alamode_bin

# ---------------------------------------------------------------------------
# Constants describing the supported calculation modes.
# ---------------------------------------------------------------------------
CALC_OPTIONS = {
    '1': ('tau',            'Phonon lifetime / MFP / mode kappa at a single temperature'),
    '2': ('tau_temp',       'Temperature dependence of lifetime for one (k, mode)'),
    '3': ('kappa',          'Temperature dependence of total thermal conductivity'),
    '4': ('cumulative',     'Cumulative thermal conductivity vs. size (isotropic)'),
    '5': ('cumulative2',    'Cumulative thermal conductivity along xyz directions'),
    ('6'): ('kappa_boundary', 'Thermal conductivity with finite-size boundary effect'),
}

# Sentinel value used by the C++ program to mean "no isotope file".
_NO_ISOTOPE = 'none'


# ---------------------------------------------------------------------------
# Helper input routines.
# ---------------------------------------------------------------------------
def _ask(prompt: str, default: Optional[str] = None) -> str:
    """Prompt the user for a string, returning the default on empty input."""
    suffix = f" [default: {default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _ask_int(prompt: str, default: Optional[int] = None,
             allow_none: bool = False) -> Optional[int]:
    """Prompt for an integer. Returns None if allowed and input is empty."""
    while True:
        raw = _ask(prompt, str(default) if default is not None else None)
        if raw == '' and allow_none:
            return None
        try:
            return int(raw)
        except ValueError:
            print("  -> please enter a valid integer.")


def _ask_float(prompt: str, default: Optional[float] = None,
               allow_none: bool = False) -> Optional[float]:
    """Prompt for a float. Returns None if allowed and input is empty."""
    while True:
        raw = _ask(prompt, str(default) if default is not None else None)
        if raw == '' and allow_none:
            return None
        try:
            return float(raw)
        except ValueError:
            print("  -> please enter a valid number.")


def _ask_mode_range(prompt: str) -> tuple:
    """Prompt for a mode range of the form ``beg`` or ``beg:end``.

    Returns a ``(beg_s, end_s)`` pair in the C++ 1-based convention
    (``end_s = 0`` means "all modes").
    """
    while True:
        raw = _ask(prompt + " (single index or 'beg:end', empty = all modes)", '').strip()
        if raw == '':
            return 1, 0  # all modes
        parts = raw.split(':')
        try:
            if len(parts) == 1:
                v = int(parts[0])
                return v, v
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except ValueError:
            pass
        print("  -> invalid format. Use a single integer or 'beg:end'.")


# ---------------------------------------------------------------------------
# Build the command-line argument list for each calc mode.
# ---------------------------------------------------------------------------
def build_command(result_file: str, calc: str, average_gamma: int,
                  options: dict) -> List[str]:
    """Return the full argv list (without the executable) for the analyzer.

    Parameters
    ----------
    result_file : str
        Path to the ``*.result`` file.
    calc : str
        Calculation mode (one of the CALC_OPTIONS values).
    average_gamma : int
        1 to average damping at degenerate points, 0 otherwise.
    options : dict
        Mode-specific options with keys:
          tau          -> kpoint_beg, kpoint_end, mode_beg, mode_end,
                         temp, isotope_file
          tau_temp     -> kpoint, mode, isotope_file
          kappa        -> mode_beg, mode_end, isotope_file
          cumulative   -> mode_beg, mode_end, max_len, d_len, temp,
                         nsample, gridtype, isotope_file
          cumulative2  -> (cumulative fields) + direction
          kappa_boundary -> mode_beg, mode_end, boundary_size, isotope_file
    """
    isotope = options.get('isotope_file')
    isotope_flag = '1' if isotope else '0'
    isotope_arg = isotope if isotope else _NO_ISOTOPE

    cmd = [result_file, calc, str(average_gamma)]

    if calc == 'tau':
        cmd += [str(options['kpoint_beg']), str(options['kpoint_end']),
                str(options['mode_beg']), str(options['mode_end']),
                str(options['temp']), isotope_flag, isotope_arg]

    elif calc == 'tau_temp':
        cmd += [str(options['kpoint']), str(options['mode']),
                isotope_flag, isotope_arg]

    elif calc == 'kappa':
        cmd += [str(options['mode_beg']), str(options['mode_end']),
                isotope_flag, isotope_arg]

    elif calc in ('cumulative', 'cumulative2'):
        cmd += [str(options['mode_beg']), str(options['mode_end']),
                isotope_flag, isotope_arg,
                str(options['max_len']), str(options['d_len']),
                str(options['temp']), str(options['nsample']),
                options['gridtype']]
        if calc == 'cumulative2':
            flags = options.get('direction_flags', [0, 0, 0])
            cmd += [str(flags[0]), str(flags[1]), str(flags[2])]

    elif calc == 'kappa_boundary':
        cmd += [str(options['mode_beg']), str(options['mode_end']),
                isotope_flag, isotope_arg, str(options['boundary_size'])]

    else:
        raise ValueError(f"Unknown calc mode: {calc}")

    return cmd


# ---------------------------------------------------------------------------
# Interactive option collection.
# ---------------------------------------------------------------------------
def collect_options(calc: str) -> dict:
    """Interactively gather the options required by ``calc``."""
    opts: dict = {}

    # Optional isotope scattering file (shared by all modes).
    iso = _ask("Isotope scattering file (leave empty to ignore)", '')
    opts['isotope_file'] = iso if iso else None

    if calc == 'tau':
        kb = _ask_int("Begin kpoint index (empty = 1)", 1) or 1
        ke = _ask_int("End   kpoint index (empty = all)", 0) or 0
        opts.update(kpoint_beg=kb, kpoint_end=ke)
        mb, me = _ask_mode_range("Mode range")
        opts.update(mode_beg=mb, mode_end=me)
        opts['temp'] = _ask_float("Target temperature [K] (REQUIRED for tau)")

    elif calc == 'tau_temp':
        opts['kpoint'] = _ask_int("Target kpoint index (REQUIRED)")
        opts['mode'] = _ask_int("Target mode index (REQUIRED)")

    elif calc == 'kappa':
        mb, me = _ask_mode_range("Mode range")
        opts.update(mode_beg=mb, mode_end=me)

    elif calc in ('cumulative', 'cumulative2'):
        mb, me = _ask_mode_range("Mode range")
        opts.update(mode_beg=mb, mode_end=me)
        opts['max_len'] = _ask_float("Maximum sample size L_max [nm] (empty = 0)", 0.0) or 0.0
        opts['d_len'] = _ask_float("Step size dL [nm] (empty = 0)", 0.0) or 0.0
        opts['temp'] = _ask_float("Temperature [K] (REQUIRED for cumulative)")
        opts['nsample'] = _ask_int("Number of sampling points", 1000) or 1000
        opts['gridtype'] = _ask("Grid type (linear | log)", 'log')
        if calc == 'cumulative2':
            raw = _ask("Directions (1 2 3 separated by spaces, empty = isotropic)", '')
            if raw:
                flags = [0, 0, 0]
                for tok in raw.split():
                    idx = int(tok) - 1
                    if 0 <= idx < 3:
                        flags[idx] = 1
                opts['direction_flags'] = flags
            else:
                opts['direction_flags'] = [0, 0, 0]

    elif calc == 'kappa_boundary':
        mb, me = _ask_mode_range("Mode range")
        opts.update(mode_beg=mb, mode_end=me)
        opts['boundary_size'] = _ask_float("Boundary size [nm] (empty = 1000)", 1000.0) or 1000.0

    return opts


# ---------------------------------------------------------------------------
# Execute the analyzer and capture its stdout to a file.
# ---------------------------------------------------------------------------
def run_analyzer(result_file: str, calc: str, options: dict,
                 average_gamma: int = 1,
                 output_path: Optional[str] = None) -> str:
    """Run ``analyze_phonons`` and write its stdout to ``output_path``.

    Parameters
    ----------
    result_file : str
        Path to the ``*.result`` file.
    calc : str
        Calculation mode.
    options : dict
        Mode-specific options (see :func:`build_command`).
    average_gamma : int
        1/0 flag for degenerate-point averaging.
    output_path : str, optional
        Where to save the captured text output. If omitted, the file
        ``<prefix>_<calc>.dat`` is created next to the result file.

    Returns
    -------
    str
        The path of the written output file.
    """
    binary = get_alamode_bin('analyze_phonons')

    # Fall back to a same-directory sibling if the configured binary is absent
    # (mirrors the behaviour of the upstream script).
    if not (os.path.isabs(binary) and os.path.isfile(binary)):
        sibling = os.path.join(os.path.dirname(os.path.abspath(result_file)),
                               'analyze_phonons')
        if shutil.which(binary) is None and os.path.isfile(sibling):
            binary = sibling

    argv = [binary] + build_command(result_file, calc, average_gamma, options)

    if output_path is None:
        prefix = os.path.splitext(os.path.basename(result_file))[0]
        output_path = f"{prefix}_{calc}.dat"

    print("\nExecuting:")
    print("  " + " ".join(argv))
    print("-" * 60)

    with open(output_path, 'w', encoding='utf-8') as out:
        proc = subprocess.run(argv, stdout=out, stderr=subprocess.PIPE, text=True)

    print("-" * 60)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise RuntimeError(
            f"analyze_phonons failed (exit code {proc.returncode}).")

    print(f"Result captured to: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Interactive entry point.
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  ALAMODE analyze_phonons wrapper (sub-feature 2/202-03)")
    print("=" * 60)

    # --- Select calculation mode -------------------------------------------
    print("\nAvailable calculations:")
    for key, (name, desc) in CALC_OPTIONS.items():
        print(f"  [{key}] {desc}")
    while True:
        choice = input("\nSelect calculation (1-6): ").strip()
        if choice in CALC_OPTIONS:
            calc = CALC_OPTIONS[choice][0]
            break
        print("  -> invalid choice, please enter a number from 1 to 6.")

    # --- Locate the .result file -------------------------------------------
    result_file = _ask("\nPath to the *.result file", '').strip()
    if not result_file or not os.path.isfile(result_file):
        print(f"ERROR: result file '{result_file}' not found.")
        sys.exit(1)

    # --- Averaging switch --------------------------------------------------
    avg = _ask_int("Average damping at degenerate points? (1=yes, 0=no)", 1)
    average_gamma = 1 if (avg is None or int(avg) != 0) else 0

    # --- Collect mode-specific options ------------------------------------
    options = collect_options(calc)

    # --- Validate required fields -----------------------------------------
    missing = []
    if calc == 'tau' and options.get('temp') is None:
        missing.append('temp')
    if calc == 'tau_temp' and (options.get('kpoint') is None or options.get('mode') is None):
        missing.append('kpoint/mode')
    if calc in ('cumulative', 'cumulative2') and options.get('temp') is None:
        missing.append('temp')
    if missing:
        print(f"ERROR: missing required option(s): {', '.join(missing)}")
        sys.exit(1)

    # --- Run --------------------------------------------------------------
    out_path = run_analyzer(result_file, calc, options, average_gamma)

    # --- Plot the result automatically ------------------------------------
    try:
        from plot_analyze_phonons import plot_result
        plot_result(out_path, calc)
    except Exception as exc:  # pragma: no cover - plotting is optional
        print(f"(Plotting unavailable: {exc})")

    print("\nDone.")


if __name__ == '__main__':
    main()
