#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
post_sbte.py
============

ShengBTE post-processing program for 3D periodic materials.

Given the per-temperature directories ``T*K`` produced by ShengBTE, this
script consolidates the raw outputs into tidy CSV files:

* group velocities
* Gruneisen parameters
* scattering rates / lifetimes / mean free paths (3ph + optional 4ph)
* phase-space (WP3 / WP4)
* cumulative thermal conductivity (by MFP and by frequency)

This is the refactored, English-commented version of the original author's
script (Xin Liu, 3480235563@qq.com); behaviour is preserved while fixing the
duplicate-``.csv`` filename bug in the coherent cumulative kappa output.
"""
from __future__ import annotations

import os
import sys
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

# Suppress the harmless pandas whitespace-delimited-read warning.
warnings.filterwarnings("ignore")

# ---- Constants (centralised for easy maintenance). ------------------------
CONV_2PI = 1 / (2 * np.pi)        # angular frequency -> THz
UNIT_CONV_MFP = 10                # MFP unit conversion factor (-> Angstrom)
GRUNEISEN_CATEGORIES = ["ZA", "TA", "LA", "OPTICAL"]
TEMP_DIR_PREFIX = "T"
TEMP_DIR_SUFFIX = "K"


# ---------------------------------------------------------------------------
# Helper utilities.
# ---------------------------------------------------------------------------
def get_temperature_dirs() -> list:
    """Return the list of ``T*K`` directories in the current folder."""
    current_dir = os.path.abspath(".")
    temp_dirs = []
    for item in os.listdir(current_dir):
        path = os.path.join(current_dir, item)
        if os.path.isdir(path) and item.startswith(TEMP_DIR_PREFIX) \
                and item.endswith(TEMP_DIR_SUFFIX):
            temp_dirs.append(item)
    if not temp_dirs:
        raise FileNotFoundError(
            "No temperature directory found (expected format T*K, e.g. T300K).")
    return temp_dirs


def safe_read_csv(file_path: str, **kwargs) -> pd.DataFrame:
    """Read a whitespace-delimited CSV, raising on missing/bad files."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")
    try:
        return pd.read_csv(file_path, header=None,
                          delim_whitespace=True, **kwargs)
    except Exception as exc:
        raise RuntimeError(f"Failed to read {file_path}: {exc}")


# ---------------------------------------------------------------------------
# Per-quantity processors.
# ---------------------------------------------------------------------------
def process_group_velocities(temp_dirs: list) -> None:
    """Compute |v_x|, |v_y|, |v_z| and total velocity; write group_velocities.csv."""
    gruneisen_df = safe_read_csv("./BTE.gruneisen")
    n_rows = gruneisen_df.shape[0]
    freq_df = safe_read_csv(os.path.join(temp_dirs[0], "BTE.w_final"))
    gv = safe_read_csv("./BTE.v")  # columns 0,1,2 -> vx,vy,vz

    gv["frequency_thz"] = freq_df[0] * CONV_2PI
    gv["vx_abs"] = gv[0].abs()
    gv["vy_abs"] = gv[1].abs()
    gv["vz_abs"] = gv[2].abs()
    gv["v_total"] = np.sqrt(gv["vx_abs"] ** 2 + gv["vy_abs"] ** 2 + gv["vz_abs"] ** 2)

    # Insert NaN separators at the same offsets ShengBTE uses.
    for pos in (n_rows, 2 * n_rows + 1, 3 * n_rows + 2):
        pos = min(pos, len(gv))
        nan_row = pd.DataFrame([[np.nan] * len(gv.columns)], columns=gv.columns)
        gv = pd.concat([gv.iloc[:pos], nan_row, gv.iloc[pos:]], ignore_index=True)

    cols = ["frequency_thz", "vx_abs", "vy_abs", "vz_abs", "v_total"]
    gv[cols].to_csv("./group_velocities.csv", index=False,
                    header=["Frequency/THZ", "vx/km/s", "vy/km/s", "vz/km/s", "vtot/km/s"])


