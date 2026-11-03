# Plano: tarefa 7, botão Adiar

## Contexto

A tarefa 7 cria a rota do botão Adiar. Regra decidida por você: `nova data = o maior entre a data marcada e hoje em Brasília, mais 1 dia`. O critério da seção 10 é que os testes cubram 0, 1, 2, 3 e 4 adiamentos. Hoje são 439 testes coletados. Nenhuma tabela muda, então não é preciso apagar o `agenda.db`. Até aqui só li arquivos e rodei uma simulação num banco em memória, sem gravar nada em disco.

## Regra 11: três pontos diferentes do pedido, para a sua decisão

### 1. `change_due_date` não pode ser chamada inteira

Ela altera a `Task` em memória, e o commit grava sem condição nenhuma. Se depois viesse um `UPDATE` condicional, o SQLModel enviaria antes a alteração pendente (o *autoflush*), e a condição não protegeria nada.

**Proposta:** tirar dela as duas conferências, sem mudar o que ela faz, numa função nova que a edição e o Adiar usam.

```python
# Responde 409 se a data não puder mudar: tarefa concluída ou data travada.
def ensure_due_date_can_change(task: Task, days_late: int) -> None:
    if task.completed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a data."
        )

    if is_due_date_locked(task.postponements, days_late):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A data desta tarefa está travada e não pode mudar."
        )


# Muda a data de uma tarefa na edição. Quem chama já conferiu que a data é outra e que não é
# anterior a hoje. A trava vem antes do contador, porque postponements_after_date_change não a
# confere. Os dias de atraso podem sair negativos aqui, com a data no futuro: as regras de xp.py
# tratam esse valor como 0.
def change_due_date(task: Task, new_due_date: date) -> None:
    days_late = (app_today() - task.due_date).days
    ensure_due_date_can_change(task, days_late)

    task.postponements = postponements_after_date_change(
        task.postponements, days_late, task.due_date, new_due_date
    )
    task.due_date = new_due_date
```

O Adiar reaproveita as duas conferências, as mensagens e `postponements_after_date_change`. Os testes atuais da edição não mudam e protegem essa troca.

### 2. `ensure_date_is_not_past` não entra no Adiar

Ela nunca dispararia aqui. A data nova é no mínimo `hoje + 1`, então nunca é anterior a hoje. Seria uma linha que você leria e nenhum teste conseguiria exercitar (regra 5). No lugar dela, um teste em `test_xp.py` prova que a data nova é sempre depois de hoje.

**Isso muda a decisão da etapa 5.9** ("a tarefa 7 chama as duas, nesta ordem"), e atualizo o texto na especificação.

### 3. O pedido deixa de ser sem corpo

A tarefa 6 não tem corpo, mas aqui a data da tela precisa viajar. O corpo é `{"shown_due_date": "2026-11-02"}`. O nome evita confundir com a data nova, que é o servidor quem calcula.

## As 5 decisões

### 1. A rota: `POST /tasks/{task_id}/postpone`

| | |
| --- | --- |
| Corpo | `{"shown_due_date": "AAAA-MM-DD"}`, obrigatório. Campo desconhecido dá 422, como em toda a API |
| Sucesso | 200 com a `Task` atualizada, como no `PUT` |
| Recusas | 422, 404, 409 |

- **Por que `POST`:** altera dados, então não pode ser `GET` (seção 6.7). Também não é `PUT`, porque repetir o pedido não dá o mesmo resultado: o segundo é recusado.
- **Por que devolve só a `Task`:** adiar não mexe no XP, porque nenhuma linha entra no histórico. Um `xp_change` valeria sempre 0. A tela precisa só de `due_date` e `postponements`.

### 2. A conta da nova data fica em `rules/xp.py`

É regra do jogo (seção 4.2), é pura e não lê o relógio, então a regra 9 manda para lá. `dates.py` responde "que dia é", e não é ele quem decide quanto um adiamento anda. O número vira constante no topo.

```python
# O botão Adiar leva a tarefa para este número de dias depois da data marcada.
POSTPONE_DAYS = 1


# Calcula a data nova do botão Adiar: 1 dia depois da data marcada. Se a tarefa estiver
# atrasada, conta a partir de hoje, então ela vai para amanhã. Devolve None se esse dia não
# existir: o Python não representa nenhuma data depois de 9999-12-31.
def postponed_due_date(due_date: date, today: date) -> date | None:
    try:
        return max(due_date, today) + timedelta(days=POSTPONE_DAYS)
    except OverflowError:
        return None
```

