"""Declarative menu navigation: items + callbacks, no per-screen handler boilerplate."""

from dataclasses import dataclass
from collections.abc import Callable

from src.utils.constants import MenuAction


@dataclass(frozen=True)
class MenuItem:
    label: str
    on_confirm: Callable[[], None] | None = None
    on_left: Callable[[], None] | None = None
    on_right: Callable[[], None] | None = None


class MenuController:
    """UP/DOWN cycles the cursor; CONFIRM/LEFT/RIGHT dispatch to the active item."""

    def __init__(
        self,
        items: list[MenuItem],
        on_select: Callable[[], None] | None = None,
        on_back: Callable[[], None] | None = None,
    ) -> None:
        if not items:
            raise ValueError("MenuController requires at least one MenuItem")
        self._items = items
        self._on_select = on_select
        self._on_back = on_back
        self.selection: int = 0

    @property
    def labels(self) -> list[str]:
        """Return the ordered labels of this menu's items."""
        return [item.label for item in self._items]

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
