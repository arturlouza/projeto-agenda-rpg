from datetime import date, datetime, timedelta, timezone
from typing import get_args

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DEFAULT_TASK_COLOR, Task, XpEntry
from app.routers import tasks as tasks_router
from app.routers.tasks import Difficulty
from app.rules.xp import TASK_BASE_XP

UNKNOWN_TYPE_MESSAGE = "Esse tipo de tarefa não existe."
PAST_DATE_MESSAGE = "A data não pode ser anterior a hoje."
COMPLETED_DIFFICULTY_MESSAGE = "Desmarque a tarefa antes de mudar a dificuldade."
COMPLETED_DATE_MESSAGE = "Desmarque a tarefa antes de mudar a data."
LOCKED_DATE_MESSAGE = "A data desta tarefa está travada e não pode mudar."
ALREADY_COMPLETED_MESSAGE = "A tarefa já está concluída."
ALREADY_PENDING_MESSAGE = "A tarefa já está pendente."

# As duas ações sobre o estado da tarefa, no fim da rota.
COMPLETION_ACTIONS = ["complete", "uncomplete"]

# O que uma tarefa inserida no banco precisa ter para estar concluída.
COMPLETED_FIELDS = {
    "completed": True,
    "completed_at": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
}


# Muda o relógio nos dois lugares que leem a hora: o "hoje" de dates.py e o completed_at que
# tasks.py grava ao concluir.
def set_now(monkeypatch, moment):
    monkeypatch.setattr("app.dates.utc_now", lambda: moment)
    monkeypatch.setattr("app.routers.tasks.utc_now", lambda: moment)


# Vale para todos os testes deste arquivo: o "hoje" é sempre 01/11/2026 em Brasília, para
# nenhum teste depender da data real do computador.
@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    set_now(monkeypatch, datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc))


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


# Grava uma tarefa direto no banco e devolve o id dela, porque a API não cria tarefa atrasada
# nem já concluída, e não deixa escolher o id, o created_at nem o completed_at.
def insert_task(test_engine, **fields):
    data = {"title": "Tarefa", "due_date": date(2026, 11, 1), "difficulty": "easy"} | fields

    with Session(test_engine) as session:
        task = Task(**data)
        session.add(task)
        session.commit()
        return task.id


# Grava uma linha de XP direto no banco, para o teste escolher um valor ou um motivo que a API
# não geraria.
def insert_xp_entry(test_engine, amount, reason, task_id):
    with Session(test_engine) as session:
        session.add(XpEntry(amount=amount, reason=reason, task_id=task_id))
        session.commit()


# Lê todas as linhas do histórico de XP direto no banco, porque ainda não há rota para isso.
def xp_entries_in_database(test_engine):
    with Session(test_engine) as session:
        return list(session.exec(select(XpEntry)).all())


# Pede os grupos de um dia pela API, confere que deu certo e devolve o JSON da resposta.
def day_tasks(client, day):
    response = client.get(f"/tasks/day/{day}")
    assert response.status_code == 200
    return response.json()


# Pede os dias de uma semana pela API, confere que deu certo e devolve o JSON da resposta.
def week_tasks(client, day):
    response = client.get(f"/tasks/week/{day}")
    assert response.status_code == 200
    return response.json()


# Devolve só os ids de um grupo, na ordem em que a API respondeu.
def ids(tasks):
    return [task["id"] for task in tasks]


# Devolve só os dias da semana que têm tarefas, cada um com os ids das tarefas dele.
def week_ids(week):
    return {week_day["day"]: ids(week_day["tasks"]) for week_day in week if week_day["tasks"]}


# Confere que o pedido foi recusado com 422 e que nada foi gravado.
def assert_refused(client, test_engine, data):
    response = client.post("/tasks", json=data)

    assert response.status_code == 422
    assert tasks_in_database(test_engine) == []
    return response


# Monta um pedido de edição completo, com os 6 campos, mais o que o teste quiser mudar. A data
# é a mesma que create_task e insert_task usam, então ela só muda quando o teste pedir.
def update_data(**changes):
    return {
        "title": "Título novo",
        "notes": "Nota nova",
        "difficulty": "hard",
        "color": "#112233",
        "task_type_id": None,
        "due_date": "2026-11-01",
    } | changes


# Edita uma tarefa pela API, confere que deu certo e devolve o JSON da resposta.
def update_task(client, task_id, **changes):
    response = client.put(f"/tasks/{task_id}", json=update_data(**changes))
    assert response.status_code == 200
    return response.json()


# Confere que a edição foi recusada com o código esperado e que o registro continua igual.
def assert_update_refused(client, test_engine, task_id, data, status_code=422):
    before = [task.model_dump() for task in tasks_in_database(test_engine)]

    response = client.put(f"/tasks/{task_id}", json=data)

    assert response.status_code == status_code
    assert [task.model_dump() for task in tasks_in_database(test_engine)] == before
    return response


# Conclui uma tarefa pela API, confere que deu certo e devolve o JSON da resposta.
def complete_task(client, task_id):
    response = client.post(f"/tasks/{task_id}/complete")
    assert response.status_code == 200
    return response.json()


# Desmarca uma tarefa pela API, confere que deu certo e devolve o JSON da resposta.
def uncomplete_task(client, task_id):
    response = client.post(f"/tasks/{task_id}/uncomplete")
    assert response.status_code == 200
    return response.json()


# O XP total é a soma de todas as linhas do histórico (seção 4.4).
def xp_total(test_engine):
    return sum(entry.amount for entry in xp_entries_in_database(test_engine))


# Devolve os valores das linhas de uma tarefa, sem contar com nenhuma ordem entre elas.
def task_amounts(test_engine, task_id):
    entries = xp_entries_in_database(test_engine)
    return sorted(entry.amount for entry in entries if entry.task_id == task_id)


# Foto de tudo o que uma recusa não pode mudar: as tarefas e o histórico.
def database_snapshot(test_engine):
    tasks = [task.model_dump() for task in tasks_in_database(test_engine)]
    entries = [entry.model_dump() for entry in xp_entries_in_database(test_engine)]
    return tasks, entries


# Confere que concluir ou desmarcar foi recusado com o código esperado e que nada foi gravado.
def assert_completion_refused(client, test_engine, task_id, action, status_code):
    before = database_snapshot(test_engine)

    response = client.post(f"/tasks/{task_id}/{action}")

    assert response.status_code == status_code
    assert database_snapshot(test_engine) == before
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


def test_week_without_tasks_returns_seven_empty_days(client):
    assert week_tasks(client, "2026-11-04") == [
        {"day": "2026-11-02", "tasks": []},
        {"day": "2026-11-03", "tasks": []},
        {"day": "2026-11-04", "tasks": []},
        {"day": "2026-11-05", "tasks": []},
        {"day": "2026-11-06", "tasks": []},
        {"day": "2026-11-07", "tasks": []},
        {"day": "2026-11-08", "tasks": []},
    ]