**Conceito novo, `try`/`except`:** o Python tenta o bloco do `try`. Se aquele erro acontecer, ele roda o `except` em vez de quebrar. Prefiro isso a comparar com `date.max`, que só estaria certo enquanto `POSTPONE_DAYS` valesse 1.

### 3. Toque duplo: aprovo a sua proposta e acrescento o `UPDATE` condicional

Simulei cada caso com os modelos reais, no SQLite em memória, em ordem controlada, sem threads de verdade. Tarefa marcada para 02/11, sem adiamentos.

| Caso | Solução | Resultado | Certo? |
| --- | --- | --- | --- |
| A. Dois toques em sequência | Sem conferência | 04/11, 2 adiamentos | Não: o erro que você apontou |
| B. Dois toques simultâneos | Ler, conferir e gravar | 03/11, 1 adiamento, os dois respondem 200 | Sim |
| C. Adiar e Concluir simultâneos | Ler, conferir e gravar | Tarefa **concluída** com data 03/11 e 1 adiamento | Não: quebra a seção 6.1 |
| D. Dois toques simultâneos | `UPDATE` condicional | 03/11, 1 adiamento, um muda 1 linha e o outro 0 | Sim |
| E. Adiar e Concluir simultâneos | `UPDATE` condicional | Concluída, com data 02/11 e 0 adiamentos | Sim |

**O que é diferente da tarefa 6:** lá, dois pedidos simultâneos davam XP em dobro, porque cada um **acrescentava** uma linha. Aqui, cada um **grava valores absolutos** calculados a partir da mesma leitura, então o segundo só repete o primeiro (caso B). Para o toque duplo puro, a data da tela já resolve sozinha.

**Por que quero o `UPDATE` condicional mesmo assim:** o caso C. A caixinha e o botão Adiar ficam no mesmo cartão, e a tarefa concluída acabaria com a data mudada. O efeito é pequeno e a chance é baixa, mas o custo também é: uma instrução, no padrão que você já conhece da tarefa 6. A sua regra, "só adia se a tarefa ainda tiver essa data", passa a valer no momento da gravação, não só no da leitura. E a conferência da data **é** a condição do `UPDATE`, então não existe um `if` a mais.

| Alternativa | Por que não |
| --- | --- |
| Só bloquear o botão no front-end | Não protege pedidos que já saíram, e a garantia precisa estar no back-end |
| O celular manda a data nova, e repetir não muda nada | A conta iria para o JavaScript, contra a regra 9 |
| Coluna de versão na tarefa | Muda a tabela e apaga o `agenda.db`, para um ganho que a data já dá |
| Ignorar toques em menos de N segundos | Regra de tempo frágil, que recusaria um segundo adiamento legítimo |

**Conceito novo, a concorrência otimista:** em vez de impedir que os outros mexam, o pedido diz em que estado viu a tarefa e só grava se ela continuar assim. Se não continuar, ele avisa, e quem pediu olha de novo.

**O código da rota:**

```python
# O que a API recebe ao adiar: a data que a tela mostrava. A data nova é o servidor quem
# calcula. Um toque duplo manda duas vezes a mesma data, e o segundo pedido é recusado.
class TaskPostpone(SQLModel):
    model_config = ConfigDict(extra="forbid")

    shown_due_date: date


# A tarefa só muda se ainda estiver pendente e com a data que a tela mostrava, numa instrução
# só, como em change_completed. Assim, dois pedidos ao mesmo tempo, ou um Adiar junto com um
# Concluir, não passam os dois. Adiar não mexe no XP, então nada entra no histórico.
@router.post(
    "/{task_id}/postpone",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {
            "description": (
                "A tarefa está concluída, travada ou na última data possível, "
                "ou a tela estava desatualizada."
            )
        },
    },
)
def postpone_task(task_id: TaskId, postpone_input: TaskPostpone, session: SessionDep) -> Task:
    task = get_task_or_404(session, task_id)

    today = app_today()
    days_late = (today - task.due_date).days
    ensure_due_date_can_change(task, days_late)

    new_due_date = postponed_due_date(task.due_date, today)
    if new_due_date is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Esta tarefa já está na última data possível e não pode ser adiada.",
        )

    new_postponements = postponements_after_date_change(
        task.postponements, days_late, task.due_date, new_due_date
    )

    changed_rows = session.exec(
        update(Task)
        .where(
            Task.id == task_id,
            Task.completed == False,
            Task.due_date == postpone_input.shown_due_date,
        )
        .values(due_date=new_due_date, postponements=new_postponements)
    ).rowcount

    if changed_rows == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A tarefa mudou desde que a tela foi aberta. Atualize a lista.",
        )

    session.commit()
    session.refresh(task)
    return task
```