def process_gruneisen_parameters(temp_dirs: list) -> None:
    """Group Gruneisen parameters by acoustic/optical category; write gruneisen.csv."""
    gruneisen_df = safe_read_csv("./BTE.gruneisen")
    n_rows, n_cols = gruneisen_df.shape

    # Break points partition columns into ZA / TA / LA / OPTICAL.
    break_points = [1, 2, 3, n_cols]
    grouped = defaultdict(list)
    for col in gruneisen_df.columns:
        assigned = False
        for bp in break_points:
            if col < bp and not assigned:
                grouped[bp] += list(gruneisen_df[col])
                assigned = True
            elif not assigned:
                grouped[bp] += [np.nan] * n_rows

    out_df = pd.DataFrame(grouped.values(), index=GRUNEISEN_CATEGORIES).T
    freq_df = safe_read_csv(os.path.join(temp_dirs[0], "BTE.w_final"))
    out_df["Frequency/THZ"] = freq_df[0] * CONV_2PI
    out_df[["Frequency/THZ"] + GRUNEISEN_CATEGORIES].to_csv("gruneisen.csv", index=False)


def process_scattering_properties(temp_dirs: list) -> None:
    """Scattering rates / lifetimes / MFP and 3ph+4ph breakdown per temperature."""
    gv = safe_read_csv("./BTE.v")
    gv["v_total"] = np.sqrt(gv[0] ** 2 + gv[1] ** 2 + gv[2] ** 2)

    for temp_dir in temp_dirs:
        base = os.path.join(".", temp_dir)
        print(f"Processing scattering data for {temp_dir}...")

        # --- Total scattering rate, lifetime, MFP. --------------------------
        freq_df = safe_read_csv(os.path.join(base, "BTE.w_final"))
        scatter = freq_df.copy()
        scatter[0] = freq_df[0] * CONV_2PI          # frequency (THz)
        scatter[2] = 1.0 / scatter[1]              # lifetime = 1 / rate
        scatter[3] = gv["v_total"] / scatter[1] * UNIT_CONV_MFP  # MFP
        scatter.to_csv(os.path.join(base, "total_scattering_rate&MFP.csv"),
                       index=False,
                       header=["Frequency/THZ", "scattering rate/ps-1",
                               "lifetime/ps", "Mean free path/A"])

        # --- 3ph / 4ph breakdown. ------------------------------------------
        ph3 = [safe_read_csv(os.path.join(base, f))
               for f in ("BTE.w_3ph", "BTE.w_3ph_plus", "BTE.w_3ph_minus")]
        ph = ph3[0].copy()
        ph[0] = freq_df[0] * CONV_2PI
        ph[2] = ph3[1][1]
        ph[3] = ph3[2][1]

        if os.path.exists(os.path.join(base, "BTE.w_4ph")):
            ph4 = [safe_read_csv(os.path.join(base, f))
                   for f in ("BTE.w_4ph", "BTE.w_4ph_plusplus",
                             "BTE.w_4ph_plusminus", "BTE.w_4ph_minusminus")]
            ph[4] = ph4[0][1]
            ph[5] = ph4[1][1]
            ph[6] = ph4[2][1]
            ph[7] = ph4[3][1]
            headers = ["Frequency/THZ", "3ph/ps-1", "3ph plus/ps-1", "3ph minus/ps-1",
                       "4ph/ps-1", "4ph plusplus/ps-1", "4ph plusminus/ps-1",
                       "4ph minusminus/ps-1"]
        else:
            ph = ph.iloc[:, :4]
            headers = ["Frequency/THZ", "3ph/ps-1", "3ph plus/ps-1", "3ph minus/ps-1"]
        ph.to_csv(os.path.join(base, "3ph&4ph_scattering_rate.csv"),
                  index=False, header=headers)


def process_phase_space(temp_dirs: list) -> None:
    """Phase-space files WP3 (+ WP4 if present) per temperature."""
    for temp_dir in temp_dirs:
        base = os.path.join(".", temp_dir)
        print(f"Processing phase-space data for {temp_dir}...")

        wp3 = [safe_read_csv(os.path.join(base, f))
               for f in ("BTE.WP3", "BTE.WP3_plus", "BTE.WP3_minus")]
        wp3_df = wp3[0].copy()
        wp3_df[0] = wp3_df[0] * CONV_2PI
        wp3_df[2] = wp3[1][1]
        wp3_df[3] = wp3[2][1]
        wp3_df.to_csv(os.path.join(base, "WP3.csv"), index=False,
                      header=["Frequency/THZ", "Wtot", "W+", "W-"])

        if os.path.exists(os.path.join(base, "BTE.WP4")):
            wp4 = [safe_read_csv(os.path.join(base, f))
                   for f in ("BTE.WP4", "BTE.WP4_plusplus",
                             "BTE.WP4_plusminus", "BTE.WP4_minusminus")]
            wp4_df = wp4[0].copy()
            wp4_df[0] = wp4_df[0] * CONV_2PI
            wp4_df[2] = wp4[1][1]
            wp4_df[3] = wp4[2][1]
            wp4_df[4] = wp4[3][1]
            wp4_df.to_csv(os.path.join(base, "WP4.csv"), index=False,
                          header=["Frequency/THZ", "Wtot", "W++", "W+-", "W--"])


