#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifcs_dis.py
===========

Plot interatomic force constants (IFCs) versus atomic distance from an
ALAMODE ``*.fcs`` file.

The script detects the highest IFC order present (2nd..6th), extracts each
order's |IFC| together with the interatomic distance, writes a per-order
text file, and scatters them on a single log-friendly plot.

Per-order colors come from the palette in ``config/settings.yaml``; DPI,
figure size and output formats are likewise controlled there.

Usage
-----
    python ifcs_dis.py IFCs2ND.fcs
"""
from __future__ import annotations

import os
import sys
import argparse

import alamodekit_io
alamodekit_io.ensure_package_root()

import numpy as np
import matplotlib.pyplot as plt

from plot_style import (apply_plot_style, save_figure, make_figure,
                        get_palette, apply_grid)
from alamodekit_config import get_plotting_config


class _Constants:
    """Physical conversion factors used to express IFCs in eV / Angstrom^n."""
    ang_to_bohr = 1.8897259886
    ry_to_ev = 13.605698066
    bohr_to_ang = 0.529177249


class FcsDistance:
    """One IFC entry: its global index, magnitude and distance (Bohr)."""
    __slots__ = ('globalindex', 'fcs', 'distance')

    def __init__(self, globalindex: int, fcs: float, distance: float):
        self.globalindex = globalindex
        self.fcs = fcs
        self.distance = distance


class FcsDistanceReader:
    """Read an ALAMODE ``*.fcs`` file and expose per-order IFC/distance data."""

    def __init__(self, fcs_filename: str):
        self.fcs_filename = fcs_filename
        self.maxorder = 0
        self.localindex: list = []
        self.force_constant_with_distance: list = []

    def _order_present(self, order: int) -> bool:
        """True if the file contains a top-level ``*FC<order>`` block."""
        marker = f"*FC{order}"
        nested = f"**FC{order}"
        with open(self.fcs_filename, 'r', encoding='utf-8') as handle:
            for line in handle:
                if marker in line and nested not in line:
                    return True
        return False

    def get_order(self) -> None:
        """Detect the maximum IFC order (2..6) present in the file."""
        present = [self._order_present(o) for o in range(2, 7)]
        self.maxorder = sum(present)
        print("-" * 34)
        print("maxorder is ::", self.maxorder + 1)

    def get_localindex(self) -> None:
        """Count the number of entries within each present order block."""
        self.localindex = [-1] * self.maxorder
        for i in range(self.maxorder):
            order = i + 2
            marker, nested = f"*FC{order}", f"**FC{order}"
            counting = False
            with open(self.fcs_filename, 'r', encoding='utf-8') as handle:
                for line in handle:
                    if counting:
                        if line == "\n":
                            break
                        self.localindex[i] += 1
                    if marker in line and nested not in line:
                        counting = True
                        self.localindex[i] = 0
        print("-" * 34)
        print("local index for each order ::", self.localindex)

    def get_fcs(self) -> None:
        """Read (globalindex, fcs, distance) for every entry per order."""
        self.force_constant_with_distance = [[] for _ in range(self.maxorder)]
        for i in range(self.maxorder):
            order = i + 2
            marker, nested = f"*FC{order}", f"**FC{order}"
            counting = False
            with open(self.fcs_filename, 'r', encoding='utf-8') as handle:
                for line in handle:
                    if counting:
                        if line == "\n":
                            break
                        tok = line.split()
                        self.force_constant_with_distance[i].append(
                            FcsDistance(int(tok[0]), float(tok[2]),
                                        float(tok[6 + i])))
                    if marker in line and nested not in line:
                        counting = True
        print("-" * 34)
        print("finished loading fcs and distances")

    def make_plots(self) -> None:
        """Scatter |IFC| vs distance for every order on one axes."""
        cfg = apply_plot_style()
        fig, ax = make_figure(figsize=(10, 6))
        palette = get_palette()
        c = _Constants()

        for i in range(self.maxorder):
            if self.localindex[i] <= 0:
                continue
            order = i + 2
            n = self.localindex[i]
            dist = np.array([self.force_constant_with_distance[i][j].distance
                             * c.bohr_to_ang for j in range(n)])
            val = np.array([self.force_constant_with_distance[i][j].fcs
                            * c.ry_to_ev / (c.bohr_to_ang ** order)
                            for j in range(n)])
            with open(f"{order}th_order_ifc.txt", "w", encoding='utf-8') as out:
                for x, y in zip(dist, val):
                    out.write(f"{x:.6f} {y:.6f}\n")
            color = palette[i % len(palette)]
            ax.scatter(dist, np.abs(val), color=color, label=f"{order}th IFC",
                       alpha=0.6, s=30)

        ax.set_xlim(0, 10)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Distance (\u00c5)", fontsize=16, fontweight='bold')
        ax.set_ylabel("|IFCs| (eV/\u00c5$^n$)", fontsize=16, fontweight='bold')
        ax.tick_params(axis='both', labelsize=14, direction='in',
                       top=True, right=True)
        ax.legend(loc='upper right', fontsize=14, framealpha=0.9)
        apply_grid(ax)
        fig.tight_layout()
        save_figure(fig, "all_orders_ifc_vs_distance", cfg=cfg)
        plt.show()
        plt.close(fig)

    def process(self) -> None:
        self.get_order()
        self.get_localindex()
        self.get_fcs()
        self.make_plots()


def parse_cml_args(cml):
    """Parse the single positional argument: the .fcs file path."""
    parser = argparse.ArgumentParser(add_help=True,
                                     description="Plot IFCs vs distance.")
    parser.add_argument('file', help='ALAMODE ifc file (.fcs)')
    return parser.parse_args(cml)


def main(fcs_filename: str) -> None:
    print("\ninput filename :: {}".format(fcs_filename))
    FcsDistanceReader(fcs_filename).process()


if __name__ == '__main__':
    print("*" * 65)
    print("                       ifcs_dis.py")
    print("                Version 0.1.0 (config-driven)")
    print("*" * 65)
    args = parse_cml_args(sys.argv[1:])
    if not args.file:
        print("ERROR: alm file (.fcs or .xml) is not specified.")
        sys.exit(1)
    if not args.file.endswith("fcs"):
        print("WARNING: filename does not end with 'fcs'.")
    main(args.file)
