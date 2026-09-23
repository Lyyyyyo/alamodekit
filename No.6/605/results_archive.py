#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
results_archive.py
==================

Helper: collect and archive the output files of a calculation.

After a phonon run you typically end up with a pile of result files
(``.bands``, ``.dos``, ``.result``, ``.kl``, ``.fcs``, ``.xml``, ...).
This tool gathers the ones you care about into a single timestamped
``.tar.gz`` archive and writes a small ``README`` describing the contents,
so a calculation folder can be stored or shared compactly.

It only walks the filesystem and reads file metadata — no solver knowledge
is involved. The list of extensions to collect is configurable and defaults
to the common text-output extensions; adjust with ``--exts``.

Usage
-----
    python results_archive.py --prefix harfit --outdir archive
    python results_archive.py --exts .bands,.dos,.result --note "T=300K, RTA"
"""
from __future__ import annotations

import os
import sys
import tarfile
import argparse
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402

# Default extensions of common text result files. This is just a list of
# file-name suffixes; it contains no program-specific logic or source.
DEFAULT_EXTS = [
    ".bands", ".dos", ".result", ".kl", ".kl_spec", ".kl_coherent",
    ".fcs", ".xml", ".cvscore", ".pattern", ".phvel", ".gruneisen",
    ".scph_bands", ".scph_dos", ".scph_ucorr", ".qha_ucorr",
]


def collect_files(directory: str, prefix: str, exts: list) -> list:
    """Return the matching files (basename) in ``directory``."""
    matched = []
    for name in sorted(os.listdir(directory)):
        full = os.path.join(directory, name)
        if not os.path.isfile(full):
            continue
        if prefix and not name.startswith(prefix):
            continue
        if not any(name.endswith(e) for e in exts):
            continue
        matched.append(name)
    return matched


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Archive a calculation's result files into a tarball.")
    parser.add_argument("--prefix", "-p", default="",
                        help="Only collect files starting with this prefix")
    parser.add_argument("--exts", default="",
                        help="Comma-separated extensions (default: common outputs)")
    parser.add_argument("--outdir", "-o", default="archive",
                        help="Output directory for the tarball (default: archive)")
    parser.add_argument("--note", default="",
                        help="A free-text note recorded in the archive README")
    parser.add_argument("--dir", default=".",
                        help="Directory to scan (default: current)")
    args = parser.parse_args(argv if argv is not None else None)

    src = args.dir
    if not os.path.isdir(src):
        print(f"Error: directory '{src}' not found.")
        sys.exit(1)
    exts = [e.strip() if e.strip().startswith(".") else "." + e.strip()
            for e in args.exts.split(",") if e.strip()] or DEFAULT_EXTS

    files = collect_files(src, args.prefix, exts)
    if not files:
        print("No matching result files found.")
        print(f"Scanned: {os.path.abspath(src)}")
        print(f"Prefix : '{args.prefix}'")
        print(f"Exts   : {', '.join(exts)}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    label = (args.prefix + "_" if args.prefix else "") + stamp
    tar_name = f"results_{label}.tar.gz"
    tar_path = os.path.join(args.outdir, tar_name)
    total = 0
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in files:
            full = os.path.join(src, name)
            tar.add(full, arcname=name)
            total += os.path.getsize(full)

    # Write a README describing the archive.
    readme_path = os.path.join(args.outdir, f"README_{label}.md")
    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Results archive — {label}\n\n")
        fh.write(f"- created : {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"- source dir : {os.path.abspath(src)}\n")
        fh.write(f"- prefix : '{args.prefix}'\n")
        fh.write(f"- extensions : {', '.join(exts)}\n")
        fh.write(f"- file count : {len(files)}\n")
        fh.write(f"- total size : {human_size(total)}\n")
        if args.note:
            fh.write(f"- note : {args.note}\n")
        fh.write("\n## Contents\n\n")
        fh.write("| file | size |\n|---|---|\n")
        for name in files:
            sz = os.path.getsize(os.path.join(src, name))
            fh.write(f"| {name} | {human_size(sz)} |\n")

    print("=" * 60)
    print(f"Archived {len(files)} file(s) ({human_size(total)})")
    print(f"  tarball : {tar_path}")
    print(f"  readme  : {readme_path}")
    print("-" * 60)
    for name in files:
        sz = os.path.getsize(os.path.join(src, name))
        print(f"  {human_size(sz):>10}  {name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
