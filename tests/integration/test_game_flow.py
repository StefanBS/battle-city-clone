import pytest
import pygame
from src.managers.game_manager import GameManager
from src.utils.constants import FPS, TILE_SIZE

# Initialize Pygame non-graphically for testing
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME) # Minimal display init

# TODO: Maybe a fixture to set up GameManager?

def test_initial_game_state():
    # TODO: Initialize game components
    # TODO: Assert initial state (e.g., player position, score)
    assert True  # Placeholder assertion

@pytest.mark.parametrize(
    "key, axis, direction_sign",
    [
        (pygame.K_UP, 1, -1),    # UP: axis=1 (y), direction=-1 (decrease)
        (pygame.K_DOWN, 1, 1),  # DOWN: axis=1 (y), direction=1 (increase)
        (pygame.K_LEFT, 0, -1),   # LEFT: axis=0 (x), direction=-1 (decrease)
        (pygame.K_RIGHT, 0, 1),  # RIGHT: axis=0 (x), direction=1 (increase)
    ],
)
def test_player_movement(key, axis, direction_sign):
    """Test player tank movement in all four directions."""
    game_manager = GameManager()
    player_tank = game_manager.player_tank

    # Manually set position to an open space (grid 8, 8)
    start_grid_x, start_grid_y = 8, 8
    new_x = start_grid_x * TILE_SIZE
    new_y = start_grid_y * TILE_SIZE
    player_tank.set_position(new_x, new_y)
    player_tank.target_position = (new_x, new_y) # Ensure target is also updated
    player_tank.prev_x, player_tank.prev_y = new_x, new_y # Sync previous position

    initial_pos = player_tank.get_position()
    dt = 1.0 / FPS
    update_duration = 0.2
    num_updates = int(update_duration / dt)

    # Simulate key press
    key_down_event = pygame.event.Event(pygame.KEYDOWN, key=key)
    game_manager.player_tank.handle_event(key_down_event)

    # Update game state
    for _ in range(num_updates):
        game_manager.update()

    # Simulate key release
    key_up_event = pygame.event.Event(pygame.KEYUP, key=key)
    game_manager.player_tank.handle_event(key_up_event)

    final_pos = player_tank.get_position()

    # Assert position changed
    assert final_pos != initial_pos

    # Assert movement occurred in the correct direction
    if direction_sign == -1:
        assert final_pos[axis] < initial_pos[axis]
    else:
        assert final_pos[axis] > initial_pos[axis]

# Add more integration tests for other game flows and movements
# e.g., test_player_movement_blocked_by_wall

# Add more integration tests for other game flows