from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel

# Cor de fundo do cartão quando nenhuma outra é escolhida (tom de pergaminho).
DEFAULT_TASK_COLOR = "#F5E6C8"


# Devolve a data e a hora atuais em UTC, para gravar quando algo aconteceu.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Etiqueta livre que diz o que a tarefa é: Leitura, Treino, Estudo.
class TaskType(SQLModel, table=True):
    # Faz o SQLite não reaproveitar o id de uma linha excluída, como o PostgreSQL. Só o SQLite
    # lê esta opção; no PostgreSQL ela não tem efeito (seção 6.6 da especificação).
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)


# Campos da tarefa. Ficam numa classe sem tabela para a resposta da visão do dia (TaskView, em
# routers/tasks.py) reaproveitar os mesmos campos sem repetir a lista. A tabela continua igual:
# Task herda tudo daqui, na mesma ordem.
class TaskBase(SQLModel):
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


# Algo a fazer num dia. Os campos vêm de TaskBase; aqui fica só o que transforma a classe em
# tabela do banco.
class Task(TaskBase, table=True):
    # Mesmo motivo do TaskType.
    __table_args__ = {"sqlite_autoincrement": True}


# Uma linha do histórico de XP. O XP total é a soma de todas as linhas.
class XpEntry(SQLModel, table=True):
    # Mesmo motivo do TaskType.
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    amount: int
    reason: str
    task_id: int | None = Field(default=None, foreign_key="task.id")
    created_at: datetime = Field(default_factory=utc_now)