O relógio é lido uma vez só, então a trava e o contador usam o mesmo "hoje", mesmo à meia-noite. Por isso `ensure_due_date_can_change` recebe `days_late`, em vez de ler o relógio por conta própria.

**Limites que ficam:**

- **Testei só no SQLite.** No PostgreSQL, o comportamento documentado é o mesmo da tarefa 6. Junto com ela, conferir com pedidos simultâneos quando o driver entrar, na tarefa 16.
- **A data sai de D, vai para outra e volta a D:** uma tela antiga, ainda com D, consegue adiar. É inofensivo: a data é a que você via, e o contador é calculado da tarefa lida agora.

### 4. A última data: 409

Uma tarefa em `9999-12-31` responde **409**: "Esta tarefa já está na última data possível e não pode ser adiada." Nada é gravado.

- Pela seção 6.1, 409 é "dado válido, mas o estado da tarefa impede". É esse o caso: a `shown_due_date` está certa, e quem não permite adiar é a data atual da tarefa.
- 422 seria errado, porque o pedido não trouxe dado inválido. Quem calcula a data nova é o servidor.
- Conferi: somar um dia a essa data dá `OverflowError`. Sem o cuidado, viraria 500.
- `9999-12-30` continua adiando normalmente, para `9999-12-31`.

### 5. Ordem das recusas

| # | Código | Quando | Quem confere |
| --- | --- | --- | --- |
| 1 | 422 | Id fora do intervalo ou corpo inválido | O FastAPI, antes de a rota rodar |
| 2 | 404 | Id desconhecido | `get_task_or_404` |
| 3 | 409 | Tarefa concluída | `ensure_due_date_can_change` |
| 4 | 409 | Data travada | `ensure_due_date_can_change` |
| 5 | 409 | Última data possível | `postponed_due_date` |
| 6 | 409 | Tela desatualizada | Condição do `UPDATE` |

**Por que essa ordem dos 409, do mais definitivo para o mais passageiro:**

1. **Concluída primeiro:** é a mesma ordem da edição, e a mensagem diz o que fazer: desmarcar. A tarefa concluída e travada recebe essa mensagem, como já testa `test_completed_and_locked_task_gets_the_completed_message`.
2. **Travada depois:** recarregar não resolve, então esse é o motivo real. Dizer "atualize a lista" para uma tarefa travada mandaria você tentar de novo à toa.
3. **Última data depois:** a data nova precisa existir antes do `UPDATE`.
4. **Tela desatualizada por último:** é o único caso que se resolve recarregando. E vem do próprio mecanismo: a condição só roda quando o `UPDATE` roda.

**Consequência:** no toque duplo que atinge a trava (2 → 3), o segundo toque recebe "travada", não "tela desatualizada". É verdade e não grava nada. E como todo 409 faz a tela recarregar (tarefa 10), o botão aparece bloqueado logo depois.

## Testes

Escrevo os testes antes do código e vejo falharem. Depois da implementação, tiro por um momento cada condição do `UPDATE`, uma de cada vez, vejo os testes da corrida falharem e desfaço. Espero chegar perto de **500 testes** e digo o número exato no resumo.

Nos testes, "hoje" é 01/11/2026 (`fixed_today`). Auxiliares novos em `test_tasks.py`: `postpone_task` e `assert_postpone_refused`, que compara `database_snapshot` antes e depois.

**`test_xp.py`, `postponed_due_date` e `POSTPONE_DAYS`:**

| Marcada | Hoje | Esperado |
| --- | --- | --- |
| 10/11 (futura) | 01/11 | 11/11 |
| 01/11 (hoje) | 01/11 | 02/11 |
| 31/10 e 30/10 (atrasada) | 01/11 | 02/11 |
| 31/12/2026 | 31/12/2026 | 01/01/2027 |
| 9999-12-30 | 01/11 | 9999-12-31 |
| 9999-12-31 | 01/11 | `None` |

