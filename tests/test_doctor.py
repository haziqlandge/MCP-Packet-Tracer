"""Offline diagnostics must be read-only, injectable and safe to print."""
from __future__ import annotations

import io
import json
import shlex
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.packet_tracer_mcp.infrastructure.platform import doctor
from src.packet_tracer_mcp.infrastructure.platform.base import HostInfo


class Probes(doctor.DoctorProbes):
    def __init__(self, **overrides):
        self.home = Path('/home/test')
        self.platform = SimpleNamespace(host=HostInfo('macos', '26.5', 'arm64', '3.12'),
                                        state_dir=self.home / '.local/state/packet-tracer-mcp',
                                        clipboard=SimpleNamespace(name='pbcopy'))
        self.values = dict(version=(3, 12, 0), installed=True, writable=True,
                           token='x' * 40, root=(self.home / 'Documents/output', True),
                           pids=[123], mailbox=dict(dir=str(self.platform.state_dir / 'bridge'),
                                                   alive=True, age_s=0.8, legacy=False),
                           http=dict(identity='ours', authenticated=True, last_poll_ago=0.8),
                           free=False, pid=99, ui=dict(backend='macos', ok=True, reason='',
                               permissions=dict(accessibility=True, screen_recording=True), grant_to='Claude'))
        self.values.update(overrides)
        self.requests = []

    def python_version(self): return self.values['version']
    def installed(self): return self.values['installed']
    def writable(self, path): return self.values['writable']
    def token(self): return self.values['token']
    def output(self): return self.values['root']
    def pt_pids(self): return self.values['pids']
    def mailbox(self, file_bridge=None): return dict(self.values['mailbox'])
    def http_bridge(self, token): return self.values['http']
    def port_free(self): return self.values['free']
    def listener_pid(self): return self.values['pid']
    def ui(self, *, request=False):
        self.requests.append(request)
        return self.values['ui']


def invoke(probes, *args):
    out = io.StringIO()
    code = doctor.run(['--json', *args], probes=probes, out=out)
    return code, json.loads(out.getvalue())


def test_json_order_and_fingerprint_only():
    p = Probes()
    code, report = invoke(p)
    assert code == 0
    assert list(report) == ['checks', 'ok']
    assert [r['id'] for r in report['checks']] == [
        'python', 'install', 'state_dir', 'token', 'output_root', 'pt', 'extension', 'port', 'clipboard', 'ui']
    assert all(list(r) == ['id', 'required', 'ok', 'detail', 'fix'] for r in report['checks'])
    raw = json.dumps(report)
    assert p.values['token'] not in raw
    assert 'fingerprint' in raw
    assert 'fallback' in raw
    assert p.requests == [False]


@pytest.mark.parametrize('override,failed', [
    ({'version': (3, 10, 9)}, 'python'), ({'installed': False}, 'install'),
    ({'writable': False}, 'state_dir'), ({'token': None}, 'token'),
    ({'pids': []}, 'pt'),
    ({'mailbox': dict(dir='/none', alive=False, age_s=None, legacy=False),
      'http': dict(identity='none', authenticated=False, last_poll_ago=None)}, 'extension'),
    ({'http': dict(identity='foreign', authenticated=False, last_poll_ago=None)}, 'port'),
])
def test_required_failures_have_remedies(override, failed):
    code, report = invoke(Probes(**override))
    assert code == 1
    row = next(r for r in report['checks'] if r['id'] == failed)
    assert not row['ok'] and row['fix']


def test_optional_checks_and_ui_flag():
    p = Probes(ui=dict(backend='null', ok=False, reason='Install UI backend',
                      permissions={}, grant_to=None))
    p.platform.clipboard.name = 'none'
    assert invoke(p)[0] == 0
    assert invoke(p, '--ui')[0] == 1


def test_permissions_are_requested_only_explicitly():
    p = Probes()
    invoke(p, '--ui')
    invoke(p, '--request-permissions')
    assert p.requests == [False, True]


