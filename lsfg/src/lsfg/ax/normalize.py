"""Roles, names, states, values, and text normalization (implementation.md §6.4).

The role map is an exact port of agent-desktop crates/macos/src/tree/roles.rs. The codex
laws were measured in that vocabulary, so a different mapping would silently break them.
"""
from __future__ import annotations

import unicodedata
from typing import Any

ROLE_MAP: dict[str, str] = {
    "AXApplication": "application", "AXButton": "button", "AXMenuButton": "menubutton",
    "AXTextField": "textfield", "AXTextArea": "textfield", "AXSearchField": "textfield",
    "AXSecureTextField": "textfield", "AXCheckBox": "checkbox", "AXSwitch": "switch",
    "AXToggle": "switch", "AXLink": "link", "AXMenuItem": "menuitem", "AXMenuBarItem": "menuitem",
    "AXRadioButton": "radiobutton", "AXTab": "tab", "AXTabGroup": "tablist", "AXSlider": "slider",
    "AXValueIndicator": "handle", "AXComboBox": "combobox", "AXPopUpButton": "combobox",
    "AXOutlineRow": "treeitem", "AXRow": "row", "AXCell": "cell", "AXColumn": "column",
    "AXWindow": "window", "AXSheet": "sheet", "AXDialog": "dialog", "AXGroup": "group",
    "AXGenericElement": "group", "AXSplitGroup": "group", "AXRadioGroup": "radiogroup",
    "AXToolbar": "toolbar", "AXStaticText": "statictext", "AXImage": "image", "AXTable": "table",
    "AXList": "list", "AXOutline": "outline", "AXScrollArea": "scrollarea",
    "AXScrollBar": "scrollbar", "AXSplitter": "splitter", "AXSeparator": "separator",
    "AXMenu": "menu", "AXMenuBar": "menu", "AXIncrementor": "incrementor",
    "AXStepper": "incrementor", "AXDisclosureTriangle": "disclosure",
    "AXProgressIndicator": "progressbar", "AXBusyIndicator": "progressbar",
    "AXColorWell": "colorwell", "AXWebArea": "webarea", "AXBrowser": "browser", "AXGrid": "grid",
    "AXHandle": "handle", "AXPopover": "popover", "AXDockItem": "dockitem", "AXRuler": "ruler",
    "AXRulerMarker": "rulermarker", "AXTimeField": "timefield", "AXDateField": "datefield",
    "AXHelpTag": "helptag", "AXMatte": "matte", "AXDrawer": "drawer", "AXLayoutArea": "layoutitem",
    "AXLayoutItem": "layoutitem", "AXLevelIndicator": "levelindicator",
    "AXRelevanceIndicator": "relevanceindicator", "AXDocument": "document",
    "AXHeading": "heading", "AXParagraph": "paragraph", "AXStatus": "status",
    "AXToolTip": "tooltip",
}

SUBROLE_MAP: dict[str, str] = {
    "AXApplicationAlert": "alert", "AXApplicationAlertDialog": "alertdialog",
    "AXApplicationDialog": "dialog", "AXApplicationLog": "log", "AXApplicationMarquee": "marquee",
    "AXApplicationStatus": "status", "AXApplicationTimer": "timer",
    "AXDocumentArticle": "article", "AXDocumentMath": "math", "AXDocumentNote": "note",
    "AXDocumentRegion": "region", "AXLandmarkBanner": "banner",
    "AXLandmarkComplementary": "complementary", "AXLandmarkContentInfo": "contentinfo",
    "AXLandmarkForm": "form", "AXLandmarkMain": "main", "AXLandmarkNavigation": "navigation",
    "AXLandmarkSearch": "search", "AXDefinition": "definition", "AXTerm": "term",
    "AXTabPanel": "tabpanel", "AXUserInterfaceTooltip": "tooltip", "AXOutlineRow": "treeitem",
    "AXTableRow": "row", "AXSecureTextField": "textfield", "AXSearchField": "textfield",
    "AXDialog": "dialog", "AXSystemDialog": "dialog", "AXCloseButton": "button",
    "AXMinimizeButton": "button", "AXZoomButton": "button", "AXToolbarButton": "button",
    "AXFullScreenButton": "button", "AXSortButton": "button", "AXToggle": "switch",
    "AXSwitch": "switch", "AXContentList": "list", "AXDefinitionList": "list",
    "AXDescriptionList": "list", "AXSeparatorDockItem": "separator",
}

