"""Platform dependencies install by themselves (PLAN/phases/PHASE-04.md).

Users asked for "connect the MCP and it works": a `[ui]` extra they must
remember is a step too many. pyobjc comes with the package on macOS, comtypes
on Windows, neither on Linux.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

PROJECT = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml")
                        .read_text(encoding="utf-8"))["project"]
DEPS = {Requirement(d).name.lower(): Requirement(d) for d in PROJECT["dependencies"]}
PYOBJC = ["pyobjc-core", "pyobjc-framework-cocoa", "pyobjc-framework-quartz",
          "pyobjc-framework-applicationservices", "pyobjc-framework-screencapturekit"]


def installs_on(req: Requirement, sys_platform: str) -> bool:
    return req.marker is None or req.marker.evaluate({"sys_platform": sys_platform})


def test_pyobjc_packages_install_on_macos_only():
    for name in PYOBJC:
        req = DEPS[name]
        assert installs_on(req, "darwin")
        assert not installs_on(req, "win32") and not installs_on(req, "linux")
        assert req.specifier.contains("12.2.2")   # the version PHASE-00 verified


def test_comtypes_installs_on_windows_only():
    req = DEPS["comtypes"]
    assert installs_on(req, "win32")
    assert not installs_on(req, "darwin") and not installs_on(req, "linux")


def test_ui_extra_is_kept_as_an_empty_alias():
    assert PROJECT["optional-dependencies"]["ui"] == []


def test_macos_classifier():
    assert "Operating System :: MacOS" in PROJECT["classifiers"]
