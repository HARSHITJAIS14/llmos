"""Element identity: (pid, CFHash(ref)) plus short session aliases (implementation.md §6.2).

Measured: CFHash and CFEqual were stable for 393/393 nodes across two walks of 5 apps
(native, WKWebView, Electron); repr(ref) was not (it holds a memory address). arc-cua's
repr-based ids are why its settle loop never saw two equal frames (reasoning.md B1–B3).
"""
from __future__ import annotations

from typing import Any

from . import raw

MAX_ALIASES = 200_000


class AliasTable:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int], list[str]] = {}
        self._ref: dict[str, Any] = {}
        self._pid: dict[str, int] = {}
        self._n = 0
        self.collisions = 0

    def alias(self, pid: int, ref: Any) -> tuple[str, tuple[int, int]]:
        key = (pid, raw.cf_key(ref))
        for a in self._by_key.get(key, ()):
            old = self._ref.get(a)
            if old is not None and raw.cf_equal(old, ref):
                self._ref[a] = ref                     # keep the newest ref object
                return a, key
        if key in self._by_key:
            self.collisions += 1                       # same hash, different element
        if self._n >= MAX_ALIASES:
            self.clear()
        self._n += 1
        a = f"e{self._n}"
        self._by_key.setdefault(key, []).append(a)
        self._ref[a] = ref
        self._pid[a] = pid
        return a, key

    def ref(self, alias: str) -> Any:
        return self._ref.get(alias)

    def pid(self, alias: str) -> int | None:
        return self._pid.get(alias)

    def forget_pid(self, pid: int) -> None:
        dead = [a for a, p in self._pid.items() if p == pid]
        for a in dead:
            self._ref.pop(a, None)
            self._pid.pop(a, None)
        for k in [k for k in self._by_key if k[0] == pid]:
            del self._by_key[k]

    def clear(self) -> None:
        self._by_key.clear()
        self._ref.clear()
        self._pid.clear()

    def __len__(self) -> int:
        return len(self._ref)