# Em 2026, 02/11 é uma segunda, 04/11 é uma quarta e 08/11 é um domingo.
def test_monday_wednesday_and_sunday_return_the_same_week(client):
    create_task(client, due_date="2026-11-05")

    monday_week = week_tasks(client, "2026-11-02")

    assert monday_week[0]["day"] == "2026-11-02"
    assert week_tasks(client, "2026-11-04") == monday_week
    assert week_tasks(client, "2026-11-08") == monday_week


def test_pending_task_appears_only_on_its_day_of_the_week(client):
    task = create_task(client, due_date="2026-11-05")

    week = week_tasks(client, "2026-11-05")

    assert week[3] == {"day": "2026-11-05", "tasks": [task]}
    assert week_ids(week) == {"2026-11-05": [task["id"]]}
    assert week_ids(week_tasks(client, "2026-11-01")) == {}
    assert week_ids(week_tasks(client, "2026-11-09")) == {}


# A data marcada fica na semana seguinte, e a tarefa não pode aparecer lá.
def test_completed_task_appears_on_the_completion_day_not_on_another_week(client, test_engine):
    task_id = insert_task(
        test_engine,
        due_date=date(2026, 11, 5),
        completed=True,
        completed_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
    )

    assert week_ids(week_tasks(client, "2026-10-28")) == {"2026-10-28": [task_id]}
    assert week_ids(week_tasks(client, "2026-11-05")) == {}


# Dentro da mesma semana, a concluída também não fica repetida no dia marcado.
def test_completed_task_appears_only_on_the_completion_day_of_the_week(client, test_engine):
    task_id = insert_task(
        test_engine,
        due_date=date(2026, 10, 30),
        completed=True,
        completed_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
    )

    assert week_ids(week_tasks(client, "2026-10-28")) == {"2026-10-28": [task_id]}


# Às 22h30 de domingo em Brasília, já é segunda-feira em UTC. A tarefa precisa ficar no
# domingo, então ela é da semana que termina em 01/11, não da que começa em 02/11.
def test_task_completed_at_2230_on_sunday_stays_in_that_week(client, test_engine):
    task_id = insert_task(
        test_engine,
        due_date=date(2026, 11, 5),
        completed=True,
        completed_at=datetime(2026, 11, 2, 1, 30, tzinfo=timezone.utc),
    )

    assert week_ids(week_tasks(client, "2026-11-01")) == {"2026-11-01": [task_id]}
    assert week_ids(week_tasks(client, "2026-11-02")) == {}


# Hoje é 01/11, na mesma semana de 30/10, então a tarefa poderia aparecer nas duas colunas.
def test_overdue_task_appears_on_its_due_date_not_on_today(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30))

    assert week_ids(week_tasks(client, "2026-11-01")) == {"2026-10-30": [task_id]}


# Pela ordem de id, viria [1, 2, 3]. Com as pendentes antes das concluídas, viria [1, 3, 2].
# Só o created_at explica [2, 1, 3].
def test_week_day_mixes_pending_and_completed_by_created_at(client, test_engine):
    insert_task(test_engine, id=1, created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    insert_task(
        test_engine,
        id=2,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )
    insert_task(test_engine, id=3, created_at=datetime(2026, 3, 1, tzinfo=timezone.utc))

    assert week_ids(week_tasks(client, "2026-11-01")) == {"2026-11-01": [2, 1, 3]}


# No SQLite, o empate já sai em ordem de id mesmo sem o desempate no ORDER BY. Este teste
# documenta o resultado esperado, mas não detecta a remoção do desempate.
def test_week_day_breaks_created_at_tie_by_id(client, test_engine):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    insert_task(
        test_engine,
        id=2,
        created_at=created_at,
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )
    insert_task(test_engine, id=1, created_at=created_at)

    assert week_ids(week_tasks(client, "2026-11-01")) == {"2026-11-01": [1, 2]}


# 9999-12-31 é uma sexta-feira, então a semana dela tem só os 5 dias que existem.
def test_last_week_has_five_days_and_lists_its_tasks(client, test_engine):
    pending_task = create_task(client, due_date="9999-12-31")
    completed_id = insert_task(
        test_engine,
        completed=True,
        completed_at=datetime(9999, 12, 31, 12, 0, tzinfo=timezone.utc),
    )

    week = week_tasks(client, "9999-12-31")

    assert [week_day["day"] for week_day in week] == [
        "9999-12-27",
        "9999-12-28",
        "9999-12-29",
        "9999-12-30",
        "9999-12-31",
    ]
    assert week_ids(week) == {"9999-12-31": [pending_task["id"], completed_id]}


def test_first_week_does_not_become_error_500(client):
    week = week_tasks(client, "0001-01-01")

    assert len(week) == 7
    assert week[0]["day"] == "0001-01-01"


@pytest.mark.parametrize("day", ["2026-13-01", "abc"])
def test_week_refuses_invalid_date(client, day):
    response = client.get(f"/tasks/week/{day}")

    assert response.status_code == 422


# Confere uma garantia do banco (seção 6.6). O código do app não pode contar com isso.
def test_new_task_does_not_reuse_id_of_deleted_task(client):
    create_task(client)
    largest_id = create_task(client)["id"]
    assert client.delete(f"/tasks/{largest_id}").status_code == 204

    assert create_task(client)["id"] != largest_id


def test_delete_removes_the_task(client, test_engine):
    task = create_task(client)

    response = client.delete(f"/tasks/{task['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert tasks_in_database(test_engine) == []
    assert day_tasks(client, task["due_date"])["pending"] == []


# Seção 4.2: a tarefa travada só sai da lista se for concluída ou excluída, então nenhum
# estado impede a exclusão. Cada linha é um estado: pendente, atrasada, travada e concluída.
@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"due_date": date(2026, 10, 30)},
        {"due_date": date(2026, 11, 5), "postponements": 3},
        {"completed": True, "completed_at": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)},
    ],
)
def test_delete_accepts_task_in_any_state(client, test_engine, fields):
    task_id = insert_task(test_engine, **fields)

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 204
    assert tasks_in_database(test_engine) == []


@pytest.mark.parametrize("task_id", [999, 2147483647])
def test_delete_unknown_task_returns_404(client, test_engine, task_id):
    insert_task(test_engine, id=1)

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 404
    assert len(tasks_in_database(test_engine)) == 1


@pytest.mark.parametrize("task_id", [0, -1, 2147483648, 10**30])
def test_delete_refuses_id_out_of_range(client, test_engine, task_id):
    insert_task(test_engine, id=1)

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 422
    assert len(tasks_in_database(test_engine)) == 1


