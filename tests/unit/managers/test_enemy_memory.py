from src.managers.enemy_memory import EnemyMemory


class TestEnemyMemory:
    def test_remembers_a_value_per_enemy(self) -> None:
        memory: EnemyMemory[str] = EnemyMemory()
        memory.remember(1, (3, 4), "left")
        assert 1 in memory
        assert memory.get(1) == "left"
        assert 2 not in memory
        assert memory.get(2) is None

    def test_forgets_an_enemy_that_moves(self) -> None:
        memory: EnemyMemory[None] = EnemyMemory()
        memory.remember(1, (3, 4), None)
        memory.expire({1: (3, 5)})
        assert 1 not in memory

    def test_forgets_an_enemy_that_is_gone(self) -> None:
        memory: EnemyMemory[None] = EnemyMemory()
        memory.remember(1, (3, 4), None)
        memory.remember(2, (8, 8), None)
        memory.expire({2: (8, 8)})
        assert 1 not in memory
        assert 2 in memory
