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
| `src/managers/dodge.py` | The Dodge (section 4): `incoming_shots`, `can_shoot_down`, `shields_base`, `sidestep`, and `Awareness` (reaction time and missed shots). |
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
2. Dodges an Incoming Shot if it has noticed one (diagram 4), and if so
   stops there for this frame,
3. otherwise settles its Goal through `GoalTiming` (diagrams 1 and 2),
4. acts on that Goal (diagram 3 for Defend and Hunt), and
5. passes the shot through `Hesitation`.

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

Preferring a new Goal (diagram 1) doesn't make the CPU Partner switch to it
straight away. `GoalTiming` keeps two Goals: the one it has **decided** on and
the one it is **acting** on. A switch runs through three steps, left to right:

```mermaid
stateDiagram-v2
    direction LR
    Settled : <b>Settled</b><br/>acts on its Goal
    Tempted : <b>Tempted</b><br/>prefers another Goal,<br/>keeps its own for now
    Reacting : <b>Reacting</b><br/>has decided on the new Goal,<br/>still acts on the old one

    [*] --> Settled
    Settled --> Tempted : prefers another Goal
    Tempted --> Settled : prefers its own Goal again
    Tempted --> Reacting : has preferred other Goals for 0.5 s
    Settled --> Reacting : its target is gone, or it was Ambushing
    Reacting --> Settled : 0.25 s passed, now acts on the new Goal
```

It checks what it prefers only at a decision (every 0.25 s), so Tempted lasts
at least one decision.

- **Stickiness** (`CPU_PARTNER_GOAL_STICKINESS`, 0.5 s) counts the time it
  has preferred *any* other Goal, even if that Goal changes along the way. If
  only one particular Goal counted, it could never switch while its preference
  kept changing, for example when two Base Threats take turns being nearest
  the Base.
- **Straight to Reacting**: when its Goal's target is gone (from Settled or
  Tempted), or when it was only Ambushing, which is just waiting.
- **Reaction Delay** (`CPU_PARTNER_REACTION_DELAY`, 0.25 s): after deciding
  on a new Goal, it keeps acting on the old one until the delay passes. If
  it decides on yet another Goal meanwhile, the delay starts over.
