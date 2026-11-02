# Especificação do App — Agenda RPG

> Nome provisório. O nome definitivo fica para depois (sem usar "D&D" ou "Dungeons & Dragons", que são marcas registradas).

## 1. Visão geral

Um app de tarefas simples como o Google Tarefas, mas com cara e regras de RPG. Você escreve livremente o que tem que fazer, escolhe a dificuldade e acompanha tudo **no dia e na semana**. Cumprir tarefas dá XP, o XP sobe o seu nível (1 a 100 em 1 a 3 anos) e, nas versões seguintes, tarefas passam a fazer parte de missões, sobem habilidades e atributos, e você tem um personagem com raça, classe, foto e história.

Princípios que valem para tudo:

- **Simples de usar.** Um adolescente de 14 anos tem que entender sem manual.
- **Um único usuário.** O app é só para mim; não há cadastro nem login de várias pessoas.
- **Tudo bem separado.** O app é construído em versões, e cada versão já funciona sozinha.

## 2. Arquitetura (Bloco 1, fechado)

| Camada | Escolha |
| --- | --- |
| Plataforma | PWA (app web instalável), usado no celular Android |
| Front-end | HTML, CSS e JavaScript puros, sem framework |
| Back-end | Python com FastAPI |
| Banco de dados | SQLite no desenvolvimento, PostgreSQL em produção |
| Acesso ao banco | SQLModel (o mesmo código funciona nos dois bancos) |
| Testes | pytest |
| Hospedagem | Front e back-end no mesmo serviço gratuito, escolhido na hora de publicar. Critério obrigatório: um banco gratuito que não expira. Os outros critérios estão na tarefa 17 |

O próprio FastAPI entrega os arquivos do front-end, no desenvolvimento e em produção. No computador, tudo roda com um único comando. Na publicação, front e API ficam no mesmo endereço, o que dispensa CORS e permite guardar o token num cookie protegido (seção 6.7).

A partir da tarefa 16, a URL do banco vem da variável de ambiente `DATABASE_URL`. Em desenvolvimento (`APP_ENV=development`), sem a variável, vale o SQLite local. Fora do desenvolvimento, ela é obrigatória, e o app recusa subir sem ela (seção 6.7).

**Atenção:** como não há contas de usuário, antes de publicar o back-end na internet ele precisa de uma proteção simples: uma senha única guardada em variável de ambiente, trocada por um token no login. Sem isso, qualquer pessoa com o endereço mexeria nos dados. As regras estão na seção 6.7.

## 3. Conceitos do jogo

| Conceito | O que é |
| --- | --- |
| **Tarefa** | Algo a fazer num dia. Tem título, data, dificuldade, cor e, opcionalmente, tipo, missão e habilidade. |
| **Tipo de tarefa** | Etiqueta simples, criada livremente, que diz *o que* a tarefa é: Leitura, Treino, Estudo. Corrida e musculação são tarefas diferentes do mesmo tipo, Treino. |
| **Missão** | Objetivo grande, formado por tarefas. Avança de 0 a 100% e **sempre tem fim**. |
| **Dificuldade** | Tarefas: fácil, médio, difícil. Missões: fácil, médio, difícil, extremo, semideus, deus. |
| **XP** | Pontos ganhos ao concluir tarefas e missões e ao manter sequências. |
| **Nível** | Calculado a partir do XP total. Vai de 1 a 100 e continua depois do 100. |
| **Habilidade** | O que você treina de forma específica (História, Natação, Oratória). Vem de um **catálogo fixo**, não é criada pelo usuário. Uso opcional. |
| **Atributo** | Os seis atributos clássicos: Força, Destreza, Constituição, Inteligência, Sabedoria e Carisma. Cada habilidade pertence a um atributo. |
| **Personagem** | Nome, raça, classe, foto e história. Puramente diversão: não dá bônus. |

Exemplo do fluxo completo: a tarefa "Ler 30 páginas" é do tipo **Leitura**; o livro é de história, então a habilidade marcada é **História**, que pertence a **Inteligência**. Concluir a tarefa dá XP para o nível, para História e para Inteligência.

## 4. Regras de XP e nível

Todos os números ficam como constantes no topo de `backend/app/rules/xp.py`, para poderem ser ajustados num lugar só.

### 4.1 XP por tarefa

| Dificuldade | XP |
| --- | --- |
| Fácil | 10 |
| Médio | 25 |
| Difícil | 50 |

### 4.2 Atraso e adiamento

- Concluir no dia marcado vale 100% do XP.
- Concluir antes do dia marcado também vale 100%: os dias de atraso nunca são negativos. A função `task_xp`, em `backend/app/rules/xp.py`, trata atraso negativo como 0, com teste na tarefa 5.
- Cada adiamento tira 25%: 1 adiamento vale 75%, 2 valem 50% e 3 valem 25%.
- Um adiamento acontece de duas formas: quando você muda a data da tarefa para depois, ou quando o dia passa sem ela ser concluída (cada dia de atraso conta como um adiamento).
- Mudar a data de uma tarefa pendente para depois conta como 1 adiamento, seja pelo botão "Adiar", seja pela edição, para qualquer data nova. Antecipar não conta.
- Ao adiar uma tarefa atrasada, os dias de atraso acumulados até aquele momento são somados ao contador de adiamentos e não se perdem. Exemplo: com 0 adiamentos e 2 dias de atraso, adiar deixa o contador em `0 + 2 + 1 = 3`.
- **Com 3 ou mais adiamentos efetivos, a data trava:** não pode mais ser mudada por nenhum caminho, nem pelo botão "Adiar", nem pela edição, nem para antecipar. A tarefa só sai da lista se for concluída ou excluída.
- A tarefa travada vale 25% com exatamente 3 adiamentos efetivos e **perde o XP** com mais de 3: ainda dá para concluí-la, mas ela vale 0.
- A tarefa travada só aparece nas atrasadas se estiver mesmo atrasada. Com 3 adiamentos manuais e data futura, ela fica no dia marcado.
- A trava usa a mesma conta do XP, com os dias de atraso nunca negativos. Sem isso, 3 adiamentos e uma data 5 dias à frente dariam `3 − 5 = −2` e destravariam a data.
- O resultado é sempre arredondado para baixo, para um número inteiro, como no D&D. Exemplo: 25 × 75% = 18,75 vira 18.

Em código: `adiamentos_efetivos = adiamentos_manuais + dias_de_atraso`. Se for maior que 3, o XP é 0; senão, `XP = arredondar_para_baixo(XP_base × (1 − 0,25 × adiamentos_efetivos))`.

### 4.3 Desmarcar

Desmarcar uma tarefa concluída devolve exatamente o XP que ela deu. Assim não dá para "farmar" XP marcando e desmarcando.

Excluir uma tarefa concluída mantém no histórico o XP que ela deu. Para remover esse XP, é preciso desmarcar a tarefa antes de excluir. Ao excluir a tarefa, as linhas dela no histórico ficam com `task_id` nulo: a chave estrangeira recusaria a exclusão, e um id solto poderia apontar para outra tarefa quando o SQLite reaproveitasse o número (seção 6.6).

### 4.4 Histórico de XP

O XP nunca é guardado como um número solto. Cada ganho ou perda vira uma linha no histórico (`XpEntry`), com valor, motivo e tarefa de origem. O XP total é a soma do histórico, e o nível é calculado a partir dele. Isso garante que desmarcar devolva o valor certo e permite auditar de onde veio cada ponto.

