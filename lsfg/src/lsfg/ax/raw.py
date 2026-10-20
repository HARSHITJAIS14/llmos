"""Thin PyObjC wrappers over the AX C API (implementation.md §6.1).

Every AX call is a synchronous round trip to the target app's main thread. The cost is
the number of calls, not Python (bridge 0.96 µs vs 15–1,228 µs per call), so every call
goes through here: counted, timed, given a timeout, and returning (err, value) so a caller
can tell "absent" from "busy" from "gone". Add attributes to a batch freely; never add calls.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import objc
import ApplicationServices as AS
from CoreFoundation import CFEqual, CFHash

OK = 0
FAILURE = -25200
ILLEGAL_ARGUMENT = -25201
INVALID_UI_ELEMENT = -25202
CANNOT_COMPLETE = -25204
ATTRIBUTE_UNSUPPORTED = -25205
ACTION_UNSUPPORTED = -25206
NOTIFICATION_UNSUPPORTED = -25207
NOT_IMPLEMENTED = -25208
API_DISABLED = -25211
NO_VALUE = -25212
PARAM_ATTR_UNSUPPORTED = -25213

# "Not there" answers. Everything else non-zero is a transport problem (busy, gone, no permission).
ABSENT = frozenset({FAILURE, ATTRIBUTE_UNSUPPORTED, ACTION_UNSUPPORTED, NOT_IMPLEMENTED,
                    NO_VALUE, PARAM_ATTR_UNSUPPORTED})

DEFAULT_TIMEOUT = 0.5
MIN_TIMEOUT = 0.05

_T_POINT = AS.kAXValueCGPointType
_T_SIZE = AS.kAXValueCGSizeType
_T_RECT = AS.kAXValueCGRectType
_T_RANGE = AS.kAXValueCFRangeType
_T_ERROR = AS.kAXValueAXErrorType


class Stats:
    """Per-observe counters. `calls` is the number to trust: it has no timing noise."""
    __slots__ = ("calls", "seconds", "timeouts")

    def __init__(self) -> None:
        self.calls = 0
        self.seconds = 0.0
        self.timeouts = 0

    def reset(self) -> None:
        self.calls = 0
        self.seconds = 0.0
        self.timeouts = 0


STATS = Stats()
_APP_REFS: dict[int, Any] = {}


def _prep(ref: Any, timeout: float) -> None:
    # Local call, no IPC. Without it one wedged app blocks a read for the 6 s default.
    try:
        AS.AXUIElementSetMessagingTimeout(ref, max(MIN_TIMEOUT, min(float(timeout), DEFAULT_TIMEOUT)))
    except Exception:
        pass


def _done(t0: float, err: int) -> None:
    STATS.calls += 1
    STATS.seconds += time.perf_counter() - t0
    if err == CANNOT_COMPLETE:
        STATS.timeouts += 1


def trusted() -> bool:
    return bool(AS.AXIsProcessTrusted())


def app_element(pid: int) -> Any:
    ref = _APP_REFS.get(pid)
    if ref is None:
        ref = AS.AXUIElementCreateApplication(pid)
        _APP_REFS[pid] = ref
    return ref


def forget_app(pid: int) -> None:
    _APP_REFS.pop(pid, None)


def system_wide() -> Any:
    return AS.AXUIElementCreateSystemWide()


def is_ref(v: Any) -> bool:
    return v is not None and type(v).__name__ == "AXUIElementRef"


def cf_key(ref: Any) -> int:
    return int(CFHash(ref))


def cf_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    try:
        return bool(CFEqual(a, b))
    except Exception:
        return False


def decode(v: Any) -> Any:
    """Turn one AX value into plain Python. Error placeholders become None (never a value)."""
    if v is None or v is objc.NULL:
        return None
    tname = type(v).__name__
    if tname == "AXUIElementRef":
        return v
    if tname == "AXValueRef":
        try:
            t = AS.AXValueGetType(v)
        except Exception:
            return None
        if t == _T_ERROR:
            return None
        try:
            ok, s = AS.AXValueGetValue(v, t, None)
        except Exception:
            return None
        if not ok:
            return None
        if t == _T_POINT:
            return (float(s.x), float(s.y))
        if t == _T_SIZE:
            return (float(s.width), float(s.height))
        if t == _T_RECT:
            return (float(s.origin.x), float(s.origin.y), float(s.size.width), float(s.size.height))
        if t == _T_RANGE:
            if isinstance(s, tuple):
                return (int(s[0]), int(s[1]))
            return (int(s.location), int(s.length))
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return str(v)
    if hasattr(v, "absoluteString"):                      # NSURL
        try:
            return str(v.absoluteString())
        except Exception:
            return None
    if hasattr(v, "timeIntervalSince1970"):               # NSDate
        try:
            return datetime.fromtimestamp(float(v.timeIntervalSince1970())).astimezone().isoformat()
        except Exception:
            return None
    if hasattr(v, "objectAtIndex_") and hasattr(v, "count"):  # NSArray
        try:
            return [x for x in (decode(i) for i in v) if x is not None]
        except Exception:
            return None
    if hasattr(v, "string") and callable(getattr(v, "string")):  # NSAttributedString
        try:
            return str(v.string())
        except Exception:
            return None
    return None


def batch(ref: Any, attrs: list[str], timeout: float = DEFAULT_TIMEOUT) -> tuple[int, dict[str, Any]]:
    """One IPC for many attributes. Missing attributes are left out of the dict."""
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, values = AS.AXUIElementCopyMultipleAttributeValues(ref, attrs, 0, None)  # options MUST be 0
    except Exception:
        err, values = FAILURE, None
    _done(t0, err)
    if err != OK:
        return err, {}
    if values is None:
        return FAILURE, {}
    values = list(values)
    if len(values) != len(attrs):
        return FAILURE, {}
    out: dict[str, Any] = {}
    for name, raw_value in zip(attrs, values):
        d = decode(raw_value)
        if d is not None:
            out[name] = d
    return OK, out


def attr(ref: Any, name: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, Any]:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, value = AS.AXUIElementCopyAttributeValue(ref, name, None)
    except Exception:
        err, value = FAILURE, None
    _done(t0, err)
    return err, (decode(value) if err == OK else None)


def actions(ref: Any, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, list[str]]:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, names = AS.AXUIElementCopyActionNames(ref, None)
    except Exception:
        err, names = FAILURE, None
    _done(t0, err)
    if err != OK or not names:
        return err, []
    return OK, [str(n) for n in names]


def settable(ref: Any, name: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, bool]:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, ok = AS.AXUIElementIsAttributeSettable(ref, name, None)
    except Exception:
        err, ok = FAILURE, False
    _done(t0, err)
    return err, bool(ok) if err == OK else False


def set_attr(ref: Any, name: str, value: Any, timeout: float = DEFAULT_TIMEOUT) -> int:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err = AS.AXUIElementSetAttributeValue(ref, name, value)
    except Exception:
        err = FAILURE
    _done(t0, err)
    return int(err)


def perform(ref: Any, action: str, timeout: float = DEFAULT_TIMEOUT) -> int:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err = AS.AXUIElementPerformAction(ref, action)
    except Exception:
        err = FAILURE
    _done(t0, err)
    return int(err)


def hit_test(app_ref: Any, x: float, y: float, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, Any]:
    _prep(app_ref, timeout)
    t0 = time.perf_counter()
    try:
        err, el = AS.AXUIElementCopyElementAtPosition(app_ref, float(x), float(y), None)
    except Exception:
        err, el = FAILURE, None
    _done(t0, err)
    return err, (el if err == OK else None)


def count(ref: Any, name: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, int]:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, n = AS.AXUIElementGetAttributeValueCount(ref, name, None)
    except Exception:
        err, n = FAILURE, 0
    _done(t0, err)
    return err, int(n or 0) if err == OK else 0


def slice_values(ref: Any, name: str, index: int, n: int, timeout: float = DEFAULT_TIMEOUT) -> tuple[int, list]:
    _prep(ref, timeout)
    t0 = time.perf_counter()
    try:
        err, values = AS.AXUIElementCopyAttributeValues(ref, name, index, n, None)
    except Exception:
        err, values = FAILURE, None
    _done(t0, err)
    if err != OK or values is None:
        return err, []
    return OK, [x for x in (decode(v) for v in values) if x is not None]


def pid_of(ref: Any) -> int | None:
    try:
        err, pid = AS.AXUIElementGetPid(ref, None)
    except Exception:
        return None
    return int(pid) if err == OK else None


def make_range(location: int, length: int) -> Any:
    return AS.AXValueCreate(_T_RANGE, (int(location), int(length)))


def make_point(x: float, y: float) -> Any:
    from Quartz import CGPointMake
    return AS.AXValueCreate(_T_POINT, CGPointMake(float(x), float(y)))


def bounds_of(ref: Any) -> tuple[float, float, float, float] | None:
    err, a = batch(ref, ["AXPosition", "AXSize"])
    pos, size = a.get("AXPosition"), a.get("AXSize")
    if err != OK or pos is None or size is None:
        return None
    return (pos[0], pos[1], size[0], size[1])