- **Abandoning** a Goal (its target can't be reached) drops the Goal it is
  acting on. A newer Goal it has decided on but not yet reacted to is kept.

## 3. Engaging an Enemy (Defend and Hunt)

Both Goals that target an Enemy go through the checks below every frame,
starting from the top. Only three things carry over from one frame to the
next: how long it has held fire, which sides of each Enemy it has given up,
and which Enemies are Cut Off.

```mermaid
flowchart TD
    Start(["Each frame, with a Defend or Hunt target"])
    Q1{"Lined up on the Enemy<br/>from a Firing Position<br/>on a side it hasn't given up?"}
    Q2{"Facing the Enemy?"}
    Q3{"Line of Fire safe, and<br/>the Enemy can't slip away?"}
    Q4{"Held fire on this Enemy<br/>for 1 s without a break?"}
    Q5{"A Firing Position left<br/>on another side?"}
    QP{"Path to a Firing Position<br/>on a side it hasn't given up?"}
    Step["<b>Approach</b><br/>take the next step,<br/>shooting a brick in the way"]
    Turn["<b>Turn</b> toward the Enemy"]
    Fire["<b>Fire</b><br/>unless it hesitates"]
    Hold["<b>Hold fire</b> this frame"]
    GiveUp["<b>Give up this side</b><br/>approaches another side next frame"]
    CutOff["<b>Cut Off</b><br/>Goal abandoned"]

    Start --> Q1
    Q1 -- no --> QP
    QP -- yes --> Step
    QP -- no --> CutOff
    Q1 -- yes --> Q2
    Q2 -- no --> Turn
    Q2 -- yes --> Q3
    Q3 -- yes --> Fire
    Q3 -- no --> Q4
    Q4 -- no --> Hold
    Q4 -- yes --> Q5
    Q5 -- yes --> GiveUp
    Q5 -- no --> CutOff
```

- **Approach**: A* to the cheapest Firing Position on a side it hasn't given
  up. It shoots a brick that blocks the next step once it faces it, but only
  when that shot is safe. When it has been stuck for `CPU_PARTNER_STUCK_TIME`,
  it routes around the tanks right ahead of it until they move. If the only
  thing in the way is the Human Player, it waits and never pushes, and the
  Enemy isn't Cut Off.
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

## 4. Dodging an Incoming Shot

A Dodge is a reflex, not a Goal
([ADR 0005](adr/0005-dodge-is-a-reflex-not-a-goal.md)). A Goal switch takes
at least 0.75 s (stickiness, then the Reaction Delay), and stepping out of a
bullet's way takes about 0.2 s. So each frame, before its Goal, the CPU
Partner checks for an Incoming Shot, and while it Dodges it skips its Goal
entirely. The Goal and its target are left as they were, and every clock
behind them pauses: `GoalTiming`, the refused-shot count, Hesitation, and
the forgetting of Cut Off Enemies and given-up sides. It carries on with
them the frame the Dodge ends, so a long run of Dodges delays a Goal switch
by as long as it lasts.

```mermaid
flowchart TD
    Start(["Each frame, before its Goal"])
    Q0{"Shielded or Frozen?"}
    Q1{"Noticed an Incoming Shot?"}
    Q2{"Facing it, with a shot left,<br/>and in line with its own bullet?"}
    Q3{"Would the shot fly on<br/>into the Base?"}
    Q4{"A clear way out of its lane in time?"}
    Q5{"Could it shoot it down<br/>after turning?"}
    Goal(["Acts on its Goal (diagrams 1 to 3)"])
    ShootDown["<b>Shoot it down</b><br/>holding its ground"]
    Step["<b>Sidestep</b><br/>the sooner way"]
    Turn["<b>Turn and fire</b> at it"]
    Stay["<b>Take the hit</b><br/>standing still"]

    Start --> Q0
    Q0 -- yes --> Goal
    Q0 -- no --> Q1
    Q1 -- no --> Goal
    Q1 -- yes --> Q2
    Q2 -- yes --> ShootDown
    Q2 -- no --> Q3
    Q3 -- no --> Q4
    Q4 -- yes --> Step
    Q4 -- no --> Q5
    Q3 -- yes --> Q5
    Q5 -- yes --> Turn
    Q5 -- "no, guarding the Base" --> Stay
    Q5 -- "no, otherwise" --> Goal
```

- **Incoming Shot** (`incoming_shots`): an Enemy bullet whose lane overlaps
  the CPU Partner, flying toward it, with no solid tile (brick counts) and
  no other Player in between, due to hit within `CPU_PARTNER_DODGE_HORIZON`
  (0.75 s). Enemy bullets fly through Enemies, so an Enemy never shields it.
  The Human Player's bullets never count. With several, it deals with the
  one due to hit first.
- **Noticing** (`Awareness`): a shot must have been coming at it for
  `CPU_PARTNER_DODGE_REACTION_TIME` (0.1 s) before it reacts. The first
  time a bullet comes at it, there is a `CPU_PARTNER_DODGE_MISS_CHANCE`
  (20%) chance it never notices that bullet at all. Once noticed, a bullet
  stays noticed for as long as it flies, unless it fires back at it: that
  shot is then left to its own bullet, and it doesn't sidestep it while
  its bullet is on the way.
- **Shoot it down** (`can_shoot_down`): its bullet leaves from its middle,
  so it only meets a shot in line with that; one that would clip the tank's
  edge flies past. It needs a shot left under its Bullet Cap. There is no
  Line of Fire safety check (the two bullets cancel out first) and no
  Hesitation.
- **Sidestep** (`sidestep`): at right angles to the shot, the way that gets
  the whole tank out of the lane sooner, if it can get there before the
  shot hits. A way is ruled out when a tile or another tank is in it, or
  when it would bring any other shot sooner: one not coming at it yet, or
  one already coming at it along that way. It never backs away along the
  lane: that only buys time.
- **Guarding the Base** (`shields_base`): when the shot would fly on to hit
  the Base itself if the CPU Partner weren't there, it doesn't step aside.
  It fires back if it can, else takes the hit: a life is worth less than
  the Base. A shot that would only hit a Base Wall brick is sidestepped.
- **Turn and fire** is the last resort. Turning and firing happen in the
  same frame. If firing back would miss too, a Dodge can't help, and it
  simply carries on with its Goal.

## Testing

- Unit tests: `tests/unit/managers/test_cpu_partner.py` builds `WorldView`s by
  hand and checks the movement and shots that come out.
- Integration: `tests/integration/test_cpu_partner_integration.py` runs a real
  `GameManager` in 1 Player + CPU mode.