# Seção 4.3: excluir mantém o XP no histórico. A tarefa tem mais de uma linha, inclusive
# negativa, como acontece ao concluir, desmarcar e concluir de novo.
# Este teste não detecta a remoção do flush da rota: sem ele, a ordem das mudanças saiu certa
# no SQLite, mas nada garante isso, porque os modelos não têm relationship.
def test_delete_keeps_xp_in_history_without_the_task(client, test_engine):
    deleted_id = insert_task(
        test_engine,
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )
    other_id = insert_task(test_engine)
    insert_xp_entry(test_engine, 25, "Tarefa concluída", deleted_id)
    insert_xp_entry(test_engine, -25, "Tarefa desmarcada", deleted_id)
    insert_xp_entry(test_engine, 18, "Tarefa concluída de novo", deleted_id)
    insert_xp_entry(test_engine, 10, "Outra tarefa", other_id)

    response = client.delete(f"/tasks/{deleted_id}")

    assert response.status_code == 204
    entries = xp_entries_in_database(test_engine)
    assert sum(entry.amount for entry in entries) == 28
    assert {(entry.amount, entry.reason, entry.task_id) for entry in entries} == {
        (25, "Tarefa concluída", None),
        (-25, "Tarefa desmarcada", None),
        (18, "Tarefa concluída de novo", None),
        (10, "Outra tarefa", other_id),
    }
    assert [task.id for task in tasks_in_database(test_engine)] == [other_id]


# O delete falha depois que o task_id do histórico já foi limpo. Se a limpeza tivesse sido
# gravada num commit separado, a linha perderia o vínculo com uma tarefa que continua existindo.
def test_failed_delete_changes_nothing(client, test_engine, monkeypatch):
    task_id = insert_task(test_engine)
    insert_xp_entry(test_engine, 25, "Tarefa concluída", task_id)

    def fail_delete(session, instance):
        raise RuntimeError("Falha simulada")

    monkeypatch.setattr(Session, "delete", fail_delete)

    with pytest.raises(RuntimeError):
        client.delete(f"/tasks/{task_id}")

    assert [task.id for task in tasks_in_database(test_engine)] == [task_id]
    assert [entry.task_id for entry in xp_entries_in_database(test_engine)] == [task_id]


def test_update_saves_all_fields(client, test_engine):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]
    task = create_task(client)

    updated = update_task(client, task["id"], task_type_id=task_type_id)

    assert updated["title"] == "Título novo"
    assert updated["notes"] == "Nota nova"
    assert updated["difficulty"] == "hard"
    assert updated["color"] == "#112233"
    assert updated["task_type_id"] == task_type_id

    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.title == "Título novo"
    assert saved_task.notes == "Nota nova"
    assert saved_task.difficulty == "hard"
    assert saved_task.color == "#112233"
    assert saved_task.task_type_id == task_type_id


def test_update_appears_in_the_day_list(client):
    task = create_task(client)

    updated = update_task(client, task["id"])

    assert day_tasks(client, task["due_date"])["pending"] == [updated]


# O PUT substitui só o que o pedido pode definir. Os valores são diferentes dos padrões, para
# provar que a rota não volta nenhum deles ao padrão.
def test_update_keeps_fields_that_the_request_does_not_set(client, test_engine):
    task_id = insert_task(
        test_engine,
        due_date=date(2026, 10, 30),
        completed=True,
        completed_at=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        postponements=2,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    update_task(client, task_id, difficulty="easy", due_date="2026-10-30")

    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.id == task_id
    assert saved_task.due_date == date(2026, 10, 30)
    assert saved_task.completed is True
    assert saved_task.completed_at == datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    assert saved_task.postponements == 2
    assert saved_task.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


# Sem esta recusa, esquecer um campo apagaria as notas ou voltaria a cor ao padrão.
@pytest.mark.parametrize(
    "field", ["title", "notes", "difficulty", "color", "task_type_id", "due_date"]
)
def test_update_refuses_missing_field(client, test_engine, field):
    task = create_task(client, notes="Capítulo 3", color="#ABCDEF")
    data = update_data()
    del data[field]

    assert_update_refused(client, test_engine, task["id"], data)


def test_update_with_null_removes_notes_and_task_type(client, test_engine):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]
    task = create_task(client, notes="Capítulo 3", task_type_id=task_type_id)

    updated = update_task(client, task["id"], notes=None, task_type_id=None)

    assert updated["notes"] is None
    assert updated["task_type_id"] is None
    assert tasks_in_database(test_engine)[0].notes is None
    assert tasks_in_database(test_engine)[0].task_type_id is None


def test_update_removes_spaces_from_the_ends_of_the_title(client):
    task = create_task(client)

    updated = update_task(client, task["id"], title="  Título novo  ")

    assert updated["title"] == "Título novo"


# Os espaços das pontas saem antes da contagem, então os dois títulos têm 100 caracteres.
@pytest.mark.parametrize("title", ["a" * 100, "  " + "a" * 100 + "  "])
def test_update_accepts_title_with_100_characters(client, title):
    task = create_task(client)

    updated = update_task(client, task["id"], title=title)

    assert updated["title"] == "a" * 100


@pytest.mark.parametrize("title", ["", "   ", "a" * 101, None])
def test_update_refuses_invalid_title(client, test_engine, title):
    task = create_task(client)

    assert_update_refused(client, test_engine, task["id"], update_data(title=title))


def test_update_removes_spaces_from_the_ends_of_the_notes(client):
    task = create_task(client)

    updated = update_task(client, task["id"], notes="  Capítulo 3  ")

    assert updated["notes"] == "Capítulo 3"


# Os espaços das pontas saem antes da contagem, então as duas notas têm 1.000 caracteres.
@pytest.mark.parametrize("notes", ["a" * 1000, "  " + "a" * 1000 + "  "])
def test_update_accepts_notes_with_1000_characters(client, notes):
    task = create_task(client)

    updated = update_task(client, task["id"], notes=notes)

    assert updated["notes"] == "a" * 1000


@pytest.mark.parametrize("notes", ["", "   "])
def test_update_saves_empty_notes_as_null(client, test_engine, notes):
    task = create_task(client, notes="Capítulo 3")

    updated = update_task(client, task["id"], notes=notes)

    assert updated["notes"] is None
    assert tasks_in_database(test_engine)[0].notes is None


def test_update_refuses_notes_with_1001_characters(client, test_engine):
    task = create_task(client, notes="Capítulo 3")

    assert_update_refused(client, test_engine, task["id"], update_data(notes="a" * 1001))


@pytest.mark.parametrize("color", ["#ff0000", "#FF0000", "#Ff0000"])
def test_update_saves_color_in_uppercase(client, color):
    task = create_task(client)

    updated = update_task(client, task["id"], color=color)

    assert updated["color"] == "#FF0000"


