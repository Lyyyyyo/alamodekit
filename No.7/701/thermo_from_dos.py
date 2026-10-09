#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thermo_from_dos.py
==================

Post-processing helper: compute lattice-thermodynamic quantities from a
phonon density of states.

Given a phonon DOS g(omega) (states per unit frequency per primitive cell),
the standard statistical-mechanics expressions for a harmonic lattice are

    ZPE = (1/2) * integral hbar*omega * g(omega) d omega

    U(T) = integral hbar*omega * [ n(omega,T) + 1/2 ] * g(omega) d omega

    F(T) = integral [ hbar*omega/2 + k_B*T*ln(1 - exp(-hbar*omega/k_B*T)) ]
                      * g(omega) d omega

    S(T) = ( U(T) - F(T) ) / T

    C_v(T) = k_B * integral (hbar*omega/k_B*T)^2
             * exp(x)/(exp(x)-1)^2 * g(omega) d omega

where n(omega,T) = 1/(exp(hbar*omega/k_B*T) - 1) is the Bose-Einstein
distribution and x = hbar*omega/k_B*T.

These are textbook formulas (no program-specific code). The frequency is
read in cm^-1 (the unit used by ALAMODE .dos files); the conversion
hc/k_B = 1.4387770 cm*K is used to build the dimensionless x.

Outputs: a table of T, ZPE, U, F, S, C_v printed to the terminal, a CSV file,
and (optionally) a figure of C_v(T).

Usage
-----
    python thermo_from_dos.py Si.dos --tmin 0 --tmax 1000 --tstep 10 --yes
