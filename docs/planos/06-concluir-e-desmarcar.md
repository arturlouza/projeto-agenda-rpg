# Plano: tarefa 6, concluir e desmarcar

## Contexto

A tarefa 6 é a primeira que gera XP de verdade. Até aqui, os testes inseriam linhas de histórico direto no banco. O critério da seção 10 é: concluir e desmarcar deixa o XP total igual ao de antes. Hoje são 353 testes. Nenhuma tabela muda, então não é preciso apagar o `agenda.db`. Até aqui só li arquivos e rodei um experimento num banco temporário, fora do projeto.

## O que encontrei e muda o pedido

### Toque duplo dá XP em dobro (regra 11: preciso da sua decisão)

O jeito comum seria ler a tarefa, conferir `task.completed` e gravar. Esse jeito tem uma brecha. Dois pedidos ao mesmo tempo leem `completed = False`, os dois passam na conferência e os dois gravam uma linha. O FastAPI roda rotas `def` em várias threads, então os pedidos podem mesmo se sobrepor: basta um toque duplo na caixinha.

Testei com dois pedidos simultâneos, 30 rodadas em cada jeito, numa tarefa média, forçando a sobreposição com uma barreira entre as threads. Sem a barreira, ela acontece menos vezes, mas pode acontecer.

| Jeito | Rodadas com XP errado | Total |
| --- | --- | --- |
| Ler, conferir e gravar | 30 de 30 | 50 XP (o certo é 25) |
| `UPDATE` condicional, 2 pedidos | 0 de 30 | 25 XP |
| `UPDATE` condicional, 8 pedidos | 0 de 30 | 25 XP |

No desmarcar, o problema seria duas linhas de −25, que deixariam a tarefa pendente com soma −25.

**Conceito novo, a condição de corrida:** é o erro em que o resultado depende de qual pedido chega primeiro. O `task.completed` que li pode já estar velho quando eu for gravar.

**Proposta, o `UPDATE` condicional:** em vez de conferir em Python, peço ao banco uma instrução só, "mude para concluída **se ainda estiver pendente**". O banco deixa só um pedido fazer isso de cada vez. O segundo espera e encontra 0 linhas para mudar, e `rowcount` (quantas linhas a instrução mudou) vira o 409.

- Usa `update` do próprio SQLModel, sem SQL à mão e sem dependência nova. Conferi: a versão 0.0.48 exporta `update`, e `session.exec` aceita essa instrução.
- É um pouco menos direto que um `if task.completed`, mas é uma função só, e a brecha mexe no XP, o dado que o app existe para proteger.
- O front-end da tarefa 10 pode bloquear a caixinha enquanto espera, mas isso não basta: a garantia precisa estar no back-end.

**Limite do que testei:** rodei só no SQLite. No PostgreSQL, o comportamento documentado do nível de isolamento padrão (`READ COMMITTED`) é o mesmo: o segundo `UPDATE` espera o primeiro e confere a condição de novo. Ainda não executei isso lá, porque o driver só entra na tarefa 16.

### O relógio dos testes precisa de mais um ponto

O `fixed_today` troca só `app.dates.utc_now`. Como `tasks.py` vai importar `utc_now` para gravar o `completed_at`, os testes gravariam a hora real do computador. Crio em `test_tasks.py` um auxiliar `set_now(monkeypatch, moment)`, que troca os dois pontos, e o `fixed_today` passa a usá-lo.

### Comentários que ficam falsos

Em `test_tasks.py`, os comentários de `insert_task` e `insert_xp_entry` dizem que a API não conclui tarefa e que gerar XP "só chega na tarefa 6". Corrijo os dois e nada além deles.

## As 9 decisões

### 1. Rotas

| Rota | O que faz | Sucesso | Recusas |
| --- | --- | --- | --- |
| `POST /tasks/{task_id}/complete` | Conclui e gera a linha de XP | 200 | 404, 409, 422 |
| `POST /tasks/{task_id}/uncomplete` | Desmarca e gera a linha de devolução | 200 | 404, 409, 422 |