# O null é recusado aqui, ao contrário de notas e tipo: toda tarefa tem uma cor.
@pytest.mark.parametrize(
    "color", ["#FFF", "FF0000", "#GGGGGG", "#FF00000", " #FF0000 ", "#FF0000\n", "", None]
)
def test_update_refuses_invalid_color(client, test_engine, color):
    task = create_task(client)

    assert_update_refused(client, test_engine, task["id"], update_data(color=color))


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_update_changes_difficulty_of_pending_task(client, difficulty):
    task = create_task(client, difficulty="medium")

    updated = update_task(client, task["id"], difficulty=difficulty)

    assert updated["difficulty"] == difficulty


@pytest.mark.parametrize("difficulty", ["extreme", "Easy", "", None])
def test_update_refuses_invalid_difficulty(client, test_engine, difficulty):
    task = create_task(client)

    assert_update_refused(client, test_engine, task["id"], update_data(difficulty=difficulty))


# Inexistente ou fora do intervalo do banco, a recusa e a mensagem são as mesmas.
@pytest.mark.parametrize(
    "task_type_id", [999, 0, -1, 2147483647, 2147483648, 10**30, -(10**30)]
)
def test_update_refuses_unknown_task_type(client, test_engine, task_type_id):
    task = create_task(client)

    response = assert_update_refused(
        client, test_engine, task["id"], update_data(task_type_id=task_type_id)
    )

    assert response.json()["detail"] == UNKNOWN_TYPE_MESSAGE


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
def test_update_refuses_unknown_field(client, test_engine, extra_field):
    task = create_task(client)

    assert_update_refused(client, test_engine, task["id"], update_data(**extra_field))


# A dificuldade é a mesma do pedido, então só título, notas, cor e tipo mudam.
def test_completed_task_accepts_title_notes_color_and_task_type(client, test_engine):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]
    task_id = insert_task(
        test_engine,
        difficulty="hard",
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )

    updated = update_task(client, task_id, difficulty="hard", task_type_id=task_type_id)

    assert updated["title"] == "Título novo"
    assert updated["notes"] == "Nota nova"
    assert updated["color"] == "#112233"
    assert updated["task_type_id"] == task_type_id
    assert updated["completed"] is True


def test_completed_task_refuses_changing_difficulty(client, test_engine):
    task_id = insert_task(
        test_engine,
        difficulty="easy",
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )

    response = assert_update_refused(
        client, test_engine, task_id, update_data(difficulty="hard"), status_code=409
    )

    assert response.json()["detail"] == COMPLETED_DIFFICULTY_MESSAGE


# Seção 6.1: o formulário envia todos os campos, e mandar o valor atual não é mudança.
def test_completed_task_accepts_the_same_difficulty(client, test_engine):
    task_id = insert_task(
        test_engine,
        difficulty="hard",
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )

    updated = update_task(client, task_id, title="Título novo", difficulty="hard")

    assert updated["title"] == "Título novo"
    assert updated["difficulty"] == "hard"


# O dado é conferido antes do estado da tarefa, então o pedido com os dois problemas dá 422.
def test_update_refuses_invalid_data_before_checking_task_state(client, test_engine):
    task_id = insert_task(
        test_engine,
        difficulty="easy",
        completed=True,
        completed_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    )

    response = assert_update_refused(
        client, test_engine, task_id, update_data(difficulty="hard", task_type_id=999)
    )

    assert response.json()["detail"] == UNKNOWN_TYPE_MESSAGE


# Seção 6.1: mandar a data que a tarefa já tem não é mudança, então nenhuma regra de data se
# aplica e o atraso não entra no contador. Cada linha é um estado: atrasada, travada por
# adiamento manual, travada por atraso, travada pelos dois, concluída e concluída com data antiga.
@pytest.mark.parametrize(
    "fields",
    [
        {"due_date": date(2026, 10, 30)},
        {"due_date": date(2026, 11, 5), "postponements": 3},
        {"due_date": date(2026, 10, 29)},
        {"due_date": date(2026, 10, 30), "postponements": 3},
        {"due_date": date(2026, 11, 1), **COMPLETED_FIELDS},
        {"due_date": date(2026, 10, 30), **COMPLETED_FIELDS},
    ],
)
def test_same_date_accepts_editing_in_any_state(client, test_engine, fields):
    task_id = insert_task(test_engine, **fields)

    updated = update_task(
        client,
        task_id,
        title="Título novo",
        difficulty="easy",
        due_date=fields["due_date"].isoformat(),
    )

    assert updated["title"] == "Título novo"
    assert updated["due_date"] == fields["due_date"].isoformat()
    assert updated["postponements"] == fields.get("postponements", 0)
    assert tasks_in_database(test_engine)[0].title == "Título novo"


@pytest.mark.parametrize("task_id", [999, 2147483647])
def test_update_unknown_task_returns_404(client, test_engine, task_id):
    insert_task(test_engine, id=1)

    assert_update_refused(client, test_engine, task_id, update_data(), status_code=404)


@pytest.mark.parametrize("task_id", [0, -1, 2147483648, 10**30])
def test_update_refuses_id_out_of_range(client, test_engine, task_id):
    insert_task(test_engine, id=1)

    assert_update_refused(client, test_engine, task_id, update_data())


@pytest.mark.parametrize("postponements, expected", [(0, 1), (1, 2), (2, 3)])
def test_moving_date_later_counts_one_postponement(client, test_engine, postponements, expected):
    task_id = insert_task(test_engine, due_date=date(2026, 11, 5), postponements=postponements)

    updated = update_task(client, task_id, due_date="2026-11-10")

    assert updated["due_date"] == "2026-11-10"
    assert updated["postponements"] == expected
    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.due_date == date(2026, 11, 10)
    assert saved_task.postponements == expected


def test_changed_date_moves_the_task_in_the_day_list(client):
    task = create_task(client)

    updated = update_task(client, task["id"], due_date="2026-11-05")

    assert day_tasks(client, "2026-11-05")["pending"] == [updated]
    assert day_tasks(client, "2026-11-01")["pending"] == []


# Na segunda vez, a data já é a mesma, então o pedido repetido não conta outro adiamento.
def test_repeating_the_same_update_counts_one_postponement(client):
    task = create_task(client)

    update_task(client, task["id"], due_date="2026-11-05")
    updated = update_task(client, task["id"], due_date="2026-11-05")

    assert updated["postponements"] == 1


# Seção 4.2: "0 + 2 + 1 = 3", para qualquer data nova, inclusive hoje.
@pytest.mark.parametrize("new_date", ["2026-11-01", "2026-11-05"])
def test_overdue_task_adds_days_late_to_the_counter(client, test_engine, new_date):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30))

    updated = update_task(client, task_id, due_date=new_date)

    assert updated["due_date"] == new_date
    assert updated["postponements"] == 3


