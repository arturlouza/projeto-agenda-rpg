from datetime import date, datetime, timezone
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models import DEFAULT_TASK_COLOR, Task
from app.routers.tasks import Difficulty
from app.rules.xp import TASK_BASE_XP

UNKNOWN_TYPE_MESSAGE = "Esse tipo de tarefa não existe."
PAST_DATE_MESSAGE = "A data não pode ser anterior a hoje."


# Banco em arquivo na pasta temporária do pytest, para nunca tocar no agenda.db real.
@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


# Cliente da API que usa o banco de teste no lugar do banco real.
@pytest.fixture
def client(test_engine):
    def get_test_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# Vale para todos os testes deste arquivo: o "hoje" é sempre 01/11/2026 em Brasília, para
# nenhum teste depender da data real do computador.
@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    fixed_now = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)


# Monta uma tarefa válida, só com os campos obrigatórios, mais o que o teste quiser mudar.
def task_data(**changes):
    return {"title": "Ler 30 páginas", "due_date": "2026-11-01", "difficulty": "medium"} | changes


# Cria uma tarefa pela API, confere que deu certo e devolve o JSON da resposta.
def create_task(client, **changes):
    response = client.post("/tasks", json=task_data(**changes))
    assert response.status_code == 201
    return response.json()


# Lê todas as tarefas direto no banco, porque a rota de listagem só mostra um dia por vez.
def tasks_in_database(test_engine):
    with Session(test_engine) as session:
        return list(session.exec(select(Task)).all())


# Grava uma tarefa direto no banco e devolve o id dela, porque a API ainda não cria tarefa
# concluída nem atrasada, e não deixa escolher o id nem o created_at.
def insert_task(test_engine, **fields):
    data = {"title": "Tarefa", "due_date": date(2026, 11, 1), "difficulty": "easy"} | fields

    with Session(test_engine) as session:
        task = Task(**data)
        session.add(task)
        session.commit()
        return task.id


# Pede os grupos de um dia pela API, confere que deu certo e devolve o JSON da resposta.
def day_tasks(client, day):
    response = client.get(f"/tasks/day/{day}")
    assert response.status_code == 200
    return response.json()


# Devolve só os ids de um grupo, na ordem em que a API respondeu.
def ids(tasks):
    return [task["id"] for task in tasks]


# Confere que o pedido foi recusado com 422 e que nada foi gravado.
def assert_refused(client, test_engine, data):
    response = client.post("/tasks", json=data)

    assert response.status_code == 422
    assert tasks_in_database(test_engine) == []
    return response


def test_create_with_required_fields_uses_default_values(client):
    task = create_task(client)

    assert task["id"] is not None
    assert task["title"] == "Ler 30 páginas"
    assert task["due_date"] == "2026-11-01"
    assert task["difficulty"] == "medium"
    assert task["notes"] is None
    assert task["color"] == DEFAULT_TASK_COLOR
    assert task["task_type_id"] is None
    assert task["completed"] is False
    assert task["completed_at"] is None
    assert task["postponements"] == 0
    assert task["created_at"].endswith("Z")


def test_create_saves_all_fields_in_the_database(client, test_engine):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]

    create_task(
        client,
        title="Ler 30 páginas",
        notes="Capítulo 3",
        due_date="2026-11-05",
        difficulty="hard",
        color="#112233",
        task_type_id=task_type_id,
    )

    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.title == "Ler 30 páginas"
    assert saved_task.notes == "Capítulo 3"
    assert saved_task.due_date == date(2026, 11, 5)
    assert saved_task.difficulty == "hard"
    assert saved_task.color == "#112233"
    assert saved_task.task_type_id == task_type_id


@pytest.mark.parametrize("field", ["title", "due_date", "difficulty"])
def test_create_refuses_missing_required_field(client, test_engine, field):
    data = task_data()
    del data[field]

    assert_refused(client, test_engine, data)


def test_create_removes_spaces_from_the_ends_of_the_title(client):
    task = create_task(client, title="  Ler 30 páginas  ")

    assert task["title"] == "Ler 30 páginas"


# Os espaços das pontas saem antes da contagem, então os dois títulos têm 100 caracteres.
@pytest.mark.parametrize("title", ["a" * 100, "  " + "a" * 100 + "  "])
def test_create_accepts_title_with_100_characters(client, title):
    task = create_task(client, title=title)

    assert task["title"] == "a" * 100


