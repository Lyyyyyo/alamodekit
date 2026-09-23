#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py
========

Packaging script for ALAMODEkit.

Install the toolkit (and its console entry point) with::

    pip install .

or, for an editable developer install::

    pip install -e .

After installation, the interactive menu can be launched from anywhere with
the ``alamodekit`` command, which is equivalent to running
``python alamodekit.py``.

Note: the No.X/<submenu>/<script>.py files are NOT importable Python modules
(their names contain dots and they are executed by the menu, not imported).
They are shipped as package data instead. Because the toolkit has no
top-level package directory, the project root itself is declared as the
package (``packages=[""]`` together with ``package_dir={"": "."}``). Without
that declaration setuptools finds no package to attach ``package_data`` to,
silently drops the whole ``No.X`` tree from the wheel, and ``pip install .``
installs a toolkit that cannot resolve a single subprogram.

Both installation modes therefore work:

* ``pip install .`` copies the five top-level modules, the ``No.X`` script
  tree and ``config/settings.yaml`` into site-packages -- which is exactly
  where the launcher looks for them, because the shipped ``settings.yaml``
  leaves ``alamodekit.base_path`` empty and the launcher then falls back to
  the directory holding ``alamodekit.py``.
* ``pip install -e .`` keeps the tree in the source checkout.

Two traps to keep in mind when editing the payload lists
-------------------------------------------------------
* ``[tool.setuptools.package-data]`` in ``pyproject.toml`` **overrides**
  ``package_data`` below -- setuptools reads the pyproject value and ignores
  this one. Both files consequently carry the same wildcard so the outcome
  is identical no matter which declaration is honoured. Never let them
  drift apart.
* The root package ``""`` cannot be expressed in ``pyproject.toml``
  (setuptools rejects it during schema validation), so ``packages`` and
  ``package_dir`` have to stay in this file. Do not remove them.
"""
from __future__ import annotations

import os

from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))


def _read_text(name: str) -> str:
    """Read a file's text if it exists, otherwise return an empty string."""
    path = os.path.join(HERE, name)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    return ""


setup(
    name="alamodekit",
    version="1.5.0",
    description="Advanced ALAMODE Toolkit - input generation, post-processing and plotting for ALAMODE.",
    long_description=_read_text("README.md"),
    long_description_content_type="text/markdown",
    author="ALAMODEkit contributors",
    license="MIT",
    python_requires=">=3.8",
    # The toolkit has no top-level package directory, so we expose the root
    # files by treating the project root as a package.
    #
    # ``packages=[""]`` is what makes the package_data patterns below
    # effective at all: package_data is keyed by package, so with no package
    # declared setuptools has nothing to attach the No.X tree to and drops it
    # from the wheel without any error. ``package_dir={"": "."}`` maps that
    # root package onto the project directory and additionally keeps unrelated
    # top-level files (README, LICENSE, requirements.txt, ...) out of the
    # wheel. Both are also required by ``pip install -e .``.
    #
    # This declaration cannot move to pyproject.toml: setuptools rejects the
    # empty package name "" there during schema validation.
    packages=[""],
    package_dir={"": "."},
    py_modules=[
        "alamodekit", "alamodekit_config", "alamodekit_io",
        "alamode_input", "plot_style",
    ],
    # Ship the menu subprograms and the config file as package data.
    # ``No.*/*/*.py`` expands to No.<section>/<submenu>/<script>.py, so a new
    # No.8 section needs no edit here, in pyproject.toml or in MANIFEST.in.
    package_data={
        "": [
            "config/settings.yaml",
            "No.*/*/*.py",
        ],
    },
    include_package_data=True,
    install_requires=[
        "numpy>=1.20",
        "matplotlib>=3.3",
        "pandas>=1.2",
        "PyYAML>=5.4",
    ],
    entry_points={
        "console_scripts": [
            "alamodekit = alamodekit:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Physics",
        "Intended Audience :: Science/Research",
    ],
)
