#!/usr/bin/env python3
"""Extract player tank sprite from atlas and generate icon files.

One-time script. Run from project root:
    python scripts/generate_icons.py
"""

import os
import pygame

pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)

# Load the sprite atlas
atlas = pygame.image.load("assets/sprites/sprites.png").convert_alpha()

# Player tank facing up, frame 1: grid position (0, 0), each grid cell is 8x8
# Sprite is 2x2 grid cells = 16x16 pixels
SOURCE_TILE = 8
sprite_rect = pygame.Rect(0, 0, SOURCE_TILE * 2, SOURCE_TILE * 2)
sprite = atlas.subsurface(sprite_rect)

os.makedirs("assets/icons", exist_ok=True)

# Generate PNGs at required sizes
for size in (64, 128, 256):
    scaled = pygame.transform.scale(sprite, (size, size))
    pygame.image.save(scaled, f"assets/icons/battle-city-{size}.png")
    print(f"Generated assets/icons/battle-city-{size}.png")

# Generate ICO (PIL required for .ico)
try:
    from PIL import Image

    img = Image.open("assets/icons/battle-city-256.png")
    img.save(
        "assets/icons/battle-city.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("Generated assets/icons/battle-city.ico")
except ImportError:
    print("Pillow not installed — skipping .ico generation.")
    print("Install with: uv pip install Pillow")

pygame.quit()
