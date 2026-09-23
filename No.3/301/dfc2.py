#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dfc2.py
=======

Batch process the ALAMODE ``dfc2`` tool to extract temperature-dependent 2nd
force constants from an SCPH run.

``dfc2`` invocation
-------------------
    dfc2 FILE_A FILE_C FILE_B TEMPERATURE

Validation rules
----------------
* FILE_A (original harmonic force constants): MUST NOT contain "scph".
* FILE_B (SCPH-renormalized force constants): MUST contain "scph".
* FILE_C: output path (``scpb_<T>K.xml``).

The path to the ``dfc2`` executable is resolved from
``config/settings.yaml`` via :func:`alamodekit_config.get_alamode_bin`, with
a cluster "module load" command option for HPC environments.

Outputs
-------
    scpb_<T>K.xml   SCPH-derived 2nd force constants per temperature
"""
from __future__ import annotations

import os
import sys
import subprocess

import alamodekit_io
alamodekit_io.ensure_package_root()

from alamodekit_config import get_alamode_bin


def check_input_number(prompt: str) -> int:
    """Prompt for a strictly positive integer, re-asking on bad input."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            print("Error: input cannot be empty.")
            continue
        try:
            value = int(raw)
            if value > 0:
                return value
            print("Error: please enter a number greater than 0.")
        except ValueError:
            print("Error: please enter a valid integer.")


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
        print("Error: please enter 1, 2, or 3.")
    if choice == "1":
        return f"module load {default_module}"
    if choice == "2":
        custom = input("Enter the full environment command "
                       "(e.g. module load intel2024): ").strip()
        return custom
    return ""


def main():
    print("===== BATCH DFC2 TEMPERATURE PROCESSING SCRIPT =====")
    print("Validation: FileA = NO 'scph' | FileB = MUST have 'scph'\n")

    env_cmd = get_env_command()

    t_start = check_input_number("\n1. Start temperature (K): ")
    t_step = check_input_number("2. Temperature step (K): ")
    t_end = check_input_number("3. End temperature (K): ")

    print("\n----------------------------------------")
    file_a = input("4. Original force-constant file (FileA): ").strip().replace(" ", "")
    file_b = input("5. SCPH-processed force-constant file (FileB): ").strip().replace(" ", "")

    # --- Validate FileA: exists and does not contain 'scph'. ----------------
    if not os.path.isfile(file_a):
        print(f"\nError: FileA '{file_a}' does not exist.")
        return
    if 'scph' in file_a.lower():
        print(f"\nError: FileA cannot contain 'scph' in the filename.")
        return

    # --- Validate FileB: exists and must contain 'scph'. --------------------
    if not os.path.isfile(file_b):
        print(f"\nError: FileB '{file_b}' does not exist.")
        return
    if 'scph' not in file_b.lower():
        print(f"\nError: FileB must contain 'scph' in the filename.")
        return

    # --- Resolve the dfc2 executable path from settings.yaml. ----------------
    dfc2_path = get_alamode_bin('dfc2')
    # Fall back to a sibling in the data directory if the configured path is missing.
    if not (os.path.isfile(dfc2_path) and os.access(dfc2_path, os.X_OK)):
        sibling = os.path.join(os.path.dirname(os.path.abspath(file_a)), 'dfc2')
        if os.path.isfile(sibling) and os.access(sibling, os.X_OK):
            dfc2_path = sibling
        else:
            print(f"\nError: dfc2 program not found or not executable.\n   Path: {dfc2_path}")
            return

    # --- Batch execution over every temperature point. ----------------------
    print("\n----------------------------------------")
    print("All checks passed. Starting batch processing...")
    print("-" * 40 + "\n")

    for temp in range(t_start, t_end + 1, t_step):
        file_c = f"scpb_{temp}K.xml"
        print(f"Processing temperature: {temp} K")
        print(f"Output file: {file_c}")

        # Quote every path so special characters (parentheses, spaces) are safe.
        cmd = (f'"{dfc2_path}" "{file_a}" "{file_c}" "{file_b}" {temp}')
        full_cmd = f"{env_cmd} && {cmd}" if env_cmd else cmd

        try:
            subprocess.run(["bash", "-c", full_cmd], check=True,
                           capture_output=True, text=True, encoding="utf-8")
            print(f"{temp} K processed successfully!\n")
        except subprocess.CalledProcessError as exc:
            print(f"{temp} K processing failed!")
            print(f"Error log: {exc.stderr.strip() or exc.stdout.strip()}\n")
        except Exception as exc:
            print(f"{temp} K unexpected error: {exc}\n")

    print("=" * 40)
    print("All temperature points completed!")
    print("Output files: scpb_*K.xml (current directory)")
    print("=" * 40)


if __name__ == "__main__":
    main()
