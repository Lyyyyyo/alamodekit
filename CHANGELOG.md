# Changelog

All notable changes to ALAMODEkit are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.0] — 2026-10-08

### Fixed
- **ANPHON input generators no longer emit an `&interaction` block.** The
  four ANPHON input scripts (`pre_scph.py`, `pre_cal_k.py`, `pre_harphband.py`,
  `pre_harphdos.py` under No.1/102) mistakenly wrote an ALM-only
  `&interaction` / `NORDER = 1` namelist. ANPHON has no such namelist; the
  force-constant expansion order is carried by FCSXML/FC2XML, so the block is
  now omitted. The four ALM scripts under No.1/101 correctly keep it.
- **CI workflow validity and NumPy 2.x compatibility.** The
  vibration-visualiser CI step embedded a POSCAR heredoc whose body was
  accidentally left at column 0, which made `.github/workflows/ci.yml`
  invalid YAML (the `run:` block scalar ended early) so the workflow failed
  before creating any job; the heredoc body is now correctly indented. In
  addition, `thermo_from_dos.py` and `kappa_spec.py` called the removed
  `numpy.trapz` (renamed `numpy.trapezoid` in NumPy 2.0); both now use a
  version-agnostic integration alias, and the in-CI Python snippet was fixed
  the same way.
- **No.6 convergence-helper CI step.** The smoke test put the template in
  `/tmp` but `conv_test_helper.py` writes its expanded inputs and `run_all.sh`
  into the current working directory, so the path assertion failed on every
  Python version; the test now runs inside a dedicated empty folder with the
  template placed there too, matching the tool's behaviour.
- **No.7 external-interface and vibration CI steps.** Same class of fix:
  `structure_to_vesta.py` and `vib_vesta.py` also write their exported
  `.xsf`/`.cif`/`.axsf` into the current working directory, but the smoke
  tests ran from the checkout root while looking for those files next to the
  `/tmp` inputs; both steps now run in dedicated empty folders
  (`/tmp/ext`, `/tmp/vib`) with their inputs placed alongside.

### Changed
- Package version bumped to **4.0** (author-assigned release number); the
  toolkit content is otherwise 1.5.1 plus the ANPHON fix above.
- **Unified on-screen rule width.** Every `====` menu banner and separator
  line now uses a fixed 60-character width, with the title centred on the
  rule. Previously the main-menu title/footer and the per-script
  banners/separators were mixed across 40/50/60/72 characters and looked
  uneven. (The reST title underlines inside module docstrings are unchanged.)
- **Removed redundant execution confirmations.** Choosing a function now runs
  it immediately after the REQUIRED FILES are listed; the
  "Proceed to execute? (y/n)" prompt is gone. The batch FORCE_CONSTANTS tool
  no longer asks "Use this path?" or "Start processing?" — it uses the
  resolved `convert_fc2.py` path and starts directly.
- **Plots are produced automatically.** The plotting steps in `APR_band`,
  `gru_band`, `ALMcv_result`, `phvel_band`, and `analyze_phonons` no longer
  ask a post-computation "Plot ...? (y/n)" question; they draw the figure as
  soon as the data are ready. On a headless node `plt.show()` still needs X
  forwarding/a display (no image file is written).
- The `run_anphon` "Run with MPI?" prompt is intentionally kept, together with
  every genuine parameter, file-number, and menu input: it selects serial vs.
  `mpirun -np N` execution and is a real runtime option, not a confirmation.
- **Author attribution and repository metadata.** The MIT `LICENSE` copyright
  line and the package metadata now name the authors (刘欣 / Xin Liu and
  刘宇佳 / Yujia Liu, Liu Group, State Key Laboratory of New Textile Materials
  and Advanced Processing Technologies, Wuhan Textile University), and
  `setup.py`, `pyproject.toml` and the README point at the GitHub repository.

## [1.5.1] — 2026-09-23

### Added
- **Shared-layer pytest suite (`tests/`)** — 36 tests covering the four
  shared modules: the pure-Python YAML fallback parser and the settings
  search order (`alamodekit_config`); high-symmetry label parsing/merging
  and the `.bands` reader (`alamodekit_io`); POSCAR/KPATH/namelist helpers
  (`alamode_input`); custom colormap anchors and rcParams (`plot_style`).
  Run with `python -m pytest tests/`. pytest is a development-only
  dependency and is not added to the runtime requirements.
