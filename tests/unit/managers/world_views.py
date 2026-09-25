"""World View builders shared by the CPU Partner and Dodge tests."""

from dataclasses import replace

from src.core.tile import TileType
from src.managers.world_view import BulletView, EnemyView, PlayerView, WorldView
from src.utils.constants import SUB_TILE_SIZE, Direction, OwnerType
from tests.conftest import tile_fields

GRID = 26
CPU_ID = 2

Cell = tuple[int, int]


def cell(n: int) -> float:
    """Pixel coordinate of sub-tile ``n``."""
    return float(n * SUB_TILE_SIZE)


def make_view(
    own: tuple[int, int, Direction] | None = (12, 12, Direction.UP),
    enemies: list[tuple[int, int]] | None = None,
    human: tuple[float, float] = (0, 24),
    tiles: dict[Cell, TileType] | None = None,
    base_cells: frozenset[Cell] = frozenset(),
    base_wall_cells: frozenset[Cell] = frozenset(),
    half_brick_cells: frozenset[Cell] = frozenset(),
) -> WorldView:
    """Build a World View with the CPU Partner at sub-tile ``own``.

    The field is open except for ``tiles``; the Human Player sits at ``human``.
    """
    players: list[PlayerView] = [
        PlayerView(
            player_id=1, x=cell(human[0]), y=cell(human[1]), direction=Direction.UP
        )
    ]
    if own is not None:
        gx, gy, facing = own
        players.append(
            PlayerView(player_id=CPU_ID, x=cell(gx), y=cell(gy), direction=facing)
        )
    return WorldView(
        tile_size=SUB_TILE_SIZE,
        **tile_fields(tiles or {}, GRID),
        base_cells=base_cells,
        base_wall_cells=base_wall_cells,
        half_brick_cells=half_brick_cells,
        enemies=tuple(
            EnemyView(enemy_id=i, x=cell(gx), y=cell(gy), direction=Direction.DOWN)
            for i, (gx, gy) in enumerate(enemies or [])
        ),
        players=tuple(players),
        own_player_id=CPU_ID,
    )


# A Base in mid-field so targets can stand on either side of it: Base cells
# (12..13, 16..17) inside a ring of Base Wall cells (11..14, 15..18).
BASE = frozenset((x, y) for x in (12, 13) for y in (16, 17))
BASE_WALL = frozenset(
    (x, y) for x in range(11, 15) for y in range(15, 19) if (x, y) not in BASE
)


def base_tiles(wall: TileType | None = TileType.BRICK) -> dict[Cell, TileType]:
    """Tiles for the mid-field Base, with its wall made of ``wall`` (or gone)."""
    tiles = {cell: TileType.BASE for cell in BASE}
    if wall is not None:
        tiles |= {cell: wall for cell in BASE_WALL}
    return tiles


def enemy_bullet(
    x: float, y: float, direction: Direction, bullet_id: int = 0, **fields
) -> BulletView:
    """An Enemy bullet with its top-left corner at pixel ``(x, y)``."""
    return BulletView(
        bullet_id=bullet_id,
        x=x,
        y=y,
        direction=direction,
        owner_type=OwnerType.ENEMY,
        **fields,
    )


# The CPU Partner at sub-tile (12, 12) spans pixels 192 to 224 on both axes;
# its bullet's lane (and the middle of its side) runs from 206 to 210.
MIDDLE = cell(12) + 14


def with_bullets(view: WorldView, *bullets: BulletView) -> WorldView:
    """``view`` with exactly ``bullets`` in flight."""
    return replace(view, bullets=bullets)


def with_own(view: WorldView, **fields) -> WorldView:
    """``view`` with the CPU Partner's tank changed by ``fields``."""
    human, own = view.players
    return replace(view, players=(human, replace(own, **fields)))


SHOT_FROM_THE_LEFT = enemy_bullet(cell(6), MIDDLE, Direction.RIGHT)
