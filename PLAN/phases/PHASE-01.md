# PHASE-01 — Platform layer

## Objective

`infrastructure/platform/` exists and is the only place, together with
`ui/backends/`, that knows which OS it is on. The state directory, clipboard and
output root work on Windows, macOS and Linux. CI runs the suite on macOS too.

## Why it exists

This is requirement (a), (b) and part of (e) in `RESEARCH/SYNTHESIS.md` §1. It
is also the seam the rest of the plan plugs into: PHASE-02 needs
`mailbox_candidates()`, PHASE-04 needs `responsible_app()`, and PHASE-06 needs
`host_info()`. Without one home for OS facts (C1), the next OS check lands in a
tool module and the code drifts back to Windows-only. Without `output_dir()`
(C11), a GUI client that starts the server in `/` breaks every exporting tool on
macOS, even with UI mode perfect.

## Dependencies

- PHASE-00: the cwd and PATH each client gives the server (SYNTHESIS §9,
  question 10), and the macOS baseline.
- Can be built in parallel with PHASE-03.

## Files to create

```
src/packet_tracer_mcp/infrastructure/platform/__init__.py   current(), reset_current()
src/packet_tracer_mcp/infrastructure/platform/base.py       OsName, detect_os, HostInfo, Clipboard, Platform
src/packet_tracer_mcp/infrastructure/platform/paths.py      state_dir(), mailbox_candidates()
src/packet_tracer_mcp/infrastructure/platform/clipboard.py  clipboard implementations + clipboard_for()
src/packet_tracer_mcp/infrastructure/platform/output.py     output_root(), output_dir()
src/packet_tracer_mcp/infrastructure/platform/host.py       host_info(), pt_processes(), responsible_app()
tests/test_platform_paths.py
tests/test_platform_clipboard.py
tests/test_platform_output.py
tests/test_platform_host.py
tests/test_os_checks_confined.py     C1 grep test
```

## Files to modify

- `infrastructure/execution/bridge_token.py`: `token_dir()` returns
  `platform.paths.state_dir(detect_os(), os.environ, Path.home())`. Keep the
  function name and signature (`file_bridge.py` and tests import it).
- `infrastructure/execution/deploy_executor.py`: `_copy_to_clipboard` →
  `platform.current().clipboard.copy`. Keep `is_available()`, but have it
  report whether the clipboard exists, not "is Windows".
- Every tool site that builds `Path(safe_name_component(output_dir, ...))`:
  `tools/canvas.py`, `tools/planning.py`, `tools/live.py` (`ManualExecutor` and
  `DeployExecutor` `output_dir="projects"`), `panel_support.screenshot_path`.
  They switch to `platform.output_dir()`. Find them with
  `grep -rn "safe_name_component(output_dir\|output_dir=\"projects\"" src`.
- `.github/workflows/tests.yml`: add `macos-latest` to `matrix.os` and update the
  comment.
- `devtools/codemap.py`: add the `infrastructure/platform/` description, then
  regenerate `CODEMAP.md`.
- `tests/test_bridge_token.py`: the `isolated` fixture still sets `HOME`, so
  isolation holds without `XDG_STATE_HOME`. Add a test that `XDG_STATE_HOME` is
  now ignored (it fails before the change, as AGENTS rule 5 requires).

## Implementation details

### State directory

Implement `INTERFACES.md` §5 exactly. **Dropping `XDG_STATE_HOME` is a
deliberate behaviour change.** It fixes Linux and macOS users who set it, whose
extension could never find the token. Record it in `CHANGELOG.md` under
Unreleased. `mailbox_candidates()` returns the canonical directory, plus the
legacy one on macOS and Linux. The `FileBridge` logic that uses it belongs to
PHASE-02.

### Clipboard

One small class per tool. Each takes a `run` callable (default
`subprocess.run`) so tests inject a fake. `clipboard_for()` selects as in
`INTERFACES.md` §1.

- `Pbcopy` passes `env={**os.environ, "LC_CTYPE": "UTF-8"}` and UTF-8 bytes.
  **Without it, a GUI-launched process can lack a locale, and pbcopy mangles
  non-ASCII text.**
- `ClipExe` keeps today's call byte-for-byte: `"clip"`, UTF-16-LE, 5 s timeout.
- Each `copy()` catches `SubprocessError`, `FileNotFoundError` and `OSError`,
  and returns False.

### Output root

`output_root()` returns the cwd when the cwd is writable and is not a filesystem
root. Writability is tested with `os.access(cwd, os.W_OK)`, never by creating
files. The `PT_MCP_OUTPUT_DIR` override wins over everything. The fallback
folder is created lazily by `output_dir()`'s caller, as today. Users whose cwd
was fine see no change. This keeps C9: tool parameters stay the same.

### Host

