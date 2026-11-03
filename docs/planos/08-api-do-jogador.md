# Plano: tarefa 8, API do jogador

## Contexto

A tarefa 8 cria a rota que a tela vai ler para o topo fixo (seção 6.2): nível e barra de XP. O critério da seção 10 é "`/player` devolve nível e porcentagem corretos". O XP continua sem tabela própria: é a soma do `XpEntry` (seções 4.4 e 6.1). Hoje são 535 testes passando. Nenhuma tabela muda, então o `agenda.db` fica como está. Até aqui só li arquivos e rodei simulações num banco em memória, sem gravar nada em disco.

## Regra 11: um ponto que muda o que existe

**`level_from_total_xp` deixa de existir e vira `level_progress`.** A barra precisa da sobra que ela descarta. Se eu mantivesse as duas, ou o laço ficaria repetido, ou `level_from_total_xp` viraria uma linha que só os testes chamam, porque nenhuma rota precisa do nível sem a sobra (regra 5). Os 9 casos de teste dela continuam, agora conferindo também a sobra. Se preferir manter o nome antigo como atalho de uma linha, me diga na aprovação.

## As 7 decisões

### 1. A rota: `GET /player`

Só leitura, sem corpo e sem parâmetro. `GET` pode, porque não altera dados (seção 6.7). Resposta 200:

| Campo | O que é | Com 120 XP |
| --- | --- | --- |
| `total_xp` | Soma do histórico, sem retoque | 120 |
| `level` | Nível atual | 2 |
| `xp_into_level` | XP já acumulado dentro do nível atual | 20 |
| `xp_for_next_level` | XP que o nível atual custa para passar | 102 |
| `progress_percent` | Porcentagem da barra, inteira, de 0 a 99 | 19 |

"Quanto falta" (seção 6.2) é `xp_for_next_level − xp_into_level`. Não vira um sexto campo: a tela pode mostrar "20/102 XP", e decidir isso é da tarefa 9.

### 2. A conta fica em `rules/xp.py`, em duas funções puras

```python
# Descobre o nível e o XP acumulado dentro dele: começa no 1 e "paga" um nível de cada vez.
# Do nível 100 em diante todo nível custa o mesmo, então uma divisão resolve o resto de uma vez.
# XP total negativo conta como 0.
def level_progress(total_xp: int) -> tuple[int, int]:
    level = 1
    remaining_xp = max(total_xp, 0)

    while level < LEVEL_GROWTH_CAP and remaining_xp >= xp_to_next_level(level):
        remaining_xp -= xp_to_next_level(level)
        level += 1

    if level == LEVEL_GROWTH_CAP:
        levels_after_cap, remaining_xp = divmod(remaining_xp, xp_to_next_level(LEVEL_GROWTH_CAP))
        level += levels_after_cap

    return level, remaining_xp


# Porcentagem da barra, arredondada para baixo. Como o XP dentro do nível é sempre menor que o
# custo dele, o resultado vai no máximo a 99: a barra nunca mostra 100% antes de subir.
def progress_percent(xp_into_level: int, xp_for_next_level: int) -> int:
    return xp_into_level * 100 // xp_for_next_level
```

**Conceitos novos:**

- **Tupla de retorno:** a função devolve dois valores juntos, e quem chama separa os dois numa linha só: `level, xp_into_level = level_progress(total_xp)`.
- **`divmod(a, b)`:** devolve o resultado inteiro da divisão e o resto de uma vez. `divmod(4139, 2070)` dá `(1, 2069)`: 1 nível a mais e 2.069 XP de sobra.
- **`//`:** divisão que descarta a parte fracionária, só com números inteiros.

O comentário "Atenção" no topo de `xp.py`, que explica os arredondamentos diferentes, ganha uma linha sobre `progress_percent`. O `100` da porcentagem não vira constante: é a unidade "por cento", não um número do jogo que se ajusta.

### 3. A porcentagem: inteira, arredondada para baixo, com conta só de inteiros