### 4.5 Fórmula do nível

XP necessário para passar do nível *n* para o *n + 1*:

```
xp_necessario(n) = arredondar(100 + 2 × (n − 1) ^ 1,5)
```

Do nível 100 em diante, a barra **para de crescer**: todo nível depois do 100 custa sempre 2.070 XP.

| Nível | XP para subir |
| --- | --- |
| 1 | 100 |
| 10 | 154 |
| 30 | 412 |
| 50 | 786 |
| 75 | 1.373 |
| 99 | 2.040 |
| 100 em diante | 2.070 (fixo) |

O total para chegar ao nível 100 é de cerca de 87 mil XP. A calibragem considera um jogador ativo, com uns 120 XP por dia (por exemplo, 4 tarefas médias mais bônus):

| Ritmo | Chega ao nível 100 em | Nível mais lento leva |
| --- | --- | --- |
| 90 XP/dia | ~2,6 anos | ~23 dias |
| 120 XP/dia | ~2 anos | ~17 dias |
| 160 XP/dia | ~1,5 ano | ~13 dias |

Com 120 XP/dia: nível 10 em cerca de 9 dias, nível 50 em uns 5 meses, nível 75 em cerca de 1 ano. Quem cumpre pouca coisa sobe mais devagar, o que é justo.

### 4.6 Missões (Versão 2)

- Toda missão tem uma meta com fim: ou uma lista de tarefas, ou uma tarefa repetida com número de vezes definido (exemplo: 30 dias de leitura). Missão sem fim não pode ser criada.
- Progresso = tarefas concluídas ÷ total de tarefas da missão, de 0 a 100%.
- As tarefas da missão dão o XP normal delas. Ao chegar a 100%, a missão dá um bônus:

| Dificuldade da missão | Bônus |
| --- | --- |
| Fácil | 100 |
| Médio | 250 |
| Difícil | 500 |
| Extremo | 1.000 |
| Semideus | 2.000 |
| Deus | 4.000 |

### 4.7 Sequências e conquistas (Versão 2)

| Conquista | Bônus |
| --- | --- |
| Dia perfeito: concluir todas as tarefas do dia (mínimo de 3) | +30 |
| 7 dias seguidos com pelo menos 1 tarefa concluída | +100 |
| 30 dias seguidos com pelo menos 1 tarefa concluída | +500 |
| 100 dias seguidos com pelo menos 1 tarefa concluída | +1.500 |
| Marcos de tarefas concluídas: 10, 50, 100, 250, 500, 1.000 | +50, +150, +300, +600, +1.000, +2.000 |

Com missões e sequências ativas, o XP diário médio sobe. Se o ritmo ficar rápido demais, ajusta-se a constante da fórmula, não as regras.

## 5. Versões

| Versão | O que entra |
| --- | --- |
| **V1** | Tarefas com data, dificuldade, cor e tipo; visão do dia e da semana; concluir, desmarcar e adiar; XP, nível e barra de progresso; PWA instalável. |
| **V2** | Missões com progresso; tarefas que se repetem (com contador opcional); bônus de sequência e conquistas. |
| **V3** | Habilidades (catálogo fixo) e atributos, com XP e níveis próprios; tela de ficha. |
| **V4** | Personagem completo (nome, raça, classe, foto, história) e o capricho visual de RPG. |

## 6. Versão 1 em detalhe

### 6.1 Dados

```
TaskType (tipo de tarefa)
  id, name, created_at

Task (tarefa)
  id, title, notes (opcional), due_date (data, obrigatória na V1),
  difficulty ("easy" | "medium" | "hard"),
  color (cor em hexadecimal, padrão #F5E6C8),
  task_type_id (opcional),
  completed (verdadeiro/falso), completed_at (opcional),
  postponements (inteiro, começa em 0, sem teto no modelo), created_at

XpEntry (histórico de XP)
  id, amount (pode ser negativo), reason, task_id (opcional), created_at
```

O nível e o XP do jogador não são tabelas: são calculados a partir do `XpEntry`.

Na prática, a trava da seção 4.2 faz o campo `postponements` parar em 3: a data só muda com até 2 adiamentos efetivos, e a conta nova dá no máximo `2 + 1 = 3`. O que passa de 3 são os adiamentos efetivos (manuais + dias de atraso).

**Ids:** o id de cada registro é só um identificador, não é contagem nem ordem. Nenhum código, teste ou tela pode depender de o id ser sequencial, sem buracos ou nunca reaproveitado (seção 6.6).

**Regras dos tipos de tarefa:**

- Não pode haver dois tipos com o mesmo nome, ignorando maiúsculas e minúsculas: "Leitura" e "LEITURA" são o mesmo nome. Acentos contam: "Música" e "Musica" são nomes diferentes.
- Nome vazio é recusado. Espaços no começo e no fim são removidos, então um nome só com espaços também conta como vazio.
- O nome tem no máximo 50 caracteres, contados depois de remover os espaços do começo e do fim.
- Ao excluir um tipo usado por tarefas, as tarefas ficam sem tipo; nenhuma tarefa é apagada.
- Os tipos são listados pela ordem de criação (`created_at`), com o id só como desempate em caso de empate exato.

**Regras das tarefas:**

Campos:

- **Título:** espaços das pontas removidos; vazio é recusado; no máximo 100 caracteres, contados depois de remover os espaços.
- **Notas:** espaços das pontas removidos; no máximo 1.000 caracteres, contados depois de remover os espaços. Notas vazias ou só com espaços são gravadas como sem notas (nulo).
- **Cor:** hexadecimal no formato `#RRGGBB`, com letras maiúsculas ou minúsculas, sempre gravada em maiúsculas (`#ff0000` vira `#FF0000`). Qualquer outro formato, como `#FFF`, é recusado. Sem cor informada, vale a cor padrão `#F5E6C8`.
- **Dificuldade:** só aceita `easy`, `medium` ou `hard`.
- **Tipo:** um `task_type_id` que não existe é recusado com mensagem clara, verificado antes de gravar, para nunca virar erro 500. Um id fora do intervalo aceito pelo banco é recusado do mesmo jeito.
- **Data:** toda tarefa tem data obrigatória na V1.

Mudanças:

- **Data nova:** quando a data é definida ou alterada, ela não pode ser anterior a hoje, no horário de Brasília. A regra vale só para a data nova: editar outros campos de uma tarefa atrasada continua permitido.
- **Tarefa concluída:** só título, notas, cor e tipo podem ser editados. Dificuldade e data ficam travadas; para mudar, é preciso desmarcar antes.
- **Mesmo valor:** mandar o valor que o campo já tem não é mudança. Como o formulário envia todos os campos, editar o título de uma tarefa atrasada, travada ou concluída não pode ser recusado por causa da data que não mudou.

Recusas:

- **422:** dado inválido, ou seja, os casos da lista de campos, a data nova anterior a hoje e campo desconhecido no pedido.
- **409:** dado válido, mas o estado da tarefa impede: mudar a data de uma tarefa travada (seção 4.2), ou mudar a dificuldade ou a data de uma tarefa concluída.
- O pedido recusado não grava nada.

### 6.2 Telas

