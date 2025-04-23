#!/usr/bin/env python3
"""
Battle City Clone - Main Entry Point
"""

import sys
import pygame
from loguru import logger
from src.managers.game_manager import GameManager

# Configure Loguru
logger.remove()  # Remove default stderr handler
logger.add(sys.stdout, level="INFO")  # Add stdout handler with INFO level
logger.add("game.log", rotation="10 MB", level="INFO")  # Keep file handler

def main() -> None:
    """Initialize and run the game."""
    logger.info("Initializing Pygame...")
    pygame.init()

    # Initialize game manager
    logger.info("Initializing GameManager...")
    game = GameManager()

    try:
        logger.info("Starting game loop...")
        game.run()
    except Exception as e:
        logger.exception(f"An error occurred: {e}")  # Log the exception with traceback
        sys.exit(1)
    finally:
        logger.info("Quitting Pygame...")
        pygame.quit()
        logger.info("Exiting game.")


if __name__ == "__main__":
    main()
