from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session

from app.models import Task, TaskType
from app.routers.task_types import name_key

# "Exercício" com o "í" em duas partes: "i" e o acento agudo combinante (U+0301). O escape
# impede que um editor junte o acento à letra sem ninguém ver.
DECOMPOSED_EXERCICIO = "Exercício"

# Campos que o pedido não pode mandar. O id e o created_at existem no tipo, mas quem os define
# é o app.
UNKNOWN_FIELDS = [
    {"id": 123},
    {"created_at": "2026-11-01T12:00:00Z"},
    {"nome": "campo errado"},
]


# Cria um tipo pela API e devolve o id dele.
def create_type(client, name):
    response = client.post("/task-types", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


# Grava um tipo direto no banco, porque a API não deixa escolher o id nem o created_at.
def insert_type(test_engine, task_type_id, name, created_at):
    with Session(test_engine) as session:
        session.add(TaskType(id=task_type_id, name=name, created_at=created_at))
        session.commit()


def test_create_returns_the_new_type(client):
    response = client.post("/task-types", json={"name": "Leitura"})

    assert response.status_code == 201
    assert response.json()["name"] == "Leitura"
    assert response.json()["id"] is not None


def test_list_returns_types_in_creation_order(client):
    create_type(client, "Treino")
    create_type(client, "Estudo")

    response = client.get("/task-types")

    assert response.status_code == 200
    assert [task_type["name"] for task_type in response.json()] == ["Treino", "Estudo"]


def test_list_shows_created_at(client):
    create_type(client, "Leitura")

    response = client.get("/task-types")

    assert response.json()[0]["created_at"].endswith("Z")


def test_list_orders_by_created_at_not_by_id(client, test_engine):
    insert_type(test_engine, 1, "Mais novo", datetime(2026, 2, 1, tzinfo=timezone.utc))
    insert_type(test_engine, 2, "Mais antigo", datetime(2026, 1, 1, tzinfo=timezone.utc))

    response = client.get("/task-types")

    assert [task_type["id"] for task_type in response.json()] == [2, 1]


# No SQLite, o empate já sai em ordem de id mesmo sem o desempate no ORDER BY. Este teste
# documenta o resultado esperado, mas não detecta a remoção do desempate.
def test_list_breaks_created_at_tie_by_id(client, test_engine):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    insert_type(test_engine, 2, "Segundo", created_at)
    insert_type(test_engine, 1, "Primeiro", created_at)

    response = client.get("/task-types")

    assert [task_type["id"] for task_type in response.json()] == [1, 2]


# Grava uma tarefa direto no banco, com o tipo e o estado que o teste escolher.
def insert_task(test_engine, task_type_id, completed=False):
    with Session(test_engine) as session:
        task = Task(
            title="Tarefa",
            due_date=date(2026, 1, 1),
            difficulty="easy",
            task_type_id=task_type_id,
            completed=completed,
        )
        session.add(task)
        session.commit()
        return task.id


# A contagem da tela de tipos: pendentes e concluídas contam, uma tarefa sem tipo não entra em
# nenhuma conta, e um tipo sem tarefas mostra 0.
def test_list_counts_the_tasks_of_each_type(client, test_engine):
    used_id = create_type(client, "Treino")
    unused_id = create_type(client, "Leitura")
    insert_task(test_engine, used_id)
    insert_task(test_engine, used_id, completed=True)
    insert_task(test_engine, None)

    response = client.get("/task-types")

    counts = {task_type["id"]: task_type["task_count"] for task_type in response.json()}
    assert counts == {used_id: 2, unused_id: 0}


# O número é lido do banco a cada pedido: mudar o tipo de uma tarefa pela edição muda a contagem
# dos dois tipos.
def test_list_count_follows_the_task_type(client, test_engine):
    first_id = create_type(client, "Treino")
    second_id = create_type(client, "Leitura")
    task_id = insert_task(test_engine, first_id)

    response = client.put(
        f"/tasks/{task_id}",
        json={
            "title": "Tarefa",
            "notes": None,
            "difficulty": "easy",
            "color": "#F5E6C8",
            "task_type_id": second_id,
            "due_date": "2026-01-01",
            "shown_due_date": "2026-01-01",
        },
    )

    assert response.status_code == 200
    counts = {task_type["id"]: task_type["task_count"] for task_type in client.get("/task-types").json()}
    assert counts == {first_id: 0, second_id: 1}


def test_create_removes_spaces_from_the_ends(client):
    response = client.post("/task-types", json={"name": "  Leitura  "})

    assert response.json()["name"] == "Leitura"


@pytest.mark.parametrize("name", ["", "   "])
def test_create_refuses_empty_name(client, name):
    response = client.post("/task-types", json={"name": name})

    assert response.status_code == 422


# Os espaços das pontas saem antes da contagem, então os dois nomes têm 50 caracteres.
@pytest.mark.parametrize("name", ["a" * 50, "  " + "a" * 50 + "  "])
def test_create_accepts_name_with_50_characters(client, name):
    response = client.post("/task-types", json={"name": name})

    assert response.status_code == 201
    assert response.json()["name"] == "a" * 50


def test_create_refuses_name_with_51_characters(client):
    response = client.post("/task-types", json={"name": "a" * 51})

    assert response.status_code == 422
    assert client.get("/task-types").json() == []


@pytest.mark.parametrize(
    ("existing", "repeated"),
    [
        ("Leitura", "Leitura"),
        ("Leitura", "LEITURA"),
        ("MÚSICA", "música"),
        ("Leitura", "  leitura  "),
    ],
)
def test_create_refuses_repeated_name(client, existing, repeated):
    create_type(client, existing)

    response = client.post("/task-types", json={"name": repeated})

    assert response.status_code == 409
    assert response.json()["detail"] == f"Já existe um tipo com esse nome: {existing}."
    assert len(client.get("/task-types").json()) == 1


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Exercício", "exercicio"),
        ("EXERCÍCIO", "exercicio"),
        (DECOMPOSED_EXERCICIO, "exercicio"),
        ("Força", "forca"),
        ("Leitura", "leitura"),
    ],
)
def test_name_key(name, key):
    assert name_key(name) == key


