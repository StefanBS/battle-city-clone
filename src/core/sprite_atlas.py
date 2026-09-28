"""SpriteAtlas: where entities get their sprites, without naming the shell."""

from typing import Protocol

import pygame


class SpriteAtlas(Protocol):
    """Looks up a sprite by name.

    ``TextureManager`` matches it by shape; ``core/`` and the Battle only
    annotate with this, so they never import the shell (ADR 0008).
    """

    def get_sprite(self, name: str) -> pygame.Surface:
        """Return the sprite called ``name``; raise ``KeyError`` if missing."""
        ...
