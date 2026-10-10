"""CGImage bytes → tightly packed top-down B,G,R,A (PLAN/phases/PHASE-04.md).

Measured on the Mac (PREVIOUS_WORK 2.4 #8): CGWindowListCreateImage and SCK give
bitmap info 8194 (32-bit little-endian, premultiplied alpha first = B,G,R,A in
memory) with padded rows (5632 bytes for 1400 px); `screencapture`'s PNG read back
through ImageIO gives info 3 (R,G,B,A). Wrong padding shears the image; a wrong
order swaps colours. Checked byte-exact on a synthetic 3x2 image.
"""

from __future__ import annotations

import sys

import pytest

from src.packet_tracer_mcp.infrastructure.ui.backends.macos import capture as cap

# Six distinct pixels, as (B, G, R, A). Alpha 0x80 with premultiplied colours:
# it must come through untouched.
PIXELS = [(1, 2, 3, 255), (10, 20, 30, 255), (40, 50, 60, 0x80),
          (70, 80, 90, 255), (100, 110, 120, 0), (200, 210, 220, 255)]
W, H = 3, 2
EXPECTED = bytes(b for px in PIXELS for b in px)


def encode(layout: str, pad: int) -> tuple[bytes, int]:
    """Memory bytes for `layout` (e.g. "ARGB"), each row followed by `pad` junk bytes."""
    idx = {"B": 0, "G": 1, "R": 2, "A": 3}
    rows = []
    for y in range(H):
        row = bytearray()
        for px in PIXELS[y * W:(y + 1) * W]:
            row += bytes(px[idx[ch]] for ch in layout)
        rows.append(bytes(row) + b"\xee" * pad)
    return b"".join(rows), W * 4 + pad


LITTLE, BIG = cap.ORDER_32_LITTLE, cap.ORDER_32_BIG
FIRST = (cap.ALPHA_PREMULTIPLIED_FIRST, cap.ALPHA_FIRST, cap.ALPHA_NONE_SKIP_FIRST)
LAST = (cap.ALPHA_PREMULTIPLIED_LAST, cap.ALPHA_LAST, cap.ALPHA_NONE_SKIP_LAST)
CASES = (
    [("BGRA", LITTLE | a) for a in FIRST]
    + [("ABGR", LITTLE | a) for a in LAST]
    + [("ARGB", order | a) for order in (0, BIG) for a in FIRST]
    + [("RGBA", order | a) for order in (0, BIG) for a in LAST]
)


@pytest.mark.parametrize("layout, info", CASES)
@pytest.mark.parametrize("pad", [0, 4, 20])
def test_every_layout_and_padding_gives_exact_bgra(layout, info, pad):
    data, bpr = encode(layout, pad)
    assert cap.layout_for(info) == layout
    assert cap.to_bgra(data, W, H, bpr, info) == EXPECTED


def test_the_measured_cases():
    assert cap.layout_for(8194) == "BGRA"   # CGWindowListCreateImage / SCK
    assert cap.layout_for(3) == "RGBA"      # screencapture PNG through ImageIO


def test_a_short_buffer_is_rejected():
    data, bpr = encode("BGRA", 4)
    with pytest.raises(ValueError):
        cap.to_bgra(data[:-5], W, H, bpr, LITTLE | cap.ALPHA_PREMULTIPLIED_FIRST)


def test_rows_narrower_than_the_pixels_are_rejected():
    data, _ = encode("BGRA", 0)
    with pytest.raises(ValueError):
        cap.to_bgra(data, W, H, W * 4 - 1, LITTLE | cap.ALPHA_PREMULTIPLIED_FIRST)


@pytest.mark.skipif(sys.platform != "darwin", reason="compares with Quartz's own constants")
def test_constants_are_quartz_constants():
    Quartz = pytest.importorskip("Quartz")
    assert cap.ORDER_32_LITTLE == Quartz.kCGBitmapByteOrder32Little
    assert cap.ORDER_32_BIG == Quartz.kCGBitmapByteOrder32Big
    assert cap.ORDER_MASK == Quartz.kCGBitmapByteOrderMask
    assert cap.ALPHA_MASK == Quartz.kCGBitmapAlphaInfoMask
    assert cap.ALPHA_PREMULTIPLIED_FIRST == Quartz.kCGImageAlphaPremultipliedFirst
    assert cap.ALPHA_PREMULTIPLIED_LAST == Quartz.kCGImageAlphaPremultipliedLast
    assert cap.ALPHA_FIRST == Quartz.kCGImageAlphaFirst
    assert cap.ALPHA_LAST == Quartz.kCGImageAlphaLast
    assert cap.ALPHA_NONE_SKIP_FIRST == Quartz.kCGImageAlphaNoneSkipFirst
    assert cap.ALPHA_NONE_SKIP_LAST == Quartz.kCGImageAlphaNoneSkipLast