TOGGLE_ROLES = frozenset({"checkbox", "radiobutton", "switch"})

# Invisible format characters seen in WhatsApp (57), Word (18) and Safari (4) (LAW-ID-10).
_INVISIBLE = dict.fromkeys(
    map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩"
             "​‌‍⁠﻿­"),
    None,
)

MAX_VALUE_CHARS = 2000


def normalize_role(ax_role: str | None, ax_subrole: str | None = None) -> str:
    if ax_subrole:
        if ax_subrole == "AXToggleButton":
            base = ROLE_MAP.get(ax_role or "", "unknown")
            return base if base in TOGGLE_ROLES else "button"
        mapped = SUBROLE_MAP.get(ax_subrole)
        if mapped:
            return mapped
    return ROLE_MAP.get(ax_role or "", "unknown")


def norm(s: Any) -> str:
    """Strip invisible format chars, NFC, collapse whitespace. Use on BOTH sides of a compare."""
    if s is None:
        return ""
    text = str(s).translate(_INVISIBLE)
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def fold(s: Any) -> str:
    return norm(s).casefold()


def truthy(v: Any) -> bool:
    return v is not None and bool(v)


def falsy(v: Any) -> bool:
    return v is not None and not bool(v)


def checked_value(v: Any) -> bool | None:
    """Toggle state lives in value as '0'/'1' (LAW-TXT-10)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v) if v in (0, 1) else None
    if isinstance(v, str):
        s = v.strip()
        if s == "1":
            return True
        if s == "0":
            return False
    return None


def coerce_value(v: Any) -> tuple[str | int | float | bool | None, int]:
    if v is None:
        return None, 0
    if isinstance(v, bool):
        return v, 0
    if isinstance(v, (int, float)):
        return v, 0
    if isinstance(v, str):
        n = len(v)
        return (v if n <= MAX_VALUE_CHARS else v[:MAX_VALUE_CHARS]), n
    return None, 0


def states_from(attrs: dict[str, Any], role: str, subrole: str | None, value: Any) -> set[str]:
    s: set[str] = set()
    if falsy(attrs.get("AXEnabled")):
        s.add("disabled")
    if truthy(attrs.get("AXFocused")):
        s.add("focused")
    if truthy(attrs.get("AXSelected")):
        s.add("selected")
    if truthy(attrs.get("AXExpanded")):
        s.add("expanded")
    if truthy(attrs.get("AXHidden")):
        s.add("hidden")
    if truthy(attrs.get("AXElementBusy")):
        s.add("busy")
    if truthy(attrs.get("AXModal")):
        s.add("modal")
    if truthy(attrs.get("AXRequired")):
        s.add("required")
    if subrole == "AXSecureTextField":
        s.add("secure")
    if role in TOGGLE_ROLES and checked_value(value):
        s.add("checked")
    return s


def base_name(attrs: dict[str, Any], role: str, title_text: str = "") -> str:
    """agent-desktop's name order minus the child label (added after the walk):
    AXLabelValue → AXTitleUIElement text → AXTitle → statictext value → AXDescription → placeholder."""
    for candidate in (
        attrs.get("AXLabelValue"),
        title_text,
        attrs.get("AXTitle"),
        attrs.get("AXValue") if role == "statictext" else None,
        attrs.get("AXDescription"),
    ):
        text = norm(candidate) if isinstance(candidate, str) else ""
        if text:
            return text
    return ""


def placeholder_of(attrs: dict[str, Any]) -> str:
    p = attrs.get("AXPlaceholderValue")
    return norm(p) if isinstance(p, str) else ""
