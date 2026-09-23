#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_anphon.py
=============

Run the ALAMODE ``anphon`` executable on a generated input file
(sub-feature 6/602).

This is the companion to ``run_alm.py``: it runs ``anphon <input> > <log>``
for phonon / RTA / SCPH calculations, resolving the binary from
``config/settings.yaml`` and optionally prepending a cluster ``module load``
command. It then reports the generated ``.bands`` / ``.dos`` / ``.result``
files so the analysis scripts (No.2) can pick them up.

The wrapper supports parallel execution via MPI when ``--mpi`` is requested:
it then invokes ``mpirun -np <N> anphon <input>``.
"""
from __future__ import annotations

import os
import sys
import subprocess

import alamodekit_io
alamodekit_io.ensure_package_root()

from alamodekit_config import get_alamode_bin


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
        return input("Enter the full environment command "
                     "(e.g. module load intel2024): ").strip()
    return ""


def _ask(prompt: str, default=None) -> str:
    suffix = f" [default: {default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  -> please enter a valid integer.")


def main():
    print("=" * 60)
    print("  ANPHON runner (phonons / RTA / SCPH)")
    print("=" * 60)

    inp = _ask("ANPHON input file (e.g. phband.in / scph.in) [REQUIRED]")
    if not inp or not os.path.isfile(inp):
        print(f"ERROR: input file '{inp}' not found.")
        sys.exit(1)

    env_cmd = get_env_command()

    anphon_bin = get_alamode_bin("anphon")
    if not (os.path.isfile(anphon_bin) and os.access(anphon_bin, os.X_OK)):
        from shutil import which
        on_path = which(os.path.basename(anphon_bin))
        if on_path:
            anphon_bin = on_path
        else:
            print(f"\nERROR: anphon executable not found.\n   Resolved path: {anphon_bin}")
            print("   Set 'alamode.bin_dir' in config/settings.yaml to your ALAMODE build dir.")
            sys.exit(1)

    log = _ask("Log file name", os.path.splitext(inp)[0] + ".log")

    # Optional MPI parallel run.
    use_mpi = alamodekit_io.ask_yes_no("Run with MPI (mpirun -np N anphon ...)?")
    mpi_prefix = ""
    if use_mpi:
        nproc = _ask_int("Number of MPI processes", 4)
        mpi_prefix = f"mpirun -np {nproc} "

    cmd = f'{mpi_prefix}"{anphon_bin}" "{inp}" > "{log}"'
    full_cmd = f"{env_cmd} && {cmd}" if env_cmd else cmd

    print("\n" + "-" * 60)
    print("Running:", full_cmd)
    print("-" * 60)
    completed = subprocess.run(["bash", "-c", full_cmd])

    if completed.returncode != 0:
        print(f"\nERROR: anphon exited with code {completed.returncode}.")
        sys.exit(completed.returncode)

    print("\n----- tail of", log, "-----")
    if os.path.isfile(log):
        with open(log, "r", encoding="utf-8", errors="replace") as handle:
            tail = handle.readlines()[-25:]
        print("".join(tail), end="")

    # Report generated output files (.bands / .dos / .result / .phvel / .gruneisen ...).
    interesting_exts = (".bands", ".dos", ".result", ".phvel", ".gruneisen",
                        ".scph_bands", ".scph_dos", ".scph_dfc2")
    print("\nGenerated result files:")
    for name in sorted(os.listdir(".")):
        if name.endswith(interesting_exts) and name != inp:
            print(f"  - {name}")

    print("\nANPHON run completed. Use the No.2 analysis scripts to plot these.")


if __name__ == "__main__":
    main()
