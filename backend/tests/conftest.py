import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app


# Banco em arquivo na pasta temporária do pytest, ainda sem tabelas, para nunca tocar no
# agenda.db real.
@pytest.fixture
def empty_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    yield engine
    engine.dispose()


# O mesmo banco de teste, já com as tabelas criadas.
@pytest.fixture
def test_engine(empty_engine):
    SQLModel.metadata.create_all(empty_engine)
    return empty_engine


# Cliente da API que usa o banco de teste no lugar do banco real.
@pytest.fixture
def client(test_engine):
    def get_test_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()
