from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import ConfigDict, StringConstraints, field_validator
from sqlmodel import Session, SQLModel, and_, or_, select

from app.dates import app_day_bounds, app_today, week_days
from app.models import DEFAULT_TASK_COLOR, Task, TaskType
from app.routers.task_types import MAX_ID, SessionDep

# Tamanhos máximos, contados depois de remover os espaços das pontas.
MAX_TASK_TITLE_LENGTH = 100
MAX_TASK_NOTES_LENGTH = 1000

# Cor no formato #RRGGBB, com letras maiúsculas ou minúsculas.
TASK_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

# Dificuldades aceitas. Precisam ser as mesmas chaves de TASK_BASE_XP, em rules/xp.py.
Difficulty = Literal["easy", "medium", "hard"]

router = APIRouter(prefix="/tasks", tags=["tasks"])


# O que a API recebe ao criar uma tarefa. É separada de Task porque modelos com table=True
# não validam os dados. A data não é conferida aqui porque a regra vale só para data nova,
# e a edição não pode recusar uma tarefa atrasada por causa da data que não mudou.
class TaskInput(SQLModel):
    # Campo desconhecido é recusado, então o pedido não escolhe postponements nem completed.
    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TASK_TITLE_LENGTH),
    ]
    notes: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=MAX_TASK_NOTES_LENGTH)
    ] | None = None
    due_date: date
    difficulty: Difficulty
    color: Annotated[
        str, StringConstraints(pattern=TASK_COLOR_PATTERN, to_upper=True)
    ] = DEFAULT_TASK_COLOR
    task_type_id: int | None = None

    # Roda depois de tirar os espaços, então notas só com espaços também viram None.
    @field_validator("notes")
    @classmethod
    def empty_notes_become_none(cls, notes: str | None) -> str | None:
        return notes or None


# O que a API devolve ao listar um dia: os três grupos da visão do dia (seção 6.2).
class DayTasks(SQLModel):
    overdue: list[Task]
    pending: list[Task]
    completed: list[Task]


# Um dia da visão da semana: pendentes e concluídas ficam na mesma lista (seção 6.2).
class WeekDay(SQLModel):
    day: date
    tasks: list[Task]


# Responde 422 se o tipo não existir. O intervalo é conferido antes de consultar o banco,
# porque um id gigante daria erro ao chegar lá, e o pedido viraria um erro 500.
def ensure_task_type_exists(session: Session, task_type_id: int) -> None:
    if not 1 <= task_type_id <= MAX_ID or session.get(TaskType, task_type_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Esse tipo de tarefa não existe."
        )


# Filtro das tarefas pendentes de um dia: a pendente aparece no dia marcado. O "== False" é
# de propósito: o SQLModel transforma essa comparação em SQL, e "not Task.completed" não
# seria transformado.
def pending_on(day: date):
    return and_(Task.completed == False, Task.due_date == day)


# Filtro das tarefas concluídas de um dia: a concluída aparece no dia em que foi concluída
# em Brasília, não no dia marcado.
def completed_on(day: date):
    day_start, day_end = app_day_bounds(day)
    return and_(
        Task.completed == True,
        Task.completed_at >= day_start,
        Task.completed_at < day_end,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(task_input: TaskInput, session: SessionDep) -> Task:
    if task_input.due_date < app_today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A data não pode ser anterior a hoje."
        )

    if task_input.task_type_id is not None:
        ensure_task_type_exists(session, task_input.task_type_id)

    task = Task(
        title=task_input.title,
        notes=task_input.notes,
        due_date=task_input.due_date,
        difficulty=task_input.difficulty,
        color=task_input.color,
        task_type_id=task_input.task_type_id,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


# As atrasadas só vêm na visão de hoje.
@router.get("/day/{day}")
def list_tasks_by_day(day: date, session: SessionDep) -> DayTasks:
    overdue = []
    if day == app_today():
        overdue = session.exec(
            select(Task)
            .where(Task.completed == False, Task.due_date < day)
            .order_by(Task.due_date, Task.created_at, Task.id)
        ).all()

    pending = session.exec(
        select(Task).where(pending_on(day)).order_by(Task.created_at, Task.id)
    ).all()

    completed = session.exec(
        select(Task).where(completed_on(day)).order_by(Task.created_at, Task.id)
    ).all()

    return DayTasks(overdue=overdue, pending=pending, completed=completed)


# Faz uma consulta por dia, com os mesmos filtros da visão do dia. Aqui não há atrasadas:
# a tarefa atrasada aparece no dia marcado dela.
@router.get("/week/{day}")
def list_tasks_by_week(day: date, session: SessionDep) -> list[WeekDay]:
    week = []
    for week_day in week_days(day):
        tasks = session.exec(
            select(Task)
            .where(or_(pending_on(week_day), completed_on(week_day)))
            .order_by(Task.created_at, Task.id)
        ).all()
        week.append(WeekDay(day=week_day, tasks=tasks))

    return week
