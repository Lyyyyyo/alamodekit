#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vib_vesta.py
============

Post-processing helper: generate VESTA / XCrySDen-readable ``.axsf`` animation
files of phonon vibration modes from an ALAMODE eigenvector file (``*.evec``,
``*.band.evec`` or ``*.mesh.evec``) and a structure file (POSCAR).

This is a **pure-Python** tool: it only reads two text files (an ``.evec`` and a
POSCAR) and writes ``.axsf`` files. It does not call any ALAMODE binary and
contains no ALAMODE source. The vibration model is the standard textbook
lattice-dynamics description of a phonon normal mode:

    u(R, kappa, t) = A * sqrt(m_min / m_kappa) * |e(kappa)|
                    * sin( 2*pi * (k . R) + arg(e(kappa)) + 2*pi*t/N )

where
    e(kappa)   : the (mass-weighted) complex eigenvector component of atom
                 ``kappa`` for the mode (read from the .evec file),
    R          : the integer lattice-translation vector of a cell inside the
                 supercell used to visualise the mode,
    k . R      : the inter-cell phase (the reason a super-cell is needed for
                 any k-point away from Gamma),
    m_kappa    : the atomic mass (read from the .evec header),
    A          : a user amplitude (Angstrom),
    t = 0..N-1 : the animation time step (N frames per period).

For a Gamma-point mode the phase k.R vanishes and the primitive cell itself
is the animation cell. For a generic k-point a super-cell of size
``--dim nx ny nz`` is built (it should be commensurate with k).

Output
------
One ``<prefix>_k<k>_mode<m>.axsf`` file per requested mode, each containing
``--frames`` PRIMCOORD blocks. Open it in VESTA and use the animation toolbar
(or File > Render) to play the vibration.

Usage
-----
    # Gamma-point modes (most common), primitive cell:
    python vib_vesta.py POSCAR Si.band.evec --kpoint 1 --modes all

    # Specific modes, custom amplitude and frame count:
    python vib_vesta.py POSCAR Si.band.evec -k 1 --modes 4,5,6 --amp 0.4 --frames 12

    # A generic k-point (needs a commensurate super-cell):
    python vib_vesta.py POSCAR Si.mesh.evec -k 12 --modes all --dim 2 2 2
"""
from __future__ import annotations

import os
import sys
import argparse
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


# --------------------------------------------------------------------------- #
# .evec parser.
# --------------------------------------------------------------------------- #
def parse_evec(path: str):
    """Parse an ALAMODE ``.evec`` file.

    Returns a dict with:
      lattice   : (3,3) primitive lattice vectors (row vectors,
                  i.e. lattice[i] is the i-th vector), in Angstrom.
      masses    : list of per-kind masses.
      nk        : number of k-points.
      nbands    : number of phonon modes (= 3 * natmin).
      kpoints   : (nk,3) array of k-point fractional coordinates.
      omega2    : (nk,nbands) array of omega^2 (signed: negative for imag.).
      evec      : (nk,nbands,3*natmin) complex array of eigenvectors.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    def find(prefix, start=0):
        """Return the index of the first line starting with ``prefix``."""
        for i in range(start, len(lines)):
            if lines[i].strip().startswith(prefix):
                return i
        return -1

    # Primitive lattice vectors (column-major in the file -> transpose).
    i = find("# Lattice vectors")
    if i < 0:
        raise ValueError("Missing '# Lattice vectors' header.")
    lat_raw = np.array([[float(x) for x in lines[i + 1 + k].split()[:3]]
                        for k in range(3)])
    lattice = lat_raw.T

    # Header fields (scanned anywhere in the file).
    nbands = nk = None
    masses = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("# Number of phonon modes"):
            nbands = int(s.split(":")[1])
        elif s.startswith("# Number of k points"):
            nk = int(s.split(":")[1])
        elif s.startswith("# Atomic masses"):
            masses = [float(x) for x in s.split(":")[1].split()]
    if nbands is None or nk is None or not masses:
        raise ValueError("Could not parse the .evec header (modes/kpoints/masses).")

    natmin = nbands // 3
    kpoints = np.zeros((nk, 3))
    omega2 = np.zeros((nk, nbands))
    evec = np.zeros((nk, nbands, 3 * natmin), dtype=complex)

    # Scan for k-point (##) and mode (###) blocks.
    ik = 0
    i = 0
    while i < len(lines) and ik < nk:
        s = lines[i].strip()
        if s.startswith("## kpoint"):
            kpoints[ik] = [float(x) for x in s.split(":")[1].split()[:3]]
            i += 1
            im = 0
            while i < len(lines) and im < nbands:
                s = lines[i].strip()
                if s.startswith("### mode"):
                    omega2[ik, im] = float(s.split(":")[1])
                    i += 1
                    comps = []
                    while i < len(lines) and len(comps) < 3 * natmin:
                        t = lines[i].split()
                        if len(t) >= 2:
                            try:
                                comps.append(float(t[0]) + 1j * float(t[1]))
                            except ValueError:
                                break
                        else:
                            break
                        i += 1
                    if len(comps) != 3 * natmin:
                        raise ValueError(
                            f"Mode {im+1} of k {ik+1}: expected "
                            f"{3*natmin} components, got {len(comps)}.")
                    evec[ik, im, :] = comps
                    im += 1
                else:
                    i += 1
            ik += 1
        else:
            i += 1

    return {"lattice": lattice, "masses": masses, "nk": nk, "nbands": nbands,
            "natmin": natmin, "kpoints": kpoints, "omega2": omega2,
            "evec": evec}


