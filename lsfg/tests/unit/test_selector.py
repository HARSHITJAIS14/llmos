import pytest

from lsfg.resolve.selector import SelectorError, fmt, id_tier, parse


@pytest.mark.parametrize("text", [
    "#WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD", "button:\"New Tab\"", "button~\"Tab\"", "textfield=\"Report.pdf\"",
    "#ChatListView_TableView>button~\"Priya\"", "row:\"Mom\"[1]", "groupdom#root", "button#\"previous day\"",
    "radiobutton#TabBarTab?isPinned=*", "focused", "@chosen", "@e12",
])
def test_round_trip(text):
    assert fmt(parse(text)) == text


def test_parts():
    s = parse('list#Chats>button~"Pri"[2]')
    assert s.scope[0].role == "list" and s.scope[0].ident == "Chats"
    assert s.target.name == "Pri" and s.target.name_mode == "contains" and s.target.nth == 2
    assert parse("groupdom#root").target.dom_id == "root"
    assert parse("groupdom#root").target.role == "group"
    assert parse("@e7").special == "alias:e7"


@pytest.mark.parametrize("bad", ["", "button:", 'button:"x', "#", "button[x]", "a b c"])
def test_errors(bad):
    with pytest.raises(SelectorError):
        parse(bad)


def test_id_tiers():                                            # LAW-ID-2, ID-3
    assert id_tier("_NS:13") == "low"
    assert id_tier(":r1a:") == "volatile"
    assert id_tier("view_42") == "volatile"
    assert id_tier("SafariWindow?IsSecure=0&UUID=6F9619FF-8B86-D011-B42D-00C04FC964FF") == "session"
    assert id_tier("WEB_BROWSER_ADDRESS_AND_SEARCH_FIELD") == "high"
