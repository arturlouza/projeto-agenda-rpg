from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import utc_now

# Fuso usado em todo cálculo de "que dia é" (seção 6.4 da especificação).
APP_TIMEZONE = "America/Sao_Paulo"


# Descobre em que dia de Brasília caiu uma data e hora. Sem fuso, ela é tratada como UTC.
def to_app_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return moment.astimezone(ZoneInfo(APP_TIMEZONE)).date()


# Devolve o dia de hoje em Brasília.
def app_today() -> date:
    return to_app_date(utc_now())


# Devolve, em UTC, o instante em que um dia começa em Brasília. O fuso real decide a conta,
# porque em dias de horário de verão a diferença para o UTC não é de 3 horas.
def app_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(APP_TIMEZONE)).astimezone(timezone.utc)


# Devolve, em UTC, o início de um dia de Brasília e o início do dia seguinte. O início faz
# parte do dia e o fim não, então nenhum instante cai em dois dias nem fica sem dia.
def app_day_bounds(day: date) -> tuple[datetime, datetime]:
    # O dia seguinte a 9999-12-31 não existe no Python e daria OverflowError. Nesse dia,
    # o fim é o maior horário que o Python consegue representar.
    if day == date.max:
        return app_midnight(day), datetime.max.replace(tzinfo=timezone.utc)

    return app_midnight(day), app_midnight(day + timedelta(days=1))


# Devolve o dia anterior e o seguinte. O Python não representa dia antes de 0001-01-01 nem
# depois de 9999-12-31: nessas pontas, o vizinho que não existe vem como None, em vez de
# OverflowError.
def adjacent_days(day: date) -> tuple[date | None, date | None]:
    previous_day = None if day == date.min else day - timedelta(days=1)
    next_day = None if day == date.max else day + timedelta(days=1)
    return previous_day, next_day


# Devolve os dias da semana de uma data, de segunda a domingo. weekday() dá 0 na segunda
# e 6 no domingo. A última semana do calendário termina em 9999-12-31, uma sexta-feira,
# então ela tem só 5 dias: somar um dia a essa data daria OverflowError.
def week_days(day: date) -> list[date]:
    days = [day - timedelta(days=day.weekday())]
    while len(days) < 7 and days[-1] != date.max:
        days.append(days[-1] + timedelta(days=1))

    return days