# --------------------------------------------------------------------------- #
# POSCAR parser (self-contained).
# --------------------------------------------------------------------------- #
def parse_poscar(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    scale = float(lines[1].split()[0])
    lattice = np.array([[float(x) for x in lines[i].split()[:3]]
                        for i in range(2, 5)]) * scale
    idx = 5
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    elements = []
    try:
        counts = [int(x) for x in lines[idx].split()]
    except ValueError:
        elements = lines[idx].split()
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        counts = [int(x) for x in lines[idx].split()]
    idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if lines[idx].strip().lower().startswith("s"):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    coord_type = lines[idx].strip()
    idx += 1
    labels = []
    for el, c in zip(elements, counts):
        labels += [el] * c
    pos = []
    for i in range(sum(counts)):
        parts = lines[idx + i].split()
        pos.append([float(parts[0]), float(parts[1]), float(parts[2])])
    return lattice, labels, np.array(pos), coord_type


# --------------------------------------------------------------------------- #
# AXSF writer.
# --------------------------------------------------------------------------- #
def write_axsf(path, super_lattice, frames):
    """Write an animated XSF (.axsf) file.

    super_lattice : (3,3) row vectors of the super-cell, in Angstrom.
    frames        : list of lists of (element, cart_position) per frame.
    """
    nframes = len(frames)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"ANIMSTEPS {nframes}\n")
        fh.write("CRYSTAL\n")
        fh.write("PRIMVEC\n")
        for v in super_lattice:
            fh.write(f"  {v[0]:18.12f}  {v[1]:18.12f}  {v[2]:18.12f}\n")
        for i, frame in enumerate(frames, 1):
            fh.write(f"PRIMCOORD {i:6d}\n")
            fh.write(f"  {len(frame):6d}  1\n")
            for el, p in frame:
                fh.write(f"  {el:<3} {p[0]:18.12f} {p[1]:18.12f} {p[2]:18.12f}\n")


