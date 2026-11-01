from datetime import date

import pytest

from app.rules.xp import (
    effective_postponements,
    is_due_date_locked,
    level_from_total_xp,
    postponements_after_date_change,
    task_xp,
    xp_to_next_level,
)


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


# Concluir antes do dia marcado vale 100%: atraso negativo conta como 0.
def test_task_xp_treats_negative_days_late_as_zero():
    assert task_xp("hard", 0, -1) == 50


# Exatamente 3 adiamentos valem 25%, mesmo com a data 5 dias à frente.
def test_task_xp_with_three_postponements_and_future_date_is_25_percent():
    assert task_xp("hard", 3, -5) == 12


def test_task_xp_is_zero_with_three_postponements_and_one_day_late():
    assert task_xp("hard", 3, 1) == 0


def test_effective_postponements_adds_days_late():
    assert effective_postponements(1, 2) == 3


def test_effective_postponements_ignores_negative_days_late():
    assert effective_postponements(2, -5) == 2


@pytest.mark.parametrize(
    "manual_postponements, days_late",
    [
        (2, 0),
        (1, 1),
        (2, -5),
    ],
)
def test_due_date_is_not_locked_below_three_effective_postponements(manual_postponements, days_late):
    assert is_due_date_locked(manual_postponements, days_late) is False


@pytest.mark.parametrize(
    "manual_postponements, days_late",
    [
        (3, 0),
        (0, 3),
        (1, 2),
        (4, 0),
    ],
)
def test_due_date_is_locked_from_three_effective_postponements(manual_postponements, days_late):
    assert is_due_date_locked(manual_postponements, days_late) is True


# Exemplo da seção 4.2: sem o atraso nunca negativo, 3 − 5 = −2 destravaria a data.
def test_due_date_stays_locked_with_three_postponements_and_future_date():
    assert is_due_date_locked(3, -5) is True


@pytest.mark.parametrize(
    "manual_postponements, expected_postponements",
    [
        (0, 1),
        (1, 2),
        (2, 3),
    ],
)
def test_moving_date_later_counts_one_postponement(manual_postponements, expected_postponements):
    result = postponements_after_date_change(
        manual_postponements, 0, date(2026, 11, 1), date(2026, 11, 2)
    )
    assert result == expected_postponements


# Exemplo da seção 4.2: 0 adiamentos e 2 dias de atraso dão 0 + 2 + 1 = 3.
def test_moving_late_task_to_today_adds_days_late_to_counter():
    result = postponements_after_date_change(0, 2, date(2026, 10, 30), date(2026, 11, 1))
    assert result == 3


def test_moving_future_date_later_ignores_negative_days_late():
    result = postponements_after_date_change(1, -5, date(2026, 11, 6), date(2026, 11, 10))
    assert result == 2


def test_moving_date_earlier_does_not_count():
    result = postponements_after_date_change(1, -5, date(2026, 11, 6), date(2026, 11, 3))
    assert result == 1


# Mandar a mesma data não é mudança: os dias de atraso não entram no contador.
def test_same_date_on_late_task_does_not_change_counter():
    result = postponements_after_date_change(0, 2, date(2026, 10, 30), date(2026, 10, 30))
    assert result == 0


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
