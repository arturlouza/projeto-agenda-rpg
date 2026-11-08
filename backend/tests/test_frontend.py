import re
from html.parser import HTMLParser
from pathlib import Path
from typing import get_args

import pytest

from app.models import DEFAULT_TASK_COLOR
from app.routers.task_types import MAX_TASK_TYPE_NAME_LENGTH
from app.routers.tasks import Difficulty, TaskInput, TaskUpdate

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


# Lê o formulário de tarefa (<form id="task-form">): os atributos do <form>, os campos (input,
# select e textarea) com os atributos deles, os botões, o "for" de cada <label> e os valores das
# opções da dificuldade.
class TaskFormFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.inside_form = False
        self.fields = []
        self.buttons = []
        self.label_targets = []
        self.difficulty_options = []
        self.current_select = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form" and attributes.get("id") == "task-form":
            self.form = attributes
            self.inside_form = True
        if not self.inside_form:
            return
        if tag in ("input", "select", "textarea"):
            self.fields.append(attributes)
        if tag == "button":
            self.buttons.append(attributes)
        if tag == "select":
            self.current_select = attributes.get("name")
        if tag == "label":
            self.label_targets.append(attributes.get("for"))
        if tag == "option" and self.current_select == "difficulty":
            self.difficulty_options.append(attributes.get("value"))

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside_form = False
        if tag == "select":
            self.current_select = None


def task_form():
    finder = TaskFormFinder()
    finder.feed((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))
    finder.close()
    assert finder.form is not None, "o index.html não tem o <form id=\"task-form\">"
    return finder


# Lê todos os <form> do index.html, inclusive o que está dentro do <template> da linha de tipo: os
# atributos de cada um, os campos e os botões dele. Anota em "misplaced" o que está no lugar
# errado: um <form> dentro de outro, ou a tela de tipos (o <dialog> e o modelo da linha) dentro do
# <dialog> do formulário de tarefa, onde o Enter no campo de renomear salvaria a tarefa. Os
# <dialog> do index.html não ficam um dentro do outro, então o fim de qualquer <dialog> encerra o
# do formulário.
class FormsFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.ids = []
        self.misplaced = []
        self.current_form = None
        self.inside_task_dialog = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id is not None:
            self.ids.append(element_id)
        if tag == "dialog" and element_id == "task-form-dialog":
            self.inside_task_dialog = True
        if self.inside_task_dialog and element_id in ("task-types-dialog", "task-type-row-template"):
            self.misplaced.append(f"#{element_id} dentro do formulário de tarefa")
        if tag == "form":
            if self.current_form is not None:
                self.misplaced.append("<form> dentro de outro <form>")
            self.current_form = {"attributes": attributes, "fields": [], "buttons": []}
            self.forms.append(self.current_form)
        elif self.current_form is not None:
            if tag in ("input", "select", "textarea"):
                self.current_form["fields"].append(attributes)
            if tag == "button":
                self.current_form["buttons"].append(attributes)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current_form = None
        if tag == "dialog":
            self.inside_task_dialog = False


def html_forms():
    finder = FormsFinder()
    finder.feed((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))
    finder.close()
    return finder


# O <form> de renomear tipo, que fica no modelo da linha da tela de tipos.
def rename_form():
    forms = [
        form
        for form in html_forms().forms
        if "type-rename-form" in form["attributes"].get("class", "").split()
    ]
    assert len(forms) == 1, forms
    return forms[0]


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


# O campo de cor abre mostrando a cor escrita no HTML, e o "Cor padrão" volta a ela. Sem cor
# escolhida, o pedido não leva cor e o servidor aplica DEFAULT_TASK_COLOR. Os dois precisam ser
# a mesma cor, senão o formulário mostraria uma e a tarefa ficaria com outra.
def test_task_form_default_color_matches_the_server():
    colors = [field for field in task_form().fields if field.get("type") == "color"]

    assert len(colors) == 1
    assert colors[0]["value"] == DEFAULT_TASK_COLOR


