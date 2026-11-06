import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

# As pastas são achadas a partir deste arquivo: tests/ está em backend/, que está na raiz.
BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
JAVASCRIPT_DIR = FRONTEND_DIR / "js"

# Todo .js de frontend/, como o navegador pede: "/js/api.js", "/js/day.js"... Montada a partir
# da pasta, para um arquivo novo entrar nos testes de entrega sem ninguém lembrar de pôr aqui.
JAVASCRIPT_PATHS = [
    "/" + path.relative_to(FRONTEND_DIR).as_posix() for path in sorted(FRONTEND_DIR.rglob("*.js"))
]

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


# Lê os <script> do HTML na ordem em que aparecem, cada um com os atributos dele. Um atributo
# sem valor, como o defer, aparece com o valor None.
class ScriptFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts.append(dict(attrs))


def index_scripts():
    finder = ScriptFinder()
    finder.feed((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))
    finder.close()
    return finder.scripts


def test_main_page_opens_with_the_csp(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# O tipo vem do Python, que no Windows pode lê-lo do registro do sistema. Com o tipo errado,
# o navegador recusa o estilo ou o script, e a página quebra sem aviso.
@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/css/style.css", "text/css")] + [(path, "text/javascript") for path in JAVASCRIPT_PATHS],
)
def test_frontend_files_open_with_the_csp(client, path, content_type):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# Seção 6.5: o navegador pode guardar os arquivos do front, mas confere com o servidor antes
# de usar. Assim, um F5 comum já pega a versão nova depois de uma mudança.
@pytest.mark.parametrize("path", ["/", "/index.html", "/css/style.css"] + JAVASCRIPT_PATHS)
def test_frontend_files_are_checked_before_use(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-security-policy"] == EXPECTED_CSP


# O caminho do F5 com o arquivo igual: o navegador manda a ETag da cópia que tem, e o servidor
# responde 304, sem corpo, dizendo que a cópia ainda vale.
@pytest.mark.parametrize("path", JAVASCRIPT_PATHS)
def test_unchanged_frontend_file_answers_304(client, path):
    first = client.get(path)

    second = client.get(path, headers={"If-None-Match": first.headers["etag"]})

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


# Sem o defer, o script rodaria antes de o HTML estar pronto, e os getElementById do alto dos
# arquivos voltariam null. Com um src errado, o navegador só dá 404, e a página quebra sem aviso.
def test_every_script_is_deferred_and_exists():
    scripts = index_scripts()
    assert scripts

    for script in scripts:
        assert "defer" in script, script
        assert script["src"].startswith("js/"), script
        assert (FRONTEND_DIR / script["src"]).is_file(), script


# Um arquivo fora do index.html nunca roda. Um arquivo que aparece duas vezes roda duas vezes:
# as let e const repetidas dão erro, e os ouvintes seriam registrados em dobro.
def test_every_javascript_file_is_loaded_once():
    sources = [script["src"] for script in index_scripts()]
    javascript_files = sorted("js/" + path.name for path in JAVASCRIPT_DIR.glob("*.js"))

    assert len(sources) == len(set(sources)), sources
    assert sorted(sources) == javascript_files


# Os arquivos rodam na ordem do index.html, e o código que roda ao carregar só enxerga o que
# veio dos arquivos de cima. O app.js faz os primeiros pedidos ao carregar (loadPlayer e
# loadDay, dos outros arquivos), então precisa ser o último.
def test_app_js_is_the_last_script():
    assert index_scripts()[-1]["src"] == "js/app.js"


# Sem módulos, todos os arquivos dividem os mesmos nomes. Uma const ou let repetida impede o
# segundo arquivo de rodar, e uma function repetida troca a primeira sem aviso. O teste lê só
# as declarações que começam na coluna 0: no front, toda declaração do alto do arquivo começa
# assim, e o que está dentro de uma função tem recuo.
def test_no_top_level_name_is_declared_twice():
    declaration = re.compile(r"^(?:async function|function|const|let|var|class) (\w+)", re.MULTILINE)
    files_by_name = {}
    for javascript_file in sorted(JAVASCRIPT_DIR.glob("*.js")):
        for name in declaration.findall(javascript_file.read_text(encoding="utf-8")):
            files_by_name.setdefault(name, []).append(javascript_file.name)

    assert files_by_name
    repeated = {name: files for name, files in files_by_name.items() if len(files) > 1}
    assert repeated == {}
