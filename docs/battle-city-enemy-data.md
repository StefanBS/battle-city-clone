# Battle City Enemy Composition Data

Source: Cross-referenced from NES ROM data via `sapser/pygame_tank` and `shinima/battle-city` open-source clones.

## Enemy Types

| Type | Speed | Bullet Speed | Health | Shoot Interval |
|------|-------|-------------|--------|---------------|
| basic | 0.75x | 1x | 1 | 2.0s |
| fast | 1.5x | 1x | 1 | 1.8s |
| power | 1x | 1.5x | 1 | 1.0s |
| armor | 1x | 1x | 4 | 1.5s |

## Per-Stage Enemy Composition (20 tanks each)

Format: (basic, fast, power, armor)

```
Stage  1: (18, 2, 0, 0)
Stage  2: (14, 4, 0, 2)
Stage  3: (14, 4, 0, 2)
Stage  4: (2, 5, 10, 3)
Stage  5: (8, 5, 5, 2)
Stage  6: (9, 2, 7, 2)
Stage  7: (7, 4, 6, 3)
Stage  8: (7, 4, 7, 2)
Stage  9: (6, 4, 7, 3)
Stage 10: (12, 2, 4, 2)
Stage 11: (5, 5, 4, 6)
Stage 12: (0, 6, 8, 6)
Stage 13: (0, 8, 8, 4)
Stage 14: (0, 4, 10, 6)
Stage 15: (0, 2, 10, 8)
Stage 16: (16, 2, 0, 2)
Stage 17: (8, 2, 8, 2)
Stage 18: (2, 8, 6, 4)
Stage 19: (4, 4, 4, 8)
Stage 20: (2, 8, 2, 8)
Stage 21: (6, 2, 8, 4)
Stage 22: (6, 8, 2, 4)
Stage 23: (0, 10, 4, 6)
Stage 24: (10, 4, 4, 2)
Stage 25: (0, 8, 2, 10)
Stage 26: (4, 6, 4, 6)
Stage 27: (2, 8, 2, 8)
Stage 28: (15, 2, 2, 1)
Stage 29: (0, 4, 10, 6)
Stage 30: (4, 8, 4, 4)
Stage 31: (3, 8, 3, 6)
Stage 32: (6, 4, 2, 8)
Stage 33: (4, 4, 4, 8)
Stage 34: (0, 10, 4, 6)
Stage 35: (0, 6, 4, 10)
```

After stage 35, the game loops using stage 35's composition.

## Spawn Order

The NES ROM stores only type counts, not a fixed spawn sequence. The spawn order can be randomized or interleaved. The 4th, 11th, and 18th tanks are "flashing" tanks that drop power-ups when destroyed (future feature).

## Difficulty Levels

The game supports two AI difficulty levels, selectable from the Options menu:

### Easy

Original NES-style random AI. Enemies pick directions randomly and shoot on a fixed timer. No awareness of player or base position.

### Normal

Enhanced AI with directional bias and context-aware shooting:

- **Weighted movement**: At direction changes, enemies favor directions that move toward the player or base. The bias strength varies by type (see multipliers below).
- **Aligned shooting**: When an enemy is lined up with the player or base (same row/column, facing toward it), its shoot interval is halved.
- **Type-specific tendencies**:

| Type  | Base Bias | Player Bias | Behavior                    |
|-------|-----------|-------------|-----------------------------|
| basic | 0.5x      | 0.5x        | Wanders more aimlessly      |
| fast  | 0.5x      | 1.5x        | Tends to chase the player   |
| power | 1.0x      | 1.5x        | Hunts the player            |
| armor | 1.5x      | 0.5x        | Pushes toward the base      |

Multipliers are applied to the difficulty-level base biases (base_bias=0.3, player_bias=0.2).

## Notes

- All stages spawn exactly 20 enemies total
- Max 4 enemies on screen at once in the original game (our current max is 5)
