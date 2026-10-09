# RESEARCH — Index

Outside knowledge that the cross-platform plan rests on. It was written on
2026-10-10 on the Windows machine, from web sources and this repo's code.
**Nothing here was measured on a Mac.** PHASE-00 measures it. Its results go at
the end of `SYNTHESIS.md` as a dated "Local empirical update", never into the
sections above it.

## Notes

| ID | Source | Claim the plan uses | Grade | Why |
|---|---|---|---|---|
| S1 | Cisco PT FAQ / troubleshooting guide, items 39 and 150 (tutorials.ptnetacad.net/help/default/faqTroubleShoot.htm) | PT user folder: Windows `C:\Users\<u>\Cisco Packet Tracer <ver>`, macOS `~/Cisco Packet Tracer <ver>`, Linux `~/pt`. App bundle under `/Applications/Cisco Packet Tracer/` | High | Cisco's own help, but written for 8.2.0. Confirm the path for 9.0 |
| S2 | netpilot.io PT download page; fileion.com mac page | PT 9.0 for macOS is an x86-64 build that runs on Apple Silicon through Rosetta 2 | Low | Third-party pages. Confirm with `file` on the binary |
| S3 | Cisco Community thread 5014598 | macOS 10.14+, amd64 CPU | Low | Forum answer about an older release |
| S4 | qtbase `dev`, `src/plugins/platforms/cocoa/qcocoaaccessibilityelement.mm` | `accessibilityIdentifier` returns `QAccessibleBridgeUtils::accessibleId(iface)`. `accessibilityPerformAction` maps AX actions to Qt actions | High | Primary source |
| S5 | qtbase `5.15` and `6.2`, same file | No `accessibilityIdentifier` implementation. `accessibilityPerformAction` is present | High, with a caveat | Absence was reported by an extraction tool. Grep the raw file before relying on it |
| S6 | Qt blog, "The Curious Case of the Responsible Process" | TCC permissions belong to the *responsible* process, which is the GUI app at the top of the launch chain. Children inherit it | High | Qt engineers, with a documented experiment |
| S7 | Apple Developer Forums thread 805245 | Inheritance can fail for some launch methods (Swift parent → Python child) | Medium | A single report, unresolved |
| S8 | nonstrict.eu, "A look at ScreenCaptureKit on macOS Sonoma" | `SCScreenshotManager` (macOS 14) replaces `CGWindowListCreateImage`, which is deprecated. Both need Screen Recording | Medium | Experienced vendor blog. Matches Apple's deprecation notes |
| S9 | pyobjc GitHub issue #590 | Working pyobjc code for an SCK screenshot. Completion handlers only run while the process stays alive | Medium | Community code that worked for its authors |
| S10 | PyPI `pyobjc-framework-ScreenCaptureKit` | The wrapper exists and needs Python ≥ 3.10 | High | Package index |
| S11 | This repo: `EXTENSION/script-engine/main.js:44-129`, `bridge_token.py:40-53`, `file_bridge.py`, `deploy_executor.py:19-31`, `infrastructure/ui/*` | Where the OS assumptions live (see `topics/pt-on-macos.md` §3) | High | Primary source, read on 2026-10-10 at `bcb2ef3` |

**Do not cite** S2 or S3 for any number. They only motivate a check.

## Lookup

| Looking for | Go to |
|---|---|
| Where PT keeps its user folder on each OS | `topics/pt-on-macos.md` §1 |
| Whether PT runs natively on Apple Silicon | `topics/pt-on-macos.md` §2 |
| Why the file mailbox cannot work on macOS today | `topics/pt-on-macos.md` §3 |
| Whether Qt exposes objectName paths to macOS Accessibility | `topics/pt-on-macos.md` §4 |
| Which permission an API needs, and which app gets it | `topics/macos-ui-automation.md` §1 |
| Finding PT's windows | `topics/macos-ui-automation.md` §2 |
| Capturing a covered window | `topics/macos-ui-automation.md` §3 |
| Clicking without moving the cursor | `topics/macos-ui-automation.md` §4 |
| Points versus pixels | `topics/macos-ui-automation.md` §5 |
| UIA call → AX call, one by one | `topics/macos-ui-automation.md` §6 |
| The open questions PHASE-00 answers | `SYNTHESIS.md` §9 |

## Reading rule

Reach a note through the lookup table and read only the section it names.
`SYNTHESIS.md` is the one document to read alongside `PLAN/INDEX.md`.
