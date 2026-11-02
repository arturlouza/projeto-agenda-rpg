# Plano: Tarefa 3, banco SQLite e modelos

## Contexto

As próximas tarefas (API de tipos, tarefas e XP) precisam de um lugar para guardar dados. Esta tarefa cria o banco e as três tabelas da seção 6.1. **Pronto quando:** o banco é criado ao iniciar o app.

Não entra aqui: rotas da API, `get_session` (primeiro uso é na tarefa 4), validação de dados (tarefas 4 e 5) e variável de ambiente para o endereço do banco (tarefa 16).

## O que muda

### 1. `backend/app/models.py` (novo)

Constante `DEFAULT_TASK_COLOR = "#F5E6C8"` no topo, uma função `utc_now()` e as três tabelas:

| Tabela | Campos |
| --- | --- |
| `TaskType` | `id`, `name` |
| `Task` | `id`, `title`, `notes` (opcional), `due_date`, `difficulty`, `color` (padrão pergaminho), `task_type_id` (opcional, chave estrangeira), `completed` (padrão falso), `completed_at` (opcional), `postponements` (padrão 0), `created_at` |
| `XpEntry` | `id`, `amount`, `reason`, `task_id` (opcional, chave estrangeira), `created_at` |

Decisões:
- `difficulty` é texto simples (`str`), igual às chaves de `TASK_BASE_XP` em `rules/xp.py`.
- Sem `Relationship`: nenhuma tarefa da V1 precisa disso ainda, e `task_type_id` e `task_id` bastam.
- `created_at` e `completed_at` são gravados em UTC, o horário que continua igual quando o servidor muda.

### 2. `backend/app/database.py` (novo)

- `DATABASE_URL = "sqlite:///./agenda.db"`: cria `backend/agenda.db`, já coberto pelo `*.db` do `.gitignore`.
- `engine = create_engine(DATABASE_URL)`: só configura a conexão, o arquivo ainda não é criado.
- `create_db_and_tables()`: chama `SQLModel.metadata.create_all(engine)`.
- `enable_sqlite_foreign_keys()`: roda a cada nova conexão, com `@event.listens_for(Engine, "connect")`, e executa `PRAGMA foreign_keys=ON`. Segue o código da documentação do SQLAlchemy, incluindo o ajuste temporário de `autocommit`, e acrescenta um `if isinstance(dbapi_connection, sqlite3.Connection)` para aplicar só no SQLite. `sqlite3` já vem com o Python, então não é dependência nova.
- `from app import models`: precisa existir, senão o SQLModel não conhece as tabelas e cria um banco vazio.
- Sem `check_same_thread`: o SQLAlchemy já cuida disso em bancos SQLite de arquivo (`sqlite/pysqlite.py`, linha 824). Esse parâmetro só existe no SQLite, então deixá-lo de fora mantém a troca para PostgreSQL só na configuração.

### 3. `backend/app/main.py` (alterado)

Adicionar uma função `lifespan` (código que roda ao ligar o app) que chama `create_db_and_tables()`, e passar `FastAPI(lifespan=lifespan)`. A rota `/health` não muda. Vou explicar os conceitos novos: decorator, `async` e `yield`.

### 4. `backend/tests/test_database.py` (novo)

Usa um banco em arquivo na pasta temporária do pytest (`tmp_path`), para nunca tocar no `agenda.db` real:
- Ao iniciar o app, as tabelas `task`, `tasktype` e `xpentry` existem. Este teste cobre o critério de pronto e também pega o erro de esquecer o `from app import models`.
- Uma `Task` criada só com os campos obrigatórios recebe os padrões certos, incluindo a cor `#F5E6C8`.
- Um `XpEntry` com valor negativo e ligado a uma tarefa é salvo e lido corretamente.
- Uma `Task` com `task_type_id=999`, que não existe, é recusada com `IntegrityError`.

O teste de início precisa de `with TestClient(app)`, porque sem o `with` o `lifespan` não roda. Por isso o `test_health.py` atual segue sem criar banco. Banco em memória não serve aqui, porque o `lifespan` roda em outra thread e as tabelas não aparecem na thread do teste (testado).

### 5. `docs/especificacao.md` (alterado)

- **Seção 6.1:** trocar `color (cor em hexadecimal, com um padrão)` por `color (cor em hexadecimal, padrão #F5E6C8)`.
- **Seção 6.3:** acrescentar que a moldura dourada usa um tom de ouro mais escuro, para manter o contraste com o fundo pergaminho padrão.

### 6. `CLAUDE.md` (alterado)

- **"Como trabalhar comigo":** acrescentar a regra 11, com o texto exato que você passou ("Regras não podem prejudicar o projeto...").
- **Nova seção "Exceções aprovadas":** registrar que `PRAGMA foreign_keys=ON` é a única exceção à regra de SQL escrito à mão. Motivo: o SQLite não confere chaves estrangeiras por padrão e o PostgreSQL confere, então sem isso o desenvolvimento se comportaria diferente da produção. O comando só roda no SQLite.

## Limitações que ficam para as próximas tarefas

Testei estes pontos num banco temporário, com as versões instaladas:

1. **Os modelos não validam nada sozinhos.** O banco aceitou `difficulty="banana"` e `postponements=99`. Quem vai barrar isso é a API, nas tarefas 4 e 5, e o limite de adiamentos fica na tarefa 7.
2. **Com a checagem ligada, excluir algo que está em uso dá erro.** Com o `PRAGMA`, `task_type_id=999` foi recusado e excluir um tipo usado por uma tarefa também. As exclusões das tarefas 4 e 5 precisam tratar esse caso no código. O ajuste só foi testado no SQLite, porque ainda não há PostgreSQL neste projeto; o comportamento em produção só poderá ser conferido na tarefa 16.
3. **A especificação não diz o que acontece com o histórico de XP ao excluir uma tarefa, nem com as tarefas ao excluir um tipo.** Vou perguntar isso nas tarefas 4 e 5, antes de escrever as exclusões.
4. **`create_all` só cria o que falta; não altera tabelas que já existem.** Se um modelo mudar depois, será preciso apagar o `agenda.db` de desenvolvimento.
5. **O dia de atraso precisa usar a sua data local, não a data em UTC.** À noite, a data em UTC já pode ser a de amanhã. Isso entra nas tarefas 6 e 7.

## Como verificar

Vou rodar o `pytest` ao terminar. Depois você confere no PowerShell, na pasta `backend`, com o ambiente virtual ativo:

```powershell
pytest
Test-Path agenda.db                # False: os testes não criam o banco real
uvicorn app.main:app --reload      # deixe rodando e abra outro terminal
```

No segundo terminal, também na pasta `backend` e com o ambiente virtual ativo:

```powershell
Test-Path agenda.db                # True: o banco nasceu ao iniciar o app
python -c "from sqlalchemy import inspect; from app.database import engine; print(inspect(engine).get_table_names())"
# esperado: ['task', 'tasktype', 'xpentry']
```

Abra também `http://localhost:8000/health`, que deve continuar respondendo `{"status": "ok"}`.

Nenhum commit será feito por mim, e nenhuma dependência nova entra: `sqlmodel` já está no `requirements.txt`.
