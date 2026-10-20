"""Capabilities in the codex vocabulary, computed lazily (implementation.md §6.5).

Rules are an exact port of agent-desktop crates/macos/src/tree/action_list.rs, because the
71 laws were measured with them. AXUIElementIsAttributeSettable has no batch form, so the
settable probes run only when a rule actually needs them (usually < 10 nodes per step).
"""
from __future__ import annotations

from ..types import Node
from . import raw

PRIMARY_ACTIVATION = ("AXPress", "AXOpen", "AXConfirm")
TOGGLE_ROLES = frozenset({"checkbox", "radiobutton", "switch"})
SELECT_BY_SELECTION = frozenset({"row", "treeitem", "cell", "listitem", "option", "tab"})
INTERACTIVE_ROLES = frozenset({
    "button", "cell", "checkbox", "colorwell", "combobox", "dockitem", "incrementor", "link",
    "listbox", "menubutton", "menuitem", "option", "radiobutton", "slider", "switch", "tab",
    "textfield", "treeitem",
})
VALUE_ROLES = frozenset({"textfield", "combobox", "slider", "incrementor", "checkbox",
                         "radiobutton", "switch", "colorwell", "scrollbar", "handle"})
FOCUS_ROLES = INTERACTIVE_ROLES | {"table", "outline", "list", "browser", "webarea",
                                   "scrollarea", "group", "row"}
EXPANDABLE = frozenset({"combobox", "menubutton", "treeitem", "disclosure"})
EXPAND_ROLES = EXPANDABLE | {"group", "outline", "row", "browser", "table", "list", "cell"}
INPUT_ROLES = frozenset({"textfield", "combobox", "slider", "incrementor", "checkbox",
                         "radiobutton", "switch", "colorwell"})
TEXT_ROLES = frozenset({"textfield", "combobox"})
CONTAINER_ROLES = frozenset({"list", "table", "outline", "grid", "browser", "scrollarea",
                             "webarea", "window", "sheet", "dialog", "application"})
SCROLL_PAGE_ACTIONS = ("AXScrollUpByPage", "AXScrollDownByPage", "AXScrollLeftByPage",
                       "AXScrollRightByPage")
GECKO_INTERACTIVE = frozenset({"button", "link", "checkbox", "radiobutton", "switch", "combobox",
                               "textfield", "treeitem", "menubutton"})

CAP_NAMES = ("Click", "Toggle", "RightClick", "ScrollTo", "Scroll", "SetValue", "Select",
             "SetFocus", "TypeText", "Expand", "Collapse")


def ensure_actions(node: Node) -> frozenset[str]:
    if node.actions is None:
        if node.ref is None:
            node.actions = frozenset()
        else:
            err, names = raw.actions(node.ref)
            node.actions = frozenset(names) if err == raw.OK else frozenset()
    return node.actions


def settable(node: Node, attribute: str) -> bool:
    key = "settable:" + attribute
    if key in node.caps:
        return node.caps[key]
    ok = False
    if node.ref is not None and not node.caps_preset:
        err, ok = raw.settable(node.ref, attribute)
        ok = err == raw.OK and ok
    node.caps[key] = ok
    return ok


def cap(node: Node, name: str) -> bool:
    if node.caps_preset:
        return bool(node.caps.get(name, False))
    if name in node.caps:
        return node.caps[name]
    acts = ensure_actions(node)
    role = node.role
    if name == "Click":
        result = any(a in acts for a in PRIMARY_ACTIVATION) or (
            role in SELECT_BY_SELECTION and settable(node, "AXSelected"))
    elif name == "Toggle":
        result = role in TOGGLE_ROLES and cap(node, "Click")
    elif name == "RightClick":
        result = "AXShowMenu" in acts and role not in ("combobox", "menubutton")
    elif name == "ScrollTo":
        result = "AXScrollToVisible" in acts
    elif name == "Scroll":
        result = any(a in acts for a in SCROLL_PAGE_ACTIONS) or bool(node.caps.get("_scrollbars"))
    elif name == "SetValue":
        result = ("AXIncrement" in acts or "AXDecrement" in acts
                  or (role in VALUE_ROLES and settable(node, "AXValue")))
    elif name == "Select":
        result = role in ("list", "table", "outline") or (
            role == "combobox" and settable(node, "AXValue"))
    elif name == "SetFocus":
        result = role in FOCUS_ROLES and settable(node, "AXFocused")
    elif name == "TypeText":
        result = role in TEXT_ROLES and settable(node, "AXSelectedText")
    elif name in ("Expand", "Collapse"):
        result = ("AXPress" in acts and role in EXPANDABLE) or (
            role in EXPAND_ROLES and settable(node, "AXExpanded"))
    else:
        result = False
    node.caps[name] = result
    return result


def clickable(node: Node, framework: str) -> bool:
    """Can a press activate it? No settable probes (cheap). Never counts AXShowMenu alone (LAW-ACT-6)."""
    if framework == "gecko":                               # LAW-ACT-5: Firefox puts Click on everything
        return node.role in GECKO_INTERACTIVE
    if node.role in CONTAINER_ROLES:
        return False
    if node.caps_preset:
        return cap(node, "Click") or cap(node, "Toggle") or (
            cap(node, "Expand") and node.role in EXPANDABLE)
    acts = ensure_actions(node)
    return any(a in acts for a in PRIMARY_ACTIVATION)


def interactive(node: Node, framework: str) -> bool:
    """For the digest and candidate lists: clickable, or an input by role (checked lazily later)."""
    if node.role in INPUT_ROLES and not node.caps_preset:
        return True
    if node.role == "unknown":                             # LAW-ACT-12
        return clickable(node, framework)
    if node.caps_preset and node.role in INPUT_ROLES:
        return cap(node, "SetValue") or cap(node, "TypeText") or cap(node, "SetFocus") or clickable(node, framework)
    return clickable(node, framework)


def typeable(node: Node, stack: str) -> bool:
    """AppKit textfields without SetFocus are labels (LAW-ACT-8); web fields expose TypeText (ACT-9)."""
    if node.role not in TEXT_ROLES:
        return False
    if "secure" in node.states or "readonly" in node.states:
        return False
    if stack == "web":
        return cap(node, "TypeText") or cap(node, "SetFocus")
    return cap(node, "SetFocus")


def actionable(node: Node, framework: str) -> bool:
    """Disabled controls keep Click in most stacks; check the state (LAW-ACT-7)."""
    if "disabled" in node.states:
        return False
    if framework in ("webkit_native", "qt") and node.role == "button":
        return cap(node, "Click")
    return True


def preset_from_actions(node: Node, available_actions: list[str]) -> None:
    """Fixtures: agent-desktop already computed the capabilities."""
    node.caps_preset = True
    node.actions = frozenset()
    for n in CAP_NAMES:
        node.caps[n] = n in available_actions
