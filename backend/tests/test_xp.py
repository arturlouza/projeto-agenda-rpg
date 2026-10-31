import pytest

from app.rules.xp import level_from_total_xp, task_xp, xp_to_next_level


# Cada linha é um caso: dificuldade, adiamentos e o XP esperado (sempre arredondado para baixo).
@pytest.mark.parametrize(
    "difficulty, postponements, expected_xp",
    [
        ("easy", 0, 10),
        ("easy", 1, 7),
        ("easy", 2, 5),
        ("easy", 3, 2),
        ("medium", 0, 25),
        ("medium", 1, 18),
        ("medium", 2, 12),
        ("medium", 3, 6),
        ("hard", 0, 50),
        ("hard", 1, 37),
        ("hard", 2, 25),
        ("hard", 3, 12),
    ],
)
def test_task_xp_applies_penalty_and_rounds_down(difficulty, postponements, expected_xp):
    assert task_xp(difficulty, postponements, 0) == expected_xp


# Adiamento manual e dia de atraso contam da mesma forma.
def test_task_xp_adds_days_late_to_manual_postponements():
    assert task_xp("hard", 1, 2) == 12


def test_task_xp_is_zero_when_postponements_and_days_late_exceed_limit():
    assert task_xp("hard", 2, 2) == 0


@pytest.mark.parametrize("days_late", [4, 10])
def test_task_xp_is_zero_when_only_days_late_exceed_limit(days_late):
    assert task_xp("hard", 0, days_late) == 0


# Números da tabela 4.5 da especificação.
@pytest.mark.parametrize(
    "level, expected_xp",
    [
        (1, 100),
        (10, 154),
        (30, 412),
        (50, 786),
        (75, 1373),
        (99, 2040),
        (100, 2070),
    ],
)
def test_xp_to_next_level_matches_spec_table(level, expected_xp):
    assert xp_to_next_level(level) == expected_xp


@pytest.mark.parametrize("level", [101, 500])
def test_xp_to_next_level_stops_growing_after_level_100(level):
    assert xp_to_next_level(level) == 2070


@pytest.mark.parametrize(
    "total_xp, expected_level",
    [
        (0, 1),
        (99, 1),
        (100, 2),
        (201, 2),
        (202, 3),
    ],
)
def test_level_from_total_xp_at_start(total_xp, expected_level):
    assert level_from_total_xp(total_xp) == expected_level


@pytest.mark.parametrize(
    "total_xp, expected_level",
    [
        (86927, 99),
        (86928, 100),
    ],
)
def test_level_from_total_xp_reaches_level_100(total_xp, expected_level):
    assert level_from_total_xp(total_xp) == expected_level


@pytest.mark.parametrize(
    "total_xp, expected_level",
    [
        (88997, 100),
        (88998, 101),
    ],
)
def test_level_from_total_xp_continues_after_level_100(total_xp, expected_level):
    assert level_from_total_xp(total_xp) == expected_level
