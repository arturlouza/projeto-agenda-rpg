from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import ConfigDict, StringConstraints, field_validator
from sqlmodel import Session, SQLModel, and_, or_, select, update

from app.dates import app_day_bounds, app_today, week_days
from app.models import DEFAULT_TASK_COLOR, Task, TaskType, XpEntry, utc_now
from app.routers.task_types import MAX_ID, SessionDep
from app.rules.xp import (
    completion_reason,
    is_due_date_locked,
    postponements_after_date_change,
    task_xp,
    uncompletion_reason,
    xp_to_refund,
)

# Tamanhos máximos, contados depois de remover os espaços das pontas.
MAX_TASK_TITLE_LENGTH = 100
MAX_TASK_NOTES_LENGTH = 1000

# Cor no formato #RRGGBB, com letras maiúsculas ou minúsculas.
TASK_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

# Dificuldades aceitas. Precisam ser as mesmas chaves de TASK_BASE_XP, em rules/xp.py.
Difficulty = Literal["easy", "medium", "hard"]

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Id que vem na rota. Fora deste intervalo, o FastAPI responde 422 sem consultar o banco.
TaskId = Annotated[int, Path(ge=1, le=MAX_ID)]


# Regras de cada campo de texto, usadas tanto ao criar quanto ao editar.
TaskTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TASK_TITLE_LENGTH),
]
TaskNotes = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=MAX_TASK_NOTES_LENGTH)
]
TaskColor = Annotated[str, StringConstraints(pattern=TASK_COLOR_PATTERN, to_upper=True)]


# O que a API recebe ao editar uma tarefa. É separada de Task porque modelos com table=True
# não validam os dados. Nenhum campo tem valor padrão, então todos são obrigatórios: esquecer
# um campo dá 422, em vez de apagar as notas ou voltar a cor ao padrão. Notas e tipo aceitam
# null, que é o jeito de remover o valor de propósito. A data não é conferida aqui porque a
# regra vale só para data nova, e a edição não pode recusar uma tarefa atrasada por causa da
# data que não mudou.
class TaskUpdate(SQLModel):
    # Campo desconhecido é recusado, então o pedido não escolhe postponements nem completed.
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle
    notes: TaskNotes | None
    difficulty: Difficulty
    color: TaskColor
    task_type_id: int | None
    due_date: date

    # Roda depois de tirar os espaços, então notas só com espaços também viram None.
    @field_validator("notes")
    @classmethod
    def empty_notes_become_none(cls, notes: str | None) -> str | None:
        return notes or None


# O que a API recebe ao criar uma tarefa: as mesmas regras da edição, mais os valores padrão.
class TaskInput(TaskUpdate):
    notes: TaskNotes | None = None
    color: TaskColor = DEFAULT_TASK_COLOR
    task_type_id: int | None = None


# O que a API devolve ao listar um dia: os três grupos da visão do dia (seção 6.2).
class DayTasks(SQLModel):
    overdue: list[Task]
    pending: list[Task]
    completed: list[Task]


# Um dia da visão da semana: pendentes e concluídas ficam na mesma lista (seção 6.2).
class WeekDay(SQLModel):
    day: date
    tasks: list[Task]


# O que a API devolve ao concluir ou desmarcar: a tarefa e quanto o XP total mudou.
class TaskXpChange(SQLModel):
    task: Task
    xp_change: int


# Busca a tarefa pelo id e responde 404 se ela não existir.
def get_task_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tarefa não encontrada.")
    return task


# Responde 422 se o tipo não existir. O intervalo é conferido antes de consultar o banco,
# porque um id gigante daria erro ao chegar lá, e o pedido viraria um erro 500.
def ensure_task_type_exists(session: Session, task_type_id: int) -> None:
    if not 1 <= task_type_id <= MAX_ID or session.get(TaskType, task_type_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Esse tipo de tarefa não existe."
        )


# Responde 422 se a data for anterior a hoje em Brasília. Vale só para data nova.
def ensure_date_is_not_past(day: date) -> None:
    if day < app_today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A data não pode ser anterior a hoje."
        )


# Muda a data de uma tarefa, para a edição e para o botão Adiar (tarefa 7). Quem chama já
# conferiu que a data é outra e que não é anterior a hoje. A trava vem antes do contador,
# porque postponements_after_date_change não a confere. Os dias de atraso podem sair negativos
# aqui, com a data no futuro: as regras de xp.py tratam esse valor como 0.
def change_due_date(task: Task, new_due_date: date) -> None:
    if task.completed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a data."
        )

    days_late = (app_today() - task.due_date).days

    if is_due_date_locked(task.postponements, days_late):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A data desta tarefa está travada e não pode mudar."
        )

    task.postponements = postponements_after_date_change(
        task.postponements, days_late, task.due_date, new_due_date
    )
    task.due_date = new_due_date


