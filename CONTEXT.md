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

**Cut Off**:
An Enemy the CPU Partner found it can't reach from where the Enemy stands. It is left out of the CPU Partner's Goals until it moves.

**Co-op**:
A game with two Players, where P2 is either a second Human Player or a CPU Partner.

### Opponents

**Enemy**:
A computer-controlled tank that attacks Players and the Base.

**Enemy Spawn Point**:
One of the fixed spots on a map where Enemies appear. A tank standing on it stops Enemies from spawning there.

**Enemy AI**:
The behaviour that drives an Enemy's movement and shooting. Never used for the CPU Partner.

### Battlefield

**Base**:
The eagle the Players defend. When it is destroyed, the game is lost.
_Avoid_: Eagle, HQ

**Base Wall**:
The brick (or, after a shovel, steel) tiles directly surrounding the Base.

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

**Game Over**:
The end of a game: the Base is destroyed, or every Human Player is out of lives. A CPU Partner that still has lives does not keep the game going.
