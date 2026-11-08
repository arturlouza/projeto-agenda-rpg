import unicodedata
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ConfigDict, StringConstraints
from sqlmodel import Session, SQLModel, col, func, select

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


# O que a API devolve ao listar os tipos: o tipo e quantas tarefas o usam, pendentes e
# concluídas. A tela de tipos mostra o número antes de excluir, sem contar nada no JavaScript.
# Os campos do tipo são escritos de novo aqui porque herdar de um modelo com tabela (TaskType)
# não tem suporte no SQLModel. Criar e renomear continuam devolvendo o tipo sem a contagem.
class TaskTypeView(SQLModel):
    id: int
    name: str
    created_at: datetime
    task_count: int


# Quantas tarefas usam cada tipo, numa consulta só: {id do tipo: quantidade}. As tarefas sem tipo
# ficam de fora, e um tipo sem tarefas não aparece no resultado (quem lê usa 0).
def task_count_by_type(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(Task.task_type_id, func.count())
        .where(col(Task.task_type_id).is_not(None))
        .group_by(Task.task_type_id)
    ).all()
    return dict(rows)


# Chave de comparação de um nome de tipo: sem diferença de maiúsculas e minúsculas e sem
# acentos, então "Exercício", "EXERCICIO" e "exercicio" dão a mesma chave. O casefold tira a
# caixa. O NFD separa cada letra acentuada em letra mais marca ("é" vira "e" + acento
# combinante, "ç" vira "c" + cedilha), e as marcas saem. O casefold vem antes porque pode criar
# uma marca nova (o "İ" turco vira "i" + ponto), e o NFD depois separa também essa. Os espaços
# das pontas já saíram no TaskTypeInput.
def name_key(name: str) -> str:
    decomposed = unicodedata.normalize("NFD", name.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# Responde 409 se outro tipo já usa um nome com a mesma chave, citando o nome como foi gravado.
# A comparação é no Python, igual nos dois bancos: o lower() do SQLite não mexe em letras
# acentuadas, e tirar acentos no PostgreSQL pediria uma extensão que o SQLite não tem.
# O ignored_id deixa um tipo trocar a caixa ou o acento do próprio nome sem colidir consigo
# mesmo. A busca segue a ordem da lista, para a mensagem citar sempre o tipo mais antigo quando
# dois tipos antigos tiverem a mesma chave.
def ensure_name_is_free(session: Session, name: str, ignored_id: int | None = None) -> None:
    key = name_key(name)
    task_types = session.exec(select(TaskType).order_by(TaskType.created_at, TaskType.id)).all()
    for task_type in task_types:
        if task_type.id != ignored_id and name_key(task_type.name) == key:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Já existe um tipo com esse nome: {task_type.name}.",
            )


# Busca o tipo pelo id e responde 404 se ele não existir.
def get_task_type_or_404(session: Session, task_type_id: int) -> TaskType:
    task_type = session.get(TaskType, task_type_id)
    if task_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tipo de tarefa não encontrado.")
    return task_type


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": (
                "Já existe um tipo com esse nome, ignorando maiúsculas, minúsculas e acentos."
            )
        }
    },
)
def create_task_type(task_type_input: TaskTypeInput, session: SessionDep) -> TaskType:
    ensure_name_is_free(session, task_type_input.name)

    task_type = TaskType(name=task_type_input.name)
    session.add(task_type)
    session.commit()
    session.refresh(task_type)
    return task_type


# A ordem de criação vem do created_at. O id só desempata, em caso de empate exato. Cada tipo
# vem com a contagem das tarefas dele, lida do banco a cada pedido.
@router.get("")
def list_task_types(session: SessionDep) -> list[TaskTypeView]:
    task_types = session.exec(select(TaskType).order_by(TaskType.created_at, TaskType.id)).all()
    counts = task_count_by_type(session)
    return [
        TaskTypeView.model_validate(
            task_type, update={"task_count": counts.get(task_type.id, 0)}
        )
        for task_type in task_types
    ]


@router.patch(
    "/{task_type_id}",
    responses={
        404: {"description": "Tipo de tarefa não encontrado."},
        409: {
            "description": (
                "Já existe um tipo com esse nome, ignorando maiúsculas, minúsculas e acentos."
            )
        },
    },
)
def rename_task_type(
    task_type_id: TaskTypeId, task_type_input: TaskTypeInput, session: SessionDep
) -> TaskType:
    task_type = get_task_type_or_404(session, task_type_id)

    ensure_name_is_free(session, task_type_input.name, ignored_id=task_type_id)

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
