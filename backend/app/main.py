from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from app.database import create_db_and_tables
from app.routers import player, task_types, tasks

# Pasta do front-end, achada a partir deste arquivo, e não da pasta de onde o servidor foi ligado.
# main.py está em backend/app/, então dois níveis acima fica a raiz do projeto.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Diz ao navegador que scripts, estilos, imagens e pedidos só podem vir deste endereço (seção 6.7).
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; "
    "form-action 'none'"
)

# Os arquivos de frontend/ podem ficar guardados no navegador, mas ele confere com o servidor
# antes de usar (seção 6.5). Sem isso, o Chrome usou o CSS e o JavaScript velhos depois de uma
# mudança, e o app pareceu quebrado até um Ctrl+Shift+R.
FRONTEND_CACHE_CONTROL = "no-cache"


# O que vem antes do yield roda ao ligar o app; o que viesse depois rodaria ao desligar.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(task_types.router)
app.include_router(tasks.router)
app.include_router(player.router)

# Páginas da documentação automática: carregam scripts de fora e inline, então ficam sem CSP.
DOCS_PATHS = {app.docs_url, app.redoc_url, app.swagger_ui_oauth2_redirect_url}


# Roda em toda resposta e liga a CSP, menos nas páginas da documentação.
@app.middleware("http")
async def add_content_security_policy(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if request.url.path not in DOCS_PATHS:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


# Rota simples para conferir se o servidor está no ar.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# O StaticFiles com o Cache-Control. file_response é o método do StaticFiles que monta a
# resposta de um arquivo achado, inclusive o 304 ("a sua cópia ainda vale"). Os 404 e as
# respostas da API não passam por aqui.
class FrontendFiles(StaticFiles):
    def file_response(self, full_path, stat_result, scope, status_code=200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = FRONTEND_CACHE_CONTROL
        return response


# Entrega os arquivos de frontend/ só quando nenhuma rota da API casou com o pedido.
# Com app.mount("/"), um GET numa rota só de POST daria 404 em vez de 405 (exceção no CLAUDE.md).
app.router.default = FrontendFiles(directory=FRONTEND_DIR, html=True)
