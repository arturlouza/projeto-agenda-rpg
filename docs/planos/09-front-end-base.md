# Plano: tarefa 9, front-end base

## Contexto

A tarefa 9 é a primeira de front-end. O FastAPI passa a entregar a pasta `frontend/`, e a página mostra o topo fixo com nível, barra e XP, lidos do `GET /player` (tarefa 8). O critério da seção 10 é: "a página abre no navegador mostrando o nível real; `/agenda.db` e `/.env` dão 404; a CSP está ligada; um teste recusa `innerHTML` e parecidos". Hoje são 567 testes passando. Nenhuma tabela muda. Até aqui só li arquivos e rodei simulações em memória, usando a pasta `docs/` no lugar de `frontend/`, sem gravar nada.

## Regra 11: o "montar" da seção 10 muda respostas da API

A seção 10 diz que o `StaticFiles` **monta** a pasta `frontend/` depois das rotas. Simulei o `app.mount("/", StaticFiles(...))` e ele muda respostas da API:

| Pedido | Hoje | Com `app.mount("/")` | Com a alternativa |
| --- | --- | --- | --- |
| `GET /tasks/1/complete` | 405 | **404** | 405 |
| `GET /tasks/1/postpone` | 405 | **404** | 405 |
| `GET /tasks` | 405 | **404** | 405 |
| `POST /player` | 405 | 405 | 405 |
| `POST /nao-existe` | 404 | 405 | 405 |

**Por quê:** o roteador do Starlette percorre as rotas na ordem. Quando o caminho casa mas o método não, ele guarda essa rota como "quase" e continua procurando. Um `mount` em `/` casa com qualquer caminho, então ganha da rota "quase", e o 405 vira 404 do arquivo que não existe. Três testes de hoje quebrariam (`test_completion_does_not_accept_get`, nas duas ações, e `test_postpone_does_not_accept_get`).

**Alternativa que proponho:** em vez de `mount`, o `StaticFiles` vira a **resposta padrão do roteador**, aquela que só roda quando nenhuma rota da API casou, nem pela metade:

```python
app.router.default = StaticFiles(directory=FRONTEND_DIR, html=True)
```

É o "depois das rotas da API" ao pé da letra: a API inteira tem prioridade, inclusive os 405. A única diferença que sobra é `POST`, `PUT` ou `DELETE` num endereço que não existe: dá 405 em vez de 404, porque o `StaticFiles` só aceita leitura. Nada grava, e a tarefa 15 põe a conferência de `Origin` antes disso.

**Risco da alternativa:** `default` é um parâmetro do `Router` do Starlette, não uma opção documentada do FastAPI. Se uma atualização mudar isso, os testes de 405 e o teste da página principal falham na hora. A outra saída seria manter o `mount` e trocar os três testes para aceitar 404, o que deixa a API pior (o 405 diz "esse endereço existe, mas não com esse método").

Se você aprovar, registro a exceção em "Exceções aprovadas" do `CLAUDE.md` e corrijo o texto da seção 10 ("monta" vira "resposta padrão do roteador").

## As 6 decisões

### 1. Como o FastAPI entrega `frontend/`

Em `backend/app/main.py`, no fim do arquivo, depois de todas as rotas:

```python
# Pasta do front-end, achada a partir deste arquivo, e não da pasta de onde o servidor foi ligado.
# main.py está em backend/app/, então dois níveis acima fica a raiz do projeto.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Entrega os arquivos de frontend/ só quando nenhuma rota da API casou com o pedido.
# Com app.mount("/"), um GET numa rota só de POST daria 404 em vez de 405 (exceção no CLAUDE.md).
app.router.default = StaticFiles(directory=FRONTEND_DIR, html=True)
```

- **`Path(__file__).resolve().parents[2]`:** `__file__` é o caminho do próprio `main.py`; `resolve()` o transforma em caminho completo; `parents[2]` sobe dois níveis (`app` e depois `backend`). Conferi: dá a raiz do projeto. Funciona igual com o `uvicorn` ligado de dentro de `backend/` ou de qualquer outra pasta.
- **`html=True`:** pedir `/` entrega o `index.html`.
- **Só `frontend/`:** o `StaticFiles` recusa com 404 qualquer caminho que saia da pasta. Conferi `/%2e%2e/CLAUDE.md`, `/..%2fbackend%2fagenda.db`, `/planos/..%2f..%2fbackend/requirements.txt` e barra invertida: todos 404.
- **Pasta faltando:** o `StaticFiles` confere a pasta ao ligar e recusa subir sem ela, em vez de falhar escondido.
- **Não esconde nada:** `/docs`, `/openapi.json`, `/health`, `/player`, `/tasks` e `/task-types` são rotas, então vêm antes. Conferido na simulação.
- **Vale para produção também,** como pede a seção 10. Nenhum nome de arquivo em `frontend/` coincide com uma rota, e se um dia coincidir, a rota ganha.