@pytest.mark.parametrize('age,authenticated,expected', [(9.9, True, True), (10.0, True, False),
                                                     (0.1, False, False), (None, True, False)])
def test_http_extension_requires_authenticated_fresh_poll(age, authenticated, expected):
    p = Probes(mailbox=dict(dir='/none', alive=False, age_s=None, legacy=False),
               http=dict(identity='ours', authenticated=authenticated, last_poll_ago=age))
    _, report = invoke(p)
    assert next(r['ok'] for r in report['checks'] if r['id'] == 'extension') == expected


def test_free_port_passes_without_a_server():
    p = Probes(free=True, http=dict(identity='none', authenticated=False, last_poll_ago=None))
    assert invoke(p)[0] == 0


def test_foreign_listener_remedy_names_pid_and_platform_command():
    _, report = invoke(Probes(http=dict(identity='foreign', authenticated=False, last_poll_ago=None)))
    row = next(r for r in report['checks'] if r['id'] == 'port')
    assert '99' in row['detail'] and 'lsof -i :54321' in row['fix']


def test_platform_schema_and_tilde():
    st = doctor.platform_status(probes=Probes())
    assert list(st) == ['os', 'os_version', 'arch', 'state_dir', 'mailbox', 'clipboard', 'ui']
    assert st['state_dir'].startswith('~/') and st['mailbox']['dir'].startswith('~/')
    assert list(st['mailbox']) == ['dir', 'alive', 'age_s', 'legacy']
    assert list(st['ui']) == ['backend', 'ok', 'reason', 'permissions', 'grant_to']


def test_print_config_uses_absolute_python_and_shell_quotes(monkeypatch):
    executable = str(Path('/Applications/Test folder/python $x;echo').absolute())
    monkeypatch.setattr(doctor.sys, 'executable', executable)
    p = Probes()
    out = io.StringIO()
    assert doctor.run(['--print-config', 'claude-code'], probes=p, out=out) == 0
    argv = shlex.split(out.getvalue())
    assert argv == ['claude', 'mcp', 'add', 'packet-tracer', '--', executable,
                    '-m', 'packet_tracer_mcp.server', '--stdio']
    out = io.StringIO()
    doctor.run(['--print-config', 'claude-desktop'], probes=p, out=out)
    config = json.loads(out.getvalue())['mcpServers']['packet-tracer']
    assert config == dict(command=executable, args=['-m', 'packet_tracer_mcp.server', '--stdio'])
    assert p.requests == []


def test_missing_or_invalid_token_is_never_created_or_rotated(tmp_path):
    p = doctor.DoctorProbes(home=tmp_path, env={})
    p.platform = SimpleNamespace(state_dir=tmp_path / 'state')
    assert p.token() is None
    assert not p.platform.state_dir.exists()
    p.platform.state_dir.mkdir()
    target = p.platform.state_dir / 'bridge_token'
    target.write_text('bad-token')
    assert p.token() is None
    assert target.read_text() == 'bad-token'


def test_http_identity_probe_never_sends_secret_to_foreign_listener(monkeypatch):
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b'{"service":"other","id":"bad"}'
    def urlopen(req, **kwargs):
        calls.append(req)
        return Response()
    monkeypatch.setattr(doctor.urllib.request, 'build_opener',
                        lambda *handlers: SimpleNamespace(open=urlopen))
    token = 'x' * 40
    result = doctor.DoctorProbes().http_bridge(token)
    assert result['identity'] == 'foreign'
    assert len(calls) == 1
    assert token not in calls[0].full_url
    assert not calls[0].headers


def test_home_paths_use_forward_slashes_on_windows(monkeypatch):
    from pathlib import PureWindowsPath
    monkeypatch.setattr(doctor, 'Path', PureWindowsPath)
    home = PureWindowsPath('C:/Users/Test')
    assert doctor._tilde(home / '.local/state/packet-tracer-mcp', home) == '~/.local/state/packet-tracer-mcp'