@pytest.mark.parametrize("title", ["", "   ", "a" * 101])
def test_create_refuses_invalid_title(client, test_engine, title):
    assert_refused(client, test_engine, task_data(title=title))


def test_create_removes_spaces_from_the_ends_of_the_notes(client):
    task = create_task(client, notes="  Capítulo 3  ")

    assert task["notes"] == "Capítulo 3"


# Os espaços das pontas saem antes da contagem, então as duas notas têm 1.000 caracteres.
@pytest.mark.parametrize("notes", ["a" * 1000, "  " + "a" * 1000 + "  "])
def test_create_accepts_notes_with_1000_characters(client, notes):
    task = create_task(client, notes=notes)

    assert task["notes"] == "a" * 1000


@pytest.mark.parametrize("notes", ["", "   ", None])
def test_create_saves_empty_notes_as_null(client, test_engine, notes):
    task = create_task(client, notes=notes)

    assert task["notes"] is None
    assert tasks_in_database(test_engine)[0].notes is None


def test_create_refuses_notes_with_1001_characters(client, test_engine):
    assert_refused(client, test_engine, task_data(notes="a" * 1001))


@pytest.mark.parametrize("color", ["#ff0000", "#FF0000", "#Ff0000"])
def test_create_saves_color_in_uppercase(client, color):
    task = create_task(client, color=color)

    assert task["color"] == "#FF0000"


@pytest.mark.parametrize(
    "color", ["#FFF", "FF0000", "#GGGGGG", "#FF00000", " #FF0000 ", "#FF0000\n", "", None]
)
def test_create_refuses_invalid_color(client, test_engine, color):
    assert_refused(client, test_engine, task_data(color=color))


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_create_accepts_each_difficulty(client, difficulty):
    task = create_task(client, difficulty=difficulty)

    assert task["difficulty"] == difficulty


@pytest.mark.parametrize("difficulty", ["extreme", "Easy", "", None])
def test_create_refuses_invalid_difficulty(client, test_engine, difficulty):
    assert_refused(client, test_engine, task_data(difficulty=difficulty))


# Se uma dificuldade aceita aqui não tivesse XP, task_xp daria erro ao concluir a tarefa.
def test_accepted_difficulties_are_the_ones_with_base_xp():
    assert set(get_args(Difficulty)) == set(TASK_BASE_XP)


def test_create_accepts_existing_task_type(client):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]

    task = create_task(client, task_type_id=task_type_id)

    assert task["task_type_id"] == task_type_id


def test_create_accepts_null_task_type(client):
    task = create_task(client, task_type_id=None)

    assert task["task_type_id"] is None


# Inexistente ou fora do intervalo do banco, a recusa e a mensagem são as mesmas.
@pytest.mark.parametrize(
    "task_type_id", [999, 0, -1, 2147483647, 2147483648, 10**30, -(10**30)]
)
def test_create_refuses_unknown_task_type(client, test_engine, task_type_id):
    response = assert_refused(client, test_engine, task_data(task_type_id=task_type_id))

    assert response.json()["detail"] == UNKNOWN_TYPE_MESSAGE


@pytest.mark.parametrize("due_date", ["2026-11-01", "2026-11-02", "9999-12-31"])
def test_create_accepts_today_or_later(client, due_date):
    task = create_task(client, due_date=due_date)

    assert task["due_date"] == due_date


def test_create_refuses_yesterday(client, test_engine):
    response = assert_refused(client, test_engine, task_data(due_date="2026-10-31"))

    assert response.json()["detail"] == PAST_DATE_MESSAGE


@pytest.mark.parametrize("due_date", ["01/11/2026", "2026-13-01", "", None])
def test_create_refuses_invalid_date(client, test_engine, due_date):
    assert_refused(client, test_engine, task_data(due_date=due_date))


# Às 01h30 UTC de 01/11 ainda são 22h30 de 31/10 em Brasília. Se a rota usasse o dia em UTC,
# 31/10 seria recusado, então este teste prova que o "hoje" vem do fuso de Brasília.
def test_today_follows_brasilia_not_utc(client, test_engine, monkeypatch):
    fixed_now = datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)

    assert_refused(client, test_engine, task_data(due_date="2026-10-30"))
    task = create_task(client, due_date="2026-10-31")

    assert task["due_date"] == "2026-10-31"


