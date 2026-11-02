# Plano da etapa 5.8: editar tarefa, ainda sem mudar a data

## Contexto

A API das tarefas já cria, lista e exclui, mas ainda não edita. Esta etapa adiciona a edição de título, notas, cor, dificuldade e tipo, com as mesmas validações da criação. A mudança de data fica para a etapa 5.9.

## PUT ou PATCH

Não há motivo técnico para preferir PATCH, então fica **`PUT /tasks/{task_id}`**, como você decidiu. Conferi três pontos:

- **Repetir o pedido dá o mesmo resultado.** Essa é a promessa do PUT (idempotência). Ela continua valendo na 5.9: repetir a mesma data nova cai na regra do "mesmo valor" e não conta outro adiamento.
- **Os campos controlados pelo servidor ficam fora do pedido.** `id`, `completed`, `completed_at`, `postponements` e `created_at` não são enviados e não mudam. O HTTP permite isso: o PUT substitui o que o cliente pode definir.
- **O `PATCH /task-types/{id}` continua como está.** Ele muda só uma parte do tipo (o nome), então PATCH é o método certo ali. A diferença entre as duas rotas é proposital.

Até a 5.9, o PUT ainda não substitui a data. É um estado temporário, porque essa etapa deixa a data de fora.

## O que muda

### 1. `backend/app/routers/tasks.py`

**Tipos reaproveitáveis.** As regras de título, notas e cor saem de dentro de `TaskInput` e viram `TaskTitle`, `TaskNotes` e `TaskColor`, no mesmo estilo do `TaskId`. Assim, cada regra fica escrita uma vez só.

**Nova classe `TaskUpdate`, com a parte comum.** Ela exige todos os campos e herda de `SQLModel`:

```python
class TaskUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle
    notes: TaskNotes | None        # obrigatório, mas pode ser null
    difficulty: Difficulty
    color: TaskColor
    task_type_id: int | None       # obrigatório, mas pode ser null

    # o validador empty_notes_become_none vem para cá
```

**`TaskInput` passa a herdar de `TaskUpdate`.** Ela só acrescenta a data e os valores padrão da criação:

```python
class TaskInput(TaskUpdate):
    due_date: date
    notes: TaskNotes | None = None
    color: TaskColor = DEFAULT_TASK_COLOR
    task_type_id: int | None = None
```

Conceito novo: **`int | None` sem `= None` é obrigatório, mas aceita nulo.** O campo precisa vir no pedido, mesmo que seja como `null`. Esquecer o campo dá 422; mandar `null` remove as notas ou o tipo de propósito. Testei esse comportamento com o SQLModel instalado, e ele também vale para a herança: `TaskUpdate` exige os 5 campos e `TaskInput` continua exigindo só título, dificuldade e data. Nos dois casos, as notas vazias viram nulo e a cor vira maiúscula.

**Nova função `get_task_or_404`.** Agora são duas rotas que buscam a tarefa pelo id, então uso o mesmo padrão de `get_task_type_or_404`. O `delete_task` passa a chamar essa função, sem mudar de comportamento.

**Nova rota:**

```python
@router.put(
    "/{task_id}",
    responses={
        404: {"description": "Tarefa não encontrada."},
        409: {"description": "A tarefa concluída não pode mudar de dificuldade."},
    },
)
def update_task(task_id: TaskId, task_update: TaskUpdate, session: SessionDep) -> Task:
    task = get_task_or_404(session, task_id)

    if task_update.task_type_id is not None:
        ensure_task_type_exists(session, task_update.task_type_id)

    if task.completed and task_update.difficulty != task.difficulty:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Desmarque a tarefa antes de mudar a dificuldade."
        )

    task.title = task_update.title
    task.notes = task_update.notes
    task.difficulty = task_update.difficulty
    task.color = task_update.color
    task.task_type_id = task_update.task_type_id
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
```

A tarefa só é alterada depois de todas as conferências, então um pedido recusado não grava nada.

