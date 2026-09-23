#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
input_validator.py
==================

Helper: validate the *syntax* of a Fortran-namelist-style input file.

ALM / ANPHON (and many other simulation codes) read input files made of
*namelist blocks* of the form::

    &general
        PREFIX = Si
        MODE    = optimize
        NKD     = 1
        KD      = Si
    /

    &cell
        1.0
        0.0 0.5 0.5
        0.5 0.0 0.5
        0.5 0.5 0.0
    /

This tool performs purely *syntactic* checks — it does not need to know what
any tag means, so it contains no program-specific knowledge and no source
code from any solver:

  * every ``&block`` is closed by a matching ``/`` ;
  * no block is left unclosed, and there is no stray ``/`` ;
  * inside a block, non-comment, non-blank lines that should be
    ``key = value`` assignments actually look like one;
  * duplicate keys within the same block are reported (usually a mistake).

It does NOT check whether the *values* are physically sensible or whether
required tags are present — that would require program-specific knowledge.
Use ``--expected a,b,c`` to get a soft hint about which of the expected
block names are missing.

Usage
-----
    python input_validator.py alm.in
    python input_validator.py phband.in --expected general,cell,kpoint
"""
from __future__ import annotations

import os
import sys
import argparse
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import alamodekit_io  # noqa: E402
alamodekit_io.ensure_package_root()  # noqa: E402


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment (respecting simple quotes)."""
    in_s = in_d = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            return line[:i]
    return line


def parse_blocks(text: str):
    """Tokenise the file into ordered blocks.

    Returns a list of dicts: ``{name, start_line, body_lines, closed}`` where
    ``body_lines`` are the raw (comment-stripped) lines inside the block and
    ``closed`` says whether a ``/`` terminator was found. Text outside any
    block is collected into a synthetic block named ``<top-level>``.
    """
    blocks = []
    current = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        # A line that is just "/" closes the current block.
        if stripped == "/":
            if current is None:
                blocks.append({"name": None, "start_line": lineno,
                               "body_lines": [], "closed": True,
                               "error": "stray '/' with no open block"})
            else:
                current["closed"] = True
                blocks.append(current)
                current = None
            continue
        # Opening a new block: a token starting with '&'.
        if stripped.startswith("&"):
            name = stripped[1:].strip()
            if current is not None:
                # The previous block was never closed — report and start fresh.
                current["closed"] = False
                current["error"] = "block not closed before next '&'"
                blocks.append(current)
            current = {"name": name, "start_line": lineno,
                       "body_lines": [], "closed": False}
            continue
        # Ordinary content line.
        if current is None:
            current = {"name": "<top-level>", "start_line": lineno,
                       "body_lines": [], "closed": True}
        current["body_lines"].append((lineno, stripped))
    if current is not None and not current.get("closed", True):
        blocks.append(current)
    return blocks


def _looks_like_assignment(line: str) -> bool:
    """True if the line parses as ``key = value`` (key is an identifier)."""
    if "=" not in line:
        return False
    key = line.split("=", 1)[0].strip()
    if not key:
        return False
    # Allow letters, digits, underscore in the key (Fortran identifiers).
    return all(ch.isalnum() or ch == "_" for ch in key)


def validate(path: str, expected: list | None = None):
    """Run the checks and return a list of (severity, message) tuples."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    blocks = parse_blocks(text)
    issues = []
    seen_names = []
    for blk in blocks:
        name = blk.get("name") or "<anonymous>"
        seen_names.append(name)
        if name == "<top-level>":
            # Top-level stray content is suspicious for a namelist file.
            if blk["body_lines"]:
                issues.append(("warn",
                               f"line {blk['body_lines'][0][0]}: content outside "
                               f"any &block (top-level lines ignored by most codes)"))
            continue
        if not blk.get("closed", False):
            issues.append(("error",
                           f"&{name} (opened at line {blk['start_line']}) "
                           f"is never closed with '/'"))
            continue
        if "error" in blk:
            issues.append(("error", f"&{name}: {blk['error']}"))
        # Inspect body lines that should be key=value.
        key_counter = Counter()
        for lineno, line in blk["body_lines"]:
            # Lines that are just numbers (e.g. lattice vectors, coordinates)
            # are legitimately NOT assignments — accept them silently.
            tokens = line.split()
            if all(_is_number(t) for t in tokens):
                continue
            if "=" not in line:
                # Not an assignment and not pure numbers -> ambiguous.
                issues.append(("info",
                               f"line {lineno} in &{name}: not a 'key = value' "
                               f"line (may be a data block — usually fine)"))
                continue
            if not _looks_like_assignment(line):
                issues.append(("warn",
                               f"line {lineno} in &{name}: malformed assignment "
                               f"'{line}'"))
                continue
            key = line.split("=", 1)[0].strip()
            key_counter[key] += 1
        for key, cnt in key_counter.items():
            if cnt > 1:
                issues.append(("warn",
                               f"&{name}: key '{key}' assigned {cnt} times "
                               f"(usually a mistake)"))
    # Soft hint about expected block names.
    if expected:
        missing = [b for b in expected if b not in seen_names]
        if missing:
            issues.append(("info",
                           f"expected blocks not found: {', '.join(missing)}"))
    return blocks, issues


def _is_number(tok: str) -> bool:
    try:
        float(tok.replace("D", "E").replace("d", "e"))
        return True
    except ValueError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate the syntax of a namelist-style input file.")
    parser.add_argument("file", help="Input file to validate")
    parser.add_argument("--expected", default="",
                        help="Comma-separated expected block names (e.g. general,cell)")
    args = parser.parse_args(argv if argv is not None else None)
    if not os.path.isfile(args.file):
        print(f"Error: file '{args.file}' not found.")
        sys.exit(1)
    expected = [b.strip() for b in args.expected.split(",") if b.strip()] \
        if args.expected else None
    blocks, issues = validate(args.file, expected)
    print("=" * 60)
    print(f"File: {args.file}")
    print(f"Blocks found: {len(blocks)}")
    for blk in blocks:
        name = blk.get("name") or "<anonymous>"
        status = "closed" if blk.get("closed") else "UNCLOSED"
        nlines = len(blk.get("body_lines", []))
        print(f"  &{name:<16} (line {blk['start_line']:>4})  "
              f"[{status}]  {nlines} content line(s)")
    print("-" * 60)
    if not issues:
        print("No syntax issues found.")
    else:
        for sev, msg in issues:
            tag = {"error": "ERROR", "warn": "WARN ", "info": "info "}[sev]
            print(f"  [{tag}] {msg}")
    n_err = sum(1 for s, _ in issues if s == "error")
    print("-" * 60)
    print(f"Result: {n_err} error(s), "
          f"{sum(1 for s, _ in issues if s == 'warn')} warning(s).")
    print("=" * 60)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
