"""정책 레지스트리 — 플러그인 방식 등록."""
from __future__ import annotations

from typing import Callable

from agents.protocol import PolicyFn

_DISPATCH_POLICIES: dict[str, PolicyFn] = {}


def register_dispatch(name: str) -> Callable[[PolicyFn], PolicyFn]:
    def deco(fn: PolicyFn) -> PolicyFn:
        _DISPATCH_POLICIES[name] = fn
        return fn
    return deco


def get_dispatch(name: str) -> PolicyFn:
    if name not in _DISPATCH_POLICIES:
        raise KeyError(f"unknown dispatch policy: {name}")
    return _DISPATCH_POLICIES[name]


def list_dispatch() -> list[str]:
    return sorted(_DISPATCH_POLICIES)