### 2. A CSP

O cabeçalho, igual ao da seção 10, numa constante em `main.py`:

```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'
```

**A que respostas se aplica: a todas, menos as três páginas da documentação** (`/docs`, `/redoc` e `/docs/oauth2-redirect`). Conferi que o `/docs` carrega scripts de `cdn.jsdelivr.net` e tem `<script>` inline: com a CSP, ele ficaria em branco.

```python
# Páginas da documentação automática: carregam scripts de fora e inline, então ficam sem CSP.
# Só existem no desenvolvimento a partir da tarefa 15.
DOCS_PATHS = {app.docs_url, app.redoc_url, app.swagger_ui_oauth2_redirect_url}


# Roda em toda resposta e liga a CSP, menos nas páginas da documentação (seção 6.7).
@app.middleware("http")
async def add_content_security_policy(request: Request, call_next):
    response = await call_next(request)
    if request.url.path not in DOCS_PATHS:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response
```

- **Por que "todas menos a documentação", e não "só os arquivos do front":** esquecer um caso vira "tem CSP", e não "ficou sem". Uma página nova em `frontend/` já nasce protegida. Nas respostas JSON da API, a CSP não muda nada, e é inofensiva.
- **Lista fechada e lida do próprio app:** os caminhos vêm de `app.docs_url` e companhia, não de texto repetido. Quando a tarefa 15 desligar a documentação fora do desenvolvimento, esses valores viram `None`, e a lista não deixa nada aberto. O `/openapi.json` fica com a CSP: ele é JSON, e a CSP de um arquivo buscado não afeta a página que o buscou.
- **Conceito novo, middleware:** uma função que fica "em volta" de todas as rotas. Ela recebe o pedido, passa adiante com `call_next`, recebe a resposta pronta e pode mexer nela antes de devolver. É o mesmo lugar onde a tarefa 15 vai pôr a conferência de `Origin`.
- **Conceito novo, CSP:** um cabeçalho em que o servidor diz ao navegador de onde a página pode carregar scripts, estilos e imagens. Com `'self'`, só do próprio endereço; com `default-src 'none'`, o que não foi liberado fica proibido. O script inline, o `onclick` no HTML e o `eval` ficam bloqueados, o que barra a maior parte dos ataques de injeção de script.

### 3. Os arquivos do front

A estrutura do `CLAUDE.md`, sem nada além dela:

```
frontend/
├── index.html
├── css/style.css
└── js/app.js
```

**A função única de chamada à API fica em `app.js`**, no topo, junto da constante `API_BASE`. Um arquivo próprio exigiria uma segunda tag `<script>` com variável global compartilhada, ou módulos do JavaScript, que são um conceito a mais. Com uns 40 linhas, um arquivo só se lê de cima para baixo. Se `app.js` crescer demais nas tarefas 10 a 12, a separação é decidida lá.

```js
// Endereço da API (seção 6.5). Front e API têm a mesma origem, então é um caminho relativo.
const API_BASE = "./";

// Toda chamada à API passa por aqui (seção 6.5). Na tarefa 15, esta função passa a tratar o 401.
async function apiRequest(path, options) {
  const response = await fetch(API_BASE + path, options);
  if (!response.ok) {
    throw new Error("A API respondeu " + response.status);
  }
  return response.json();
}
```

- **`"./"`:** relativo à página. Com a página em `/`, `apiRequest("player")` busca `/player`. Se o app for publicado num subcaminho, a API vem junto, e nada muda.
- **`fetch` no modo padrão,** como pede a seção 6.7, e só com o que a tarefa 9 usa. O tratamento da resposta 204 (excluir) entra quando a tela de excluir precisar.

### 4. O topo fixo

