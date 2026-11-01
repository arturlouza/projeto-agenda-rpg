from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.main import app
from app.models import DEFAULT_TASK_COLOR, Task, XpEntry


# Banco em arquivo na pasta temporária do pytest, para nunca tocar no agenda.db real.
@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    yield engine
    engine.dispose()


# Sessão aberta num banco de teste que já tem as tabelas criadas.
@pytest.fixture
def session(test_engine):
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


def test_app_startup_creates_tables(test_engine, monkeypatch):
    monkeypatch.setattr("app.database.engine", test_engine)

    # O with faz o TestClient rodar o lifespan, como acontece ao ligar o app de verdade.
    with TestClient(app):
        pass

    assert set(inspect(test_engine).get_table_names()) == {"task", "tasktype", "xpentry"}


def test_task_gets_default_values(session):
    task = Task(title="Ler 30 páginas", due_date=date(2026, 1, 1), difficulty="medium")

    session.add(task)
    session.commit()
    session.refresh(task)

    assert task.id is not None
    assert task.notes is None
    assert task.color == DEFAULT_TASK_COLOR == "#F5E6C8"
    assert task.task_type_id is None
    assert task.completed is False
    assert task.completed_at is None
    assert task.postponements == 0
    assert task.created_at is not None


def test_xp_entry_keeps_negative_amount_and_task(session):
    task = Task(title="Ler 30 páginas", due_date=date(2026, 1, 1), difficulty="medium")
    session.add(task)
    session.commit()
    session.refresh(task)

    entry = XpEntry(amount=-18, reason="Tarefa desmarcada", task_id=task.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)

    assert entry.amount == -18
    assert entry.reason == "Tarefa desmarcada"
    assert entry.task_id == task.id
    assert entry.created_at is not None


def test_task_with_unknown_task_type_is_refused(session):
    task = Task(
        title="Ler 30 páginas",
        due_date=date(2026, 1, 1),
        difficulty="medium",
        task_type_id=999,
    )
    session.add(task)

    with pytest.raises(IntegrityError):
        session.commit()
