# Contributing to ALAMODEkit

First of all, thank you for taking the time to contribute!

The following is a short guide to keep the toolkit consistent and easy to
maintain.

## Development setup

```bash
git clone https://github.com/<your-fork>/ALAMODEkit.git
cd ALAMODEkit/alamodekit_linux
pip install -e .                 # editable install
pip install -r requirements.txt
pip install pytest               # to run the test suite under tests/
```

You can now edit the toolkit and immediately run `alamodekit` from anywhere.

## Code style

- **Comments and docstrings in English**, so the project is accessible to the
  international community.
- Every module starts with a docstring describing its purpose.
- No hard-coded visual parameters in plotting scripts. Colours, line widths,
  DPI, colormaps, colorbar style, output formats, axis units — all live in
  `config/settings.yaml` and are read via `plot_style.py` /
  `alamodekit_config.py`. If you need a new style knob, add it to
  `settings.yaml` first, then expose it through `plot_style`.
- Shared logic goes into `alamodekit_io.py` (parsing) or `alamode_input.py`
  (namelist generation) rather than being duplicated across scripts.
- Each subprogram must be runnable **standalone**, including directly as
  `python No.X/<submenu>/<script>.py`. In that case `sys.path[0]` is the
  script's own folder and **not** the toolkit root, so importing
  `alamodekit_io` first is not enough — the import itself would fail. Put the
  toolkit root on `sys.path` *before* the first toolkit import:

  ```python
  import os
  import sys

  # --- Bootstrap: make the toolkit root importable when run as a script. ---
  _HERE = os.path.dirname(os.path.abspath(__file__))
  _ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
  if _ROOT not in sys.path:
      sys.path.insert(0, _ROOT)

  import alamodekit_io  # noqa: E402
  alamodekit_io.ensure_package_root()  # noqa: E402
  ```

  Copy this verbatim from any `No.6`/`No.7` script. `alamodekit.py` also
  exports the toolkit root on `PYTHONPATH` for every subprocess it launches,
  which masks a missing bootstrap when the subprogram is reached through the
  menu — but direct invocation still breaks. That asymmetry is exactly how
  the `No.1`–`No.5` scripts shipped broken. CI enforces this (see
  "Guard the subprogram bootstrap").

## Adding a new subprogram

1. Place the script under the right `No.X/<submenu>/` folder.
2. Add the `sys.path` bootstrap block (see "Code style") as the first
   executable lines, before any toolkit import. CI fails the build without it.
3. Register it in the `HIERARCHICAL_SCRIPTS` dictionary in `alamodekit.py`,
   with a unique `id`, a clear `desc`, the `script` filename, and the list of
   `required_files` the user must have in the working directory.
4. If it plots, import from `plot_style` and never hard-code styling.
5. Update `README.md` (menu layout table). The `No.*/*/*.py` wildcards in
   `setup.py`, `pyproject.toml` and `MANIFEST.in` already match any
   `No.X/<submenu>/` folder, so an ordinary new subprogram needs **no**
   manifest edit at all.
6. Run `python -m py_compile <your_script>.py` to confirm it parses; if you
   touched a shared module, also run `python -m pytest tests/` (see
   "Testing").
7. Confirm the script actually ships, by building the wheel and looking
   inside it: `pip wheel . --no-deps -w /tmp/whl` then
   `python -c "import glob,zipfile;print([n for n in zipfile.ZipFile(glob.glob('/tmp/whl/*.whl')[0]).namelist() if 'No.8' in n])"`.
   CI runs the same check automatically (see "Guard the wheel payload").

## Testing

The four shared modules are covered by a pytest suite under `tests/`. Run it
from the repository root:

```bash
python -m pytest tests/ -v
```

- Run the suite before opening a pull request; CI runs the same checks and
  fails on any regression.
- When you change a shared module (`alamodekit_config.py`, `alamodekit_io.py`,
  `alamode_input.py`, `plot_style.py`), add or update tests for the behaviour
  you touched. When a new subprogram adds reusable logic to one of those
  modules, test it there rather than inside the menu script.
- Tests build small synthetic files (POSCAR, KPATH, bands, settings) in
  temporary directories — follow the pattern in the existing tests instead of
  reading real calculation data.
- Keep tests **unit-scoped and offline**: no interactive menu, no
  `alm` / `anphon` subprocess, no network. `conftest.py` already puts the
  toolkit root on `sys.path` and forces the headless Agg backend.
- pytest is a **development-only** dependency: do not add it to
  `requirements.txt` or to `install_requires` in `setup.py`.

## Packaging invariants

These facts have bitten this toolkit before. Please do not undo them.

- **`setup.py` must keep `packages=[""]` and `package_dir={"": "."}`.** The
  toolkit is flat — there is no importable top-level package directory — so
  the project root is declared as the package. `package_data` is keyed by
  package, so without this declaration setuptools has nothing to attach the
  `No.X` tree to: it drops every subprogram from the wheel **without any
  error**, and `pip install .` then installs a toolkit that resolves nothing.
  `pip install -e .` masks the problem, because editable installs read the
  source tree directly.
- **`[tool.setuptools.package-data]` in `pyproject.toml` overrides
  `setup.py`'s `package_data`.** Editing only `setup.py` therefore has no
  effect on the wheel. Both lists are kept identical on purpose; never let
  them drift apart.
- **The root package cannot be declared in `pyproject.toml`.** setuptools
  rejects the empty package name `""` during schema validation, which is why
  `packages` / `package_dir` live in `setup.py` and must stay there.
- **Every `.py` file at the repository root is installed into
  `site-packages`.** Declaring the project root as a package means setuptools
  treats each root-level module as part of it — that is how `alamodekit.py` and
  friends get there, and it is also why `setup.py` and `check_deploy.py` end up
  there. It is harmless, but **do not leave scratch or experimental scripts in
  the repository root**: they will be shipped to every user.
- **Build from a clean tree.** `bdist_wheel` reuses `build/bdist.*/wheel` and
  only removes it after a *successful* run, so an interrupted build leaves its
  payload behind and the next wheel silently contains files that are no longer
  in the source. Always `rm -rf build dist *.egg-info` before packaging. (Both
  `build/` and `dist/` are in `.gitignore`; this is about local builds, not
  version control.)

## Deployment-sensitive files

- `config/settings.yaml` ships as package data and is what every user edits;
  keep new user-facing knobs there rather than in code.
- `DEPLOYMENT.md` documents the install modes; update it when the packaging
  changes.
- `INSTALL.txt` (Chinese) and `INSTALL_EN.txt` (English) are the plain-text
  install walkthroughs. They are the same document section by section, both
  ship in the sdist (see `MANIFEST.in`), so keep the two in step whenever the
  install procedure changes.
- `check_deploy.py` is the post-install health check. It must stay
  **standard-library-only at import time** so it can run on a machine where the
  dependencies are not installed yet, and it must keep working both from the
  source tree and from the copy installed into `site-packages`.

## Submitting changes

- Open a pull request against `main`.
- Fill in the PR checklist (`.github/PULL_REQUEST_TEMPLATE.md`).
- Make sure the CI workflow passes.

## Reporting bugs

Use the bug-report issue template and include the output of:

```bash
python -c "import alamodekit_config as c; print(c.get_settings_path())"
```

together with the relevant input file / traceback / figure.
