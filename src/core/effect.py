import pygame


class Effect:
    """A transient, frame-based visual effect (e.g., explosion).

    Plays through a list of sprite frames at a fixed rate,
    then marks itself inactive for removal.
    """

    def __init__(
        self,
        x: float,
        y: float,
        frames: list[pygame.Surface],
        frame_duration: float,
    ) -> None:
        """Initialize the effect.

        Args:
            x: Center x position of the effect.
            y: Center y position of the effect.
            frames: List of sprite surfaces to animate through.
            frame_duration: Seconds each frame is displayed.
        """
        self.x = x
        self.y = y
        self.frames = frames
        self.frame_duration = frame_duration
        self.current_frame: int = 0
        self.timer: float = 0.0
        self.active: bool = True

    def update(self, dt: float) -> None:
        """Advance the animation timer and frame index.

        Args:
            dt: Time elapsed since last update in seconds.
        """
        if not self.active:
            return

        self.timer += dt
        frames_to_advance = int(self.timer / self.frame_duration)
        if frames_to_advance > 0:
            self.timer -= frames_to_advance * self.frame_duration
            self.current_frame += frames_to_advance
            if self.current_frame >= len(self.frames):
                self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the current frame centered on (x, y).

        Each frame is centered individually based on its own
        dimensions, so variable-sized frames (e.g., small -> large
        explosion) expand outward from center.

        Args:
            surface: Surface to draw on.
        """
        if not self.active:
            return

        frame = self.frames[self.current_frame]
        fw, fh = frame.get_size()
        draw_x = self.x - fw // 2
        draw_y = self.y - fh // 2
        surface.blit(frame, (draw_x, draw_y))