- **`DEPLOYMENT.md`** — a deployment guide for installing the toolkit on a
  machine that is not the developer's: prerequisites, the three install modes
  and when each is appropriate, distributing a tarball/wheel, the per-user
  configuration pattern for a shared server or cluster (the `settings.yaml`
  search order), verification, and the traps listed below.
- **`check_deploy.py`** — post-deployment health check. Verifies the
  interpreter, the script tree, that all 43 menu entries resolve to real files,
  which `settings.yaml` is in use, every ALAMODE binary, the Python
  dependencies, a headless matplotlib smoke test, MPI, and that the working
  directory is writable. Exit status is the number of failures, so it can gate
  a deployment script. Standard-library-only at import time, and it works both
  from the source tree and from the copy installed into `site-packages`.
- **`INSTALL.txt` and `INSTALL_EN.txt`** — a plain-text installation walkthrough
  in Chinese and English (the same document section by section): prerequisites,
  the six-step deployment path, the three install modes, the configuration
  lookup order, thirteen caveats that have actually bitten this project, and a
  symptom-to-fix table. Aimed at whoever installs the toolkit on a machine that
  is not the developer's.
- **A "global command" step in both INSTALL documents.** Step 7 (optional)
  documents the three ways to get a bare `alamodekit` command instead of typing
  `python3 .../alamodekit.py`: the entry point pip already generates (modes B
  and C), a three-line wrapper script in `~/.local/bin` for a source install
  (modes A and clusters), and a shell alias for quick personal use — with the
  failure mode of each, what to verify, and the rule that `alamodekit.py` must
  not be symlinked or moved on its own. Verified on a fresh `pip install .`:
  the command is created, it works from an unrelated directory, it dispatches
  a subprogram from there, and all 44 scripts under No.X (43 menu functions
  plus 1 imported plotting companion) plus the five shared modules and
  `config/settings.yaml` are present in `site-packages`.
- `MANIFEST.in` now also ships `CONTRIBUTING.md`, `DEPLOYMENT.md`,
  `INSTALL.txt` and `INSTALL_EN.txt`.

### Fixed
- **`run_alm.py` output-scan cleanup.** Removed an unused `base` variable
  and replaced five separate `os.listdir(".")` passes (one per suffix) with
  a single directory scan matched against a suffix tuple.
- **Documentation count wording unified.** README, DEPLOYMENT, both INSTALL
  documents and CHANGELOG now consistently distinguish the **43 menu
  functions** from the **44 on-disk scripts** — the extra one,
  `plot_analyze_phonons.py`, is an imported plotting companion, not a menu
  entry.
- **Fallback YAML parser now strips a UTF-8 BOM.** A `settings.yaml` saved by
  Windows Notepad starts with a BOM, which the pure-Python fallback (used when
  PyYAML is absent) treated as part of the first key, silently dropping the
  whole `alamode` section. `.gitignore` now also ignores `.pytest_cache/`.
- **Subprograms can be run standalone again.** 21 of the 44 scripts under No.X
  (`No.1`, `No.3`, `No.5` and most of `No.2`) imported `alamodekit_io` without
  first putting the toolkit root on `sys.path`. The menu launches them as
  `python <root>/No.X/<submenu>/<script>.py`, so `sys.path[0]` is the script's
  own folder; every one of them died with

      ModuleNotFoundError: No module named 'alamodekit_io'

  They now carry the same bootstrap block the `No.6`/`No.7` scripts already
  used. (The root cause was a documentation gap: `CONTRIBUTING.md` said a
  subprogram only needed `ensure_package_root()`, which cannot work, because
  the `import` on the line above it fails first.)
- `alamodekit.py` exports the toolkit root and `BASE_PATH` on `PYTHONPATH` for
  every subprocess it launches, so the menu no longer depends on each script
  having a correct bootstrap.
- **The wheel now actually carries the toolkit.** `package_data` was declared
  but no package was, so setuptools silently dropped the whole `No.X` script
  tree *and* `config/settings.yaml` from the wheel: `pip install .` produced an
  installation in which none of the 43 menu entries could be resolved, while
  `pip install -e .` masked the problem by reading the source tree directly.
  `setup.py` now declares `packages=[""]` together with
  `package_dir={"": "."}`; the payload went from 5 files to the complete tree.
