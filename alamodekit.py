#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alamodekit.py
=============

Top-level interactive launcher for the ALAMODEkit toolkit.

The launcher presents a three-level menu (main -> submenu -> function), shows
the required input files for the chosen function, asks for confirmation, and
then runs the target script as a subprocess. The base install path is read
from ``config/settings.yaml`` so the toolkit is relocatable without editing
this file.

Menu structure (mirrors the on-disk folder layout)
--------------------------------------------------
1  Input File Generation
   101 ALM        -> displace_har, esti_har, alm_cv, esti_anhar
   102 ANPHON     -> pre_harphband, pre_harphdos, pre_scph, pre_cal_k
2  Analysis & Plotting
   201 Harmonic Phonon Properties  -> APR_band, phvel_band, plot_harband, plot_hardos
   202 Anharmonic Phonon Properties -> gru_band, phonon_lifetime (analyze_phonons)
   203 CV Calculation Analysis     -> ALMcv_result
   204 Interatomic Force Constants -> ifcs_dis
   205 SCPH Result Analysis       -> scph_band, scph_dos
3  SCPH 2nd Force Constants Processing
   301 dfc2 / 302 FORCE_CONSTANTS
4  ShengBTE Integration
   401 pre_sbtecontrol / 402 post_sbte
5  Run ALAMODE Solvers (alm / anphon)
   501 Run ALM / 502 Run ANPHON
6  Pure-Python Helpers (no solver/source dependency)
   601 Structure pre-processing | 602 Result analysis | 603 Cluster job scripts
   604 Input validation & sweeps | 605 Results archiving
7  External Interfaces & Thermodynamics
   701 Thermodynamics from DOS | 702 NAC parameter extraction (VASP/QE)
   703 Structure export to XSF/CIF/VESTA | 704 ASE bridge | 705 Spectral kappa
   706 Phonon vibration visualisation (.axsf for VESTA)
"""
from __future__ import annotations

import os
import subprocess
import sys

import alamodekit_config  # ensures the toolkit root is importable
from alamodekit_config import get_config_value


# ---------------------------------------------------------------------------
# ASCII banner.
# ---------------------------------------------------------------------------
def display_logo() -> None:
    logo = """
    _    _       _    __  __   ___   ____   _____  _    _ _
   / \\  | |     / \\  |  \\/  | / _ \\ |  _ \\ | ____|| | _(_) |_
  / _ \\ | |    / _ \\ | |\\/| || | | || | | ||  _|  | |/ / | __|
 / ___ \\| |__ / ___ \\| |  | || |_| || |_| || |___ |   <| | |_
