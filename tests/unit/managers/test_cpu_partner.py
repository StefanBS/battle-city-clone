from dataclasses import replace

import pytest

from src.core.tile import TileType
from src.managers.cpu_partner import CpuPartnerInput
from src.managers.world_view import EnemyView, PlayerView, WorldView
from src.utils.constants import SUB_TILE_SIZE, Direction

GRID = 26
CPU_ID = 2


def cell(n: int) -> float:
    """Pixel coordinate of sub-tile ``n``."""
    return float(n * SUB_TILE_SIZE)


def make_view(
    own: tuple[int, int, Direction] | None = (12, 12, Direction.UP),
    enemies: list[tuple[int, int]] | None = None,
) -> WorldView:
    """Build an open-field World View with the CPU Partner at sub-tile ``own``."""
    players: list[PlayerView] = [
        PlayerView(player_id=1, x=cell(0), y=cell(24), direction=Direction.UP)
    ]
    if own is not None:
        gx, gy, facing = own
        players.append(
            PlayerView(player_id=CPU_ID, x=cell(gx), y=cell(gy), direction=facing)
        )
    return WorldView(
        tile_size=SUB_TILE_SIZE,
        tiles=tuple(tuple(TileType.EMPTY for _ in range(GRID)) for _ in range(GRID)),
        enemies=tuple(
            EnemyView(enemy_id=i, x=cell(gx), y=cell(gy), direction=Direction.DOWN)
            for i, (gx, gy) in enumerate(enemies or [])
        ),
        players=tuple(players),
        own_player_id=CPU_ID,
    )


@pytest.fixture
def cpu() -> CpuPartnerInput:
    return CpuPartnerInput()


class TestCpuPartnerHunt:
    def test_heads_for_nearest_of_several_enemies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 0), (18, 12)]))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    @pytest.mark.parametrize(
        ("enemy", "expected"),
        [
            ((16, 2), Direction.RIGHT),  # 4 cells right, 10 up: line up the column
            ((8, 2), Direction.LEFT),
            ((2, 16), Direction.DOWN),  # 10 left, 4 down: line up the row
            ((22, 8), Direction.UP),
        ],
    )
    def test_lines_up_on_shorter_axis_first(self, cpu, enemy, expected) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[enemy]))
        assert cpu.get_movement_direction() == expected.delta
        assert cpu.consume_shoot() is False

    def test_keeps_target_when_another_enemy_comes_closer(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        # Enemy 1 appears right next to it; it keeps hunting enemy 0.
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (16, 12)]))
        assert cpu.consume_shoot() is True
        assert cpu.get_movement_direction() == (0, 0)

    def test_retargets_nearest_when_target_dies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (20, 12)]))
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2), (20, 12)])
        cpu.observe(replace(view, enemies=view.enemies[1:]))
        assert cpu.get_movement_direction() == Direction.RIGHT.delta

    def test_stands_still_without_enemies(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[]))
        assert cpu.get_movement_direction() == (0, 0)
        assert cpu.consume_shoot() is False

    def test_idle_when_own_tank_is_dead(self, cpu) -> None:
        view = make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)])
        dead = replace(view.players[1], alive=False)
        cpu.observe(replace(view, players=(view.players[0], dead)))
        assert cpu.get_movement_direction() == (0, 0)
        assert cpu.consume_shoot() is False


class TestCpuPartnerFiring:
    def test_fires_and_holds_position_when_lined_up_and_facing(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        assert cpu.consume_shoot() is True
        assert cpu.get_movement_direction() == (0, 0)

    def test_fires_within_half_a_tile_of_alignment(self, cpu) -> None:
        # One sub-tile (half a tank) off the column still counts as lined up.
        cpu.observe(make_view(own=(12, 12, Direction.RIGHT), enemies=[(20, 13)]))
        assert cpu.consume_shoot() is True

    def test_turns_to_face_enemy_before_firing(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.LEFT), enemies=[(12, 2)]))
        assert cpu.consume_shoot() is False
        assert cpu.get_movement_direction() == Direction.UP.delta

    def test_shoot_request_is_consumed_once(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        cpu.consume_shoot()
        assert cpu.consume_shoot() is False

    def test_clear_pending_shoot_drops_request(self, cpu) -> None:
        cpu.observe(make_view(own=(12, 12, Direction.UP), enemies=[(12, 2)]))
        cpu.clear_pending_shoot()
        assert cpu.consume_shoot() is False
