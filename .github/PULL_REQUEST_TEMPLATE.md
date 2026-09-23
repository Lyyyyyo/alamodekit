# Pull request checklist

Thank you for contributing to ALAMODEkit! Please tick every box below.

## Code
- [ ] My code follows the toolkit's style: English comments, module
      docstring, type hints where helpful, and config-driven styling for any
      new figure (no hard-coded colours / DPI).
- [ ] I ran `python -m py_compile <my_script>.py` and it compiles cleanly.
- [ ] If my change adds/changes a plotting parameter, I added it to
      `config/settings.yaml` and read it via `plot_style` / `alamodekit_config`.

## Menu / launcher
- [ ] If I added a new subprogram, I registered it in the
      `HIERARCHICAL_SCRIPTS` dictionary in `alamodekit.py` and placed the file
      under the correct `No.X/<submenu>/` folder.

## Docs
- [ ] I updated `README.md` (menu layout, new feature, or dependency).
- [ ] I updated the relevant function's docstring.

## Tests
- [ ] The CI workflow (`.github/workflows/ci.yml`) still passes.

## Description
<!-- Describe what this PR does and why. -->