### 2. `backend/tests/test_tasks.py`

Dois auxiliares novos:

- `update_data(**changes)` monta um pedido completo.
- `assert_update_refused(...)` confere o código da recusa e compara o registro no banco antes e depois.

| Assunto | Casos testados |
| --- | --- |
| Edição | Os 5 campos mudam na resposta e no banco; a listagem do dia mostra o novo valor |
| O que não pode mudar | `due_date`, `completed`, `completed_at`, `postponements` e `created_at` continuam iguais |
| Campo ausente | Faltar qualquer um dos 5 campos dá 422 (esta é a sua decisão 1) |
| `null` de propósito | `notes` e `task_type_id` nulos removem o valor |
| Título, notas e cor | Um caso aceito e um recusado por regra, incluindo os limites de 100 e 1.000 caracteres e a cor em maiúsculas |
| Dificuldade | Valor inválido dá 422; tarefa pendente pode mudar |
| Tipo | Inexistente ou fora do intervalo dá 422 com a mesma mensagem |
| Campo desconhecido | `due_date`, `completed`, `postponements` e outros dão 422 |
| Tarefa concluída | Aceita título, notas, cor e tipo; mudar a dificuldade dá 409; mandar a mesma dificuldade passa |
| Tarefa atrasada ou travada | Aceita editar o título |
| Ordem das recusas | Concluída, com dificuldade nova e tipo inexistente, dá 422 |
| Id da rota | Id desconhecido dá 404; `0`, `-1`, `2147483648` e `10**30` dão 422 |

Os testes de criação existentes não mudam. Eles protegem a troca de `TaskInput` para herança.

### 3. `docs/especificacao.md`

Registro as decisões, como nas etapas anteriores:

- **Etapa 5.8:** a entrega passa a citar `PUT /tasks/{task_id}`, e os arquivos passam a incluir a especificação. O "A decidir" vira "Decisão": todos os campos são exigidos e a edição usa PUT.
- **Etapa 5.9:** a entrega passa a dizer que `due_date` entra como campo obrigatório. O "A decidir" sobre 422 e 409 vira "Decisão", conforme o ponto abaixo.

## Decisões para você conferir

1. **O 422 vem antes do 409 já nesta etapa.** A especificação deixa essa escolha para a 5.9, mas ela já aparece aqui: uma tarefa concluída pode receber dificuldade nova e tipo inexistente no mesmo pedido. Sigo a recomendação da própria especificação (dado primeiro, estado depois) e a registro desde já.
2. **`due_date` no pedido dá 422 nesta etapa.** Isso sai sozinho do `extra="forbid"`. Na 5.9, o campo passa a ser aceito e obrigatório, e o teste correspondente muda.

## Fora desta etapa

Mudar a data e aplicar a trava (5.9), concluir e desmarcar (tarefa 6) e a rota do Adiar (tarefa 7).

## Como testar

Dentro da pasta `backend`, com o ambiente virtual ativado:

```powershell
pytest tests/test_tasks.py
pytest
uvicorn app.main:app --reload
```

Depois, em `http://localhost:8000/docs`:

1. Com `POST /tasks`, crie uma tarefa para hoje e anote o `id`.
2. Com `PUT /tasks/{task_id}`, envie o corpo abaixo. A resposta deve ser 200, com a cor em maiúsculas:
   ```json
   {"title": "Título novo", "notes": "Minha nota", "difficulty": "hard", "color": "#ff0000", "task_type_id": null}
   ```
3. Com `GET /tasks/day/{day}`, confira os novos valores e veja que a data continua a mesma.
4. Repita o `PUT` sem `notes`: deve dar 422. Confira na listagem que a nota continua lá.
5. Repita o `PUT` acrescentando `"due_date": "2030-01-01"`: deve dar 422.

O 409 da tarefa concluída só aparece nos testes, porque concluir pela API só chega na tarefa 6.

**Pronto quando:** todos os testes passam (hoje são 232, mais os novos) e os passos acima dão o resultado descrito.
