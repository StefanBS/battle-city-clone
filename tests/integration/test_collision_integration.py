import pytest
from loguru import logger
from src.utils.constants import FPS, TILE_SIZE
from src.states.game_state import GameState
from src.core.tile import Tile, TileType
from src.core.enemy_tank import EnemyTank

# Tests related to collision interactions between different game objects


@pytest.mark.parametrize(
    "tile_to_place, expected_bullet_active, expected_tile_type",
    [
        (TileType.BRICK, False, TileType.EMPTY),  # Bullet hits brick, brick destroyed
        (TileType.STEEL, False, TileType.STEEL),  # Bullet hits steel, steel unchanged
        (TileType.WATER, True, TileType.WATER),  # Bullet passes through water
        (TileType.BUSH, True, TileType.BUSH),  # Bullet passes through bush
    ],
)
def test_player_bullet_vs_tile(
    game_manager_fixture,  # Use the base fixture
    tile_to_place,
    expected_bullet_active,
    expected_tile_type,
):
    """Test player bullet interaction with various tile types."""
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    game_map = game_manager.map

    # Define target tile location
    target_x_grid = 7
    target_y_grid = 10

    # Manually place the specified tile type at the target location
    if 0 <= target_y_grid < game_map.height and 0 <= target_x_grid < game_map.width:
        target_tile = Tile(tile_to_place, target_x_grid, target_y_grid, TILE_SIZE)
        game_map.tiles[target_y_grid][target_x_grid] = target_tile
        logger.debug(
            f"Placed {tile_to_place.name} tile at ({target_x_grid}, {target_y_grid})"
        )
    else:
        pytest.fail(
            f"Target tile coordinates ({target_x_grid}, {target_y_grid}) "
            f"are out of bounds."
        )

    # Position player below the target tile
    player_start_x = target_x_grid * TILE_SIZE
    player_start_y = (target_y_grid + 1) * TILE_SIZE
    player_tank.set_position(player_start_x, player_start_y)
    player_tank.target_position = (player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim up and shoot
    player_tank.direction = "up"
    player_tank.shoot()

    assert player_tank.bullet is not None, "Bullet failed to spawn."
    bullet = player_tank.bullet  # Get reference to the bullet

    # Simulate game time until bullet should have hit (or passed)
    dt = 1.0 / FPS
    update_duration = 0.2  # Sufficient time for bullet to travel one tile
    num_updates = int(update_duration / dt)

    for i in range(num_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)
        # Stop checking early if bullet becomes inactive for relevant cases
        if not expected_bullet_active and not bullet.active:
            logger.debug(f"Bullet became inactive as expected after {i + 1} updates.")
            break

    # --- Assertions after updates ---
    # 1. Verify bullet's final active state
    assert bullet.active == expected_bullet_active, (
        f"Bullet active state mismatch for {tile_to_place.name}. "
        f"Expected: {expected_bullet_active}, Got: {bullet.active}"
    )

    # 2. Verify the tile's final type
    # Re-fetch the tile in case it was replaced (though unlikely with current impl)
    final_tile = game_map.get_tile_at(target_x_grid, target_y_grid)
    assert final_tile is not None, "Target tile somehow disappeared."
    assert final_tile.type == expected_tile_type, (
        f"Tile type mismatch for {tile_to_place.name}. "
        f"Expected: {expected_tile_type.name}, Got: {final_tile.type.name}"
    )


def test_player_bullet_destroys_enemy_tank(game_manager_fixture, mocker):
    """Test player bullet hitting and destroying a basic enemy tank."""
    mocker.patch('src.core.enemy_tank.random.uniform', return_value=0.0)
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank

    # --- Spawn Enemy Tank --- #
    enemy_type = "basic"
    enemy_x_grid = 7
    enemy_y_grid = 5
    enemy_start_x = enemy_x_grid * TILE_SIZE
    enemy_start_y = enemy_y_grid * TILE_SIZE

    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    # Replace existing enemies with just this one for a clean test
    game_manager.enemy_tanks = [enemy_tank]
    initial_enemy_count = len(game_manager.enemy_tanks)
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid})"
    )
    # --- End Spawn --- #

    # Position player below the enemy tank
    player_start_x = enemy_x_grid * TILE_SIZE
    player_start_y = (enemy_y_grid + 1) * TILE_SIZE
    player_tank.set_position(player_start_x, player_start_y)
    player_tank.target_position = (player_start_x, player_start_y)
    player_tank.prev_x, player_tank.prev_y = player_start_x, player_start_y

    # Aim up and shoot
    player_tank.direction = "up"
    player_tank.shoot()

    assert player_tank.bullet is not None, "Bullet failed to spawn."
    bullet = player_tank.bullet

    # Simulate game time until bullet should have hit
    dt = 1.0 / FPS
    max_simulation_time = 0.5  # Increased timeout duration
    max_updates = int(max_simulation_time / dt)
    enemy_destroyed_during_loop = False
    bullet_became_inactive_during_loop = False

    for i in range(max_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)
        if not bullet.active:
            logger.debug(f"Player bullet became inactive after {i + 1} updates.")
            bullet_became_inactive_during_loop = True
            # If bullet is inactive, check if enemy is also destroyed
            if enemy_tank not in game_manager.enemy_tanks:
                enemy_destroyed_during_loop = True
            break  # Stop if bullet is inactive

        if enemy_tank not in game_manager.enemy_tanks:
            logger.debug(f"Enemy tank destroyed after {i + 1} updates.")
            enemy_destroyed_during_loop = True
            # If enemy destroyed, bullet might still be active if it passed through
            if not bullet.active:
                 bullet_became_inactive_during_loop = True
            break # Stop if enemy is destroyed
    else: # Loop finished without break
        logger.warning(
            f"Max updates ({max_updates}) reached. Bullet active: {bullet.active}, "
            f"Enemy in list: {enemy_tank in game_manager.enemy_tanks}"
        )


    # --- Assertions after updates ---
    # 1. Bullet should be inactive if it hit the enemy.
    # If the enemy was destroyed, the bullet might have passed through, so this check is conditional.
    if enemy_destroyed_during_loop or (enemy_tank not in game_manager.enemy_tanks):
        # If enemy is gone, bullet could be active or inactive.
        # The critical part is enemy destruction.
        pass
    else: # Enemy not destroyed, so bullet must have become inactive (e.g. hit armor, or missed and hit wall)
          # This test expects destruction, so if enemy is still there, it's a failure.
          # We rely on the next assertion to catch this. For now, ensure bullet did *something*.
        assert bullet_became_inactive_during_loop, "Bullet remained active but enemy was not destroyed."


    # 2. The enemy tank should have been removed from the list
    assert enemy_tank not in game_manager.enemy_tanks, (
        "Enemy tank was not removed after being hit."
    )
    assert len(game_manager.enemy_tanks) == initial_enemy_count - 1, (
        "Enemy count did not decrease by one."
    )


