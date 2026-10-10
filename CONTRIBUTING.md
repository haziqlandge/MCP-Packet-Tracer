# Contributing

Thanks for looking. This is a personal project, so the process is light — but a
few things are worth knowing before you open a PR.

## Getting set up

```bash
git clone https://github.com/Mats2208/MCP-Packet-Tracer.git
cd MCP-Packet-Tracer
pip install -e ".[test]"
python -m pytest
```

The suite runs **offline** — nothing requires Cisco Packet Tracer. Use cases take
`bridge_send` / `query_pt_topology` as injectable callables, so tests pass
lambdas instead of talking to PT. Keep it that way: a test that needs PT open is
a test that never runs in CI.

Run pytest from the repo root; a couple of tests read source files by relative
path.

## Architecture in one minute

```
domain/         models (pydantic), rules (validation), services (planning)
application/    use cases — orchestrate rules + generators, no I/O of their own
infrastructure/ generators (JS + IOS CLI), execution (bridge, executors), catalog
adapters/mcp/   the MCP tools; a thin layer over the use cases
```

Two conventions that matter:

- **Validation lives in `domain/rules/`**, not in the models. Models are mostly
  free-form; the rules modules decide what's legal and return `ValidationResult`.
- **Generated JavaScript is built with `json.dumps`**, never with raw f-strings.
  Everything the generators emit is executed by PT's script engine via
  `new Function()`, so an unescaped field is code execution, not a typo. If you
  must interpolate into an existing literal, use `js_escape` from `shared/utils`.

## Filesystem paths

Anything that becomes a path component goes through `safe_name_component()` and
then `resolve_within()` from `shared/utils.py`. The sanitizer is the first
barrier; the post-`resolve()` containment check is what actually decides. Don't
add a third copy of that logic.

## Tests

New behaviour needs a test. Bug fixes need a test that **fails without the fix** —
if you can't make it fail first, it isn't testing what you think.

The suite was entirely happy-path until v0.6.0. If you touch anything that builds
JS or IOS config, add a case with a quote, a newline and a `..` in it. See
`tests/test_injection_regressions.py`.

## Live smoke lists and macOS fixtures

`tests/live/` contains JSON call lists for a running Packet Tracer; pytest does not
collect them. See [the live-test README](tests/live/README.md). Run from the repo
root, with one PT and one bridge at a time:

```bash
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json
python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/ui.json
```

These use the code in this checkout. A client's already-running MCP server keeps
its old code until reconnected. `setup.json` creates the fixture topology: save
your existing topology first, and run it only on an empty canvas. Read every tool
result; a reply without a traceback can still report a failure. UI smoke requires
the platform backend and, on macOS, grants for the app that launches the harness.

Record macOS Accessibility fixtures from real PT windows, rather than editing
`tests/fixtures/macos/*.json` by hand:

```bash
python -m src.packet_tracer_mcp.devtools.macos_probe windows --pid <PT_PID>
python -m src.packet_tracer_mcp.devtools.macos_probe ax --pid <PT_PID> --title PC1 --out /tmp/pc1-ax.json
```

Inspect the recording and its metadata before adding it as a fixture. AX frames
and click coordinates use points; captures use pixels. `macos_probe perms` is
preflight only; `--request` explicitly asks for permissions. Live checks establish
behavior only on the OS where they run; an offline test is not a live acceptance.

## Documentation checks

```bash
pip install -r docs/requirements.txt
mkdocs build --strict
```

Keep platform paths in [Live Deploy Setup](docs/live-deploy.md#per-os-paths) and
link to that table from other pages.

## Security

Don't open a public issue for a vulnerability — see [SECURITY.md](SECURITY.md).
It also documents what is deliberate rather than broken, which is worth reading
before reporting that `pt_send_raw` executes arbitrary JavaScript.

## Commits

Conventional-ish prefixes (`feat:`, `fix:`, `docs:`, `chore:`). Explain *why* in
the body, not just what — the diff already says what.
