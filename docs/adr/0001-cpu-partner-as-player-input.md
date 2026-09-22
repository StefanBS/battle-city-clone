# CPU Partner is a PlayerInput, not a tank subclass

The CPU Partner is built as a `PlayerInput` implementation that reads a read-only view of the game world and outputs a movement direction and shoot requests. `PlayerManager` pairs it with an ordinary `PlayerTank`, exactly as it does for keyboard and controller input. This differs from Enemy AI, which lives inside `EnemyTank` (see ADR 0002: since then, both Enemy AI and `PlayerInput` only produce intent, and one `TankStepper` moves every tank). We chose it so the CPU Partner follows exactly the same rules as a Human Player (ice sliding, friendly-fire freeze, bullet caps, star upgrades, lives, score) without any special-case code, and so its decisions can be unit-tested as a function from world state to input.

## Consequences

- `PlayerInput` implementations need a way to see the game world. Human inputs ignore it.
- Do not "fix" the asymmetry by moving the CPU Partner into a `PlayerTank` subclass: that would split the same-rules guarantee across two code paths.
