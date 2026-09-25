import pytest
import pygame
from unittest.mock import MagicMock
from src.core.tank import HitResult
from src.utils.constants import (
    Direction,
    FPS,
    HELMET_INVINCIBILITY_DURATION,
    SPAWN_INVINCIBILITY_DURATION,
    SHIELD_FLICKER_INTERVAL,
    SHIELD_FAST_FLICKER_INTERVAL,
    BULLET_SPEED,
    STAR_BULLET_SPEED_MULTIPLIER,
    STAR_MAX_BULLETS,
)


class TestPlayerTank:
    """Test cases for the PlayerTank class."""

    @pytest.fixture
    def player_tank(self, create_player_tank):
        """Fixture to create a PlayerTank instance."""
        return create_player_tank(x=5, y=12)

    def test_player_tank_initialization(self, player_tank):
        """Test PlayerTank initialization aligns to grid and sets correct defaults."""
        assert player_tank.x == 0
        assert player_tank.y == 0
        assert player_tank.initial_position == (5.0, 12.0)
        assert player_tank.lives == 3
        assert player_tank.health == 1
        assert not player_tank.is_invincible

    @pytest.mark.parametrize(
        "dx,dy,expected_direction",
        [
            (1, 0, Direction.RIGHT),
            (-1, 0, Direction.LEFT),
            (0, 1, Direction.DOWN),
            (0, -1, Direction.UP),
        ],
    )
    def test_move_sets_direction(self, player_tank, dx, dy, expected_direction):
        """Test that move() sets the correct direction."""
        dt = 1.0 / FPS
        player_tank.prev_x = player_tank.x
        player_tank.prev_y = player_tank.y
        player_tank.move(dx, dy, dt)
        assert player_tank.direction == expected_direction

    def test_move_zero_does_nothing(self, player_tank):
        """Test that move(0, 0) doesn't change direction."""
        dt = 1.0 / FPS
        initial_direction = player_tank.direction
        player_tank.move(0, 0, dt)
        assert player_tank.direction == initial_direction

    def test_player_tank_respawn(self, player_tank):
        """Test player tank respawn functionality."""
        initial_pos = player_tank.initial_position
        player_tank.take_damage()

        player_tank.respawn()

        assert (player_tank.x, player_tank.y) == initial_pos
        assert player_tank.is_invincible
        assert player_tank.invincibility_timer == 0
        assert player_tank.blink_timer == 0
        assert player_tank.direction == Direction.UP

    def test_an_eliminated_player_does_not_respawn(self, player_tank):
        player_tank.eliminate()
        position = (player_tank.x, player_tank.y)

        player_tank.respawn()

        assert (player_tank.x, player_tank.y) == position
        assert not player_tank.is_invincible

    def test_draw_with_sprite_not_invincible(self, player_tank):
        """Test drawing with sprite when not invincible."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = False
        player_tank.sprite = mock_sprite

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_called_once_with(mock_sprite, player_tank.rect)

    def test_draw_no_sprite_not_invincible(self, player_tank):
        """Test drawing without sprite when not invincible does nothing."""
        mock_surface = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = False
        player_tank.sprite = None

        player_tank.draw(mock_surface)

        mock_surface.blit.assert_not_called()

    def test_draw_invincible_never_blinks(self, player_tank):
        """Test that invincible tank is always visible (shield replaces blink)."""
        mock_surface = MagicMock(spec=pygame.Surface)
        mock_sprite = MagicMock(spec=pygame.Surface)
        player_tank.is_invincible = True
        # Even in what would be the "invisible" blink phase, tank is drawn
        player_tank.blink_timer = player_tank.blink_interval * 1.5
        player_tank.sprite = mock_sprite

        player_tank.draw(mock_surface)

        # Tank is always drawn when invincible (shield replaces blink)
        assert mock_surface.blit.call_count == 2

    def test_respawn_syncs_rect(self, player_tank):
        """Test that respawn() updates rect to match the new position."""
        dt = 1.0 / FPS
        player_tank.prev_x = player_tank.x
        player_tank.prev_y = player_tank.y
        player_tank.move(0, 1, dt)
        player_tank.move(0, 1, dt)
        moved_rect = player_tank.rect.copy()

        player_tank.respawn()

        assert player_tank.rect.topleft == (
            round(player_tank.initial_position[0]),
            round(player_tank.initial_position[1]),
        )
        assert player_tank.rect.topleft != moved_rect.topleft


class TestPlayerTankLives:
    @pytest.fixture
    def player(self, create_player_tank):
        return create_player_tank(x=5, y=12)

    def test_a_hit_with_lives_left_destroys_and_spends_a_life(self, player):
        assert player.take_damage() is HitResult.DESTROYED
        assert player.lives == 2
        assert player.health == player.max_health
        assert not player.is_eliminated

    def test_a_hit_on_the_last_life_eliminates(self, player):
        player.take_damage()
        player.take_damage()

        assert player.take_damage() is HitResult.ELIMINATED
        assert player.lives == 0
        assert player.is_eliminated

    def test_a_shielded_player_absorbs_a_hit(self, player):
        player.activate_invincibility(HELMET_INVINCIBILITY_DURATION)

        assert player.take_damage() is HitResult.ABSORBED
        assert player.lives == 3

    def test_a_hit_on_an_eliminated_player_changes_nothing(self, player):
        player.eliminate()

        assert player.take_damage() is HitResult.ELIMINATED
        assert player.lives == 0
        assert player.is_eliminated

    def test_restore_lives_rejects_fewer_than_one(self, player):
        with pytest.raises(ValueError):
            player.restore_lives(0)

    def test_gain_life_adds_a_life(self, player):
        player.gain_life()

        assert player.lives == 4

    def test_restore_lives_sets_the_carried_count(self, player):
        player.restore_lives(5)

        assert player.lives == 5
        assert not player.is_eliminated


class TestActivateInvincibility:
    @pytest.fixture
    def player(self, create_player_tank):
        return create_player_tank(x=96, y=96, map_width_px=512, map_height_px=512)

    def test_activates_for_duration_and_resets_timers(self, player):
        player.invincibility_timer = 2.0
        player.blink_timer = 1.5

        player.activate_invincibility(5.0)

        assert player.is_invincible is True
        assert player.invincibility_duration == 5.0
        assert player.invincibility_timer == 0
        assert player.blink_timer == 0

    def test_respawn_after_helmet_restores_short_duration(self, player):
        player.activate_invincibility(HELMET_INVINCIBILITY_DURATION)
        player.is_invincible = False
        player.respawn()
        assert player.is_invincible is True
        assert player.invincibility_duration == SPAWN_INVINCIBILITY_DURATION


class TestStarUpgrade:
    @pytest.fixture
    def player(self, create_player_tank):
        return create_player_tank(x=96, y=96, map_width_px=512, map_height_px=512)

    def test_initial_star_level(self, player):
        assert player.star_level == 0

    def test_tier1_faster_bullets(self, player):
        player.apply_star()
        assert player.star_level == 1
        assert player.bullet_speed == BULLET_SPEED * STAR_BULLET_SPEED_MULTIPLIER

    def test_tier2_double_fire(self, player):
        player.apply_star()
        player.apply_star()
        assert player.star_level == 2
        assert player.max_bullets == STAR_MAX_BULLETS

    def test_tier3_power_bullets(self, player):
        for _ in range(3):
            player.apply_star()
        assert player.star_level == 3
        assert player.power_bullets is True

    def test_star_caps_at_tier3(self, player):
        for _ in range(5):
            player.apply_star()
        assert player.star_level == 3

    def test_respawn_resets_star_level(self, player):
        player.apply_star()
        player.apply_star()
        player.respawn()
        assert player.star_level == 0
        assert player.bullet_speed == BULLET_SPEED
        assert player.max_bullets == 1
        assert player.power_bullets is False

    def test_star_changes_sprite(self, player, mock_texture_manager):
        mock_texture_manager.reset_mock()
        player.apply_star()
        called_names = [
            c.args[0] for c in mock_texture_manager.get_sprite.call_args_list
        ]
        assert any("tier1" in name for name in called_names)


class TestPlayerTankPlayerId:
    def test_default_player_id_is_1(self, create_player_tank):
        """PlayerTank defaults to player_id=1."""
        tank = create_player_tank(map_width_px=512, map_height_px=512)
        assert tank.player_id == 1

    def test_player_id_2_accepted(self, create_player_tank):
        """PlayerTank accepts player_id=2."""
        tank = create_player_tank(map_width_px=512, map_height_px=512, player_id=2)
        assert tank.player_id == 2

    def test_player2_uses_player2_sprite_prefix(
        self, create_player_tank, mock_texture_manager
    ):
        """Player 2 tank requests sprites with 'player2_tank_' prefix."""
        create_player_tank(map_width_px=512, map_height_px=512, player_id=2)
        mock_texture_manager.get_sprite.assert_any_call("player2_tank_tier0_up_1")

    def test_player1_uses_player_tank_sprite_prefix(
        self, create_player_tank, mock_texture_manager
    ):
        """Player 1 tank requests sprites with 'player_tank_' prefix (unchanged)."""
        create_player_tank(map_width_px=512, map_height_px=512, player_id=1)
        mock_texture_manager.get_sprite.assert_any_call("player_tank_tier0_up_1")


class TestShieldAnimation:
    @pytest.fixture
    def mock_texture_manager(self):
        """Override to return distinct surfaces per sprite name."""
        from src.managers.texture_manager import TextureManager

        mock_tm = MagicMock(spec=TextureManager)
        sprite_cache: dict = {}

        def get_sprite(name: str) -> MagicMock:
            if name not in sprite_cache:
                sprite_cache[name] = MagicMock(spec=pygame.Surface)
            return sprite_cache[name]

        mock_tm.get_sprite.side_effect = get_sprite
        return mock_tm

    @pytest.fixture
    def player_tank(self, create_player_tank):
        return create_player_tank(x=5, y=12)

    def test_shield_frames_cached_at_init(self, player_tank):
        assert len(player_tank._shield_frames) == 2

    def test_shield_frame_alternates_with_timer(self, player_tank):
        player_tank.activate_invincibility(10.0)
        player_tank.invincibility_timer = SHIELD_FLICKER_INTERVAL * 0.5
        player_tank.sprite = MagicMock()
        surface = MagicMock()
        player_tank.draw(surface)
        first_shield = surface.blit.call_args_list[1][0][0]

        surface.reset_mock()
        player_tank.invincibility_timer = SHIELD_FLICKER_INTERVAL * 1.5
        player_tank.draw(surface)
        second_shield = surface.blit.call_args_list[1][0][0]

        assert first_shield != second_shield

    def test_shield_uses_normal_flicker_before_warning(self, player_tank):
        player_tank.activate_invincibility(10.0)
        player_tank.update(2.0)  # 8s remaining, well before warning
        assert player_tank.shield_flicker_interval == SHIELD_FLICKER_INTERVAL

    def test_shield_stays_up_with_fast_flicker_during_warning(self, player_tank):
        player_tank.activate_invincibility(10.0)
        player_tank.update(8.5)  # 1.5s remaining, in warning phase
        assert player_tank.is_invincible is True
        assert player_tank.shield_flicker_interval == SHIELD_FAST_FLICKER_INTERVAL

    def test_short_shield_stays_up_with_normal_flicker(self, player_tank):
        """Short invincibility (< warning) uses normal speed the whole time."""
        player_tank.activate_invincibility(1.5)
        player_tank.update(1.0)
        assert player_tank.is_invincible is True
        assert player_tank.shield_flicker_interval == SHIELD_FLICKER_INTERVAL
