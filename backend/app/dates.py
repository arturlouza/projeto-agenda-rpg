from datetime import date, datetime, timezone
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