- **Por que `POST`:** alteram dados, então não podem ser `GET` (seção 6.7). Também não são `PUT`, porque repetir o pedido não dá o mesmo resultado: o segundo é recusado. A tarefa 7 pode seguir o mesmo desenho, com `/postpone`.
- **Sem corpo no pedido:** o id na rota já diz tudo.
- **Resposta:** a tarefa e quanto o XP total mudou.

```json
{"task": {"id": 7, "completed": true, "...": "..."}, "xp_change": 18}
```

O `xp_change` vale `+18` ao concluir, `-18` ao desmarcar e `0` numa tarefa que vale 0. Ele serve para o "+XP" da seção 6.3 sem outra consulta, e já decido isso agora para não mudar o formato da resposta depois. O nível e o XP total ficam com o `/player`, na tarefa 8. É um modelo novo, `TaskXpChange`, no mesmo estilo de `DayTasks`.

### 2. XP ao concluir

```python
days_late = (app_today() - task.due_date).days
amount = task_xp(task.difficulty, task.postponements, days_late)
```

- `app_today()` dá o dia de hoje em Brasília, nunca em UTC, igual a `change_due_date`.
- Concluir antes do dia marcado deixa `days_late` negativo, e `task_xp` já trata isso como 0, ou seja, 100%. Um adiamento manual continua contando: 1 adiamento com data futura vale 75%.
- Não existe conta nova, só o `task_xp` de `rules/xp.py`.

**A conta pedida, tarefa média com 1 adiamento manual e 1 dia de atraso:**

```
adiamentos efetivos = 1 + 1 = 2
multiplicador       = 1 − 0,25 × 2 = 0,5
XP                  = 25 × 0,5 = 12,5, arredondado para baixo = 12
```

### 3. Devolução ao desmarcar: aprovo a sua proposta

A linha de desmarcar vale o negativo da soma das linhas da tarefa. Fica em `rules/xp.py`, como função pura:

```python
def xp_to_refund(earned_amounts: list[int]) -> int:
    return -sum(earned_amounts)
```

Exemplo com uma tarefa média marcada para 01/11:

| Quando | Ação | Linha | Soma da tarefa |
| --- | --- | --- | --- |
| 01/11 | concluir, sem atraso | +25 | 25 |
| 04/11 | desmarcar | −25 | 0 |
| 04/11 | concluir, 3 dias de atraso | +6 | 6 |
| 04/11 | desmarcar | −6 | 0 |

**Por que a soma é melhor do que negar a última linha:** "a última" dependeria de ordem, e a seção 6.1 proíbe depender da ordem dos ids, enquanto `created_at` pode empatar. A soma não precisa de ordem. E se um dia a soma estiver errada, o próximo desmarcar a traz de volta a 0.

**Dois cuidados:**

- **Bônus da V2:** a regra só vale se as linhas com `task_id` forem apenas as de concluir e desmarcar. Um bônus de missão ou sequência gravado com `task_id` seria devolvido junto. Registro isso na seção 4.4 para a V2 não tropeçar.
- **Ordem no código:** a soma é lida **depois** do `UPDATE` condicional. Assim nenhum outro pedido consegue mudar a tarefa entre a leitura e a gravação.

### 4. Estados inválidos: 409

Concluir uma tarefa já concluída e desmarcar uma pendente dão **409**, com as mensagens "A tarefa já está concluída." e "A tarefa já está pendente."

- A seção 6.1 já define 409 como "dado válido, mas o estado da tarefa impede".
- 422 seria errado, porque o pedido não tem dado inválido.
- Responder 200 sem fazer nada esconderia do front-end o que aconteceu.

A ordem é: 422 do id (o FastAPI confere antes de a rota rodar), depois 404, depois 409. Na tarefa 10, o front-end trata o 409 recarregando a lista, porque ele significa só que a tela estava desatualizada.

### 5. Tarefa que vale 0: grava a linha, ao concluir e ao desmarcar