# Muda o estado numa instrução só, que vale apenas se a tarefa ainda estiver no estado oposto.
# Dois pedidos ao mesmo tempo, como num toque duplo, não passam os dois: o segundo encontra 0
# linhas para mudar e recebe 409. Conferir task.completed em Python não protegeria, porque o
# valor lido pode já estar velho. Quem chama lê o resto da tarefa e do histórico depois daqui
# e ainda precisa fazer o commit.
def change_completed(
    session: Session, task: Task, completed: bool, completed_at: datetime | None, refusal: str
) -> None:
    changed_rows = session.exec(
        update(Task)
        .where(Task.id == task.id, Task.completed != completed)
        .values(completed=completed, completed_at=completed_at)
    ).rowcount

    if changed_rows == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=refusal)

    session.refresh(task)


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
    ensure_date_is_not_past(task_input.due_date)

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


# O dado é conferido antes do estado da tarefa, então os 422 da data e do tipo vêm antes dos
# 409. A tarefa só é alterada depois de todas as conferências, e por isso o pedido recusado
# não grava nada.
@router.put(
    "/{task_id}",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {
            "description": (
                "A tarefa concluída não pode mudar de dificuldade nem de data, "
                "e a tarefa travada não pode mudar de data."
            )
        },
    },
)
def update_task(task_id: TaskId, task_update: TaskUpdate, session: SessionDep) -> Task:
    task = get_task_or_404(session, task_id)

    # Mandar a data que a tarefa já tem não é mudança, então nenhuma regra de data se aplica.
    date_changed = task_update.due_date != task.due_date

    if date_changed:
        ensure_date_is_not_past(task_update.due_date)

    if task_update.task_type_id is not None:
        ensure_task_type_exists(session, task_update.task_type_id)

    if task.completed and task_update.difficulty != task.difficulty:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a dificuldade."
        )

    if date_changed:
        change_due_date(task, task_update.due_date)

    task.title = task_update.title
    task.notes = task_update.notes
    task.difficulty = task_update.difficulty
    task.color = task_update.color
    task.task_type_id = task_update.task_type_id
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


# O XP já ganho continua no histórico: as linhas da tarefa só perdem o vínculo com ela (seção
# 4.3). Tudo vale só no commit, numa única transação: se algo falhar no meio, nada muda no banco.
@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Tarefa não encontrada."}},
)
def delete_task(task_id: TaskId, session: SessionDep) -> None:
    task = get_task_or_404(session, task_id)

    for entry in session.exec(select(XpEntry).where(XpEntry.task_id == task_id)).all():
        entry.task_id = None
        session.add(entry)

    # Envia as mudanças do histórico antes de excluir a tarefa, senão a chave estrangeira
    # poderia recusar a exclusão.
    session.flush()

    session.delete(task)
    session.commit()


# Os dias de atraso usam o dia de Brasília e podem sair negativos, com a data no futuro: as
# regras de xp.py tratam esse valor como 0. A tarefa e a linha de XP valem só no commit, numa
# única transação: se algo falhar no meio, nada muda no banco.
@router.post(
    "/{task_id}/complete",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {"description": "A tarefa já está concluída."},
    },
)
def complete_task(task_id: TaskId, session: SessionDep) -> TaskXpChange:
    task = get_task_or_404(session, task_id)
    change_completed(session, task, True, utc_now(), "A tarefa já está concluída.")

    days_late = (app_today() - task.due_date).days
    amount = task_xp(task.difficulty, task.postponements, days_late)
    session.add(XpEntry(amount=amount, reason=completion_reason(task.title), task_id=task_id))
    session.commit()
    session.refresh(task)
    return TaskXpChange(task=task, xp_change=amount)


# A devolução vem do histórico, não de uma conta nova, porque os dias de atraso mudam com o
# tempo. Vale a mesma transação única de complete_task.
@router.post(
    "/{task_id}/uncomplete",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {"description": "A tarefa já está pendente."},
    },
)
def uncomplete_task(task_id: TaskId, session: SessionDep) -> TaskXpChange:
    task = get_task_or_404(session, task_id)
    change_completed(session, task, False, None, "A tarefa já está pendente.")

    earned_amounts = session.exec(select(XpEntry.amount).where(XpEntry.task_id == task_id)).all()
    amount = xp_to_refund(earned_amounts)
    session.add(XpEntry(amount=amount, reason=uncompletion_reason(task.title), task_id=task_id))
    session.commit()
    session.refresh(task)
    return TaskXpChange(task=task, xp_change=amount)
