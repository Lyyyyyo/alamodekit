# Contributing to ALAMODEkit

First of all, thank you for taking the time to contribute! 🎉

The following is a short guide to keep the toolkit consistent and easy to
maintain.

## Development setup

```bash
git clone https://github.com/<your-fork>/ALAMODEkit.git
cd ALAMODEkit/alamodekit_linux
pip install -e .                 # editable install
pip install -r requirements.txt
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
- Each subprogram must be runnable **standalone** — call
  `alamodekit_io.ensure_package_root()` at the top so the toolkit root is
  importable no matter the working directory.

## Adding a new subprogram

1. Place the script under the right `No.X/<submenu>/` folder.
2. Register it in the `HIERARCHICAL_SCRIPTS` dictionary in `alamodekit.py`,
   with a unique `id`, a clear `desc`, the `script` filename, and the list of
   `required_files` the user must have in the working directory.
3. If it plots, import from `plot_style` and never hard-code styling.
4. Update `README.md` (menu layout table). The `No.*/*/*.py` wildcards in
   `setup.py`, `pyproject.toml` and `MANIFEST.in` already match any
   `No.X/<submenu>/` folder, so an ordinary new subprogram needs **no**
   manifest edit at all.
5. Run `python -m py_compile <your_script>.py` to confirm it parses.
6. Confirm the script actually ships, by building the wheel and looking
   inside it: `pip wheel . --no-deps -w /tmp/whl` then
   `python -c "import glob,zipfile;print([n for n in zipfile.ZipFile(glob.glob('/tmp/whl/*.whl')[0]).namelist() if 'No.8' in n])"`.
   CI runs the same check automatically (see "Guard the wheel payload").

## Packaging invariants

These three facts have bitten this toolkit before. Please do not undo them.

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
