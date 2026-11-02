# Tarefa 1: esqueleto do back-end com a rota `/health`

## Contexto

A especificação (seção 10) define a tarefa assim: "FastAPI com a rota `/health`". Ela fica pronta quando abrir `http://localhost:8000/health` responde "ok".

Hoje `backend/` só tem o `requirements.txt`. FastAPI, Uvicorn e pytest já estão instalados no `.venv`.

Ajustes pedidos por você na revisão: a rota responde `{"status": "ok"}` e ganha um teste no pytest, com o `httpx2` como dependência nova autorizada.

## O que vou criar ou mudar

### 1. `backend/app/main.py` (novo)

```python
from fastapi import FastAPI

app = FastAPI()


# Rota simples para conferir se o servidor está no ar.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

### 2. `backend/requirements.txt` (acrescentar uma linha)

```
httpx2==2.16.0
```

O `TestClient` precisa dessa biblioteca para fazer os pedidos do teste. Ela instala junto `httpcore2` e `truststore`.

### 3. `backend/tests/test_health.py` (novo)

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### 4. `backend/pytest.ini` (novo, não estava na sua lista de ajustes)

```ini
[pytest]
pythonpath = .
```

Sem ele, o comando `pytest` falha com `ModuleNotFoundError: No module named 'app'`, porque o pytest não procura módulos na pasta `backend/` por padrão. Essa configuração faz o comando `pytest` do `CLAUDE.md` funcionar como está escrito.

### 5. `docs/especificacao.md` (mudar o critério de pronto da tarefa 1, na seção 10)

De:

```
Abrir `http://localhost:8000/health` responde "ok"
```

Para:

```
Abrir `http://localhost:8000/health` responde `{"status": "ok"}`
```

## Decisões

1. **A rota fica no `main.py`, sem `routers/`.** Com uma rota só, um router seria uma camada sem uso. A pasta `routers/` entra na tarefa 4.
2. **Sem `__init__.py`.** A estrutura de pastas do `CLAUDE.md` não lista esse arquivo, e tanto o `uvicorn` quanto o `pytest` funcionam sem ele.

## O que não vou mexer

`database.py`, `models.py`, `rules/`, `routers/` e `frontend/` ficam para as próximas tarefas. Também não farei commit.

## Como verificar

Depois de criar os arquivos, instalo as dependências no `.venv`, rodo o pytest e subo o servidor uma vez para conferir a resposta, desligando-o em seguida.

Depois, você confere no PowerShell, a partir da raiz do projeto:

```powershell
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
pytest
uvicorn app.main:app --reload
```

O `pytest` deve mostrar `1 passed`, sem aviso de obsolescência.

Com o servidor rodando, abra no navegador:

- `http://localhost:8000/health`: deve mostrar `{"status":"ok"}`.
- `http://localhost:8000/docs`: deve listar a rota `GET /health`.

Para desligar o servidor, use `Ctrl+C` no terminal.

## O que vou explicar ao terminar

Em português e em poucas linhas: o objeto `app`, o decorator (`@app.get`), por que a rota devolve um dicionário e como ele vira JSON, como o teste funciona linha por linha (`TestClient`, `assert`, como o pytest encontra o teste) e o que o `pytest.ini` faz.