# Antecipar não conta como adiamento, nem quando a data nova é hoje.
@pytest.mark.parametrize("new_date", ["2026-11-03", "2026-11-01"])
def test_moving_date_earlier_keeps_the_counter(client, test_engine, new_date):
    task_id = insert_task(test_engine, due_date=date(2026, 11, 5), postponements=1)

    updated = update_task(client, task_id, due_date=new_date)

    assert updated["due_date"] == new_date
    assert updated["postponements"] == 1


# A segunda linha já está atrasada e 31/10 é depois da data dela, mas continua antes de hoje.
@pytest.mark.parametrize("due_date", [date(2026, 11, 5), date(2026, 10, 30)])
def test_update_refuses_new_date_before_today(client, test_engine, due_date):
    task_id = insert_task(test_engine, due_date=due_date)

    response = assert_update_refused(
        client, test_engine, task_id, update_data(due_date="2026-10-31")
    )

    assert response.json()["detail"] == PAST_DATE_MESSAGE


@pytest.mark.parametrize("due_date", ["01/11/2026", "2026-13-01", "", None])
def test_update_refuses_invalid_date(client, test_engine, due_date):
    task = create_task(client)

    assert_update_refused(client, test_engine, task["id"], update_data(due_date=due_date))


# Com 2 adiamentos efetivos, a data ainda muda: um pelo contador e outro, na segunda linha, pelo
# dia de atraso. A conta dá no máximo 2 + 1 = 3 (seção 6.1).
@pytest.mark.parametrize(
    "postponements, due_date", [(2, date(2026, 11, 1)), (1, date(2026, 10, 31))]
)
def test_date_still_changes_with_two_effective_postponements(
    client, test_engine, postponements, due_date
):
    task_id = insert_task(test_engine, due_date=due_date, postponements=postponements)

    updated = update_task(client, task_id, due_date="2026-11-05")

    assert updated["due_date"] == "2026-11-05"
    assert updated["postponements"] == 3


# Seção 4.2: a data 5 dias à frente não pode destravar a tarefa (3 − 5 = −2). As datas são uma
# depois, uma antes da atual e hoje: nenhuma passa pela trava, nem para antecipar.
@pytest.mark.parametrize("new_date", ["2026-11-10", "2026-11-03", "2026-11-01"])
def test_task_locked_by_manual_postponements_refuses_any_new_date(client, test_engine, new_date):
    task_id = insert_task(test_engine, due_date=date(2026, 11, 6), postponements=3)

    response = assert_update_refused(
        client, test_engine, task_id, update_data(due_date=new_date), status_code=409
    )

    assert response.json()["detail"] == LOCKED_DATE_MESSAGE


# Cada estado é uma forma de travar com atraso: só atraso, adiamento mais atraso e 3 adiamentos
# mais atraso. A data nova é hoje ou depois, porque antes de hoje o pedido daria 422.
@pytest.mark.parametrize(
    "postponements, due_date",
    [(0, date(2026, 10, 29)), (1, date(2026, 10, 30)), (3, date(2026, 10, 30))],
)
@pytest.mark.parametrize("new_date", ["2026-11-01", "2026-11-05"])
def test_task_locked_by_days_late_refuses_new_date(
    client, test_engine, postponements, due_date, new_date
):
    task_id = insert_task(test_engine, due_date=due_date, postponements=postponements)

    response = assert_update_refused(
        client, test_engine, task_id, update_data(due_date=new_date), status_code=409
    )

    assert response.json()["detail"] == LOCKED_DATE_MESSAGE


# A dificuldade é a mesma da tarefa, então só a data explica o 409. A segunda linha antecipa.
@pytest.mark.parametrize(
    "due_date, new_date",
    [(date(2026, 11, 1), "2026-11-05"), (date(2026, 11, 5), "2026-11-03")],
)
def test_completed_task_refuses_changing_date(client, test_engine, due_date, new_date):
    task_id = insert_task(test_engine, due_date=due_date, **COMPLETED_FIELDS)

    response = assert_update_refused(
        client,
        test_engine,
        task_id,
        update_data(difficulty="easy", due_date=new_date),
        status_code=409,
    )

    assert response.json()["detail"] == COMPLETED_DATE_MESSAGE


# A data anterior a hoje é um dado inválido, então vale o 422 mesmo com a tarefa impedida de
# mudar. Cada linha é um estado: travada por adiamento manual, travada por atraso (antecipar
# é sempre ir para antes de hoje, então aqui nunca dá 409) e concluída.
@pytest.mark.parametrize(
    "fields, new_date",
    [
        ({"due_date": date(2026, 11, 6), "postponements": 3}, "2026-10-31"),
        ({"due_date": date(2026, 10, 29)}, "2026-10-28"),
        (COMPLETED_FIELDS, "2026-10-31"),
    ],
)
def test_past_date_is_refused_before_checking_task_state(client, test_engine, fields, new_date):
    task_id = insert_task(test_engine, **fields)

    response = assert_update_refused(
        client, test_engine, task_id, update_data(difficulty="easy", due_date=new_date)
    )

    assert response.json()["detail"] == PAST_DATE_MESSAGE


def test_past_date_is_refused_before_checking_task_type(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 11, 5))

    response = assert_update_refused(
        client, test_engine, task_id, update_data(due_date="2026-10-31", task_type_id=999)
    )

    assert response.json()["detail"] == PAST_DATE_MESSAGE


# O tipo é um dado, então o 422 dele vem antes do 409 da trava e do 409 da tarefa concluída.
@pytest.mark.parametrize(
    "fields",
    [{"due_date": date(2026, 11, 6), "postponements": 3}, COMPLETED_FIELDS],
)
def test_unknown_task_type_is_refused_before_changing_date(client, test_engine, fields):
    task_id = insert_task(test_engine, **fields)

    response = assert_update_refused(
        client,
        test_engine,
        task_id,
        update_data(difficulty="easy", due_date="2026-11-10", task_type_id=999),
    )

    assert response.json()["detail"] == UNKNOWN_TYPE_MESSAGE


# A tarefa concluída recebe a mensagem que diz o que fazer: desmarcar. A trava vem depois.
def test_completed_and_locked_task_gets_the_completed_message(client, test_engine):
    task_id = insert_task(
        test_engine, due_date=date(2026, 11, 5), postponements=3, **COMPLETED_FIELDS
    )

    response = assert_update_refused(
        client,
        test_engine,
        task_id,
        update_data(difficulty="easy", due_date="2026-11-10"),
        status_code=409,
    )

    assert response.json()["detail"] == COMPLETED_DATE_MESSAGE


# O roteiro manual da etapa 5.9, do começo ao fim, só pela API.
def test_three_date_changes_lock_the_date_but_title_still_changes(client, test_engine):
    task = create_task(client)

    for new_date, expected in [("2026-11-02", 1), ("2026-11-03", 2), ("2026-11-04", 3)]:
        updated = update_task(client, task["id"], due_date=new_date)
        assert updated["postponements"] == expected

    assert_update_refused(
        client, test_engine, task["id"], update_data(due_date="2026-11-05"), status_code=409
    )

    updated = update_task(client, task["id"], title="Só o título", due_date="2026-11-04")

    assert updated["title"] == "Só o título"
    assert updated["postponements"] == 3


