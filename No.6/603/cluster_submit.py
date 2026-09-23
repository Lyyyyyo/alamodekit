#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster_submit.py
=================

Linux-only helper: generate a cluster job-submission script for an ALAMODE
solver (``alm`` / ``anphon``) or any generic executable.

Running ab-initio force calculations and ALAMODE fittings on an HPC cluster
requires a scheduler script (SLURM or PBS/Torque). Writing these by hand is
tedious and error-prone. This tool fills in a clean, well-commented template
from a few command-line arguments and writes it to disk.

The executable path is resolved, when possible, from ``settings.yaml``
(``alamode.bin_dir`` + ``alamode.binaries``), so you do not have to hard-code
it; you can also pass ``--exe /full/path/to/alm`` to override.

This tool only writes a text script — it does **not** submit the job itself,
so you can review/edit the script before running ``sbatch`` / ``qsub``. The
generated script contains no ALAMODE source; it is a generic scheduler wrapper.

Usage
-----
    python cluster_submit.py --scheduler slurm --exe alm --input alm_har.in \\
        --jobname harfit --partition short --nodes 1 --ntasks 16 --time 02:00:00
    python cluster_submit.py --scheduler pbs --exe anphon --input rta.in -J rta300
"""
from __future__ import annotations

import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402
from alamodekit_config import get_config_value, get_alamode_bin  # noqa: E402


def _resolve_exe(exe_arg: str) -> str:
    """Resolve the executable: an explicit path wins, else settings.yaml."""
    if exe_arg:
        # Could be a logical name (alm/anphon) or a real path.
        if os.sep in exe_arg or os.path.isfile(exe_arg):
            return os.path.abspath(os.path.expanduser(exe_arg))
        try:
            resolved = get_alamode_bin(exe_arg)
            if os.path.isfile(resolved):
                return resolved
        except Exception:
            pass
        return exe_arg  # leave as-is (rely on PATH / module load)
    return ""


def build_slurm(exe: str, inp: str, jobname: str, partition: str,
                nodes: int, ntasks: int, time: str, mpi: bool,
                extra_modules: list) -> str:
    """Render a SLURM batch script as a string."""
    lines = ["#!/bin/bash",
             f"#SBATCH --job-name={jobname}",
             f"#SBATCH --partition={partition}" if partition else "#SBATCH --partition=normal",
             f"#SBATCH --nodes={nodes}",
             f"#SBATCH --ntasks={ntasks}",
             f"#SBATCH --time={time}",
             f"#SBATCH --output={jobname}.%j.out",
             f"#SBATCH --error={jobname}.%j.err",
             "",
             "# ---- Environment / modules (edit for your cluster) ----",
             "# module load intel/2021",
             "# module load impi/2021",
             "# module load mkl/2021",
             ]
    for m in extra_modules:
        lines.append(f"module load {m}")
    lines += ["",
              f"cd $SLURM_SUBMIT_DIR",
              "",
              "echo \"Running on $(hostname) at $(date)\"",
              f"echo \"Job {jobname}, executable: {exe}\"",
              ""]
    if mpi:
        lines.append(f"mpirun -np $SLURM_NTASKS {exe} < {inp} > {jobname}.log 2>&1")
    else:
        lines.append(f"{exe} < {inp} > {jobname}.log 2>&1")
    lines += ["",
              "echo \"Finished at $(date)\""]
    return "\n".join(lines) + "\n"


def build_pbs(exe: str, inp: str, jobname: str, queue: str,
              nodes: int, ntasks: int, time: str, mpi: bool,
              extra_modules: list) -> str:
    """Render a PBS/Torque batch script as a string."""
    # PBS walltime uses HH:MM:SS too; reuse the same format.
    ppn = max(1, ntasks // max(1, nodes))
    lines = ["#!/bin/bash",
             f"#PBS -N {jobname}",
             f"#PBS -q {queue}" if queue else "#PBS -q default",
             f"#PBS -l nodes={nodes}:ppn={ppn}",
             f"#PBS -l walltime={time}",
             f"#PBS -o {jobname}.out",
             f"#PBS -e {jobname}.err",
             "",
             "# ---- Environment / modules (edit for your cluster) ----",
             "# module load intel",
             "# module load impi",
             ]
    for m in extra_modules:
        lines.append(f"module load {m}")
    lines += ["",
              f"cd $PBS_O_WORKDIR",
              "",
              "echo \"Running on $(hostname) at $(date)\"",
              f"echo \"Job {jobname}, executable: {exe}\"",
              ""]
    nproc = nodes * ppn
    if mpi:
        lines.append(f"mpirun -np {nproc} {exe} < {inp} > {jobname}.log 2>&1")
    else:
        lines.append(f"{exe} < {inp} > {jobname}.log 2>&1")
    lines += ["",
              "echo \"Finished at $(date)\""]
    return "\n".join(lines) + "\n"


def build_local(exe: str, inp: str, jobname: str, mpi: bool,
                ntasks: int) -> str:
    """Render a plain bash script (no scheduler) for a workstation."""
    lines = ["#!/bin/bash",
             f"# Local run script for {jobname}",
             "",
             f"cd \"$(dirname \"$0\")\"",
             "",
             "echo \"Running on $(hostname) at $(date)\"",
             f"echo \"Job {jobname}, executable: {exe}\"",
             ""]
    if mpi:
        lines.append(f"mpirun -np {ntasks} {exe} < {inp} > {jobname}.log 2>&1")
    else:
        lines.append(f"{exe} < {inp} > {jobname}.log 2>&1")
    lines += ["",
              "echo \"Finished at $(date)\""]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a cluster job-submission script.")
    parser.add_argument("--scheduler", default="slurm",
                        choices=["slurm", "pbs", "local"],
                        help="Job scheduler (default: slurm)")
    parser.add_argument("--exe", required=True,
                        help="Executable (alm/anphon), a logical name or path")
    parser.add_argument("--input", "-i", required=True,
                        help="Input file for the executable")
    parser.add_argument("--jobname", "-J", default="alamode",
                        help="Job name (default: alamode)")
    parser.add_argument("--partition", "-p", default="",
                        help="SLURM partition / PBS queue")
    parser.add_argument("--nodes", type=int, default=1,
                        help="Number of nodes (default: 1)")
    parser.add_argument("--ntasks", type=int, default=8,
                        help="Total MPI tasks (default: 8)")
    parser.add_argument("--time", "-t", default="02:00:00",
                        help="Wall time HH:MM:SS (default: 02:00:00)")
    parser.add_argument("--mpi", action="store_true", default=True,
                        help="Use mpirun (default: yes)")
    parser.add_argument("--no-mpi", dest="mpi", action="store_false",
                        help="Run in serial (no mpirun)")
    parser.add_argument("--module", action="append", default=[],
                        help="Extra 'module load' line (repeatable)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output script name (default: submit_<jobname>.sh)")
    args = parser.parse_args(argv if argv is not None else None)

    if not os.path.isfile(args.input):
        print(f"Warning: input file '{args.input}' not found "
              f"(the script will still be generated).")

    exe = _resolve_exe(args.exe)
    out = args.output or f"submit_{args.jobname}.sh"

    if args.scheduler == "slurm":
        script = build_slurm(exe, args.input, args.jobname, args.partition,
                             args.nodes, args.ntasks, args.time, args.mpi,
                             args.module)
    elif args.scheduler == "pbs":
        script = build_pbs(exe, args.input, args.jobname, args.partition,
                           args.nodes, args.ntasks, args.time, args.mpi,
                           args.module)
    else:
        script = build_local(exe, args.input, args.jobname, args.mpi,
                             args.ntasks)

    with open(out, "w", encoding="utf-8") as fh:
        fh.write(script)
    os.chmod(out, 0o755)
    print("=" * 60)
    print(f"Wrote submission script -> {out}")
    print(f"  scheduler : {args.scheduler}")
    print(f"  executable: {exe}")
    print(f"  input     : {args.input}")
    print(f"  jobname   : {args.jobname}")
    print(f"  nodes/ntasks: {args.nodes} / {args.ntasks}  "
          f"({'MPI' if args.mpi else 'serial'})")
    print(f"  time      : {args.time}")
    print("Next steps:")
    if args.scheduler == "slurm":
        print(f"  sbatch {out}")
    elif args.scheduler == "pbs":
        print(f"  qsub {out}")
    else:
        print(f"  bash {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
