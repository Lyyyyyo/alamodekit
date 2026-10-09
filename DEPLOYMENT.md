# Deploying ALAMODEkit

This guide is for **whoever is installing the toolkit on a machine that is not
the developer's** — a group member's workstation, a shared compute server, or a
cluster login node. It covers the three supported install modes, the one file
every new user must edit, how to verify the result, and the traps that have
actually bitten this project.

If you only read one thing: **Mode A or Mode B, then edit
`alamode.bin_dir` in `config/settings.yaml`, then run
`python check_deploy.py`.**

---

## 0. A deployment is three separate things

| Piece | Who provides it | Where it is configured |
|---|---|---|
| **ALAMODE itself** (`alm`, `anphon`, `analyze_phonons`, `dfc2`) | the user compiles it | `alamode.bin_dir` in `config/settings.yaml` |
| **ALAMODEkit** (the Python menu + 43 menu functions; 44 on-disk scripts incl. 1 imported companion) | this repository | nothing — it comes preconfigured |
| **The user's own calculation directory** (POSCAR, DFSET, ...) | the user | just `cd` there and run |

ALAMODEkit **never bundles or imports the ALAMODE source**. It only calls the
compiled binaries. So a deployment is never finished until `bin_dir` points at
a real build.

---

## 1. Prerequisites

On the target machine:

| Requirement | Needed for | Check |
|---|---|---|
| Python ≥ 3.8 | everything | `python3 --version` |
| numpy, matplotlib, pandas, PyYAML | everything / plotting / 2 scripts / config | `python3 check_deploy.py` |
| A **compiled** ALAMODE build | No.5 solver runners, No.2/202 | `$BIN_DIR/alm --help` |
| MPI (`mpirun`) | No.5/502 with parallel onphon, No.6/603 | `which mpirun` |
| ShengBTE | No.4 only | — |
| spglib, ase | No.7/704 only | `pip install spglib ase` |

PyYAML is a normal dependency: `alamodekit_config.py` ships a small fallback
parser, so the toolkit still starts without it, but real YAML parsing is what
you want.

**Use a dedicated virtualenv or conda environment.** Do not install into the
system Python or into `conda`'s `base` — a several-hundred-line toolkit has no
business writing `No.1/` … `No.7/` into a shared site-packages.

---

## 2. Get the code

```bash
# from git
git clone <repository-url> ALAMODEkit
cd ALAMODEkit

# or from an archive somebody handed you
tar xzf ALAMODEkit-4.0.tar.gz && cd ALAMODEkit-4.0
```

Everything below assumes the current directory contains `alamodekit.py`,
`config/settings.yaml` and the `No.1` … `No.7` folders. If it does not, you are
one level too deep or too shallow.

---

## 3. Choose an install mode

| | Mode A — run from the source tree | Mode B — editable install | Mode C — regular install |
|---|---|---|---|
| Command | `python /path/to/ALAMODEkit/alamodekit.py` | `pip install -e .` then `alamodekit` | `pip install .` then `alamodekit` |
| Script tree lives in | the checkout | the checkout | `site-packages` |
| Global `alamodekit` command | no | **yes** | **yes** |
| Survives upgrading the toolkit how? | replace the checkout | `git pull` | `pip install --force-reinstall` |
| Writes into `site-packages` | nothing | a `.pth`/finder + dist-info | the whole tree |
| Good for | shared/cluster installs, users who want to read the code | developers, single users | distributing a single artifact |

### Mode A — run straight from the source tree (recommended on a cluster)

```bash
python3 -m venv ~/.venvs/alamodekit
source ~/.venvs/alamodekit/bin/activate
pip install -r requirements.txt

# from any working directory at all:
python ~/opt/ALAMODEkit/alamodekit.py
```

The launcher resolves every subprogram relative to its own location, and each
subprogram finds the toolkit root by itself, so the working directory can be
your calculation directory. Nothing is written outside your venv.

To avoid typing the path, add an alias to `~/.bashrc`:

```bash
alias alamodekit='python ~/opt/ALAMODEkit/alamodekit.py'
```

This is the mode to use on a shared server: install once into a read-only
shared location, let every user point their own config at it.

### Mode B — editable install

```bash
python3 -m venv ~/.venvs/alamodekit && source ~/.venvs/alamodekit/bin/activate
pip install -e .
alamodekit          # works from any directory
```

