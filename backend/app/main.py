from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_db_and_tables
from app.routers import task_types


# O que vem antes do yield roda ao ligar o app; o que viesse depois rodaria ao desligar.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(task_types.router)


# Rota simples para conferir se o servidor está no ar.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