/_/   \\_\\____/_/   \\_\\_|  |_| \\___/ |____/ |_____||_|\\_\\_|\\__|
   -------------------------------------------------------------
                Advanced ALAMODE Toolkit (ALAMODEkit)
    """
    print("\033[94m" + logo + "\033[0m")


# ---------------------------------------------------------------------------
# Menu hierarchy. Each leaf function carries the script filename and the list
# of input files that must be present in the working directory.
# ---------------------------------------------------------------------------
HIERARCHICAL_SCRIPTS = {
    "1": {
        "name": "Input File Generation",
        "submenus": {
            "101": {"name": "ALM", "functions": {
                "1": {"id": "10101", "desc": "Prepare input files for harmonic displacement modes",
                      "script": "displace_har.py", "required_files": ["SPOSCAR"]},
                "2": {"id": "10102", "desc": "Prepare input files for fitting harmonic force constants",
                      "script": "esti_har.py", "required_files": ["SPOSCAR"]},
                "3": {"id": "10103", "desc": "Prepare input files for CV calculation",
                      "script": "alm_cv.py", "required_files": ["SPOSCAR"]},
                "4": {"id": "10104", "desc": "Prepare input files for fitting anharmonic force constants",
                      "script": "esti_anhar.py", "required_files": ["SPOSCAR"]},
            }},
            "102": {"name": "ANPHON", "functions": {
                "1": {"id": "10201", "desc": "Prepare harmonic phonon band input files",
                      "script": "pre_harphband.py", "required_files": ["KPATH.in", "POSCAR-unitcell"]},
                "2": {"id": "10202", "desc": "Prepare harmonic phonon DOS input files",
                      "script": "pre_harphdos.py", "required_files": ["POSCAR-unitcell"]},
                "3": {"id": "10203", "desc": "Prepare SCPH calculation input files",
                      "script": "pre_scph.py", "required_files": ["KPATH.in", "POSCAR-unitcell"]},
                "4": {"id": "10204", "desc": "Prepare thermal conductivity calculation input files",
                      "script": "pre_cal_k.py", "required_files": ["POSCAR-unitcell"]},
            }},
        },
    },
    "2": {
        "name": "Analysis & Plotting",
        "submenus": {
            "201": {"name": "Harmonic Phonon Properties", "functions": {
                "1": {"id": "20101", "desc": "Process APR-projected phonon band",
                      "script": "APR_band.py", "required_files": ["XXX.bands", "XXX.band.apr"]},
                "2": {"id": "20102", "desc": "Process phonon group velocity projected band",
                      "script": "phvel_band.py", "required_files": ["XXX.bands", "XXX.phvel"]},
                "3": {"id": "20103", "desc": "Plot harmonic phonon band diagram",
                      "script": "plot_harband.py", "required_files": ["XXX.bands"]},
                "4": {"id": "20104", "desc": "Plot harmonic phonon DOS diagram",
                      "script": "plot_hardos.py", "required_files": ["XXX.dos"]},
            }},
            "202": {"name": "Anharmonic Phonon Properties", "functions": {
                "1": {"id": "20201", "desc": "Process Gruneisen parameter projected band",
                      "script": "gru_band.py", "required_files": ["XXX.bands", "XXX.gruneisen"]},
                "2": {"id": "20202", "desc": "Process phonon lifetime calculation results",
                      "script": "phonon_lifetime.py", "required_files": ["XXX.result"]},
                "3": {"id": "20203", "desc": "Analyze phonon lifetime / thermal conductivity (analyze_phonons)",
                      "script": "analyze_phonons.py", "required_files": ["XXX.result"]},
            }},
            "203": {"name": "CV Calculation Analysis", "functions": {
                "1": {"id": "20301", "desc": "Analyze CV calculation results",
                      "script": "ALMcv_result.py", "required_files": ["XXX.cvscore"]},
            }},
            "204": {"name": "Interatomic Force Constants Analysis", "functions": {
                "1": {"id": "20401", "desc": "Analyze interatomic force constants",
                      "script": "ifcs_dis.py", "required_files": ["FORCE_CONSTANTS_XXX (or *.fcs)"]},
            }},
            "205": {"name": "SCPH Result Analysis", "functions": {
                "1": {"id": "20501", "desc": "Process SCPH-calculated phonon band",
                      "script": "scph_band.py", "required_files": ["XXX.scph_band"]},
                "2": {"id": "20502", "desc": "Process SCPH-calculated phonon DOS",
                      "script": "scph_dos.py", "required_files": ["XXX.scph_dos"]},
            }},
        },
    },
    "3": {
        "name": "SCPH 2nd Force Constants Processing",
        "submenus": {
            "301": {"name": "SCPH-derived 2nd Force Constants", "functions": {
                "1": {"id": "30101", "desc": "Process SCPH-derived 2nd force constants",
                      "script": "dfc2.py", "required_files": ["XML force-constant files"]},
            }},
            "302": {"name": "XML to PhononPy Format", "functions": {
                "1": {"id": "30201", "desc": "Convert XML 2nd force constants to PhononPy format",
                      "script": "FORCE_CONSTANTS.py", "required_files": ["scpb_*K.xml"]},
            }},
        },
    },
    "4": {
        "name": "ShengBTE Integration",
        "submenus": {
            "401": {"name": "ShengBTE Input Preparation", "functions": {
                "1": {"id": "40101", "desc": "Prepare ShengBTE CONTROL input file",
                      "script": "pre_sbtecontrol.py", "required_files": ["POSCAR"]},
            }},
            "402": {"name": "ShengBTE Result Extraction", "functions": {
                "1": {"id": "40201", "desc": "Batch extract ShengBTE calculation results",
                      "script": "post_sbte.py", "required_files": ["ShengBTE output folder (e.g. T300K)"]},
            }},
        },
    },
    "5": {
        "name": "Run ALAMODE Solvers (alm / anphon)",
        "submenus": {
            "501": {"name": "Run ALM", "functions": {
                "1": {"id": "50101", "desc": "Run alm (suggest/optimize) on an input file",
                      "script": "run_alm.py", "required_files": ["alm*.in"]},
            }},
            "502": {"name": "Run ANPHON", "functions": {
                "1": {"id": "50201", "desc": "Run anphon (phonons/RTA/SCPH) on an input file",
                      "script": "run_anphon.py", "required_files": ["phband.in / scph.in / ..."]},
            }},
        },
    },
    "6": {
        "name": "Pure-Python Helpers (no solver/source dependency)",
        "submenus": {
            "601": {"name": "Structure Pre-processing", "functions": {
                "1": {"id": "60101", "desc": "Inspect a POSCAR/CONTCAR structure (+3D preview)",
                      "script": "poscar_info.py", "required_files": ["POSCAR / CONTCAR / SPOSCAR"]},
                "2": {"id": "60102", "desc": "Build a supercell from a POSCAR (-> SPOSCAR)",
                      "script": "build_supercell.py", "required_files": ["POSCAR / CONTCAR"]},
                "3": {"id": "60103", "desc": "Convert POSCAR <-> Quantum ESPRESSO pw.in",
                      "script": "structure_convert.py", "required_files": ["POSCAR or *.pw.in"]},
                "4": {"id": "60104", "desc": "Generate a high-symmetry q-point path",
                      "script": "qpath_generator.py", "required_files": ["(none) -- uses --system/--custom"]},
                "5": {"id": "60105", "desc": "Inspect a DFSET displacement/force dataset",
                      "script": "dfset_inspector.py", "required_files": ["DFSET file"]},
            }},
            "602": {"name": "Result Analysis (pure Python)", "functions": {
                "1": {"id": "60201", "desc": "Analyse thermal conductivity (.kl) file(s)",
                      "script": "kappa_analyzer.py", "required_files": ["*.kl"]},
                "2": {"id": "60202", "desc": "Detect soft / imaginary modes in a .bands file",
                      "script": "softmode_detector.py", "required_files": ["*.bands"]},
                "3": {"id": "60203", "desc": "Compare / overlay several .bands files",
                      "script": "bands_compare.py", "required_files": ["two or more *.bands"]},
            }},
            "603": {"name": "Cluster Job Script Generator", "functions": {
                "1": {"id": "60301", "desc": "Generate a SLURM/PBS/local submission script",
                      "script": "cluster_submit.py", "required_files": ["input file for the solver"]},
            }},
            "604": {"name": "Input Validation & Parameter Sweeps", "functions": {
                "1": {"id": "60401", "desc": "Validate syntax of a namelist-style input file",
                      "script": "input_validator.py", "required_files": ["*.in input file"]},
                "2": {"id": "60402", "desc": "Generate a parameter sweep from a template",
                      "script": "conv_test_helper.py", "required_files": ["template *.in file"]},
            }},
            "605": {"name": "Results Archiving", "functions": {
                "1": {"id": "60501", "desc": "Archive result files into a tar.gz with a README",
                      "script": "results_archive.py", "required_files": ["result files in the folder"]},
            }},
        },
    },
    "7": {
        "name": "External Interfaces & Thermodynamics",
        "submenus": {
            "701": {"name": "Thermodynamics from DOS", "functions": {
                "1": {"id": "70101", "desc": "Compute Cv/F/S/ZPE from a phonon DOS file",
                      "script": "thermo_from_dos.py", "required_files": ["*.dos"]},
            }},
            "702": {"name": "NAC Parameter Extraction (VASP / QE)", "functions": {
                "1": {"id": "70201", "desc": "Extract dielectric tensor + Born charges -> BORN file",
                      "script": "extract_born.py", "required_files": ["OUTCAR or QE output"]},
            }},
            "703": {"name": "Structure Export (XSF/CIF/VESTA)", "functions": {
                "1": {"id": "70301", "desc": "Export a POSCAR to XSF/CIF/VESTA for visualisation",
                      "script": "structure_to_vesta.py", "required_files": ["POSCAR / CONTCAR"]},
            }},
            "704": {"name": "ASE Bridge (optional dependency)", "functions": {
                "1": {"id": "70401", "desc": "Space group / primitive cell / neighbours via ASE",
                      "script": "ase_bridge.py", "required_files": ["POSCAR / cif / ... (needs ase+spglib)"]},
            }},
            "705": {"name": "Spectral Thermal Conductivity", "functions": {
                "1": {"id": "70501", "desc": "Plot mode-resolved kappa(omega) from a .kl_spec file",
                      "script": "kappa_spec.py", "required_files": ["*.kl_spec"]},
            }},
            "706": {"name": "Phonon Vibration Visualisation (VESTA)", "functions": {
                "1": {"id": "70601", "desc": "Generate .axsf animations of phonon modes from an .evec file",
                      "script": "vib_vesta.py", "required_files": ["POSCAR", "*.evec / *.band.evec / *.mesh.evec"]},
            }},
        },
    },
}


# ---------------------------------------------------------------------------
# Resolve each function's script path. The base path is configurable in
# settings.yaml so the toolkit can live anywhere on the filesystem.
# ---------------------------------------------------------------------------
def _base_path() -> str:
    """Return the toolkit installation root from settings.yaml."""
    path = get_config_value("alamodekit", "base_path", default=None)
    if path:
        return os.path.expanduser(path)
    # Fall back to the directory this file lives in.
    return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = _base_path()


def build_script_paths() -> dict:
    """Map every function id to its script path, description and inputs."""
    paths = {}
    for l1, l1_data in HIERARCHICAL_SCRIPTS.items():
        for l2, l2_data in l1_data["submenus"].items():
            for _, fval in l2_data["functions"].items():
                sub = f"No.{l1}/{l2}"
                full = os.path.join(BASE_PATH, sub, fval["script"])
                paths[fval["id"]] = {
                    "path": full,
                    "desc": fval["desc"],
                    "required": fval["required_files"],
                }
    return paths


SCRIPT_PATHS = build_script_paths()


# ---------------------------------------------------------------------------
# Menu rendering.
# ---------------------------------------------------------------------------
def display_level1() -> None:
    menu = "\n========================== ALAMODEkit MAIN MENU ==========================\n"
    for k, v in HIERARCHICAL_SCRIPTS.items():
        menu += f"  [{k}] {v['name']}\n"
    menu += "\n[q] Quit\n======================================================================\n"
    print(menu)


def display_level2(l1: str) -> None:
    data = HIERARCHICAL_SCRIPTS[l1]
    menu = f"\n========================== {data['name']} ==========================\n"
    for k, v in data["submenus"].items():
        menu += f"  [{k}] {v['name']}\n"
    menu += "\n[b] Back | [q] Quit\n======================================================================\n"
    print(menu)


def display_level3(l1: str, l2: str) -> None:
    data = HIERARCHICAL_SCRIPTS[l1]["submenus"][l2]
    menu = f"\n========================== {data['name']} ==========================\n"
    for k, v in data["functions"].items():
        menu += f"  [{k}] {v['desc']}\n"
    menu += "\n[b] Back | [q] Quit\n======================================================================\n"
    print(menu)


def show_info_and_confirm(func_id: str) -> bool:
    """Show the required files for ``func_id`` and ask whether to proceed."""
    info = SCRIPT_PATHS[func_id]
    print("\n" + "=" * 60)
    print("REQUIRED FILES (MUST EXIST IN CURRENT DIRECTORY):")
    for f in info["required"]:
        print(f"  - {f}")
    print("=" * 60)
    while True:
        choice = input("\nProceed to execute? (y/n): ").strip().lower()
        if choice == "y":
            return True
        if choice == "n":
            print("Execution canceled. Exiting program...")
            return False
        print("Invalid input! Enter 'y' or 'n'.")


def execute_script(func_id: str) -> None:
    """Run the script referenced by ``func_id`` as a subprocess."""
    info = SCRIPT_PATHS[func_id]
    path = info["path"]
    if not os.path.exists(path):
        print(f"\nERROR: Script not found!\nPath: {path}")
        print(f"Check: folder {os.path.dirname(path)} contains {os.path.basename(path)}")
        sys.exit(1)

    print(f"\nExecuting: {info['desc']}")
    print(f"Script: {os.path.basename(path)}")
    print("-" * 50)
    try:
        # Run the script interactively in the foreground so it can prompt.
        subprocess.run([sys.executable, path], check=True, text=True)
        print("-" * 50)
        print("SUCCESS: Script executed successfully!")
    except subprocess.CalledProcessError as exc:
        print("-" * 50)
        print(f"FAILED: Script exited with error code {exc.returncode}")
        sys.exit(1)


def main():
    display_logo()
    print("Welcome to ALAMODEkit - Interactive ALAMODE Toolkit")
    level, l1, l2 = 1, "", ""
    while True:
        if level == 1:
            display_level1()
            ipt = input("Select main menu: ").strip().lower()
            if ipt == "q":
                print("\nGoodbye!")
                return
            if ipt in HIERARCHICAL_SCRIPTS:
                l1, level = ipt, 2
            continue
        if level == 2:
            display_level2(l1)
            ipt = input("Select submenu: ").strip().lower()
            if ipt == "q":
                print("\nGoodbye!")
                return
            if ipt == "b":
                level = 1
            elif ipt in HIERARCHICAL_SCRIPTS[l1]["submenus"]:
                l2, level = ipt, 3
            continue
        if level == 3:
            display_level3(l1, l2)
            ipt = input("Select function: ").strip().lower()
            if ipt == "q":
                print("\nGoodbye!")
                return
            if ipt == "b":
                level = 2
            elif ipt in HIERARCHICAL_SCRIPTS[l1]["submenus"][l2]["functions"]:
                func_id = HIERARCHICAL_SCRIPTS[l1]["submenus"][l2]["functions"][ipt]["id"]
                if show_info_and_confirm(func_id):
                    execute_script(func_id)
                    return
            continue


if __name__ == "__main__":
    main()