# As opções da dificuldade são exatamente as que o servidor aceita, na mesma ordem. Um erro de
# digitação, como "meduim", daria 422 só na hora de salvar.
def test_task_form_difficulties_match_the_server():
    assert task_form().difficulty_options == list(get_args(Difficulty))


# O formulário acha o campo de um erro 422 pelo name, que é o nome do campo na API, e escreve a
# frase com o texto do <label> dele. Por isso cada campo de TaskInput está no formulário com o
# mesmo name, e cada campo tem um <label> que aponta para ele. Só os campos com name são da
# tarefa: o nome do tipo novo não tem (test_new_type_field_is_not_a_task_field).
def test_task_form_fields_match_the_api():
    form = task_form()
    names = [field["name"] for field in form.fields if "name" in field]

    assert sorted(names) == sorted(TaskInput.model_fields)
    for field in form.fields:
        assert field["id"] in form.label_targets, field


# A edição manda os mesmos campos do formulário e mais shown_due_date, a data que o formulário
# mostrou ao abrir, que sai da lista, e não de um campo. Se a API passar a exigir outro campo na
# edição, toda edição pela tela daria 422, e este teste falha antes.
def test_task_form_fields_match_the_edit_api():
    form_names = {field["name"] for field in task_form().fields if "name" in field}

    assert set(TaskUpdate.model_fields) == form_names | {"shown_due_date"}
    assert "shown_due_date" not in form_names


# O nome do tipo novo fica dentro do <form> da tarefa, mas não é campo dela: não tem name, então
# não entra na comparação com a API, e o erro 422 da tarefa nunca o acha. Ele é o único campo sem
# name: um campo da tarefa esquecido sem name continua sendo pego aqui.
def test_new_type_field_is_not_a_task_field():
    form = task_form()
    without_name = [field for field in form.fields if "name" not in field]

    assert [field["id"] for field in without_name] == ["task-form-new-type-name"]
    assert without_name[0].get("type") == "text"
    assert "task-form-new-type-name" in form.label_targets


# Dentro de um <form>, um <button> sem type envia o formulário. Um Excluir ou um Criar tipo sem
# type salvaria a tarefa em vez de excluir ou de criar o tipo. Por isso todo botão do formulário
# tem o type escrito, e o único que envia é o Salvar.
def test_only_save_submits_the_task_form():
    buttons = task_form().buttons
    ids = [button["id"] for button in buttons]

    for button in buttons:
        assert button.get("type") in ("button", "submit"), button
    assert [button["id"] for button in buttons if button["type"] == "submit"] == ["task-form-save"]
    assert "task-form-delete" in ids
    assert "task-form-new-type-create" in ids


# As regras ficam só no servidor (tasks.py): o HTML não leva nenhum limite que o navegador
# conferiria, e o novalidate desliga a conferência dele. Sem method e sem action, o <form> só
# serve para o Enter salvar; a gravação é por fetch (seção 6.7).
def test_task_form_leaves_the_rules_to_the_server():
    form = task_form()

    assert "novalidate" in form.form
    assert "method" not in form.form
    assert "action" not in form.form
    for field in form.fields:
        for attribute in ["required", "minlength", "maxlength", "pattern", "min", "max"]:
            assert attribute not in field, (field, attribute)


# O formulário traduz o erro 422 do tipo novo lendo o loc, o type e, no nome longo, o
# ctx.max_length (showNewTypeError, no task-form.js). Se esse formato mudar, a tela cairia na
# mensagem genérica; este teste falha antes. O número vem do servidor, nunca do JavaScript.
@pytest.mark.parametrize(
    ("name", "error_type"),
    [
        ("", "string_too_short"),
        ("   ", "string_too_short"),
        ("a" * (MAX_TASK_TYPE_NAME_LENGTH + 1), "string_too_long"),
    ],
)
def test_type_name_errors_have_the_shape_the_form_reads(client, name, error_type):
    response = client.post("/task-types", json={"name": name})

    assert response.status_code == 422
    [item] = response.json()["detail"]
    assert item["loc"] == ["body", "name"]
    assert item["type"] == error_type
    if error_type == "string_too_long":
        assert item["ctx"]["max_length"] == MAX_TASK_TYPE_NAME_LENGTH


