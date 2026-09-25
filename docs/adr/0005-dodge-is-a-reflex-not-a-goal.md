# Dodge is a reflex, not a Goal

The CPU Partner's Dodge (shooting down or sidestepping an Incoming Shot) runs as a reflex checked every frame before it acts on its Goal, not as a fifth Goal above Defend. When there is an Incoming Shot, the Dodge overrides movement and shooting for that frame; the Goal, its target and `GoalTiming` are left untouched, so the CPU Partner resumes its Goal the moment the Dodge ends. We chose this because a Goal switch runs through stickiness (0.5 s) and the Reaction Delay (0.25 s), far slower than the ~0.2 s a sidestep needs, and because making Dodge a Goal would drop the current target on every bullet and break "only one Goal at a time" as the thing that describes what the CPU Partner is trying to do.

## Consequences

- While it Dodges, the Goal's clocks pause: `GoalTiming` (decision interval, stickiness, Reaction Delay), the refused-shot count, the stuck count that makes it route around tanks, Hesitation, and the forgetting of Cut Off Enemies and given-up sides all pick up where they left off. A long run of Dodges therefore delays a Goal switch, such as turning to Defend, by as long as it lasts.
- When it doesn't Dodge, the Goal's step is still checked against Incoming Shots after the Goal acts: the CPU Partner holds still rather than step back into the way of a shot it has just sidestepped.
- Dodge has its own, much shorter timing (a reaction time and a per-bullet chance of not noticing), separate from the Goal timers.
- Do not "tidy" Dodge into the Goal list or route it through `GoalTiming`: the delays that make Goal switching feel human would make every Dodge too late.
