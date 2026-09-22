# Every tank goes through one stepping path; Enemy AI only produces intent

Players and Enemies are stepped through a frame by the same `TankStepper`: tank timers, then the ice check, then Slide or move, then firing within the Bullet Cap. Enemy AI no longer turns, moves or starts a Slide for its own tank. It records a wanted direction and a wish to shoot, which `TankStepper` reads through the same two methods a `PlayerInput` provides. We chose this over keeping Enemy AI in charge of its own movement and only fixing the ice-flag ordering. With two stepping paths, the same rule (when a Slide starts, when the ice flag is read) was already written twice and had drifted: Enemies were deciding from last frame's ice flag.

## Consequences

- Don't add Enemy-only (or Player-only) movement rules to `EnemyTank.update()` or `PlayerManager`. Tank rules go in `Tank` or `TankStepper`, so both kinds of tank follow them.
- Sounds are the caller's choice. `TankStepper` reports what happened (a Slide started, a bullet was fired), and callers decide what to play. That is how only Players make the ice sound.