- **Topo fixo:** nível atual e barra de XP (quanto falta para o próximo nível).
- **Dia:** lista das tarefas da data escolhida, no estilo Google Tarefas. Na visão de hoje, as tarefas pendentes atrasadas aparecem em destaque no topo. Nas outras datas, uma tarefa pendente aparece no dia marcado. As tarefas concluídas vão para uma seção "Concluídas" no fim do dia, que pode ser aberta e fechada. Toda tarefa concluída aparece em "Concluídas" no dia em que foi concluída, no horário de Brasília, não no dia marcado.
- **Semana:** sete colunas, de segunda a domingo, com as tarefas de cada dia, e setas para navegar entre semanas. É a visão ampla que falta no Google Tarefas. Vale a mesma regra da visão do dia: tarefa pendente aparece no dia marcado; tarefa concluída aparece no dia em que foi concluída, no horário de Brasília.
- **Ordem das listas:** dentro de um dia, as pendentes, as concluídas e as colunas da semana seguem a ordem de criação (`created_at`), com o id só como desempate em caso de empate exato. As atrasadas no topo da visão de hoje seguem a data marcada, da mais antiga para a mais recente; em empate, `created_at` e depois id.
- **Notas no dia e na semana:** tarefas que têm notas mostram um ícone.
- **Toque na tarefa:** tocar na tarefa expande o cartão, mostrando as notas (se houver) e os botões Editar e Adiar; tocar de novo recolhe. Numa tarefa sem notas, o toque expande do mesmo jeito, mostrando só os botões. O cartão expandido de uma tarefa concluída não mostra o botão Adiar, só as notas e o Editar. Numa tarefa travada (seção 4.2), o botão Adiar fica bloqueado. Concluir é pela caixinha de marcar, separada do toque.
- **Criar/editar tarefa:** título, data, dificuldade, cor, tipo e notas. Excluir fica dentro da tela de edição e sempre pede confirmação antes de apagar. Numa tarefa travada, a data fica travada no formulário. Numa tarefa concluída, a dificuldade e a data ficam travadas no formulário.
- **Ao subir de nível:** uma comemoração curta na tela.

### 6.3 Aparência

