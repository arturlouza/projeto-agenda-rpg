import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

# Este import parece não ser usado, mas é ele que apresenta as tabelas ao SQLModel.
# Sem ele, create_all não conhece nenhuma tabela e cria um banco vazio.
from app import models  # noqa: F401

# Endereço do banco. O arquivo fica na pasta de onde o app é iniciado (backend).
DATABASE_URL = "sqlite:///./agenda.db"

# Só configura a conexão: o arquivo do banco ainda não é criado aqui.
engine = create_engine(DATABASE_URL)


# Roda a cada nova conexão e liga a checagem de chaves estrangeiras no SQLite, que vem
# desligada. Assim o desenvolvimento se comporta como o PostgreSQL (exceção registrada
# no CLAUDE.md). O código segue a documentação do SQLAlchemy.
@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        # O SQLite ignora este comando dentro de uma transação, por isso o autocommit
        # fica ligado só durante o comando.
        previous_autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

        dbapi_connection.autocommit = previous_autocommit


# Cria o arquivo do banco e as tabelas que ainda não existem.
def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
