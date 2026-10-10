"""PT's Accessibility tree: one walk shared by the backend and `devtools/macos_probe.py`,
and the conversion of its nodes to `UiElement`s.

`walk` produces nodes in the fixture format (PLAN/INTERFACES.md §7), so recorded
fixtures and live trees take the same path through `to_element`. Every AX name
used here was exercised by the probe on PT 9.0.1 / macOS 26.5.1 first (C6,
PREVIOUS_WORK 2.4). pyobjc is imported inside the functions (C2); the
conversion is pure and runs on every OS.

Role mapping, from the PHASE-00 fixtures: AXRadioButton inside an AXTabGroup →
TAB (other radio buttons are not tabs); AXButton → BUTTON; AXCheckBox →
CHECKBOX (the Select tool, Config/Services sections, check boxes); AXRow and
AXCell → LIST_ITEM; AXTextField and AXTextArea → EDIT; AXScrollBar → SCROLLBAR;
AXStaticText → STATIC; AXWindow → WINDOW; anything else → OTHER.
"""

from __future__ import annotations

from typing import Callable

from ...backend import Role, UiElement

MAX_DEPTH = 40
MAX_NODES = 5000
VALUE_CAP = 200

_ROLES = {
    "AXButton": Role.BUTTON, "AXCheckBox": Role.CHECKBOX, "AXRow": Role.LIST_ITEM,
    "AXCell": Role.LIST_ITEM, "AXTextField": Role.EDIT, "AXTextArea": Role.EDIT,
    "AXScrollBar": Role.SCROLLBAR, "AXStaticText": Role.STATIC, "AXWindow": Role.WINDOW,
}


# -- pure: nodes → elements --------------------------------------------------------

def role_of(ax_role: str, parent_role: str = "") -> Role:
    if ax_role == "AXRadioButton":
        return Role.TAB if parent_role == "AXTabGroup" else Role.OTHER
    return _ROLES.get(ax_role, Role.OTHER)


def _rect(frame) -> tuple[int, int, int, int]:
    if not frame:
        return (0, 0, 0, 0)
    x, y, w, h = frame
    return (round(x), round(y), round(x + w), round(y + h))


def _offscreen(frame, window_frame) -> bool:
    """Zero size, no frame, or no overlap with the window."""
    if not frame or frame[2] <= 0 or frame[3] <= 0:
        return True
    if not window_frame:
        return False
    x, y, w, h = frame
    wx, wy, ww, wh = window_frame
    return x >= wx + ww or y >= wy + wh or x + w <= wx or y + h <= wy


def to_element(node: dict, window_frame=None, parent_role: str = "", raw: object = None) -> UiElement:
    """One fixture-format node → UiElement. `raw` defaults to the node itself."""
    name = node.get("title") or node.get("description") or ""
    if not name and node.get("role") == "AXStaticText":
        name = node.get("value") or ""
    frame = node.get("frame")
    return UiElement(
        raw=node if raw is None else raw,
        name=name,
        ident=node.get("identifier") or "",
        role=role_of(node.get("role", ""), parent_role),
        offscreen=_offscreen(frame, window_frame),
        bounds=_rect(frame),
    )


def elements_from_tree(tree: dict, raw: Callable[[dict], object] | None = None) -> list[UiElement]:
    """Every node below the window, parents before children (UIA's order), as
    UiElements. `raw(node)` picks each element's backend handle."""
    window_frame = tree.get("frame")
    out: list[UiElement] = []

    def visit(node: dict) -> None:
        for child in node.get("children", []):
            out.append(to_element(child, window_frame, node.get("role", ""),
                                  raw(child) if raw else None))
            visit(child)

    visit(tree)
    return out


# -- pyobjc: reading the live tree -------------------------------------------------

def _as():
    import ApplicationServices
    return ApplicationServices


def attr(el, name: str):
    """An attribute's value, or None when it is missing or the read failed."""
    err, val = _as().AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def frame(el) -> list[float] | None:
    """[x, y, width, height] in points, or None."""
    AS = _as()
    pos, size = attr(el, "AXPosition"), attr(el, "AXSize")
    if pos is None or size is None:
        return None
    ok1, p = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    ok2, s = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return [float(p.x), float(p.y), float(s.width), float(s.height)]


def value_text(val, redact: Callable[[str], str] = lambda s: s) -> str:
    if val is None:
        return ""
    if isinstance(val, (str, int, float, bool)):
        return redact(str(val))[:VALUE_CAP]
    return ""  # AXUIElement references, AXValue structs and arrays are not text


def walk(root, *, redact: Callable[[str], str] = lambda s: s, with_actions: bool = True,
         keep_el: bool = False, max_depth: int = MAX_DEPTH,
         max_nodes: int = MAX_NODES) -> tuple[dict, dict]:
    """(tree, stats). The tree is in the fixture format; `keep_el` adds each
    node's AXUIElement under "_el" (live use only, not serialisable)."""
    AS = _as()
    stats = {"nodes": 0, "max_depth": 0, "with_identifier": 0, "truncated": False}

    def node(el, depth: int) -> dict:
        stats["nodes"] += 1
        stats["max_depth"] = max(stats["max_depth"], depth)
        acts: list[str] = []
        if with_actions:
            err, names = AS.AXUIElementCopyActionNames(el, None)
            acts = [str(a) for a in (names or [])] if err == 0 else []
        ident = str(attr(el, "AXIdentifier") or "")
        if ident:
            stats["with_identifier"] += 1
        out = {
            "role": str(attr(el, "AXRole") or ""),
            "subrole": str(attr(el, "AXSubrole") or ""),
            "title": redact(str(attr(el, "AXTitle") or "")),
            "description": redact(str(attr(el, "AXDescription") or "")),
            "identifier": redact(ident),
            "value": value_text(attr(el, "AXValue"), redact),
            "frame": frame(el),
            "actions": acts,
            "children": [],
        }
        if keep_el:
            out["_el"] = el
        if depth >= max_depth:
            stats["truncated"] = True
            return out
        for child in attr(el, "AXChildren") or []:
            if stats["nodes"] >= max_nodes:
                stats["truncated"] = True
                break
            out["children"].append(node(child, depth + 1))
        return out

    return node(root, 0), stats


def perform(el, action: str) -> int:
    """AXUIElementPerformAction; returns the AX error code (0 = done)."""
    return int(_as().AXUIElementPerformAction(el, action))


def set_attr(el, name: str, value) -> int:
    """AXUIElementSetAttributeValue; returns the AX error code (0 = done)."""
    return int(_as().AXUIElementSetAttributeValue(el, name, value))
