#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_sbtecontrol.py
==================

Pre-processing program for ShengBTE: produce the ``CONTROL`` input file
quickly from VASP outputs (``POSCAR`` and optional ``BORN``).

Features
--------
* Single temperature, temperature range, or batch temperatures (one folder
  per temperature).
* Optional nanowire orientation support.
* Optional 4-phonon (4ph) sampling switches.
* Non-analytic correction (NAC) enabled automatically when ``BORN`` exists.

This is a refactored, English-commented version of the original author's
script (Xin Liu, 3480235563@qq.com); the trailing colon that made the
original file a syntax error has been removed.

Outputs
-------
    CONTROL             single/range mode
    <T>/CONTROL         batch mode (one folder per temperature)
"""
from __future__ import annotations

import os
import re
import sys


def ask_float(prompt: str) -> float:
    """Read a float from stdin; exit on bad input."""
    try:
        return float(input(prompt + "\n"))
    except ValueError:
        print("Invalid input!")
        sys.exit(1)


def parse_poscar(path: str = "POSCAR") -> dict:
    """Parse a VASP POSCAR and return the data needed for CONTROL."""
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    elements = lines[5].split()
    atom_num = lines[6].split()
    natom = sum(int(x) for x in atom_num)
    lat1, lat2, lat3 = lines[2].strip(), lines[3].strip(), lines[4].strip()
    elements_str = " ".join(f'"{e}"' for e in elements)
    types = " ".join(f"{idx + 1} " * int(num)
                     for idx, num in enumerate(atom_num)).strip()
    return {
        "elements": elements, "elements_str": elements_str, "natom": natom,
        "atom_num": atom_num, "lat1": lat1, "lat2": lat2, "lat3": lat3,
        "types": types, "positions": [lines[8 + i].strip() for i in range(natom)],
    }


def parse_born(path: str = "BORN", natom: int = 0) -> dict:
    """Parse the BORN file (dielectric tensor + Born charges)."""
    if not os.path.isfile(path):
        print("BORN file does not exist; NAC correction will not be applied.")
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    eps = lines[1].split()
    # The first line lists atom-count ranges; append natom as the final bound.
    number = [int(x) for x in re.findall(r"\d+", lines[0])]
    number.append(natom)
    born = [lines[i + 2].split() for i in range(len(number) - 1)]
    return {"eps": eps, "number": number, "Born": born}


def write_control_file(output_path: str, pos: dict, born_info: dict,
                       ngrid: str, scell: str, nano: float, orientation: str,
                       temp_val, is_range: bool, four_ph: float) -> None:
    """Write a CONTROL file to ``output_path`` for the requested temperature."""
    with open(output_path, "w", encoding="utf-8") as handle:
        # &allocations
        handle.write("&allocations\n")
        handle.write(f"\tnelements={len(pos['elements'])}\n")
        handle.write(f"\tnatoms={pos['natom']}\n")
        handle.write(f"\tngrid(:)={ngrid}\n")
        if nano == 1:
            handle.write(f"\tnorientations={len(orientation.split()) // 3}\n")
        handle.write("&end\n")

        # &crystal
        handle.write("&crystal\n")
        handle.write("\tlfactor=0.1\n")
        handle.write(f"\tlattvec(:,1)={pos['lat1']}\n")
        handle.write(f"\tlattvec(:,2)={pos['lat2']}\n")
        handle.write(f"\tlattvec(:,3)={pos['lat3']}\n")
        handle.write(f"\telements={pos['elements_str']}\n")
        handle.write(f"\ttypes={pos['types']}\n")
        for i, position in enumerate(pos['positions']):
            handle.write(f"\tpositions(:,{i + 1})={position}\n")
        if born_info:
            eps = born_info["eps"]
            handle.write(f"\tepsilon(:,1)={eps[0]} {eps[1]} {eps[2]}\n")
            handle.write(f"\tepsilon(:,2)={eps[3]} {eps[4]} {eps[5]}\n")
            handle.write(f"\tepsilon(:,3)={eps[6]} {eps[7]} {eps[8]}\n")
            number, born = born_info["number"], born_info["Born"]
            for i in range(number[0], pos['natom'] + 1):
                for j in range(len(number) - 1):
                    if number[j] <= i <= number[j + 1]:
                        handle.write(f"\tborn(:,1,{i})={born[j][0]} {born[j][1]} {born[j][2]}\n")
                        handle.write(f"\tborn(:,2,{i})={born[j][3]} {born[j][4]} {born[j][5]}\n")
                        handle.write(f"\tborn(:,3,{i})={born[j][6]} {born[j][7]} {born[j][8]}\n")
        handle.write(f"\tscell(:)={scell}\n")
        if nano == 1:
            tokens = orientation.split()
            for j in range(len(tokens) // 3):
                handle.write(f"orientations(:,{j + 1})="
                             f"{tokens[3 * j]} {tokens[3 * j + 1]} {tokens[3 * j + 2]}\n")
        handle.write("&end\n")

        # &parameters
        handle.write("&parameters\n")
        if is_range:
            t = temp_val.split()
            handle.write(f"\tT_min={t[0]}\n \tT_max={t[2]}\n \tT_step={t[1]}\n")
        else:
            handle.write(f"\tT={temp_val}\n")
        handle.write("\tscalebroad=0.2\n")
        if four_ph == 1:
            handle.write("\tnum_sample_process_4ph_phase_space = 10000000\n")
            handle.write("\tnum_sample_process_4ph = 10000000\n")
        handle.write("&end\n")

        # &flags
        handle.write("&flags\n")
        handle.write("\tconvergence=.true.\n \tisotopes=.true.\n \tautoisotopes=.true.\n")
        handle.write("\tnonanalytic=.true.\n" if born_info else "\tnonanalytic=.false.\n")
        if nano == 1:
            handle.write("\tnanowires=.true.\n")
        if four_ph == 1:
            handle.write("\tfour_phonon=.true.\n")
        handle.write("&end\n")


def main():
    # --- User inputs. ------------------------------------------------------
    ngrid = input("Set ngrid (grid planes along each reciprocal axis):\n")
    scell = input("Set supercell sizes along each axis (2nd-order IFC calc):\n")
    nano = ask_float("Calculate nano-line heat transfer? (0 no, 1 yes)")
    orientation = ""
    if nano == 1:
        orientation = input("Set nano-line orientations (3*n dims, space-separated):\n")

    print("\n=== Temperature mode selection ===")
    print("1: single temperature (T=X)")
    print("2: temperature range (T_min T_step T_max)")
    print("3: batch temperatures (one folder per T)")
    temp_mode = int(input("Enter temperature mode (1/2/3): "))

    single_t = None
    t_range = None
    temp_list = []
    if temp_mode == 1:
        single_t = float(input("Enter single temperature (e.g. 300): "))
    elif temp_mode == 2:
        t_range = input("Set the temperature range: (T_min T_step T_max)\n")
    elif temp_mode == 3:
        temp_str = input("Enter batch temperatures (e.g. 300 350 400): ")
        temp_list = [float(t) for t in temp_str.split()]
    else:
        print("Invalid temperature mode!")
        sys.exit(1)

    four_ph = ask_float("\nConsider 4ph? (0 no, 1 yes)")

    # --- Parse POSCAR and BORN. -------------------------------------------
    if not os.path.isfile("POSCAR"):
        print("Sorry, POSCAR does not exist, please double check!")
        sys.exit(1)
    pos = parse_poscar("POSCAR")
    born_info = parse_born("BORN", pos['natom'])

    # --- Emit CONTROL file(s) for the chosen temperature mode. -------------
    if temp_mode == 1:
        write_control_file("CONTROL", pos, born_info, ngrid, scell, nano,
                           orientation, single_t, False, four_ph)
        print(f"CONTROL file for single temperature {single_t} K generated.")
    elif temp_mode == 2:
        write_control_file("CONTROL", pos, born_info, ngrid, scell, nano,
                           orientation, t_range, True, four_ph)
        print("CONTROL file for temperature range generated.")
    elif temp_mode == 3:
        for t in temp_list:
            folder = f"{t:.0f}" if t.is_integer() else f"{t}"
            os.makedirs(folder, exist_ok=True)
            write_control_file(os.path.join(folder, "CONTROL"), pos, born_info,
                               ngrid, scell, nano, orientation, t, False, four_ph)
        print(f"Batch CONTROL files generated for temperatures: {temp_list}")


if __name__ == "__main__":
    main()
