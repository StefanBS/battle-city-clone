# The Screen Flow never holds a Battle; GameManager is its pygame adapter

`ScreenFlow` (`src/managers/screen_flow.py`) owns the Screen Flow: the current `Screen`, the title, pause and options menus, the timed transitions (Victory pause, curtain, Game Over animation), returning from Options to where it was opened, and which Stage comes next. It never builds, holds or steps a `Battle`. It takes `MenuAction`s (including `PAUSE`), `dt` and the `BattleResult` of the frame, and reports what to draw, whether the Battle steps this frame (`battle_steps`), and when a new Battle should start (`take_battle_request()` returns a `BattleRequest` with the Stage, the `GameMode`, the difficulty and whether it is a new game). `GameManager` is the adapter around it: it turns pygame events into `MenuAction`s, loads the Stage's map file, builds and steps the Battle, and draws what the flow reports. We did this so the Screen Flow is tested through its interface alone, with no window, map files or fake Battle, the way ADR 0004 made frame rules testable against a `Battle`.

## Considered Options

- **The flow only reports a `BattleRequest` and receives `BattleResult`s (chosen).**
- **The flow holds the Battle, built through an injected factory, and steps it itself (rejected).** Its tests would need real map files and a `TextureManager`, or a fake Battle standing in for the most complex object in the game. The flow only needs a Battle's result, so it gets nothing else.
- **Settings and sound as reported values or cues (rejected).** The flow is given the `SettingsManager` and `SoundManager` and uses them directly, as the Battle does with sound in ADR 0004. Tests use a real `SettingsManager` on a temporary file and a `SoundManager` mock.

## Consequences

- Carrying progress stays in the adapter: a `BattleRequest` that is not a new game means "build the next Battle from the last one's `carried_progress`". The flow never sees lives, Stars or score.
- Leaving Pause does not reach into the Battle. When a menu action takes the flow from Pause back to the running Battle, the adapter clears the Battle's pending shoot, so the button that confirmed Resume doesn't fire a bullet.
- Menu actions reach the flow in event order, and the flow ignores them on screens without a menu. An action queued before `PAUSE` in the same frame is therefore dropped rather than moving the pause cursor. The adapter still resets `InputHandler` on pausing, so a stick held through the pause moves the cursor when it next moves.
- `Screen.GAME_OVER` does not exist: Game Over arrives as a `BattleResult` and goes straight to the Game Over animation.