@pytest.mark.parametrize(
    "extra_field",
    [
        {"completed": True},
        {"completed": False},
        {"postponements": 5},
        {"completed_at": "2026-11-01T12:00:00Z"},
        {"id": 123},
        {"created_at": "2026-11-01T12:00:00Z"},
        {"note": "nome errado"},
    ],
)
def test_create_refuses_unknown_field(client, test_engine, extra_field):
    assert_refused(client, test_engine, task_data(**extra_field))


def test_day_without_tasks_returns_three_empty_lists(client):
    assert day_tasks(client, "2026-11-01") == {"overdue": [], "pending": [], "completed": []}


def test_task_created_by_the_api_appears_only_on_its_day(client):
    task = create_task(client, due_date="2026-11-05")

    assert day_tasks(client, "2026-11-05") == {"overdue": [], "pending": [task], "completed": []}
    assert day_tasks(client, "2026-11-04")["pending"] == []
    assert day_tasks(client, "2026-11-06")["pending"] == []


# O exemplo da seção 6.4: concluída às 22h30 de 31/10 em Brasília, gravada como 01h30 UTC.
# A data marcada é outra, para provar que o dia vem do completed_at, não do due_date.
def test_task_completed_at_2230_appears_on_the_brasilia_day(client, test_engine):
    task_id = insert_task(
        test_engine,
        due_date=date(2026, 11, 5),
        completed=True,
        completed_at=datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc),
    )

    completed = day_tasks(client, "2026-10-31")["completed"]

    assert ids(completed) == [task_id]
    assert completed[0]["completed_at"] == "2026-11-01T01:30:00Z"
    assert day_tasks(client, "2026-11-01")["completed"] == []
    assert day_tasks(client, "2026-11-05") == {"overdue": [], "pending": [], "completed": []}


# Cada linha é um caso: a hora da conclusão em UTC, o dia em que ela aparece e o dia em que
# ela não aparece. A meia-noite de Brasília é às 03h00 UTC e já pertence ao dia novo.
@pytest.mark.parametrize(
    "completed_at, right_day, wrong_day",
    [
        (
            datetime(2026, 11, 1, 2, 59, 59, 999999, tzinfo=timezone.utc),
            "2026-10-31",
            "2026-11-01",
        ),
        (datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc), "2026-11-01", "2026-10-31"),
    ],
)
def test_completed_task_at_the_limits_of_the_day(
    client, test_engine, completed_at, right_day, wrong_day
):
    task_id = insert_task(test_engine, completed=True, completed_at=completed_at)

    assert ids(day_tasks(client, right_day)["completed"]) == [task_id]
    assert day_tasks(client, wrong_day)["completed"] == []


def test_completed_task_due_today_is_not_pending(client, test_engine):
    task_id = insert_task(
        test_engine,
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )

    tasks = day_tasks(client, "2026-11-01")

    assert tasks["pending"] == []
    assert ids(tasks["completed"]) == [task_id]


# Em dia passado, a tarefa fica em pendentes, porque aquele é o dia marcado dela (seção 6.2).
def test_overdue_task_is_highlighted_only_in_the_today_view(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30))

    today = day_tasks(client, "2026-11-01")
    due_day = day_tasks(client, "2026-10-30")

    assert ids(today["overdue"]) == [task_id]
    assert today["pending"] == []
    assert due_day["overdue"] == []
    assert ids(due_day["pending"]) == [task_id]
    assert day_tasks(client, "2026-10-31") == {"overdue": [], "pending": [], "completed": []}
    assert day_tasks(client, "2026-11-02") == {"overdue": [], "pending": [], "completed": []}


