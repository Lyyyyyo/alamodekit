#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FORCE_CONSTANTS.py
=================

Batch-convert the SCPH-derived XML force constants (``scpb_*K.xml``) into
PhononPy ``FORCE_CONSTANTS_2ND`` files, renaming each to include the
temperature (``FORCE_CONSTANTS_2ND_<T>K``).

The conversion is performed by ALAMODE's ``convert_fc2.py`` helper, whose
location is resolved from ``config/settings.yaml`` via
:func:`alamodekit_config.get_alamode_bin` (logical name ``dfc2`` is reused
because the convert script lives in the same tools directory; override the
``convert_fc2`` binary name in settings.yaml if needed).

Outputs
-------
    FORCE_CONSTANTS_2ND_<T>K   one file per temperature
"""
from __future__ import annotations

import os
import re
import sys
import subprocess

# --- Bootstrap: make the toolkit root importable when run as a script. ---
# When this file is executed directly, sys.path[0] is this script's own
# folder (No.X/<submenu>/), which does NOT contain the toolkit modules.
# Add the package root (two levels up) to sys.path *before* importing
# anything toolkit-level. Harmless when imported as a package module.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402

from alamodekit_config import get_alamode_bin, get_config_value

OUTPUT_FILENAME = "FORCE_CONSTANTS_2ND"
FILE_PATTERN = r"^scpb_(\d+)K\.xml$"


def get_convert_script_path(default_path: str) -> str:
    """Report the resolved convert_fc2.py path and use it directly."""
    print("\n" + " Convert script path setup ".center(60, "="))
    print(f"Using convert script: {default_path}")
    return default_path


def find_target_files() -> list:
    """Return ``[(filename, temperature), ...]`` sorted by temperature."""
    pattern = re.compile(FILE_PATTERN)
    files = []
    for name in os.listdir("."):
        match = pattern.match(name)
        if match:
            files.append((name, match.group(1)))
    return sorted(files, key=lambda item: int(item[1]))


def main():
    print(" BATCH FORCE_CONSTANTS CONVERTER ".center(60, "="))
    print("Auto-process scpb_*K.xml -> rename the output file\n")

    # The convert_fc2.py script is resolved via the alamode binaries config.
    # By default settings.yaml maps the "dfc2" logical name to the dfc2 binary;
    # a separate "convert_fc2" logical name can be added if desired.
    default_path = get_config_value('alamode', 'binaries', 'convert_fc2', default=None)
    if not default_path:
        # Fall back to convert_fc2.py sitting next to the ALAMODE binaries.
        bin_dir = get_config_value('alamode', 'bin_dir', default='')
        default_path = os.path.join(os.path.expanduser(bin_dir) if bin_dir else '.',
                                    'convert_fc2.py')
    convert_script = get_convert_script_path(default_path)

    if not os.path.isfile(convert_script):
        print(f"\nError: convert script not found at: {convert_script}")
        return

    target_files = find_target_files()
    if not target_files:
        print("\nError: no scpb_*K.xml files found in the current directory!")
        return

    print(f"\nFound {len(target_files)} files to process:")
    for name, temp in target_files:
        print(f"  - {name} (temperature: {temp} K)")

    print("\n----------------------------------------")
    print("Starting batch conversion...")
    print("-" * 40 + "\n")

    success_count = 0
    fail_count = 0
    for xml_file, temp in target_files:
        final_name = f"{OUTPUT_FILENAME}_{temp}K"
        print(f"Processing: {xml_file}")
        print(f"Temperature: {temp} K")
        print(f"Final output: {final_name}")

        cmd = f'python "{convert_script}" -i "{xml_file}" -o "{OUTPUT_FILENAME}" -f'
        try:
            subprocess.run(["bash", "-c", cmd], check=True,
                          capture_output=True, text=True, encoding="utf-8")
            if os.path.exists(OUTPUT_FILENAME):
                os.rename(OUTPUT_FILENAME, final_name)
                print(f"Success: {final_name} created!\n")
                success_count += 1
            else:
                print(f"Error: {OUTPUT_FILENAME} was not generated.\n")
                fail_count += 1
        except subprocess.CalledProcessError as exc:
            print(f"Conversion failed for {xml_file}!")
            print(f"Error: {exc.stderr.strip() or exc.stdout.strip()}\n")
            fail_count += 1
        except Exception as exc:
            print(f"Unexpected error: {exc}\n")
            fail_count += 1

    print("=" * 60)
    print("Processing completed!")
    print(f"Successful files: {success_count}")
    print(f"Failed files: {fail_count}")
    print("All output files: FORCE_CONSTANTS_2ND_*K")
    print("=" * 60)


if __name__ == "__main__":
    main()
