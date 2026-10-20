"""Shared helpers for the M0 probes. Read-only: nothing here clicks, types, or writes to disk.
Prints counts and timings only, never UI text."""
import statistics
import time

import objc
import AppKit
import ApplicationServices as AS


def unwrap(v):
    """A missing attribute comes back as an AXValue of type kAXValueAXErrorType (5), not None."""
    if v is None or v is objc.NULL:
        return None
    try:
        if AS.AXValueGetType(v) == AS.kAXValueAXErrorType:
            return None
    except Exception:
        pass
    return v


def batch(ref, attrs):
    err, vals = AS.AXUIElementCopyMultipleAttributeValues(ref, attrs, 0, None)  # options MUST be 0
    if err != 0 or vals is None:
        return {}
    return {a: unwrap(v) for a, v in zip(attrs, list(vals))}


def pid_of(name):
    for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
        if str(a.localizedName()) == name:
            return int(a.processIdentifier())
    return None


def regular_apps():
    return [(str(a.localizedName()), int(a.processIdentifier()))
            for a in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
            if a.activationPolicy() == 0]


def timed(fn, n=3):
    samples, out = [], None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples), max(samples), out
