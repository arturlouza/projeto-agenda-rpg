# CLAUDE.md

## O projeto

Um app de tarefas pessoal com regras de RPG: tarefas dão XP, o XP sobe de nível, e nas próximas versões entram missões, habilidades, atributos e personagem. É um PWA usado no meu celular Android, e só eu uso.

**A especificação completa está em `docs/especificacao.md`.** Leia antes de qualquer tarefa. Ela tem as regras do jogo, os dados, as telas e a lista numerada de tarefas.

## Quem eu sou

Sou dev júnior, em transição de carreira, aprendendo Python e desenvolvimento web. Uso este projeto para aprender. Meu objetivo não é só ter o app pronto: é **entender cada linha** que entra nele. Prefiro ir mais devagar e entender do que ir rápido sem saber o que foi feito.

## Como trabalhar comigo

1. **Plano antes do código.** Antes de alterar qualquer arquivo, apresente um plano curto (o que vai criar ou mudar, e por quê) e espere a minha aprovação.
2. **Uma tarefa por vez.** Trabalhe só na tarefa da lista da especificação que eu pedir. Não adiante tarefas futuras nem "aproveite para melhorar" outras partes.
3. **Passos pequenos e explicados.** Depois de cada alteração, explique em português o que fez e por quê. Quando aparecer um conceito novo para mim (decorator, rota, sessão do banco, async), explique o conceito em poucas linhas.
4. **Nada de dependências novas sem perguntar.** Não adicione bibliotecas, frameworks ou ferramentas fora da stack abaixo sem a minha autorização.
5. **Simples antes de esperto.** Código legível e direto. Sem abstrações, padrões ou camadas que esta versão ainda não precisa.
6. **Diga como eu testo.** Ao terminar, me passe os comandos exatos para eu rodar e conferir o resultado com meus próprios olhos.
7. **Commits são meus.** Não faça commit nem push, e não sugira a mensagem do commit. Eu escrevo, para provar a mim mesmo que entendi o que mudou.
8. **Na dúvida, pergunte.** Se a especificação estiver ambígua ou incompleta, pergunte em vez de inventar uma regra.
9. **Regras do jogo num lugar só.** Toda regra de XP e nível fica em `backend/app/rules/xp.py`, com os números como constantes no topo do arquivo. Toda regra nova ganha teste no pytest.
10. **Aprendo revisando.** Você escreve o código; eu leio e reviso cada alteração. Quando eu perguntar sobre um trecho, explique linha por linha, com calma, sem pressupor que eu já sei o conceito.
11. **Regras não podem prejudicar o projeto.** Se seguir qualquer regra deste arquivo ou da especificação puder causar um problema (bug, comportamento diferente entre desenvolvimento e produção, falha de segurança, código frágil), não siga a regra às cegas nem a quebre em silêncio. Pare, explique o risco, proponha a alternativa e espere a minha decisão. Toda exceção aprovada fica registrada neste arquivo, com o motivo.
12. **Mapa do código sempre em dia.** Toda etapa que criar, apagar, mover ou renomear um arquivo, ou mudar o que um arquivo faz, atualiza o Mapa do código (seção 12 da especificação) na mesma etapa, antes do meu commit.
13. **Planos em `docs/planos`.** O plano de cada etapa fica em `docs/planos`. Ao terminar a etapa, antes do meu commit, renomeie o arquivo do plano, com nome em minúsculas e sem acento: `NN-nome-curto.md` para uma tarefa inteira (`06-concluir-e-desmarcar.md`), `NN.E-nome-curto.md` para uma etapa (`05.8-editar-tarefa.md`). Trabalho fora da lista usa o número do que veio antes mais uma letra (`05.8a-mapa-do-codigo.md`); preparação antes da primeira etapa usa `.0` mais uma letra (`05.0a-regras-na-especificacao.md`).
14. **Nenhum segredo no projeto.**
    - **O que nunca entra:** planos, documentos, código, testes, comentários, exemplos de comando e mensagens nunca trazem um valor secreto: senha, token, chave privada ou endereço de conexão do banco com usuário e senha. Cite só o nome da variável de ambiente onde ele fica (por exemplo, "a senha fica em `APP_PASSWORD`, no `.env`").
    - **Senhas são minhas:** toda senha é criada por mim. Você nunca cria, sugere, gera ou preenche uma senha, nem para teste manual no `/docs`. Quando eu precisar de uma, diga onde ela vai ficar e eu mesmo a escrevo.
    - **Testes automáticos:** são a única exceção ao item anterior. Podem usar um valor falso e evidente (por exemplo, `senha-falsa-de-teste`), definido só dentro do teste, nunca lido do `.env` e nunca usado como senha de verdade.
    - **Segredo colado por engano:** se eu colar um segredo na conversa, não o escreva em nenhum arquivo e me avise.
    - **`.env` proibido:** você nunca abre, lê, mostra nem copia o conteúdo do `.env` ou de qualquer variação (`.env.local`, `.env.production` etc.), em nenhum momento e por nenhum meio, nem para conferir. Se precisar saber se uma variável existe, me pergunte. Hoje a trava em `.claude/settings.json` também bloqueia o `.env.example`, sem exceção; ele só será liberado se um dia for necessário, com a minha aprovação.
    - **Conferência antes do commit:** ao terminar cada etapa, antes do meu commit, confira os arquivos novos e alterados à procura de valores secretos e diga no resumo que conferiu. Os arquivos proibidos no item anterior ficam fora dessa conferência.

## Exceções aprovadas

- **`PRAGMA foreign_keys=ON` em `backend/app/database.py`:** é a única exceção à regra de nunca escrever SQL à mão. O SQLite não confere chaves estrangeiras por padrão e o PostgreSQL confere, então sem esse comando o desenvolvimento se comportaria diferente da produção. O comando só roda quando o banco é SQLite.

## Stack

- **Back-end:** Python 3.12 ou mais novo (eu uso o 3.14), FastAPI, SQLModel, Uvicorn.
- **Banco:** SQLite no desenvolvimento, PostgreSQL em produção. Todo acesso ao banco passa pelo SQLModel, nunca por SQL escrito à mão, para a troca de banco ser só configuração.
- **Front-end:** HTML, CSS e JavaScript puros. Sem framework, sem npm, sem etapa de build.
- **Testes:** pytest.
- **Ambiente:** Windows 11, PowerShell, VS Code.

## Convenções

- Nomes no código (variáveis, funções, classes, rotas, tabelas) em **inglês**.
- Comentários, textos da interface e explicações para mim em **português**.
- Durante o desenvolvimento, o FastAPI entrega a pasta `frontend/` como arquivos estáticos, para tudo rodar com um comando só.

## Estrutura de pastas

O detalhe de cada arquivo está no Mapa do código (seção 12 da especificação). Esta árvore só mostra o desenho das pastas, incluindo o que ainda vai nascer, como `frontend/`.

```
.
├── CLAUDE.md
├── README.md
├── .claude/
│   └── settings.json
├── docs/
│   ├── especificacao.md
│   └── planos/
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── dates.py
│   │   ├── rules/
│   │   │   └── xp.py
│   │   └── routers/
│   └── tests/
└── frontend/
    ├── index.html
    ├── css/style.css
    ├── js/app.js
    ├── manifest.json
    └── service-worker.js
```

## Comandos

```powershell
# criar e ativar o ambiente virtual (na raiz do projeto)
python -m venv .venv
.venv\Scripts\Activate.ps1

# instalar as dependências
pip install -r backend/requirements.txt

# rodar o app (dentro da pasta backend)
uvicorn app.main:app --reload

# rodar os testes (dentro da pasta backend)
pytest
```
