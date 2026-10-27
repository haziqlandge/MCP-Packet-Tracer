"""The doctor subcommand dispatches before any MCP transport starts."""

from __future__ import annotations

import importlib
import pytest


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "doctor-entrypoint-test-token-long-enough-012345")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PT_MCP_WORKDIR", str(tmp_path / "work"))
    # main() enters the workdir before serving; give the suite its cwd back.
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module("src.packet_tracer_mcp.server")
    monkeypatch.setattr(module.BRIDGE, "ensure_bridge", lambda **kwargs: None)
    return module


@pytest.mark.parametrize("exit_code", [0, 1])
def test_doctor_receives_its_flags_and_never_starts_mcp(server, monkeypatch, exit_code):
    seen = []

    def doctor_main(args):
        seen.append(args)
        return exit_code

    def forbidden_run(**kwargs):
        raise AssertionError("Doctor must not start an MCP transport")

    doctor = importlib.import_module("src.packet_tracer_mcp.infrastructure.platform.doctor")
    monkeypatch.setattr(doctor, "main", doctor_main)
    monkeypatch.setattr(server.mcp, "run", forbidden_run)
    with pytest.raises(SystemExit) as exc:
        server.main(["doctor", "--ui", "--json"])
    assert exc.value.code == exit_code
    assert seen == [["--ui", "--json"]]


@pytest.mark.parametrize("args,transport", [([], "streamable-http"), (["--stdio"], "stdio")])
def test_existing_transport_choices_still_work(server, monkeypatch, args, transport):
    seen = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: seen.append(kwargs))
    server.main(args)
    assert seen == [{"transport": transport}]


def test_transport_port_is_configurable(server, monkeypatch):
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: None)
    monkeypatch.setattr(server.mcp.settings, "port", server.mcp.settings.port)
    server.main(["--port", "39009"])
    assert server.mcp.settings.port == 39009


@pytest.mark.parametrize("args", [["--port", "0"], ["--port", "65536"], ["--unknown"]])
def test_invalid_transport_arguments_fail_before_starting(server, monkeypatch, args):
    def forbidden_run(**kwargs):
        raise AssertionError("Invalid arguments must not start MCP")

    monkeypatch.setattr(server.mcp, "run", forbidden_run)
    with pytest.raises(SystemExit) as exc:
        server.main(args)
    assert exc.value.code == 2


def test_install_skill_dispatches_before_any_transport(server, monkeypatch):
    seen = []
    skill = importlib.import_module("src.packet_tracer_mcp.skill_install")
    monkeypatch.setattr(skill, "main", lambda args: seen.append(args) or 0)
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("install-skill must not start MCP")))
    with pytest.raises(SystemExit) as exc:
        server.main(["install-skill", "--dest", "x"])
    assert exc.value.code == 0
    assert seen == [["--dest", "x"]]
