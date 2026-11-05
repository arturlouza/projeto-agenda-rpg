import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

# As pastas são achadas a partir deste arquivo: tests/ está em backend/, que está na raiz.
BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Escrita por extenso, copiada da seção 10, para pegar uma mudança acidental em main.py.
EXPECTED_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; "
    "form-action 'none'"
)

# Seção 6.7: dados entram na tela só por textContent ou value. O eval é procurado como
# palavra inteira, para uma palavra como "retrieval" não reprovar o arquivo.
FORBIDDEN_IN_JAVASCRIPT = [
    r"innerHTML",
    r"outerHTML",
    r"insertAdjacentHTML",
    r"document\.write",
    r"\beval\b",
]


# Lê o HTML e anota o que a CSP bloquearia sem aviso: script dentro da página, atributos
# on... (onclick, onerror) e estilo dentro da página. O HTMLParser entrega os nomes dos
# atributos em minúsculas e pula os comentários.
class InlineCodeFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.problems = []
        self.inside_script = False

    def handle_starttag(self, tag, attrs):
        names = [name for name, value in attrs]
        for name in names:
            if name.startswith("on") or name == "style":
                self.problems.append(f"<{tag}> com o atributo {name}")
        if tag == "style":
            self.problems.append("<style> dentro da página")
        if tag == "script":
            self.inside_script = True
            if "src" not in names:
                self.problems.append("<script> sem src")

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside_script = False

    def handle_data(self, data):
        if self.inside_script and data.strip():
            self.problems.append("código dentro de <script>")


def test_main_page_opens_with_the_csp(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# O tipo vem do Python, que no Windows pode lê-lo do registro do sistema. Com o tipo errado,
# o navegador recusa o estilo ou o script, e a página quebra sem aviso.
@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/css/style.css", "text/css"), ("/js/app.js", "text/javascript")],
)
def test_frontend_files_open_with_the_csp(client, path, content_type):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# Seção 6.5: o navegador pode guardar os arquivos do front, mas confere com o servidor antes
# de usar. Assim, um F5 comum já pega a versão nova depois de uma mudança.
@pytest.mark.parametrize("path", ["/", "/index.html", "/css/style.css", "/js/app.js"])
def test_frontend_files_are_checked_before_use(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# O caminho do F5 com o arquivo igual: o navegador manda a ETag da cópia que tem, e o servidor
# responde 304, sem corpo, dizendo que a cópia ainda vale.
def test_unchanged_frontend_file_answers_304(client):
    first = client.get("/js/app.js")

    second = client.get("/js/app.js", headers={"If-None-Match": first.headers["etag"]})

    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["cache-control"] == "no-cache"


# O no-cache é só dos arquivos do front: a API responde como antes. Na etapa 15.2, a API ganha
# o próprio Cache-Control: no-store (seção 6.7), e este teste muda junto.
@pytest.mark.parametrize("path", ["/health", "/player", "/tasks/today", "/openapi.json"])
def test_api_does_not_get_the_frontend_cache_header(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert "cache-control" not in response.headers


@pytest.mark.parametrize("path", ["/agenda.db", "/.env"])
def test_database_and_secrets_are_not_served(client, path):
    response = client.get(path)

    assert response.status_code == 404


# Só olha o código de status, nunca o conteúdo: se algum arquivo vazasse, o teste falharia
# sem mostrar o que tem dentro dele.
def test_no_backend_file_is_reachable(client):
    backend_files = [path for path in BACKEND_DIR.rglob("*") if path.is_file()]
    assert backend_files

    for path in backend_files:
        relative_path = path.relative_to(BACKEND_DIR).as_posix()
        for url in [f"/{relative_path}", f"/backend/{relative_path}"]:
            assert client.get(url).status_code == 404, url


# Tentativas de sair da pasta frontend/ com ".." escondido de vários jeitos.
@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/backend/agenda.db",
        "/..%2fbackend%2fagenda.db",
        "/css/..%2f..%2fbackend/requirements.txt",
        "/..\\backend\\agenda.db",
        "/%5c..%5cbackend%5cagenda.db",
    ],
)
def test_paths_cannot_leave_the_frontend_folder(client, path):
    response = client.get(path)

    assert response.status_code == 404


# O uvicorn é ligado de dentro de backend/, mas a pasta do front não pode depender disso.
def test_frontend_does_not_depend_on_the_current_folder(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    response = client.get("/")

    assert response.status_code == 200


# As páginas da documentação carregam scripts de fora e inline, então ficam sem CSP.
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/docs/oauth2-redirect"])
def test_documentation_pages_open_without_the_csp(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers


def test_docs_still_loads_swagger(client):
    assert "swagger-ui" in client.get("/docs").text
    assert client.get("/openapi.json").status_code == 200


def test_api_answers_as_before(client):
    health = client.get("/health")
    player = client.get("/player")

    assert health.json() == {"status": "ok"}
    assert player.json() == {
        "total_xp": 0,
        "level": 1,
        "xp_into_level": 0,
        "xp_for_next_level": 100,
        "progress_percent": 0,
    }


# Com o front montado em "/", estes pedidos virariam 404. A API tem que vir antes do front.
@pytest.mark.parametrize("path", ["/tasks", "/tasks/1/complete", "/tasks/1/postpone"])
def test_wrong_method_on_api_route_is_still_405(client, path):
    response = client.get(path)

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}


def test_javascript_never_writes_html_or_evaluates_text():
    javascript_files = sorted(FRONTEND_DIR.rglob("*.js"))
    assert javascript_files

    for javascript_file in javascript_files:
        text = javascript_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IN_JAVASCRIPT:
            assert re.search(pattern, text) is None, f"{javascript_file.name} usa {pattern}"


# Seção 6.7: a CSP bloqueia código dentro da página em silêncio (o botão só não funciona), e o
# pytest não perceberia. Este teste pega antes.
def test_html_has_no_inline_code():
    html_files = sorted(FRONTEND_DIR.rglob("*.html"))
    assert html_files

    for html_file in html_files:
        finder = InlineCodeFinder()
        finder.feed(html_file.read_text(encoding="utf-8"))
        finder.close()
        assert finder.problems == [], f"{html_file.name}: {finder.problems}"