# O limite do nome do tipo fica só em task_types.py. Ele não pode aparecer, como número inteiro, em
# nenhum .js nem no index.html: a mensagem de erro usa o ctx.max_length da resposta. Com \b, o
# número é procurado como palavra inteira (5000 não conta como 50).
def test_type_name_limit_is_only_on_the_server():
    limit = re.compile(rf"\b{MAX_TASK_TYPE_NAME_LENGTH}\b")
    paths = sorted(FRONTEND_DIR.rglob("*.js")) + [FRONTEND_DIR / "index.html"]

    for path in paths:
        assert not limit.search(path.read_text(encoding="utf-8")), path


# A tela de tipos traduz o erro 422 de renomear do mesmo jeito que o formulário traduz o de criar
# (showRenameError, no task-types.js): pelo loc, pelo type e, no nome longo, pelo ctx.max_length.
# Se o formato do PATCH mudar, a tela cairia na mensagem genérica; este teste falha antes.
@pytest.mark.parametrize(
    ("name", "error_type"),
    [
        ("", "string_too_short"),
        ("   ", "string_too_short"),
        ("a" * (MAX_TASK_TYPE_NAME_LENGTH + 1), "string_too_long"),
    ],
)
def test_type_rename_errors_have_the_shape_the_screen_reads(client, name, error_type):
    task_type_id = client.post("/task-types", json={"name": "Leitura"}).json()["id"]

    response = client.patch(f"/task-types/{task_type_id}", json={"name": name})

    assert response.status_code == 422
    [item] = response.json()["detail"]
    assert item["loc"] == ["body", "name"]
    assert item["type"] == error_type
    if error_type == "string_too_long":
        assert item["ctx"]["max_length"] == MAX_TASK_TYPE_NAME_LENGTH


# Vale para todo <form> da página, o da tarefa e o de renomear tipo: as regras ficam só no
# servidor (novalidate e nenhum limite nos campos), e sem method e sem action o <form> só serve
# para o Enter enviar; a gravação é por fetch (seção 6.7).
def test_every_form_leaves_the_rules_to_the_server():
    forms = html_forms().forms
    names = [form["attributes"].get("id") or form["attributes"].get("class") for form in forms]

    assert names == ["task-form", "type-rename-form"]
    for form in forms:
        assert "novalidate" in form["attributes"], form["attributes"]
        assert "method" not in form["attributes"], form["attributes"]
        assert "action" not in form["attributes"], form["attributes"]
        for field in form["fields"]:
            for attribute in ["required", "minlength", "maxlength", "pattern", "min", "max"]:
                assert attribute not in field, (field, attribute)


# Dentro do <form> de renomear, um <button> sem type envia o formulário: o "Desistir" renomearia
# o tipo. Por isso todo botão dele tem o type escrito, e o único que envia é o "Salvar nome". O
# "Excluir" fica fora desse <form>, na área própria, para nunca enviá-lo.
def test_only_save_name_submits_the_rename_form():
    buttons = rename_form()["buttons"]
    classes = [button.get("class", "").split() for button in buttons]

    for button in buttons:
        assert button.get("type") in ("button", "submit"), button
    submit_classes = [button["class"].split() for button in buttons if button["type"] == "submit"]
    assert len(submit_classes) == 1
    assert "type-rename-save" in submit_classes[0]
    assert not any("type-delete" in button_classes for button_classes in classes)


# A armadilha da etapa 11.6: um campo dentro do <form> da tarefa faz o Enter salvar a tarefa. A tela
# de tipos fica fora do <dialog> do formulário, e nenhum <form> fica dentro de outro.
def test_types_screen_is_not_inside_the_task_form():
    finder = html_forms()

    assert "task-types-dialog" in finder.ids
    assert "task-type-row-template" in finder.ids
    assert finder.misplaced == []
