from lsfg.ax.normalize import checked_value, coerce_value, norm, normalize_role, states_from


def test_role_map_matches_agent_desktop():
    assert normalize_role("AXTextArea") == "textfield"
    assert normalize_role("AXSearchField") == "textfield"
    assert normalize_role("AXPopUpButton") == "combobox"
    assert normalize_role("AXOutlineRow") == "treeitem"
    assert normalize_role("AXGenericElement") == "group"
    assert normalize_role("AXMenuBarItem") == "menuitem"
    assert normalize_role("AXCustomThing") == "unknown"
    assert normalize_role("AXButton", "AXCloseButton") == "button"
    assert normalize_role("AXGroup", "AXLandmarkMain") == "main"
    assert normalize_role("AXCheckBox", "AXToggleButton") == "checkbox"
    assert normalize_role("AXButton", "AXToggleButton") == "button"
    assert normalize_role("AXTextField", "AXSecureTextField") == "textfield"


def test_norm_strips_invisible_and_collapses():                 # LAW-ID-10
    assert norm("‎WhatsApp") == "WhatsApp"
    assert norm("  a​ b⁦c⁩  ") == "a bc"
    assert norm("7:05 PM") == "7:05 PM"
    assert norm(None) == ""


def test_toggle_value_semantics():                              # LAW-TXT-10
    assert checked_value("1") is True
    assert checked_value("0") is False
    assert checked_value("Dark") is None
    assert checked_value(True) is True


def test_states_and_values():
    s = states_from({"AXEnabled": False, "AXFocused": True}, "checkbox", None, "1")
    assert {"disabled", "focused", "checked"} <= s
    assert "secure" in states_from({}, "textfield", "AXSecureTextField", None)
    v, n = coerce_value("x" * 5000)
    assert len(v) == 2000 and n == 5000