- **Inteira:** a barra tem uns 400 px no celular, então 1% são uns 4 px. Casas decimais não mudariam o que se vê.
- **Para baixo:** com `xp < custo`, `xp × 100 // custo` vai no máximo a 99. Simulei todos os valores possíveis de todos os níveis: o máximo é 99. O arredondamento normal mostraria 100% em 10 valores do nível 100 (de 2.060 a 2.069 XP) e também com 86.927 XP, ainda no nível 99.
- **Só inteiros:** com `math.floor(xp / custo * 100)`, o número quebrado do computador erra em 9 casos. Exemplo: `29 / 100 * 100` dá `28.999999999999996`, e a barra mostraria 28% com 29 XP no nível 1. A conta com `//` não tem esse erro.
- **Limite que fica:** no nível 100, 1% são 20,7 XP, então uma tarefa fácil (10 XP) às vezes não move a porcentagem. O XP aparece no "+XP" ao concluir (seção 6.3) e no `xp_into_level`.

### 4. XP total zero ou negativo

Pelas regras atuais a soma nunca fica negativa: a tarefa pendente soma 0 e a concluída soma o que deu (seção 4.3). Só ficaria com o banco mexido à mão ou, na tarefa 16, com um arquivo de restauração errado. Com −50 a rota responde:

```json
{"total_xp": -50, "level": 1, "xp_into_level": 0, "xp_for_next_level": 100, "progress_percent": 0}
```

`total_xp` mostra a soma real, porque o histórico existe para auditar (seção 4.4) e esconder o número atrapalharia achar o erro. Nível e barra tratam o negativo como 0, igual ao atraso negativo em `effective_postponements`. Sem o `max`, a barra sairia −50%.

### 5. Desempenho

O laço atual dá **uma volta por nível**. Medi no meu computador:

| XP total | Nível | Voltas do laço atual | Tempo atual | Com a divisão |
| --- | --- | --- | --- | --- |
| 4.380.000 (100 anos a 120 XP/dia) | 2.173 | 2.172 | 0,002 s | 0,0001 s |
| 2.147.483.647 | 1.037.489 | 1.037.488 | 0,98 s | 0,0001 s |
| 10.000.000.000 | 4.830.975 | 4.830.974 | 4,3 s | 0,0001 s |
| 10¹⁵ | 483.091.787.497 | 483 bilhões | horas | 0,0001 s |

**Com o uso real, o laço nunca ficaria lento:** 100 anos dão 2 ms. Mesmo assim vale a divisão: custa 3 linhas, o número de voltas passa a ter teto (no máximo 99), e a rota fica protegida de um total absurdo vindo de uma restauração, que travaria o servidor.

**Por que não uma conta direta desde o nível 1:** os níveis de 1 a 99 têm custos diferentes, então eles precisam do laço, que tem no máximo 99 voltas. Guardar os 86.928 XP como constante seria um segundo número a manter em dia quando a fórmula mudar (seção 4.7).

Conferi o resultado novo contra o laço atual de 0 a 120.000 XP, de 13 em 13: deu igual em todos.

### 6. A soma: no banco, com `SUM`

```python
total_xp = session.exec(select(func.sum(XpEntry.amount))).one() or 0
```

- **No banco, porque:** com 365 mil linhas (100 anos a 10 tarefas por dia), o `SUM` levou 0,02 s e a soma no Python, 0,35 s. O Python precisaria trazer todas as linhas para a memória; o banco devolve um número só.
- **Continua SQLModel:** `func.sum` monta o `SELECT sum(xpentry.amount)` para cada banco, sem SQL escrito à mão. Conferi que o texto gerado é o mesmo no SQLite e no PostgreSQL.
- **Histórico vazio:** a soma de nenhuma linha dá `NULL`, que chega como `None`. Conferi. O `or 0` troca por 0, e a resposta é nível 1, 0 XP, barra em 0%.
- **Fica para a tarefa 16:** no PostgreSQL, `sum` de `INTEGER` devolve `BIGINT`, que chega ao Python como `int`. Conferir quando o driver entrar.

**Conceito novo, função de agregação:** em vez de devolver uma linha por registro, o banco junta todas e devolve um valor só. `SUM` soma; `COUNT` contaria.

### 7. Arquivo novo `backend/app/routers/player.py`

O jogador não é tarefa nem tipo, então ganha um router próprio, no padrão dos outros dois. Em `main.py`: `from app.routers import player, task_types, tasks` e `app.include_router(player.router)`.

