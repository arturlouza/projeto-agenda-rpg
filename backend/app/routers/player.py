from fastapi import APIRouter
from sqlmodel import SQLModel, func, select

from app.models import XpEntry
from app.routers.task_types import SessionDep
from app.rules.xp import level_progress, progress_percent, xp_to_next_level

router = APIRouter(prefix="/player", tags=["player"])


# O que a API devolve sobre o jogador: XP total, nível e barra (seção 6.2).
class Player(SQLModel):
    total_xp: int
    level: int
    xp_into_level: int
    xp_for_next_level: int
    progress_percent: int


# Só lê o banco, então pode ser GET (seção 6.7). As contas ficam em rules/xp.py.
@router.get("")
def get_player(session: SessionDep) -> Player:
    # A soma de nenhuma linha vem do banco como None, e o histórico vazio vale 0.
    total_xp = session.exec(select(func.sum(XpEntry.amount))).one() or 0
    level, xp_into_level = level_progress(total_xp)
    xp_for_next_level = xp_to_next_level(level)

    return Player(
        total_xp=total_xp,
        level=level,
        xp_into_level=xp_into_level,
        xp_for_next_level=xp_for_next_level,
        progress_percent=progress_percent(xp_into_level, xp_for_next_level),
    )
