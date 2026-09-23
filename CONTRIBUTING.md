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
4. Update `README.md` (menu layout table) and `setup.py` / `pyproject.toml`
   `package-data` globs if you created a new folder.
5. Run `python -m py_compile <your_script>.py` to confirm it parses.

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