```python
# O que a API devolve sobre o jogador: XP total, nível e barra (seção 6.2).
class Player(SQLModel):
    total_xp: int
    level: int
    xp_into_level: int
    xp_for_next_level: int
    progress_percent: int


# Só lê o banco, então pode ser GET (seção 6.7). As contas ficam em rules/xp.py.
@router.get("")
def get_player(session: SessionDep) -> Player:
    # A soma de nenhuma linha vem do banco como None, e o histórico vazio vale 0.
    total_xp = session.exec(select(func.sum(XpEntry.amount))).one() or 0
    level, xp_into_level = level_progress(total_xp)
    xp_for_next_level = xp_to_next_level(level)

    return Player(
        total_xp=total_xp,
        level=level,
        xp_into_level=xp_into_level,
        xp_for_next_level=xp_for_next_level,
        progress_percent=progress_percent(xp_into_level, xp_for_next_level),
    )
```

Reaproveita `SessionDep` de `task_types.py`, como `tasks.py` já faz. Na tarefa 15, o teste que percorre `app.openapi()` vai cobrir `/player` sozinho.

## Testes

Escrevo os testes antes do código e vejo falharem. Depois, tiro por um momento, uma de cada vez, o `max`, o desvio do nível 100, o `//` (trocando por arredondamento normal) e o `or 0`, vejo algum teste falhar em cada caso e desfaço. Espero perto de **580 testes** e digo o número exato no resumo.

**`test_xp.py`, `level_progress` e `progress_percent`:**

| XP total | Nível | Dentro do nível | Custo | % |
| --- | --- | --- | --- | --- |
| −50 | 1 | 0 | 100 | 0 |
| 0 | 1 | 0 | 100 | 0 |
| 99 | 1 | 99 | 100 | 99 |
| 100 | 2 | 0 | 102 | 0 |
| 201 / 202 | 2 / 3 | 101 / 0 | 102 / 106 | 99 / 0 |
| 86.927 | 99 | 2.039 | 2.040 | 99 |
| 86.928 (chega ao 100) | 100 | 0 | 2.070 | 0 |
| 86.929 (um XP depois) | 100 | 1 | 2.070 | 0 |
| 88.997 / 88.998 | 100 / 101 | 2.069 / 0 | 2.070 | 99 / 0 |

Mais:

- **Os 9 casos antigos de `level_from_total_xp`**, passados para `level_progress`.
- **Nunca 100% sem subir, em todos os níveis de 1 a 110:** no último XP antes de subir, a barra está em 99% ou menos e o nível não mudou; no XP seguinte, o nível sobe e a barra volta a 0%.
- **Depois do 100, cada 2.070 XP é um nível:** `86.928 + n × 2.070` dá o nível `100 + n` com sobra 0, para alguns `n`.
- **A divisão dá o mesmo que pagar nível por nível:** o teste tem um laço simples próprio, sem o desvio, e compara os dois de 86.000 a 100.000 XP.
- **Total enorme, rápido e certo:** 10¹⁵ XP dá nível 483.091.787.497 com sobra 1.282. Um contador troca `xp_to_next_level` e exige no máximo 199 chamadas. Ele falha na chamada 200, então, se o laço voltar a ser nível por nível, o teste falha na hora em vez de travar o pytest por horas.
- **Conta só de inteiros:** 29 XP no nível 1 dá 29%, não 28%.

**`tests/test_player.py` (novo):**

| Caso | Esperado |
| --- | --- |
| Critério da tarefa | Linhas somando 120: nível 2 e 19%, com o JSON inteiro conferido |
| Histórico vazio | `{"total_xp": 0, "level": 1, "xp_into_level": 0, "xp_for_next_level": 100, "progress_percent": 0}` |
| Fronteiras da 4.5 pela rota | 0, 99, 100, 86.928 e 86.929 XP |
| Concluir muda, desmarcar volta | Com 0 XP, concluir uma tarefa média leva a 25 XP e 25%; desmarcar devolve o JSON igual ao de antes |
| Subir e descer de nível | Com 95 XP, concluir a média leva ao nível 2 e 19%; desmarcar volta ao nível 1 e 95% |
| Tarefa que vale 0 | Concluir não muda o `/player` |
| Excluir concluída mantém o XP | O `/player` não muda (seção 4.3) |
| Soma negativa | A resposta da decisão 4, nunca 500 |
| Total enorme pela rota | 5 linhas de 2.147.483.647 (o maior `INTEGER` do PostgreSQL): nível 5.187.216, sobra 1.187, 57%, em menos de 0,5 s. O laço atual levaria uns 4 s |
| Só lê | Duas chamadas seguidas dão o mesmo JSON, e o histórico continua igual |
| `POST /player` | 405 |

