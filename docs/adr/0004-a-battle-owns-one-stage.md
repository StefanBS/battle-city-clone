# A Battle owns one Stage; GameManager keeps only the screen flow

`GameManager` keeps the screen flow: menus, pause, options, curtain, the Game Over animation and which Stage comes next. Everything that happens while a Stage is played lives in a `Battle` (`src/managers/battle.py`). That covers the Stage's collaborators, the frame pipeline, applying outcomes, and the single Game Over / Victory decision. A new `Battle` is built for each Stage from a loaded `Map`, the `GameMode` and each slot's `CarriedProgress` (lives, Stars, score). When it ends, it hands its `carried_progress` back for the next Battle. This replaces `PlayerManager.preserve_state` / `restore_state`, and `PlayerManager` now lasts one Battle. We did this so frame rules can be tested without a window, menus or `SettingsManager`, and so a Stage's lifetime belongs to one object.

## Considered Options

- **Sounds: an injected sink (chosen), not a frame report.** The Battle, `PlayerManager` and `CollisionResponseHandler` play sounds through the `SoundManager` they are given. This departs from #324, where the Enemy side reported "fired" and the caller played the sound. We rejected returning sound cues from `step()` (or emitting domain events that `GameManager` maps to sounds) because it meant rewiring every sound call in two more modules. It also bought no testability that a recording fake doesn't already give. If sounds ever need to depend on screen flow, revisit this.

## Consequences

- `step(dt)` returns the Battle's outcome (`GAME_OVER`, `VICTORY` or `None`). Stepping a Battle that has ended does nothing, so Game Over is still decided once and still beats Victory. After it ends, `GameManager` stops stepping it but keeps rendering it (Victory pause, Game Over rise).
- File I/O stays outside: `GameManager` finds the Stage's map file (falling back to `level_01`) and rebuilds the `Renderer`. The Battle applies the map's difficulty override itself, because that is a Stage rule.