- **Auditoria:** a seção 4.4 quer saber de onde veio cada ponto. A linha de 0 mostra que a tarefa foi concluída e não rendeu nada, em vez de parecer que o XP se perdeu.
- **Simplicidade:** concluir sempre grava uma linha, e desmarcar também. Não há `if` especial, e a soma continua certa, porque 0 não muda nada.
- **Custo:** uma linha a mais, sem efeito no total.

### 6. `completed_at`

- **Ao concluir:** recebe `utc_now()`, em UTC, como manda a seção 6.4.
- **Ao desmarcar:** volta a `None`.
- **Listagens:** `completed_on` e `pending_on` já resolvem tudo, sem mudança. Os testes passam a provar isso pela API, com a tarefa concluída de verdade: às 22h30 de 31/10 em Brasília, ela aparece em 31/10 e não em 01/11; ao desmarcar, volta ao dia marcado.
- **O que não muda:** `due_date` e `postponements`. Concluir não soma o atraso ao contador. Se somasse, desmarcar contaria o atraso duas vezes.

### 7. Texto do `reason`

```
Tarefa concluída: Ler 30 páginas
Tarefa desmarcada: Ler 30 páginas
```

- **Por que o título entra:** ao excluir a tarefa, a linha fica com `task_id` nulo (seção 4.3). Sem o título, "Tarefa concluída +25" não diria mais de onde veio o ponto.
- **Efeito colateral aceitável:** o título fica como estava naquele momento e continua no histórico depois de excluir a tarefa. A seção 6.7 já proíbe guardar dados sensíveis no título.
- **Regra:** nenhum código decide nada lendo esse texto. A lógica usa só `amount` e `task_id`.
- **Onde fica:** em `rules/xp.py`, nas funções `completion_reason(title)` e `uncompletion_reason(title)`.

### 8. Uma única transação

O `UPDATE` da tarefa e o `add` da linha acontecem antes de um único `session.commit()`. Se algo falhar no meio, a sessão fecha sem commit e o banco desfaz tudo. Testei isso: fechando a sessão sem commit, o `UPDATE` não ficou gravado. Um teste novo força um erro depois do `UPDATE` e confere que nem a tarefa nem o histórico mudaram, no mesmo estilo de `test_failed_delete_changes_nothing`.

### 9. Desmarcar uma tarefa atrasada: não abre brecha

Tarefa média marcada para 30/10:

| Dia | Ação | Atraso | Linha | XP total |
| --- | --- | --- | --- | --- |
| 01/11 | concluir | 2 dias | +12 | 12 |
| 02/11 | desmarcar (volta às atrasadas) | | −12 | 0 |
| 02/11 | concluir | 3 dias | +6 | 6 |
| 03/11 | desmarcar | | −6 | 0 |
| 03/11 | concluir | 4 dias | +0 | 0 |

**Por que não dá para ganhar a mais:**

1. Em qualquer momento, a soma de uma tarefa é 0 ou o valor da última conclusão. Os valores não se acumulam.
2. Os adiamentos efetivos nunca diminuem. Os dias passam e somam atraso. Ao tirar a tarefa do atraso, a data nova conta `manuais + atraso + 1`. E antecipar só é possível para uma data de hoje em diante, sem atraso envolvido.
3. Com o mesmo valor ou um menor a cada conclusão, marcar e desmarcar nunca rende mais. No caso atrasado, só faz perder.

A devolução lida do histórico é o que garante isso. Com um cálculo novo, a linha de 02/11 seria −6, e sobrariam 6 XP de graça a cada volta.

**O que continua possível, porque a especificação permite. Não mudo nada aqui:**

- **Editar a dificuldade da tarefa pendente:** concluir fácil (+10), desmarcar (−10), trocar para difícil e concluir (+50) dá 50 no total, não 60. É o mesmo que escolher difícil desde o início.
- **Criar, concluir e excluir tarefas repetidamente:** o XP fica, como manda a seção 4.3. Não vem de marcar e desmarcar, e criar tarefas é livre.

## Código

**`backend/app/rules/xp.py`:** `xp_to_refund`, `completion_reason`, `uncompletion_reason`.

**`backend/app/routers/tasks.py`:** o modelo `TaskXpChange`, uma função auxiliar e as duas rotas.

