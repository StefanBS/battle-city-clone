# CPU Partner

The CPU Partner is the computer-controlled Player in the P2 slot of a
**1 Player + CPU** game. It fights on the Human Player's side, takes no orders,
and follows exactly the same rules as a Human Player: it is a `PlayerInput`
paired with an ordinary `PlayerTank` (see
[ADR 0001](adr/0001-cpu-partner-as-player-input.md)). Terms in **bold** or
capitalised (Goal, Firing Position, Cut Off, ...) are defined in
[CONTEXT.md](../CONTEXT.md).

## Where it lives

| Module | Responsibility |
|---|---|
| `src/managers/cpu_partner.py` | `CpuPartnerInput`: picks a Goal and turns it into a movement direction and shoot requests. Also the pure checks `is_line_of_fire_safe`, `can_evade_shot` and `ambush_positions`. |
| `src/managers/goal_timing.py` | `GoalTiming` (when it decides, Goal stickiness, Reaction Delay) and `Hesitation` (holding back a shot now and then). |
| `src/managers/world_view.py` | `WorldView`: the read-only snapshot it decides from. Lines of Fire, Firing Positions, Base Threats. |
| `src/managers/pathfinding.py` | `NavGrid` and A* `find_path` over the sub-tile grid, for the tank's full footprint. Bricks are passable at extra cost (it shoots through them). Base Wall bricks never are. |
| `src/managers/steering.py` | `Steering`: notices it is stuck and picks the tanks to route around. |
| `src/managers/refused_shots.py` | `RefusedShots`: how long it has stayed lined up on a target without a safe shot. |
| `src/managers/enemy_memory.py` | `EnemyMemory`: per-Enemy facts (Cut Off, given-up sides) kept until the Enemy moves. |

Tuning values are the `CPU_PARTNER_*` constants in `src/utils/constants.py`.

## The frame loop

Each frame, `Battle` builds one `WorldView` and `PlayerManager.observe` hands
each Player's input its own view of it (`WorldView.for_player`). Human inputs
ignore it. `CpuPartnerInput.observe` then:

1. tells `Steering` whether last frame's move got it anywhere,
2. settles its Goal through `GoalTiming` (diagrams 1 and 2),
3. acts on that Goal (diagram 3 for Defend and Hunt), and
4. passes the shot through `Hesitation`.

`TankStepper` reads the result through `get_movement_direction()` and
`consume_shoot()`, the same way it reads a keyboard. `reset()` clears
everything it has decided, learned or planned. It runs at Stage start and on
respawn.

## 1. Choosing a Goal

The CPU Partner decides which Goal it prefers by asking the questions below
in order and taking the first "yes". Cut Off Enemies don't count for any of
them. Its Goal is the state it is in, and this check is how it moves from one
Goal to another.

```mermaid
flowchart TD
    Start(["Time to decide<br/>every 0.25 s, or at once when it has no Goal,<br/>its target is gone or it gave up on it"])
    Q1{"Is there a Base Threat?"}
    Q2{"Is a Power-Up within range?"}
    Q3{"Can it reach a Firing Position<br/>on any Enemy?"}
    Q4{"Can it reach an<br/>Enemy Spawn Point?"}
    Defend["<b>Defend</b><br/>the Base Threat nearest the Base"]
    Grab["<b>Grab Power-Up</b><br/>the one cheapest to reach"]
    Hunt["<b>Hunt</b><br/>its current target while it lives,<br/>else the Enemy cheapest to reach"]
    Ambush["<b>Ambush</b><br/>its current Spawn Point,<br/>else the one cheapest to reach"]
    None["<b>No Goal</b><br/>stands still"]
    Switch(["Preferred Goal goes to diagram 2,<br/>which decides when it takes over"])

    Start --> Q1
    Q1 -- yes --> Defend
    Q1 -- no --> Q2
    Q2 -- yes --> Grab
    Q2 -- no --> Q3
    Q3 -- yes --> Hunt
    Q3 -- no --> Q4
    Q4 -- yes --> Ambush
    Q4 -- no --> None
    Defend & Grab & Hunt & Ambush & None --> Switch
```

It leaves a Goal in one of three ways:

- **A better Goal comes up** at a decision: diagram 2.
- **Its target is gone** (destroyed or collected): it decides again at once.
- **Its target can't be reached**: it gives up on the Goal and decides again
  next frame. An Enemy it gave up on is Cut Off until the Enemy moves.

More on each Goal:

- **Defend** targets the Base Threat nearest the Base.
- **Grab Power-Up** targets the Power-Up cheapest to reach, and only if the
  path costs at most `CPU_PARTNER_POWER_UP_RANGE` (10 sub-tile steps, bricks at
  their extra cost).
- **Hunt** keeps its current target while that Enemy lives. Otherwise it takes
  the Enemy whose Firing Position is cheapest to reach.
- **Ambush** keeps its current Enemy Spawn Point. Otherwise it takes the one
  cheapest to reach, then waits at a Firing Position at least
  `CPU_PARTNER_AMBUSH_DISTANCE` sub-tiles away from it, facing it. It never
  waits on a Spawn Point, since that would stop Enemies from spawning there.
