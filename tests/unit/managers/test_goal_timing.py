import pytest

from src.managers.goal_timing import Goal, GoalKind, GoalTiming

HUNT_A = Goal(GoalKind.HUNT, 1)
HUNT_B = Goal(GoalKind.HUNT, 2)
DEFEND_A = Goal(GoalKind.DEFEND, 1)
GRAB = Goal(GoalKind.GRAB_POWER_UP, (5, 5))
AMBUSH = Goal(GoalKind.AMBUSH, (12, 0))


class Preferences:
    """Stands in for the battlefield: the preferred Goal and which are gone."""

    def __init__(self, preferred: Goal | None) -> None:
        self.preferred = preferred
        self.gone: set[Goal] = set()
        self.decisions = 0

    def prefer(self) -> Goal | None:
        self.decisions += 1
        return self.preferred

    def exists(self, goal: Goal) -> bool:
        return goal not in self.gone


def run(timing: GoalTiming, prefs: Preferences, frames: int) -> list[Goal | None]:
    """The Goal acted on in each of ``frames`` frames."""
    return [timing.update(prefs.prefer, prefs.exists) for _ in range(frames)]


def acting_on(timing: GoalTiming, prefs: Preferences, goal: Goal) -> None:
    """Bring ``timing`` to act on ``goal``."""
    prefs.preferred = goal
    for _ in range(100):
        if timing.update(prefs.prefer, prefs.exists) == goal:
            return
    raise AssertionError(f"never acted on {goal}")


class TestGoalTimingDecisionInterval:
    @pytest.fixture
    def timing(self) -> GoalTiming:
        return GoalTiming(decision_frames=4, reaction_frames=0, stickiness_frames=1)

    def test_decides_again_only_every_interval(self, timing) -> None:
        prefs = Preferences(HUNT_A)
        run(timing, prefs, 1)
        prefs.preferred = DEFEND_A
        assert run(timing, prefs, 3) == [HUNT_A] * 3
        assert prefs.decisions == 1
        assert run(timing, prefs, 1) == [DEFEND_A]
        assert prefs.decisions == 2

    def test_switches_at_once_when_its_target_is_gone(self) -> None:
        timing = GoalTiming(decision_frames=4, reaction_frames=0, stickiness_frames=8)
        prefs = Preferences(HUNT_A)
        run(timing, prefs, 1)
        prefs.gone.add(HUNT_A)
        prefs.preferred = HUNT_B
        assert run(timing, prefs, 1) == [HUNT_B]


class TestGoalTimingReactionDelay:
    @pytest.fixture
    def timing(self) -> GoalTiming:
        return GoalTiming(decision_frames=1, reaction_frames=3, stickiness_frames=1)

    def test_keeps_acting_on_its_old_goal_while_reacting(self, timing) -> None:
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        prefs.preferred = HUNT_B
        assert run(timing, prefs, 3) == [HUNT_A] * 3
        assert timing.decided == HUNT_B
        assert run(timing, prefs, 1) == [HUNT_B]


class TestGoalTimingStickiness:
    @pytest.fixture
    def timing(self) -> GoalTiming:
        return GoalTiming(decision_frames=1, reaction_frames=0, stickiness_frames=3)

    def test_keeps_its_goal_until_another_is_preferred_for_long_enough(
        self, timing
    ) -> None:
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        prefs.preferred = DEFEND_A
        assert run(timing, prefs, 3) == [HUNT_A, HUNT_A, DEFEND_A]

    def test_ignores_a_preference_that_flickers(self, timing) -> None:
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        for _ in range(3):
            prefs.preferred = DEFEND_A
            assert run(timing, prefs, 2) == [HUNT_A] * 2
            prefs.preferred = HUNT_A
            assert run(timing, prefs, 1) == [HUNT_A]

    def test_counts_time_preferring_any_other_goal(self, timing) -> None:
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        prefs.preferred = GRAB
        run(timing, prefs, 1)
        prefs.preferred = DEFEND_A
        assert run(timing, prefs, 2) == [HUNT_A, DEFEND_A]

    def test_ambush_gives_way_at_once(self, timing) -> None:
        prefs = Preferences(AMBUSH)
        acting_on(timing, prefs, AMBUSH)
        prefs.preferred = HUNT_A
        assert run(timing, prefs, 1) == [HUNT_A]


class TestGoalTimingAbandon:
    def test_decides_afresh_after_abandoning_its_goal(self) -> None:
        timing = GoalTiming(decision_frames=10, reaction_frames=0, stickiness_frames=1)
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        timing.abandon()
        assert timing.decided is None
        prefs.preferred = HUNT_B
        assert run(timing, prefs, 1) == [HUNT_B]

    def test_keeps_a_newer_goal_it_is_still_reacting_to(self) -> None:
        timing = GoalTiming(decision_frames=1, reaction_frames=2, stickiness_frames=1)
        prefs = Preferences(HUNT_A)
        acting_on(timing, prefs, HUNT_A)
        prefs.preferred = HUNT_B
        assert run(timing, prefs, 1) == [HUNT_A]
        timing.abandon()
        assert timing.decided == HUNT_B
        assert run(timing, prefs, 2) == [None, HUNT_B]