# Às 01h30 UTC de 01/11 ainda é 31/10 em Brasília, então o atraso é de 1 dia. Em UTC, seriam
# 2 dias: 31/10 daria 422, por ser anterior ao dia em UTC.
def test_date_change_counts_days_late_in_brasilia(client, test_engine, monkeypatch):
    fixed_now = datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30))

    updated = update_task(client, task_id, due_date="2026-10-31")

    assert updated["postponements"] == 2


# No mesmo horário, a tarefa vence "hoje" em Brasília e não está atrasada. Em UTC, ela teria
# 1 dia de atraso e estaria travada, com 2 + 1 = 3 adiamentos efetivos.
def test_lock_counts_days_late_in_brasilia(client, test_engine, monkeypatch):
    fixed_now = datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: fixed_now)
    task_id = insert_task(test_engine, due_date=date(2026, 10, 31), postponements=2)

    updated = update_task(client, task_id, due_date="2026-11-05")

    assert updated["postponements"] == 3


def test_complete_returns_the_task_and_the_xp_change(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")

    result = complete_task(client, task_id)

    assert result["xp_change"] == 25
    assert result["task"]["id"] == task_id
    assert result["task"]["completed"] is True
    assert result["task"]["completed_at"] == "2026-11-01T12:00:00Z"


def test_complete_saves_the_completion_in_utc(client, test_engine):
    task_id = insert_task(test_engine)

    complete_task(client, task_id)

    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.completed is True
    assert saved_task.completed_at == datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_complete_writes_one_history_line(client, test_engine):
    task_id = insert_task(test_engine, title="Ler 30 páginas", difficulty="medium")

    complete_task(client, task_id)

    entries = xp_entries_in_database(test_engine)
    assert [(entry.amount, entry.reason, entry.task_id) for entry in entries] == [
        (25, "Tarefa concluída: Ler 30 páginas", task_id)
    ]


def test_uncomplete_returns_the_task_and_the_xp_change(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")
    complete_task(client, task_id)

    result = uncomplete_task(client, task_id)

    assert result["xp_change"] == -25
    assert result["task"]["id"] == task_id
    assert result["task"]["completed"] is False
    assert result["task"]["completed_at"] is None


def test_uncomplete_clears_the_completion(client, test_engine):
    task_id = insert_task(test_engine)
    complete_task(client, task_id)

    uncomplete_task(client, task_id)

    saved_task = tasks_in_database(test_engine)[0]
    assert saved_task.completed is False
    assert saved_task.completed_at is None


def test_uncomplete_writes_one_history_line(client, test_engine):
    task_id = insert_task(test_engine, title="Ler 30 páginas", difficulty="medium")
    complete_task(client, task_id)

    uncomplete_task(client, task_id)

    entries = xp_entries_in_database(test_engine)
    assert {(entry.amount, entry.reason, entry.task_id) for entry in entries} == {
        (25, "Tarefa concluída: Ler 30 páginas", task_id),
        (-25, "Tarefa desmarcada: Ler 30 páginas", task_id),
    }


# O critério da tarefa 6, com outra tarefa concluída para o total de antes não ser 0. A cada
# passo, a soma da tarefa é 0 quando ela está pendente e o XP ganho quando está concluída.
@pytest.mark.parametrize("cycles", [1, 2, 5])
def test_complete_and_uncomplete_keep_the_total_xp(client, test_engine, cycles):
    complete_task(client, insert_task(test_engine, difficulty="hard"))
    task_id = insert_task(test_engine, difficulty="medium")
    total_before = xp_total(test_engine)

    for _ in range(cycles):
        complete_task(client, task_id)
        assert sum(task_amounts(test_engine, task_id)) == 25
        assert xp_total(test_engine) == total_before + 25

        uncomplete_task(client, task_id)
        assert sum(task_amounts(test_engine, task_id)) == 0
        assert xp_total(test_engine) == total_before


# Cada linha é um caso: dificuldade, adiamentos efetivos e o XP esperado, seção 4.2.
@pytest.mark.parametrize(
    "difficulty, postponements, expected_xp",
    [
        ("easy", 0, 10),
        ("easy", 1, 7),
        ("easy", 2, 5),
        ("easy", 3, 2),
        ("easy", 4, 0),
        ("medium", 0, 25),
        ("medium", 1, 18),
        ("medium", 2, 12),
        ("medium", 3, 6),
        ("medium", 4, 0),
        ("hard", 0, 50),
        ("hard", 1, 37),
        ("hard", 2, 25),
        ("hard", 3, 12),
        ("hard", 4, 0),
    ],
)
def test_complete_gives_the_xp_of_the_difficulty_and_postponements(
    client, test_engine, difficulty, postponements, expected_xp
):
    task_id = insert_task(test_engine, difficulty=difficulty, postponements=postponements)

    result = complete_task(client, task_id)

    assert result["xp_change"] == expected_xp
    assert task_amounts(test_engine, task_id) == [expected_xp]


# Tarefa média. A primeira linha é a conta do plano: 25 × (1 − 0,25 × 2) = 12,5, que vira 12.
@pytest.mark.parametrize(
    "postponements, days_late, expected_xp",
    [
        (1, 1, 12),
        (0, 1, 18),
        (0, 2, 12),
        (0, 3, 6),
        (2, 1, 6),
        (0, 4, 0),
        (1, 3, 0),
    ],
)
def test_complete_adds_days_late_to_manual_postponements(
    client, test_engine, postponements, days_late, expected_xp
):
    due_date = date(2026, 11, 1) - timedelta(days=days_late)
    task_id = insert_task(
        test_engine, difficulty="medium", postponements=postponements, due_date=due_date
    )

    assert complete_task(client, task_id)["xp_change"] == expected_xp


@pytest.mark.parametrize("due_date", [date(2026, 11, 2), date(2026, 11, 10), date.max])
def test_complete_before_the_due_date_is_worth_100_percent(client, test_engine, due_date):
    task_id = insert_task(test_engine, difficulty="medium", due_date=due_date)

    assert complete_task(client, task_id)["xp_change"] == 25


# A data futura não desconta os adiamentos manuais: o atraso negativo conta como 0.
@pytest.mark.parametrize("postponements, expected_xp", [(1, 18), (3, 6)])
def test_future_date_does_not_cancel_manual_postponements(
    client, test_engine, postponements, expected_xp
):
    task_id = insert_task(
        test_engine, difficulty="medium", postponements=postponements, due_date=date(2026, 11, 6)
    )

    assert complete_task(client, task_id)["xp_change"] == expected_xp


# Às 02h59 UTC de 01/11 ainda são 23h59 de 31/10 em Brasília, e às 03h00 UTC o dia já virou.
# Em UTC, os dois horários já seriam 01/11, e a primeira e a terceira linhas dariam outro valor.
@pytest.mark.parametrize(
    "now, due_date, expected_xp",
    [
        (datetime(2026, 11, 1, 2, 59, tzinfo=timezone.utc), date(2026, 10, 31), 25),
        (datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc), date(2026, 10, 31), 18),
        (datetime(2026, 11, 1, 2, 59, tzinfo=timezone.utc), date(2026, 10, 30), 18),
    ],
)
def test_days_late_follow_the_brasilia_day(
    client, test_engine, monkeypatch, now, due_date, expected_xp
):
    set_now(monkeypatch, now)
    task_id = insert_task(test_engine, difficulty="medium", due_date=due_date)

    assert complete_task(client, task_id)["xp_change"] == expected_xp


# Com 4 ou mais adiamentos efetivos, concluir vale 0, mas as linhas existem para mostrar que a
# tarefa foi concluída e não rendeu nada (seção 4.4).
def test_task_worth_zero_writes_zero_lines(client, test_engine):
    task_id = insert_task(test_engine, title="Atrasada", due_date=date(2026, 10, 28))

    completed = complete_task(client, task_id)
    uncompleted = uncomplete_task(client, task_id)

    assert completed["xp_change"] == 0
    assert completed["task"]["completed"] is True
    assert uncompleted["xp_change"] == 0
    entries = xp_entries_in_database(test_engine)
    assert {(entry.amount, entry.reason) for entry in entries} == {
        (0, "Tarefa concluída: Atrasada"),
        (0, "Tarefa desmarcada: Atrasada"),
    }


# Depois de 5 dias, a tarefa valeria 0: a devolução vem do histórico, não de uma conta nova.
def test_uncomplete_returns_the_saved_value_days_later(client, test_engine, monkeypatch):
    task_id = insert_task(test_engine, difficulty="medium")
    complete_task(client, task_id)

    set_now(monkeypatch, datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc))
    result = uncomplete_task(client, task_id)

    assert result["xp_change"] == -25
    assert xp_total(test_engine) == 0