def process_cumulative_kappa(temp_dirs: list) -> None:
    """Cumulative thermal conductivity by MFP and by frequency, per temperature."""
    keep_cols = [1, 5, 9]  # diagonal k_xx, k_yy, k_zz tensor elements
    drop_cols = [2, 3, 4, 6, 7, 8]

    for temp_dir in temp_dirs:
        base = os.path.join(".", temp_dir)
        print(f"Processing cumulative kappa for {temp_dir}...")

        # --- By MFP, incoherent. -------------------------------------------
        kt = safe_read_csv(os.path.join(base, "BTE.cumulative_kappa_tensor"))
        ks = safe_read_csv(os.path.join(base, "BTE.cumulative_kappa_scalar"))
        kt[10] = ks[1]
        kt = kt.drop(drop_cols, axis=1)
        kt.to_csv(os.path.join(base, "kp_cumulative_kappa_MFP.csv"), index=False,
                  header=["Mean free path/nm", "kxx", "kyy", "kzz", "kscalar"])

        # --- By MFP, coherent. ---------------------------------------------
        ktc = safe_read_csv(os.path.join(base, "BTE.cumulative_kappa_coh_tensor"))
        ksc = safe_read_csv(os.path.join(base, "BTE.cumulative_kappa_coh_scalar"))
        ktc[10] = ksc[1]
        ktc = ktc.drop(drop_cols, axis=1)
        ktc.to_csv(os.path.join(base, "kc_cumulative_kappa_MFP.csv"), index=False,
                   header=["Mean free path/nm", "kxx", "kyy", "kzz", "kscalar"])

        # --- By frequency, incoherent. -------------------------------------
        ko = safe_read_csv(os.path.join(base, "BTE.cumulative_kappaVsOmega_tensor"))
        ko[0] = ko[0] * CONV_2PI
        ko[10] = (ko[1] + ko[5] + ko[9]) / 3.0
        ko = ko.drop(drop_cols, axis=1)
        ko.to_csv(os.path.join(base, "kp_cumulative_kappa_Omega.csv"), index=False,
                  header=["Frequency/THZ", "kxx", "kyy", "kzz", "kscalar"])

        # --- By frequency, coherent (fixed duplicate .csv bug). ------------
        koc = safe_read_csv(os.path.join(base, "BTE.cumulative_kappa_cohVsOmega_tensor"))
        koc[0] = koc[0] * CONV_2PI
        koc[10] = (koc[1] + koc[5] + koc[9]) / 3.0
        koc = koc.drop(drop_cols, axis=1)
        koc.to_csv(os.path.join(base, "kc_cumulative_kappa_Omega.csv"), index=False,
                   header=["Frequency/THZ", "kxx", "kyy", "kzz", "kscalar"])


def main():
    """Run every processor in order, reporting progress."""
    try:
        print("Starting ShengBTE post-processing...")
        temp_dirs = get_temperature_dirs()
        print(f"Detected temperature directories: {temp_dirs}")

        process_group_velocities(temp_dirs)
        print("Group velocities processed.")
        process_gruneisen_parameters(temp_dirs)
        print("Gruneisen parameters processed.")
        process_scattering_properties(temp_dirs)
        print("Scattering rates / lifetimes / MFP processed.")
        process_phase_space(temp_dirs)
        print("Phase-space data processed.")
        process_cumulative_kappa(temp_dirs)
        print("Cumulative kappa processed.")

        print("\nCongratulations!")
        print("ShengBTE post-processing has ended successfully!")
        print("Please check the CSV files under the main directory "
              "and the temperature-dependent subdirectories.")
    except Exception as exc:
        print(f"\nExecution error: {exc}")
        raise


if __name__ == "__main__":
    main()