```python
# Muda o estado numa instrução só, que vale apenas se a tarefa ainda estiver no estado oposto.
# Dois pedidos ao mesmo tempo não passam os dois: o segundo encontra 0 linhas e recebe 409.
# Quem chama ainda precisa fazer o commit.
def change_completed(
    session: Session, task: Task, completed: bool, completed_at: datetime | None, refusal: str
) -> None:
    changed_rows = session.exec(
        update(Task)
        .where(Task.id == task.id, Task.completed != completed)
        .values(completed=completed, completed_at=completed_at)
    ).rowcount

    if changed_rows == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=refusal)

    session.refresh(task)


def complete_task(task_id: TaskId, session: SessionDep) -> TaskXpChange:
    task = get_task_or_404(session, task_id)
    change_completed(session, task, True, utc_now(), "A tarefa já está concluída.")

    days_late = (app_today() - task.due_date).days
    amount = task_xp(task.difficulty, task.postponements, days_late)
    session.add(XpEntry(amount=amount, reason=completion_reason(task.title), task_id=task_id))
    session.commit()
    session.refresh(task)
    return TaskXpChange(task=task, xp_change=amount)
```

`uncomplete_task` tem o mesmo formato, com `change_completed(session, task, False, None, ...)`, a soma lida do histórico e `xp_to_refund`. As duas rotas declaram os `responses` de 404 e 409, como as outras.

## Testes

Escrevo os testes antes do código e vejo falharem. Depois da implementação, troco por um momento o `UPDATE` condicional pela conferência comum, vejo o teste da corrida falhar e desfaço a troca. Espero chegar perto de **430 testes**, os 353 de hoje mais uns 78 novos, e digo o número exato no resumo.

**`test_xp.py`:** `xp_to_refund` com `[]`, `[25]`, `[0]`, `[25, -25]` e `[25, -25, 18]`, e o texto exato dos dois motivos.

**`test_tasks.py`, os obrigatórios:**

| Pedido | Como fica |
| --- | --- |
| Critério da tarefa | Total igual ao de antes em 1, 2 e 5 ciclos, conferindo a cada passo que a soma é 0 na pendente e igual ao XP ganho na concluída |
| Cada dificuldade × 0 a 4 adiamentos | 15 casos, com o número esperado escrito no teste: fácil 10, 7, 5, 2, 0; médio 25, 18, 12, 6, 0; difícil 50, 37, 25, 12, 0 |
| Mistura de manuais e atraso | Inclui o exemplo acima, 1 + 1 = 12 XP, e casos só com atraso |
| Antes do dia marcado | Vale 100%, inclusive com `9999-12-31`. Com 1 ou 3 adiamentos manuais e data futura, o atraso negativo não desconta nada: 18 e 6 XP |
| Meia-noite em Brasília | Tarefa de 31/10: às 02h59 UTC de 01/11 (23h59 em Brasília) vale 25; às 03h00 UTC (00h00 em Brasília) vale 18 |
| Devolução dias depois | Concluir (+25), avançar 5 dias, desmarcar (−25). Outro caso com uma linha de 7 no histórico, valor que a conta não daria, devolve −7 |
| Excluir concluída | O XP fica, com `task_id` nulo. Desmarcar antes de excluir remove o XP |
| Id desconhecido e fora do intervalo | 404 e 422 nas duas rotas, sem gravar nada, como nas outras rotas. Tarefa já excluída também dá 404 |
| Pedido recusado não grava | Todos os 404, 409 e 422 comparam tarefas e histórico antes e depois |

**`test_tasks.py`, os que proponho a mais:**

- **Corrida:** uma sessão lê a tarefa, outro pedido a conclui, e a rota é chamada com a sessão de leitura velha. Tem de dar 409, sem segunda linha. É determinístico, sem threads, e vale também para desmarcar.
- **Transação única:** erro forçado depois do `UPDATE`, sem nada gravado, nas duas rotas.
- **Sem brecha:** a tabela da decisão 9, com o relógio avançando; ciclos em dias seguidos nunca passam do valor atual; a troca de dificuldade dá 50, não 60.
- **Atrasada volta às atrasadas** na visão de hoje, ao desmarcar.
- **Conteúdo da linha:** `amount`, `reason` e `task_id` certos.
- **`postponements` e `due_date`** não mudam ao concluir nem ao desmarcar.
- **Tarefa que vale 0:** grava a linha de 0 nas duas ações, e `xp_change` é 0.
- **Outra tarefa:** desmarcar uma não mexe nas linhas da outra.
- **`GET` nas duas rotas** dá 405.
- **Concluída pela API** recusa mudar a dificuldade com 409.

