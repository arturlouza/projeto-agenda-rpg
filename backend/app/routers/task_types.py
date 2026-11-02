from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ConfigDict, StringConstraints
from sqlmodel import Session, SQLModel, select

from app.database import get_session
from app.models import Task, TaskType

# Tamanho máximo do nome de um tipo, contado depois de remover os espaços das pontas.
MAX_TASK_TYPE_NAME_LENGTH = 50

# Maior valor da coluna INTEGER do PostgreSQL. Com este limite, um id gigante é recusado
# do mesmo jeito nos dois bancos, em vez de causar um erro 500 ao chegar ao banco.
MAX_ID = 2_147_483_647

router = APIRouter(prefix="/task-types", tags=["task-types"])

# Pede ao FastAPI uma sessão do banco para a rota que declarar este tipo.
SessionDep = Annotated[Session, Depends(get_session)]

# Id que vem na rota. Fora deste intervalo, o FastAPI responde 422 sem consultar o banco.
TaskTypeId = Annotated[int, Path(ge=1, le=MAX_ID)]


# O que a API recebe ao criar ou renomear. Tira os espaços das pontas e recusa nome vazio
# ou longo demais. É separada de TaskType porque modelos com table=True não validam os dados.
class TaskTypeInput(SQLModel):
    # Campo desconhecido é recusado, então o pedido não escolhe id nem created_at.
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_TASK_TYPE_NAME_LENGTH
        ),
    ]


# Diz se outro tipo já usa este nome, ignorando maiúsculas e minúsculas. A comparação é no
# Python porque o lower() do SQLite não converte letras acentuadas, como o Ú de MÚSICA.
# O ignored_id deixa um tipo trocar a caixa do próprio nome sem colidir consigo mesmo.
def name_is_taken(session: Session, name: str, ignored_id: int | None = None) -> bool:
    for task_type in session.exec(select(TaskType)).all():
        if task_type.id != ignored_id and task_type.name.casefold() == name.casefold():
            return True
    return False


# Busca o tipo pelo id e responde 404 se ele não existir.
def get_task_type_or_404(session: Session, task_type_id: int) -> TaskType:
    task_type = session.get(TaskType, task_type_id)
    if task_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tipo de tarefa não encontrado.")
    return task_type


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Já existe um tipo com esse nome."}},
)
def create_task_type(task_type_input: TaskTypeInput, session: SessionDep) -> TaskType:
    if name_is_taken(session, task_type_input.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Já existe um tipo com esse nome.")

    task_type = TaskType(name=task_type_input.name)
    session.add(task_type)
    session.commit()
    session.refresh(task_type)
    return task_type


# A ordem de criação vem do created_at. O id só desempata, em caso de empate exato.
@router.get("")
def list_task_types(session: SessionDep) -> list[TaskType]:
    return list(session.exec(select(TaskType).order_by(TaskType.created_at, TaskType.id)).all())


@router.patch(
    "/{task_type_id}",
    responses={
        404: {"description": "Tipo de tarefa não encontrado."},
        409: {"description": "Já existe um tipo com esse nome."},
    },
)
def rename_task_type(
    task_type_id: TaskTypeId, task_type_input: TaskTypeInput, session: SessionDep
) -> TaskType:
    task_type = get_task_type_or_404(session, task_type_id)

    if name_is_taken(session, task_type_input.name, ignored_id=task_type_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Já existe um tipo com esse nome.")

    task_type.name = task_type_input.name
    session.add(task_type)
    session.commit()
    session.refresh(task_type)
    return task_type


# As tarefas do tipo ficam sem tipo; nenhuma é apagada. Tudo vale só no commit, numa
# única transação: se algo falhar no meio, nada muda no banco.
@router.delete(
    "/{task_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Tipo de tarefa não encontrado."}},
)
def delete_task_type(task_type_id: TaskTypeId, session: SessionDep) -> None:
    task_type = get_task_type_or_404(session, task_type_id)

    for task in session.exec(select(Task).where(Task.task_type_id == task_type_id)).all():
        task.task_type_id = None
        session.add(task)

    # Envia as mudanças das tarefas antes de excluir o tipo, senão a chave estrangeira
    # poderia recusar a exclusão.
    session.flush()

    session.delete(task_type)
    session.commit()
