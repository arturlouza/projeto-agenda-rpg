from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import StringConstraints
from sqlmodel import Session, SQLModel, select

from app.database import get_session
from app.models import Task, TaskType

router = APIRouter(prefix="/task-types", tags=["task-types"])

# Pede ao FastAPI uma sessão do banco para a rota que declarar este tipo.
SessionDep = Annotated[Session, Depends(get_session)]


# O que a API recebe ao criar ou renomear. Tira os espaços das pontas e recusa nome vazio.
# É separada de TaskType porque modelos com table=True não validam os dados.
class TaskTypeInput(SQLModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task_type(task_type_input: TaskTypeInput, session: SessionDep) -> TaskType:
    if name_is_taken(session, task_type_input.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Já existe um tipo com esse nome.")

    task_type = TaskType(name=task_type_input.name)
    session.add(task_type)
    session.commit()
    session.refresh(task_type)
    return task_type


# A ordem por id (ordem de criação) é a mesma no SQLite e no PostgreSQL.
@router.get("")
def list_task_types(session: SessionDep) -> list[TaskType]:
    return list(session.exec(select(TaskType).order_by(TaskType.id)).all())


@router.patch("/{task_type_id}")
def rename_task_type(
    task_type_id: int, task_type_input: TaskTypeInput, session: SessionDep
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
@router.delete("/{task_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_type(task_type_id: int, session: SessionDep) -> None:
    task_type = get_task_type_or_404(session, task_type_id)

    for task in session.exec(select(Task).where(Task.task_type_id == task_type_id)).all():
        task.task_type_id = None
        session.add(task)

    # Envia as mudanças das tarefas antes de excluir o tipo, senão a chave estrangeira
    # poderia recusar a exclusão.
    session.flush()

    session.delete(task_type)
    session.commit()