`responsible_app()` takes a `ps` callable that returns `(ppid, exe_path)` for a
pid. The default runs `ps -o ppid=,comm= -p <pid>`. The chain is walked up to 30
levels. The function is pure over that callable, so it can be tested with a
fixture chain on any OS. `pt_processes()` uses `pgrep -f "Packet Tracer"` on
macOS, `tasklist /FI "IMAGENAME eq PacketTracer.exe" /FO CSV /NH` on Windows,
and `pgrep -f PacketTracer` on Linux. Any failure returns `[]`.

### C1 enforcement

`tests/test_os_checks_confined.py` walks `src/packet_tracer_mcp/**/*.py` and
fails on `sys.platform` or `os.name` outside `infrastructure/platform/` and
`infrastructure/ui/backends/`. Until PHASE-03 lands, `ui/win32.py` (it moves to
`backends/windows/` in PHASE-03) and `ui/presenter.py` (`is_available`) are on
an allow-list. The test prints that list so PHASE-03 empties it.

## Inputs / outputs

- In: PHASE-00's cwd and PATH findings.
- Out: the `platform` package and CI on three OSes.

## Relevant interfaces

`INTERFACES.md` §1 (signatures), §5 (state dir and mailbox candidates).

## Relevant research

`RESEARCH/SYNTHESIS.md` §6 (cwd, PATH and pbcopy failure modes),
`RESEARCH/topics/pt-on-macos.md` §3 (why `XDG_STATE_HOME` must go).

## Tests

- `state_dir` for each OS, with fake env and home: Windows identical to today's
  `token_dir()` for each env combination. **This is the one the bridge rests on.**
- `XDG_STATE_HOME` ignored on macOS and Linux.
- `mailbox_candidates`: Windows has one entry; macOS and Linux have two, in order.
- `clipboard_for` with a fake `which`: every branch, including Wayland and none found.
- `Pbcopy.copy("héllo")` passes UTF-8 bytes and an env with `LC_CTYPE`.
  `ClipExe` passes UTF-16-LE.
- `output_root`: writable cwd; cwd `/` (macOS and Linux) or a drive root;
  unwritable cwd; env override.
- `responsible_app` on recorded chains: Claude.app, Terminal, iTerm2, VS Code,
  and a chain with no `.app` (returns None). Include the chain measured in
  PHASE-00 (Homebrew `Python.framework/.../Python.app` → zsh → Claude Code CLI
  `claude.app` → `disclaimer` → `Claude.app`): the answer is the CLI's `claude`,
  never `Python` (INTERFACES §1 amendment, 2026-10-10).
- C1 grep test.

## Acceptance criteria

- [x] All new tests pass on the Mac; the suite stays ≥ the macOS baseline (`CLAUDE.md` §5) — new platform/C1/XDG tests 93 passed (all watched failing first: missing module, 4 C1 offenders, token under XDG); full suite 906 passed ≥ 825; 2026-10-10
- [x] `test_bridge_token.py` passes unchanged except for the new XDG test — only `TestXdgStateHomeIgnored` appended; the file passes in the 93; 2026-10-10
- [x] CI is green on windows, ubuntu and macos (or, until pushed, the suite passes on the Mac and `tests.yml` lists macos-latest) — not pushed (the user asked for no commits); suite 906 passed on the Mac and `tests.yml` lists macos-latest. Remote CI unverified; 2026-10-10. Pushed later: CI run 38059124205 on `f86cfe9` green on windows, ubuntu and macos (3.11, 3.13)
- [x] Live on the Mac: `pt_deploy` reports "copied to clipboard", and `pbpaste` equals the generated script, including a non-ASCII device name — "SCRIPT COPIED TO THE CLIPBOARD"; `pbpaste` == `topology.js` with device `PC-Ñandú-é` (the generator writes it as `\u` escapes by AGENTS rule 1, so the script is ASCII). Raw UTF-8 checked directly: `platform.current().clipboard` under `env -i` (no locale) round-trips `héllo PC-Ñandú-é`; bare `pbcopy` without a locale gives `h√©llo PC-√ëand√∫-√©`; 2026-10-10
- [x] Live on the Mac: with the client's real cwd, `pt_screenshot` and `pt_export` write under `output_root()` and report the absolute path — cwd `~/packet tracer` (Claude desktop Code tab, PREVIOUS_WORK 2.4 #10) → `output_root()` = that folder; export to `.../projects/phase01-export`, screenshot `.../projects/phase01-shot.png` (13,646 bytes), both absolute, through this checkout's code via FastMCP with the live bridge. The cwd-`/` fallback is covered offline only; 2026-10-10
- [x] `CODEMAP.md` regenerated — `infrastructure/platform/` row added; `test_codemap.py` passes in the 906; 2026-10-10

## Known failure conditions

- `test_bridge_token` touches the real token → a test forgot `PT_MCP_BRIDGE_TOKEN`
  or the `isolated` fixture. Never point tests at the real state dir.
- `pbpaste` shows `h?llo` → `LC_CTYPE` was not passed. Check the env given to `run`.
- Exports vanish → they went to the fallback root. The reply must print the
  absolute path. Check `output_dir()` is used at that tool site.
- The C1 test flags a file outside the allow-list → move the check into
  `platform/`. Do not extend the allow-list.
