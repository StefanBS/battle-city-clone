"""Shared collection helpers."""

from __future__ import annotations

from typing import Protocol, TypeVar


class _Updatable(Protocol):
    active: bool

    def update(self, dt: float) -> None: ...


T = TypeVar("T", bound=_Updatable)


def update_and_prune(items: list[T], dt: float) -> list[T]:
    """Call ``update(dt)`` on each item and return those still ``active``."""
    for item in items:
        item.update(dt)
    return [i for i in items if i.active]