The `alamodekit` command and the `No.X` script tree stay in the checkout, so
`git pull` is the whole upgrade procedure.

### Mode C — regular install

```bash
python3 -m venv ~/.venvs/alamodekit && source ~/.venvs/alamodekit/bin/activate
pip install .
alamodekit          # works from any directory
```

Because the toolkit is flat (there is no top-level package directory), the
project root itself is installed as a package. That is what makes the `No.X`
tree and `config/settings.yaml` land in `site-packages` — and it also means
**every `.py` file sitting at the project root is installed there**, including
`setup.py` and `check_deploy.py`. Harmless, but do not be surprised by it, and
do not leave scratch scripts in the repository root.

Mode C is right when you want to hand out a single artifact. Read
"Installing from an artifact" below.

### Installing from an artifact (no git access for the new user)

Build once, on any machine:

```bash
rm -rf build dist            # see the trap in section 7
python -m build              # or: python setup.py sdist bdist_wheel
ls dist/                     # alamodekit-4.0.tar.gz, alamodekit-4.0-py3-none-any.whl
```

Then the new user does:

```bash
pip install alamodekit-4.0.tar.gz     # source distribution: builds on their machine
# or
pip install alamodekit-4.0-py3-none-any.whl
```

The wheel is pure Python (`py3-none-any`), so the same file works on Linux and
macOS. The sdist additionally carries `check_deploy.py` and `MANIFEST.in` and
is the better thing to archive.

---

## 4. Configure — the only file a new user must edit

`config/settings.yaml` is the single source of truth. At minimum, set:

```yaml
alamode:
  bin_dir: /home/your_user/alamode/alamode/build   # <- YOUR compiled ALAMODE
```

Shipped value is the placeholder `/home/username/alamode/alamode/build`; if you
forget to change it, every No.5 run fails with "No such file or directory".

Leave `alamodekit.base_path` **empty**. The launcher then uses the directory
that contains `alamodekit.py`, which is correct for all three install modes.

Everything else in the file is plotting style (DPI, fonts, colours, colormaps,
units) and applies globally.

### Where the file is looked up

`alamodekit_config.py` searches, in order:

1. the path in the **`ALAMODEKIT_CONFIG`** environment variable
2. **`./config/settings.yaml`** in the current working directory
3. **`./settings.yaml`** in the current working directory
4. the copy shipped with the toolkit

That order is what makes a **shared read-only install plus per-user config**
work:

```bash
# toolkit installed centrally, every user keeps their own settings
export ALAMODEKIT_CONFIG=~/.config/alamodekit.yaml
```

or simply drop a `settings.yaml` into your calculation directory. Note that a
per-directory file **replaces** the bundled one entirely — it does not merge —
so start by copying the shipped file and editing it.

To see which file is actually in use:

```bash
python -c "import alamodekit_config as c; print(c.get_settings_path())"
```

---

## 5. Verify the deployment

One command, from the toolkit root:

```bash
python check_deploy.py                    # the tree next to this file
python check_deploy.py --root /opt/ALAMODEkit --project ~/work/Si
python check_deploy.py --save deploy.txt   # keep the transcript
```

It checks the interpreter, the script tree, that all 43 menu entries resolve to
real files, which `settings.yaml` is in use, every ALAMODE binary, the Python
dependencies, a headless matplotlib smoke test, MPI, and that your working
directory is writable. The exit status is the number of failures, so it is
usable in a script:

```bash
python check_deploy.py || echo "deployment incomplete"
```

A healthy deployment looks like this (the `alm/anphon/...` lines appear once
`bin_dir` is set):

```
1. Python interpreter          [ OK ]  Python >= 3.8
2. Toolkit root and script tree[ OK ]  No.X 章节齐全   7 个
                               [ OK ]  脚本文件   44 个 .py
3. Launcher registry vs. disk  [ OK ]  菜单注册的 43 个功能全部能定位到文件
4. settings.yaml resolution    [ OK ]  配置加载成功
5. ALAMODE binaries            [ OK ]  alm 可执行
6. Python dependencies         [ OK ]  numpy 2.5.3   matplotlib 3.11.2 ...
7. matplotlib headless test    [ OK ]  Agg 后端可正常出图
8. MPI                         [ OK ]  找到 MPI 启动器
9. Working directory           [ OK ]  可写
```