@pytest.mark.parametrize(
    ("existing", "repeated"),
    [
        ("Exercício", "exercicio"),
        ("Exercício", "EXERCÍCIO"),
        ("Exercício", "Exercicio"),
        ("Exercício", DECOMPOSED_EXERCICIO),
        ("Força", "Forca"),
    ],
)
def test_create_refuses_name_that_differs_only_by_accent(client, existing, repeated):
    create_type(client, existing)

    response = client.post("/task-types", json={"name": repeated})

    assert response.status_code == 409
    assert response.json()["detail"] == f"Já existe um tipo com esse nome: {existing}."
    assert [task_type["name"] for task_type in client.get("/task-types").json()] == [existing]


def test_create_accepts_different_names(client):
    create_type(client, "Leitura")
    create_type(client, "Escrita")

    names = [task_type["name"] for task_type in client.get("/task-types").json()]
    assert names == ["Leitura", "Escrita"]


@pytest.mark.parametrize("extra_field", UNKNOWN_FIELDS)
def test_create_refuses_unknown_field(client, extra_field):
    response = client.post("/task-types", json={"name": "Leitura"} | extra_field)

    assert response.status_code == 422
    assert client.get("/task-types").json() == []


def test_rename_changes_the_name(client):
    task_type_id = create_type(client, "Leitura")
    created_at = client.get("/task-types").json()[0]["created_at"]

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "Estudo"})

    expected = {"id": task_type_id, "name": "Estudo", "created_at": created_at}
    assert response.status_code == 200
    assert response.json() == expected
    # A lista traz também a contagem das tarefas do tipo (etapa 11.7); o PATCH não traz.
    assert client.get("/task-types").json() == [expected | {"task_count": 0}]


def test_rename_can_change_only_the_case_of_its_own_name(client):
    task_type_id = create_type(client, "leitura")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "Leitura"})

    assert response.status_code == 200
    assert response.json()["name"] == "Leitura"


def test_rename_refuses_name_of_another_type(client):
    create_type(client, "Leitura")
    task_type_id = create_type(client, "Treino")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "LEITURA"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um tipo com esse nome: Leitura."
    assert client.get("/task-types").json()[1]["name"] == "Treino"


def test_rename_can_change_only_the_accent_of_its_own_name(client):
    task_type_id = create_type(client, "Exercicio")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "Exercício"})

    assert response.status_code == 200
    assert response.json()["name"] == "Exercício"


def test_rename_refuses_name_of_another_type_that_differs_only_by_accent(client):
    create_type(client, "Exercício")
    task_type_id = create_type(client, "Treino")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "exercicio"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um tipo com esse nome: Exercício."
    assert client.get("/task-types").json()[1]["name"] == "Treino"


# Um par que a regra antiga aceitava, gravado direto no banco porque a API já não deixa criar.
def insert_old_duplicates(test_engine):
    insert_type(test_engine, 1, "Exercício", datetime(2026, 1, 1, tzinfo=timezone.utc))
    insert_type(test_engine, 2, "exercicio", datetime(2026, 2, 1, tzinfo=timezone.utc))


