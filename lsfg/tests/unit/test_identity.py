import Foundation

from lsfg.ax.identity import AliasTable


def test_same_element_keeps_alias():
    t = AliasTable()
    a1, k1 = t.alias(1, Foundation.NSString.stringWithString_("x"))
    a2, k2 = t.alias(1, Foundation.NSString.stringWithString_("x"))   # a new object, equal content
    assert a1 == a2 and k1 == k2
    a3, _ = t.alias(1, Foundation.NSString.stringWithString_("y"))
    assert a3 != a1
    a4, _ = t.alias(2, Foundation.NSString.stringWithString_("x"))    # another pid
    assert a4 != a1


def test_forget_pid():
    t = AliasTable()
    a, _ = t.alias(5, Foundation.NSString.stringWithString_("z"))
    t.forget_pid(5)
    assert t.ref(a) is None