```html
<header class="top-bar">
  <div class="top-bar-row">
    <span id="player-level" class="player-level">Nível</span>
    <span id="player-xp" class="player-xp"></span>
  </div>
  <progress id="player-progress" class="xp-bar" max="100" value="0"
            aria-label="Progresso até o próximo nível"></progress>
  <p id="player-message" class="player-message" role="status">Carregando…</p>
</header>
```

**O que aparece:** "Nível 2" à esquerda, "20 / 102 XP" à direita e a barra embaixo, com 19%. O "quanto falta" da seção 6.2 fica visível pela barra e pelo "20 / 102". Mostrar "faltam 82 XP" exigiria uma subtração no JavaScript, que é conta de XP (regra 9). Números grandes saem com ponto de milhar ("2.039 / 2.040 XP"), com `Intl.NumberFormat("pt-BR")`, que só formata.

**A barra é um `<progress>`,** o elemento do próprio HTML para barra de progresso. O JavaScript só põe o `value`, que é um dos dois caminhos permitidos para dados entrarem na tela (seção 6.7). O leitor de tela já o reconhece como barra, sem atributo extra. Uma `<div>` com `style.width` também passaria pela CSP, mas seria um terceiro caminho de entrada de dados, sem ganho nenhum.

```js
const numberFormat = new Intl.NumberFormat("pt-BR");

// Mostra no topo o que o servidor mandou, sem nenhuma conta de XP (regra 9 do CLAUDE.md).
function showPlayer(player) {
  document.getElementById("player-level").textContent = "Nível " + numberFormat.format(player.level);
  document.getElementById("player-xp").textContent =
    numberFormat.format(player.xp_into_level) + " / " + numberFormat.format(player.xp_for_next_level) + " XP";
  document.getElementById("player-progress").value = player.progress_percent;
  document.getElementById("player-message").hidden = true;
}

async function loadPlayer() {
  try {
    showPlayer(await apiRequest("player"));
  } catch (error) {
    console.error(error);
    const message = document.getElementById("player-message");
    message.textContent = "Não foi possível carregar o nível. Recarregue a página.";
    message.classList.add("is-error");
  }
}

loadPlayer();
```

- **Carregando:** o HTML já nasce com "Nível", a barra vazia e "Carregando…". A barra começa em `value="0"`, porque um `<progress>` sem valor mostra uma animação de "carregando sem fim", e a seção 6.3 pede efeitos sutis.
- **Erro** (servidor desligado, rede caída ou resposta fora de 200): a mesma linha vira "Não foi possível carregar o nível. Recarregue a página.", na cor de erro. O erro completo vai para o console do F12. Sem botão de tentar de novo, para manter o JavaScript mínimo.
- **Conceitos novos:** `fetch` faz o pedido HTTP; `async`/`await` esperam a resposta sem travar a página; `try`/`catch` pega o erro, tanto o de rede quanto o que `apiRequest` lança; `defer` na tag `<script>` faz o arquivo rodar só depois de o HTML estar pronto, então o `getElementById` encontra os elementos.

### 5. Celular primeiro

- `<meta name="viewport" content="width=device-width, initial-scale=1">`, `lang="pt-BR"` e `charset="utf-8"`.
- **Topo com `position: sticky; top: 0`:** fica preso no alto ao rolar, sem precisar compensar a altura no resto da página, como o `fixed` exigiria.
- **Largura:** o layout é pensado para uns 360 px. No computador, o conteúdo fica centralizado com largura máxima de `40rem`, e o fundo do topo ocupa a tela toda.
- **Toque:** a tarefa 9 não tem nada para tocar. A variável `--touch-size: 48px` (o mínimo recomendado no Android) já fica pronta para os botões da tarefa 10.
- **Variáveis de CSS em `:root`:** cores (fundo, superfície, texto, texto secundário, destaque da barra, trilho da barra, erro), espaçamentos (`--space-1` a `--space-4`, de 4 a 24 px), raio das bordas, altura da barra e tamanhos de fonte. Cores neutras, com contraste de leitura confortável. A tarefa 13 troca o visual mexendo só nelas.
- **Sem nada de fora:** fonte do sistema (`system-ui, sans-serif`), sem ícones, sem imagens. O navegador vai pedir `/favicon.ico` e receber 404: é inofensivo, e o ícone é da tarefa 14.
- **Barra no CSS:** o `<progress>` precisa de três regras para cada navegador (`::-webkit-progress-bar`, `::-webkit-progress-value` e `::-moz-progress-bar`). Explico cada uma no próprio arquivo.
- **Conceito novo, variável de CSS:** `--color-accent: #2f6f4f;` em `:root` define o valor uma vez; `background: var(--color-accent);` o usa em qualquer lugar.

