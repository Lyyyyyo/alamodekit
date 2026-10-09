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
        note("解释器类型", "独立环境 / venv / conda")
    else:
        warn("使用的是系统解释器", "建议装进独立环境，避免污染系统 Python")

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
                note("本目录没有 alamodekit.py，改用已安装副本", alt)
                ROOT = alt
        except Exception:
            pass
    out("  toolkit root : %s" % ROOT)

    for f in ("alamodekit.py", "alamodekit_config.py", "alamodekit_io.py",
              "alamode_input.py", "plot_style.py"):
        if os.path.isfile(os.path.join(ROOT, f)):
            ok("模块存在: %s" % f)
        else:
            fail("模块缺失: %s" % f, os.path.join(ROOT, f))

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
            ok("No.X 章节齐全", "7 个: %s" % ", ".join(sections))
        else:
            fail("No.X 章节数异常", "找到 %d 个: %s" % (len(sections), sections))
        if scripts:
            ok("脚本文件", "%d 个 .py" % len(scripts))
        else:
            fail("No.X 下没有脚本", "脚本树缺失或位置不对")
    else:
        fail("toolkit root 不是目录", ROOT)

    # ----------------------------------------------------------------------
    # 3. Launcher registration vs. files on disk
    # ----------------------------------------------------------------------
    heading("3. Launcher registry vs. files on disk")
    sys.path.insert(0, ROOT)
    try:
        import alamodekit as ak
    except Exception as exc:
        fail("无法导入 alamodekit", repr(exc))
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
        out("  launcher 解析脚本树用 : %s" % BASE)
        if base_path_cfg:
            note("settings.yaml 里 alamodekit.base_path 已设置", base_path_cfg)
        else:
            note("alamodekit.base_path 为空 -> 回退到启动器所在目录")
        if os.path.isdir(BASE):
            ok("脚本树根存在")
        else:
            fail("脚本树根不存在", BASE)

        reg = getattr(ak, "SCRIPT_PATHS", None)
        if reg is None:
            warn("启动器没有 SCRIPT_PATHS 属性，跳过注册表核对")
        else:
            missing = sorted(k for k, v in reg.items()
                             if not os.path.isfile(os.path.join(BASE, v["path"])))
            if missing:
                fail("已注册但找不到脚本文件",
                     "%d 个: %s" % (len(missing), missing[:6]))
            else:
                ok("菜单注册的 %d 个功能全部能定位到文件" % len(reg))

    # ----------------------------------------------------------------------
    # 4. settings.yaml
    # ----------------------------------------------------------------------
    heading("4. settings.yaml resolution")
    try:
        from alamodekit_config import load_config, get_settings_path
        load_config()
        cfg_path = get_settings_path()
        ok("配置加载成功", cfg_path)
        if os.environ.get("ALAMODEKIT_CONFIG"):
            note("来源", "环境变量 ALAMODEKIT_CONFIG")
        elif os.path.abspath(cfg_path).startswith(os.path.abspath(os.getcwd())):
            note("来源", "当前目录下的 settings.yaml")
        else:
            note("来源", "随包副本")
        cfg = load_config()
        keys = sorted(k for k in cfg if not k.startswith("_"))
        if "alamode" not in cfg:
            # A malformed file (bad indentation, a stray character) parses into
            # something that has no `alamode` key at all -- and every downstream
            # lookup then quietly falls back to its default.
            warn("settings.yaml 里没有 alamode 段",
                 "顶层键为 %s；请检查缩进与格式" % keys)
        if not cfg.get("plotting"):
            warn("settings.yaml 里没有 plotting 段", "绘图脚本将使用内置默认值")
    except Exception as exc:
        fail("配置加载失败", repr(exc))

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
        fail("无法读取 alamode 配置", repr(exc))

    if bin_dir:
        out("  bin_dir : %s" % bin_dir)
        if "username" in bin_dir.replace("\\", "/"):
            fail("bin_dir 仍是出厂占位符",
                 "改成你自己的 ALAMODE 编译目录，例如 /home/you/alamode/build")
        else:
            expanded = os.path.expanduser(bin_dir)
            if os.path.isdir(expanded):
                ok("bin_dir 存在")
                bin_usable = True
            else:
                fail("bin_dir 不存在", expanded)
    else:
        warn("bin_dir 为空", "将依赖系统 PATH 查找 alm / anphon / ...")
        bin_usable = True       # an empty bin_dir legitimately means "use PATH"

    for name in ("alm", "anphon", "analyze_phonons", "dfc2"):
        if not bin_usable:
            note("%s  (跳过，先修好 bin_dir)" % name)
            continue
        if get_alamode_bin is None:
            fail("%s  (无法解析路径)" % name)
            continue
        try:
            p = get_alamode_bin(name)
        except Exception as exc:
            fail("解析 %s 路径失败" % name, repr(exc))
            continue
        # A POSIX path is not "absolute" to os.path on Windows, so treat a
        # leading slash as absolute as well.
        if os.path.isabs(p) or p.replace("\\", "/").startswith("/"):
            if os.path.isfile(p):
                if os.name == "nt" or os.access(p, os.X_OK):
                    ok("%s 可执行" % name, p)
                else:
                    fail("%s 没有执行权限" % name, "chmod +x %s" % p)
            else:
                fail("%s 找不到" % name, p)
        else:
            found = shutil.which(p)
            if found:
                ok("%s 在 PATH 上" % name, found)
            else:
                fail("%s 既不在 PATH 上，bin_dir 也无法解析" % name, p)

    # ----------------------------------------------------------------------
    # 6. Python dependencies
    # ----------------------------------------------------------------------
    heading("6. Python dependencies")
    for mod, req in REQUIRED:
        if has(mod):
            v = version_of(mod)
            ok("%-11s %s" % (mod, v or "(版本未知)"))
            if mod == "yaml" and not v:
                warn("PyYAML 未正常暴露 __version__",
                     "配置可能走了内置兜底解析器")
        elif mod == "yaml":
            warn("PyYAML 未安装", "内置兜底解析器可用，但建议 pip install %s" % req)
        else:
            fail("%s 未安装" % mod, "pip install %s" % req)
    for mod, why in OPTIONAL:
        if has(mod):
            ok("%-11s %s" % (mod, version_of(mod) or ""), why)
        else:
            note("%-11s (可选，未安装)" % mod, why)

    # ----------------------------------------------------------------------
    # 7. Headless matplotlib smoke test
    # ----------------------------------------------------------------------
    heading("7. matplotlib headless smoke test")
    if has("matplotlib"):
        try:
            import matplotlib
            matplotlib.use("Agg")           # 集群节点没有显示器
            import matplotlib.pyplot as plt
            fig = plt.figure(figsize=(2, 2))
            fig.add_subplot(111).plot([0, 1], [0, 1])
            fig.canvas.draw()
            plt.close(fig)
            ok("Agg 后端可正常出图")
        except Exception as exc:
            fail("matplotlib 无法出图", repr(exc))
        note("MPLBACKEND", os.environ.get("MPLBACKEND", "(未设置)"))
    else:
        warn("跳过", "matplotlib 未安装，No.2 等绘图功能不可用")

    # ----------------------------------------------------------------------
    # 8. MPI
    # ----------------------------------------------------------------------
    heading("8. MPI (No.5/502 并行, No.6/603 任务脚本)")
    mpi = shutil.which("mpirun") or shutil.which("mpiexec")
    if mpi:
        ok("找到 MPI 启动器", mpi)
        try:
            r = subprocess.run([mpi, "--version"], capture_output=True,
                               text=True, timeout=20)
            first = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            if first:
                note("版本", first[0][:70])
        except Exception:
            pass
    else:
        warn("未找到 mpirun / mpiexec", "串行运行不受影响")

    # ----------------------------------------------------------------------
    # 9. Working directory
    # ----------------------------------------------------------------------
    heading("9. Working directory")
    cwd = os.path.abspath(args.project or os.getcwd())
    out("  working dir : %s" % cwd)
    if os.path.isdir(cwd) and os.access(cwd, os.W_OK):
        ok("可写（alm.in / *.bands 等会生成在这里）")
    else:
        fail("不可写", cwd)

    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------
    out("")
    out("=" * 60)
    out("  结果：%d 项失败，%d 项警告" % (len(FAILS), len(WARNS)))
    for name in FAILS:
        out("    FAIL  %s" % name)
    for name in WARNS:
        out("    WARN  %s" % name)
    out("=" * 60)
    if not FAILS:
        out("  部署基本可用。最后确认 config/settings.yaml 的 alamode.bin_dir")
        out("  指向你自己的 ALAMODE 编译目录，然后运行 alamodekit 即可。")

    if args.save:
        with open(args.save, "w", encoding="utf-8") as fh:
            fh.write("\n".join(REPORT))
        print("\n  报告已写入: %s" % args.save)

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
