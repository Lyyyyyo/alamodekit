# ALAMODEkit — Linux CLI edition

**Advanced ALAMODE Toolkit (Linux / command-line edition)** — an interactive,
menu-driven toolkit that drives the full ALAMODE workflow from the terminal:

> input-file generation → **run alm / anphon** → result post-processing →
> publication-quality plotting

This edition targets Linux compute servers / clusters, where ALAMODE is
compiled and run. The toolkit **does not bundle or import the ALAMODE source
code** — it only invokes the compiled binaries (`alm`, `anphon`,
`analyze_phonons`, `dfc2`) that you build yourself, and it ships its own
independent post-processing & plotting code.

A separate **Windows GUI edition** (pure-Python, matplotlib-based, no ALAMODE
dependency) is available for desktop post-processing analysis.

---

## ✨ Features

- **Three-level interactive menu** dispatching to **43** subprograms across
  7 categories: input generation, analysis & plotting, force-constant
  processing, ShengBTE integration, solver running, pure-Python helpers,
  and external interfaces & thermodynamics.
- **One configuration file** (`config/settings.yaml`) controls the ALAMODE
  binary location plus every plotting parameter (DPI, line width, colours,
  colormaps, colorbars, axis units, output formats).
- **Solver runners** (No.5) that resolve `alm` / `anphon` from config,
  optionally prepend a cluster `module load`, support MPI parallel runs for
  anphon, and report the generated `.bands` / `.result` / `.fcs` files.
- **Config-driven plotting** through a shared `plot_style` module (harmonic /
  APR / velocity / Gruneisen bands, DOS, IFC-vs-distance, CV curves, phonon
  lifetimes & thermal conductivity).
- **External interfaces** (No.7): thermodynamics from DOS, dielectric/
  Born-charge extraction (VASP/QE → ALAMODE & Phonopy BORN), structure
  export to XSF/CIF/VESTA, an ASE/spglib bridge, spectral-kappa plotting,
  and phonon vibration animations (.axsf) for VESTA.
- **PyYAML optional**: the config loader ships a built-in fallback parser.

---

## 📦 Repository layout

```
alamodekit_linux/
├── alamodekit.py            # interactive menu launcher (37 functions)
├── alamodekit_config.py     # config loader (settings.yaml → dict)
├── alamodekit_io.py          # shared parsing helpers (bands/DOS/labels)
├── alamode_input.py          # shared ALM/ANPHON namelist helpers
├── plot_style.py             # shared matplotlib styling + save helpers
├── config/settings.yaml      # ← THE single user-editable config file
├── No.1/  Input File Generation
│   ├── 101/  ALM       displace_har.py, esti_har.py, alm_cv.py, esti_anhar.py
│   └── 102/  ANPHON    pre_harphband.py, pre_harphdos.py, pre_scph.py, pre_cal_k.py
├── No.2/  Analysis & Plotting
│   ├── 201/  Harmonic   APR_band.py, phvel_band.py, plot_harband.py, plot_hardos.py
│   ├── 202/  Anharmonic gru_band.py, phonon_lifetime.py, analyze_phonons.py,
│   │                    plot_analyze_phonons.py
│   ├── 203/  CV         ALMcv_result.py
│   ├── 204/  IFC        ifcs_dis.py
│   └── 205/  SCPH       scph_band.py, scph_dos.py
├── No.3/  SCPH 2nd force constants   301/dfc2.py, 302/FORCE_CONSTANTS.py
├── No.4/  ShengBTE integration       401/pre_sbtecontrol.py, 402/post_sbte.py
├── No.5/  Run ALAMODE solvers        501/run_alm.py, 502/run_anphon.py (MPI)
├── No.6/  Pure-Python helpers (no solver/source dependency)
│   ├── 601/  Structure pre-processing   poscar_info, build_supercell,
│   │        structure_convert, qpath_generator, dfset_inspector
│   ├── 602/  Result analysis            kappa_analyzer, softmode_detector,
│   │        bands_compare
│   ├── 603/  Cluster job scripts        cluster_submit (SLURM/PBS/local)
│   ├── 604/  Input validation & sweeps  input_validator, conv_test_helper
│   └── 605/  Results archiving         results_archive
├── No.7/  External interfaces & thermodynamics
│   ├── 701/  thermodynamics from DOS   thermo_from_dos
│   ├── 702/  NAC parameter extraction  extract_born (VASP/QE -> ALAMODE/Phonopy)
│   ├── 703/  structure export          structure_to_vesta (XSF/CIF/VESTA)
│   ├── 704/  ASE bridge                ase_bridge (space group / primitive / ...)
│   ├── 705/  spectral thermal kappa    kappa_spec (.kl_spec)
│   └── 706/  vibration visualisation   vib_vesta (.evec -> .axsf for VESTA)
├── setup.py, pyproject.toml, requirements.txt, MANIFEST.in
├── LICENSE, .gitignore, CHANGELOG.md, CONTRIBUTING.md
└── .github/ (CI workflow, issue/PR templates)
```

