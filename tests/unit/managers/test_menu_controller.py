import pytest
from unittest.mock import MagicMock

from src.managers.menu_controller import MenuController, MenuItem
from src.utils.constants import MenuAction


class TestMenuController:
    def test_requires_at_least_one_item(self):
        with pytest.raises(ValueError):
            MenuController(items=[])

    def test_initial_selection_is_zero(self):
        mc = MenuController(items=[MenuItem("a"), MenuItem("b")])
        assert mc.selection == 0

    def test_down_advances_selection(self):
        mc = MenuController(items=[MenuItem("a"), MenuItem("b"), MenuItem("c")])
        mc.handle_action(MenuAction.DOWN)
        assert mc.selection == 1

    def test_up_wraps_to_last(self):
        mc = MenuController(items=[MenuItem("a"), MenuItem("b"), MenuItem("c")])
        mc.handle_action(MenuAction.UP)
        assert mc.selection == 2

    def test_down_wraps_to_first(self):
        mc = MenuController(items=[MenuItem("a"), MenuItem("b")])
        mc.handle_action(MenuAction.DOWN)
        mc.handle_action(MenuAction.DOWN)
        assert mc.selection == 0

    def test_navigation_invokes_on_select(self):
        on_select = MagicMock()
        mc = MenuController(items=[MenuItem("a"), MenuItem("b")], on_select=on_select)
        mc.handle_action(MenuAction.DOWN)
        on_select.assert_called_once()

    def test_confirm_invokes_active_items_callback(self):
        cb_a, cb_b = MagicMock(), MagicMock()
        mc = MenuController(
            items=[MenuItem("a", on_confirm=cb_a), MenuItem("b", on_confirm=cb_b)]
        )
        mc.handle_action(MenuAction.CONFIRM)
        cb_a.assert_called_once()
        cb_b.assert_not_called()

    def test_confirm_without_callback_is_noop(self):
        mc = MenuController(items=[MenuItem("a")])
        mc.handle_action(MenuAction.CONFIRM)  # must not raise

    def test_left_and_right_dispatch_to_active_item(self):
        on_left, on_right = MagicMock(), MagicMock()
        mc = MenuController(
            items=[MenuItem("only", on_left=on_left, on_right=on_right)]
        )
        mc.handle_action(MenuAction.LEFT)
        mc.handle_action(MenuAction.RIGHT)
        on_left.assert_called_once()
        on_right.assert_called_once()

    def test_back_invokes_on_back(self):
        on_back = MagicMock()
        mc = MenuController(items=[MenuItem("a")], on_back=on_back)
        mc.handle_action(MenuAction.BACK)
        on_back.assert_called_once()

    def test_back_without_callback_is_noop(self):
        mc = MenuController(items=[MenuItem("a")])
        mc.handle_action(MenuAction.BACK)

    def test_reset_clears_selection(self):
        mc = MenuController(items=[MenuItem("a"), MenuItem("b"), MenuItem("c")])
        mc.handle_action(MenuAction.DOWN)
        mc.handle_action(MenuAction.DOWN)
        mc.reset()
        assert mc.selection == 0
