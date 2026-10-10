"""CONSTRAINTS C2: every module imports on every OS.

Each run is a fresh interpreter. It first imports every module with the real OS
(so third-party and stdlib modules are loaded the normal way), then drops this
package from `sys.modules`, fakes `sys.platform`, makes the OS-only packages
(comtypes, pyobjc) unimportable, and imports every module again. A module that
touches an OS API or an OS-only package at import time fails here, on any CI
runner, instead of on the user's machine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import importlib, pkgutil, sys

BLOCKED = {"comtypes", "objc", "AppKit", "Foundation", "Quartz", "ApplicationServices",
           "ScreenCaptureKit", "CoreFoundation", "Cocoa", "PyObjCTools"}
PKG = "src.packet_tracer_mcp"


class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"{name} is blocked: OS-only package")
        return None


root = importlib.import_module(PKG)
names = [i.name for i in pkgutil.walk_packages(root.__path__, PKG + ".")
         if not i.name.endswith(".__main__")]
for n in names:
    importlib.import_module(n)
for n in [m for m in sys.modules if m == PKG or m.startswith(PKG + ".")
          or m.split(".")[0] in BLOCKED]:
    del sys.modules[n]
sys.meta_path.insert(0, Block())
sys.platform = sys.argv[1]

failed = []
try:
    import comtypes  # noqa: F401
    failed.append("the blocker is not active")
except ImportError:
    pass
for n in names:
    try:
        importlib.import_module(n)
    except Exception as exc:
        failed.append(f"{n}: {type(exc).__name__}: {exc}")
print(f"{len(names)} modules")
print("\n".join(failed))
sys.exit(1 if failed else 0)
'''


@pytest.mark.parametrize("fake_platform", ["win32", "darwin", "linux"])
def test_every_module_imports(fake_platform):
    r = subprocess.run([sys.executable, "-c", SCRIPT, fake_platform], cwd=ROOT,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert int(r.stdout.split()[0]) > 100  # the walk really found the package