Mais: em todos os casos com data, a data nova é depois de hoje. É a prova da decisão de não chamar `ensure_date_is_not_past`.

**`test_tasks.py`, os obrigatórios:**

| Pedido | Como fica |
| --- | --- |
| 0, 1, 2 adiamentos | Tarefa em 05/11: contador vira 1, 2, 3, data vira 06/11 |
| 3 e 4 adiamentos | 409 com a mensagem da trava, nada gravado |
| Efetivos com atraso | Aceita: 0 + 1 → 2 e 1 + 1 → 3. Recusa: 0 + 3, 1 + 2, 2 + 1, 2 + 2, 0 + 4 |
| Data futura | 10/11 vai para 11/11, não para amanhã |
| Vence hoje | 01/11 vai para 02/11 |
| Atrasada | 30/10 vai para 02/11, contador `0 + 2 + 1 = 3`, e a próxima tentativa dá 409 |
| Meia-noite em Brasília | Tarefa de 31/10, 0 adiamentos: às 02h59 UTC de 01/11 vai para 01/11, contador 1; às 03h00 UTC vai para 02/11, contador 2 |
| Trava à meia-noite | Tarefa de 31/10, 2 adiamentos: às 02h59 UTC aceita, às 03h00 UTC dá 409 |
| Concluída | 409 com a mensagem de desmarcar, inserida no banco e concluída pela API |
| Toque duplo em sequência | Segundo pedido com a mesma data dá 409: fica 1 dia e 1 adiamento. Concluir depois vale 18 XP, não 12 |
| 9999-12-31 | 409, nunca 500, nada gravado. 9999-12-30 aceita, e o segundo toque dá 409 |
| Id | 999 e 2147483647 dão 404; 0, −1, 2147483648 e 10³⁰ dão 422; tarefa excluída dá 404 |
| `GET` na rota | 405, nada gravado |
| Recusado não grava | Todo 404, 409 e 422 passa por `assert_postpone_refused` |

**`test_tasks.py`, os que proponho a mais:**

- **Corrida, dois Adiar:** uma sessão lê a tarefa, outro pedido adia, e a rota roda com a leitura velha. Dá 409 e fica 1 adiamento. Sem threads, no estilo de `test_complete_with_an_old_read_gets_409_and_gives_no_xp`.
- **Corrida, Adiar e Concluir (caso C):** a sessão lê a tarefa pendente, outro pedido conclui, e a rota dá 409. A data e o contador não mudam.
- **Tela antiga com qualquer data:** `shown_due_date` diferente, no passado ou no futuro, dá 409 com a mensagem de tela desatualizada.
- **Recarregar e adiar de novo:** com a data nova da resposta, o pedido passa, contador 2.
- **Sequência inteira pela API:** 3 adiamentos seguidos a partir de hoje e o quarto dá 409. A tarefa travada ainda aceita editar o título, e concluir vale 6 XP.
- **Ordem dos 409:** concluída + travada + tela antiga dá a mensagem de concluída; travada + tela antiga, a da trava; última data + tela antiga, a da última data; travada + última data, a da trava; concluída + última data, a de concluída.
- **Corpo inválido:** sem corpo, sem o campo, data malformada, `null` e campo desconhecido (como `due_date`) dão 422. Com id desconhecido ou tarefa concluída, continua 422, porque o dado vem antes.
- **O resto não muda:** título, notas, cor, dificuldade, tipo, `created_at` e as outras tarefas ficam iguais, e nenhuma linha entra no histórico.
- **Listagens:** a tarefa adiada muda de dia; a atrasada sai de `overdue` e aparece em `pending` de amanhã.
- **Adiar custa 25%:** tarefa média adiada uma vez e concluída no dia novo vale 18 XP.

## Especificação e regras 9, 12, 13 e 14

**`docs/especificacao.md`:**

