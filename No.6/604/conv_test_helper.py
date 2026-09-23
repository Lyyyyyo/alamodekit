#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conv_test_helper.py
===================

Helper: run a parameter sweep over an input-file template.

Convergence tests (cutoff radius, q/k mesh density, smearing width, ...)
are a routine but repetitive part of a phonon workflow: you take one input
file, change a single number, re-run, and compare the results. This tool
automates the file generation step from a *template*.

The template is a copy of a normal input file in which the values to sweep
are replaced by placeholders, e.g.::

    &general
        PREFIX = Si
        ...
    /

    &optimize
        ...
        NMAX = @CUTOFF@     <- placeholder
        ...
    /

You then ask the helper to sweep one or more placeholders across lists of
values, and it generates one input file per combination (Cartesian product),
plus a small ``run_all.sh`` that runs them in sequence.

This tool only does text substitution — it has no knowledge of what the
placeholders mean, so it works for any text-based input file and contains no
solver-specific code.

Usage
-----
    python conv_test_helper.py --template phband.in \\
        --param "@CUTOFF@:5.0,7.0,9.0" \\
        --param "@KMESH@:8,16" --exe anphon
"""
from __future__ import annotations

import os
import sys
import argparse
import itertools

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


def _parse_param(spec: str):
    """Parse "PLACEHOLDER:v1,v2,v3" -> (placeholder, [v1, v2, v3])."""
    if ":" not in spec:
        raise ValueError(f"Bad --param '{spec}' (expected PLACEHOLDER:v1,v2,...).")
    ph, vals = spec.split(":", 1)
    ph = ph.strip()
    vals = [v.strip() for v in vals.split(",") if v.strip() != ""]
    if not ph or not vals:
        raise ValueError(f"Bad --param '{spec}' (empty placeholder or values).")
    return ph, vals


def _safe_tag(val: str) -> str:
    """Make a value safe to embed in a filename (strip path separators etc.)."""
    return "".join(ch if ch.isalnum() or ch in ".-_" else "_"
                   for ch in val).strip("._")


def generate(template_path: str, params, exe: str, prefix: str):
    """Generate one input file per parameter combination + a run_all.sh.

    ``params`` is a list of (placeholder, [values]) tuples.
    Returns the list of generated input file paths.
    """
    with open(template_path, "r", encoding="utf-8") as fh:
        template = fh.read()
    base = os.path.splitext(os.path.basename(template_path))[0]

    placeholders = [p for p, _ in params]
    value_lists = [v for _, v in params]
    generated = []

    for combo in itertools.product(*value_lists):
        text = template
        tag_parts = []
        for ph, val in zip(placeholders, combo):
            text = text.replace(ph, val)
            tag_parts.append(f"{ph.strip('@')}_{_safe_tag(val)}")
        tag = "_".join(tag_parts)
        out_name = f"{base}__{tag}.in" if tag else f"{base}_sweep.in"
        with open(out_name, "w", encoding="utf-8") as fh:
            fh.write(text)
        generated.append(out_name)
        print(f"  generated {out_name}  ({dict(zip(placeholders, combo))})")

    # write the runner script
    run_lines = ["#!/bin/bash",
                 "# Auto-generated batch runner for a convergence sweep.",
                 "# Review each command before executing.",
                 "set -e",
                 ""]
    for f in generated:
        run_lines.append(f"{exe} < {f} > {os.path.splitext(f)[0]}.log 2>&1")
    run_path = "run_all.sh"
    with open(run_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(run_lines) + "\n")
    os.chmod(run_path, 0o755)
    print(f"\n  wrote runner -> {run_path}")
    return generated


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a parameter sweep from an input-file template.")
    parser.add_argument("--template", required=True,
                        help="Template input file with @PLACEHOLDER@ tokens")
    parser.add_argument("--param", action="append", required=True,
                        help='Placeholder spec "PH:v1,v2,..."; repeatable')
    parser.add_argument("--exe", default="anphon",
                        help="Executable used in run_all.sh (default: anphon)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.template):
        print(f"Error: template '{args.template}' not found.")
        sys.exit(1)
    params = [_parse_param(s) for s in args.param]
    print("=" * 60)
    print(f"Template: {args.template}")
    print("Sweep parameters:")
    for ph, vals in params:
        print(f"  {ph} -> {vals}")
    print(f"Total combinations: "
          f"{len(list(itertools.product(*[v for _, v in params])))}")
    print("-" * 60)
    generate(args.template, params, args.exe, "")
    print("=" * 60)


if __name__ == "__main__":
    main()
