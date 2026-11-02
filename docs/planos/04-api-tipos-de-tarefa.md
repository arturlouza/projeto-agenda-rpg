> Texto recuperado em 02/11/2026 da conversa gravada, porque o arquivo original foi sobrescrito na mesma sessão.

# Plano: Tarefa 4 (API dos tipos de tarefa) e ajustes na especificação

## Contexto

A tarefa 4 cria a API para criar, listar, renomear e excluir tipos de tarefa, e fica pronta quando funcionar pelo `/docs`. Suas duas decisões (exclusão e nome) vão para a especificação. A seção 6.2 também ganha a regra das notas, sem nenhum código agora.

## O que testei antes de planejar

Testei em memória, sem alterar nenhum arquivo. Os 39 testes atuais passam.

| Teste | Resultado | Consequência |
| --- | --- | --- |
| Excluir um tipo em uso, sem mais nada | `IntegrityError` (a chave estrangeira recusa) | A rota precisa soltar as tarefas antes de excluir |
| `lower()` do SQLite com `MÚSICA` | Continua `MÚSICA`, só troca letras sem acento | **Comparar no SQL deixaria passar `MÚSICA` e `música`**, e o PostgreSQL pode se comportar diferente. A comparação fica no Python |
| `TaskType(name="")` | Aceito: modelos com `table=True` não validam | É preciso uma classe separada para validar a entrada |

## Rotas

| Método e rota | Sucesso | Erros |
| --- | --- | --- |
| `POST /task-types` | 201 | 422 nome vazio, 409 nome repetido |
| `GET /task-types` | 200, por ordem de criação | |
| `PATCH /task-types/{id}` | 200 | 404, 422, 409 |
| `DELETE /task-types/{id}` | 204 | 404 |

## Arquivos

**1. `docs/especificacao.md`**

Na seção 6.1, depois da frase sobre nível e XP:

> **Regras dos tipos de tarefa:**
> - Não pode haver dois tipos com o mesmo nome, ignorando maiúsculas e minúsculas: "Leitura" e "LEITURA" são o mesmo nome. Acentos contam: "Música" e "Musica" são nomes diferentes.
> - Nome vazio é recusado. Espaços no começo e no fim são removidos, então um nome só com espaços também conta como vazio.
> - Ao excluir um tipo usado por tarefas, as tarefas ficam sem tipo; nenhuma tarefa é apagada.

As frases sobre acentos e espaços foram aprovadas por você.

Na seção 6.2:

- No fim do item **Dia**: `As tarefas concluídas vão para uma seção "Concluídas" no fim do dia, que pode ser aberta e fechada.`
- No fim do item **Semana**: `As tarefas concluídas continuam no seu dia.`
- Novos itens depois de **Semana**:

> - **Notas no dia e na semana:** tarefas que têm notas mostram um ícone.
> - **Toque na tarefa:** tocar na tarefa expande o cartão, mostrando as notas (se houver) e os botões Editar e Adiar; tocar de novo recolhe. Numa tarefa sem notas, o toque expande do mesmo jeito, mostrando só os botões. Concluir é pela caixinha de marcar, separada do toque.

- No fim do item **Criar/editar tarefa**: `Excluir fica dentro da tela de edição e sempre pede confirmação antes de apagar.`

Na seção 6.3, novo item depois do item sobre a dificuldade:

> - **Tarefa concluída:** fica com a caixinha marcada, o título riscado e o cartão mais transparente, e mostra o XP que rendeu (por exemplo "+25 XP"). Ao concluir, um "+XP" aparece e some numa animação curta.

Tudo isso é só texto na especificação: nenhum código de tela agora.

**2. `backend/app/database.py`**

Acrescenta `get_session()`, que abre uma sessão por pedido e a fecha no final. A criação do `engine` não muda, porque o SQLAlchemy já libera o uso entre threads em banco SQLite de arquivo.

**3. `backend/app/routers/task_types.py` (novo)**

- `TaskTypeInput`: classe sem `table=True` que recebe o nome, remove os espaços das pontas e recusa nome vazio (`StringConstraints`, do Pydantic, que já vem com o FastAPI).
- `name_is_taken(session, name, ignored_id=None)`: busca os tipos e compara os nomes com `casefold()` no Python. O `ignored_id` permite renomear `leitura` para `Leitura` sem o tipo colidir consigo mesmo.
- As quatro rotas. A exclusão faz tudo numa única transação:
  1. Busca as tarefas do tipo e põe `task_type_id = None`.
  2. Chama `session.flush()`, que envia essa mudança ao banco antes da exclusão. O teste passou sem o `flush`, mas aí a ordem fica a critério do SQLAlchemy.
  3. Exclui o tipo e faz o `commit`.

**4. `backend/app/main.py`**

Registra o router com `include_router`.

**5. `backend/tests/test_task_types.py` (novo)**

Usa um banco na pasta temporária do pytest, ligado por `app.dependency_overrides`, sem tocar no `agenda.db`. Os testes cobrem:
- criar e listar, incluindo a ordem;
- remoção dos espaços das pontas;
- nome vazio e só com espaços, ao criar e ao renomear (422);
- nome repetido com outra caixa, incluindo `MÚSICA` e `música` (409);
- `Música` e `Musica` podem coexistir;
- renomear: caso normal, só mudando a caixa do próprio nome, para o nome de outro tipo (409) e id inexistente (404);
- excluir: tipo sem uso, id inexistente (404) e tipo em uso (a tarefa continua existindo, com `task_type_id` igual a `None`).

## Decisões suas

**Nome repetido em dois pedidos simultâneos:** limite aceito por enquanto. A checagem fica no Python, sem coluna nova, e o `agenda.db` não muda.

## Fora deste plano

Sem dependências novas, sem mudança em `models.py` e sem commit. Também não mexo na API de tarefas nem no front-end.

## Como testar (PowerShell, na pasta `backend`, com a `.venv` ativa)

```powershell
pytest
uvicorn app.main:app --reload
```

Abra `http://localhost:8000/docs` e confira:

1. `POST /task-types` com `{"name": "Leitura"}` responde 201.
2. `POST` com `{"name": "LEITURA"}` responde 409.
3. `POST` com `{"name": "   "}` responde 422.
4. `GET /task-types` lista um tipo só.
5. `PATCH` com `{"name": "Estudo"}` responde 200.
6. `DELETE` responde 204, e o `GET` volta a lista vazia.

A exclusão de um tipo em uso só é conferida pelo pytest, porque a API de tarefas só chega na tarefa 5.