- `MANIFEST.in` had never been committed: the `.gitignore` rule `*.in`, meant
  for generated ALAMODE inputs (`alm.in`, `phband.in`, ...), also matched it.
- The packaging lists stopped at `No.5`, so 19 subprograms were missing from
  both the sdist and wheel manifests.

### Changed
- The three packaging lists (`setup.py`, `pyproject.toml`, `MANIFEST.in`) use
  the `No.*/*/*.py` wildcard, so a new `No.X` section needs no manifest edit.
  They are kept identical on purpose: `[tool.setuptools.package-data]` in
  `pyproject.toml` overrides `setup.py`'s `package_data`.
- CI builds a wheel and asserts its payload contains every subprogram plus
  `config/settings.yaml` — the regression this release fixes went unnoticed
  precisely because every other CI step runs from the source tree.
- The README installation section now describes all three install modes, warns
  against installing into the system Python, and points at `DEPLOYMENT.md` for
  anything beyond a single-user machine. The previous text told the reader to
  `git clone https://github.com/<your-username>/ALAMODEkit.git`, a placeholder
  URL that resolves nowhere.
- Both INSTALL documents were restructured around a **vaspkit-style "unpack and
  run"** route, which is now the default and needs **no virtual environment**
  (dependencies install with `python3 -m pip install --user`). Virtual
  environments (venv / conda, including re-activation after every re-login and
  the `(alamodekit)` prompt marker) were moved into an optional section with
  guidance on when they actually help (shared clusters, conflicting Python
  projects). The install-modes table, caveats and the error table were updated
  to match — answering the common question "why can't this just work like
  vaspkit?".

## [1.5.0] — Linux: phonon vibration visualisation (No.7/706) + source audit

### Source audit
- Searched every ``.py`` file for references to ``alamode``. All hits are:
  - the toolkit's own ``alamodekit_*`` modules, or
  - calls to :func:`get_alamode_bin` that resolve a **compiled binary** path
    (``alm`` / ``anphon`` / ``analyze_phonons`` / ``dfc2``) and invoke it via
  ``subprocess``. **No ALAMODE source code is bundled or imported.**
- The ``alamode-develop`` tree in the working directory is read *only* to
  confirm the on-disk format of the public output files (``.evec``,
  ``.bands``, ``.dos``, ``.kl``, ``.kl_spec``, ``BORN``) so that the parsers
  are correct; none of it ships with the toolkit.

### Added
- **706 phonon vibration visualisation** — :file:`vib_vesta` reads an ALAMODE
  eigenvector file (``.evec`` / ``.band.evec`` / ``.mesh.evec``) together with a
  POSCAR and writes per-mode ``.axsf`` animations for VESTA / XCrySDen. The
  vibration model is the standard textbook phonon displacement field,
  including the inter-cell phase ``2*pi*(k.R)`` for non-Gamma k-points (which
  forces the use of a commensurate super-cell via ``--dim``), mass-weighted
  displacement amplitudes, and a sinusoidal time animation. No ALAMODE
  binary or source is needed — it only parses the two text files.
- The menu now registers **43** functions (42 + 1).
- CI workflow extended with a No.7/706 smoke test.

### Verified
- Gamma-point Si (2 atoms): 6 modes written, optical modes show the two Si
  atoms moving in opposite directions with the correct amplitude.
- X-point (k = 1/2) mode in a 2x1x1 super-cell: the two cells carry opposite
  phases, confirming the ``2*pi*(k.R)`` inter-cell phase is correct.

## [1.4.0] — Linux: external interfaces & thermodynamics (No.7)

