#!/usr/bin/env python3
"""
Battle City Clone - Main Entry Point
"""

import sys
import pygame
from src.managers.game_manager import GameManager


def main() -> None:
    """Initialize and run the game."""
    pygame.init()

    # Initialize game manager
    game = GameManager()

    try:
        game.run()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
