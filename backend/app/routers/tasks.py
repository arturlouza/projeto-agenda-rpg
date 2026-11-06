from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import ConfigDict, StringConstraints, field_validator
from sqlmodel import Session, SQLModel, and_, col, func, or_, select, update

from app.dates import adjacent_days, app_day_bounds, app_today, week_days
from app.models import DEFAULT_TASK_COLOR, Task, TaskBase, TaskType, XpEntry, utc_now
from app.routers.task_types import MAX_ID, SessionDep
from app.rules.xp import (
    completion_reason,
    is_due_date_locked,
    postponed_due_date,
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

# Resposta do Adiar e da edição quando a tarefa não está mais como a tela a mostrava.
STALE_TASK_MESSAGE = "A tarefa mudou desde que a tela foi aberta. Atualize a lista."

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


# Os campos que a tela manda ao criar e ao editar, com as regras de cada um. É separada de Task
# porque modelos com table=True não validam os dados. Aqui nenhum campo tem valor padrão. Notas e
# tipo aceitam null, que é o jeito de remover o valor de propósito. A data não é conferida aqui
# porque a regra vale só para data nova, e a edição não pode recusar uma tarefa atrasada por
# causa da data que não mudou.
class TaskFields(SQLModel):
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


# O que a API recebe ao criar uma tarefa: os mesmos campos, mais os valores padrão.
class TaskInput(TaskFields):
    notes: TaskNotes | None = None
    color: TaskColor = DEFAULT_TASK_COLOR
    task_type_id: int | None = None


# O que a API recebe ao editar uma tarefa. Todos os campos são obrigatórios: esquecer um dá 422,
# em vez de apagar as notas ou voltar a cor ao padrão. shown_due_date é a data que o formulário
# mostrava, como no Adiar: se a tarefa não tiver mais essa data, a tela estava desatualizada.
class TaskUpdate(TaskFields):
    shown_due_date: date


# O que a API recebe ao adiar: a data que a tela mostrava. A data nova é o servidor quem
# calcula. Um toque duplo manda duas vezes a mesma data, e o segundo pedido é recusado.
class TaskPostpone(SQLModel):
    model_config = ConfigDict(extra="forbid")

    shown_due_date: date


# Uma tarefa como a visão do dia a recebe: todos os campos da tarefa, mais o que a tela não pode
# calcular sozinha, porque são regras do servidor (regra 9 do CLAUDE.md).
class TaskView(TaskBase):
    # Se a data está travada agora (seção 4.2). Na concluída, diz se ela voltaria travada ao
    # ser desmarcada; a tela não usa o campo nesse caso.
    due_date_locked: bool
    # Soma das linhas da tarefa no histórico: o XP que a concluída rendeu, 0 na pendente (4.3).
    xp_earned: int


# O que a API devolve ao listar um dia: a data listada, se ela é hoje em Brasília, os dias
# vizinhos para a tela navegar sem fazer conta de data, e os três grupos da visão do dia (seção
# 6.2). previous_day e next_day vêm como null quando o dia não existe.
class DayTasks(SQLModel):
    day: date
    is_today: bool
    previous_day: date | None
    next_day: date | None
    # A data que o formulário sugere para uma tarefa nova: o dia listado ou, se ele já passou,
    # hoje, porque a data nova não pode ser anterior a hoje (seção 6.1). Vem pronta do servidor
    # para a tela não comparar datas (regra 9 do CLAUDE.md).
    new_task_due_date: date
    overdue: list[TaskView]
    pending: list[TaskView]
    completed: list[TaskView]


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


# Responde 409 se a data não puder mudar: tarefa concluída ou data travada. Quem chama informa
# os dias de atraso, para a trava e o contador usarem o mesmo "hoje", mesmo à meia-noite.
def ensure_due_date_can_change(task: Task, days_late: int) -> None:
    if task.completed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a data."
        )

    if is_due_date_locked(task.postponements, days_late):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A data desta tarefa está travada e não pode mudar."
        )


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


# Soma o histórico de cada tarefa numa consulta só: o group_by junta as linhas pelo task_id, e o
# banco soma cada grupo. Devolve {id da tarefa: soma}; tarefa sem linhas não aparece no resultado.
def xp_earned_by_task(session: Session, task_ids: list[int]) -> dict[int, int]:
    rows = session.exec(
        select(XpEntry.task_id, func.sum(XpEntry.amount))
        .where(col(XpEntry.task_id).in_(task_ids))
        .group_by(XpEntry.task_id)
    ).all()
    return dict(rows)


# Acrescenta à tarefa os dois campos da tela. "earned" é o resultado de xp_earned_by_task: a
# tarefa que não está nele não tem linhas no histórico e rendeu 0. Os dias de atraso podem sair
# negativos, com a data no futuro: as regras de xp.py tratam esse valor como 0.
def task_view(task: Task, today: date, earned: dict[int, int]) -> TaskView:
    days_late = (today - task.due_date).days
    return TaskView.model_validate(
        task,
        update={
            "due_date_locked": is_due_date_locked(task.postponements, days_late),
            "xp_earned": earned.get(task.id, 0),
        },
    )


