# ALAMODEkit test suite

Unit tests for the shared modules, written for
[pytest](https://docs.pytest.org/). They guard the common layer every
subprogram depends on, so a refactor cannot silently corrupt the data behind
input generation or plots.

## Running

From the toolkit root (the folder above this one):

```bash
pip install pytest                 # development-only dependency
python -m pytest tests/ -v
```

The same command runs in CI on every push.

## Layout

| File | Module under test | Focus |
| --- | --- | --- |
| `conftest.py` | — | bootstrap: puts the toolkit root on `sys.path`, forces the headless Agg backend |
| `test_config_loader.py` | `alamodekit_config.py` | YAML loading, the pure-Python fallback parser, the settings search order, nested lookups, UTF-8 BOM handling |
| `test_io_helpers.py` | `alamodekit_io.py` | POSCAR / `.bands` / `.dos` parsing, high-symmetry label merging, Γ-point renaming |
| `test_input_helpers.py` | `alamode_input.py` | ALM/ANPHON namelist generation, k-path handling, number formatting |
| `test_plot_style.py` | `plot_style.py` | rcParams, custom colormap colour anchors, colormap caching |

## Scope

These are **offline unit tests**. They deliberately do **not**:

- operate the interactive menu (`alamodekit.py`),
- invoke the ALAMODE binaries (`alm`, `anphon`, `analyze_phonons`, `dfc2`),
- or inspect rendered images.

Tests create small synthetic files in temporary directories; they never read
or modify real calculation data. When adding tests, keep them fast,
self-contained and independent of execution order.