@pytest.mark.parametrize(
    "player_initial_lives, player_is_invincible, expected_game_state, "
    "expected_player_lives_after_hit",
    [
        # Case 1: Vulnerable player, final life -> Game Over
        (1, False, GameState.GAME_OVER, 0),
        # Case 2: Vulnerable player, multiple lives -> Respawn
        (3, False, GameState.RUNNING, 2),
        # Case 3: Invincible player -> No effect
        (3, True, GameState.RUNNING, 3),
    ],
)
def test_enemy_bullet_hits_player_tank(
    game_manager_fixture,
    player_initial_lives,
    player_is_invincible,
    expected_game_state,
    expected_player_lives_after_hit,
    mocker,
):
    """Test enemy bullet hitting the player tank under different conditions."""
    mocker.patch('src.core.enemy_tank.random.uniform', return_value=0.0)
    game_manager = game_manager_fixture
    player_tank = game_manager.player_tank
    initial_spawn_pos = player_tank.initial_position

    # --- Configure Player State ---
    player_tank.lives = player_initial_lives
    player_tank.is_invincible = player_is_invincible
    player_tank.invincibility_timer = 0  # Reset timer if starting invincible
    logger.debug(
        f"Setting up player: lives={player_tank.lives}, "
        f"invincible={player_tank.is_invincible}"
    )
    # --- End Player Config ---

    # --- Spawn Enemy Tank Above Player --- #
    enemy_type = "basic"
    player_x_grid = int(player_tank.x // TILE_SIZE)
    player_y_grid = int(player_tank.y // TILE_SIZE)
    enemy_x_grid = player_x_grid
    enemy_y_grid = player_y_grid - 2  # Place enemy 2 tiles above

    enemy_start_x = enemy_x_grid * TILE_SIZE
    enemy_start_y = enemy_y_grid * TILE_SIZE

    # Ensure enemy spawns within bounds
    if not (
        0 <= enemy_y_grid < game_manager.map.height
        and 0 <= enemy_x_grid < game_manager.map.width
    ):
        pytest.skip(
            f"Calculated enemy position ({enemy_x_grid}, {enemy_y_grid}) "
            f"is out of bounds. Skipping."
        )

    enemy_tank = EnemyTank(
        enemy_start_x,
        enemy_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy_tank.direction = "down"  # Aim at player
    game_manager.enemy_tanks = [enemy_tank]  # Replace default enemies
    logger.debug(
        f"Manually added {enemy_type} enemy at ({enemy_x_grid}, {enemy_y_grid}) "
        f"aiming {enemy_tank.direction}"
    )
    # --- End Enemy Spawn --- #

    # --- Fire Enemy Bullet --- #
    enemy_tank.shoot()
    assert enemy_tank.bullet is not None, "Enemy bullet failed to spawn."
    enemy_bullet = enemy_tank.bullet
    assert enemy_bullet.active, "Enemy bullet spawned inactive."
    # --- End Fire --- #

    # --- Simulate game time until bullet should hit --- #
    dt = 1.0 / FPS
    max_simulation_time = 0.6  # Increased timeout duration
    max_updates = int(max_simulation_time / dt)
    interaction_processed = False

    original_player_lives = player_tank.lives # Store to check if lives changed

    for i in range(max_updates):
        game_manager.update()  # Update game (moves bullet, processes collisions)

        current_lives = player_tank.lives
        current_state = game_manager.state

        # Check for interaction conditions
        if not player_is_invincible:
            if not enemy_bullet.active:
                logger.debug(
                    f"Enemy bullet became inactive after {i + 1} updates (hit detected)."
                )
                interaction_processed = True
                break
            if current_lives < original_player_lives:
                logger.debug(
                    f"Player lost a life (lives: {current_lives}) after {i + 1} updates."
                )
                interaction_processed = True
                break
            if current_state == GameState.GAME_OVER and expected_game_state == GameState.GAME_OVER:
                logger.debug(
                    f"Game state became GAME_OVER as expected after {i + 1} updates."
                )
                interaction_processed = True
                break
        else: # Player is invincible
            if i == max_updates -1: # Let simulation run for invincible case
                interaction_processed = True # Assume interaction window passed
                break


        # Early exit if game state changes definitively and unexpectedly
        if current_state != GameState.RUNNING and current_state != expected_game_state:
            logger.warning(
                f"Game state changed to {current_state.name} unexpectedly after {i+1} updates."
            )
            interaction_processed = True # Mark as processed to evaluate current state
            break
    else: # Loop finished without break
        logger.warning(
            f"Max updates ({max_updates}) reached. Bullet active: {enemy_bullet.active}, "
            f"GameState: {game_manager.state.name}, PlayerLives: {player_tank.lives}"
        )
        # If loop finished, mark interaction_processed as true to allow assertions to run on final state
        interaction_processed = True


    # --- Assertions after updates --- #
    # If player was invincible, the bullet might or might not be active (e.g. hit a wall later)
    # The key is that player state (lives, game state) should match expectations.
    if not player_is_invincible:
        assert interaction_processed, (
            f"Enemy bullet interaction with vulnerable player not detected. "
            f"Bullet active: {enemy_bullet.active}, Player lives: {player_tank.lives}, "
            f"Game state: {game_manager.state.name}"
        )
        # If an interaction was processed, and player was vulnerable, bullet should be inactive.
        if player_tank.lives < original_player_lives or game_manager.state == GameState.GAME_OVER:
             assert not enemy_bullet.active, (
                "Enemy bullet should be inactive after damaging player or causing game over."
            )

    # 1. Assert Game State
    assert game_manager.state == expected_game_state, (
        f"Expected game state {expected_game_state.name}, "
        f"but got {game_manager.state.name}"
    )

    # 2. Assert Player Lives
    assert player_tank.lives == expected_player_lives_after_hit, (
        f"Expected player lives {expected_player_lives_after_hit}, "
        f"but got {player_tank.lives}"
    )

    # 3. Assert Respawn effects (if life lost but game not over)
    if (
        expected_player_lives_after_hit == player_initial_lives - 1
        and expected_game_state == GameState.RUNNING
    ):
        assert player_tank.get_position() == initial_spawn_pos, (
            "Player did not return to spawn position after losing a life."
        )
        assert player_tank.is_invincible, "Player is not invincible after respawning."
    # 4. Assert Invincible state persisted (if hit while invincible)
    elif player_is_invincible:
        assert player_tank.is_invincible, (
            "Player lost invincibility after being hit while invincible."
        )


def test_enemy_bullet_hits_other_enemy(game_manager_fixture, mocker):
    """Test that an enemy bullet has no effect on another enemy tank."""
    mocker.patch('src.core.enemy_tank.random.uniform', return_value=0.0)
    game_manager = game_manager_fixture

    # --- Spawn Two Enemy Tanks --- #
    enemy_type = "basic"
    enemy1_x_grid, enemy1_y_grid = 7, 5  # Top enemy (shooter)
    enemy2_x_grid, enemy2_y_grid = 7, 7  # Bottom enemy (target)

    enemy1_start_x = enemy1_x_grid * TILE_SIZE
    enemy1_start_y = enemy1_y_grid * TILE_SIZE
    enemy2_start_x = enemy2_x_grid * TILE_SIZE
    enemy2_start_y = enemy2_y_grid * TILE_SIZE

    enemy1 = EnemyTank(
        enemy1_start_x,
        enemy1_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy1.direction = "down"  # Aim at enemy2

    enemy2 = EnemyTank(
        enemy2_start_x,
        enemy2_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )

    game_manager.enemy_tanks = [enemy1, enemy2]  # Set the enemies
    initial_enemy_count = len(game_manager.enemy_tanks)
    initial_enemy2_health = enemy2.health
    logger.debug(f"Spawned enemy1 at ({enemy1_x_grid}, {enemy1_y_grid}) aiming down.")
    logger.debug(f"Spawned enemy2 at ({enemy2_x_grid}, {enemy2_y_grid}).")
    # --- End Spawn --- #

    # --- Fire Enemy Bullet --- #
    enemy1.shoot()
    assert enemy1.bullet is not None, "Enemy1 bullet failed to spawn."
    bullet = enemy1.bullet
    assert bullet.active, "Enemy1 bullet spawned inactive."
    # --- End Fire --- #

    # --- Simulate game time until bullet should hit --- #
    dt = 1.0 / FPS
    update_duration = 0.4  # Time to cross ~2 tiles
    num_updates = int(update_duration / dt)

    initial_bullet_state = bullet.active

    for _ in range(num_updates):
        game_manager.update()

    # --- Assertions --- #
    # Bullet should remain active as enemy bullets don't hit other enemies
    assert bullet.active == initial_bullet_state, "Bullet state changed unexpectedly."
    assert bullet.active, "Bullet should still be active after passing another enemy."

    # 1. Enemy2 health should be unchanged
    assert enemy2.health == initial_enemy2_health, (
        f"Enemy2 health changed. Expected: {initial_enemy2_health}, "
        f"Got: {enemy2.health}"
    )

    # 2. Enemy2 should still be in the list
    assert enemy2 in game_manager.enemy_tanks, "Enemy2 was removed from the list."

    # 3. Total enemy count should be unchanged
    assert len(game_manager.enemy_tanks) == initial_enemy_count, (
        f"Enemy count changed. Expected: {initial_enemy_count}, "
        f"Got: {len(game_manager.enemy_tanks)}"
    )


def test_enemy_bullets_collide(game_manager_fixture, mocker):
    """Test that two enemy bullets pass through each other."""
    mocker.patch('src.core.enemy_tank.random.uniform', return_value=0.0)
    game_manager = game_manager_fixture

    # --- Spawn Two Enemy Tanks Facing Each Other --- #
    enemy_type = "basic"
    enemy1_x_grid, enemy1_y_grid = 5, 7  # Left enemy
    enemy2_x_grid, enemy2_y_grid = 9, 7  # Right enemy (4 tiles apart)

    enemy1_start_x = enemy1_x_grid * TILE_SIZE
    enemy1_start_y = enemy1_y_grid * TILE_SIZE
    enemy2_start_x = enemy2_x_grid * TILE_SIZE
    enemy2_start_y = enemy2_y_grid * TILE_SIZE

    enemy1 = EnemyTank(
        enemy1_start_x,
        enemy1_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy1.direction = "right"  # Aim at enemy2

    enemy2 = EnemyTank(
        enemy2_start_x,
        enemy2_start_y,
        TILE_SIZE,
        game_manager.texture_manager,
        enemy_type,
    )
    enemy2.direction = "left"  # Aim at enemy1

    game_manager.enemy_tanks = [enemy1, enemy2]  # Set the enemies
    logger.debug(f"Spawned enemy1 at ({enemy1_x_grid}, {enemy1_y_grid}) aiming right.")
    logger.debug(f"Spawned enemy2 at ({enemy2_x_grid}, {enemy2_y_grid}) aiming left.")
    # --- End Spawn --- #

    # --- Fire Both Bullets Simultaneously --- #
    enemy1.shoot()
    enemy2.shoot()

    assert enemy1.bullet is not None, "Enemy1 bullet failed to spawn."
    assert enemy2.bullet is not None, "Enemy2 bullet failed to spawn."
    bullet1 = enemy1.bullet
    bullet2 = enemy2.bullet
    assert bullet1.active, "Enemy1 bullet spawned inactive."
    assert bullet2.active, "Enemy2 bullet spawned inactive."
    # --- End Fire --- #

    # --- Simulate game time until bullets should have passed each other --- #
    # They are 4 tiles apart, need to travel ~2 tiles each.
    dt = 1.0 / FPS
    update_duration = 0.4  # Should be sufficient time
    num_updates = int(update_duration / dt)

    # Record initial active states
    initial_bullet1_active = bullet1.active
    initial_bullet2_active = bullet2.active

    logger.info(f"Simulating {num_updates} updates to check bullet pass-through.")
    for i in range(num_updates):
        game_manager.update()
        # Check if bullets became inactive unexpectedly
        if not bullet1.active and initial_bullet1_active:
            logger.warning(f"Bullet 1 became inactive unexpectedly on update {i + 1}")
            # Allow simulation to continue to check bullet 2
        if not bullet2.active and initial_bullet2_active:
            logger.warning(f"Bullet 2 became inactive unexpectedly on update {i + 1}")
            # Allow simulation to continue to check bullet 1

    # --- Assertions --- #
    # Bullets should still be active after passing each other's paths
    assert bullet1.active, (
        "Enemy1 bullet should still be active after passing enemy2 bullet."
    )
    assert bullet2.active, (
        "Enemy2 bullet should still be active after passing enemy1 bullet."
    )

    logger.info("Enemy bullets correctly remained active after passing each other.")
