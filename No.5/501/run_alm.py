#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_alm.py
==========

Run the ALAMODE ``alm`` executable on a generated input file
(sub-feature 6/601).

This bridges the gap in the toolkit between the input-file generators
(No.1/101) and the result analyzers (No.2): previously the user had to leave
the menu and type the ``alm`` command manually. This wrapper resolves the
binary from ``config/settings.yaml`` (``alamode.binaries.alm``), optionally
prepends a cluster ``module load`` command for HPC environments, and runs
``alm <input> > <log>`` in the current directory.

It prints the log tail and, if a ``*.fcs`` / ``*.xml`` was produced, reports
its path so the next workflow step can pick it up.
"""
from __future__ import annotations

import os
import sys
import subprocess

import alamodekit_io
alamodekit_io.ensure_package_root()

from alamodekit_config import get_alamode_bin, get_config_value


def get_env_command(default_module: str = "intel20232") -> str:
    """Interactively choose the cluster environment-loading command."""
    print("\n===== Cluster environment setup =====")
    print("1. Load default Intel environment (module load intel20232)")
    print("2. Custom environment-loading command")
    print("3. Skip environment loading")
    while True:
        choice = input("Select an option [1/2/3]: ").strip()
        if choice in ("1", "2", "3"):
            break
        print("  -> please enter 1, 2, or 3.")
    if choice == "1":
        return f"module load {default_module}"
    if choice == "2":
        custom = input("Enter the full environment command "
                       "(e.g. module load intel2024): ").strip()
        return custom
    return ""


def _ask(prompt: str, default=None) -> str:
    suffix = f" [default: {default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def main():
    print("=" * 60)
    print("  ALM runner (MODE = suggest / optimize)")
    print("=" * 60)

    inp = _ask("ALM input file (e.g. alm.in / alm_cv.in) [REQUIRED]")
    if not inp or not os.path.isfile(inp):
        print(f"ERROR: input file '{inp}' not found.")
        sys.exit(1)

    env_cmd = get_env_command()

    # Resolve the alm binary from settings.yaml.
    alm_bin = get_alamode_bin("alm")
    if not (os.path.isfile(alm_bin) and os.access(alm_bin, os.X_OK)):
        # Fall back to PATH lookup (shutil.which-style) before failing.
        from shutil import which
        on_path = which(os.path.basename(alm_bin))
        if on_path:
            alm_bin = on_path
        else:
            print(f"\nERROR: alm executable not found.\n   Resolved path: {alm_bin}")
            print("   Set 'alamode.bin_dir' in config/settings.yaml to your ALAMODE build dir.")
            sys.exit(1)

    log = _ask("Log file name", os.path.splitext(inp)[0] + ".log")

    # Build the shell command (env_cmd + alm input > log), run via bash so the
    # optional module-load prefix works on clusters.
    alm_cmd = f'"{alm_bin}" "{inp}" > "{log}"'
    full_cmd = f"{env_cmd} && {alm_cmd}" if env_cmd else alm_cmd

    print("\n" + "-" * 60)
    print("Running:", full_cmd)
    print("-" * 60)
    completed = subprocess.run(["bash", "-c", full_cmd])

    if completed.returncode != 0:
        print(f"\nERROR: alm exited with code {completed.returncode}.")
        sys.exit(completed.returncode)

    # Show the tail of the log for a quick sanity check.
    print("\n----- tail of", log, "-----")
    if os.path.isfile(log):
        with open(log, "r", encoding="utf-8", errors="replace") as handle:
            tail = handle.readlines()[-25:]
        print("".join(tail), end="")

    # Report generated outputs (fcs / xml / pattern / cvscore).
    base = os.path.splitext(os.path.basename(inp))[0]
    for ext in (".fcs", ".xml", ".pattern_HARMONIC", ".pattern_ANHARMONIC", ".cvscore"):
        for name in os.listdir("."):
            if name.endswith(ext):
                print(f"\nGenerated: {name}")

    print("\nALM run completed.")


if __name__ == "__main__":
    main()
