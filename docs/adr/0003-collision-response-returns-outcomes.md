# Collision response changes the physics right away and returns the consequences as outcomes

`CollisionResponseHandler` still makes, in the middle of its loop, the changes that later events in the same frame depend on: deactivating bullets, reverting tanks, damaging tiles and calling `take_damage`. Everything with a game-level consequence it returns as a list of outcomes (`EnemyDestroyed`, `PlayerDestroyed`, `BaseDestroyed`, `PowerUpCollected`) in the order the events happened. `GameManager` applies them in one place: score, removal, Carrier drops, explosions and sounds, respawn and Power-Up effects. Game Over and then Victory are checked only after every outcome has been applied. We chose this over two alternatives. The first was making everything an outcome, which breaks the same-frame dedup that relies on `bullet.active`. The second was keeping the old callbacks and the Power-Up mailbox. That lost a second Power-Up collected in the same frame, let Grenade kills skip the Enemy-destroyed path, and decided Game Over in two places.

## Consequences

- Because respawn now happens after the loop, the handler keeps track of tanks destroyed so far in the frame. Bullets pass through them, and a destroyed Player can't collect a Power-Up. Without this, a Player hit by two bullets in one frame would lose two lives.
- Applying an outcome can produce more outcomes. `PowerUpManager.apply` returns `EnemyDestroyed(by=None)` for each Enemy a Grenade destroys, and `GameManager` works through a queue until it's empty. Points go to the Player named in `by`, so Grenade kills score nothing, as on the NES.
- Don't give `CollisionResponseHandler` callbacks for score or game state again. A new consequence becomes a new outcome type.