# O ignored_id ignora o próprio tipo, mas não o outro do par: até mandar o próprio nome, sem
# mudança, é recusado. A mensagem cita o mais antigo, e nenhum dos dois muda.
@pytest.mark.parametrize("name", ["exercicio", "Exercicio"])
def test_renaming_an_old_duplicate_to_the_same_key_is_refused(client, test_engine, name):
    insert_old_duplicates(test_engine)

    response = client.patch("/task-types/2", json={"name": name})

    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um tipo com esse nome: Exercício."
    names = [task_type["name"] for task_type in client.get("/task-types").json()]
    assert names == ["Exercício", "exercicio"]


def test_renaming_an_old_duplicate_to_another_name_works(client, test_engine):
    insert_old_duplicates(test_engine)

    response = client.patch("/task-types/2", json={"name": "Corrida"})

    assert response.status_code == 200
    names = [task_type["name"] for task_type in client.get("/task-types").json()]
    assert names == ["Exercício", "Corrida"]


@pytest.mark.parametrize("name", ["", "   "])
def test_rename_refuses_empty_name(client, name):
    task_type_id = create_type(client, "Leitura")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": name})

    assert response.status_code == 422
    assert client.get("/task-types").json()[0]["name"] == "Leitura"


def test_rename_refuses_name_with_51_characters(client):
    task_type_id = create_type(client, "Leitura")

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "a" * 51})

    assert response.status_code == 422
    assert client.get("/task-types").json()[0]["name"] == "Leitura"


@pytest.mark.parametrize("extra_field", UNKNOWN_FIELDS)
def test_rename_refuses_unknown_field(client, extra_field):
    task_type_id = create_type(client, "Leitura")
    before = client.get("/task-types").json()

    response = client.patch(f"/task-types/{task_type_id}", json={"name": "Estudo"} | extra_field)

    assert response.status_code == 422
    assert client.get("/task-types").json() == before


def test_rename_unknown_type_returns_404(client):
    response = client.patch("/task-types/999", json={"name": "Estudo"})

    assert response.status_code == 404


@pytest.mark.parametrize("task_type_id", [0, -1, 2147483648, 10**30])
def test_rename_refuses_id_out_of_range(client, task_type_id):
    response = client.patch(f"/task-types/{task_type_id}", json={"name": "Estudo"})

    assert response.status_code == 422


def test_rename_with_largest_id_returns_404(client):
    response = client.patch("/task-types/2147483647", json={"name": "Estudo"})

    assert response.status_code == 404


def test_delete_removes_unused_type(client):
    task_type_id = create_type(client, "Leitura")

    response = client.delete(f"/task-types/{task_type_id}")

    assert response.status_code == 204
    assert client.get("/task-types").json() == []


# Confere uma garantia do banco (seção 6.6). O código do app não pode contar com isso.
def test_new_type_does_not_reuse_id_of_deleted_type(client):
    create_type(client, "Leitura")
    largest_id = create_type(client, "Treino")
    assert client.delete(f"/task-types/{largest_id}").status_code == 204

    assert create_type(client, "Estudo") != largest_id


def test_delete_unknown_type_returns_404(client):
    response = client.delete("/task-types/999")

    assert response.status_code == 404


@pytest.mark.parametrize("task_type_id", [0, -1, 2147483648, 10**30])
def test_delete_refuses_id_out_of_range(client, task_type_id):
    response = client.delete(f"/task-types/{task_type_id}")

    assert response.status_code == 422


def test_delete_with_largest_id_returns_404(client):
    response = client.delete("/task-types/2147483647")

    assert response.status_code == 404


def test_delete_used_type_keeps_tasks_without_type(client, test_engine):
    task_type_id = create_type(client, "Treino")
    other_type_id = create_type(client, "Leitura")

    with Session(test_engine) as session:
        used_task = Task(
            title="Corrida",
            due_date=date(2026, 1, 1),
            difficulty="easy",
            task_type_id=task_type_id,
        )
        other_task = Task(
            title="Ler 30 páginas",
            due_date=date(2026, 1, 1),
            difficulty="medium",
            task_type_id=other_type_id,
        )
        session.add(used_task)
        session.add(other_task)
        session.commit()
        used_task_id = used_task.id
        other_task_id = other_task.id

    response = client.delete(f"/task-types/{task_type_id}")

    assert response.status_code == 204
    assert [task_type["id"] for task_type in client.get("/task-types").json()] == [other_type_id]

    with Session(test_engine) as session:
        assert session.get(Task, used_task_id).task_type_id is None
        assert session.get(Task, other_task_id).task_type_id == other_type_id
