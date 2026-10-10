"""El token del bridge: aprovisionamiento, rotacion y validacion.

Este modulo es el ancla de seguridad de TODO el bridge HTTP. `bridge_token.py`
lo dice en su propio encabezado: bindear a loopback no protege nada, porque un
`POST /queue` con `Content-Type: text/plain` es una peticion CORS simple y
cualquier pagina web abierta podia encolar JS que PT ejecuta con `new
Function()`. Lo unico que cierra ese agujero es este secreto.

Y no tenia un solo test. `grep -rln bridge_token tests/` no devolvia nada:
`test_bridge_security.py` cubre el PROTOCOLO (que se exija token, el Host, los
tamanos), pero el APROVISIONAMIENTO -- la carrera con O_EXCL, la rotacion ante
archivo corrupto, el fallback efimero, el gate `_is_valid` -- estaba a ciegas.

Peor: el CI setea `PT_MCP_BRIDGE_TOKEN` para todo el job y `get_bridge_token()`
lo devuelve en su PRIMERA linea, asi que aunque se escribieran estos tests el
camino real no se ejecutaria nunca ahi. Por eso la fixture quita esa variable y
redirige `token_dir()` a un tmp: para que el camino de archivo corra de verdad,
tambien en CI, y sin tocar el token real de quien ejecute la suite.
"""

import os

import pytest

from src.packet_tracer_mcp.infrastructure.execution import bridge_token
from src.packet_tracer_mcp.infrastructure.execution.bridge_token import (
    BridgeTokenError, get_bridge_token, token_path, token_fingerprint,
    token_was_rotated, token_is_ephemeral, reset_cache,
)

VALID_ENV_TOKEN = "ci-token-long-enough-to-be-considered-valid-0123456789"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Aisla el token: sin env var y con el directorio en tmp."""
    monkeypatch.delenv("PT_MCP_BRIDGE_TOKEN", raising=False)
    # token_dir() mira estas, segun el SO.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    reset_cache()
    yield tmp_path
    reset_cache()


class TestEnvOverrideIsValidated:
    """El override saltaba el gate: `PT_MCP_BRIDGE_TOKEN=x` daba un token de UN caracter.

    El archivo en disco pasa por `_is_valid` (>=32 chars, charset acotado); la
    variable de entorno no pasaba por nada. Un token corto es adivinable, y con
    el token adivinado toda la defensa contra la pagina web atacante se cae.
    """

    def test_a_valid_env_token_is_used(self, isolated, monkeypatch):
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", VALID_ENV_TOKEN)
        reset_cache()
        assert get_bridge_token() == VALID_ENV_TOKEN

    def test_a_short_env_token_is_rejected(self, isolated, monkeypatch):
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "x")
        reset_cache()
        with pytest.raises(BridgeTokenError):
            get_bridge_token()

    def test_an_env_token_with_bad_characters_is_rejected(self, isolated, monkeypatch):
        # El charset es [A-Za-z0-9_-]: va dentro de una query string sin escapar.
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "a" * 40 + "&evil=1")
        reset_cache()
        with pytest.raises(BridgeTokenError):
            get_bridge_token()

    def test_the_error_says_which_variable_is_wrong(self, isolated, monkeypatch):
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "corto")
        reset_cache()
        with pytest.raises(BridgeTokenError, match="PT_MCP_BRIDGE_TOKEN"):
            get_bridge_token()

    def test_surrounding_whitespace_is_tolerated(self, isolated, monkeypatch):
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", f"  {VALID_ENV_TOKEN}  ")
        reset_cache()
        assert get_bridge_token() == VALID_ENV_TOKEN

    def test_an_empty_env_var_falls_back_to_the_file(self, isolated, monkeypatch):
        """Vacio significa "no seteado", no "token invalido"."""
        monkeypatch.setenv("PT_MCP_BRIDGE_TOKEN", "   ")
        reset_cache()
        token = get_bridge_token()
        assert len(token) >= 32
        assert token_path().exists()


class TestFileProvisioning:
    def test_first_call_creates_a_valid_token_file(self, isolated):
        token = get_bridge_token()
        assert token_path().exists()
        assert token_path().read_text(encoding="utf-8").strip() == token
        assert len(token) >= 32

    def test_the_token_persists_across_processes(self, isolated):
        """Segunda lectura sin cache: tiene que salir el MISMO del disco."""
        first = get_bridge_token()
        reset_cache()
        assert get_bridge_token() == first

    def test_a_bom_and_whitespace_in_the_file_are_tolerated(self, isolated):
        """Alguien va a abrir el archivo con el Notepad tarde o temprano."""
        get_bridge_token()
        good = token_path().read_text(encoding="utf-8").strip()
        token_path().write_text(f"﻿  {good}  \n", encoding="utf-8")
        reset_cache()
        assert get_bridge_token() == good


class TestRotationOnCorruptFile:
    @pytest.mark.parametrize("bad", ["", "   ", "corto", "a" * 20, "con espacios adentro!!"])
    def test_an_invalid_file_is_rotated(self, isolated, bad):
        get_bridge_token()
        token_path().write_text(bad, encoding="utf-8")
        reset_cache()

        token = get_bridge_token()
        assert len(token) >= 32
        assert token != bad
        assert token_was_rotated(), "rotar en silencio deja al cliente emparejado obsoleto"

    def test_a_healthy_file_is_not_rotated(self, isolated):
        get_bridge_token()
        reset_cache()
        get_bridge_token()
        assert not token_was_rotated()


class TestEphemeralFallback:
    def test_an_unwritable_directory_falls_back_instead_of_crashing(
        self, isolated, monkeypatch
    ):
        """Un servidor que no arranca es peor que uno que avisa."""
        import pathlib

        def boom(*args, **kwargs):
            raise OSError("directorio de solo lectura")

        monkeypatch.setattr(pathlib.Path, "mkdir", boom)
        reset_cache()

        token = get_bridge_token()
        assert len(token) >= 32
        assert token_is_ephemeral()


class TestWriteRace:
    def test_the_loser_of_the_race_does_not_overwrite(self, isolated):
        """O_EXCL y no replace: con replace, dos servidores a la vez se quedaban
        con tokens DISTINTOS y el cliente solo podia hablar con uno."""
        first = get_bridge_token()
        # Simula al segundo proceso: el archivo ya existe.
        assert bridge_token._write_new(token_path()) is None
        assert token_path().read_text(encoding="utf-8").strip() == first


class TestFingerprint:
    def test_the_fingerprint_never_contains_the_token(self, isolated):
        token = get_bridge_token()
        fp = token_fingerprint(token)
        assert token not in fp
        assert len(fp) == 16

    def test_the_fingerprint_is_stable(self, isolated):
        token = get_bridge_token()
        assert token_fingerprint(token) == token_fingerprint(token)

    def test_different_tokens_give_different_fingerprints(self, isolated):
        assert token_fingerprint("a" * 40) != token_fingerprint("b" * 40)


@pytest.mark.skipif(os.name == "nt", reason="POSIX state directory")
class TestXdgStateHomeIgnored:
    """PLAN/INTERFACES.md §5: the extension cannot read XDG_STATE_HOME, so honouring
    it put the token where PT never looks and broke pairing on Linux and macOS."""

    def test_token_stays_under_home_local_state(self, isolated, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
        assert token_path() == isolated / ".local" / "state" / "packet-tracer-mcp" / "bridge_token"