---

## 🚀 Installation

### Prerequisites
- Python ≥ 3.8
- A working **compiled** ALAMODE build (`alm`, `anphon`, `analyze_phonons`,
  `dfc2`). The toolkit calls these binaries; it does not need the ALAMODE
  Python sources.
- (Optional) ShengBTE for the No.4 integration scripts.

### Option A — install as a package (recommended)
```bash
git clone https://github.com/<your-username>/ALAMODEkit.git
cd ALAMODEkit/alamodekit_linux
pip install -e .
# launch from anywhere:
alamodekit
```

### Option B — run directly without installing
```bash
cd ALAMODEkit/alamodekit_linux
pip install -r requirements.txt
python alamodekit.py
```

---

## ⚙️ Configuration

Open **`config/settings.yaml`** and point `alamode.bin_dir` at your compiled
ALAMODE build:

```yaml
alamode:
  bin_dir: /home/your_user/alamode/alamode/build
  binaries:
    alm: alm
    anphon: anphon
    analyze_phonons: analyze_phonons
    dfc2: dfc2

plotting:
  dpi: 600
  lines:
    band_linewidth: 1.5
  colors:
    palette: ["#e41a1c", "#377eb8", ...]
  colormaps:
    velocity:  custom_yellow_green_blue
    gruneisen: custom_blue_white_red
```

---

## 🧭 Using the menu

Run `alamodekit` (or `python alamodekit.py`):

```
[1] Input File Generation
    [101] ALM     (suggest / optimize harmonic & anharmonic)
    [102] ANPHON  (phonon band, DOS, SCPH, RTA thermal conductivity)
[2] Analysis & Plotting
    [201] Harmonic    APR / velocity / band / DOS plotting
    [202] Anharmonic  Gruneisen / lifetime / analyze_phonons
    [203] CV          CV-curve analysis
    [204] IFC         IFC vs. distance
    [205] SCPH        temperature-dependent bands & DOS
[3] SCPH 2nd force constants → dfc2 / FORCE_CONSTANTS
[4] ShengBTE integration      → CONTROL / batch result extraction
[5] Run ALAMODE solvers
    [501] Run alm      (suggest/optimize; optional module load)
    [502] Run anphon   (phonons/RTA/SCPH; optional MPI)
```

### A typical harmonic workflow
1. **No.1/101** `displace_har.py` → `alm.in` (MODE=suggest)
2. **No.5/501** `run_alm.py` → run `alm`, get `prefix.pattern_HARMONIC`
3. Run DFT on the displaced structures (outside the toolkit)
4. Build `DFSET` and run **No.1/101** `esti_har.py` → `alm2.in`
5. **No.5/501** `run_alm.py` → fit force constants → `*.fcs` / `*.xml`
6. **No.1/102** `pre_harphband.py` → `phband.in`
7. **No.5/502** `run_anphon.py` → `*.bands` / `*.dos`
8. **No.2/201** plotting (config-driven)

---

## 🤝 Acknowledgements

ALAMODEkit builds on [ALAMODE](https://alamode.readthedocs.io/) by Terumasa
Tadano and co-authors. This edition only invokes the compiled ALAMODE
binaries; it does not redistribute the ALAMODE source code.

## 📄 License

MIT — see [LICENSE](LICENSE). ALAMODE and ShengBTE are independent third-party
projects under their own licenses.
