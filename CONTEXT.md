# Battle City Clone

A clone of the NES game Battle City: one or two player tanks defend their Base from waves of enemy tanks.

## Language

### Players

**Player**:
A tank that occupies a player slot (P1 or P2). A Player is controlled by either a human or the CPU, and both follow the same rules.
_Avoid_: User, hero

**Human Player**:
A Player controlled by a person through the keyboard or a game controller. P1 is always a Human Player.

**CPU Partner**:
A Player in the P2 slot that the computer controls, fighting on the Human Player's side. It is fully autonomous and takes no orders.
_Avoid_: Bot, AI player, ally, companion

**Goal**:
What the CPU Partner is currently trying to do: in priority order **Defend** (intercept a Base Threat), **Grab Power-Up**, **Hunt** (attack the Enemy with the Firing Position cheapest to reach) and **Ambush** (wait at a Firing Position covering an Enemy Spawn Point when there is nothing else to do). Only one Goal is active at a time.
_Avoid_: State, mode, task

**Firing Position**:
A spot in a target's row or column from which a Player's Line of Fire reaches the target, either clear or blocked only by brick, and could never hit the Base or a Base Wall cell, even beyond the target.

**Reaction Delay**:
The moment the CPU Partner takes before acting on a new Goal. Until it passes, it keeps acting on its previous Goal.

**Refused Shot**:
The CPU Partner lined up on an Enemy from a Firing Position but holding fire because the shot isn't safe. Held on one side for too long, the CPU Partner gives up firing from that side until the Enemy moves.

**Cut Off**:
An Enemy the CPU Partner has no Firing Position left to use against from where the Enemy stands: it found none it can reach, or it has given up every side after holding a Refused Shot too long on each. It is left out of the CPU Partner's Goals until it moves.

**Incoming Shot**:
An Enemy bullet that will hit the CPU Partner if it stays where it is.
_Avoid_: Threat (that is a Base Threat), incoming bullet

**Dodge**:
The CPU Partner's reflex against an Incoming Shot: it shoots the bullet down or sidesteps out of its way. A Dodge overrides the CPU Partner's movement and shooting while it lasts, but it is not a Goal: the Goal and its target stay as they were and the CPU Partner goes back to them straight after.
_Avoid_: Evade (an Enemy slipping away from a shot), evasion

**Co-op**:
A game with two Players, where P2 is either a second Human Player or a CPU Partner.

**Destroyed**:
What happens to a tank when it takes the hit that ends it. An Enemy leaves the battlefield. A Player loses a life and, if it has any left, reappears at its spawn point.

**Eliminated**:
A Player destroyed on its last life. It stays off the battlefield for the rest of the game, including later Battles.
_Avoid_: Dead, out of lives

### Opponents

**Enemy**:
A computer-controlled tank that attacks Players and the Base.

**Roster**:
The Enemies a Stage sends against the Players, by type and count. They enter the battlefield one at a time, in random order, until none are left.
_Avoid_: Wave, spawn queue

**Enemy Spawn Point**:
One of the fixed spots on a map where Enemies appear. A tank covering any part of it stops Enemies from spawning there.

**Spawning**:
An Enemy drawn from the Roster while its spawn animation plays at an Enemy Spawn Point. It is not on the battlefield yet and can't be hit, but it blocks that Enemy Spawn Point.

**Appear**:
What a Spawning Enemy does when its animation ends: it becomes an Enemy on the battlefield. The first Enemy starts Spawning as soon as the Battle begins, and each later one a spawn interval after the previous one started, or as soon after that as a free Enemy Spawn Point is picked.
_Avoid_: Materialize, enter

**Carrier**:
An Enemy that flashes red and makes a Power-Up appear the first time a Player's bullet hits it, or when a Grenade destroys it. It then stops flashing and is an ordinary Enemy.
_Avoid_: Flashing tank, bonus tank

**Enemy AI**:
The behaviour that drives an Enemy's movement and shooting. Never used for the CPU Partner.

**Frozen**:
The state of a tank that for a while neither moves, turns nor fires, though its bullets already in flight keep going and it can still be destroyed. A tank that is on ice when it becomes Frozen still finishes its Slide, then stands still. Every Enemy is Frozen while a Clock is in effect, and Enemies that appear during it are Frozen too. A Player is Frozen for a moment when the other Player's bullet hits it.
_Avoid_: Paused, stopped

### Battlefield

**Base**:
The eagle the Players defend. When it is destroyed, the game is lost.
_Avoid_: Eagle, HQ

**Base Wall**:
The brick tiles directly surrounding the Base. While a Shovel is in effect it is **Fortified**: steel instead of brick.

**Base Threat**:
An Enemy close to the Base, or with a line of fire to the Base that is clear or blocked only by brick.

**World View**:
A read-only snapshot of the battlefield (tiles, Base, Enemies, Power-Ups, bullets, Players), built once per frame and handed to every Player's input. Human Players' inputs ignore it; the CPU Partner decides from it alone.
_Avoid_: Game state, world state

**Line of Fire**:
The straight row or column a tank's bullet would travel along from its current position and facing.

**Slide**:
The short, fixed distance a tank keeps travelling in its old direction when it stops or turns on ice. Players and Enemies follow the same rule. A tank that has just run into something doesn't Slide.

**Bullet Cap**:
The number of a tank's bullets that can be in flight at once: 1, or 2 for a Player with enough Stars. A tank at its Bullet Cap can't fire.

**Power-Up**:
A pickup that appears on the battlefield and gives the Player who collects it an effect (star, helmet, grenade, clock, shovel, extra life).

**Grenade**:
The Power-Up that destroys every Enemy on the battlefield at once.
_Avoid_: Bomb

**Clock**:
The Power-Up that makes every Enemy Frozen for a while, including those that Appear before it runs out.
_Avoid_: Timer, freeze power-up

**Shovel**:
The Power-Up that Fortifies the Base Wall for a while, first rebuilding any of its destroyed bricks. Shortly before it runs out the wall flashes between steel and brick, then goes back to brick. Collecting another Shovel while one is in effect starts it over.
_Avoid_: Spade

### Game flow

**Stage**:
One numbered level of the game: its map, its Roster and its difficulty. Stages are played in order.
_Avoid_: Level

**Battle**:
One playing of a Stage, from the moment its Players appear until it ends in Game Over or Victory. Players carry their lives, Stars and score from one Battle into the next.
_Avoid_: Round, match

**Victory**:
The end of a Battle in which every Enemy in the Stage's Roster has been destroyed. If Game Over happens at the same moment, Game Over wins.

**Game Over**:
The end of a Battle, and of the game: the Base is destroyed, or every Human Player is Eliminated. A CPU Partner that is not Eliminated does not keep the game going.

**Game Complete**:
The end of the game after Victory on the last Stage.
_Avoid_: Win, ending

**Screen Flow**:
The sequence of screens around the Battles: the title screen, the curtain before each Stage, pause, options, the Game Over animation and Game Complete. It decides which Stage comes next and when a Battle starts, but nothing that happens inside one.
_Avoid_: Game state, game loop
