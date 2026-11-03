from datetime import date

import pytest

from app.rules import xp as xp_rules
from app.rules.xp import (
    POSTPONE_DAYS,
    completion_reason,
    effective_postponements,
    is_due_date_locked,
    level_progress,
    postponed_due_date,
    postponements_after_date_change,
    progress_percent,
    task_xp,
    uncompletion_reason,
    xp_to_next_level,
    xp_to_refund,
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


def test_postpone_moves_one_day():
    assert POSTPONE_DAYS == 1


# Cada linha é um caso: data marcada, hoje e a data nova. "Sempre amanhã" foi descartado porque,
# numa data futura, viraria antecipar.
@pytest.mark.parametrize(
    "due_date, today, expected",
    [
        (date(2026, 11, 10), date(2026, 11, 1), date(2026, 11, 11)),
        (date(2026, 11, 2), date(2026, 11, 1), date(2026, 11, 3)),
        (date(2026, 11, 1), date(2026, 11, 1), date(2026, 11, 2)),
        (date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2)),
        (date(2026, 10, 30), date(2026, 11, 1), date(2026, 11, 2)),
        (date(2026, 12, 31), date(2026, 12, 31), date(2027, 1, 1)),
        (date(9999, 12, 30), date(2026, 11, 1), date(9999, 12, 31)),
    ],
)
def test_postponed_due_date_is_one_day_after_the_later_of_due_date_and_today(
    due_date, today, expected
):
    assert postponed_due_date(due_date, today) == expected


# Somar um dia a 9999-12-31 daria OverflowError, e o pedido viraria um erro 500.
def test_postponed_due_date_has_no_day_after_the_last_date():
    assert postponed_due_date(date.max, date(2026, 11, 1)) is None


# É por isto que a rota do Adiar não precisa conferir se a data nova é anterior a hoje.
@pytest.mark.parametrize(
    "due_date",
    [date.min, date(2026, 10, 30), date(2026, 11, 1), date(2026, 11, 2), date(9999, 12, 30)],
)
def test_postponed_due_date_is_always_after_today(due_date):
    today = date(2026, 11, 1)

    assert postponed_due_date(due_date, today) > today


# Cada linha é um histórico de tarefa concluída e o valor que desmarcar grava. A última mostra
# vários ciclos: só o ganho da conclusão atual ainda não foi devolvido.
@pytest.mark.parametrize(
    "earned_amounts, expected_refund",
    [
        ([], 0),
        ([0], 0),
        ([25], -25),
        ([25, -25], 0),
        ([25, -25, 18], -18),
    ],
)
def test_xp_to_refund_is_the_negative_of_the_sum(earned_amounts, expected_refund):
    assert xp_to_refund(earned_amounts) == expected_refund


def test_completion_reason_has_the_task_title():
    assert completion_reason("Ler 30 páginas") == "Tarefa concluída: Ler 30 páginas"


def test_uncompletion_reason_has_the_task_title():
    assert uncompletion_reason("Ler 30 páginas") == "Tarefa desmarcada: Ler 30 páginas"


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


# Cada linha é um caso: XP total, o nível e o XP já acumulado dentro dele.
@pytest.mark.parametrize(
    "total_xp, expected_level, expected_xp_into_level",
    [
        (0, 1, 0),
        (99, 1, 99),
        (100, 2, 0),
        (201, 2, 101),
        (202, 3, 0),
    ],
)
def test_level_progress_at_start(total_xp, expected_level, expected_xp_into_level):
    assert level_progress(total_xp) == (expected_level, expected_xp_into_level)


# 86.928 é o total exato para chegar ao nível 100.
@pytest.mark.parametrize(
    "total_xp, expected_level, expected_xp_into_level",
    [
        (86927, 99, 2039),
        (86928, 100, 0),
        (86929, 100, 1),
    ],
)
def test_level_progress_reaches_level_100(total_xp, expected_level, expected_xp_into_level):
    assert level_progress(total_xp) == (expected_level, expected_xp_into_level)


