"""Original Battle City NES stage enemy compositions.

Each tuple is (basic, fast, power, armor) — 20 enemies per stage.
Data sourced from NES ROM analysis. See docs/battle-city-enemy-data.md.
"""

# (basic, fast, power, armor)
STAGE_ENEMIES: list[tuple[int, int, int, int]] = [
    (18, 2, 0, 0),   # Stage 1
    (14, 4, 0, 2),   # Stage 2
    (14, 4, 0, 2),   # Stage 3
    (2, 5, 10, 3),   # Stage 4
    (8, 5, 5, 2),    # Stage 5
    (9, 2, 7, 2),    # Stage 6
    (7, 4, 6, 3),    # Stage 7
    (7, 4, 7, 2),    # Stage 8
    (6, 4, 7, 3),    # Stage 9
    (12, 2, 4, 2),   # Stage 10
    (5, 5, 4, 6),    # Stage 11
    (0, 6, 8, 6),    # Stage 12
    (0, 8, 8, 4),    # Stage 13
    (0, 4, 10, 6),   # Stage 14
    (0, 2, 10, 8),   # Stage 15
    (16, 2, 0, 2),   # Stage 16
    (8, 2, 8, 2),    # Stage 17
    (2, 8, 6, 4),    # Stage 18
    (4, 4, 4, 8),    # Stage 19
    (2, 8, 2, 8),    # Stage 20
    (6, 2, 8, 4),    # Stage 21
    (6, 8, 2, 4),    # Stage 22
    (0, 10, 4, 6),   # Stage 23
    (10, 4, 4, 2),   # Stage 24
    (0, 8, 2, 10),   # Stage 25
    (4, 6, 4, 6),    # Stage 26
    (2, 8, 2, 8),    # Stage 27
    (15, 2, 2, 1),   # Stage 28
    (0, 4, 10, 6),   # Stage 29
    (4, 8, 4, 4),    # Stage 30
    (3, 8, 3, 6),    # Stage 31
    (6, 4, 2, 8),    # Stage 32
    (4, 4, 4, 8),    # Stage 33
    (0, 10, 4, 6),   # Stage 34
    (0, 6, 4, 10),   # Stage 35
]