- The decision interval is `CPU_PARTNER_DECISION_INTERVAL` (0.25 s).

## 2. Switching Goals: stickiness and Reaction Delay

`GoalTiming` keeps two Goals: the one it has **decided** on and the one it is
**acting** on. They differ only during the Reaction Delay.

```mermaid
stateDiagram-v2
    state "Acting on its Goal" as Acting
    state "Preferring another Goal" as Wavering
    state "Reacting (still acts on the old Goal)" as Reacting

    [*] --> Acting
    Acting --> Acting : tick, still prefers its Goal
    Acting --> Wavering : tick, prefers another Goal
    Wavering --> Acting : tick, prefers its Goal again (count reset)
    Wavering --> Reacting : another Goal preferred for 0.5 s
    Acting --> Reacting : target gone, or Ambushing (gives way at once)
    Reacting --> Reacting : decides on yet another Goal (delay restarts)
    Reacting --> Acting : Reaction Delay (0.25 s) passed
```

- **Stickiness** (`CPU_PARTNER_GOAL_STICKINESS`, 0.5 s) counts the time it
  has preferred *any* other Goal, even if that Goal changes along the way. If
  only one particular Goal counted, it could never switch while its preference
  kept changing, for example when two Base Threats take turns being nearest
  the Base.
- **Ambush** is only waiting, so it gives way to any other Goal at once.
- **Reaction Delay** (`CPU_PARTNER_REACTION_DELAY`, 0.25 s): after deciding
  on a new Goal, it keeps acting on the old one until the delay passes.
- **Abandoning** a Goal (its target can't be reached) drops the Goal it is
  acting on. A newer Goal it has decided on but not yet reacted to is kept.

## 3. Engaging an Enemy (Defend and Hunt)

Both Goals that target an Enemy run the same per-frame logic. Nothing here is
stored between frames except the refused-shot count, the given-up sides and
the Cut Off list, so "states" are what it finds each frame.

```mermaid
stateDiagram-v2
    state "Approach a Firing Position" as Approach
    state "Turn to face the Enemy" as Turn
    state "Aim" as Aim
    state "Fire" as Fire
    state "Hold fire" as Hold
    state "Give up this side" as GiveUpSide
    state "Cut Off (Goal abandoned)" as CutOff
    state sides <<choice>>

    [*] --> Approach
    Approach --> Turn : lined up from a Firing Position on an open side
    Approach --> CutOff : no path to any Firing Position
    Turn --> Aim : facing the Enemy
    Aim --> Fire : Line of Fire safe and the Enemy can't slip away
    Aim --> Hold : unsafe, or the Enemy can slip away
    Fire --> Aim : next frame
    Hold --> Aim : next frame
    Hold --> GiveUpSide : held for 1 s without a break
    GiveUpSide --> sides
    sides --> Approach : a Firing Position left on another side
    sides --> CutOff : none left
    Aim --> Approach : Enemy moved out of line
    CutOff --> [*]
```

- **Approach**: A* to the cheapest Firing Position on a side it hasn't given
  up. It shoots a brick that blocks the next step once it faces it, but only
  when that shot is safe. When it has been stuck for `CPU_PARTNER_STUCK_TIME`,
  it routes around the tanks right ahead of it until they move. If only the
  Human Player is in the way, it waits and never pushes.
- **Lined up** means the centers are within half a sub-tile
  (`CPU_PARTNER_ALIGN_TOLERANCE`) on the cross axis, and the Line of Fire
  from there counts as a Firing Position for the target.
- **Safe** (`is_line_of_fire_safe`): the bullet can't hit the Base or a Base
  Wall cell, even past the target, and no Human Player stands in the Line of
  Fire before the target or the first solid tile.
- **Can slip away** (`can_evade_shot`): the Enemy is in a corridor walled on
  both sides of the Line of Fire, and can drive to an exit and clear the
  bullet's lane before the bullet arrives. Frozen or stationary Enemies can't
  slip away, and neither can an Enemy on open ground.
- **Hesitation**: each time it starts aiming, there is a 10% chance
  (`CPU_PARTNER_HESITATION_CHANCE`) it holds fire for 0.3 s. This happens after
  the logic above and doesn't count as a refused shot.
- **Given-up sides and Cut Off** are kept in `EnemyMemory` and forgotten as
  soon as the Enemy moves to another cell. The Enemy then becomes a candidate
  for every Goal again.

Grab Power-Up only uses the Approach step, toward cells where its tank would
touch the Power-Up. Ambush uses Approach and then turns to face the Enemy Spawn
Point and waits there. It doesn't fire at an empty Spawn Point. It changes Goal
to Defend or Hunt once an Enemy appears.

## Testing

- Unit tests: `tests/unit/managers/test_cpu_partner.py` builds `WorldView`s by
  hand and checks the movement and shots that come out.
- Integration: `tests/integration/test_cpu_partner_integration.py` runs a real
  `GameManager` in 1 Player + CPU mode.
