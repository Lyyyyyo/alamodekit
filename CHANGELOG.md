# Changelog

All notable changes to ALAMODEkit are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