# Monta a resposta da visão do dia. Quem chama lê o relógio uma vez e informa o "hoje", para as
# atrasadas e a trava de todas as tarefas usarem o mesmo dia, mesmo à meia-noite. As atrasadas
# só vêm na visão de hoje.
def build_day_tasks(session: Session, day: date, today: date) -> DayTasks:
    overdue = []
    if day == today:
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

    earned = xp_earned_by_task(session, [task.id for task in [*overdue, *pending, *completed]])

    previous_day, next_day = adjacent_days(day)
    return DayTasks(
        day=day,
        is_today=day == today,
        previous_day=previous_day,
        next_day=next_day,
        new_task_due_date=max(day, today),
        overdue=[task_view(task, today, earned) for task in overdue],
        pending=[task_view(task, today, earned) for task in pending],
        completed=[task_view(task, today, earned) for task in completed],
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


# A visão de hoje em Brasília. A tela abre por aqui e nunca usa o relógio do celular para
# decidir que dia é.
@router.get("/today")
def list_today_tasks(session: SessionDep) -> DayTasks:
    today = app_today()
    return build_day_tasks(session, today, today)


@router.get("/day/{day}")
def list_tasks_by_day(day: date, session: SessionDep) -> DayTasks:
    return build_day_tasks(session, day, app_today())


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
# 409. Os 409 vão do mais definitivo para o mais passageiro, como no Adiar: recarregar só
# resolve a tela desatualizada, então os outros dizem o motivo real. A tarefa lida não é
# alterada: os valores novos ficam em variáveis e vão ao banco numa instrução só, com condição.
# Se o objeto lido mudasse, o SQLModel mandaria essa mudança sozinho ao banco antes do UPDATE
# (autoflush), sem condição. O pedido recusado não grava nada.
@router.put(
    "/{task_id}",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {
            "description": (
                "A tarefa concluída não pode mudar de dificuldade nem de data, "
                "a tarefa travada não pode mudar de data, ou a tela estava desatualizada."
            )
        },
    },
)
def update_task(task_id: TaskId, task_update: TaskUpdate, session: SessionDep) -> Task:
    task = get_task_or_404(session, task_id)

    # A mudança de data é a que a pessoa fez no formulário: a data mandada contra a que ele
    # mostrava. Mandar a mesma data não é mudança (seção 6.1), então nenhuma regra de data se
    # aplica. Se a tarefa já tiver outra data no banco, o UPDATE abaixo recusa.
    date_changed = task_update.due_date != task_update.shown_due_date

    if date_changed:
        ensure_date_is_not_past(task_update.due_date)

    if task_update.task_type_id is not None:
        ensure_task_type_exists(session, task_update.task_type_id)

    if task.completed and task_update.difficulty != task.difficulty:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a dificuldade."
        )

    # A trava vem antes do contador, porque postponements_after_date_change não a confere. Os
    # dias de atraso podem sair negativos, com a data no futuro: as regras de xp.py tratam esse
    # valor como 0.
    new_postponements = task.postponements
    if date_changed:
        days_late = (app_today() - task.due_date).days
        ensure_due_date_can_change(task, days_late)
        new_postponements = postponements_after_date_change(
            task.postponements, days_late, task.due_date, task_update.due_date
        )

    # Grava numa instrução só, que vale apenas se a tarefa ainda tiver a data que o formulário
    # mostrava e ainda estiver concluída ou pendente como foi lida aqui. Assim, um Adiar ou um
    # Concluir no meio da edição não se perde nem recebe uma data ou dificuldade que não devia.
    # postponements fica fora da condição porque só muda junto com a data.
    changed_rows = session.exec(
        update(Task)
        .where(
            Task.id == task_id,
            Task.completed == task.completed,
            Task.due_date == task_update.shown_due_date,
        )
        .values(
            title=task_update.title,
            notes=task_update.notes,
            difficulty=task_update.difficulty,
            color=task_update.color,
            task_type_id=task_update.task_type_id,
            due_date=task_update.due_date,
            postponements=new_postponements,
        )
    ).rowcount

    if changed_rows == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE_TASK_MESSAGE)

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


# A tarefa só muda se ainda estiver pendente e com a data que a tela mostrava, numa instrução
# só, como em change_completed. Assim, dois pedidos ao mesmo tempo, ou um Adiar junto com um
# Concluir, não passam os dois, como na edição. A data nova é
# sempre depois de hoje, então ensure_date_is_not_past nunca recusaria. Adiar não mexe no XP,
# então nada entra no histórico.
@router.post(
    "/{task_id}/postpone",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {
            "description": (
                "A tarefa está concluída, travada ou na última data possível, "
                "ou a tela estava desatualizada."
            )
        },
    },
)
def postpone_task(task_id: TaskId, postpone_input: TaskPostpone, session: SessionDep) -> Task:
    task = get_task_or_404(session, task_id)

    today = app_today()
    days_late = (today - task.due_date).days
    ensure_due_date_can_change(task, days_late)

    new_due_date = postponed_due_date(task.due_date, today)
    if new_due_date is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Esta tarefa já está na última data possível e não pode ser adiada.",
        )

    new_postponements = postponements_after_date_change(
        task.postponements, days_late, task.due_date, new_due_date
    )

    changed_rows = session.exec(
        update(Task)
        .where(
            Task.id == task_id,
            Task.completed == False,
            Task.due_date == postpone_input.shown_due_date,
        )
        .values(due_date=new_due_date, postponements=new_postponements)
    ).rowcount

    if changed_rows == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=STALE_TASK_MESSAGE)

    session.commit()
    session.refresh(task)
    return task
