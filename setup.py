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
by the menu, not imported). They are included as package data so the menu
launcher can find them next to the package.
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
    version="1.0.0",
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
