"""Where tool outputs land (CONSTRAINTS C11, ISSUES X7).

A GUI client may start the server with cwd `/` (read-only on macOS), and every
exporting tool then failed with `[Errno 30] Read-only file system: 'projects'`.
`output_root()` keeps a writable cwd and falls back to a per-user folder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from src.packet_tracer_mcp.adapters.mcp.panel_support import screenshot_path
from src.packet_tracer_mcp.infrastructure.execution.deploy_executor import DeployExecutor
from src.packet_tracer_mcp.infrastructure.execution.manual_executor import ManualExecutor
from src.packet_tracer_mcp.infrastructure.persistence.project_repository import ProjectRepository
from src.packet_tracer_mcp.infrastructure.platform.output import output_dir, output_root


class TestOutputRoot:
    def test_env_override_wins(self, tmp_path):
        target = tmp_path / "chosen"
        assert output_root(cwd=tmp_path, env={"PT_MCP_OUTPUT_DIR": str(target)},
                           home=tmp_path, os_name="macos") == target

    def test_a_writable_cwd_is_kept(self, tmp_path):
        assert output_root(cwd=tmp_path, env={}, home=Path("/nowhere"), os_name="macos") == tmp_path

    @pytest.mark.parametrize("os_name, expected", [
        ("macos", ("Documents", "Packet Tracer MCP")),
        ("windows", ("Documents", "Packet Tracer MCP")),
        ("linux", ("packet-tracer-mcp",)),
    ])
    def test_a_filesystem_root_falls_back_to_home(self, tmp_path, os_name, expected):
        root = Path(Path.cwd().anchor)
        assert output_root(cwd=root, env={}, home=tmp_path, os_name=os_name) == tmp_path.joinpath(*expected)

    @pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                        reason="POSIX permission bits; root ignores them")
    def test_an_unwritable_cwd_falls_back_to_home(self, tmp_path):
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        try:
            home = tmp_path / "home"
            assert output_root(cwd=locked, env={}, home=home, os_name="macos") == \
                home / "Documents" / "Packet Tracer MCP"
        finally:
            locked.chmod(0o700)

    def test_output_root_creates_nothing(self, tmp_path):
        home = tmp_path / "home"
        output_root(cwd=Path(Path.cwd().anchor), env={}, home=home, os_name="linux")
        assert not home.exists()


class TestOutputDir:
    def test_is_one_safe_component_under_the_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path))
        d = output_dir("../../etc", fallback="projects")
        assert d.parent == tmp_path

    def test_empty_name_uses_the_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path))
        assert output_dir("", fallback="screenshots") == tmp_path / "screenshots"


class TestToolSitesUseTheRoot:
    """Each site wrote relative to the cwd before; now relative means "under the root"."""

    def test_screenshot_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path))
        p = screenshot_path("cap", "screenshots")
        assert p == (tmp_path / "screenshots" / "cap.png").resolve()

    @pytest.mark.parametrize("cls", [ManualExecutor, DeployExecutor])
    def test_executors_resolve_a_relative_dir_under_the_root(self, cls, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path))
        assert cls(output_dir="projects").output_dir == tmp_path / "projects"

    @pytest.mark.parametrize("cls", [ManualExecutor, DeployExecutor])
    def test_executors_keep_an_absolute_dir(self, cls, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path / "root"))
        explicit = tmp_path / "explicit"
        assert cls(output_dir=explicit).output_dir == explicit

    def test_project_repository(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_MCP_OUTPUT_DIR", str(tmp_path))
        assert ProjectRepository(base_dir="projects").base_dir == tmp_path / "projects"