### 6. Como você confere, já que o JavaScript não tem teste automático

O JavaScript fica em umas 40 linhas, sem nenhuma conta. O roteiro do navegador está em "Como você vai testar", no fim.

## Testes

Arquivo novo `backend/tests/test_frontend.py`, usando a fixture `client` do `conftest.py`. A CSP esperada fica escrita por extenso no teste, copiada da seção 10, e não importada de `main.py`: assim o teste pega uma mudança acidental na constante.

| Teste | Confere |
| --- | --- |
| Página principal | `GET /` dá 200, `text/html`, e traz a CSP exata |
| CSS e JS | `/css/style.css` e `/js/app.js` dão 200 com a CSP |
| Segredos e banco | `/agenda.db` e `/.env` dão 404 |
| Nada de `backend/` | Percorre os arquivos de `backend/` e pede cada um como `/<caminho>` e `/backend/<caminho>`: todos 404. Só olha o código de status, nunca o conteúdo |
| Saída da pasta | `/%2e%2e/backend/agenda.db`, `/..%2fbackend%2fagenda.db`, `/css/..%2f..%2fbackend/requirements.txt` e com barra invertida: todos 404 |
| Pasta de onde ligou | Com `monkeypatch.chdir` para uma pasta temporária, `GET /` continua dando 200 |
| `/docs` continua abrindo | 200, sem a CSP, e com o Swagger na página; `/openapi.json` dá 200 |
| API como antes | `/health` e `/player` respondem o JSON de sempre; `GET /tasks/1/complete` continua 405. Os 567 testes atuais também precisam passar |
| JavaScript seguro | Lê todos os `.js` de `frontend/`, exige pelo menos um arquivo, e falha se achar `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` ou `eval` (esta como palavra inteira, para `retrieval` não confundir) |

Depois, tiro por um momento, um de cada vez, e vejo algum teste falhar: troco o `default` pelo `app.mount("/")`; tiro a exceção da documentação; troco o caminho por `"../frontend"`; ponho `innerHTML` num comentário de `app.js`. Desfaço cada um e confiro por hash que os arquivos voltaram iguais. Espero perto de **590 testes** e digo o número exato no resumo.

## Especificação, `CLAUDE.md` e regras 9, 12, 13 e 14

**`docs/especificacao.md`:**

- **Seção 10, "Segurança nas tarefas 9 a 14":** o item da tarefa 9 passa a dizer "resposta padrão do roteador" em vez de "monta".
- **Seção 10:** bloco "Decisões da tarefa 9": entrega pela resposta padrão do roteador e por quê; caminho a partir de `main.py`; CSP em tudo menos as três páginas da documentação; `apiRequest` e `API_BASE` em `app.js`; "20 / 102 XP" sem subtração; `<progress>` com `value`.
- **Seção 10:** bloco "Fora da tarefa 9": `POST` em endereço inexistente dá 405; o `favicon.ico` dá 404 até a tarefa 14.
- **Mapa do código (seção 12), regra 12:** `main.py` passa a entregar o front e ligar a CSP (`FRONTEND_DIR`, `CONTENT_SECURITY_POLICY`, `DOCS_PATHS`, `add_content_security_policy`); linhas novas para `frontend/index.html`, `frontend/css/style.css`, `frontend/js/app.js` e `backend/tests/test_frontend.py`.

**`CLAUDE.md`:** a exceção da regra 11 em "Exceções aprovadas", com o motivo. A árvore de pastas já prevê `frontend/` e não muda.

**Regra 9:** nenhuma conta de XP no JavaScript. Ele só junta textos e põe o número da barra.

**Regra 13:** ao terminar, renomeio este arquivo para `09-front-end-base.md`.

**Regra 14:** confiro os arquivos novos e alterados à procura de segredos e digo no resumo. O `.env` e as variações ficam fora. O teste que percorre `backend/` só olha o código de status das respostas, nunca abre arquivo nenhum.

