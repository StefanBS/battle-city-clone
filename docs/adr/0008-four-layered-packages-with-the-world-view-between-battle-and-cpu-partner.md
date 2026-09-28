# Four layered packages, with the World View between the Battle and the CPU Partner

The code that used to sit flat in `src/managers/` is split into four packages, layered so imports only point down, and `import-linter` fails the build when one points the wrong way:

```
src/shell/        GameManager, ScreenFlow, Renderer, TextureManager, SoundManager,
                  SettingsManager, MenuController, InputHandler
  ├─ src/battle/       Battle and its collaborators, PlayerInput, outcomes
  └─ src/cpu_partner/  CpuPartnerInput and its helpers
       (battle and cpu_partner never import each other)
src/world_view/   WorldView and footprint
src/core/         entities; imports none of the above
```

`src/states/` and `src/utils/` stay importable from everywhere. The flat folder hid the groups ADR 0001 and ADR 0004 already describe, and nothing kept them apart: the Battle imported the CPU Partner to build P2's input, and the CPU Partner reached back into the Battle through the World View's use of the stepper's Bullet Cap check. The World View gets its own package because it is the only way the Battle's state reaches the CPU Partner (ADR 0001). Putting it in `core/` would make it look like one more entity, and putting it in `battle/` would make the CPU Partner import the Battle.

## Consequences

- The shell builds the CPU Partner's input and hands it to `Battle`, which passes it to `PlayerManager`. `PlayerManager` still builds the Human inputs, since they depend on which controllers are open.
- The Bullet Cap check is a method on `Tank`. The stepper still owns the bullet list and enforces the cap (ADR 0002). The World View builder asks the same question when it sets `can_fire`.
- The Battle and `core/` never name the shell's classes. They annotate with `SpriteAtlas` (`src/core/sprite_atlas.py`) and `SoundPlayer` (`src/battle/sound_player.py`), Protocols that `TextureManager` and `SoundManager` match by shape. Tests keep mocking the shell classes with `spec=`.