- **Seção 4.2:** a regra do botão, com a fórmula, o motivo de "sempre amanhã" ter sido descartado (numa data futura, viraria antecipar) e "outra data, só pela edição".
- **Seção 6.1, Recusas:** o 409 passa a incluir adiar uma tarefa na última data possível e adiar com a tela desatualizada.
- **Seção 10, etapa 5.9:** corrijo a decisão que diz que a tarefa 7 chama as duas funções, e a frase da entrega sobre o reaproveitamento.
- **Seção 10:** bloco "Decisões da tarefa 7", com a rota, o corpo, a resposta, o `UPDATE` condicional e o motivo, a ordem das recusas e a conferência no PostgreSQL na tarefa 16.
- **Seção 10:** bloco "Fora da tarefa 7", com os dois pontos abaixo.
- **Mapa do código (seção 12), regra 12:** linhas de `xp.py`, `tasks.py`, `test_xp.py` e `test_tasks.py`.

**"Fora da tarefa 7":**

- **Front-end:** o botão manda em `shown_due_date` a data que recebeu da listagem e nunca calcula a data nova. O 409 recarrega a lista, como no Concluir.
- **A edição tem a mesma brecha do caso C:** um `PUT` que muda a data, sobreposto a um Concluir, grava a data numa tarefa concluída; sobreposto a um Adiar, perde um adiamento. Não mexo agora, porque não é a tarefa pedida (regra 2) e é bem menos provável, já que o formulário fica em outra tela. Fica registrado para você decidir se e quando tratar.

**Regra 9:** a conta e a constante ficam em `rules/xp.py`, com teste. A rota só lê, chama as regras e grava.

**Regra 13:** ao terminar, renomeio este arquivo para `07-botao-adiar.md`.

**Regra 14:** confiro os arquivos novos e alterados à procura de segredos e digo no resumo. O `.env` e as variações ficam fora. Nada nesta tarefa usa senha.

**Commit:** não faço commit nem sugiro mensagem.

## Arquivos

| Arquivo | Mudança |
| --- | --- |
| `backend/app/rules/xp.py` | `POSTPONE_DAYS`, `postponed_due_date`, import de `timedelta` |
| `backend/app/routers/tasks.py` | `TaskPostpone`, `ensure_due_date_can_change` (saída de `change_due_date`), `POST /tasks/{task_id}/postpone`, comentário de `change_due_date` |
| `backend/tests/test_xp.py` | testes da conta nova |
| `backend/tests/test_tasks.py` | auxiliares e testes da rota |
| `docs/especificacao.md` | seções 4.2, 6.1, 10 e 12 |
| `docs/planos/` | este plano, renomeado |

## Resultado

- **Testes:** 535 passando, 96 a mais que os 439 de antes. A estimativa era perto de 500. A diferença vem do corpo inválido, em que cada um dos 7 corpos roda em 4 situações.
- **Condições do `UPDATE`:** sem `Task.completed == False`, falha 1 teste, o do Adiar junto com Concluir. Sem a condição da data, falham 5: o toque duplo, a tela antiga (3 casos) e a corrida de dois Adiar. O arquivo voltou idêntico, conferido por hash.
- **Threads de verdade, fora da suíte, no SQLite, com banco temporário:** 8 Adiar simultâneos, 30 rodadas, deram 30 respostas 200 e 210 respostas 409, sempre com 1 adiamento e 1 dia. Adiar junto com Concluir, 30 rodadas, deu 48 respostas 200 e 12 respostas 409, e o Concluir passou em todas. Nenhum erro 500.

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
2. `POST /tasks/{task_id}/postpone` com `{"shown_due_date": "<a data de hoje>"}`: a resposta traz amanhã em `due_date` e `postponements` 1.
3. Repita o passo 2 igual: a resposta é 409, "A tarefa mudou desde que a tela foi aberta. Atualize a lista."
4. Repita com a data que a resposta do passo 2 trouxe, e de novo com a seguinte: `postponements` chega a 3.
5. Mais uma vez, com a data atual: a resposta é 409, "A data desta tarefa está travada e não pode mudar."
6. Crie uma tarefa com data daqui a 10 dias e adie: ela vai para o dia seguinte a essa data, não para amanhã.
7. Crie uma tarefa com data `9999-12-31` e adie com essa data: a resposta é 409, não 500.
8. `POST /tasks/{task_id}/complete` numa tarefa pendente, depois adie: a resposta é 409, "Desmarque a tarefa antes de mudar a data."
9. Adie com o id `999999`: a resposta é 404. Com o id `0`: a resposta é 422.

Abra `http://localhost:8000/tasks/1/postpone` no navegador: a resposta é "Method Not Allowed" (405), porque navegar é um `GET`.

Tarefas atrasadas só aparecem nos testes, porque a API recusa criar tarefa com data passada.
