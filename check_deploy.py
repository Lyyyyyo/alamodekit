#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_deploy.py
===============

Post-deployment sanity check for ALAMODEkit.

Run this on a machine where the toolkit has just been deployed (either straight
from the source tree or after ``pip install``) to find out, in one command,
whether it is actually usable::

    python check_deploy.py                      # inspect the tree next to this file
    python check_deploy.py --root /opt/ALAMODEkit
    python check_deploy.py --project ~/work/Si  # also verify a real work directory
    python check_deploy.py --save report.txt     # keep a copy of the transcript

What it verifies
----------------
1. Python version against the documented minimum (3.8).
2. The toolkit root and the ``No.X`` script tree it contains.
3. That every subprogram registered in ``alamodekit.py`` resolves to a real
   file -- the check that catches "menu item exists but the script does not".
4. Which ``settings.yaml`` will actually be used (env var / cwd / bundled).
5. ``alamode.bin_dir``: placeholder detection plus per-binary existence and
   execute permission.
6. Required third-party modules (numpy, matplotlib, pandas, PyYAML) and the
   optional ones (spglib, ase).
7. A headless matplotlib smoke test, which catches a half-broken matplotlib
   install that only fails later at plot time.
8. MPI availability, needed by No.5/502 and the No.6/603 scheduler wrappers.
9. That an ordinary working directory is writable for the generated files.

The exit status equals the number of FAILed checks, so ``0`` means healthy.

Only the standard library is imported at module level, so this script runs even
on a host where none of the dependencies are installed yet.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

PY_MIN = (3, 8)
REQUIRED = [("numpy", "numpy>=1.20"), ("matplotlib", "matplotlib>=3.3"),
            ("pandas", "pandas>=1.2"), ("yaml", "PyYAML>=5.4")]
OPTIONAL = [("spglib", "No.7/704 ase_bridge --spacegroup"),
            ("ase", "No.7/704 ase_bridge primitive/conventional/...")]

FAILS = []
WARNS = []
REPORT = []


def out(line=""):
    print(line)
    REPORT.append(str(line))


def ok(name, detail=""):
    out("  [ OK ]  %s%s" % (name, ("   %s" % detail) if detail else ""))


def warn(name, detail=""):
    out("  [WARN]  %s%s" % (name, ("   %s" % detail) if detail else ""))
    WARNS.append(name)


def fail(name, detail=""):
    out("  [FAIL]  %s%s" % (name, ("   %s" % detail) if detail else ""))
    FAILS.append(name)


def note(name, detail=""):
    out("  [ -- ]  %s%s" % (name, ("   %s" % detail) if detail else ""))


def heading(text):
    out("")
    out("-" * 72)
    out(text)
    out("-" * 72)


def has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def version_of(mod):
    try:
        m = __import__(mod)
        return getattr(m, "__version__", "")
    except Exception:
        return ""