# Nenhuma conta de task_xp daria 7 numa tarefa média, então só o histórico explica a devolução.
def test_uncomplete_reads_the_value_from_the_history(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium", **COMPLETED_FIELDS)
    insert_xp_entry(test_engine, 7, "Tarefa concluída: Tarefa", task_id)

    assert uncomplete_task(client, task_id)["xp_change"] == -7
    assert xp_total(test_engine) == 0


def test_uncomplete_does_not_touch_lines_of_another_task(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")
    other_id = insert_task(test_engine, difficulty="hard")
    complete_task(client, task_id)
    complete_task(client, other_id)

    result = uncomplete_task(client, task_id)

    assert result["xp_change"] == -25
    assert task_amounts(test_engine, other_id) == [50]
    assert xp_total(test_engine) == 50


def test_complete_and_uncomplete_keep_due_date_and_postponements(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 31), postponements=1)

    completed = complete_task(client, task_id)
    uncompleted = uncomplete_task(client, task_id)

    for result in [completed, uncompleted]:
        assert result["task"]["due_date"] == "2026-10-31"
        assert result["task"]["postponements"] == 1


# A concluída às 22h30 de 31/10 em Brasília (01h30 UTC de 01/11) aparece em 31/10. Ao ser
# desmarcada, volta ao dia marcado, aqui 05/11.
def test_completed_task_moves_to_the_brasilia_day_and_returns_to_its_due_date(
    client, test_engine, monkeypatch
):
    set_now(monkeypatch, datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc))
    task_id = insert_task(test_engine, due_date=date(2026, 11, 5))

    complete_task(client, task_id)

    assert ids(day_tasks(client, "2026-10-31")["completed"]) == [task_id]
    assert day_tasks(client, "2026-11-01")["completed"] == []
    assert day_tasks(client, "2026-11-05")["pending"] == []
    assert week_ids(week_tasks(client, "2026-10-31")) == {"2026-10-31": [task_id]}
    assert week_ids(week_tasks(client, "2026-11-05")) == {}

    uncomplete_task(client, task_id)

    assert day_tasks(client, "2026-10-31")["completed"] == []
    assert ids(day_tasks(client, "2026-11-05")["pending"]) == [task_id]
    assert week_ids(week_tasks(client, "2026-10-31")) == {}
    assert week_ids(week_tasks(client, "2026-11-05")) == {"2026-11-05": [task_id]}


def test_uncompleted_late_task_returns_to_overdue(client, test_engine):
    task_id = insert_task(test_engine, due_date=date(2026, 10, 30))

    complete_task(client, task_id)
    today = day_tasks(client, "2026-11-01")
    assert today["overdue"] == []
    assert ids(today["completed"]) == [task_id]

    uncomplete_task(client, task_id)
    today = day_tasks(client, "2026-11-01")
    assert ids(today["overdue"]) == [task_id]
    assert today["completed"] == []


# A tabela da decisão 9 do plano: cada volta vale menos, e o total nunca passa do valor atual.
# Com uma conta nova ao desmarcar, a linha de 02/11 seria −6, e sobrariam 6 XP de graça.
def test_late_task_is_worth_less_after_each_cycle(client, test_engine, monkeypatch):
    task_id = insert_task(test_engine, difficulty="medium", due_date=date(2026, 10, 30))

    assert complete_task(client, task_id)["xp_change"] == 12
    assert xp_total(test_engine) == 12

    set_now(monkeypatch, datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc))
    assert uncomplete_task(client, task_id)["xp_change"] == -12
    assert xp_total(test_engine) == 0
    assert complete_task(client, task_id)["xp_change"] == 6
    assert xp_total(test_engine) == 6

    set_now(monkeypatch, datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc))
    assert uncomplete_task(client, task_id)["xp_change"] == -6
    assert xp_total(test_engine) == 0
    assert complete_task(client, task_id)["xp_change"] == 0
    assert xp_total(test_engine) == 0


# Marcar e desmarcar várias vezes por dia, em dias seguidos, nunca rende mais que o valor do dia.
@pytest.mark.parametrize(
    "day, expected_xp",
    [(1, 25), (2, 18), (3, 12), (4, 6), (5, 0), (6, 0)],
)
def test_cycles_never_give_more_than_the_value_of_the_day(
    client, test_engine, monkeypatch, day, expected_xp
):
    task_id = insert_task(test_engine, difficulty="medium")

    for current_day in range(1, day + 1):
        set_now(monkeypatch, datetime(2026, 11, current_day, 12, 0, tzinfo=timezone.utc))
        for _ in range(3):
            complete_task(client, task_id)
            uncomplete_task(client, task_id)
        assert xp_total(test_engine) == 0

    complete_task(client, task_id)

    assert xp_total(test_engine) == expected_xp


