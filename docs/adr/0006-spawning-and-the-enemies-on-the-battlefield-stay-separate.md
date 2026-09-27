# Spawning and the Enemies on the battlefield stay separate; the Battle hands Enemies from one to the other

`SpawnManager` owns the Roster, Spawning and the Carrier indices, and hands over the Enemies that Appear. `EnemyManager` owns the Enemies on the battlefield, the `EnemyAI` paired with each one, and the Clock. This is the same way `PlayerManager` owns the Players (#327). The `Battle` passes Enemies from one to the other. Each frame it takes the Enemies that Appeared (`take_appeared()`), adds them to `EnemyManager`, and clears the Power-Ups when one of them is a Carrier. This happens before `advance()` runs the spawn timer, so a new Enemy already blocks its Enemy Spawn Point. Victory is `is_exhausted and not enemies`. We keep this handoff in the `Battle` because it's a frame rule across Players, Enemies and Power-Ups, and ADR 0004 gives those rules to the `Battle`.

## Considered Options

- **Keep the split, with the `Battle` doing the handoff (chosen).**
- **One Enemy-side module behind a single `step` (rejected).** An architecture review suggested it (the one that also produced #383–#387). It would move the Roster, Spawning, Appear, the Enemies, their AIs and the Clock back behind one interface. That is what `SpawnManager` held before #327, which split it because it was doing two jobs its name only half described. The merge would hide only about three lines of `Battle`:
  - Spawn blocking needs every tank, Players included, so the `Battle` still passes them in.
  - A Carrier appearing clears the Power-Ups, which belong to `PowerUpManager`, so the `Battle` still acts on it.
  - Keeping both classes as internal parts behind one front module would add a module that fails the deletion test, and break the symmetry with `PlayerManager`.

## Consequences

- Don't merge `SpawnManager` and `EnemyManager` again to hide the order of the handoff. The order is a `Battle` frame rule. Keep it in `Battle.step` / `bring_in_spawns`, with the comment that says why.
- A new rule about Enemies joining the battlefield goes in `EnemyManager.add` if it applies to every Enemy, however it got there (as the Clock freeze does). It goes in `Battle.bring_in_spawns` if it involves another collaborator of the Battle (as clearing the Power-Ups does).
- Revisit this if the handoff grows beyond a few lines in `Battle`, or if a second caller has to repeat it.