"""
from __future__ import annotations

import os
import sys
import argparse
import csv
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402

# Physical constants (CODATA-ish, sufficient precision).
# h*c / k_B in units of (cm^-1)*K  ->  1.4387770 cm K
HC_OVER_KB = 1.4387770
# h*c in J*cm  ->  1.98644586e-23 J*cm  (energy per cm^-1)
HC_J_CM = 1.98644586e-23
# Avogadro number (to express per-mole quantities).
N_A = 6.02214076e23
KB = 1.380649e-23  # J/K


def parse_dos(path: str):
    """Read a .dos file: 3 header lines, then (freq_cm1, dos, [proj...]).

    Returns (frequency cm^-1, total_dos).
    """
    data = np.loadtxt(path, skiprows=3)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data[:, 0], data[:, 1]


def bose(x):
    """Bose-Einstein occupation n = 1/(exp(x)-1); x = hbar*w/(k_B*T)."""
    # Clip to avoid overflow for very small x (high T / low freq).
    xs = np.clip(x, 1e-12, 700.0)
    return 1.0 / (np.exp(xs) - 1.0)


def thermodynamics(freq, dos, temperatures):
    """Return arrays ZPE, U, F, S, Cv over the given temperatures.

    Units returned: per primitive cell. Multiply by N_A/1000 to get kJ/mol
    for energies, J/(mol*K) for S and Cv.
    """
    freq = np.asarray(freq, dtype=float)
    dos = np.asarray(dos, dtype=float)
    # Use the spacing of the frequency grid for the trapezoidal integration.
    # dw in cm^-1; energy in J via HC_J_CM.
    dw = np.empty_like(freq)
    dw[1:-1] = 0.5 * (freq[2:] - freq[:-2])
    dw[0] = 0.5 * (freq[1] - freq[0])
    dw[-1] = 0.5 * (freq[-1] - freq[-2])

    # Zero-point energy (temperature-independent).
    zpe = float(np.sum(0.5 * HC_J_CM * freq * dos * dw))

    U = np.zeros_like(temperatures, dtype=float)
    F = np.zeros_like(temperatures, dtype=float)
    Cv = np.zeros_like(temperatures, dtype=float)

    for i, T in enumerate(temperatures):
        if T <= 0:
            # At T=0 only the ZPE contributes; U=ZPE, F=ZPE, S=0, Cv=0.
            U[i] = zpe
            F[i] = zpe
            continue
        x = HC_OVER_KB * freq / T
        n = bose(x)
        # Internal energy (excluding the static 1/2 which is the ZPE).
        U[i] = zpe + float(np.sum(HC_J_CM * freq * n * dos * dw))
        # Helmholtz free energy.
        # F = ZPE + k_B*T * sum ln(1-exp(-x)) * g(w) dw
        # clip x to avoid log(0) at w=0
        xc = np.clip(x, 1e-12, 700.0)
        F[i] = zpe + float(np.sum(KB * T * np.log1p(-np.exp(-xc)) * dos * dw))
        # Heat capacity:  k_B * sum x^2 * e^x/(e^x-1)^2 * g(w) dw
        ex = np.exp(xc)
        Cv[i] = float(np.sum(KB * x**2 * ex / (ex - 1.0)**2 * dos * dw))
    S = np.where(temperatures > 0, (U - F) / np.where(temperatures > 0,
                                                       temperatures, 1.0), 0.0)
    return zpe, U, F, S, Cv


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute lattice thermodynamics from a phonon DOS.")
    parser.add_argument("file", help="*.dos file")
    parser.add_argument("--tmin", type=float, default=0.0, help="Min T (K)")
    parser.add_argument("--tmax", type=float, default=1000.0, help="Max T (K)")
    parser.add_argument("--tstep", type=float, default=50.0, help="T step (K)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Also draw the C_v(T) figure")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)

    freq, dos = parse_dos(args.file)
    temps = np.arange(args.tmin, args.tmax + args.tstep / 2, args.tstep)
    zpe, U, F, S, Cv = thermodynamics(freq, dos, temps)

    # Per-mole conversions (kJ/mol, J/mol/K).
    zpe_mol = zpe * N_A / 1000.0
    U_mol = U * N_A / 1000.0
    F_mol = F * N_A / 1000.0
    S_mol = S * N_A
    Cv_mol = Cv * N_A
    # ZPE in meV/cell: 1 eV = 1.602176634e-19 J  ->  1 meV = 1.602176634e-22 J.
    zpe_mev = zpe / 1.602176634e-22

    # Sanity check: the DOS integral should equal 3*N (number of modes).
    dos_integral = float(np.trapz(dos, freq))

    print("=" * 60)
    print(f"File: {args.file}")
    print(f"DOS integral (should be ~3*N modes): {dos_integral:.4f}")
    print(f"Zero-point energy: {zpe_mev:.4f} meV/cell  ({zpe_mol:.4f} kJ/mol)")
    print("-" * 72)
    print(f"{'T(K)':>7} {'U(kJ/mol)':>12} {'F(kJ/mol)':>12} "
          f"{'S(J/mol/K)':>12} {'Cv(J/mol/K)':>12}")
    for i, T in enumerate(temps):
        print(f"{T:7.1f} {U_mol[i]:12.4f} {F_mol[i]:12.4f} "
              f"{S_mol[i]:12.4f} {Cv_mol[i]:12.4f}")
    print("=" * 60)

    # CSV output.
    base = os.path.splitext(args.file)[0]
    csv_path = base + "_thermo.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["T(K)", "U(kJ/mol)", "F(kJ/mol)", "S(J/mol/K)",
                    "Cv(J/mol/K)"])
        for i, T in enumerate(temps):
            w.writerow([f"{T:.2f}", f"{U_mol[i]:.6f}", f"{F_mol[i]:.6f}",
                        f"{S_mol[i]:.6f}", f"{Cv_mol[i]:.6f}"])
    print(f"Wrote CSV -> {csv_path}")

    if args.yes:
        _plot_cv(temps, Cv_mol, base)


def _plot_cv(temps, cv_mol, out_base):
    from plot_style import apply_plot_style, save_figure
    import matplotlib.pyplot as plt
    cfg = apply_plot_style()
    lw = cfg["plotting"]["lines"].get("linewidth", 2.0)
    color = cfg["plotting"]["colors"]["palette"][0]
    fig, ax = plt.subplots(figsize=cfg["plotting"]["figsize"])
    ax.plot(temps, cv_mol, "-o", color=color, linewidth=lw, markersize=4,
            label=r"$C_v$")
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel(r"$C_v$ (J mol$^{-1}$ K$^{-1}$)")
    ax.set_title("Lattice heat capacity from phonon DOS",
                 fontsize=cfg["plotting"]["font"]["title_size"])
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, out_base + "_Cv", cfg=cfg)
    plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()
