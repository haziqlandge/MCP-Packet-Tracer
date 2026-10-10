"""Read-only diagnostics and client configuration (PLAN/INTERFACES.md §6).

Probes are injectable: no Packet Tracer, bridge startup, token generation or
permission request is needed to exercise any check. Only the explicit
``--request-permissions`` flag asks the UI backend for macOS permissions.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from . import current, host, output_root
from .base import Platform

PORT = 54321


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]


def _tilde(path: str | Path, home: Path) -> str:
    path = Path(path)
    try:
        relative = path.relative_to(home)
    except ValueError:
        return str(path)
    return (Path('~') / relative).as_posix()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The token belongs to this loopback listener and must never follow it.
        return None


class DoctorProbes:
    """Host probes. Override methods in tests; construction has no write effects."""

    def __init__(self, *, platform: Platform | None = None,
                 home: Path | None = None, env: Mapping[str, str] | None = None):
        self.platform = platform if platform is not None else current()
        self.home = Path.home() if home is None else Path(home)
        self.env = os.environ if env is None else env

    def python_version(self) -> tuple[int, ...]:
        return tuple(sys.version_info[:3])

    def installed(self) -> bool:
        try:
            return importlib.util.find_spec('packet_tracer_mcp') is not None
        except (ImportError, ValueError):
            return False

    def writable(self, path: Path) -> bool:
        """Check an existing directory or the closest existing ancestor; no files."""
        path = Path(path)
        while not path.exists() and path != path.parent:
            path = path.parent
        return path.is_dir() and os.access(path, os.W_OK)

    def token(self) -> str | None:
        """Read an existing valid secret, never create or rotate it."""
        value = self.env.get('PT_MCP_BRIDGE_TOKEN', '').strip()
        if not value:
            try:
                value = (self.platform.state_dir / 'bridge_token').read_text(
                    encoding='utf-8-sig').strip()
            except (OSError, UnicodeError):
                return None
        return value if len(value) >= 32 and re.fullmatch(r'[A-Za-z0-9_-]+', value) else None

    def output(self) -> tuple[Path, bool]:
        try:
            cwd = Path.cwd()
        except OSError:
            cwd = None
        root = output_root(cwd=cwd, env=self.env, home=self.home, os_name=self.platform.host.os)
        fallback = not bool(self.env.get('PT_MCP_OUTPUT_DIR', '').strip()) and root != cwd
        return root, fallback

    def pt_pids(self) -> list[int]:
        return host.pt_processes(os_name=self.platform.host.os)

    def mailbox(self, file_bridge=None) -> dict:
        if file_bridge is None:
            from ..execution.file_bridge import FileBridge
            from .paths import mailbox_candidates
            file_bridge = FileBridge(candidates=mailbox_candidates(
                self.platform.host.os, self.env, self.home))
        return file_bridge.mailbox_status()

    def _get_json(self, path: str, token: str | None = None) -> dict | None:
        req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}')
        if token:
            req.add_header('X-PT-Token', token)
        try:
            # Ignore proxies for this local connection, and never redirect secrets.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
            with opener.open(req, timeout=1.0) as response:
                if response.status != 200:
                    return None
                value = json.loads(response.read(65536).decode('utf-8'))
                return value if isinstance(value, dict) else None
        except (OSError, ValueError, urllib.error.URLError):
            return None

    def http_bridge(self, token: str | None) -> dict:
        result = {'identity': 'none', 'authenticated': False, 'last_poll_ago': None}
        ping = self._get_json('/ping')
        if ping is None:
            return result
        result['identity'] = 'foreign'
        if not token or ping.get('service') != 'pt-mcp-bridge' or ping.get('id') != _fingerprint(token):
            return result
        result['identity'] = 'ours'
        status = self._get_json('/status', token)
        if status is not None:
            result['authenticated'] = True
            result['last_poll_ago'] = status.get('last_poll_ago')
        return result

    def port_free(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('127.0.0.1', PORT))
            return True
        except OSError:
            return False

    def listener_pid(self) -> int | None:
        windows = self.platform.host.os == 'windows'
        argv = ['netstat', '-ano'] if windows else [
            'lsof', '-n', '-P', '-t', f'-iTCP:{PORT}', '-sTCP:LISTEN']
        try:
            text = subprocess.run(argv, capture_output=True, text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        for line in text.splitlines():
            fields = line.split()
            if windows:
                if len(fields) >= 5 and fields[0] == 'TCP' and fields[1].endswith(f':{PORT}') and fields[3] == 'LISTENING':
                    return int(fields[-1]) if fields[-1].isdigit() else None
            elif line.strip().isdigit():
                return int(line.strip())
        return None

    def permission_state(self) -> dict[str, bool]:
        if self.platform.host.os != 'macos':
            return {}
        from ..ui.backends.macos import permissions
        if permissions.pyobjc_missing():
            return {'accessibility': False, 'screen_recording': False}
        try:
            state = permissions.state()
            return {key: bool(state.get(key)) for key in ('accessibility', 'screen_recording')}
        except (ImportError, OSError):
            return {'accessibility': False, 'screen_recording': False}

    def grant_to(self) -> str | None:
        return host.responsible_app(os.getpid(), os_name=self.platform.host.os)

    def ui(self, *, request: bool = False) -> dict:
        backend = self.platform.ui_backend()
        ok, reason = backend.available(request=request)
        permissions = self.permission_state()
        if self.platform.host.os == 'macos':
            ok = ok and all(permissions.values())
            if not ok and not reason:
                from ..ui.backends.macos import permissions as mac_permissions
                missing = [key for key, granted in permissions.items() if not granted]
                reason = mac_permissions.remedy(missing, self.grant_to(),
                    host.responsible_bundle(os.getpid(), os_name='macos'))
        return {'backend': backend.name, 'ok': bool(ok), 'reason': reason,
                'permissions': permissions, 'grant_to': self.grant_to()}


def ui_status(platform: Platform | None = None, *, request: bool = False,
              probes: DoctorProbes | None = None) -> dict:
    """UI readiness, including both capture and navigation grants on macOS."""
    return (probes if probes is not None else DoctorProbes(platform=platform)).ui(request=request)


def platform_status(file_bridge=None, *, platform: Platform | None = None,
                    probes: DoctorProbes | None = None) -> dict:
    """Compact ordered platform block; preflight only, never asks for grants."""
    probes = probes if probes is not None else DoctorProbes(platform=platform)
    platform = probes.platform
    mailbox = probes.mailbox(file_bridge)
    return {'os': platform.host.os, 'os_version': platform.host.os_version,
            'arch': platform.host.arch, 'state_dir': _tilde(platform.state_dir, probes.home),
            'mailbox': {'dir': _tilde(mailbox['dir'], probes.home), 'alive': mailbox['alive'],
                        'age_s': mailbox['age_s'], 'legacy': mailbox['legacy']},
            'clipboard': platform.clipboard.name, 'ui': ui_status(probes=probes)}


def checks(*, ui: bool = False, request_permissions: bool = False,
           probes: DoctorProbes | None = None) -> list[dict]:
    """Ordered check data with actionable fixes and no secret in any field."""
    probes = probes if probes is not None else DoctorProbes()
    platform = probes.platform
    rows = []

    def add(id: str, ok: bool, detail: str, fix: str, required: bool = True) -> None:
        rows.append({'id': id, 'required': required, 'ok': bool(ok),
                     'detail': detail, 'fix': '' if ok else fix})

    version = probes.python_version()
    add('python', version >= (3, 11), '.'.join(map(str, version)),
        'Install Python 3.11 or newer and reinstall packet-tracer-mcp in that interpreter.')
    installed = probes.installed()
    add('install', installed, 'packet-tracer-mcp importable' if installed else 'Package is not importable',
        'Run this interpreter with -m pip install --upgrade packet-tracer-mcp.')
    state = _tilde(platform.state_dir, probes.home)
    add('state_dir', probes.writable(platform.state_dir), state,
        f'Make {state} writable by the user running this MCP server.')
    token = probes.token()
    add('token', token is not None, f'present; fingerprint {_fingerprint(token)}' if token else 'No usable existing token',
        'Start the MCP server once to create its pairing token; check PT_MCP_BRIDGE_TOKEN if set.')
    root, fallback = probes.output()
    add('output_root', probes.writable(root), f'{_tilde(root, probes.home)}; fallback={str(fallback).lower()}',
        'Set PT_MCP_OUTPUT_DIR to a writable directory or fix permissions on the output root.')
    pids = probes.pt_pids()
    add('pt', bool(pids), f'Packet Tracer PIDs: {", ".join(map(str, pids))}' if pids else 'Packet Tracer is not running',
        'Open Cisco Packet Tracer with the MCP Control Center extension installed.')
    mailbox = probes.mailbox()
    http = probes.http_bridge(token)
    age = http.get('last_poll_ago')
    polled = (http.get('identity') == 'ours' and http.get('authenticated') is True
              and isinstance(age, (int, float)) and not isinstance(age, bool) and 0 <= age < 10)
    seen = mailbox['alive'] or polled
    detail = (f'Fresh mailbox heartbeat: {_tilde(mailbox["dir"], probes.home)}' if mailbox['alive']
              else f'Authenticated HTTP poll {age}s ago' if polled
              else 'No fresh mailbox heartbeat or authenticated HTTP poll within 10 s. '
                   'When the server is down, only the mailbox heartbeat can show the extension.')
    add('extension', seen, detail,
        'Install or reload the MCP Control Center .pts extension and open its window. '
        'A missing heartbeat can mean the extension is not installed or is broken.')
    ours = http.get('identity') == 'ours' and http.get('authenticated') is True
    free = probes.port_free() if not ours else False
    pid = probes.listener_pid() if not (free or ours) else None
    port_detail = ('Port 54321 held by this authenticated bridge' if ours else 'Port 54321 is free' if free
                   else f'Port 54321 held by another process; PID {pid if pid is not None else "unknown"}')
    command = 'netstat -ano' if platform.host.os == 'windows' else 'lsof -i :54321'
    add('port', free or ours, port_detail,
        f'Identify the listener with `{command}`; stop the foreign listener or reconnect the intended MCP server.')
    clipboard = platform.clipboard.name
    add('clipboard', clipboard != 'none', clipboard,
        'Install a clipboard tool (wl-copy, xclip or xsel on Linux); file exports work meanwhile.', False)
    status = ui_status(probes=probes, request=request_permissions)
    add('ui', status['ok'], f'{status["backend"]}; grant_to={status["grant_to"]}; {status["reason"]}'.rstrip('; '),
        status['reason'] or 'Install the UI dependencies and grant the required UI permissions.', ui)
    return rows


def _config(client: str, os_name: str) -> str:
    executable = str(Path(sys.executable).absolute())
    argv = [executable, '-m', 'packet_tracer_mcp.server', '--stdio']
    if client == 'claude-desktop':
        return json.dumps({'mcpServers': {'packet-tracer': {'command': argv[0], 'args': argv[1:]}}}, indent=2)
    words = ['claude', 'mcp', 'add', 'packet-tracer', '--', *argv]
    if os_name == 'windows':
        # PowerShell quoting preserves spaces, dollar signs and command punctuation.
        return '& ' + ' '.join("'" + word.replace("'", "''") + "'" for word in words)
    return shlex.join(words)


def run(argv: Sequence[str] | None = None, *, probes: DoctorProbes | None = None,
        out: TextIO | None = None) -> int:
    """Run the doctor CLI, returning 1 only when a required check fails."""
    parser = argparse.ArgumentParser(prog='pt-mcp doctor')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--ui', action='store_true')
    parser.add_argument('--request-permissions', action='store_true')
    parser.add_argument('--print-config', choices=('claude-code', 'claude-desktop'))
    args = parser.parse_args(argv)
    probes = probes if probes is not None else DoctorProbes()
    out = sys.stdout if out is None else out
    if args.print_config:
        print(_config(args.print_config, probes.platform.host.os), file=out)
        return 0
    rows = checks(ui=args.ui, request_permissions=args.request_permissions, probes=probes)
    ok = all(row['ok'] for row in rows if row['required'])
    if args.json:
        print(json.dumps({'checks': rows, 'ok': ok}), file=out)
    else:
        for row in rows:
            print(f'{row["id"]}: {"OK" if row["ok"] else "FAIL"} — {row["detail"]}'
                  + (f' | fix: {row["fix"]}' if row['fix'] else ''), file=out)
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)