### Added
- A new **No.7** menu category with **5 tools** that connect the toolkit to
  external software and add thermodynamic analysis. None of them bundle or
  import any solver source; they parse public, documented file formats.
  - **701 thermodynamics from DOS** — `thermo_from_dos` computes ZPE, U(T),
    F(T), S(T), C_v(T) from a phonon DOS using standard statistical-mechanics
    formulas (trapezoidal integration over the frequency grid).
  - **702 NAC parameter extraction** — `extract_born` reads the dielectric
    tensor and Born effective charges from a VASP OUTCAR or Quantum ESPRESSO
    output and writes a NAC file in **both** the ALAMODE and the Phonopy BORN
    formats. Defaults to the total (electronic+ionic) dielectric.
  - **703 structure export** — `structure_to_vesta` exports a POSCAR to XSF,
    CIF and a minimal VESTA native format for visualisation in VESTA /
    XCRYSDEN / Mercury. Self-contained POSCAR parser.
  - **704 ASE bridge** — `ase_bridge` exposes space-group detection,
    primitive/conventional-cell conversion and neighbour analysis. The
    `--spacegroup` mode works with **just spglib** (no ASE) via a built-in
    POSCAR reader; the other modes require the optional `ase` package.
    Version-agnostic spglib API handling (works with 2.x).
  - **705 spectral thermal conductivity** — `kappa_spec` parses the ALAMODE
    `.kl_spec` file, plots kappa(omega) for selected temperatures and
    reports the integrated cumulative kappa as a cross-check.
- The menu now registers **42 functions** (37 + 5).
- `requirements.txt` documents the optional `spglib` / `ase` dependencies.
- CI workflow extended with No.7 smoke tests (thermo + structure export).

### Verified
- All 5 No.7 tools pass `py_compile` and end-to-end tests with synthetic data:
  Cv approaching the Dulong-Petit limit, total dielectric from OUTCAR,
  Pm-3m (221) detected for cubic BaTiO3 via spglib, XSF/CIF/VESTA written,
  kappa spectrum integrated.

## [1.3.0] — Linux: pure-Python helpers (No.6)

### Added
- A new **No.6** menu category with **12 pure-Python helpers** that depend on
  **no ALAMODE source or solver code** — only text files, numpy and the
  standard library. This makes the toolkit useful for the bookkeeping around
  a calculation, not just its plotting.
  - **601 Structure pre-processing**: `poscar_info` (inspect + 3D preview),
    `build_supercell` (POSCAR → SPOSCAR), `structure_convert` (POSCAR ↔ QE
    pw.in), `qpath_generator` (high-symmetry q-path), `dfset_inspector`.
  - **602 Result analysis**: `kappa_analyzer` (thermal conductivity `.kl`),
    `softmode_detector` (imaginary/soft modes), `bands_compare` (overlay).
  - **603 Cluster job scripts**: `cluster_submit` generates SLURM / PBS /
    local run scripts (template only — never submits the job itself).
  - **604 Input validation & sweeps**: `input_validator` checks namelist
    syntax (unclosed blocks, duplicate keys, stray content);
    `conv_test_helper` generates a Cartesian-product parameter sweep from a
    `@PLACEHOLDER@` template plus a `run_all.sh`.
  - **605 Results archiving**: `results_archive` collects output files into a
    timestamped `.tar.gz` with an auto-generated README.
- The menu now registers **37 functions** (25 + 12).
- `alamodekit_io` gained a `substitute_gamma()` label helper.
- CI workflow extended with a No.6 smoke-test step.

### Verified
- All 12 No.6 tools pass `py_compile` and end-to-end tests with synthetic
  data (kappa tensor, soft-mode bands, namelist input, sweep template, archive).

## [1.2.0] — Linux CLI edition

### Context
This is the **Linux command-line edition**, split from the unified toolkit to
keep a clear separation of concerns:

- The Linux edition drives the full workflow including running the compiled
  `alm` / `anphon` / `analyze_phonons` / `dfc2` binaries on compute servers.
- It does **NOT** bundle or import the ALAMODE Python source-code tools. The
  former official-tool wrappers (displace/extract/calcpes/plotband/plotdos)
  have been removed to avoid coupling to upstream source.

### Structure
- Menu registers **25 functions** across 5 categories (No.1,2,3,4,5).
- "Run ALAMODE solvers" is now **No.5** (`501/run_alm.py`, `502/run_anphon.py`
  with optional MPI).
- `alamode.tools_dir` setting removed from `config/settings.yaml` (no longer
  needed); only `bin_dir` and the binary names remain.
- Packaging files, CI workflow and README updated to match.

### Carried over from v1.x
- Config-driven plotting, single `settings.yaml`, `analyze_phonons` wrapper,
  all No.1/2/3/4 subprograms and their bug fixes (`pre_cal_k.py` indentation,
  `pre_sbtecontrol.py` stray colon, `post_sbte.py` duplicate `.csv`).