@pytest.mark.parametrize(
    "total_xp, expected_level, expected_xp_into_level",
    [
        (88997, 100, 2069),
        (88998, 101, 0),
    ],
)
def test_level_progress_continues_after_level_100(total_xp, expected_level, expected_xp_into_level):
    assert level_progress(total_xp) == (expected_level, expected_xp_into_level)


# Pelas regras a soma não fica negativa, mas, se ficar, o nível e a barra tratam como 0.
@pytest.mark.parametrize("total_xp", [-1, -50])
def test_level_progress_treats_negative_total_as_zero(total_xp):
    assert level_progress(total_xp) == (1, 0)


# Depois do nível 100, cada 2.070 XP a mais é exatamente um nível a mais.
@pytest.mark.parametrize("extra_levels", [1, 2, 10, 1000])
def test_each_2070_xp_after_level_100_is_one_level(extra_levels):
    assert level_progress(86928 + extra_levels * 2070) == (100 + extra_levels, 0)


# Conta do jeito antigo, pagando um nível de cada vez, sem a divisão depois do nível 100. Só
# serve para comparar com level_progress em totais pequenos, onde ela ainda é rápida.
def level_progress_one_level_at_a_time(total_xp):
    level = 1
    remaining_xp = total_xp

    while remaining_xp >= xp_to_next_level(level):
        remaining_xp -= xp_to_next_level(level)
        level += 1

    return level, remaining_xp


def test_level_progress_matches_paying_one_level_at_a_time():
    for total_xp in range(86000, 100001, 7):
        assert level_progress(total_xp) == level_progress_one_level_at_a_time(total_xp)


# Um total enorme dá o nível certo e chama xp_to_next_level no máximo 199 vezes (2 por volta
# nos 99 primeiros níveis, mais 1 da divisão). O contador falha logo na chamada 200: se a
# conta voltar a pagar nível por nível, o teste falha na hora em vez de travar por horas.
def test_level_progress_with_huge_total_is_fast_and_right(monkeypatch):
    calls = 0
    original = xp_rules.xp_to_next_level

    def counting_xp_to_next_level(level):
        nonlocal calls
        calls += 1
        if calls >= 200:
            pytest.fail("level_progress chamou xp_to_next_level 200 vezes")
        return original(level)

    monkeypatch.setattr(xp_rules, "xp_to_next_level", counting_xp_to_next_level)

    assert level_progress(10**15) == (483_091_787_497, 1282)


# Cada linha é um caso: XP dentro do nível, custo do nível e a porcentagem, sempre para baixo.
@pytest.mark.parametrize(
    "xp_into_level, xp_for_next_level, expected_percent",
    [
        (0, 100, 0),
        (99, 100, 99),
        (20, 102, 19),
        (1, 2070, 0),
        (2069, 2070, 99),
        (2039, 2040, 99),
    ],
)
def test_progress_percent_rounds_down(xp_into_level, xp_for_next_level, expected_percent):
    assert progress_percent(xp_into_level, xp_for_next_level) == expected_percent


# Com a conta de números quebrados, 29 / 100 * 100 dá 28.999999999999996, e a barra mostraria 28%.
def test_progress_percent_uses_only_whole_numbers():
    assert progress_percent(29, 100) == 29


# Em todos os níveis de 1 a 110: no último XP antes de subir, o nível não mudou e a barra está
# em 99% ou menos; no XP seguinte, o nível sobe e a barra volta a 0%.
def test_bar_never_shows_100_percent_before_leveling_up():
    level_start_xp = 0

    for level in range(1, 111):
        last_xp_before = level_start_xp + xp_to_next_level(level) - 1

        level_before, xp_into_level_before = level_progress(last_xp_before)
        assert level_before == level
        assert progress_percent(xp_into_level_before, xp_to_next_level(level)) <= 99

        level_after, xp_into_level_after = level_progress(last_xp_before + 1)
        assert level_after == level + 1
        assert progress_percent(xp_into_level_after, xp_to_next_level(level + 1)) == 0

        level_start_xp += xp_to_next_level(level)