Nos testes de concluir e desmarcar, o "hoje" fica fixo trocando `app.dates.utc_now`, como em `set_now` de `test_tasks.py`, para a meia-noite não mudar o XP da tarefa. A tarefa é criada pela API e o XP inicial entra direto no banco, com um auxiliar pequeno no próprio arquivo.

## Especificação e regras 9, 12, 13 e 14

**`docs/especificacao.md`:**

- **Seção 4.5:** a regra da barra: porcentagem inteira, arredondada para baixo, de 0 a 99, e XP total negativo tratado como 0 no nível e na barra.
- **Seção 10:** bloco "Decisões da tarefa 8", com a rota, os campos, a conta em duas funções, a porcentagem, o negativo, a divisão depois do nível 100, o `SUM` e o histórico vazio, e a conferência do `BIGINT` na tarefa 16.
- **Seção 10:** bloco "Fora da tarefa 8", abaixo.
- **Mapa do código (seção 12), regra 12:** linhas novas de `routers/player.py` e `tests/test_player.py`; `main.py` com o router novo; `xp.py` e `test_xp.py` com `level_progress` e `progress_percent` no lugar de `level_from_total_xp`.

**"Fora da tarefa 8", sem implementar:**

- **Como a tela da tarefa 13 descobre que você subiu de nível:** depois de concluir, a tela já precisa pedir o `/player` de novo para atualizar a barra. Ela compara o `level` novo com o que estava mostrando e, se for maior, mostra a comemoração. Não precisa de campo novo na API, e o JavaScript só compara dois números que vieram do servidor, sem fazer conta de XP. Ao abrir o app não há comparação, então não há comemoração falsa. Desmarcar e concluir de novo comemora outra vez, o que é inofensivo. Alternativa, se um dia o segundo pedido incomodar: a resposta de concluir traz o nível. Decidir na tarefa 13.

**Regra 9:** as contas e o arredondamento ficam em `rules/xp.py`, com teste. A rota só soma, chama as regras e responde.

**Regra 13:** ao terminar, renomeio este arquivo para `08-api-do-jogador.md`.

**Regra 14:** confiro os arquivos novos e alterados à procura de segredos e digo no resumo. O `.env` e as variações ficam fora. Nada nesta tarefa usa senha.

**Commit:** não faço commit nem sugiro mensagem.

## Arquivos

| Arquivo | Mudança |
| --- | --- |
| `backend/app/rules/xp.py` | `level_progress` no lugar de `level_from_total_xp`, `progress_percent`, uma linha no comentário "Atenção" |
| `backend/app/routers/player.py` | novo: `Player` e `GET /player` |
| `backend/app/main.py` | import e registro do router |
| `backend/tests/test_xp.py` | testes das duas funções; os casos antigos passam para `level_progress` |
| `backend/tests/test_player.py` | novo: testes da rota |
| `docs/especificacao.md` | seções 4.5, 10 e 12 |
| `docs/planos/` | este plano, renomeado |

## Resultado

- **Testes:** 567 passando, 32 a mais que os 535 de antes. A estimativa era perto de 580.
- **Trechos tirados um de cada vez:** sem o `max`, falham 3 testes; sem a divisão depois do nível 100, 9; com o laço voltando a pagar nível por nível, 2 (o contador falha na hora, e a rota passa de 0,5 s); com o arredondamento normal, 6; com `math.floor` e número quebrado, 1; sem o `or 0`, 2. Os dois arquivos voltaram idênticos, conferidos por hash.

## Como você vai testar

Na pasta `backend`, com o ambiente virtual ativo:

```powershell
pytest
pytest tests/test_xp.py tests/test_player.py -v
```

Depois, suba o app:

```powershell
uvicorn app.main:app --reload
```

1. Abra `http://localhost:8000/player` no navegador. Com o banco de hoje, vale o XP que você já ganhou pelo `/docs`; com o histórico vazio, a resposta é nível 1 e 0%.
2. Em `http://localhost:8000/docs`, crie uma tarefa `medium` com a data de hoje e conclua com `POST /tasks/{task_id}/complete`.
3. Recarregue `/player`: `total_xp` subiu 25 e `progress_percent` acompanha.
4. Desmarque com `POST /tasks/{task_id}/uncomplete` e recarregue `/player`: volta ao que estava no passo 1.