- A cor escolhida pelo usuário é o **fundo do cartão**.
- A dificuldade aparece na **moldura e num ícone**, sem mexer na cor. Tarefas: fácil com moldura simples, médio com moldura prateada, difícil com moldura dourada, em um tom de ouro mais escuro, para manter o contraste com o fundo pergaminho padrão (#F5E6C8). Missões (V2) seguem a escada bronze, prata, ouro, rubi, brilho roxo (semideus) e um efeito animado discreto (deus).
- **Tarefa concluída:** fica com a caixinha marcada, o título riscado e o cartão mais transparente, e mostra o XP que rendeu (por exemplo "+25 XP"). Ao concluir, um "+XP" aparece e some numa animação curta.
- Regra geral: nada pode confundir a vista. Efeitos sutis, nunca piscando.

### 6.4 Fuso horário

O app segue o horário de Brasília. O fuso fica numa constante única: `APP_TIMEZONE = "America/Sao_Paulo"`.

- Datas e horas (`completed_at`, `created_at`) são gravadas em UTC no banco.
- Tudo que depende de "que dia é" converte para Brasília antes de calcular: o dia de hoje, os dias de atraso, o dia da conclusão e o agrupamento por semana.
- Nunca tirar o dia de uma data e hora em UTC direto com `.date()`: sempre converter para `APP_TIMEZONE` antes.
- O SQLite guarda datas e horas sem fuso. O SQLModel já as devolve como UTC; mesmo assim, qualquer data sem fuso que chegue à função auxiliar é tratada como UTC.
- No PostgreSQL, `completed_at` e `created_at` usam `TIMESTAMP WITH TIME ZONE` (tipo `UTCDateTime` do SQLModel).
- `due_date` é uma data pura, sem hora, e não passa por conversão de fuso.
- Exemplo: uma tarefa concluída às 22h30 de 31/10 em Brasília fica gravada como 01h30 de 01/11 em UTC e conta como concluída em 31/10.

### 6.5 Front-end e PWA

Vale para as tarefas 9 a 14:

- Caminhos relativos em tudo, inclusive no `manifest.json` e no registro do service worker, para o app não depender do endereço onde está publicado.
- O endereço da API fica numa constante única. Como front e API têm a mesma origem, ele é um caminho relativo.
- Todas as chamadas à API passam por uma única função, que na tarefa 15 passa a tratar a resposta 401 mostrando a tela de login. O cookie com o token vai sozinho (seção 6.7).

A V1 precisa de internet:

- O service worker guarda só os arquivos do app, nunca dados da API.
- O cache tem um número de versão que muda a cada publicação, para o celular receber a versão nova.

### 6.6 Diferenças conhecidas entre os bancos

- **Ids:** o SQLite reaproveita ids quando os maiores são excluídos (uma tabela vazia volta ao id 1); o PostgreSQL não. Por isso vale a regra de ids da seção 6.1.
- **Caractere NUL:** o PostgreSQL recusa o caractere NUL (`\u0000`) em texto; o SQLite aceita. A validação que resolve isso é item obrigatório da tarefa 16.

### 6.7 Segurança

Decisões da revisão de segurança (plano `05.8c-revisao-de-seguranca.md`). Valem para as tarefas 9 a 17.

**Publicação só com tudo pronto:** o back-end não vai ao ar antes da tarefa 15 e só fica no ar depois de passar na conferência da tarefa 17. O endereço será público, e a proteção é a senha.

**Senha e acesso:**

- A senha fica só na variável de ambiente `APP_PASSWORD`. Sem ela, ou com menos de 16 caracteres, o app recusa subir. A senha de desenvolvimento nunca é a de produção.
- `POST /auth/login` recebe a senha no corpo e entrega um token aleatório. A senha nunca vai na URL e nunca é guardada pelo app no celular.
- O token fica num cookie `HttpOnly`, `Secure`, `SameSite=Strict`, sem `Domain`, e nunca aparece no corpo da resposta. Esse caminho só é possível porque front e API têm a mesma origem.
- A comparação usa `secrets.compare_digest` sobre bytes.
- O banco guarda só o HMAC do token, calculado com `APP_PASSWORD` como chave, com validade de 90 dias. `POST /auth/logout` encerra o aparelho atual.
- **Emergência (celular perdido, suspeita de invasão):** trocar `APP_PASSWORD` no painel do serviço. Com a chave nova, nenhum token antigo é reconhecido. Não depende de login nem de rota. Nunca voltar a uma senha já usada: os tokens antigos não expirados valeriam de novo.
- 10 erros de login em 15 minutos fazem o login responder 429. O contador é global e fica em memória, então o reinício do serviço o zera. Tokens válidos continuam funcionando.
- Toda rota exige token, menos `/health` e `/auth/login`. Um teste percorre as rotas e garante isso.
- Pedidos acima de 64 KB são recusados, exceto a restauração, que tem limite próprio.

**Conferência de `Origin` (proteção contra CSRF), decidida no plano `05.8d-origin-sem-cabecalho.md`:**

- Todo pedido que não seja `GET`, `HEAD` ou `OPTIONS` (na prática, POST, PUT, PATCH e DELETE) só passa com `Origin` exatamente igual ao endereço do app. Qualquer outro caso recebe 403: cabeçalho ausente, valor `null` ou outro endereço.
- A conferência é global, vale para as rotas futuras e para `/auth/login`, e roda antes do token e antes de ler o corpo. O 403 vem antes do 401, a rota não executa, e o login recusado aqui não conta como tentativa.
- O endereço vem da variável `APP_ORIGIN`, nunca do `Host` nem de `X-Forwarded-*`. O valor traz esquema, domínio e porta, em minúsculas, sem barra no fim, sem caminho e sem a porta padrão. Não é segredo. Fora do desenvolvimento, ele é obrigatório e em `https://`. Sem ele, ou com formato inválido, o app recusa subir.
- Em desenvolvimento, sem a variável, valem `http://localhost:8000` e `http://127.0.0.1:8000`. Com a variável, vale só ela. O teste por USB abre `http://localhost:8000` e não precisa de ajuste.
- As escritas do front-end usam `fetch` com o modo padrão. Nada de `<form>` com POST, outro `mode` ou `sendBeacon`: com `Referrer-Policy: no-referrer`, o navegador manda `Origin: null` nesses casos, e o pedido recebe 403.
- A conferência protege contra outro site usando o seu navegador. Não barra script nem robô, que escrevem o `Origin` que quiserem: contra eles, a proteção é a senha. Comandos manuais, como `curl`, precisam mandar `Origin`.
- Nenhuma rota `GET`, `HEAD` ou `OPTIONS` altera dados, porque a conferência não as cobre. Um teste percorre os `GET` e reprova qualquer instrução além de leitura no banco. Ele não vê escritas em condições que não criou nem efeitos fora do banco, então cada rota nova também é revisada.
- Nenhuma rota usa `include_in_schema=False`: ela sumiria de `app.openapi()`, que é de onde os testes tiram a lista de rotas. Um teste confere.

**Modo de execução:** a variável `APP_ENV` escolhe o modo. Sem ela, vale produção: sem `/docs`, `/redoc` e `/openapi.json`, com senha, `APP_ORIGIN` e `DATABASE_URL` obrigatórias e TLS exigido na conexão com o PostgreSQL. `debug` é sempre falso. `--reload` só no computador.

**Front-end:**

- Dados entram na tela só por `textContent` ou `value`. Nunca por `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` ou `eval`. Um teste confere.
- Nenhum script, estilo ou fonte de outro endereço. A Content-Security-Policy fica ligada desde a tarefa 9.
- O service worker guarda uma lista fechada de arquivos do app e nunca intercepta a API. As respostas da API têm `Cache-Control: no-store`.

**Teste no celular antes da publicação:** pelo cabo USB, com o encaminhamento de porta do Chrome (`chrome://inspect/#devices`), abrindo `http://localhost:8000`. `localhost` é origem segura, então o service worker, a instalação e o cookie `Secure` funcionam. Pelo Wi-Fi, só até a tarefa 15, só em casa, com a rede marcada como privada no Windows, dados de teste e o servidor desligado ao terminar. Depois da tarefa 15, só por USB.

**Banco e backup:**

- A `DATABASE_URL` de produção fica só no painel do serviço, nunca no computador nem em `alembic.ini`. As migrações rodam no serviço.
- Os logs não mostram os valores gravados (`hide_parameters=True`).
- Os testes nunca usam a `DATABASE_URL` do ambiente.
- O backup de verdade é o arquivo exportado. Fica na nuvem pessoal com 2FA e no computador, fora do repositório. Nunca no Git nem em GitHub Actions.
- A restauração só aceita banco vazio, em uma transação, com as mesmas validações das rotas (menos a da data nova).
- Exportar antes de toda migração em produção.

**O app não é cofre:** nada de senhas, dados de cartão ou números de documento em títulos e notas.

**Dependências:** Dependabot ligado no GitHub, todas as versões de produção fixadas, consulta à base OSV antes de publicar e uma vez por mês.

## 7. Versão 2 em detalhe: tarefas repetidas

- Repetição: diária, em dias da semana escolhidos, semanal ou mensal.
- **Contador opcional:** para tarefas numeradas, como um curso de 100 aulas. Você define o total (100) e um título com marcador, por exemplo `Curso de Python: aula {n}`, e o app cria "aula 1", "aula 2" e assim por diante, até a 100.
- Cada repetição é uma tarefa própria, com seu próprio XP e suas próprias regras de atraso.
- Uma tarefa repetida só pode entrar numa missão se tiver fim (número de repetições ou data final).

## 8. Versão 3 em detalhe: habilidades e atributos

- Na tarefa, o campo habilidade é **opcional**. Quem não quiser usar, ignora.
- As habilidades vêm de um catálogo fixo (abaixo). O usuário não cria habilidades.
- Concluir uma tarefa com habilidade soma o XP da tarefa à habilidade e ao atributo dela.
- Proposta de escala para os atributos, inspirada no D&D: todo atributo começa em 10 (a média humana), sobe com o XP das habilidades ligadas a ele, chega a 20 (o limite mortal) e pode ir até 30 (o divino). A curva exata é definida na própria V3.

### Catálogo inicial de habilidades

| Atributo | Habilidade | Nome no jogo |
| --- | --- | --- |
| Força | Musculação | Poder Bruto |
| Força | Artes marciais | Combate |
| Força | Calistenia | Domínio do Corpo |
| Força | Escalada | Escalada |
| Força | Trabalho físico | Labuta |
| Destreza | Dança | Graça |
| Destreza | Instrumento musical | Música |
| Destreza | Desenho e pintura | Artes Visuais |
| Destreza | Esportes com bola ou raquete | Reflexos |
| Destreza | Culinária | Ofício do Cozinheiro |
| Destreza | Trabalhos manuais | Artesanato |
| Constituição | Corrida | Fôlego |
| Constituição | Natação | Nado |
| Constituição | Ciclismo | Estrada |
| Constituição | Caminhada e trilha | Andarilho |
| Constituição | Sono e descanso | Recuperação |
| Constituição | Alimentação saudável | Vitalidade |
| Inteligência | História | História |
| Inteligência | Matemática e física | Cálculo Arcano |
| Inteligência | Química e biologia | Alquimia |
| Inteligência | Medicina e saúde | Cura |
| Inteligência | Direito | Leis do Reino |
| Inteligência | Tecnologia e programação | Arcanismo Tecnológico |
| Inteligência | Idiomas | Línguas |
| Inteligência | Economia e finanças | Tesouraria |
| Sabedoria | Filosofia | Sabedoria Antiga |
| Sabedoria | Meditação | Mente Serena |
| Sabedoria | Psicologia e autoconhecimento | Intuição |
| Sabedoria | Natureza, plantas e animais | Sobrevivência |
| Sabedoria | Espiritualidade e religião | Fé |
| Sabedoria | Organização e planejamento | Estratégia |
| Carisma | Oratória | Voz de Comando |
| Carisma | Escrita | Pena do Escriba |
| Carisma | Relacionamentos e networking | Diplomacia |
| Carisma | Liderança | Liderança |
| Carisma | Teatro e atuação | Enganação |
| Carisma | Canto | Canção |

O catálogo fica no código como dados iniciais e pode ser ajustado antes da V3.

## 9. Versão 4 em detalhe: personagem

- **Nome**, **raça**, **classe**, **foto** e **história** (texto livre).
- Raças: Humano, Elfo, Anão, Halfling, Draconato, Gnomo, Meio-elfo, Meio-orc, Tiefling.
- Classes: Bárbaro, Bardo, Bruxo, Clérigo, Druida, Feiticeiro, Guerreiro, Ladino, Mago, Monge, Paladino, Patrulheiro.
- Esses nomes vêm do SRD 5.1, que tem licença aberta (Creative Commons). O nome do app não pode usar "D&D".
- Foto: uma imagem padrão do app ou uma enviada pelo usuário.
- Raça e classe podem ser trocadas a qualquer momento e não dão bônus.

## 10. Lista de tarefas da Versão 1

Uma tarefa por sessão do Claude Code. Cada uma termina com o app funcionando, testado, revisado por mim e com commit feito por mim.

| # | Tarefa | Pronto quando |
| --- | --- | --- |
| 0 | Preparar o ambiente: repositório no GitHub, ambiente virtual, `requirements.txt`, `.gitignore`, `CLAUDE.md` e esta especificação em `docs/` | O repositório existe no GitHub com esses arquivos |
| 1 | Esqueleto do back-end: FastAPI com a rota `/health` | Abrir `http://localhost:8000/health` responde `{"status": "ok"}` |
| 2 | Regras de XP como funções puras em `rules/xp.py`: XP da tarefa (com adiamentos), XP necessário por nível, nível a partir do XP total | Os testes do pytest passam, incluindo os números da tabela 4.5 |
| 3 | Banco SQLite e modelos `TaskType`, `Task` e `XpEntry` com SQLModel | O banco é criado ao iniciar o app |
| 4 | API dos tipos de tarefa: criar, listar, renomear, excluir | Funciona pela documentação automática do FastAPI (`/docs`) |
| 5 | Primeiro passo: trocar a ordem dos tipos de id para `created_at` (coluna nova em `TaskType`, listagem e comentário em `task_types.py`; apagar o `agenda.db` local uma vez, porque o `create_all` não altera tabela existente). Depois: adicionar `tzdata` ao `requirements.txt` e criar a função auxiliar de datas, com testes (incluindo o caso das 22h30). Também: `task_xp` trata atraso negativo como 0, com teste. Depois, API das tarefas: criar, editar, excluir, listar por dia e por semana, já com as regras de mudança de data da seção 4.2 e as regras das tarefas da seção 6.1, porque a edição precisa delas | Funciona pelo `/docs` e os testes cobrem as regras |
| 6 | Concluir e desmarcar tarefa, gerando e devolvendo XP no histórico | Concluir e desmarcar deixa o XP total igual ao de antes |
| 7 | Rota do botão Adiar, reaproveitando a regra de mudança de data e a trava feitas na tarefa 5 | Os testes cobrem 0, 1, 2, 3 e 4 adiamentos |
| 8 | API do jogador: XP total, nível e progresso da barra | `/player` devolve nível e porcentagem corretos |
| 9 | Front-end base entregue pelo FastAPI, com o topo de nível e barra de XP | A página abre no navegador mostrando o nível real; `/agenda.db` e `/.env` dão 404; a CSP está ligada; um teste recusa `innerHTML` e parecidos |
| 10 | Visão do dia, com atrasadas em destaque | Dá para ver, concluir e desmarcar as tarefas do dia |
| 11 | Formulário de criar e editar tarefa | Dá para criar uma tarefa completa pela tela |
| 12 | Visão da semana em sete colunas, com navegação | Dá para ver a semana inteira e trocar de semana |
| 13 | Aparência: cor no fundo, moldura e ícone por dificuldade, comemoração de nível | Cada dificuldade é reconhecível de longe |
| 14 | PWA: `manifest.json`, ícone e service worker | O Chrome reconhece o app como instalável, com o celular ligado por USB em `localhost`; a API não aparece no cache |
| 15 | Proteção por senha única: login, token em cookie e tela de login (divisão abaixo) | Sem token, a API recusa os pedidos; nada abre sem senha configurada; trocar a senha derruba todos os tokens; pedido de outra origem, sem `Origin` ou com `Origin: null` recebe 403 |
| 16 | Dados reais: migrações com Alembic (dependência nova, autorizada nesta tarefa), URL do banco em variável de ambiente, rota e tela de exportação e restauração a partir do arquivo exportado | As migrações criam um banco novo, e exportar, apagar e restaurar devolve os mesmos dados e o mesmo XP total; fora do desenvolvimento, sem `DATABASE_URL`, o app recusa subir |
| 17 | Publicação: front, back e PostgreSQL num serviço gratuito cujo banco não expira, com o FastAPI entregando o front e sem CORS | O app abre e instala no celular, fora de casa, e passa na conferência da tarefa 17 |

**Divisão da tarefa 5:**

A tarefa 5 é grande demais para uma sessão, então vira 9 etapas, feitas nesta ordem. Cada etapa tem plano próprio, em sessão nova, e só começa depois do commit da anterior. Os caminhos abaixo são relativos a `backend/`, menos o `CLAUDE.md`.

Por que esta ordem: 5.1 vem primeiro porque é a única etapa que muda tabela (o `agenda.db` só é apagado essa vez). 5.2 e 5.3 são a base sem banco, que as rotas usam. Depois vem criar, porque sem tarefas não há o que listar; listar, para ver o resultado; e por último editar, que é a parte com mais regras. A mudança de data fecha a tarefa.

Fatos conferidos ao fazer a divisão, com SQLModel 0.0.48 e 72 testes passando:

- O `tzdata` não estava instalado, e `ZoneInfo("America/Sao_Paulo")` falhava. A etapa 5.2 resolve.
- Um campo `datetime` no modelo já usa `UTCDateTime` e volta em UTC. Falta só o `created_at` do `TaskType`.
- O `UTCDateTime` recusa gravar data sem fuso (dá erro). Testes que gravam `completed_at` direto no banco precisam usar data com fuso.
- Filtrar concluídas por intervalo de horário em UTC funcionou no SQLite, com o caso das 22h30.
- A data `9999-12-31` é aceita, mas somar um dia a ela dá `OverflowError`. Sem cuidado, as listagens responderiam 500.

Até a tarefa 6, a API não conclui tarefa e também recusa data passada. Por isso, tarefas concluídas e atrasadas só aparecem nos testes, inseridas direto no banco. Pelo `/docs` não dá para criá-las.

**Etapa 5.1: tipos ordenados por `created_at`**

- **Entrega:** `TaskType` ganha `created_at`. A listagem ordena por ele, com o id só como desempate. O comentário em `task_types.py` que fala da ordem por id é corrigido.
- **Arquivos:** `app/models.py`, `app/routers/task_types.py`, `tests/test_task_types.py`. Fora do Git: apagar `backend/agenda.db`, com um comando que eu mesmo rodo.
- **Como testar:** `pytest`. Depois, apagar o banco, subir o app e, no `/docs`, criar dois tipos e listar.
- **Pronto quando:** um teste prova que a ordem vem do `created_at` (um tipo com id maior e data mais antiga vem primeiro) e que o empate aparece em ordem de id (no SQLite, esse teste não detecta a remoção do desempate); `GET /task-types` mostra o `created_at`; todos os testes passam.
- **Atenção:** `test_rename_changes_the_name` compara o JSON exato e vai quebrar, porque a resposta ganha um campo. Ele precisa ser ajustado.

**Etapa 5.2: função auxiliar de datas**

- **Entrega:** `tzdata` no `requirements.txt` (versão fixa, `2026.6`), a constante `APP_TIMEZONE` e as funções para "que dia é agora em Brasília" e "em que dia de Brasília caiu esta data e hora". Data sem fuso é tratada como UTC.
- **Arquivos:** `requirements.txt`, `app/dates.py` (novo), `tests/test_dates.py` (novo), `CLAUDE.md` (uma linha na estrutura de pastas).
- **Como testar:** `pip install -r requirements.txt` e `pytest tests/test_dates.py`. Ainda não muda nada no `/docs`.
- **Pronto quando:** 01h30 UTC de 01/11 dá 31/10; a mesma hora sem fuso dá o mesmo resultado; o "hoje" vira à meia-noite de Brasília, não à de UTC, testado com hora fixa.
- **Decisão:** o arquivo fica em `app/dates.py`, fora de `rules/`, porque data não é regra do jogo. A estrutura de pastas do `CLAUDE.md` não previa esse arquivo.

**Etapa 5.3: regras puras de adiamento em `xp.py`**

- **Entrega:** `task_xp` trata atraso negativo como 0. Uma única conta de adiamentos efetivos, usada pelo XP e pela trava. Uma função que diz se a data está travada e outra que calcula o novo contador depois de mudar a data.
- **Arquivos:** `app/rules/xp.py`, `tests/test_xp.py`.
- **Como testar:** `pytest tests/test_xp.py`.
- **Pronto quando:** os exemplos da seção 4.2 viram testes: `0 + 2 + 1 = 3`; 3 adiamentos com data 5 dias à frente continua travada; antecipar não conta; exatamente 3 vale 25% e mais de 3 vale 0. Os testes antigos continuam passando.

**Etapa 5.4: criar tarefa**

- **Entrega:** `POST /tasks` com as regras de campos da seção 6.1 e a regra da data nova. A entrada não aceita `postponements` nem `completed`: como todo campo desconhecido, eles são recusados com 422.
- **Arquivos:** `app/routers/tasks.py` (novo), `app/main.py`, `tests/test_tasks.py` (novo).
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, criar uma tarefa válida e tentar uma com cor `#FFF` e outra com data de ontem.
- **Pronto quando:** cada regra de campo tem um caso aceito e um recusado; `task_type_id` inexistente ou fora do intervalo dá 422 com mensagem clara, nunca 500; o pedido recusado não grava nada; hoje é aceito e ontem é recusado, com "hoje" fixo no teste.
- **Reaproveita:** `SessionDep` e `MAX_ID` de `task_types.py`, `DEFAULT_TASK_COLOR` de `models.py`. O "hoje" fixo usa o `monkeypatch` do próprio pytest, sem dependência nova.

**Etapa 5.5: listar por dia**

- **Entrega:** uma rota que recebe a data e devolve três grupos: atrasadas (só quando a data é hoje), pendentes e concluídas, na ordem da seção 6.2.
- **Arquivos:** `app/routers/tasks.py`, `app/dates.py` (início e fim do dia em Brasília), `tests/test_tasks.py`, `tests/test_dates.py`.
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, ver a tarefa criada no dia dela. Atrasadas e concluídas só nos testes.
- **Pronto quando:** a concluída às 22h30 de 31/10 aparece em 31/10 e não em 01/11; as atrasadas só aparecem na visão de hoje, da mais antiga para a mais recente; as ordens e os desempates estão testados; `9999-12-31` não vira 500.

**Etapa 5.6: listar por semana**

- **Entrega:** uma rota que recebe qualquer data e devolve os sete dias da semana dela, de segunda a domingo. Cada dia traz uma lista só, com pendentes e concluídas juntas, por ordem de criação (é o que a seção 6.2 pede para as colunas).
- **Arquivos:** `app/routers/tasks.py`, `app/dates.py` (segunda-feira da semana), `tests/test_tasks.py`, `tests/test_dates.py`.
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, pedir a semana passando uma quarta-feira e depois um domingo.
- **Pronto quando:** segunda e domingo dão a mesma semana; a concluída às 22h30 de domingo fica naquela semana, não na seguinte; a semana de `9999-12-31` não vira 500.
- **Decisão:** a semana de `9999-12-31` traz só 5 dias, de 27/12 a 31/12, porque essa data é uma sexta-feira e o sábado e o domingo seguintes não existem no Python. Assim, uma tarefa marcada para esse dia continua visível na semana, o que uma recusa com 422 impediria.

**Etapa 5.7: excluir tarefa**

- **Entrega:** `DELETE /tasks/{id}`. As linhas da tarefa no histórico ficam com `task_id` nulo e mantêm o valor, tudo na mesma transação.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`.
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, excluir uma tarefa e ver que ela sumiu da lista.
- **Pronto quando:** 204 ao excluir, 404 para id desconhecido, 422 para id fora do intervalo; com um `XpEntry` inserido direto no banco (gerar XP é da tarefa 6), a soma do XP não muda e as linhas de outras tarefas ficam intactas.
- **Reaproveita:** o padrão de `delete_task_type`, com `flush` antes de excluir.

**Etapa 5.8: editar tarefa, ainda sem mudar a data**

- **Entrega:** `PUT /tasks/{task_id}`, rota de edição de título, notas, cor, dificuldade e tipo, com as mesmas validações da criação. Em tarefa concluída, mudar a dificuldade dá 409 e mandar o mesmo valor passa.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`, `docs/especificacao.md` (registro das decisões).
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, editar uma tarefa e listar para conferir.
- **Pronto quando:** cada campo é editado e validado; o pedido recusado não grava nada; tarefa concluída aceita título, notas, cor e tipo; 404 e 422 de id funcionam.
- **Decisão:** a edição exige todos os campos, porque o formulário envia todos. Assim, esquecer um campo não apaga as notas nem volta a cor ao padrão. Notas e tipo aceitam `null`, que remove o valor de propósito.
- **Decisão:** a edição usa `PUT`, porque o pedido manda o registro inteiro. O `PUT` substitui só o que o cliente pode definir: `id`, `completed`, `completed_at`, `postponements` e `created_at` ficam fora do pedido e não mudam.
- **Decisão:** nesta etapa, `due_date` no pedido dá 422, como todo campo desconhecido. Quando 422 e 409 se aplicam ao mesmo pedido, vale o 422, porque o dado é conferido antes do estado da tarefa.

**Etapa 5.9: mudança de data na edição (fecha a tarefa 5)**

- **Entrega:** a edição passa a exigir `due_date`, como os outros campos, com as regras da seção 4.2 e a regra do "mesmo valor". A lógica fica numa função que a tarefa 7 vai reaproveitar. A rota do botão Adiar não entra aqui.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`, `docs/especificacao.md` (registro das decisões e Mapa do código).
- **Como testar:** `pytest`. No `/docs`, criar uma tarefa, mudar a data para depois três vezes (`postponements` chega a 3), ver a quarta tentativa dar 409 e ver que editar só o título, mandando a mesma data, ainda funciona.
- **Pronto quando:** este é o critério da tarefa 5 na tabela, "funciona pelo `/docs` e os testes cobrem as regras". Casos testados: data anterior a hoje dá 422; atrasada com 0 adiamentos e 2 dias de atraso fica com contador 3; antecipar não conta; travada por atraso ou por adiamento manual recusa inclusive antecipar: 409 quando a data nova é hoje ou depois, 422 quando é anterior a hoje, porque o dado é conferido antes do estado; concluída recusa mudar a data (409); travada ou atrasada aceita editar o título; o pedido recusado não grava nada.
- **Decisão (tomada na etapa 5.8):** quando 422 e 409 se aplicam ao mesmo pedido, vale o 422, porque o dado é conferido antes do estado da tarefa. Por isso, antecipar uma tarefa travada por atraso dá sempre 422: a data dela já é anterior a hoje, então qualquer data mais antiga também é.
- **Decisão:** `ensure_date_is_not_past` e `change_due_date` ficam em `tasks.py`, e a tarefa 7 chama as duas, nesta ordem. São duas funções porque a conferência do tipo fica entre elas. Elas não vão para `rules/xp.py` porque leem o relógio, alteram a `Task` e respondem com códigos HTTP; as contas continuam em `xp.py`.

**Fora da tarefa 5:**

- Concluir e desmarcar (tarefa 6), rota do Adiar (tarefa 7), front-end (tarefas 9 em diante).
- Campo que diz à tela se a data está travada: as tarefas 10 e 11 vão precisar dele para bloquear o botão e o formulário sem repetir a regra em JavaScript. Ele entra quando a tela precisar, para não adiantar tarefa.

**Detalhe sobre testar no celular:** antes da publicação, o teste é pelo cabo USB, abrindo `http://localhost:8000` no celular, como explica a seção 6.7. Como `localhost` é origem segura, o service worker e a instalação já podem ser testados assim. A instalação definitiva vem na tarefa 17.

**Segurança nas tarefas 9 a 14 (regras na seção 6.7):**

- **Tarefa 9:** o `StaticFiles` monta só a pasta `frontend/`, depois das rotas da API, valendo também para produção. A CSP vai por cabeçalho: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'`. Por isso, JavaScript e CSS ficam em arquivos, sem `onclick` no HTML. Um teste do pytest lê os `.js` de `frontend/` e falha se achar `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` ou `eval`.
- **Tarefa 10:** título e notas entram por `textContent`. Teste manual: criar uma tarefa com título em forma de HTML e ver que ele aparece como texto.
- **Tarefa 11:** os campos do formulário usam `value`, o nome do tipo usa `textContent` e a cor usa `style.backgroundColor`.
- **Tarefas 12 e 13:** a mesma regra. Na 13, fontes e ícones são locais.
- **Tarefa 14:** o service worker usa uma lista fechada de arquivos e responde só a `GET` dessa lista. API e `/auth` passam direto, sem cache.

**Divisão da tarefa 15:**

- **Etapa 15.1, configuração:** `APP_ENV`, `APP_PASSWORD` e `APP_ORIGIN`, com o app recusando subir sem senha válida ou, fora do desenvolvimento, sem endereço válido (seção 6.7). O `python-dotenv` entra como dependência nova, autorizada nesta tarefa e só para desenvolvimento, porque o `uvicorn --env-file` exige. O comando passa a ser `uvicorn app.main:app --reload --env-file .env`. Eu escrevo a senha de desenvolvimento no `backend/.env`; `APP_ORIGIN` não precisa estar lá. Um `conftest.py` define valores falsos para os testes, com `APP_ORIGIN=https://testserver`.
- **Etapa 15.2, proteção no back-end:** login, cookie com o nome `__Host-session`, tabela `AuthSession` com HMAC, contador de tentativas em memória, conferência de `Origin` (regras na seção 6.7), limite de tamanho dos pedidos, cabeçalhos (`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` na API) e `/docs`, `/redoc` e `/openapi.json` desligados fora do desenvolvimento. Os clientes de teste passam a vir de uma única fixture no `conftest.py`: `TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"})`. Sem o `base_url`, o cookie `Secure` não volta; sem o `Origin`, as escritas dão 403. Teste manual: um POST pelo `/docs` funciona em `localhost:8000` e em `127.0.0.1:8000`.
- **Etapa 15.3, tela:** tela de login, resposta ao 401 e botão de sair. Conferir o cookie no Chrome do celular, por USB. Se ele recusar o prefixo `__Host-` em `localhost`, sai só o prefixo, e os outros atributos ficam. Conferir também, por USB e com o app instalado, que criar uma tarefa funciona.
- **Testes obrigatórios da 15.1:** fora do desenvolvimento, o app recusa subir sem `APP_ORIGIN` e com `http://`, barra no fim, caminho, maiúsculas, `:443` ou `null`.
- **Testes obrigatórios da 15.2:**
  - percorrer `app.openapi()["paths"]` e exigir 401 fora de `/health` e `/auth/login` (`app.routes` não serve nesta versão do FastAPI);
  - senha acentuada não vira erro 500;
  - o token vale antes de trocar a senha, dá 401 depois, e a senha nova entra;
  - a limpeza no login remove só as sessões expiradas;
  - `debug` é falso;
  - POST sem corpo vindo de outra origem dá 403;
  - em POST, PUT, PATCH e DELETE: sem `Origin`, com `Origin: null` e com `Origin` de outro endereço dão 403 e não gravam nada; com `Origin` certo, a rota responde normalmente;
  - `http://testserver`, `https://testserver:8443`, `https://testserver.evil.example`, `https://testserver/` e `HTTPS://TESTSERVER` dão 403;
  - `Host` e `Origin` iguais, mas de outro endereço, dão 403;
  - `POST /auth/login` com a senha certa e `Origin` errado dá 403, sem cookie e sem contar tentativa;
  - POST sem cookie e com `Origin` errado dá 403, não 401;
  - POST em rota que não existe, com `Origin` errado, dá 403;
  - `GET` sem `Origin` passa pela conferência;
  - em desenvolvimento, sem `APP_ORIGIN`, aceita `http://localhost:8000` e `http://127.0.0.1:8000` e recusa `http://localhost:5500`;
  - percorrer os `GET` de `app.openapi()["paths"]`, com login e banco preenchido, sem nenhuma instrução além de `SELECT` e `PRAGMA` (evento `before_cursor_execute`); parâmetro de rota desconhecido reprova;
  - `include_in_schema` não aparece em `backend/app/`.

**Detalhes sobre a tarefa 16:**

- O Alembic passa a criar e alterar as tabelas no lugar do `create_all` ao iniciar o app, porque os dois juntos colidem. O teste `test_app_startup_creates_tables` muda nessa tarefa.
- A restauração mantém os `created_at`, de que a ordem depende.
- A restauração não passa pela regra da data nova, senão tarefas antigas seriam recusadas.
- A restauração não grava os ids do arquivo: o banco gera ids novos e as referências são traduzidas. Gravar ids à mão não avança o contador do PostgreSQL, e o próximo registro criado colidiria.
- A restauração aceita só banco vazio, em uma transação, tudo ou nada, e tem limite de tamanho próprio. Assim, um clique errado ou um token roubado não substitui tudo.
- Exportar e restaurar têm uma tela simples no app, porque o `/docs` não existe em produção. A tela mostra a data da última exportação e avisa depois de 7 dias.
- O arquivo exportado não traz a tabela `AuthSession`, e a resposta usa `Cache-Control: no-store`. O nome segue o padrão `agenda-rpg-backup-*.json`, que entra no `.gitignore`.
- O `requirements.txt` passa a fixar todas as dependências de produção, incluindo as indiretas. `pytest`, `httpx2` e `python-dotenv` vão para um `requirements-dev.txt`.
- O driver do PostgreSQL ainda não está autorizado: é preciso pedir antes de adicionar.
- Entram também: `hide_parameters=True`; `alembic.ini` sem endereço do banco; TLS exigido na URL do PostgreSQL (`sslmode=verify-full` se o serviço permitir, `require` no mínimo), com o app recusando subir sem ele; `conftest.py` removendo a `DATABASE_URL` do ambiente dos testes; revisão de cada migração antes de rodar.
- **Obrigatório antes da publicação:** uma validação única de texto, usada por tipos e tarefas (nome, título e notas), que recusa com 422 o caractere NUL (`\u0000`) e caracteres Unicode inválidos como `\ud800`, com testes. Objetivo: nenhuma entrada de texto pode virar erro 500.

**Detalhes sobre a tarefa 17:**

- **Critérios do serviço, além de o banco não expirar:** regra de inatividade por escrito (pausar é aceitável, apagar não); TLS na conexão com o banco; 2FA na conta; exportação possível; variáveis de ambiente fora dos logs; versão do Python compatível; subdomínio na Public Suffix List ou domínio próprio, por causa do `SameSite`.
- **Comando de início:** `uvicorn app.main:app --host 0.0.0.0 --port <porta do serviço>`, com 1 processo, sem `--reload` e sem `--env-file`. As migrações rodam no serviço, no início do deploy. Confirmar como o serviço aplica uma variável nova: a troca de senha só vale depois do reinício. `APP_ORIGIN` fica no painel, com o endereço público final. Mudar de endereço exige mudar a variável, senão toda gravação dá 403.
- **Antes de publicar:** consulta à base OSV, e nenhuma falha conhecida sem decisão minha.
- **Conferência sem token, contra o endereço publicado:** `/docs`, `/redoc` e `/openapi.json` dão 404; `/tasks/day/<data>` e `/task-types` dão 401; `/health` responde só o status; `http://` redireciona para `https://`, com HSTS; login errado 11 vezes, mandando o `Origin` certo, dá 429 (sem ele, daria 403), e um token existente continua funcionando; `/.env` e `/agenda.db` dão 404; o log do serviço não mostra título, nota, senha nem endereço do banco.
- **Conferência com login feito:** o cookie sai com `HttpOnly`, `Secure` e `SameSite=Strict`; POST com `Origin` de outro endereço, sem `Origin` e com `Origin: null` dá 403, e o app instalado continua gravando pela própria tela, o que também prova que `APP_ORIGIN` está certa e que o proxy não apaga o cabeçalho; trocar `APP_PASSWORD` no painel faz o token antigo dar 401, e a senha nova entra.
- **Backup:** exportar de produção e restaurar num banco vazio. Repetir a restauração a cada 3 meses.

## 11. Fica para depois

- Notificações no celular (lembrete de tarefa).
- Sincronizar com o Google Agenda.
- Modo offline (a V1 precisa de internet; ver seção 6.5).
- Login de várias pessoas, caso um dia o app seja aberto ao público.

## 12. Mapa do código

Serve para achar onde está cada parte do projeto. Lista só o que já existe. Fora do mapa: `agenda.db` e tudo o que está no `.gitignore`.

| Arquivo | O que faz | Funções ou rotas principais | Regras | Teste que protege |
| --- | --- | --- | --- | --- |
| `backend/app/main.py` | Cria o app FastAPI, cria o banco ao iniciar e registra as rotas. | `lifespan`, `GET /health` | 2 | `test_health.py`, `test_database.py` |
| `backend/app/database.py` | Conecta ao banco, entrega a sessão e liga as chaves estrangeiras no SQLite. | `DATABASE_URL`, `create_db_and_tables`, `get_session`, `enable_sqlite_foreign_keys` | 2, 6.6 | `test_database.py` |
| `backend/app/models.py` | Define as três tabelas do banco. | `TaskType`, `Task`, `XpEntry`, `utc_now`, `DEFAULT_TASK_COLOR` | 6.1, 6.4 | `test_database.py` |
| `backend/app/dates.py` | Responde "que dia é" no horário de Brasília. | `APP_TIMEZONE`, `to_app_date`, `app_today`, `app_day_bounds`, `week_days` | 6.4, 6.2 | `test_dates.py` |
| `backend/app/rules/xp.py` | Guarda as regras de XP, adiamento e nível, com os números no topo. | `task_xp`, `effective_postponements`, `is_due_date_locked`, `postponements_after_date_change`, `xp_to_next_level`, `level_from_total_xp` | 4.1, 4.2, 4.5 | `test_xp.py` |
| `backend/app/routers/task_types.py` | API dos tipos de tarefa; também define `SessionDep` e `MAX_ID`, usados em `tasks.py`. | `POST /task-types`, `GET /task-types`, `PATCH /task-types/{task_type_id}`, `DELETE /task-types/{task_type_id}` | 6.1, 6.6 | `test_task_types.py` |
| `backend/app/routers/tasks.py` | API das tarefas: criar, listar por dia e semana, editar (inclusive a data) e excluir. | `POST /tasks`, `GET /tasks/day/{day}`, `GET /tasks/week/{day}`, `PUT /tasks/{task_id}`, `DELETE /tasks/{task_id}`, `ensure_date_is_not_past`, `change_due_date` | 6.1, 6.2, 4.2, 4.3 | `test_tasks.py` |
| `backend/tests/test_health.py` | Testa a rota `/health`. | `test_health_returns_ok` | 10 (tarefa 1) | não se aplica |
| `backend/tests/test_database.py` | Testa a criação das tabelas ao iniciar, os valores padrão e a chave estrangeira. | `test_app_startup_creates_tables`, `test_task_with_unknown_task_type_is_refused` | 6.1 | não se aplica |
| `backend/tests/test_dates.py` | Testa o fuso, o "hoje", os limites do dia e a semana. | testes de `to_app_date`, `app_today`, `app_day_bounds`, `week_days` | 6.4 | não se aplica |
| `backend/tests/test_xp.py` | Testa XP, adiamentos, trava da data e níveis. | testes de cada função de `xp.py` | 4.1, 4.2, 4.5 | não se aplica |
| `backend/tests/test_task_types.py` | Testa a API dos tipos de tarefa. | testes de criar, listar, renomear e excluir | 6.1 | não se aplica |
| `backend/tests/test_tasks.py` | Testa a API das tarefas. | auxiliares `insert_task`, `insert_xp_entry`, `update_data` | 6.1, 6.2, 4.2, 4.3 | não se aplica |
| `backend/requirements.txt` | Fixa as versões das dependências. | não se aplica | 2 | não se aplica |
| `backend/pytest.ini` | Faz o pytest encontrar a pasta `app`. | `pythonpath` | não se aplica | não se aplica |
| `.gitignore` | Diz o que fica fora do Git. | não se aplica | não se aplica | não se aplica |
| `.claude/settings.json` | Faz o Claude Code salvar os planos em `docs/planos` e bloqueia a leitura do `.env` e das variações. | `plansDirectory`, `permissions.deny` (regra 14 do `CLAUDE.md`) | não se aplica | não se aplica |
| `CLAUDE.md` | Define como trabalhar comigo, a stack, as convenções e os comandos. | regras 1 a 14, exceções aprovadas | não se aplica | não se aplica |
| `README.md` | Apresenta o projeto no GitHub. | não se aplica | 1 | não se aplica |
| `docs/especificacao.md` | Guarda as regras do jogo, as telas, as decisões de segurança, a lista de tarefas e este mapa. | segurança na 6.7, tarefas na seção 10, mapa na seção 12 | não se aplica | não se aplica |
| `docs/planos/*.md` | Guardam um plano por etapa, como registro histórico. Se um plano divergir da especificação, vale a especificação. | nome dos arquivos na regra 13 do `CLAUDE.md` | não se aplica | não se aplica |
