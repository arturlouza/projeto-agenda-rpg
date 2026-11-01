from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.dates import APP_TIMEZONE, app_today, to_app_date


# O exemplo da seção 6.4: concluída às 22h30 de 31/10 em Brasília, gravada como 01h30 UTC.
def test_to_app_date_converts_utc_to_brasilia():
    moment = datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc)

    assert to_app_date(moment) == date(2026, 10, 31)


def test_to_app_date_treats_naive_datetime_as_utc():
    moment = datetime(2026, 11, 1, 1, 30)

    assert to_app_date(moment) == date(2026, 10, 31)


# Uma data que já veio com fuso não pode ser reinterpretada como UTC.
def test_to_app_date_keeps_timezone_already_in_the_datetime():
    moment = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo(APP_TIMEZONE))

    assert to_app_date(moment) == date(2026, 11, 1)


# Em 01/12/2018 havia horário de verão: em Brasília eram 00h30, com offset -2.
# Um -3 fixo daria 23h30 de 30/11, então este caso prova que o fuso real é usado.
def test_to_app_date_uses_real_timezone_during_2018_daylight_saving():
    moment = datetime(2018, 12, 1, 2, 30, tzinfo=timezone.utc)

    assert to_app_date(moment) == date(2018, 12, 1)


# Cada linha é um caso: a hora fixa em UTC e o dia esperado em Brasília.
# O "hoje" vira às 03h00 UTC, que é a meia-noite de Brasília, e não às 00h00 UTC.
@pytest.mark.parametrize(
    "fixed_now, expected_today",
    [
        (datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc), date(2026, 10, 31)),
        (datetime(2026, 11, 1, 2, 59, 59, tzinfo=timezone.utc), date(2026, 10, 31)),
        (datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc), date(2026, 11, 1)),
    ],
)
def test_app_today_turns_at_brasilia_midnight(fixed_now, expected_today, monkeypatch):
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)

    assert app_today() == expected_today