def test_completed_task_is_never_overdue(client, test_engine):
    insert_task(
        test_engine,
        due_date=date(2026, 10, 30),
        completed=True,
        completed_at=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert day_tasks(client, "2026-11-01")["overdue"] == []


# Às 01h30 UTC de 01/11 ainda é 31/10 em Brasília, então a visão de hoje é a de 31/10.
def test_overdue_view_follows_brasilia_today(client, test_engine, monkeypatch):
    fixed_now = datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)
    overdue_id = insert_task(test_engine, due_date=date(2026, 10, 30))
    today_id = insert_task(test_engine, due_date=date(2026, 10, 31))

    today = day_tasks(client, "2026-10-31")

    assert ids(today["overdue"]) == [overdue_id]
    assert ids(today["pending"]) == [today_id]
    assert day_tasks(client, "2026-11-01")["overdue"] == []


# Seção 4.2: a tarefa travada só fica nas atrasadas se estiver mesmo atrasada.
def test_locked_task_with_future_date_stays_on_its_day(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 11, 5), postponements=3)

    assert day_tasks(client, "2026-11-01")["overdue"] == []
    assert ids(day_tasks(client, "2026-11-05")["pending"]) == [task_id]


def test_locked_task_that_is_late_is_overdue(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30), postponements=3)

    assert ids(day_tasks(client, "2026-11-01")["overdue"]) == [task_id]


# A mais antiga foi criada depois, então só a data explica ela vir primeiro.
def test_overdue_orders_by_due_date_before_created_at(client, test_engine):
    insert_task(
        test_engine,
        id=1,
        due_date=date(2026, 10, 30),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    insert_task(
        test_engine,
        id=2,
        due_date=date(2026, 10, 29),
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert ids(day_tasks(client, "2026-11-01")["overdue"]) == [2, 1]


# Cada linha é um grupo da visão de 01/11/2026 e o que uma tarefa precisa ter para cair nele.
DAY_GROUPS = [
    ("overdue", {"due_date": date(2026, 10, 30)}),
    ("pending", {"due_date": date(2026, 11, 1)}),
    (
        "completed",
        {"completed": True, "completed_at": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)},
    ),
]


# O id maior é o mais antigo, então só o created_at explica ele vir primeiro.
@pytest.mark.parametrize("group, fields", DAY_GROUPS)
def test_day_groups_order_by_created_at_not_by_id(client, test_engine, group, fields):
    insert_task(test_engine, id=1, created_at=datetime(2026, 2, 1, tzinfo=timezone.utc), **fields)
    insert_task(test_engine, id=2, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), **fields)

    assert ids(day_tasks(client, "2026-11-01")[group]) == [2, 1]


# No SQLite, o empate já sai em ordem de id mesmo sem o desempate no ORDER BY. Este teste
# documenta o resultado esperado, mas não detecta a remoção do desempate.
@pytest.mark.parametrize("group, fields", DAY_GROUPS)
def test_day_groups_break_created_at_tie_by_id(client, test_engine, group, fields):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    insert_task(test_engine, id=2, created_at=created_at, **fields)
    insert_task(test_engine, id=1, created_at=created_at, **fields)

    assert ids(day_tasks(client, "2026-11-01")[group]) == [1, 2]


# A primeira criada foi concluída por último e tem o id maior, então só a ordem de criação
# explica ela vir primeiro.
def test_completed_orders_by_created_at_not_by_completed_at(client, test_engine):
    insert_task(
        test_engine,
        id=2,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed=True,
        completed_at=datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc),
    )
    insert_task(
        test_engine,
        id=1,
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        completed=True,
        completed_at=datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc),
    )

    assert ids(day_tasks(client, "2026-11-01")["completed"]) == [2, 1]


@pytest.mark.parametrize("day", ["9999-12-31", "0001-01-01"])
def test_extreme_dates_do_not_become_error_500(client, day):
    assert day_tasks(client, day) == {"overdue": [], "pending": [], "completed": []}


def test_last_date_lists_pending_and_completed_tasks(client, test_engine):
    pending_task = create_task(client, due_date="9999-12-31")
    completed_id = insert_task(
        test_engine,
        completed=True,
        completed_at=datetime(9999, 12, 31, 12, 0, tzinfo=timezone.utc),
    )

    tasks = day_tasks(client, "9999-12-31")

    assert ids(tasks["pending"]) == [pending_task["id"]]
    assert ids(tasks["completed"]) == [completed_id]


@pytest.mark.parametrize("day", ["2026-13-01", "abc"])
def test_day_refuses_invalid_date(client, day):
    response = client.get(f"/tasks/day/{day}")

    assert response.status_code == 422