Then a 30-second functional smoke test — create `SPOSCAR` in an empty
directory and run the first menu entry (`1` → `101` → `1`):

```bash
mkdir -p /tmp/smoke && cd /tmp/smoke
printf 'Cu\n1.0\n3.615 0.0 0.0\n0.0 3.615 0.0\n0.0 0.0 3.615\nCu\n1\nDirect\n0.0 0.0 0.0\n' > SPOSCAR
alamodekit            # select 1, then 101, then 1; answer y
ls                    # -> alm.in
```

If `alm.in` appears, the deployment is functional: the menu dispatched a
subprogram, the shared modules imported, and the file was written into *your*
directory.

---

## 6. Cluster notes

**Keep the environment off `base`.** Create a venv (Mode A/B/C) or a named
conda env. On a login node, `python3 -m venv` for the toolkit itself is usually
faster than conda:

```bash
module load python/3.11
python3 -m venv ~/.venvs/alamodekit && source ~/.venvs/alamodekit/bin/activate
pip install -r requirements.txt
```

**No display.** Compute nodes have no X server. The toolkit's plotting uses
the `Agg` backend and works headless, but if you have configured matplotlib
globally, export it explicitly:

```bash
export MPLBACKEND=Agg
```

**`module load` is a runtime thing, not an install-time thing.** No.5/501 and
No.5/502 can prepend a `module load` line before calling the binaries; the
choice is stored per run, not in `settings.yaml`.

**MPI.** No.5/502 and No.6/603 generate `mpirun -np N <exe> < input`; the
launcher must therefore be able to start MPI. Do not run `mpirun` directly on a
login node — use No.6/603 to generate an `sbatch`/`qsub` script and submit it.

**Shared installation.** Put the checkout (or the venv) somewhere read-only and
common, e.g. `/opt/ALAMODEkit`, and have users set `ALAMODEKIT_CONFIG` or drop
their own `settings.yaml` — see section 4. Do not put the toolkit inside a
user's home directory if several people need it.

---

## 7. Traps that have actually occurred here

**Stale `build/` contaminates the wheel.**
`python setup.py bdist_wheel` reuses `build/bdist.*/wheel` if it exists, and
only removes it at the end of a successful run. If a build was interrupted (or
files were added to the tree since), the previous payload is zipped again
alongside the new one — the wheel then contains files that are no longer in the
source. Always build from a clean tree:

```bash
rm -rf build dist *.egg-info
```

**The wheel silently lost the entire No.X script tree (all 44 scripts).**
`package_data` is keyed by package. With no `packages=` declared there was
nothing to attach the `No.X` tree to, so setuptools dropped it *without an
error*, and `pip install .` produced a toolkit where nothing could be resolved.
`pip install -e .` hid the problem. See `CONTRIBUTING.md` → "Packaging
invariants" before touching `setup.py`, `pyproject.toml` or `MANIFEST.in`.

**`MANIFEST.in` was never committed**, because `.gitignore`'s `*.in` rule
(meant for generated `alm.in`, `phband.in`, …) matched it too. sdist builds
from a fresh clone were therefore missing the manifest.

**`ModuleNotFoundError: No module named 'alamodekit_io'`.**
21 subprograms used to import the shared modules without first putting the
toolkit root on `sys.path`. The menu launches each subprogram as a *separate
process*, so `sys.path[0]` is the script's own folder. Fixed in 1.5.0 —
`alamodekit.py` now also exports the root on `PYTHONPATH` — but if you see it
again, the script is missing its bootstrap block.

**`FileNotFoundError: settings.yaml`.**
The toolkit could not find any of the four candidate locations. Almost always
`ALAMODEKIT_CONFIG` pointing at a path that does not exist.

**`No such file or directory: /home/username/alamode/...`.**
`bin_dir` is still the factory placeholder.

---

## 8. Reporting a problem to whoever gave you the toolkit

Send the output of:

```bash
python check_deploy.py --save deploy.txt
cat deploy.txt
python -c "import alamodekit_config as c; print(c.get_settings_path())"
```

plus the traceback and the input file involved. That covers interpreter,
dependencies, config resolution and binary location in one shot.
