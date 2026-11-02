# Plano: dois ajustes na API dos tipos de tarefa

## Contexto

A verificação geral não encontrou nada quebrado no uso normal, mas achou dois problemas com entradas absurdas:

1. `PATCH` e `DELETE` com `id` a partir de 2^63 respondem 500. Nenhum dado é afetado, mas o erro deveria ser uma resposta controlada, e a tarefa 5 repetiria o problema se copiasse o padrão.
2. O nome do tipo não tem tamanho máximo: a API aceitou 100 mil letras. Você decidiu o limite de 50 caracteres.

Testei as duas soluções em memória. O limite do `id` funciona como descrito abaixo, e o nome de 50 letras com espaços nas pontas é aceito, porque os espaços saem antes da contagem.

## Alterações

**1. `docs/especificacao.md`, seção 6.1, nas regras dos tipos de tarefa.** Novo item depois de "Nome vazio é recusado...":

> - O nome tem no máximo 50 caracteres, contados depois de remover os espaços do começo e do fim.

**2. `backend/app/routers/task_types.py`**

- Constantes no topo: `MAX_TASK_TYPE_NAME_LENGTH = 50` e `MAX_ID = 2_147_483_647`. Esse é o maior valor da coluna `INTEGER` do PostgreSQL, então o limite fica igual nos dois bancos.
- `TaskTypeInput`: acrescenta `max_length=MAX_TASK_TYPE_NAME_LENGTH` ao `StringConstraints`.
- Novo tipo `TaskTypeId = Annotated[int, Path(ge=1, le=MAX_ID)]`, usado no `task_type_id` de `rename_task_type` e `delete_task_type`. Acrescenta `Path` ao import do `fastapi`.

**Mudança de comportamento:** `id` zero ou negativo passa de 404 para 422, porque nunca é um id válido. Um `id` válido que não existe continua dando 404.

**3. `backend/tests/test_task_types.py`**

- Nome com 50 caracteres é aceito ao criar, inclusive com espaços nas pontas.
- Nome com 51 caracteres é recusado (422) ao criar e ao renomear.
- `PATCH` e `DELETE` respondem 422 com `id` igual a `0`, `-1`, `2147483648` e `10 ** 30`.
- `PATCH` e `DELETE` com `id` igual a `2147483647` respondem 404, por ser válido e não existir.

## Fora deste plano

- A API de tarefas (tarefa 5) e o ajuste de `task_xp` com atraso negativo, já registrado para a tarefa 5.
- O nome só com caractere invisível (U+200B), que não vou tratar.
- Dependências novas e commit: os commits continuam sendo seus. A declaração dos erros no `/docs`, ainda sem commit, entra junto no mesmo arquivo.

## Como testar

Na pasta `backend`, com a `.venv` ativa:

```powershell
pytest
uvicorn app.main:app --reload
```

Devem passar todos os testes. Em `http://localhost:8000/docs`, confira:

1. `DELETE /task-types/{task_type_id}` com o id `99999999999` responde 422, não 500.
2. `POST /task-types` com um nome de 51 letras responde 422.