def main():
    here = os.path.dirname(os.path.abspath(__file__))

    # ----------------------------------------------------------------------
    # 1. Python
    # ----------------------------------------------------------------------
    heading("1. Python interpreter")
    out("  executable : %s" % sys.executable)
    out("  version    : %s" % sys.version.split()[0])
    if sys.version_info >= PY_MIN:
        ok("Python >= %d.%d" % PY_MIN)
    else:
        fail("Python >= %d.%d" % PY_MIN, "running %d.%d" % sys.version_info[:2])
    in_venv = (hasattr(sys, "real_prefix")
               or sys.prefix != getattr(sys, "base_prefix", sys.prefix))
    if in_venv:
        note("interpreter type", "virtual env / venv / conda")
    else:
        warn("using system interpreter",
             "install into a virtual env to avoid polluting system Python")

    # ----------------------------------------------------------------------
    # 2. Toolkit root and script tree
    # ----------------------------------------------------------------------
    heading("2. Toolkit root and script tree")
    ROOT = args.root or here
    if not os.path.isfile(os.path.join(ROOT, "alamodekit.py")):
        try:
            import alamodekit_config as _c
            alt = os.path.dirname(os.path.abspath(_c.__file__))
            if os.path.isfile(os.path.join(alt, "alamodekit.py")):
                note("no alamodekit.py here, using installed copy", alt)
                ROOT = alt
        except Exception:
            pass
    out("  toolkit root : %s" % ROOT)

    for f in ("alamodekit.py", "alamodekit_config.py", "alamodekit_io.py",
              "alamode_input.py", "plot_style.py"):
        if os.path.isfile(os.path.join(ROOT, f)):
            ok("module present: %s" % f)
        else:
            fail("module missing: %s" % f, os.path.join(ROOT, f))

    if os.path.isdir(ROOT):
        sections = [d for d in sorted(os.listdir(ROOT))
                    if d.startswith("No.") and os.path.isdir(os.path.join(ROOT, d))]
        scripts = []
        for sect in sections:
            for sub in sorted(os.listdir(os.path.join(ROOT, sect))):
                sp = os.path.join(ROOT, sect, sub)
                if os.path.isdir(sp):
                    scripts += [os.path.join(sect, sub, f) for f in os.listdir(sp)
                                if f.endswith(".py")]
        if len(sections) == 7:
            ok("No.X sections complete", "7 found: %s" % ", ".join(sections))
        else:
            fail("No.X section count wrong",
                 "found %d: %s" % (len(sections), sections))
        if scripts:
            ok("script files", "%d .py files" % len(scripts))
        else:
            fail("no scripts under No.X", "script tree missing or misplaced")
    else:
        fail("toolkit root is not a directory", ROOT)

    # ----------------------------------------------------------------------
    # 3. Launcher registration vs. files on disk
    # ----------------------------------------------------------------------
    heading("3. Launcher registry vs. files on disk")
    sys.path.insert(0, ROOT)
    try:
        import alamodekit as ak
    except Exception as exc:
        fail("cannot import alamodekit", repr(exc))
        ak = None

    if ak is not None:
        base_path_cfg = ""
        try:
            from alamodekit_config import get_config_value
            base_path_cfg = get_config_value("alamodekit", "base_path",
                                             default="") or ""
        except Exception:
            pass
        BASE = base_path_cfg or os.path.dirname(os.path.abspath(ak.__file__))
        out("  launcher script tree root : %s" % BASE)
        if base_path_cfg:
            note("alamodekit.base_path set in settings.yaml", base_path_cfg)
        else:
            note("alamodekit.base_path is empty -> falling back to launcher directory")
        if os.path.isdir(BASE):
            ok("script tree root exists")
        else:
            fail("script tree root does not exist", BASE)

        reg = getattr(ak, "SCRIPT_PATHS", None)
        if reg is None:
            warn("launcher has no SCRIPT_PATHS attribute, skipping registry check")
        else:
            missing = sorted(k for k, v in reg.items()
                             if not os.path.isfile(os.path.join(BASE, v["path"])))
            if missing:
                fail("registered but script file not found",
                     "%d missing: %s" % (len(missing), missing[:6]))
            else:
                ok("all %d registered menu functions resolve to files" % len(reg))

    # ----------------------------------------------------------------------
    # 4. settings.yaml
    # ----------------------------------------------------------------------
    heading("4. settings.yaml resolution")
    try:
        from alamodekit_config import load_config, get_settings_path
        load_config()
        cfg_path = get_settings_path()
        ok("config loaded", cfg_path)
        if os.environ.get("ALAMODEKIT_CONFIG"):
            note("source", "env var ALAMODEKIT_CONFIG")
        elif os.path.abspath(cfg_path).startswith(os.path.abspath(os.getcwd())):
            note("source", "settings.yaml in current directory")
        else:
            note("source", "bundled copy")
        cfg = load_config()
        keys = sorted(k for k in cfg if not k.startswith("_"))
        if "alamode" not in cfg:
            # A malformed file (bad indentation, a stray character) parses into
            # something that has no `alamode` key at all -- and every downstream
            # lookup then quietly falls back to its default.
            warn("no alamode section in settings.yaml",
                 "top-level keys are %s; check indentation and format" % keys)
        if not cfg.get("plotting"):
            warn("no plotting section in settings.yaml",
                 "plotting scripts will use built-in defaults")
    except Exception as exc:
        fail("config load failed", repr(exc))

    # ----------------------------------------------------------------------
    # 5. ALAMODE binaries
    # ----------------------------------------------------------------------
    heading("5. ALAMODE binaries (alamode.bin_dir)")
    get_alamode_bin = None
    bin_dir = ""
    bin_usable = False          # False => skip the per-binary checks
    try:
        from alamodekit_config import get_alamode_bin, get_alamode_config
        bin_dir = (get_alamode_config() or {}).get("bin_dir", "") or ""
    except Exception as exc:
        fail("cannot read alamode config", repr(exc))

    if bin_dir:
        out("  bin_dir : %s" % bin_dir)
        if "username" in bin_dir.replace("\\", "/"):
            fail("bin_dir is still the factory placeholder",
                 "set it to your ALAMODE build directory, e.g. /home/you/alamode/build")
        else:
            expanded = os.path.expanduser(bin_dir)
            if os.path.isdir(expanded):
                ok("bin_dir exists")
                bin_usable = True
            else:
                fail("bin_dir does not exist", expanded)
    else:
        warn("bin_dir is empty", "will rely on system PATH for alm / anphon / ...")
        bin_usable = True       # an empty bin_dir legitimately means "use PATH"

    for name in ("alm", "anphon", "analyze_phonons", "dfc2"):
        if not bin_usable:
            note("%s  (skipped, fix bin_dir first)" % name)
            continue
        if get_alamode_bin is None:
            fail("%s  (cannot resolve path)" % name)
            continue
        try:
            p = get_alamode_bin(name)
        except Exception as exc:
            fail("failed to resolve %s path" % name, repr(exc))
            continue
        # A POSIX path is not "absolute" to os.path on Windows, so treat a
        # leading slash as absolute as well.
        if os.path.isabs(p) or p.replace("\\", "/").startswith("/"):
            if os.path.isfile(p):
                if os.name == "nt" or os.access(p, os.X_OK):
                    ok("%s is executable" % name, p)
                else:
                    fail("%s has no execute permission" % name, "chmod +x %s" % p)
            else:
                fail("%s not found" % name, p)
        else:
            found = shutil.which(p)
            if found:
                ok("%s on PATH" % name, found)
            else:
                fail("%s neither on PATH nor resolvable via bin_dir" % name, p)

    # ----------------------------------------------------------------------
    # 6. Python dependencies
    # ----------------------------------------------------------------------
    heading("6. Python dependencies")
    for mod, req in REQUIRED:
        if has(mod):
            v = version_of(mod)
            ok("%-11s %s" % (mod, v or "(version unknown)"))
            if mod == "yaml" and not v:
                warn("PyYAML does not expose __version__",
                     "config may use the built-in fallback parser")
        elif mod == "yaml":
            warn("PyYAML not installed",
                 "built-in fallback parser available, but pip install %s is recommended" % req)
        else:
            fail("%s not installed" % mod, "pip install %s" % req)
    for mod, why in OPTIONAL:
        if has(mod):
            ok("%-11s %s" % (mod, version_of(mod) or ""), why)
        else:
            note("%-11s (optional, not installed)" % mod, why)

    # ----------------------------------------------------------------------
    # 7. Headless matplotlib smoke test
    # ----------------------------------------------------------------------
    heading("7. matplotlib headless smoke test")
    if has("matplotlib"):
        try:
            import matplotlib
            matplotlib.use("Agg")           # cluster nodes have no display
            import matplotlib.pyplot as plt
            fig = plt.figure(figsize=(2, 2))
            fig.add_subplot(111).plot([0, 1], [0, 1])
            fig.canvas.draw()
            plt.close(fig)
            ok("Agg backend can render")
        except Exception as exc:
            fail("matplotlib cannot render", repr(exc))
        note("MPLBACKEND", os.environ.get("MPLBACKEND", "(not set)"))
    else:
        warn("skipped", "matplotlib not installed, No.2 plotting unavailable")

    # ----------------------------------------------------------------------
    # 8. MPI
    # ----------------------------------------------------------------------
    heading("8. MPI (No.5/502 parallel, No.6/603 job scripts)")
    mpi = shutil.which("mpirun") or shutil.which("mpiexec")
    if mpi:
        ok("MPI launcher found", mpi)
        try:
            r = subprocess.run([mpi, "--version"], capture_output=True,
                               text=True, timeout=20)
            first = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            if first:
                note("version", first[0][:70])
        except Exception:
            pass
    else:
        warn("mpirun / mpiexec not found", "serial runs are unaffected")

    # ----------------------------------------------------------------------
    # 9. Working directory
    # ----------------------------------------------------------------------
    heading("9. Working directory")
    cwd = os.path.abspath(args.project or os.getcwd())
    out("  working dir : %s" % cwd)
    if os.path.isdir(cwd) and os.access(cwd, os.W_OK):
        ok("writable (alm.in / *.bands etc. will be generated here)")
    else:
        fail("not writable", cwd)

    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------
    out("")
    out("=" * 60)
    out("  Result: %d failed, %d warnings" % (len(FAILS), len(WARNS)))
    for name in FAILS:
        out("    FAIL  %s" % name)
    for name in WARNS:
        out("    WARN  %s" % name)
    out("=" * 60)
    if not FAILS:
        out("  Deployment is essentially usable. Confirm that alamode.bin_dir in")
        out("  config/settings.yaml points to your ALAMODE build directory, then run alamodekit.")

    if args.save:
        with open(args.save, "w", encoding="utf-8") as fh:
            fh.write("\n".join(REPORT))
        print("\n  Report written to: %s" % args.save)

    return len(FAILS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Post-deployment sanity check for ALAMODEkit.")
    parser.add_argument("--root", default=None,
                        help="toolkit root (default: the directory of this file)")
    parser.add_argument("--project", default=None,
                        help="a real working directory to check for writability")
    parser.add_argument("--save", default=None,
                        help="write the transcript to this file")
    args = parser.parse_args()
    sys.exit(main())