## Especificação e regras 12, 13 e 14

**`docs/especificacao.md`:**

- **Seção 4.3:** a linha de desmarcar é o negativo da soma das linhas da tarefa.
- **Seção 4.4:** concluir e desmarcar sempre gravam uma linha, mesmo de 0; o formato do `reason`; só essas linhas levam `task_id`; nenhum código decide lendo o texto.
- **Seção 6.1, Recusas:** o 409 passa a incluir concluir tarefa concluída e desmarcar tarefa pendente.
- **Seção 10:** bloco "Decisões da tarefa 6", com as rotas, o formato da resposta e o `UPDATE` condicional com o motivo. E um "Fora da tarefa 6": o XP no cartão da concluída (seção 6.3) exige que a listagem traga esse valor, o que entra quando a tela precisar; o front-end trata o 409 na tarefa 10.
- **Mapa do código (seção 12), regra 12:** linhas de `xp.py`, `tasks.py`, `test_xp.py` e `test_tasks.py`.

**Regra 9:** os cálculos e os textos do histórico ficam em `rules/xp.py`, e cada regra nova tem teste. `tasks.py` só lê o banco, chama as regras e grava.

**Regra 13:** ao terminar, renomeio este arquivo para `06-concluir-e-desmarcar.md`.

**Regra 14:** confiro os arquivos novos e alterados à procura de segredos e digo no resumo. O `.env` e as variações ficam fora. Nada nesta tarefa usa senha.

**Commit:** não faço commit nem sugiro mensagem.

## Arquivos

| Arquivo | Mudança |
| --- | --- |
| `backend/app/rules/xp.py` | 3 funções novas |
| `backend/app/routers/tasks.py` | `TaskXpChange`, `change_completed`, 2 rotas |
| `backend/tests/test_xp.py` | testes das funções novas |
| `backend/tests/test_tasks.py` | `set_now`, 2 comentários corrigidos, testes das rotas |
| `docs/especificacao.md` | seções 4.3, 4.4, 6.1, 10 e 12 |
| `docs/planos/` | este plano, renomeado |

## Como você vai testar

Na pasta `backend`, com o ambiente virtual ativo:

```powershell
pytest
```

Depois, suba o app:

```powershell
uvicorn app.main:app --reload
```

Em `http://localhost:8000/docs`:

1. `POST /tasks`: crie uma tarefa `medium` com a data de hoje e anote o id.
2. `POST /tasks/{task_id}/complete`: a resposta traz `"xp_change": 25` e `completed` verdadeiro.
3. Repita o passo 2: a resposta é 409.
4. `GET /tasks/day/{day}` com a data de hoje: a tarefa está em `completed`.
5. `POST /tasks/{task_id}/uncomplete`: a resposta traz `"xp_change": -25`, e a tarefa volta a `pending`.
6. Repita o passo 5: a resposta é 409.
7. `POST /tasks/{task_id}/complete` com o id `999999`: a resposta é 404.

Para ver o histórico, porque a rota do XP só chega na tarefa 8. Rode na pasta `backend`, em outro terminal com o ambiente virtual ativo:

```powershell
python -c "from sqlmodel import Session, select; from app.database import engine; from app.models import XpEntry; rows = Session(engine).exec(select(XpEntry)).all(); [print(r.amount, r.reason, r.task_id) for r in rows]; print('Total:', sum(r.amount for r in rows))"
```

Depois dos passos acima, o total dessa tarefa é 0: uma linha de +25 e uma de −25. Atrasadas só aparecem nos testes, porque a API recusa criar tarefa com data passada.
