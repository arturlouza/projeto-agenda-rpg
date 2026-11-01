from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel

# Cor de fundo do cartão quando nenhuma outra é escolhida (tom de pergaminho).
DEFAULT_TASK_COLOR = "#F5E6C8"


# Devolve a data e a hora atuais em UTC, para gravar quando algo aconteceu.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Etiqueta livre que diz o que a tarefa é: Leitura, Treino, Estudo.
class TaskType(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


# Algo a fazer num dia.
class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    notes: str | None = None
    due_date: date
    difficulty: str
    color: str = DEFAULT_TASK_COLOR
    task_type_id: int | None = Field(default=None, foreign_key="tasktype.id")
    completed: bool = False
    completed_at: datetime | None = None
    postponements: int = 0
    created_at: datetime = Field(default_factory=utc_now)


# Uma linha do histórico de XP. O XP total é a soma de todas as linhas.
class XpEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    amount: int
    reason: str
    task_id: int | None = Field(default=None, foreign_key="task.id")
    created_at: datetime = Field(default_factory=utc_now)