# Trocar a dificuldade da tarefa pendente é permitido (seção 6.1), mas os valores não se somam.
def test_changing_difficulty_after_uncomplete_does_not_accumulate_xp(client, test_engine):
    task_id = insert_task(test_engine, difficulty="easy")

    assert complete_task(client, task_id)["xp_change"] == 10
    uncomplete_task(client, task_id)
    update_task(client, task_id, difficulty="hard")
    assert complete_task(client, task_id)["xp_change"] == 50

    assert xp_total(test_engine) == 50


def test_task_completed_by_the_api_refuses_changing_difficulty(client, test_engine):
    task_id = insert_task(test_engine, difficulty="easy")
    complete_task(client, task_id)

    response = assert_update_refused(
        client, test_engine, task_id, update_data(difficulty="hard"), status_code=409
    )

    assert response.json()["detail"] == COMPLETED_DIFFICULTY_MESSAGE


# Seção 4.3: excluir uma tarefa concluída mantém o XP que ela deu.
def test_deleting_completed_task_keeps_its_xp(client, test_engine):
    task_id = insert_task(test_engine, title="Ler", difficulty="medium")
    complete_task(client, task_id)

    assert client.delete(f"/tasks/{task_id}").status_code == 204

    entries = xp_entries_in_database(test_engine)
    assert [(entry.amount, entry.reason, entry.task_id) for entry in entries] == [
        (25, "Tarefa concluída: Ler", None)
    ]


# Seção 4.3: para remover o XP, é preciso desmarcar antes de excluir.
def test_uncompleting_before_deleting_removes_the_xp(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")
    complete_task(client, task_id)
    uncomplete_task(client, task_id)

    assert client.delete(f"/tasks/{task_id}").status_code == 204

    assert xp_total(test_engine) == 0
    assert [entry.task_id for entry in xp_entries_in_database(test_engine)] == [None, None]


def test_complete_refuses_completed_task(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")
    complete_task(client, task_id)

    response = assert_completion_refused(client, test_engine, task_id, "complete", 409)

    assert response.json()["detail"] == ALREADY_COMPLETED_MESSAGE
    assert task_amounts(test_engine, task_id) == [25]


def test_uncomplete_refuses_pending_task(client, test_engine):
    task_id = insert_task(test_engine)

    response = assert_completion_refused(client, test_engine, task_id, "uncomplete", 409)

    assert response.json()["detail"] == ALREADY_PENDING_MESSAGE
    assert xp_entries_in_database(test_engine) == []


@pytest.mark.parametrize("action", COMPLETION_ACTIONS)
@pytest.mark.parametrize("task_id", [999, 2147483647])
def test_completion_of_unknown_task_returns_404(client, test_engine, action, task_id):
    insert_task(test_engine, id=1)

    assert_completion_refused(client, test_engine, task_id, action, 404)


@pytest.mark.parametrize("action", COMPLETION_ACTIONS)
@pytest.mark.parametrize("task_id", [0, -1, 2147483648, 10**30])
def test_completion_refuses_id_out_of_range(client, test_engine, action, task_id):
    insert_task(test_engine, id=1)

    assert_completion_refused(client, test_engine, task_id, action, 422)


@pytest.mark.parametrize("action", COMPLETION_ACTIONS)
def test_completion_of_deleted_task_returns_404(client, test_engine, action):
    task_id = insert_task(test_engine)
    assert client.delete(f"/tasks/{task_id}").status_code == 204

    assert_completion_refused(client, test_engine, task_id, action, 404)


# Seção 6.7: nenhum GET altera dados, porque a conferência de Origin não cobre o GET.
@pytest.mark.parametrize("action", COMPLETION_ACTIONS)
def test_completion_does_not_accept_get(client, test_engine, action):
    task_id = insert_task(test_engine)
    before = database_snapshot(test_engine)

    response = client.get(f"/tasks/{task_id}/{action}")

    assert response.status_code == 405
    assert database_snapshot(test_engine) == before


# Reproduz o toque duplo sem depender de threads: a sessão velha lê a tarefa pendente, outro
# pedido a conclui, e só então a rota roda com a leitura velha. Conferir task.completed em
# Python deixaria passar e gravaria uma segunda linha. A variável old_task precisa existir: a
# sessão só guarda a leitura enquanto algo aponta para ela. Sem a variável, a rota leria o
# valor novo do banco, e o teste passaria mesmo sem a proteção.
def test_complete_with_an_old_read_gets_409_and_gives_no_xp(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")

    with Session(test_engine) as old_session:
        old_task = old_session.get(Task, task_id)
        complete_task(client, task_id)
        assert old_session.get(Task, task_id).completed is False

        with pytest.raises(HTTPException) as refusal:
            tasks_router.complete_task(task_id, old_session)

    assert refusal.value.status_code == 409
    assert old_task.completed is True
    assert task_amounts(test_engine, task_id) == [25]


# O mesmo no desmarcar: sem a proteção, a segunda linha deixaria a soma da tarefa em −25.
def test_uncomplete_with_an_old_read_gets_409_and_takes_no_xp(client, test_engine):
    task_id = insert_task(test_engine, difficulty="medium")
    complete_task(client, task_id)

    with Session(test_engine) as old_session:
        old_task = old_session.get(Task, task_id)
        uncomplete_task(client, task_id)
        assert old_session.get(Task, task_id).completed is True

        with pytest.raises(HTTPException) as refusal:
            tasks_router.uncomplete_task(task_id, old_session)

    assert refusal.value.status_code == 409
    assert old_task.completed is False
    assert task_amounts(test_engine, task_id) == [-25, 25]


# A gravação da linha falha depois que a tarefa já mudou. Se a mudança tivesse sido gravada num
# commit separado, a tarefa ficaria com o estado novo e sem a linha de XP.
def test_failed_completion_changes_nothing(client, test_engine, monkeypatch):
    task_id = insert_task(test_engine)
    before = database_snapshot(test_engine)

    def fail_add(session, instance):
        raise RuntimeError("Falha simulada")

    monkeypatch.setattr(Session, "add", fail_add)

    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/complete")

    assert database_snapshot(test_engine) == before


def test_failed_uncompletion_changes_nothing(client, test_engine, monkeypatch):
    task_id = insert_task(test_engine)
    complete_task(client, task_id)
    before = database_snapshot(test_engine)

    def fail_add(session, instance):
        raise RuntimeError("Falha simulada")

    monkeypatch.setattr(Session, "add", fail_add)

    with pytest.raises(RuntimeError):
        client.post(f"/tasks/{task_id}/uncomplete")

    assert database_snapshot(test_engine) == before
