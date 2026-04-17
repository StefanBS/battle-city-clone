"""Declarative menu navigation: items + callbacks, no per-screen handler boilerplate."""

from dataclasses import dataclass
from typing import Callable, List, Optional

from src.utils.constants import MenuAction


@dataclass(frozen=True)
class MenuItem:
    label: str
    on_confirm: Optional[Callable[[], None]] = None
    on_left: Optional[Callable[[], None]] = None
    on_right: Optional[Callable[[], None]] = None


class MenuController:
    """UP/DOWN cycles the cursor; CONFIRM/LEFT/RIGHT dispatch to the active item."""

    def __init__(
        self,
        items: List[MenuItem],
        on_select: Optional[Callable[[], None]] = None,
        on_back: Optional[Callable[[], None]] = None,
    ) -> None:
        if not items:
            raise ValueError("MenuController requires at least one MenuItem")
        self._items = items
        self._on_select = on_select
        self._on_back = on_back
        self.selection: int = 0

    def reset(self) -> None:
        self.selection = 0

    def handle_action(self, action: MenuAction) -> None:
        if action in (MenuAction.UP, MenuAction.DOWN):
            step = -1 if action == MenuAction.UP else 1
            self.selection = (self.selection + step) % len(self._items)
            if self._on_select is not None:
                self._on_select()
        elif action == MenuAction.CONFIRM:
            cb = self._items[self.selection].on_confirm
            if cb is not None:
                cb()
        elif action == MenuAction.LEFT:
            cb = self._items[self.selection].on_left
            if cb is not None:
                cb()
        elif action == MenuAction.RIGHT:
            cb = self._items[self.selection].on_right
            if cb is not None:
                cb()
        elif action == MenuAction.BACK:
            if self._on_back is not None:
                self._on_back()
