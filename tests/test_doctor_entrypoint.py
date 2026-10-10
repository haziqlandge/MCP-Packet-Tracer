"""The doctor subcommand dispatches before any MCP transport starts."""

from __future__ import annotations

import importlib
import pytest


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "doctor-entrypoint-test-token-long-enough-012345")
    monkeypatch.setenv("HOME", str(tmp_path))
    module = importlib.import_module("src.packet_tracer_mcp.server")
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
