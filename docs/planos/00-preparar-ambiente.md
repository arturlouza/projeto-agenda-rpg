# Plano: Tarefa 0 (preparar o ambiente)

## Contexto

A tarefa 0 fica pronta quando o repositório no GitHub tiver os arquivos iniciais. Ele já existe e está vazio. Hoje a pasta local só tem `CLAUDE.md` e `docs/especificacao.md`, sem git nem ambiente virtual. Eu preparo tudo localmente; o commit e o push ficam com você.

Já conferi: Python 3.14.7, Git 2.56, branch padrão `main` e uma chave SSH (`id_ed25519.pub`).

## O que vou fazer

1. **Criar o repositório local:** `git init`, para o Git começar a controlar a pasta.
2. **Ligar ao GitHub:** `git remote add origin git@github.com:arturlouza/projeto-agenda-rpg.git`. Isso só guarda o endereço e não envia nada.
3. **Criar o `.gitignore` na raiz**, para o Git ignorar o que não deve ir para o repositório:
   - `.venv/`: o ambiente virtual, que pode ser recriado e é grande.
   - `__pycache__/` e `*.pyc`: arquivos que o Python gera sozinho.
   - `.pytest_cache/`: cache do pytest.
   - `*.db`: o banco SQLite local (tarefa 3), para seus dados não irem para o GitHub.
   - `.env`: onde a senha da tarefa 15 poderá ficar, para nunca ser publicada.
4. **Criar o `backend/requirements.txt`** só com o que a stack do `CLAUDE.md` pede: `fastapi`, `sqlmodel`, `uvicorn` e `pytest`.
5. **Criar o ambiente virtual e instalar:** `python -m venv .venv` na raiz e `pip install -r backend/requirements.txt`, usando o Python de dentro do `.venv`.
6. **Fixar as versões:** troco cada nome no `requirements.txt` pela versão que foi instalada (por exemplo, `pacote==1.2.3`). Assim, a instalação no futuro usa as mesmas versões principais.
7. **Criar o `README.md` na raiz** (pedido seu, porque o repositório é público e faz parte do seu portfólio), curto e em português: o nome do projeto, duas ou três linhas sobre o que o app é e a stack usada.

## O que não vou fazer

- **Commit e push:** ficam com você, e não vou sugerir a mensagem.
- **Código e outras pastas do app:** `app/`, `tests/` e `frontend/` ficam para as próximas tarefas. O código começa na tarefa 1.
- **`CLAUDE.md` e `docs/especificacao.md`:** já estão prontos e ficam como estão.

## Antes do seu commit

O seu `git config` global usa o e-mail `arturlouza.dev@gmail.com`. Ele vai aparecer como autor dos commits. Confira se esse e-mail está cadastrado na sua conta do GitHub, porque, se não estiver, os commits não ficam ligados ao seu perfil. Não vou mudar essa configuração.

Como o repositório é público, esse e-mail fica visível no histórico dos commits, e `CLAUDE.md` e `docs/especificacao.md` também ficam abertos para qualquer pessoa ler.

## Como você confere

Na raiz do projeto, no PowerShell:

```powershell
# ativar o ambiente virtual
.venv\Scripts\Activate.ps1

# conferir o Python e as bibliotecas instaladas
python --version
pip list

# conferir o endereço do GitHub
git remote -v

# ver o que entrará no commit: .venv NÃO pode aparecer
git status

# testar a chave SSH: deve aparecer "Hi arturlouza!"
ssh -T git@github.com
```

Se o PowerShell bloquear a ativação do ambiente virtual, me avise antes de mudar qualquer configuração de segurança.

Depois, o envio é seu:

```powershell
git add .
git status
git commit
git push -u origin main
```

A tarefa termina quando o GitHub mostrar `.gitignore`, `README.md`, `CLAUDE.md`, `docs/especificacao.md` e `backend/requirements.txt`, sem `.venv`.