def build_animation(lattice, frac_pos, labels, masses, kpoint, evec_mode,
                    dim, amp, nframes):
    """Build the list of frames and the super-cell lattice for one mode.

    Parameters
    ----------
    lattice   : (3,3) primitive lattice (row vectors), Angstrom.
    frac_pos  : (nat,3) fractional coordinates of atoms in the primitive cell.
    labels    : list[str] element symbols, length nat.
    masses    : list[float] per-atom masses, length nat.
    kpoint    : (3,) fractional k-point.
    evec_mode : (3*nat,) complex eigenvector for the mode.
    dim       : (3,) super-cell repeat along a/b/c.
    amp       : float, peak displacement in Angstrom.
    nframes   : int, number of animation frames per period.
    """
    dim = np.array(dim, dtype=int)
    nat = len(labels)
    mass_min = min(masses)

    # Magnitude and phase of the (mass-weighted) eigenvector.
    evec_mag = np.abs(evec_mode).reshape(nat, 3)
    evec_theta = np.angle(evec_mode).reshape(nat, 3)
    # Displacement amplitude in mass-weighted units, then normalised so the
    # largest atomic displacement equals ``amp`` (Angstrom).
    disp_mag = np.sqrt(mass_min / np.array(masses))[:, None] * evec_mag
    per_atom = np.sqrt(np.sum(disp_mag**2, axis=1))
    max_disp = per_atom.max()
    if max_disp < 1e-12:
        disp_mag[:] = 0.0
    else:
        disp_mag *= amp / max_disp

    # Build the super-cell atom list and the inter-cell phase.
    nx, ny, nz = dim
    super_lattice = lattice * dim[None, :]  # each vector scaled by its dim
    cells = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                phase = 2.0 * np.pi * (kpoint[0] * ix + kpoint[1] * iy
                                       + kpoint[2] * iz)
                cells.append((np.array([ix, iy, iz]), phase))

    frames = []
    for istep in range(nframes):
        phase_time = 2.0 * np.pi * istep / nframes
        frame = []
        for (R, phase_cell) in cells:
            for a in range(nat):
                frac = (frac_pos[a] + R) / dim
                cart = frac @ super_lattice
                disp = disp_mag[a] * np.sin(phase_cell + evec_theta[a]
                                            + phase_time)
                frame.append((labels[a], cart + disp))
        frames.append(frame)
    return super_lattice, frames


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate VESTA .axsf vibration animations from an .evec file.")
    parser.add_argument("poscar", help="Structure file (POSCAR / CONTCAR)")
    parser.add_argument("evec", help="ALAMODE eigenvector file (.evec/.band.evec/.mesh.evec)")
    parser.add_argument("--kpoint", "-k", type=int, default=1,
                        help="k-point index to visualise (1-based, default 1)")
    parser.add_argument("--modes", default="all",
                        help="Comma-separated mode indices (1-based) or 'all' (default)")
    parser.add_argument("--dim", default=[1, 1, 1], nargs=3, type=int,
                        help="Super-cell repeat nx ny nz (default 1 1 1 = Gamma)")
    parser.add_argument("--amp", type=float, default=0.5,
                        help="Peak displacement amplitude in Angstrom (default 0.5)")
    parser.add_argument("--frames", type=int, default=8,
                        help="Animation frames per period (default 8)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output prefix (default: <evec stem>)")
    args = parser.parse_args(argv if argv is not None else None)

    if not os.path.isfile(args.poscar):
        print(f"Error: POSCAR '{args.poscar}' not found."); sys.exit(1)
    if not os.path.isfile(args.evec):
        print(f"Error: evec '{args.evec}' not found."); sys.exit(1)

    data = parse_evec(args.evec)
    lattice_evec = data["lattice"]
    lat_pos, labels, frac_pos, coord_type = parse_poscar(args.poscar)
    # Prefer the POSCAR lattice (it carries the right scale / units in Angstrom).
    lattice = lat_pos
    nat = len(labels)
    if nat != data["natmin"]:
        print(f"Error: POSCAR has {nat} atoms but the .evec has "
              f"{data['natmin']} atoms.")
        sys.exit(1)

    # Per-atom masses: map the kind masses (from .evec) onto atoms using the
    # POSCAR element order. The two should list kinds in the same order.
    masses_per_kind = data["masses"]
    if len(masses_per_kind) < len(set(labels)):
        print(f"Warning: {len(masses_per_kind)} kind masses in .evec vs "
              f"{len(set(labels))} distinct elements in POSCAR; "
              "mass weighting may be wrong.")
    # Build per-atom masses by matching POSCAR element order to kind order.
    seen = []
    for el in labels:
        if el not in seen:
            seen.append(el)
    if len(seen) == len(masses_per_kind):
        el_to_mass = dict(zip(seen, masses_per_kind))
        masses = [el_to_mass[el] for el in labels]
    else:
        # Fallback: uniform masses (disables mass weighting).
        print("Warning: could not match elements to kind masses; "
              "using unit masses.")
        masses = [1.0] * nat

    ik = args.kpoint - 1
    if not (0 <= ik < data["nk"]):
        print(f"Error: k-point index {args.kpoint} out of range (1..{data['nk']}).")
        sys.exit(1)
    kpoint = data["kpoints"][ik]

    if args.modes.lower() == "all":
        modes = list(range(1, data["nbands"] + 1))
    else:
        modes = [int(m) for m in args.modes.split(",")]

    # Fractional coordinates of atoms.
    if coord_type.lower().startswith("d"):
        frac = frac_pos
    else:
        frac = frac_pos @ np.linalg.inv(lattice).T

    # Commensurability check for non-Gamma k.
    dim = np.array(args.dim)
    if np.any(dim > 1):
        residual = np.mod(kpoint * dim, 1.0)
        if np.linalg.norm(residual) > 1e-4:
            print(f"Warning: super-cell {tuple(dim)} is not commensurate with "
                  f"k={kpoint} (residual {residual}); the animation will be "
                  f"approximate.")

    out_base = args.output or os.path.splitext(os.path.basename(args.evec))[0]
    print("=" * 60)
    print(f"evec file : {args.evec}")
    print(f"structure : {args.poscar}  ({nat} atoms)")
    print(f"k-point   : #{args.kpoint}  k = {kpoint}")
    print(f"super-cell: {tuple(int(x) for x in dim)}   ({int(np.prod(dim))} cells, "
          f"{int(np.prod(dim)) * nat} atoms/frame)")
    print(f"amplitude : {args.amp} Angstrom   frames: {args.frames}")
    print(f"modes     : {modes}")
    print("-" * 60)

    for m in modes:
        im = m - 1
        if not (0 <= im < data["nbands"]):
            print(f"  skip mode {m}: out of range"); continue
        w2 = data["omega2"][ik, im]
        freq_cm = (np.sqrt(max(w2, 0.0)) * 521.4708 if w2 >= 0
                   else -np.sqrt(-w2) * 521.4708)
        tag = "imag" if w2 < 0 else "  "
        evec_mode = data["evec"][ik, im, :]
        super_lat, frames = build_animation(
            lattice, frac, labels, masses, kpoint, evec_mode,
            args.dim, args.amp, args.frames)
        out = f"{out_base}_k{args.kpoint}_mode{m}.axsf"
        write_axsf(out, super_lat, frames)
        print(f"  wrote {out}   [{tag} {freq_cm:8.2f} cm^-1]")
    print("=" * 60)


if __name__ == "__main__":
    main()
