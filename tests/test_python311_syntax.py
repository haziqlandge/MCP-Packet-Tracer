"""The code still parses on Python 3.11, the oldest version pyproject allows.

Python 3.12 (PEP 701) accepts a backslash inside an f-string's `{...}`; 3.11
rejects the whole file. A test written on the 3.13 Mac with
`f"{json.dumps('xx\\n' + s)}"` passed there and broke collection on every 3.11
CI runner (2026-10-26). From 3.12 on, `tokenize` shows what is inside an
f-string, so the check runs there; on 3.11 the file itself would fail to import.
"""

from __future__ import annotations

import io
import sys
import token
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12),
                                reason="tokenize splits f-strings from 3.12 on")


def backslashes_in_fstring_expressions(source: str) -> list[int]:
    """Lines where a backslash sits inside an f-string replacement field."""
    hits: list[int] = []
    depth: list[int] = []  # one brace counter per open f-string
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == token.FSTRING_START:
            depth.append(0)
        elif tok.type == token.FSTRING_END:
            depth.pop()
        elif depth and tok.type == token.OP and tok.string == "{":
            depth[-1] += 1
        elif depth and tok.type == token.OP and tok.string == "}":
            depth[-1] -= 1
        elif depth and depth[-1] > 0 and tok.type != token.FSTRING_MIDDLE and "\\" in tok.string:
            hits.append(tok.start[0])
    return hits


def test_the_check_finds_the_case_that_broke_ci():
    src = "x = f\"var __out={json.dumps('xx\\\\n' + s)};\"\n"
    assert backslashes_in_fstring_expressions(src) == [1]


@pytest.mark.parametrize("src", [
    "x = f'a\\nb {y}'\n",            # a backslash in the literal part is fine
    "x = f'{y!r:>10}\\n'\n",
    "x = f'{{literal}} \\t {y}'\n",
])
def test_backslashes_outside_the_expressions_are_allowed(src):
    assert backslashes_in_fstring_expressions(src) == []


def test_no_file_uses_a_backslash_inside_an_fstring_expression():
    hits = []
    for path in sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/**/*.py")]):
        for line in backslashes_in_fstring_expressions(path.read_text(encoding="utf-8")):
            hits.append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    assert hits == []