**Commit:** não faço commit nem sugiro mensagem.

## Arquivos

| Arquivo | Mudança |
| --- | --- |
| `backend/app/main.py` | `FRONTEND_DIR`, `CONTENT_SECURITY_POLICY`, `DOCS_PATHS`, o middleware e o `StaticFiles` como resposta padrão |
| `frontend/index.html` | novo: topo fixo e `<main>` vazio para a tarefa 10 |
| `frontend/css/style.css` | novo: variáveis, layout de celular, topo e barra |
| `frontend/js/app.js` | novo: `API_BASE`, `apiRequest`, `showPlayer`, `loadPlayer` |
| `backend/tests/test_frontend.py` | novo: os testes acima |
| `docs/especificacao.md` | seções 10 e 12 |
| `CLAUDE.md` | exceção aprovada |
| `docs/planos/` | este plano, renomeado |

Nenhuma dependência nova: `StaticFiles` e o middleware já vêm com o FastAPI.

## Resultado

- **Testes:** 588 passando, 21 a mais que os 567 de antes. A estimativa era perto de 590.
- **Fora do plano, um item a mais no teste dos arquivos do front:** ele também confere o tipo (`text/css` e `text/javascript`). No Windows, o Python pode ler esse tipo do registro do sistema, e com o tipo errado o navegador recusa o arquivo sem nenhum aviso no pytest. Nesta máquina os dois vieram certos.
- **Trechos tirados um de cada vez:** com `app.mount("/")`, falham 6 testes (os 3 novos de 405 e os 3 antigos de `test_tasks.py`); sem a exceção da documentação, 3; com `"../frontend"`, 1; com `innerHTML` num comentário do `app.js`, 1; com `eval("1")`, 1. Um comentário com `retrieval` não reprova. Os arquivos voltaram iguais, conferidos por hash.

## Como você vai testar

Na pasta `backend`, com o ambiente virtual ativo:

```powershell
pytest
pytest tests/test_frontend.py -v
uvicorn app.main:app --reload
```

No Chrome, no computador:

1. **O nível real:** abra `http://localhost:8000/player` e anote o JSON. Abra `http://localhost:8000/`: o topo mostra o mesmo `level`, "`xp_into_level` / `xp_for_next_level` XP" e a barra em `progress_percent`.
2. **A CSP:** F12, aba **Network**, recarregue com Ctrl+Shift+R, clique em `localhost` (o primeiro pedido) e, em **Headers**, confira `Content-Security-Policy` nas **Response Headers**. Faça o mesmo em `app.js` e `style.css`.
3. **Console limpo:** na aba **Console**, nenhum erro vermelho, a não ser o 404 do `favicon.ico`. Um aviso de "Refused to..." indicaria algo bloqueado pela CSP. Para ver a CSP agindo, digite `eval("1 + 1")`: deve aparecer um erro dizendo que a avaliação foi recusada.
4. **Celular:** com o F12 aberto, Ctrl+Shift+M liga o modo celular. Escolha um aparelho de uns 360 px de largura: o topo cabe sem rolar para o lado, e o texto fica legível sem zoom.
5. **Carregando:** na aba **Network**, troque "No throttling" por "3G" e recarregue: "Carregando…" aparece antes do nível. Volte para "No throttling".
6. **Erro:** na aba **Network**, clique com o botão direito no pedido `player` e escolha **Block request URL**. Recarregue: aparece "Não foi possível carregar o nível. Recarregue a página." em cor de erro, e o motivo aparece no Console. Desbloqueie depois (botão direito, **Unblock**).
7. **Nível mudando:** em `http://localhost:8000/docs`, crie uma tarefa `medium` para hoje e conclua com `POST /tasks/{task_id}/complete`. Recarregue a página do app: o XP sobe 25. Desmarque com `POST /tasks/{task_id}/uncomplete` e recarregue: volta ao que era.
8. **O `/docs` inteiro:** ele abre com todos os blocos e botões, sem erro de CSP no Console.
9. **Arquivos proibidos:** `http://localhost:8000/agenda.db` e `http://localhost:8000/.env` mostram `{"detail":"Not Found"}`.

**Opcional, no celular:** pelo cabo USB, com o encaminhamento de porta em `chrome://inspect/#devices` (seção 6.7), abra `http://localhost:8000` no Chrome do celular.
