import time
from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session, select

from app.models import Task, XpEntry

# Maior valor da coluna INTEGER do PostgreSQL: o maior XP que uma linha do histórico guarda.
MAX_INTEGER = 2_147_483_647


# Vale para todos os testes deste arquivo: o "hoje" é sempre 01/11/2026 em Brasília, para a
# meia-noite não mudar o XP das tarefas concluídas nos testes.
@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    moment = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.dates.utc_now", lambda: moment)


# Pede o jogador pela API, confere que deu certo e devolve o JSON da resposta.
def get_player(client):
    response = client.get("/player")
    assert response.status_code == 200
    return response.json()


# Monta a resposta esperada, para cada teste conferir o JSON inteiro.
def player(total_xp, level, xp_into_level, xp_for_next_level, progress_percent):
    return {
        "total_xp": total_xp,
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_for_next_level": xp_for_next_level,
        "progress_percent": progress_percent,
    }


# Grava linhas de XP direto no banco, sem tarefa, para o teste começar com o XP que quiser.
def insert_xp(test_engine, *amounts):
    with Session(test_engine) as session:
        for amount in amounts:
            session.add(XpEntry(amount=amount, reason="XP de teste"))
        session.commit()


# Lê todas as linhas do histórico de XP direto no banco.
def xp_entries_in_database(test_engine):
    with Session(test_engine) as session:
        return [entry.model_dump() for entry in session.exec(select(XpEntry)).all()]


# Cria pela API uma tarefa média para hoje, que vale 25 XP, e devolve o id dela.
def create_medium_task(client):
    response = client.post(
        "/tasks", json={"title": "Ler 30 páginas", "due_date": "2026-11-01", "difficulty": "medium"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def change_completed(client, task_id, action):
    response = client.post(f"/tasks/{task_id}/{action}")
    assert response.status_code == 200


# Critério da tarefa 8: o /player devolve o nível e a porcentagem corretos.
def test_player_returns_level_and_percent(client, test_engine):
    insert_xp(test_engine, 100, 20)

    assert get_player(client) == player(120, 2, 20, 102, 19)


def test_empty_history_is_level_1_with_empty_bar(client):
    assert get_player(client) == player(0, 1, 0, 100, 0)


# Fronteiras da tabela 4.5: 86.928 é o total exato para chegar ao nível 100.
@pytest.mark.parametrize(
    "total_xp, expected",
    [
        (0, player(0, 1, 0, 100, 0)),
        (99, player(99, 1, 99, 100, 99)),
        (100, player(100, 2, 0, 102, 0)),
        (86928, player(86928, 100, 0, 2070, 0)),
        (86929, player(86929, 100, 1, 2070, 0)),
    ],
)
def test_player_at_the_borders_of_the_level_table(client, test_engine, total_xp, expected):
    insert_xp(test_engine, total_xp)

    assert get_player(client) == expected


def test_complete_changes_player_and_uncomplete_brings_it_back(client):
    task_id = create_medium_task(client)
    before = get_player(client)

    change_completed(client, task_id, "complete")
    assert get_player(client) == player(25, 1, 25, 100, 25)

    change_completed(client, task_id, "uncomplete")
    assert get_player(client) == before


def test_complete_levels_up_and_uncomplete_levels_down(client, test_engine):
    insert_xp(test_engine, 95)
    task_id = create_medium_task(client)

    change_completed(client, task_id, "complete")
    assert get_player(client) == player(120, 2, 20, 102, 19)

    change_completed(client, task_id, "uncomplete")
    assert get_player(client) == player(95, 1, 95, 100, 95)


# Com 4 adiamentos efetivos a tarefa vale 0: concluir grava uma linha de 0 e nada muda.
def test_completing_a_task_worth_zero_does_not_change_player(client, test_engine):
    insert_xp(test_engine, 50)
    with Session(test_engine) as session:
        task = Task(title="Tarefa", due_date=date(2026, 11, 1), difficulty="hard", postponements=4)
        session.add(task)
        session.commit()
        task_id = task.id
    before = get_player(client)

    change_completed(client, task_id, "complete")

    assert get_player(client) == before


# Excluir uma tarefa concluída mantém no histórico o XP que ela deu (seção 4.3).
def test_deleting_a_completed_task_keeps_its_xp(client):
    task_id = create_medium_task(client)
    change_completed(client, task_id, "complete")
    before = get_player(client)

    assert client.delete(f"/tasks/{task_id}").status_code == 204

    assert get_player(client) == before


# Pelas regras a soma não fica negativa. Se ficar, o total mostra a soma real, para ajudar a
# achar o erro, e o nível e a barra tratam o negativo como 0.
def test_negative_total_does_not_break_the_route(client, test_engine):
    insert_xp(test_engine, 25, -75)

    assert get_player(client) == player(-50, 1, 0, 100, 0)


# Cinco linhas com o maior INTEGER do PostgreSQL. Pagando um nível de cada vez, a resposta
# levaria uns 4 segundos.
def test_huge_total_answers_fast_with_the_right_level(client, test_engine):
    insert_xp(test_engine, *[MAX_INTEGER] * 5)

    start = time.perf_counter()
    result = get_player(client)
    elapsed = time.perf_counter() - start

    assert result == player(5 * MAX_INTEGER, 5_187_216, 1187, 2070, 57)
    assert elapsed < 0.5


# GET não pode alterar dados (seção 6.7): duas chamadas dão o mesmo resultado e o histórico
# continua igual.
def test_player_only_reads(client, test_engine):
    insert_xp(test_engine, 120)
    before = xp_entries_in_database(test_engine)

    assert get_player(client) == get_player(client)
    assert xp_entries_in_database(test_engine) == before


def test_post_on_player_is_not_allowed(client, test_engine):
    response = client.post("/player")

    assert response.status_code == 405
    assert xp_entries_in_database(test_engine) == []
