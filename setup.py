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

Note: the No.X/<submenu>/<script>.py files are NOT installed as importable
Python modules (their names contain dots and they are meant to be executed
by the menu, not imported). They are declared as package data so that source
distributions and editable installs carry the complete script tree.

Because the toolkit declares no Python package of its own (there is no
``packages=`` argument), a plain ``pip install .`` copies only the five
top-level modules: neither the ``No.X`` script tree nor
``config/settings.yaml`` is installed, so the launcher would have nothing to
resolve. The ``alamodekit`` console script therefore requires an **editable**
install (``pip install -e .``), which keeps the script tree in place;
otherwise run ``python alamodekit.py`` from the source tree.
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
    py_modules=[
        "alamodekit", "alamodekit_config", "alamodekit_io",
        "alamode_input", "plot_style",
    ],
    # Ship the menu subprograms and the config file as package data.
    package_data={
        "": [
            "config/settings.yaml",
            "No.1/101/*.py", "No.1/102/*.py",
            "No.2/201/*.py", "No.2/202/*.py", "No.2/203/*.py",
            "No.2/204/*.py", "No.2/205/*.py",
            "No.3/301/*.py", "No.3/302/*.py",
            "No.4/401/*.py", "No.4/402/*.py",
            "No.5/501/*.py", "No.5/502/*.py",
            "No.6/601/*.py", "No.6/602/*.py", "No.6/603/*.py",
            "No.6/604/*.py", "No.6/605/*.py",
            "No.7/701/*.py", "No.7/702/*.py", "No.7/703/*.py",
            "No.7/704/*.py", "No.7/705/*.py", "No.7/706/*.py",
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
