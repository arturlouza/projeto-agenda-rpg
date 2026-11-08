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
- O botão "Adiar" manda a tarefa para 1 dia depois da data marcada. Se ela estiver atrasada, manda para amanhã. Em conta: `nova data = o maior entre a data marcada e hoje em Brasília, mais 1 dia`. "Sempre amanhã" foi descartado porque, numa tarefa com data futura, viraria antecipar. Outra data, só pela tela de edição.
- Ao adiar uma tarefa atrasada, os dias de atraso acumulados até aquele momento são somados ao contador de adiamentos e não se perdem. Exemplo: com 0 adiamentos e 2 dias de atraso, adiar deixa o contador em `0 + 2 + 1 = 3`.
- **Com 3 ou mais adiamentos efetivos, a data trava:** não pode mais ser mudada por nenhum caminho, nem pelo botão "Adiar", nem pela edição, nem para antecipar. A tarefa só sai da lista se for concluída ou excluída.
- A tarefa travada vale 25% com exatamente 3 adiamentos efetivos e **perde o XP** com mais de 3: ainda dá para concluí-la, mas ela vale 0.
- A tarefa travada só aparece nas atrasadas se estiver mesmo atrasada. Com 3 adiamentos manuais e data futura, ela fica no dia marcado.
- A trava usa a mesma conta do XP, com os dias de atraso nunca negativos. Sem isso, 3 adiamentos e uma data 5 dias à frente dariam `3 − 5 = −2` e destravariam a data.
- O resultado é sempre arredondado para baixo, para um número inteiro, como no D&D. Exemplo: 25 × 75% = 18,75 vira 18.

Em código: `adiamentos_efetivos = adiamentos_manuais + dias_de_atraso`. Se for maior que 3, o XP é 0; senão, `XP = arredondar_para_baixo(XP_base × (1 − 0,25 × adiamentos_efetivos))`.

### 4.3 Desmarcar

Desmarcar uma tarefa concluída devolve exatamente o XP que ela deu. Assim não dá para "farmar" XP marcando e desmarcando.

A linha de desmarcar vale o negativo da soma das linhas da tarefa, lidas do histórico. Não é uma conta nova, porque os dias de atraso mudam com o tempo. Assim, em quantos ciclos forem, uma tarefa pendente soma 0 no histórico e uma concluída soma o XP que deu.

Excluir uma tarefa concluída mantém no histórico o XP que ela deu. Para remover esse XP, é preciso desmarcar a tarefa antes de excluir. Ao excluir a tarefa, as linhas dela no histórico ficam com `task_id` nulo: a chave estrangeira recusaria a exclusão, e um id solto apontaria para uma tarefa que não existe mais.

### 4.4 Histórico de XP

O XP nunca é guardado como um número solto. Cada ganho ou perda vira uma linha no histórico (`XpEntry`), com valor, motivo e tarefa de origem. O XP total é a soma do histórico, e o nível é calculado a partir dele. Isso garante que desmarcar devolva o valor certo e permite auditar de onde veio cada ponto.

- Concluir e desmarcar gravam sempre uma linha, mesmo de valor 0, para mostrar que a tarefa foi concluída e não rendeu nada.
- O motivo traz o título da tarefa, porque a linha perde o vínculo com ela quando a tarefa é excluída: `Tarefa concluída: Ler 30 páginas` e `Tarefa desmarcada: Ler 30 páginas`. Nenhum código decide nada lendo esse texto.
- Só as linhas de concluir e desmarcar levam `task_id`. Um bônus da V2 gravado com `task_id` seria devolvido junto ao desmarcar a tarefa.

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

**Barra de progresso:**

- A barra mostra a porcentagem do XP acumulado dentro do nível atual sobre o custo desse nível: `porcentagem = arredondar_para_baixo(XP_dentro_do_nível × 100 ÷ XP_para_subir)`, inteira, com conta só de números inteiros.
- Vai de 0 a 99 e **nunca mostra 100%** antes de subir de nível. Ao subir, volta a 0%. Exemplo: com 100 XP, o nível é 2 e a barra está em 0%.
- Pelas regras, o XP total nunca fica negativo. Se ficar, por um banco mexido à mão ou uma restauração errada, o nível e a barra tratam o total como 0, e o XP total mostra a soma real.

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

**Ids:** o id de cada registro é só um identificador, não é contagem nem ordem. Nenhum código, teste ou tela pode depender de o id ser sequencial, sem buracos ou nunca reaproveitado (seção 6.6). A exceção são os testes que conferem essa garantia do banco, na seção 6.6.

**Tabelas ligadas:** toda tabela nova que aponte para outra tem chave estrangeira e uma regra de exclusão definida, que diz o que acontece com as linhas filhas quando a linha apontada é excluída (ficam com nulo, são excluídas junto ou impedem a exclusão). A chave e a regra têm teste. Hoje: excluir um `TaskType` deixa as tarefas dele sem tipo, e excluir uma `Task` deixa as linhas dela no `XpEntry` com `task_id` nulo.

**Regras dos tipos de tarefa:**

- Não pode haver dois tipos com o mesmo nome, ignorando maiúsculas, minúsculas e acentos: "Leitura" e "LEITURA" são o mesmo nome, e "Exercício" e "exercicio" também, como "Força" e "Forca". O nome é gravado como foi digitado; só a comparação ignora a caixa e os acentos. Até 08/11/2026, os acentos contavam; a etapa 11.6a mudou isso porque, no celular, um acento esquecido criava um tipo duplicado.
- Tipos que já eram duplicados pela regra nova ficam como estão. Renomear um deles para um nome do mesmo grupo é recusado.
- Nome vazio é recusado. Espaços no começo e no fim são removidos, então um nome só com espaços também conta como vazio.
- O nome tem no máximo 50 caracteres, contados depois de remover os espaços do começo e do fim.
- Ao excluir um tipo usado por tarefas, as tarefas ficam sem tipo; nenhuma tarefa é apagada.
- Os tipos são listados pela ordem de criação (`created_at`), com o id só como desempate em caso de empate exato.
- Campo desconhecido no pedido é recusado com 422, inclusive `id` e `created_at`.

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
- **409:** dado válido, mas o estado da tarefa impede: mudar a data de uma tarefa travada (seção 4.2), mudar a dificuldade ou a data de uma tarefa concluída, concluir uma tarefa já concluída, desmarcar uma tarefa pendente, adiar uma tarefa que já está na última data possível (`9999-12-31`), ou adiar ou editar com a tela desatualizada.
- O pedido recusado não grava nada.

### 6.2 Telas

- **Topo fixo:** nível atual e barra de XP (quanto falta para o próximo nível).
- **Dia:** lista das tarefas da data escolhida, no estilo Google Tarefas. Na visão de hoje, as tarefas pendentes atrasadas aparecem em destaque no topo. Nas outras datas, uma tarefa pendente aparece no dia marcado. As tarefas concluídas vão para uma seção "Concluídas" no fim do dia, que pode ser aberta e fechada. Toda tarefa concluída aparece em "Concluídas" no dia em que foi concluída, no horário de Brasília, não no dia marcado. A tela troca de dia pelas setas de dia anterior e seguinte, pelo botão "Hoje" e por um calendário, o campo de data do próprio navegador.
- **Semana:** de segunda a domingo, com as tarefas de cada dia, e setas para navegar entre semanas. É a visão ampla que falta no Google Tarefas. Em tela larga, sete colunas lado a lado; no celular, os sete dias um embaixo do outro, sem rolagem para o lado. Vale a mesma regra da visão do dia: tarefa pendente aparece no dia marcado, inclusive a atrasada, com destaque; tarefa concluída aparece no dia em que foi concluída, no horário de Brasília. Na semana, a caixinha conclui e desmarca, e tocar numa tarefa ou no título de um dia abre esse dia, com o cartão da tarefa aberto. As atrasadas de fora da semana aparecem só como contagem, com um botão para a visão de hoje. Até a divisão da tarefa 12, este item dizia só "sete colunas"; o celular de 360 px não as comporta.
- **Ordem das listas:** dentro de um dia, as pendentes, as concluídas e as colunas da semana seguem a ordem de criação (`created_at`), com o id só como desempate em caso de empate exato. As atrasadas no topo da visão de hoje seguem a data marcada, da mais antiga para a mais recente; em empate, `created_at` e depois id.
- **Notas no dia e na semana:** tarefas que têm notas mostram um ícone.
- **Toque na tarefa:** tocar na tarefa expande o cartão, mostrando as notas (se houver) e os botões Editar e Adiar; tocar de novo recolhe. Numa tarefa sem notas, o toque expande do mesmo jeito, mostrando só os botões. O cartão expandido de uma tarefa concluída não mostra o botão Adiar, só as notas e o Editar. Numa tarefa travada (seção 4.2), o botão Adiar fica bloqueado. Concluir é pela caixinha de marcar, separada do toque.
- **Adiar pede confirmação:** cada adiamento tira 25% do XP e não tem volta (antecipar não desconta o contador). O primeiro toque troca o texto do botão para "Confirmar adiar (−25% XP)", e só o segundo adia. Sem confirmação, o botão volta ao normal sozinho depois de alguns segundos, ou ao tocar em outra coisa. Sem caixa de diálogo do navegador (`confirm`, `alert`). O "−25% XP" é texto fixo, não uma conta.
- **Criar/editar tarefa:** título, data, dificuldade, cor, tipo e notas. Excluir fica dentro da tela de edição e sempre pede confirmação antes de apagar. Numa tarefa travada, a data fica travada no formulário. Numa tarefa concluída, a dificuldade e a data ficam travadas no formulário.
- **Tipos de tarefa:** uma tela pequena, aberta pelo botão no fim da página, que lista os tipos com quantas tarefas usam cada um, renomeia e exclui com confirmação. Excluir deixa as tarefas sem tipo; nenhuma tarefa é apagada.
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
- Os arquivos de `frontend/` vão com `Cache-Control: no-cache`: o navegador pode guardá-los, mas confere com o servidor antes de usar, então um recarregar comum já pega a versão nova (etapa 10.4).

A V1 precisa de internet:

- O service worker guarda só os arquivos do app, nunca dados da API.
- O cache tem um número de versão que muda a cada publicação, para o celular receber a versão nova.

### 6.6 Diferenças conhecidas entre os bancos

- **Ids:** nos dois bancos, o id de uma linha excluída não volta a ser usado, nem com a tabela vazia. No SQLite, isso vem de `sqlite_autoincrement=True` nos modelos (a palavra `AUTOINCREMENT` na tabela); sem ela, os maiores ids excluídos seriam reaproveitados. No PostgreSQL, vem da sequência da coluna `SERIAL`, e a opção não tem efeito. A garantia vale só dentro do mesmo banco: apagar o `agenda.db` ou restaurar num banco novo recomeça a contagem. E os bancos ainda diferem num ponto: um pedido desfeito (rollback) gasta um número no PostgreSQL e pode não gastar no SQLite, então só o PostgreSQL deixa um buraco nesse caso. Por isso vale a regra de ids da seção 6.1.
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
- **Decisão:** a edição exige todos os campos, porque o formulário envia todos. Assim, esquecer um campo não apaga as notas nem volta a cor ao padrão. Notas e tipo aceitam `null`, que remove o valor de propósito. Desde a etapa 11.1, a edição também exige `shown_due_date` (ver as decisões da etapa 11.1).
- **Decisão:** a edição usa `PUT`, porque o pedido manda o registro inteiro. O `PUT` substitui só o que o cliente pode definir: `id`, `completed`, `completed_at`, `postponements` e `created_at` ficam fora do pedido e não mudam.
- **Decisão:** nesta etapa, `due_date` no pedido dá 422, como todo campo desconhecido. Quando 422 e 409 se aplicam ao mesmo pedido, vale o 422, porque o dado é conferido antes do estado da tarefa.

**Etapa 5.9: mudança de data na edição (fecha a tarefa 5)**

- **Entrega:** a edição passa a exigir `due_date`, como os outros campos, com as regras da seção 4.2 e a regra do "mesmo valor". A lógica fica numa função, e a tarefa 7 reaproveita as conferências dela. A rota do botão Adiar não entra aqui.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`, `docs/especificacao.md` (registro das decisões e Mapa do código).
- **Como testar:** `pytest`. No `/docs`, criar uma tarefa, mudar a data para depois três vezes (`postponements` chega a 3), ver a quarta tentativa dar 409 e ver que editar só o título, mandando a mesma data, ainda funciona.
- **Pronto quando:** este é o critério da tarefa 5 na tabela, "funciona pelo `/docs` e os testes cobrem as regras". Casos testados: data anterior a hoje dá 422; atrasada com 0 adiamentos e 2 dias de atraso fica com contador 3; antecipar não conta; travada por atraso ou por adiamento manual recusa inclusive antecipar: 409 quando a data nova é hoje ou depois, 422 quando é anterior a hoje, porque o dado é conferido antes do estado; concluída recusa mudar a data (409); travada ou atrasada aceita editar o título; o pedido recusado não grava nada.
- **Decisão (tomada na etapa 5.8):** quando 422 e 409 se aplicam ao mesmo pedido, vale o 422, porque o dado é conferido antes do estado da tarefa. Por isso, antecipar uma tarefa travada por atraso dá sempre 422: a data dela já é anterior a hoje, então qualquer data mais antiga também é.
- **Decisão:** `ensure_date_is_not_past` e `change_due_date` ficam em `tasks.py`, e a edição chama as duas, nesta ordem. A tarefa 7 mudou o que estava previsto aqui e não chama nenhuma delas (ver as decisões da tarefa 7). São duas funções porque a conferência do tipo fica entre elas. Elas não vão para `rules/xp.py` porque leem o relógio, alteram a `Task` e respondem com códigos HTTP; as contas continuam em `xp.py`. A etapa 11.1 tirou `change_due_date`: ela mudava a `Task` lida, e a edição passou a gravar num `UPDATE` condicional, como o Adiar.

**Fora da tarefa 5:**

- Concluir e desmarcar (tarefa 6), rota do Adiar (tarefa 7), front-end (tarefas 9 em diante).
- Campo que diz à tela se a data está travada: as tarefas 10 e 11 vão precisar dele para bloquear o botão e o formulário sem repetir a regra em JavaScript. Ele entra quando a tela precisar, para não adiantar tarefa. Resolvido na etapa 10.1 (`due_date_locked`).

**Decisões da tarefa 6 (plano `06-concluir-e-desmarcar.md`):**

- **Rotas:** `POST /tasks/{task_id}/complete` e `POST /tasks/{task_id}/uncomplete`, sem corpo. Respondem 200 com `{"task": ..., "xp_change": ...}`. `xp_change` é quanto o XP total mudou: positivo ao concluir, negativo ao desmarcar e 0 numa tarefa que vale 0.
- **Recusas:** 422 para id fora do intervalo, depois 404 para id desconhecido, depois 409 para o estado da tarefa. O pedido recusado não grava nada.
- **Toque duplo:** o estado muda num `UPDATE` condicional do SQLModel, que só vale se a tarefa ainda estiver no estado oposto. Ler, conferir `task.completed` e gravar deixaria dois pedidos simultâneos passarem, e a tarefa daria XP em dobro. Foi testado só no SQLite. Conferir com pedidos simultâneos no PostgreSQL quando o driver entrar, na tarefa 16.
- **Transação única:** a tarefa e a linha do histórico entram no mesmo commit.
- **Sem brecha:** os adiamentos efetivos nunca diminuem, e a soma de uma tarefa é 0 ou o valor da última conclusão, então marcar e desmarcar nunca rende mais. Editar a dificuldade da tarefa pendente continua permitido (seção 6.1), e os valores não se somam.

**Fora da tarefa 6:**

- XP no cartão da tarefa concluída (seção 6.3): a listagem precisa trazer esse valor. Ele entra quando a tela precisar, para não adiantar tarefa. Resolvido na etapa 10.1 (`xp_earned`).
- Resposta 409 na tela: na tarefa 10, o front-end recarrega a lista, porque o 409 só significa que a tela estava desatualizada.

**Decisões da tarefa 7 (plano `07-botao-adiar.md`):**

- **Rota:** `POST /tasks/{task_id}/postpone`, com o corpo `{"shown_due_date": "AAAA-MM-DD"}`, a data que a tela mostrava. Responde 200 com a tarefa. Não traz `xp_change`, porque adiar não mexe no XP e nada entra no histórico.
- **A conta:** `postponed_due_date`, em `rules/xp.py`, com o número na constante `POSTPONE_DAYS`. Devolve `None` quando o dia seguinte não existe.
- **Toque duplo:** o servidor só adia se a tarefa ainda tiver a data enviada. Se não tiver, responde 409, porque a tela estava desatualizada. Assim, o segundo toque não adia de novo (2 dias e −50% em vez de 1 dia e −25%).
- **Dois pedidos ao mesmo tempo:** a conferência é a condição de um `UPDATE` do SQLModel, que só vale se a tarefa ainda estiver pendente e com aquela data. Para dois Adiar simultâneos, ler, conferir e gravar já daria o resultado certo, porque cada um grava valores absolutos, e não acrescenta linha como na tarefa 6. A condição é necessária para um Adiar junto com um Concluir: sem ela, a tarefa concluída ficaria com a data mudada, contra a seção 6.1. Foi testado só no SQLite. Conferir com pedidos simultâneos no PostgreSQL quando o driver entrar, na tarefa 16.
- **Reaproveitamento:** a rota usa `ensure_due_date_can_change`, que saiu de `change_due_date` e guarda as conferências de tarefa concluída e de trava, e `postponements_after_date_change`. Não chama `change_due_date`, porque ela grava sem condição. Não chama `ensure_date_is_not_past`, porque a data nova é sempre depois de hoje e ela nunca recusaria. Um teste em `test_xp.py` prova isso.
- **Última data:** adiar uma tarefa em `9999-12-31` dá 409. O pedido não tem dado inválido: é a data atual da tarefa que não permite adiar. Sem esse cuidado, somar um dia daria `OverflowError` e erro 500.
- **Ordem das recusas:** primeiro 422 (id fora do intervalo ou corpo inválido), depois 404 e depois os 409, do mais definitivo para o mais passageiro: tarefa concluída, data travada, última data possível e tela desatualizada. Recarregar só resolve o último, então os outros dizem o motivo real. No toque duplo que atinge a trava, o segundo toque recebe a mensagem da trava.

**Fora da tarefa 7:**

- Botão na tela: o front-end manda em `shown_due_date` a data que recebeu da listagem e nunca calcula a data nova. O 409 recarrega a lista, como no Concluir. Resolvido na etapa 10.3.
- A edição tem uma brecha parecida, que continua aberta: um `PUT` que muda a data, sobreposto a um Concluir, grava a data numa tarefa concluída; sobreposto a um Adiar, perde um adiamento. É bem menos provável, porque o formulário fica em outra tela. Resolvido na etapa 11.1.

**Decisões da tarefa 8 (plano `08-api-do-jogador.md`):**

- **Rota:** `GET /player`, só leitura, num router próprio (`routers/player.py`). Responde 200 com `total_xp`, `level`, `xp_into_level` (XP já acumulado dentro do nível atual), `xp_for_next_level` (quanto o nível atual custa) e `progress_percent`. "Quanto falta" (seção 6.2) é `xp_for_next_level − xp_into_level` e não vira campo próprio.
- **A conta:** duas funções puras em `rules/xp.py`. `level_progress` devolve o nível e o XP dentro dele e substitui `level_from_total_xp`, que descartava essa sobra. `progress_percent` faz a porcentagem da seção 4.5. A rota só soma o histórico e chama as regras.
- **Desempenho:** até o nível 100, o laço paga um nível por volta, no máximo 99 voltas. Do 100 em diante, como todo nível custa o mesmo, uma divisão resolve o resto. Com o laço antigo, 10 bilhões de XP levavam 4 segundos; agora qualquer total leva uma fração de milissegundo. O total de 86.928 XP até o nível 100 não vira constante, para não haver um segundo número a manter quando a fórmula mudar.
- **A soma:** feita no banco, com `func.sum` do SQLModel, sem SQL escrito à mão. Com 365 mil linhas, o banco somou em 0,02 s e o Python, em 0,35 s. O histórico vazio dá `NULL`, tratado como 0: nível 1, barra em 0%.
- **Fica para a tarefa 16:** no PostgreSQL, a soma de `INTEGER` vem como `BIGINT`. Conferir que chega ao Python como `int` quando o driver entrar.

**Fora da tarefa 8:**

- **Comemoração ao subir de nível (tarefa 13):** depois de concluir, a tela pede o `/player` de novo para atualizar a barra. Ela compara o `level` novo com o que estava mostrando e, se for maior, mostra a comemoração. Não precisa de campo novo, e o JavaScript só compara dois números vindos do servidor, sem conta de XP. Ao abrir o app não há comparação, então não há comemoração falsa. Desmarcar e concluir de novo comemora outra vez, o que é inofensivo. Alternativa, se o segundo pedido incomodar: a resposta de concluir traz o nível. Decidir na tarefa 13.
- **Limite da porcentagem inteira:** no nível 100, 1% são 20,7 XP, então uma tarefa fácil às vezes não move a porcentagem. O XP ganho aparece no "+XP" ao concluir (seção 6.3).

**Decisões da tarefa 9 (plano `09-front-end-base.md`):**

- **Entrega do front:** o `StaticFiles` é a resposta padrão do roteador (`app.router.default`), e não um `app.mount("/")`. O roteador só chega a ele quando nenhuma rota da API casou com o pedido, nem pelo caminho. Com o `mount`, um `GET` numa rota que só aceita `POST`, como `/tasks/1/complete`, daria 404 em vez de 405, porque o `mount` em `/` casa com qualquer caminho e ganha da rota que casou só pelo caminho. Exceção registrada no `CLAUDE.md`. `default` é um parâmetro do `Router` do Starlette, não uma opção do FastAPI: se uma atualização mudar isso, os testes de 405 e o da página principal falham.
- **Caminho da pasta:** `FRONTEND_DIR` é achado a partir do próprio `main.py` (`Path(__file__).resolve().parents[2]`), então não depende da pasta em que o servidor foi ligado. Sem a pasta, o app recusa subir.
- **CSP:** vale para todas as respostas, menos as três páginas da documentação (`/docs`, `/redoc` e `/docs/oauth2-redirect`), que carregam scripts de fora e inline. Os caminhos vêm de `app.docs_url` e companhia. Esquecer um caso deixa a resposta com a CSP, e não sem ela.
- **Arquivos:** `index.html`, `css/style.css` e `js/app.js`, sem módulos. `API_BASE = "./"` e a função única `apiRequest` ficam no topo de `app.js`. Desde a etapa 11.2, ficam no topo de `js/api.js`.
- **Topo:** mostra "Nível N", "`xp_into_level` / `xp_for_next_level` XP" e a barra. "Faltam X XP" exigiria uma subtração no JavaScript, então não aparece. A barra é um `<progress>`, que recebe a porcentagem por `value`. Números com ponto de milhar, por `Intl.NumberFormat("pt-BR")`, que só formata.
- **Carregando e erro:** o HTML nasce com "Carregando…" e a barra em 0. Se a rede ou a API falhar, a mesma linha mostra o aviso de erro, e o erro completo vai para o console.
- **Visual:** cores, espaçamentos e tamanhos ficam em variáveis de CSS no `:root`, para a tarefa 13 trocar num lugar só. Fonte do sistema, sem nenhum recurso de fora.

**Fora da tarefa 9:**

- `POST`, `PUT` ou `DELETE` num endereço que não existe dá 405 em vez de 404, porque o `StaticFiles` só aceita leitura. Nada é gravado.
- O navegador pede `/favicon.ico` e recebe 404 até o ícone da tarefa 14.

**Divisão da tarefa 10:**

A tarefa 10 mexe na API e cria a maior parte do JavaScript do app, então vira 4 etapas, feitas nesta ordem. Cada etapa tem plano próprio, em sessão nova, e só começa depois do commit da anterior.

Por que esta ordem: a API vem primeiro porque as três telas dependem dela, e assim todo o JavaScript nasce sem nenhuma conta de XP, de data ou de trava. A 10.2 fecha o critério da tarefa. O cartão que expande vem depois porque, sem os botões, ele mostraria um espaço vazio numa tarefa sem notas. A navegação fica por último, porque a tela de hoje já é útil sozinha.

**Etapa 10.1: API da visão do dia**

- **Entrega:** `GET /tasks/today`; a resposta do dia ganha `day`, `is_today`, `previous_day` e `next_day`; cada tarefa da resposta do dia ganha `due_date_locked` e `xp_earned`. Só back-end.
- **Arquivos:** `backend/app/models.py`, `backend/app/dates.py`, `backend/app/routers/tasks.py`, `backend/tests/test_dates.py`, `backend/tests/test_tasks.py`.
- **Como testar:** `pytest`. No `/docs`, `GET /tasks/today`, concluir uma tarefa e ver o `xp_earned`, adiar três vezes e ver o `due_date_locked`.
- **Pronto quando:** a tela consegue saber o dia de hoje, a trava e o XP rendido sem nenhuma conta; a trava da lista concorda com a rota do Adiar; os testes antigos continuam passando.

**Etapa 10.2: lista de hoje com a caixinha (fecha o critério da tarefa)**

- **Entrega:** a tela abre por `GET /tasks/today` e nunca usa o relógio do celular. Atrasadas no topo, numa seção com destaque e a data marcada escrita no cartão, só formatada; some quando vazia. Pendentes na ordem da API. "Concluídas (N)" num `<details>`, fechada ao abrir o app e mantida aberta ao recarregar a lista se estava aberta; a concluída tem caixinha marcada, título riscado, cartão mais transparente e "+N XP" de `xp_earned`. Ícone de notas: um caractere simples, com texto para leitor de tela; a tarefa 13 troca pelo definitivo.
- **Caixinha:** `<input type="checkbox">` num `<label>` de 48 px, `disabled` enquanto espera a resposta do `POST /tasks/{task_id}/complete` ou `/uncomplete`, por `fetch` no modo padrão. Depois, recarrega a lista e o topo (`GET /player`). Um 409 faz o mesmo, sem mensagem. Outro erro recarrega a lista e mostra "Não foi possível salvar. Tente de novo." O `apiRequest` passa a guardar o código da resposta no erro, para a tela reconhecer o 409 sem ler texto. Enquanto a tela estiver em hoje, recarrega por `/tasks/today`, e não pela data guardada, para a virada da meia-noite.
- **Estados:** "Carregando tarefas…"; erro da API com "Não foi possível carregar as tarefas." e um botão "Tentar de novo"; "Nenhuma tarefa para hoje." com as três listas vazias.
- **Arquivos:** `frontend/index.html`, `frontend/css/style.css`, `frontend/js/app.js`.
- **Pronto quando:** dá para ver, concluir e desmarcar as tarefas de hoje, com o topo atualizado; o título `<img src=x onerror=alert(1)>` aparece como texto, sem alerta; o teste que recusa `innerHTML` continua passando.

**Etapa 10.3: cartão que expande, com Adiar**

- **Entrega:** o título vira um `<button>` com `aria-expanded`; tocar mostra as notas, com as quebras de linha, e o botão Adiar; tocar de novo recolhe. A caixinha fica separada do toque. O Adiar manda em `shown_due_date` a data recebida da lista e nunca calcula a data nova; fica bloqueado com `due_date_locked`; não aparece na concluída. O 409 recarrega a lista. O Editar fica para a tarefa 11.
- **Arquivos:** os mesmos três da 10.2.
- **A decidir no plano desta etapa:** como a tela mostra o 409 da última data possível (`9999-12-31`), que recarregar não resolve.

**Etapa 10.4: navegar entre os dias**

- **Entrega:** setas de dia anterior e seguinte, que pedem `GET /tasks/day/{previous_day}` e `{next_day}`, e o botão "Hoje", que pede `GET /tasks/today`. A seta fica bloqueada quando o vizinho vem `null`. Também um calendário, o campo de data do navegador (`<input type="date">`), cuja data vai para `GET /tasks/day/{data}` exatamente como o campo a entrega. O calendário substituiu o "sem seletor de data por enquanto" previsto antes, por decisão minha no plano desta etapa.
- **Arquivos:** os mesmos três da 10.2, mais `backend/app/main.py` e `backend/tests/test_frontend.py`, pelo cabeçalho de cache dos arquivos do front.

**Vale para as etapas 10.2 a 10.4:** caixinha, cartão, botões, setas e o `<summary>` das Concluídas com no mínimo `var(--touch-size)` (48 px); nada que dependa de passar o mouse por cima; foco visível para teclado; layout para 360 px, sem rolagem para o lado. Título e notas entram por `textContent`. Para escrever a data, o JavaScript só formata o texto que veio da API, com `Intl.DateTimeFormat` em `timeZone: "UTC"`, porque `new Date("2026-11-04")` é meia-noite em UTC e, formatado no fuso do celular, viraria 03/11.

**Decisões da etapa 10.1 (plano `10.1-api-da-visao-do-dia.md`):**

- **Que dia é hoje:** rota `GET /tasks/today`, só leitura, que devolve o mesmo que `GET /tasks/day/{day}` para o `app_today()`. A resposta traz `day` (a data listada) e `is_today`, então a tela sabe que dia está mostrando sem ler o relógio do celular. Uma rota, e não um campo no `/player`, porque o dia é da lista, e porque a tela precisaria da data antes do primeiro pedido.
- **Um "hoje" por pedido:** as duas rotas leem o relógio uma vez e passam o valor para `build_day_tasks`, que o usa em `is_today`, nas atrasadas e na trava de todas as tarefas. Assim, um pedido à meia-noite não mistura dois dias.
- **`due_date_locked`:** calculado com `is_due_date_locked`, de `rules/xp.py`, para toda tarefa da resposta do dia, inclusive a concluída, sem exceção. Na concluída, ele diz se a tarefa voltaria travada ao ser desmarcada; a tela não o usa, porque o Adiar não aparece e o formulário da tarefa 11 trava a data por `completed`. A última data possível não entra no campo.
- **`xp_earned`:** a soma das linhas da tarefa no histórico, feita no banco com `func.sum` e `group_by`, numa consulta só para o dia inteiro. Pela seção 4.3, essa soma é o XP da última conclusão na concluída e 0 na pendente. Não é conta nova de XP. Entrou agora, e não na tarefa 13, porque o "+25 XP" é conteúdo do cartão; a 13 cuida do visual e da animação.
- **Só na listagem do dia:** criar, editar, concluir, desmarcar e adiar continuam devolvendo a tarefa como antes, porque a tela recarrega a lista depois de cada ação. A semana também continua igual.
- **`previous_day` e `next_day`:** calculados em `adjacent_days`, em `dates.py`, para o JavaScript não somar um dia a uma data. Em `0001-01-01` e `9999-12-31`, o vizinho que não existe vem `null`, em vez de `OverflowError`.
- **`TaskBase`:** os campos da tarefa passaram para uma classe sem tabela, e `Task` herda dela. A resposta do dia (`TaskView`) herda os mesmos campos e acrescenta os dois novos, sem repetir a lista. Conferido: o `CREATE TABLE task` saiu idêntico, então nada muda no `agenda.db`. Herdar direto de `Task` não tem suporte no SQLModel, e pôr a tarefa dentro de outro objeto mudaria o formato que a lista já tinha.
- **`/tasks/today` não é um id:** `PUT` e `DELETE` em `/tasks/today` continuam dando 422.

**Fora da etapa 10.1:**

- A semana (`GET /tasks/week/{day}`) sem os campos novos: decidir na tarefa 12, junto com o toque no cartão da semana. Resolvido na etapa 12.1.
- O 409 da última data possível no Adiar: decidir na etapa 10.3. Resolvido na etapa 10.3.

**Decisões da etapa 10.2 (plano `10.2-lista-de-hoje.md`):**

- **Cartões por `<template>`:** o desenho do cartão fica num `<template>` no `index.html`; o `app.js` copia o modelo com `cloneNode(true)`, acha cada parte com `querySelector` e preenche com `textContent`. O cartão se lê como HTML, e o JavaScript só tem as linhas que põem dados; com `createElement`, cada parte custaria três linhas, e a estrutura sumiria. As etapas 10.3 e 10.4 e as tarefas 11 e 12 seguem o mesmo padrão. HTML e JavaScript ficam ligados pelos nomes das classes.
- **Nome da caixinha:** o `<label>` envolve só a caixinha, para o toque no título ficar livre para a 10.3. Ele leva o título num texto escondido da vista (`.visually-hidden`), também por `textContent`, para o leitor de tela dizer qual tarefa a caixinha conclui.
- **`app.js` em sete seções**, cada função antes de quem a usa e o início no fim: API, formatação, topo, desenhar a lista, buscar a lista, caixinha e início. Desde a etapa 11.2, o `app.js` virou quatro arquivos, cada um com as próprias seções, numeradas a partir de 1.
- **Voltar ao app:** no `visibilitychange`, quando a página volta a ficar visível, a tela pede `/tasks/today` e `/player` de novo, sem "Carregando…". Assim o app que ficou em segundo plano de um dia para o outro não mostra o dia de ontem como se fosse hoje. Se a volta falhar, a lista dá lugar ao aviso de erro.
- **Pedidos que se cruzam:** `loadDay` e `loadPlayer` guardam o número do pedido mais recente e só mostram a resposta desse pedido. Sem isso, um pedido antigo que chegasse por último deixaria a tela com o estado velho.
- **Depois da caixinha:** a lista e o topo são pedidos juntos, com `Promise.all`, porque um não depende do outro, e cada um trata o próprio erro. A ação (`complete` ou `uncomplete`) vem do `completed` que o servidor mandou, não do desenho da caixinha.
- **Uma gravação por vez:** enquanto uma caixinha espera a resposta, todas ficam `disabled`. Como a lista inteira é desenhada de novo depois de cada gravação, bloquear só a tocada deixaria uma segunda caixinha em espera ser trocada por uma nova, desbloqueada e com o estado antigo. O servidor continua protegido contra XP em dobro de qualquer jeito (tarefa 6).
- **Foco do teclado:** depois de desenhar a lista de novo, o foco volta à caixinha da mesma tarefa, onde ela estiver; se ela foi para "Concluídas" fechada, vai para o `<summary>`. A caixinha tem o id `task-check-<id>` só para ser achada; nada depende de o id ser sequencial.
- **Mensagem ao salvar:** "Não foi possível salvar. Tente de novo." fica no topo fixo, para ser vista com a lista rolada, e some no próximo toque numa caixinha. O `catch` do `loadPlayer` passou a mostrar a linha de erro de novo, que um sucesso anterior tinha escondido.
- **Seções:** "Atrasadas" e "Hoje" com título, para as pendentes não parecerem atrasadas. Cada seção some vazia, e "Concluídas (N)" some com zero. A data da atrasada aparece como "Marcada para 01/11/2026", com o ano. A concluída que vale 0 mostra "+0 XP".
- **"Concluídas" aberta ao recarregar:** sai sem código. O JavaScript esvazia e preenche só as `<ul>`, e o `<details>` continua o mesmo elemento.
- **`[hidden]` com `display: none !important`** no CSS, para uma classe com `display` não fazer aparecer um elemento escondido.
- **HTML sem código dentro:** um teste lê os `.html` de `frontend/` com o `HTMLParser` da biblioteca padrão e recusa `<script>` sem `src` ou com código dentro, atributos `on...` e estilo no HTML (`<style>` e `style=`). A CSP bloqueia tudo isso no navegador, mas em silêncio. O `element.style` no JavaScript não é afetado.

**Fora da etapa 10.2:**

- Separar o `app.js` por tela, com vários `<script defer>` na ordem certa, sem módulos: decidir na tarefa 11, quando o formulário chegar. Decidido na divisão da tarefa 11: entra na etapa 11.2. Resolvido na etapa 11.2.
- O título "Hoje" passa a mostrar o dia escolhido na etapa 10.4. Resolvido na etapa 10.4.
- O ✎ das notas é provisório: a tarefa 13 troca pelo ícone definitivo, local.

**Decisões da etapa 10.3 (plano `10.3-cartao-com-adiar.md`):**

- **O botão do título:** um `<button>` com `aria-expanded` envolve o título, o ✎, a data da atrasada e o "+N XP", com 48 px de altura no mínimo e a largura do cartão. A caixinha continua fora dele. Abrir e fechar só muda o cartão (`aria-expanded` e `hidden`), sem desenhar a lista de novo, então o foco fica no botão tocado.
- **Um cartão aberto por vez:** abrir um fecha o outro. Uma variável só (`openTaskId`) guarda o estado, e com um aberto só um Adiar aparece por vez.
- **Aberto ao recarregar:** a lista é desenhada de novo depois de toda gravação e na volta ao app, e o cartão aberto nasce aberto. A concluída continua aberta em "Concluídas". Se a tarefa sumiu da lista, nenhum cartão fica aberto, para ela não reaparecer aberta outro dia.
- **O que o cartão aberto mostra:** notas, se houver, e o Adiar; na concluída, só as notas. A concluída sem notas mostra "Sem notas.", para não abrir vazia antes do Editar da tarefa 11. As notas entram por `textContent`, com `white-space: pre-wrap`, que mantém as quebras de linha.
- **Confirmação do Adiar (regra da seção 6.2):** o texto vira "Confirmar adiar (−25% XP)" e volta sozinho em 5 segundos, ou ao tocar em qualquer outra coisa da página (um ouvinte de `click` no `document`), ao abrir ou fechar um cartão e ao desenhar a lista de novo.
- **Toque duplo no Adiar (regra 11):** no Chrome do Android, com `width=device-width`, o toque duplo não dá zoom e vira dois cliques, o que passaria pela confirmação inteira sem querer. Por isso, no primeiro meio segundo da confirmação o toque é ignorado. O botão não muda de aparência nem perde o foco nesse tempo. Decidido no plano `10.3-cartao-com-adiar.md`.
- **Adiar:** manda em `shown_due_date` a `due_date` da lista, com corpo em JSON e `fetch` no modo padrão. Depois, a lista e o topo recarregam juntos. Uma gravação por vez vale para a caixinha e o Adiar juntos; os botões do título continuam livres.
- **Aviso:** "Adiada para 06/11/2026: Ler 30 páginas", no topo fixo, com a data da resposta do servidor, só formatada. O título vai junto porque o cartão sai da lista de hoje. Some em 10 segundos ou na próxima gravação.
- **Tarefa travada:** o Adiar fica `disabled`, com "Data travada: esta tarefa chegou ao limite de adiamentos." embaixo. O texto não cita o número 3, para não ser um segundo lugar com a regra, e vale também para a trava por dias de atraso.
- **Os 409:** a tela desatualizada recarrega sem mensagem. O da última data possível é reconhecido depois de recarregar, sem ler o texto da resposta: cada recusa da rota deixa um rastro diferente na lista nova (a concluída vai para "Concluídas", a travada volta com `due_date_locked`, a desatualizada some ou volta com outra data). Se a tarefa volta pendente, com a mesma `due_date` e sem trava, só sobra a última data, e o topo mostra "Esta tarefa já está na última data possível e não pode ser adiada." A comparação é de igualdade entre dois textos do servidor, sem conta de data. Um campo novo na API foi descartado: mexeria no back-end numa etapa de front, por um caso que, na tela de hoje, só acontece em 31/12/9999.

**Fora da etapa 10.3:**

- O "Sem notas." da concluída sai na tarefa 11, quando o Editar ocupar esse lugar. Decidido na divisão da tarefa 11: sai na etapa 11.4. Resolvido na etapa 11.4.
- O toque no cartão da semana fica para a tarefa 12. Decidido na divisão da tarefa 12: etapa 12.3.

**Decisões da etapa 10.4 (plano `10.4-navegar-entre-os-dias.md`):**

- **A barra:** seta "‹", campo de data, seta "›" e "Hoje", num `<nav>` fora da lista, para continuar na tela enquanto o dia carrega e no aviso de erro. As setas pedem os vizinhos que vieram da API e ficam bloqueadas quando o vizinho vem `null` (`0001-01-01` e `9999-12-31`) ou quando não há dia na tela. O "Hoje" fica sempre livre.
- **Calendário (decisão minha):** `<input type="date">`, que mostra sempre o `day` da resposta. O `value` dele é `""` ou uma data real `AAAA-MM-DD`, o mesmo formato da API, e vai para `GET /tasks/day/{data}` sem conta. Campo vazio (limpo ou com a data incompleta) não pede nada, e o campo volta ao dia da tela quando perde o foco; não volta na hora, para não atrapalhar quem digita. O Chrome aceita anos de até 6 dígitos, e o Python só vai até 9999, então o campo tem `min="0001-01-01"` e `max="9999-12-31"`, e fora deles o próprio navegador marca `validity.valid` como falso e nada é pedido. Sem isso, o 422 deixaria a tela num erro que o "Tentar de novo" repetiria.
- **Qual dia recarregar:** a variável `dayPath` guarda o caminho do pedido (`tasks/today` ou `tasks/day/AAAA-MM-DD`), não uma data. Navegar muda o caminho; recarregar (depois de gravar, na volta ao app e no "Tentar de novo") pede o mesmo caminho. Em hoje, continua `/tasks/today`, pela virada da meia-noite. Uma resposta com `is_today: true`, vinda de uma seta ou do calendário, volta o caminho para `tasks/today`. Se navegar falha, o "Tentar de novo" pede o dia pedido.
- **Título e dia vazio:** em hoje, "Hoje" e "Nenhuma tarefa para hoje."; nos outros dias, o `day` por extenso ("Sexta-feira, 06/11/2026", com `Intl.DateTimeFormat` em `timeZone: "UTC"` e a primeira letra em maiúscula) e "Nenhuma tarefa neste dia.". As atrasadas continuam só em hoje, porque só vêm do servidor nesse caso.
- **A tarefa que sai da tela:** depois de concluir ou desmarcar com sucesso e recarregar, se a tarefa não está mais na lista desenhada, o topo avisa para onde ela foi: "Foi para as Concluídas de hoje: Ler 30 páginas" ou "Desmarcada, voltou para 06/11/2026: Ler 30 páginas", com o título e a `due_date` da resposta da rota, só formatada. A tela não prevê se ela vai sumir: olha o resultado. O aviso ao desmarcar foi decisão minha no plano. O aviso do Adiar e esses dois usam a mesma linha (`#notice`).
- **Toques rápidos:** só o pedido mais recente é desenhado, com o controle da 10.2. Enquanto o dia novo não chega, as setas apontam para os vizinhos do dia que está na tela, então um toque duplo anda um dia só, e não dois sem querer (no Android, o toque duplo vira dois cliques). A lista antiga fica na tela até a nova chegar, sem "Carregando…", para a tela não piscar a cada toque.
- **Mudar de dia:** fecha o cartão aberto e cancela a confirmação do Adiar já no toque, também quando a mudança vem do teclado no calendário, sem clique. Não esconde o aviso nem a linha de erro do topo, que falam de uma ação que já aconteceu. Navegar durante uma gravação é permitido, porque só lê.
- **Cache dos arquivos do front:** sem `Cache-Control`, o Chrome guardava o CSS e o JavaScript por um prazo que ele mesmo inventa e os usava sem perguntar, e o app pareceu quebrado depois de uma mudança. Agora `FrontendFiles`, uma subclasse do `StaticFiles` em `main.py`, põe `Cache-Control: no-cache` em toda resposta de arquivo, inclusive no `304`. O navegador confere a `ETag` antes de usar a cópia. A API e a CSP não mudam. Um middleware precisaria adivinhar quais respostas são arquivos, por uma lista de caminhos da API que ficaria velha.
- **Celular e acessibilidade:** setas de 48 × 48 px com nome escondido da vista ("Dia anterior", "Dia seguinte"), "Hoje" e campo com 48 px de altura, campo com rótulo escondido ("Escolher o dia") e anel de foco. Em 360 px, a barra cabe numa linha (o campo fica com uns 138 px); com `flex-wrap`, o "Hoje" desceria de linha em vez de criar rolagem para o lado.

**Fora da etapa 10.4:**

- **Tarefa 14:** o service worker entrega os arquivos do cache dele, sem passar pelo `Cache-Control`, e quem renova o app instalado é o número de versão do cache (seção 6.5). O `no-cache` continua: quando o service worker novo se instala e baixa os arquivos, o download passa pelo cache comum do navegador, e sem o `no-cache` uma cópia velha poderia entrar no cache da versão nova.
- Ao chegar a `0001-01-01` ou `9999-12-31` pela seta, ela fica bloqueada e o navegador tira o foco dela.
- O `Intl` escreve o ano 1 como "01/01/1", sem os zeros. Só aparência, numa ponta que ninguém usa.

**Divisão da tarefa 11:**

A tarefa 11 mexe na API, cria o formulário e precisa de uma forma de cuidar dos tipos sem o `/docs`, então vira 7 etapas, feitas nesta ordem. Cada etapa tem plano próprio, em sessão nova, e só começa depois do commit da anterior. A divisão e as decisões abaixo estão no plano `11.1-api-do-formulario.md`.

| Etapa | Entrega | Arquivos |
| --- | --- | --- |
| 11.1 API do formulário | A resposta do dia ganha `new_task_due_date`. O `PUT` exige `shown_due_date` e grava num `UPDATE` condicional. Só back-end | `backend/app/routers/tasks.py`, `backend/tests/test_tasks.py` |
| 11.2 Separar o `app.js` | Arquivos por assunto, com vários `<script defer>` na ordem certa, sem módulos. Só move código, sem mudar comportamento. Um teste confere que todo `<script>` do `index.html` tem `defer` e existe | `frontend/js/*.js`, `frontend/index.html`, `backend/tests/test_frontend.py`, `CLAUDE.md` |
| 11.3 Criar tarefa (fecha o critério) | Botão "Nova tarefa"; formulário num `<dialog>` com título, data, dificuldade, cor, tipo e notas; tipos de `GET /task-types`; data de `new_task_due_date`; cor omitida até ser escolhida; erros 422 em português; aviso quando a tarefa nasce fora do dia da tela | `index.html`, `style.css`, `js/api.js`, `js/task-form.js`, `test_frontend.py`; só comentários em `js/day.js` e `js/top-bar.js` |
| 11.4 Editar tarefa | Botão Editar no cartão aberto, no lugar do "Sem notas."; formulário preenchido; data travada com `due_date_locked`; dificuldade e data travadas na concluída; `PUT` com todos os campos e `shown_due_date`; 409 recarrega a lista; aviso quando a tarefa sai da tela | os mesmos da 11.3 e `js/day.js` |
| 11.5 Excluir | "Excluir" dentro do formulário de edição, com confirmação em dois toques, como o Adiar; o `apiRequest` aceita a resposta 204, sem corpo; aviso "Excluída: …" | os mesmos da 11.4 |
| 11.6 Criar tipo no formulário | "Novo tipo" ao lado da escolha do tipo, por `POST /task-types`; o tipo novo já fica escolhido; o 409 de nome repetido aparece em português | os mesmos da 11.3 |
| 11.7 Tela de tipos | Uma tela pequena, também num `<dialog>`, que lista, renomeia (`PATCH`) e exclui (`DELETE`, com confirmação em dois toques e o aviso de que as tarefas ficam sem tipo) | `index.html`, `style.css`, `js/task-types.js` |

Por que esta ordem: a API vem primeiro, como na tarefa 10, para o formulário nascer sem conta de data e com a proteção pronta. A separação vem antes do formulário, para o diff da 11.2 só mover linhas e o formulário já nascer no arquivo dele. Criar vem antes de editar porque fecha o critério, e a edição reaproveita o formulário. Excluir fica dentro da tela de edição (seção 6.2). Os tipos ficam por último porque o formulário já funciona com os tipos que existem, e a 11.7 fecha a falta do `/docs` em produção antes da tarefa 17.

**Decisões da divisão da tarefa 11:**

- **Separar o `app.js` (etapa 11.2):** `js/api.js` (API e formatação), `js/top-bar.js` (topo e as mensagens do topo: `showSaveMessage`, `showNotice`, `hideNotice`, `hideMessages`), `js/day.js` (desenhar e buscar o dia, caixinha, cartão, Adiar e navegação), `js/task-form.js` (11.3), `js/task-types.js` (11.7) e `js/app.js` (início), nesta ordem, todos com `defer`. Sem módulos, os scripts comuns dividem o mesmo espaço de nomes; o código que roda ao carregar só enxerga o que veio dos arquivos anteriores. Uma `const` ou `let` repetida em dois arquivos impede o segundo de rodar, e uma `function` repetida troca a primeira sem aviso; um teste recusa os dois casos (corrigido na etapa 11.2).
- **Os dois formatos do 422 (etapa 11.3):** o `apiRequest` guarda o `detail` da resposta no erro. Texto (as rotas, já em português) aparece como veio. Lista (a validação automática, em inglês) vira uma frase com o nome do campo e o tipo do erro: "Título: não pode ficar vazio." (`string_too_short`), "Notas: no máximo 1.000 caracteres." (`string_too_long`, com o número de `ctx.max_length`, que vem do servidor) e "está inválida" para os outros. O campo fica com `aria-invalid` e recebe o foco. Sem `detail` legível, "Não foi possível salvar. Tente de novo.". O HTML não leva `required` nem `maxlength`, para os números ficarem só em `tasks.py`. Traduzir no servidor mudaria o formato do 422 de todas as rotas.
- **Cor padrão (etapa 11.3):** ao criar, o pedido omite `color` enquanto a cor não for escolhida, e o servidor aplica `DEFAULT_TASK_COLOR`; `null` dá 422. O `<input type="color">` abre mostrando a cor padrão escrita no HTML, e um teste compara esse valor com `DEFAULT_TASK_COLOR`. Ao editar, o `PUT` manda sempre a cor do campo. Um botão "Cor padrão" volta à cor padrão. O `style.backgroundColor` entra quando a cor pintar o cartão (tarefa 13).
- **"Sem notas." (etapa 11.4):** sai do HTML, do CSS e do JavaScript. A concluída aberta mostra as notas, se houver, e o Editar.
- **Tipos (etapas 11.3, 11.6 e 11.7, decisão minha):** o formulário escolhe num `<select>` entre "Sem tipo" e os tipos de `GET /task-types`, na ordem da API, com o nome por `textContent`. Criar tipo entra no formulário (11.6), e renomear e excluir, numa tela própria (11.7). Sem isso, depois da publicação não haveria como criar um tipo, porque o `/docs` fica desligado em produção.
- **Formulário (etapa 11.3):** um `<dialog>` aberto com `showModal()`, que prende o foco, deixa a lista de fundo sem toque, fecha com Esc e, no Chrome recente do Android, com o gesto de voltar. Conferir por USB. Dentro dele, um `<form>` com `novalidate`, sem `method` e sem `action`, só para o Enter salvar: o `submit` chama `preventDefault()` e grava por `fetch` no modo padrão (seção 6.7).
- **Valem para as etapas 11.3 a 11.7:** as regras da tela da tarefa 10 (48 px, 360 px sem rolagem para o lado, foco visível, nada que dependa de passar o mouse), `<template>` com `cloneNode`, uma gravação por vez, só o pedido mais recente desenhado, aviso quando a tarefa sai da tela e a data de hoje sempre vinda do servidor.

**Fora da divisão da tarefa 11:**

- O `DELETE` responde 204 sem corpo, e o `apiRequest` de hoje sempre lê o corpo como JSON. A etapa 11.5 corrige. Resolvido na etapa 11.5.
- Como a cor é livre, um fundo escuro deixaria o título ilegível quando a tarefa 13 pintar o cartão. Decidir na tarefa 13.

**Decisões da etapa 11.1 (plano `11.1-api-do-formulario.md`):**

- **Data sugerida (decisão minha):** `DayTasks` ganha `new_task_due_date`, o dia listado ou, se ele já passou, hoje, calculado em `build_day_tasks` com o mesmo "hoje" do resto da resposta (`max(day, today)`). Assim o formulário não compara datas, e a sugestão nunca é recusada como data anterior a hoje. Vem na resposta do dia, e não numa rota nova, porque o formulário abre a partir do dia que já está na tela.
- **`shown_due_date` na edição (decisão minha):** o `PUT` exige a data que o formulário mostrava, como o Adiar. A criação recusa o campo, como todo campo desconhecido: os campos comuns ficam em `TaskFields`, e `TaskInput` e `TaskUpdate` herdam dela.
- **Mudança de data:** é a que a pessoa fez no formulário, `due_date` diferente de `shown_due_date`. Mandar a data que o formulário mostrava não é mudança, então uma atrasada adiada em outro aparelho, editada com o formulário velho, recebe o 409 da tela desatualizada, e não o 422 da data anterior a hoje.
- **`UPDATE` condicional:** a edição grava numa instrução só, que vale apenas se a tarefa ainda tiver a data que o formulário mostrava (fecha a tela desatualizada e a corrida com o Adiar, que perderia um adiamento) e ainda estiver concluída ou pendente como foi lida no pedido (fecha a corrida com Concluir e Desmarcar, que deixaria data ou dificuldade nova numa tarefa concluída). `postponements` fica fora da condição porque só muda junto com a data. Se nada muda, 409 com `STALE_TASK_MESSAGE`, o mesmo texto do Adiar. Mesmo só o título é recusado se a tarefa foi concluída no meio da edição. Foi testado só no SQLite, como os outros `UPDATE` condicionais: conferir no PostgreSQL na tarefa 16.
- **Nada muda na `Task` lida antes do `UPDATE`:** os valores novos ficam em variáveis. Se o objeto lido mudasse, o SQLModel mandaria a mudança sozinho ao banco antes do `UPDATE` (autoflush), sem condição. Por isso `change_due_date` saiu.
- **Ordem das recusas:** 422 (corpo, data anterior a hoje, tipo), depois 404, depois os 409 do mais definitivo para o mais passageiro: dificuldade da concluída, data da concluída, data travada e tela desatualizada.
- **Tarefa excluída no meio da edição:** o `UPDATE` encontra 0 linhas e responde 409. A tela recarrega e a tarefa já não está lá.

**Decisões da etapa 11.2 (plano `11.2-separar-o-app-js.md`):**

- **Só muda o lugar:** os arquivos novos foram cortados do `app.js` por número de linha, sem redigitar nada. Uma conferência juntou os arquivos na ordem do `index.html` e comparou com o `app.js` de antes. As únicas diferenças são os cabeçalhos dos arquivos, os números das seções e cinco comentários que citavam esses números.
- **Os arquivos, nesta ordem, todos com `defer`:**
  - `js/api.js`: API e formatação;
  - `js/top-bar.js`: o topo e as mensagens do topo, que saíram da seção da caixinha;
  - `js/day.js`: desenhar e buscar o dia, caixinha, cartão, Adiar e navegação;
  - `js/app.js`: a antiga seção "Início", sem tirar nem pôr.
- **Por que `SAVE_ERROR_TEXT` ficou no `day.js`:** junto com `saving` e `disableTaskControls`, porque só a caixinha e o Adiar usam. O formulário pode usar de lá, porque só usa ao salvar, com tudo carregado.
- **Ordem obrigatória:** só o `app.js` por último, porque ao carregar ele já chama `loadPlayer` e `loadDay`. Os outros arquivos, ao carregar, só usam o HTML e nomes deles mesmos. A ordem dos três primeiros segue a direção de quem usa quem. Uma função pode chamar outra de um arquivo posterior, como `toggleTask` chama `refreshScreen`, porque só roda depois de um toque.
- **Toque entre dois scripts:** o navegador pode atender um toque antes de o próximo arquivo `defer` chegar. Nesse intervalo, as setas estão `disabled`, não há cartão e o aviso de erro está escondido. Só o "Hoje" e o calendário respondem, e os dois usam apenas o `day.js` e o `api.js`.
- **Seções por arquivo:** cada arquivo numera as próprias seções a partir de 1. Um comentário que cita a seção de outro arquivo diz qual é o arquivo ("seção 5 do day.js").
- **Testes:**
  - a CSP, o `no-cache` e o 304 passaram a valer para todo `.js` de `frontend/`, numa lista montada a partir da pasta;
  - todo `<script>` do `index.html` tem `defer` e aponta para um arquivo que existe;
  - os `.js` de `frontend/js` são exatamente os do `index.html`, sem repetição;
  - o `app.js` é o último;
  - nenhum nome é declarado no alto de dois arquivos.

**Decisões da etapa 11.3 (plano `11.3-criar-tarefa.md`):**

- **Botão:** "Nova tarefa", com 48 px e a largura toda, é o primeiro elemento de `#day-view`. Só aparece com um dia na tela, que traz `new_task_due_date`.
- **Formulário:** o `<dialog>` da divisão, com os campos na ordem da seção 6.2: Título, Data, Dificuldade, Cor (com "Cor padrão"), Tipo e Notas. Cada campo tem `<label for>` e um `name` igual ao campo da API. O "Salvar" é o único `submit`: Enter no Título salva, Enter nas Notas faz uma linha nova. A mensagem de erro fica dentro do formulário, porque o topo fica atrás do fundo escuro. Cada abertura começa vazia (`reset()`), também depois de um Cancelar, com o foco no Título (`autofocus`).
- **Dificuldade (decisão minha):** um `<select>` que abre em "Fácil" (`selected` no HTML). O servidor exige o campo e não tem padrão, e "criar só com título" precisa funcionar.
- **Cor:** o pedido só leva `color` depois que o campo muda (evento `input`). "Cor padrão" volta o campo ao `defaultValue`, o `value` escrito no HTML, e volta a omitir a cor. O JavaScript não tem a cor escrita.
- **Tipos:** pedidos a cada abertura, com o `<select>` bloqueado em "Sem tipo" até a resposta, e só o pedido mais recente preenche. Sem tipos cadastrados, fica só "Sem tipo", sem aviso. Se o pedido falha, o formulário continua utilizável, só com "Sem tipo" e o aviso "Não foi possível carregar os tipos. Dá para salvar sem tipo.".
- **`<option>` sem `<template>`:** cada tipo vira um `<option>` por `createElement`, com `textContent` e `value`. A regra do `<template>` vale para peças com estrutura, como o cartão; um `<option>` não tem estrutura.
- **Toque duplo no Salvar:** criar não é idempotente, e o servidor não tem proteção para isso. A gravação usa o `saving` do `day.js` (uma gravação por vez com a caixinha e o Adiar). O `submit` roda sem pausa até o `fetch`: `saving` vira verdadeiro e o "Salvar" fica bloqueado antes de o navegador atender o segundo toque, que cai num botão bloqueado; o Enter também não envia um formulário com o botão de envio bloqueado; e `saveNewTask` começa com `if (saving) return`. Conferido no Chrome com a rede lenta: clique duplo e Enter deram um `POST` só.
- **Esc e voltar durante a gravação:** o evento `cancel` é cancelado enquanto `saving`, e o "Cancelar" fica bloqueado. O Chrome só deixa cancelar uma vez por toque: dois Esc seguidos fecham o formulário (conferido). Nesse caso, um erro vai para a linha de erro do topo, e o que foi digitado se perde.
- **Os dois formatos do 422:** o `apiRequest` guarda o `detail` em `error.detail`. Texto aparece como veio, sem campo marcado, e o foco volta ao "Salvar". Lista vira uma frase por item com o rótulo do campo (`taskForm.elements.namedItem(loc[1])` e o texto do `<label>` dele): `string_too_short` dá "não pode ficar vazio.", `string_too_long` dá "no máximo N caracteres." com `ctx.max_length` formatado ("1.000"), e os outros dão "está inválida.". Pela tela, só chegam o título vazio ou longo, as notas longas e a data vazia ou inválida. O campo fica com `aria-invalid`, e o foco vai para o primeiro marcado na ordem do formulário. Item sem campo no formulário, rede caída ou erro sem `detail` legível dão "Não foi possível salvar. Tente de novo.". O formulário continua aberto e preenchido em todo erro.
- **Tipo excluído no meio:** o servidor responde 422 com o texto "Esse tipo de tarefa não existe.", e não 404.
- **Depois de um erro:** a lista de trás é recarregada, para liberar as caixinhas e os Adiar que a gravação bloqueou.
- **Depois de salvar:** o formulário fecha, a lista recarrega pelo `dayPath` (sem o topo, porque criar não muda XP), e o foco volta ao "Nova tarefa". Se a tarefa não está na lista desenhada, o topo mostra "Criada para 09/11/2026: Ler 30 páginas", com a data e o título da resposta do servidor, no `#notice`.
- **Virada da meia-noite:** a data sugerida de uma lista carregada ontem pode já ter passado. O servidor recusa com "A data não pode ser anterior a hoje.", o formulário fica preenchido e a pessoa troca a data. Recarregar o dia ao abrir obrigaria o formulário a esperar a lista ou a trocar uma data que a pessoa já mexeu. No celular, a volta ao app já recarrega o dia.
- **Regras só no servidor:** o HTML não leva `required`, `minlength`, `maxlength`, `pattern`, `min` nem `max`, e o JavaScript não tem nenhum número de regra. Quatro testes leem o `index.html`: a cor do campo é `DEFAULT_TASK_COLOR`; as dificuldades são `Difficulty`, na mesma ordem; os `name` são os campos de `TaskInput`, cada um com `<label>`; o `<form>` tem `novalidate`, sem `method` nem `action`, e nenhum limite nos campos.

**Fora da etapa 11.3:**

- Depois de um erro do tipo excluído, o `<select>` continua mostrando o tipo até o formulário ser aberto de novo. A etapa 11.7 pode recarregar a lista ao excluir. Na 11.7, a tela de tipos só abre com o formulário fechado, e o formulário busca os tipos a cada abertura; o caso continua só com a exclusão feita em outra aba.
- Em 360 × 740, o formulário inteiro passa um pouco da altura da tela, e o "Salvar" pode precisar de uma rolagem dentro do diálogo, maior ainda com o teclado aberto. A tarefa 13 pode apertar os espaços, e a posição do "Nova tarefa" também pode mudar nela.

**Decisões da etapa 11.4 (plano `11.4-editar-tarefa.md`):**

- **Um formulário, dois modos:** `openTaskForm(task)` recebe `null` no "Nova tarefa" e a tarefa da lista no Editar, guardada em `editingTask`. O título do formulário muda ("Nova tarefa" ou "Editar tarefa"), e a edição abre preenchida por `value`. `saveTask` grava por `POST /tasks` ou `PUT /tasks/{id}`; o resto (erros, uma gravação por vez, Esc durante a gravação) é o mesmo da 11.3. O `reset()` não mexe em `disabled`, então a função que trava os campos também os libera na criação.
- **Cartão:** o "Sem notas." saiu do HTML, do CSS e do JavaScript. A parte que abre tem as notas, se houver, e uma linha com Editar e Adiar lado a lado, com `flex-wrap` para o "Confirmar adiar (−25% XP)" descer de linha em 360 px. Na concluída, só o Adiar some. O Editar fica bloqueado durante uma gravação, como a caixinha e o Adiar.
- **Uma gravação por vez também ao abrir o formulário (decisão minha):** `openTaskForm` começa com `if (saving) return;`. Antes, depois de dois Esc durante uma gravação lenta, o "Nova tarefa" abria o formulário, e o fim da gravação anterior o fechava ou mostrava nele um erro que não era dele. O botão não fica com cara de bloqueado, porque não é desenhado de novo com a lista: o toque só não faz nada até a gravação terminar, o que se nota só com a rede lenta.
- **`shown_due_date`:** é a `due_date` de `editingTask`, a tarefa da lista desenhada quando o Editar foi tocado, e não muda enquanto o formulário está aberto, nem se a lista recarregar por trás. Nunca é o valor do campo Data: o campo é a data que se quer, e o `shown_due_date` é a data que se viu. Com as duas iguais, o servidor não veria mudança de data (sem conferir data passada e trava, sem contar o adiamento), e o `UPDATE` condicional recusaria toda mudança de data.
- **Tipo sem risco de apagar:** o corpo lê o `value` do `<select>`, então o campo mostra desde o começo o que vai no pedido. Na edição de uma tarefa com tipo, ele nasce numa opção "Tipo atual" com o id do tipo dela, bloqueada até a lista chegar. Salvar antes de os tipos chegarem, ou com o pedido falhando, mantém o tipo. Na falha, o aviso da edição é "Não foi possível carregar os tipos. Ao salvar, a tarefa continua com o tipo que já tem."; o da criação não mudou. Se o tipo da tarefa não está na lista (`selectedIndex === -1`), ele foi excluído depois de a lista do dia ser desenhada: o campo vai para "Sem tipo", com "O tipo desta tarefa não existe mais.", que é o que o banco já tem.
- **Campos travados:** a data fica `disabled` com `due_date_locked`, com o mesmo texto do cartão; na concluída, `completed` decide, e a data e a dificuldade ficam `disabled`, cada uma com "Tarefa concluída: desmarque para mudar ...". Os campos travados continuam com o valor da tarefa e vão no pedido (o corpo lê o `value` direto, e um campo bloqueado também vai), e o mesmo valor não é mudança (seção 6.1). `.form-field :disabled` dá a eles a cara de bloqueados, que a regra dos campos cobria. Os textos não usam `aria-describedby`, porque um elemento escondido apontado por ele continua sendo lido.
- **Data nova e XP (decisão minha):** embaixo da Data, na pendente não travada, um texto fixo: "Mudar a data para depois conta como adiamento: −25% XP. Antecipar não conta.". Se a Data está diferente da original e não está vazia (comparação de igualdade entre dois textos, não conta de data), o primeiro Salvar não grava: o botão vira "Confirmar nova data", na cor de aviso, e aparece uma mensagem com `role="alert"`. O segundo toque grava, e no primeiro meio segundo é ignorado (`DOUBLE_TAP_GUARD_MS`, o mesmo do Adiar). Mexer na Data, abrir o formulário ou gravar desfaz a confirmação, que não volta sozinha com o tempo. A tela não sabe se a data nova é depois ou antes, então pede confirmação nos dois casos.
- **Resultado no topo (decisão minha):** com a data mudada, o topo mostra "Adiada para 09/11/2026 (−25% XP): Ler 30 páginas" se o `postponements` da resposta é diferente do da lista (ele nunca diminui), ou "Data mudada para 08/11/2026: Ler 30 páginas" se ficou igual. O aviso aparece mesmo se a tarefa continua na tela. Sem mudança de data, não há aviso. Sem campo novo na API.
- **Cor e notas:** o `<input type="color">` aceita a cor em maiúsculas do servidor e a guarda em minúsculas; o servidor grava de novo em maiúsculas. A edição manda sempre a cor do campo, e "Cor padrão" manda a cor do HTML, que um teste já compara com `DEFAULT_TASK_COLOR`. Notas `null` viram campo vazio, e campo vazio vira `null` no servidor.
- **Os 409 e o 404:** o formulário fica aberto, com o que foi digitado, e a lista de trás recarrega. O texto do servidor aparece como veio, e a tela acrescenta uma frase fixa pelo código da resposta, sem ler o texto: no 409 (tela desatualizada, concluída ou travada em outro lugar), "A lista já foi atualizada: cancele e abra a tarefa de novo para ver como ela está agora."; no 404 (excluída), "Ela foi excluída em outro lugar.". Salvar de novo dá a mesma resposta.
- **Depois de salvar:** o formulário fecha, a lista recarrega pelo `dayPath` (sem o topo, porque editar não muda o XP), e o cartão continua aberto se a tarefa ainda está na tela. O foco vai para o Editar dela ou, se ela saiu, para o "Nova tarefa". Ao fechar a edição de qualquer jeito, o evento `close` do `<dialog>` faz o mesmo, porque o Editar que abriu pode ter sido trocado se a lista foi desenhada de novo.
- **Teste:** os campos de `TaskUpdate` são os `name` do formulário mais `shown_due_date`. O resto do comportamento é JavaScript, que o projeto não tem como testar sem dependência nova: fica para a conferência no Chrome sem janela e para o roteiro manual.

**Fora da etapa 11.4:**

- **Edição de outros campos em dois lugares:** o `PUT` só confere a data e o "concluída ou não" (etapa 11.1). Título, notas, cor, tipo e dificuldade mudados em outro aparelho são substituídos, sem aviso, por um formulário velho salvo depois. Registrado por decisão minha.

**Decisões da etapa 11.5 (plano `11.5-excluir-tarefa.md`):**

- **O 204:** o `apiRequest` devolve `null` quando a resposta é 204, sem ler corpo. As outras rotas respondem 200 ou 201 com JSON e não passam por esse caminho. Sem isso, o `json()` daria erro, e a tela diria "não foi possível" depois de o servidor já ter excluído.
- **Uma confirmação em dois toques só (regra 11, decisão minha):** as funções do Adiar, no `day.js`, passaram a servir a qualquer botão: `handleConfirmClick(button, confirmLabel, action)`, `startConfirmation`, `cancelConfirmation` e `CONFIRM_TIMEOUT_MS`, com os mesmos 5 segundos e o mesmo `DOUBLE_TAP_GUARD_MS`. O botão volta ao texto que tinha antes, e `POSTPONE_LABEL` saiu. O Adiar e o Excluir usam esse mecanismo; a confirmação da data nova (11.4) continua à parte, sem tempo. A troca de nome tocou o `app.js`, fora dos arquivos da divisão, numa linha só.
- **O que desfaz a confirmação do Excluir:** 5 segundos; um toque em outra coisa (o ouvinte de clique do `document`, que pega também os cliques dentro do `<dialog>`); mexer num campo, também pelo teclado (evento `input` no `<form>`); fechar o formulário de qualquer jeito (evento `close`) e abrir de novo; a lista desenhada de novo por trás. Armar o Excluir desfaz a confirmação da data, e tocar no Salvar (ou o Enter, que o navegador transforma num clique no Salvar) desfaz a do Excluir.
- **Lugar e visual:** uma área só da edição (`#task-form-delete-area`), depois de Cancelar e Salvar, com 24 px e uma linha fina antes, e o botão à esquerda, do lado oposto ao Salvar. O botão tem `type="button"`, porque um `<button>` sem `type` dentro do `<form>` salvaria a edição; um teste confere. `.button.is-danger` usa a cor de erro na borda e no texto e, pedindo confirmação, no fundo, com texto branco (7,5 para 1). Textos: "Excluir" e "Confirmar exclusão".
- **O XP, com texto fixo sempre à vista acima do botão:** na pendente (inclusive a atrasada), "Excluir apaga a tarefa de vez e não muda o seu XP."; na concluída, "Excluir apaga a tarefa de vez, mas o XP que ela deu continua no seu total. Para tirar esse XP, desmarque a tarefa antes de excluir.". Escolhido por `completed`. Fica à vista, e não só na confirmação, para os 5 segundos não apressarem a leitura.
- **Os erros:** o 404 (excluída em outro lugar) fecha o formulário, recarrega a lista e mostra no topo "Já tinha sido excluída em outro lugar: …", reconhecido por `error.status`. Rede caída ou erro 500: "Não foi possível excluir. Tente de novo." dentro do formulário, que fica aberto com o que foi digitado, o botão volta a "Excluir" e recebe o foco, e a lista de trás recarrega. Com o formulário fechado por dois Esc, o erro vai para a linha de erro do topo. O Esc e o voltar durante a exclusão seguem a regra da 11.3.
- **Depois de excluir:** o formulário fecha, a lista recarrega pelo `dayPath`, o topo não recarrega (excluir não muda o XP, seção 4.3), e o topo mostra "Excluída: Ler 30 páginas" com o título da lista (`editingTask.title`), e não o digitado e não salvo. O `DELETE` não leva corpo: a edição não salva some junto. O foco vai para o "Nova tarefa" ou, se a lista não carregou, para o "Tentar de novo" (`focusAfterDelete`).
- **Uma gravação por vez:** `deleteTask` segue o molde do `saveTask` (`if (saving) return;`, tudo bloqueado antes do `await`), e o `saveTask` passou a bloquear também o Excluir.
- **Teste:** `test_only_save_submits_the_task_form` confere que todo `<button>` do formulário tem `type` e que só o Salvar envia. O resto é JavaScript, conferido no Chrome sem janela e no roteiro manual.

**Fora da etapa 11.5:**

- **Foco quando a lista não carrega, na criação e na edição:** o `saveTask` manda o foco para o "Nova tarefa" mesmo quando ele está escondido pelo aviso de erro. Só o Excluir trata esse caso.
- **Toque duplo no Adiar em 360 px (vem da 11.4):** o primeiro toque troca "Adiar" por "Confirmar adiar (−25% XP)", que não cabe ao lado do Editar e desce de linha (`flex-wrap`). O segundo toque de um toque duplo cai no espaço vazio onde o botão estava e desfaz a confirmação. Nada é adiado sem querer, mas o botão volta a "Adiar" em vez de ficar armado. Numa tela larga, o comportamento é o da 10.3. Achado na conferência da 11.5; decidir depois.

**Decisões da etapa 11.6 (plano `11.6-criar-tipo-no-formulario.md`):**

- **Desenho:** um botão "Novo tipo" ao lado do `<select>` do Tipo (`.form-type-row`), com `aria-expanded`, abre uma área logo embaixo (`#task-form-new-type-area`, `.form-new-type`) com o campo "Nome do tipo novo", o lugar do erro, um texto fixo e os botões "Desistir" e "Criar tipo". "Desistir", e não "Cancelar", porque o "Cancelar" do formulário fecha tudo. Os três botões têm `type="button"`. O campo do nome não tem `name`: não é campo da tarefa e não vai no pedido dela. Foco: abrir vai para o campo do nome; criar vai para o `<select>`, com o tipo novo escolhido, e fecha a área; um erro volta ao campo do nome; Desistir volta ao "Novo tipo". O Esc fecha o formulário inteiro, como antes. Em 360 px, o `<select>` encolhe (`min-width: 0`), e um nome longo aparece cortado no `<select>` fechado.
- **O Enter no campo do tipo novo, com duas barreiras (decisão minha):** dentro do `<form>`, o Enter num campo de texto faz o navegador enviar o formulário (envio implícito), e o `submit` salvaria a tarefa. A primeira barreira é um ouvinte de `keydown` no campo: Enter chama `preventDefault()` e cria o tipo. A segunda fica no começo do ouvinte de `submit`, antes da confirmação da data: se `document.activeElement` é o campo do nome, cria o tipo e para, sem salvar. Motivo: o teclado do Android, no meio de uma palavra sugerida (composição), pode mandar a tecla de outro jeito, e o `keydown` não a reconheceria. No Chrome, tocar no Salvar põe o foco nele, então só um Enter no campo envia com o foco ali. As duas não criam o tipo duas vezes: com o `keydown`, o envio nem acontece; e a segunda chamada pararia no `if (saving)`. Conferir por USB, com o teclado de verdade.
- **Os erros do tipo ficam só na área dele** (`#task-form-new-type-error`, com `role="alert"`), pelo `showNewTypeError`, nunca no `#task-form-error`. O 422 (`loc` `["body", "name"]`) usa o `fieldErrorText` da 11.3 com o rótulo "Nome do tipo novo": "não pode ficar vazio." (vazio ou só espaços) e "no máximo N caracteres." com o `ctx.max_length` do servidor. O 409 aparece como veio ("Já existe um tipo com esse nome."; desde a etapa 11.6a, o texto cita o tipo que já existe: "Já existe um tipo com esse nome: Exercício."). Rede caída ou nada legível: "Não foi possível criar o tipo. Tente de novo.". Nos erros sobre o nome, o campo fica com `aria-invalid`. Nada do que foi digitado na tarefa muda, e um erro da tarefa que já estava na tela continua. O `clearFormErrors` também apaga o erro do tipo, porque já tira o `aria-invalid` de todo o formulário.
- **Depois de criar:** a opção entra no fim do `<select>` com a resposta do `POST` (`textContent` e `value`), sem pedir a lista de novo, e fica escolhida. A API ordena por `created_at`, e o tipo novo é o mais novo; na próxima abertura, a lista vem de novo da API. O "Novo tipo" nasce bloqueado a cada abertura e só fica livre quando o pedido mais recente dos tipos chega com sucesso; e um pedido novo dos tipos só começa ao abrir o formulário, o que não acontece durante uma gravação. Então nenhum `GET /task-types` a caminho apaga o tipo novo. Se a lista não carrega, o "Novo tipo" fica bloqueado naquela abertura.
- **Uma gravação por vez:** `createTaskType` segue o molde do `saveTask`: `if (saving) return;`, tudo bloqueado antes do `await` (Salvar, Cancelar, Excluir, Criar tipo e Desistir; o campo do nome fica `readOnly`, que mantém o foco), as duas confirmações desfeitas, `disableTaskControls()` e `hideMessages()`; no fim, tudo livre e `loadDay()`, para liberar o que ficou bloqueado na lista. O `saveTask` e o `deleteTask` passaram a bloquear também o "Criar tipo". Com dois Esc durante a criação, o resultado vai para o topo: "Tipo criado: …" ou "Não foi possível criar o tipo. Tente de novo.".
- **Cancelar a tarefa depois de criar o tipo:** o tipo continua existindo, ao criar e ao editar uma tarefa. A área diz isso antes do toque, com texto fixo: "O tipo é criado ao tocar em 'Criar tipo' e continua existindo mesmo que você cancele a tarefa.".
- **Testes:** os dois testes que comparam os campos do formulário com `TaskInput` e `TaskUpdate` passaram a olhar só os campos com `name`; `test_new_type_field_is_not_a_task_field` exige que o único campo sem `name` seja o do tipo novo; `test_only_save_submits_the_task_form` exige o "Criar tipo"; `test_type_name_errors_have_the_shape_the_form_reads` confere o formato do 422 que a tela lê; `test_type_name_limit_is_only_on_the_server` confere que `MAX_TASK_TYPE_NAME_LENGTH` não aparece nos `.js` nem no `index.html`. O resto é JavaScript, conferido no Chrome sem janela e no roteiro manual.

**Fora da etapa 11.6:**

- **Tipo criado sem querer:** só sai pela tela de tipos, na etapa 11.7. Até lá, só pelo `/docs`, no desenvolvimento. Resolvido na etapa 11.7.
- **Nome digitado e não criado:** com a área aberta e um nome digitado, o Salvar grava a tarefa sem esse tipo, e o nome some. O texto fixo da área avisa que o tipo só é criado pelo "Criar tipo".

**Decisões da etapa 11.6a (plano `11.6a-nomes-de-tipo-sem-acento.md`):**

- **A regra (decisão minha):** no teste da 11.6, "Exercício" e "exercicio" foram aceitos como tipos diferentes. Na comparação de nomes, os acentos deixaram de contar, além de maiúsculas e minúsculas (seção 6.1). O nome continua gravado como foi digitado.
- **A chave de comparação:** `name_key`, em `task_types.py`, faz `casefold()`, separa as letras acentuadas em letra mais marca (`unicodedata.normalize("NFD", ...)`) e tira as marcas (`unicodedata.combining`). Um "í" digitado numa parte só e um "i" seguido do acento combinante dão a mesma chave. O `casefold` vem antes porque pode criar uma marca nova (o "İ" turco vira "i" + ponto). NFD, e não NFKD, porque o NFKD também trocaria "²" por "2" e "ﬁ" por "fi", o que vai além da regra. Só biblioteca padrão, sem dependência nova.
- **Onde fica:** em `task_types.py`, porque só esse arquivo compara nomes de tipo, e nome de tipo não é regra do jogo (regra 9 do `CLAUDE.md`).
- **A conferência:** `name_is_taken` virou `ensure_name_is_free`, que responde 409 sozinha, no molde das `ensure_...` de `tasks.py`, no criar e no renomear. O `ignored_id` continua deixando um tipo trocar a caixa ou o acento do próprio nome. A busca segue a ordem da lista (`created_at`, depois id), para a mensagem citar sempre o mais antigo quando dois tipos antigos tiverem a mesma chave.
- **Nos dois bancos:** a comparação é no Python. O banco só entrega os tipos num `SELECT` comum, então não há coluna nova nem migração, e a tarefa 16 não muda. Comparar no banco não ficaria igual nos dois: o `lower()` do SQLite não mexe em letras acentuadas, e tirar acentos no PostgreSQL pede a extensão `unaccent`. Cada `POST` e `PATCH` lê todos os tipos, como antes; num app de uma pessoa só, são dezenas. Dois pedidos ao mesmo tempo com o mesmo nome ainda podem passar os dois, limite aceito na tarefa 4.
- **A mensagem do 409:** "Já existe um tipo com esse nome: Exercício.", com o nome como foi gravado. A tela da 11.6 mostra o texto como veio, por `textContent`; no `task-form.js`, só um comentário mudou.

**Fora da etapa 11.6a:**

- **Pares antigos:** tipos que a regra antiga aceitava e a nova considera iguais ficam como estão. Renomear um deles para qualquer nome com a mesma chave, inclusive o próprio nome sem mudança, recebe o 409, porque o `ignored_id` ignora o próprio tipo, mas não o outro do par. Renomear para outro nome e excluir funcionam. A tela de tipos (etapa 11.7) é onde se junta ou corrige um par assim, e ela precisa decidir o que mostrar quando salvar sem mudar o nome recebe esse 409. Resolvido na etapa 11.7: salvar sem mudar o texto não manda o `PATCH`, e o par se corrige renomeando um dos dois para outro nome ou excluindo um, com a contagem de tarefas à vista.
- **Letras sem marca separada:** "ø", "ł", "æ" e "đ" não são letra mais marca no Unicode e continuam diferentes de "o", "l", "ae" e "d". Não aparecem no teclado em português.
- **Nome decomposto e o limite de 50:** cada acento de um nome decomposto conta um caractere a mais no limite. O teclado do Android manda o acento junto da letra, então isso só aparece com texto colado. O nome continua gravado como veio.

**Decisões da etapa 11.7 (plano `11.7-tela-de-tipos.md`):**

- **Onde abre (decisão minha):** um botão "Tipos de tarefa", com a largura toda e 48 px, no fim do `<main>`, fora do `#day-view`: aparece mesmo quando o dia não carrega e nunca é desenhado de novo, então o foco volta para ele quando a tela fecha. A tela abre só a partir da tela principal, nunca de dentro do formulário de tarefa. Um `<dialog>` por cima de outro traria o Esc e o gesto de voltar fechando um ou os dois, o risco do Enter salvar a tarefa (a armadilha da 11.6), o `<select>` do formulário com a lista velha, o foco voltando para dentro do formulário e duas telas dividindo o `saving`. O `<dialog>` de tipos fica no HTML como irmão do formulário, e um teste confere. Ela abre com `if (saving) return;`, como o `openTaskForm`, e o foco vai para o "Fechar", no alto, ao lado do título. O Esc e o voltar fecham, menos durante uma gravação (o evento `cancel` é cancelado e o "Fechar" fica bloqueado).
- **Contagem no servidor (decisão minha):** o `GET /task-types` devolve, em cada tipo, `task_count`: quantas tarefas usam o tipo, pendentes e concluídas. `TaskTypeView` é a resposta da lista (os campos do tipo escritos de novo, porque herdar de um modelo com tabela não tem suporte), e `task_count_by_type` conta numa consulta só, com `func.count()` e `group_by`, no molde do `xp_earned_by_task`. O `POST` e o `PATCH` continuam devolvendo o tipo sem contagem, e o formulário de tarefa ignora o campo novo. A tela só formata o número e escolhe "1 tarefa" ou "3 tarefas". Por isso a etapa mexeu no back-end, fora dos arquivos da divisão.
- **A lista:** uma linha por tipo, de um `<template>` com `cloneNode`, na ordem da API, com o nome por `textContent` (e por `value` no campo). A linha mostra o nome, a contagem e o "Editar", que leva o nome num texto escondido da vista para o leitor de tela. Estados: "Carregando tipos…", "Não foi possível carregar os tipos." com "Tentar de novo" (que recebe o foco) e "Nenhum tipo cadastrado.". Sempre à vista: "Para criar um tipo, use o "Novo tipo" no formulário da tarefa.". O resultado da última gravação aparece numa linha dentro da tela (`#task-types-notice`), porque o topo fica atrás do fundo escuro.
- **Uma linha em edição por vez:** `editingTypeId` guarda qual, e a lista é desenhada de novo a partir de `shownTypes` e dessa variável, como o cartão aberto da 10.3. A edição tem um `<form>` próprio (`novalidate`, sem `method` nem `action`) com "Nome do tipo", o erro, "Desistir" e "Salvar nome", e embaixo a área do Excluir. O Excluir fica dentro da edição, sozinho na linha, e não ao lado do "Editar": lado a lado, o "Confirmar exclusão" desceria de linha em 360 px, e o segundo toque de um toque duplo cairia no vazio (o problema do Adiar em "Fora da etapa 11.5").
- **O Enter:** o campo fica no `<form>` da própria linha, fora do formulário de tarefa. O Enter envia esse `<form>`, que renomeia o tipo; é o caminho que o teclado do Android respeita até no meio de uma palavra sugerida, sem precisar de `keydown`. Dois testes conferem que só o "Salvar nome" envia e que a tela de tipos não está dentro do formulário de tarefa.
- **Renomear:** se o texto do campo é igual ao nome que veio da API (igualdade de textos, sem `trim`, porque cortar espaços é regra do servidor), não manda nada: só fecha a edição. Assim, num par antigo da 11.6a, salvar sem mudar não recebe o 409. O `renameType` segue o molde do `createTaskType`. Os erros aparecem embaixo do campo, que mantém o texto e recebe o foco: o 422 pelo `fieldErrorText` da 11.3 ("Nome do tipo: não pode ficar vazio.", "no máximo N caracteres." com o `ctx.max_length`), o 409 como veio ("Já existe um tipo com esse nome: Exercício."), e o resto com "Não foi possível renomear o tipo. Tente de novo.". O 404 tira o tipo da lista, com "Esse tipo já tinha sido excluído em outro lugar: …", e o foco vai para o "Fechar". Depois de renomear, o nome da resposta do servidor entra em `shownTypes`, sem pedir a lista de novo: um `GET` que chegasse depois apagaria o que estivesse sendo digitado em outra linha. A ordem não muda, porque vem do `created_at`.
- **O par antigo:** a tela não acha os pares sozinha (precisaria da chave do nome no JavaScript). Os dois aparecem na lista, cada um com a sua contagem, e a correção é renomear um para outro nome ou excluir o menos usado. Trocar só a caixa ou o acento de um deles recebe o 409, que cita o outro.
- **Excluir:** confirmação em dois toques com o `handleConfirmClick` da 11.5 e o mesmo `CONFIRM_DELETE_LABEL` ("Confirmar exclusão"), desfeita pelo tempo, por um toque em outra coisa, por digitar no campo, pelo "Desistir", pelo "Salvar nome", ao fechar a tela e ao desenhar a lista de novo. Texto fixo acima do botão: "Excluir este tipo não apaga nenhuma tarefa: as tarefas com ele ficam sem tipo.", e a contagem ("3 tarefas vão ficar sem tipo."). Depois: o tipo sai de `shownTypes`, "Tipo excluído: Leitura. Nenhuma tarefa foi apagada." e o foco no "Fechar". O 404 segue como o sucesso, com "Já tinha sido excluído em outro lugar: …". Rede caída ou 500: "Não foi possível excluir o tipo. Tente de novo." na área do Excluir, que recebe o foco, com a edição aberta.
- **A lista do dia:** renomear e excluir terminam com `loadDay()`, que solta o que o `disableTaskControls()` bloqueou. No excluir, ele também é o que faz as tarefas do tipo voltarem com `task_type_id: null`, para o Editar delas abrir em "Sem tipo", sem o aviso de tipo excluído.
- **Uma gravação por vez:** renomear e excluir começam com `if (saving) return;` e bloqueiam o "Fechar" e todos os botões da lista antes do `await`, com o campo em `readOnly`. Com a tela fechada por dois Esc no meio da gravação, o resultado vai para o topo (`showNotice` ou `showSaveMessage`), como no criar tipo da 11.6.
- **Arquivos fora da divisão:** além do back-end da contagem, comentários no `day.js`, no `app.js`, no `top-bar.js` e no `task-form.js` (este último avisa que `fieldErrorText` e `CONFIRM_DELETE_LABEL` também são usados pelo `task-types.js`). Nenhuma linha de código desses quatro mudou. O erro de renomear tem função própria (`showRenameError`), parecida com o `showNewTypeError`, para o criar tipo continuar exatamente igual.
- **Testes:** `test_list_counts_the_tasks_of_each_type` e `test_list_count_follows_the_task_type`, em `test_task_types.py`; `test_rename_changes_the_name` passou a esperar o `task_count` na lista. Em `test_frontend.py`: o formato do 422 do `PATCH`, todo `<form>` sem regra no HTML, só o "Salvar nome" enviando o `<form>` da linha e a tela de tipos fora do formulário de tarefa. O resto é JavaScript, conferido no Chrome sem janela e no roteiro manual.

**Fora da etapa 11.7:**

- **Contagem do momento:** o número vale para quando a tela abriu. Uma tarefa criada ou mudada em outra aba só aparece na contagem na próxima abertura.
- **Pares e junção:** a tela não acha sozinha os tipos com o mesmo nome pela regra da 11.6a e não junta dois tipos movendo as tarefas de um para o outro. Excluir um tipo deixa as tarefas dele sem tipo, e o novo tipo é escolhido tarefa por tarefa.
- **Volta ao app:** o `visibilitychange` recarrega o dia e o topo, mas não a lista de tipos aberta. Um tipo mudado em outro aparelho aparece pelos 404 e 409, ou ao abrir de novo.
- **Esc na edição:** o Esc e o gesto de voltar fecham a tela inteira, até no meio de uma edição, e o que foi digitado se perde.

**Divisão da tarefa 12:**

A tarefa 12 mexe na API, cria a segunda visão do app e precisa ligar as duas, então vira 4 etapas, feitas nesta ordem. Cada etapa tem plano próprio, em sessão nova, e só começa depois do commit da anterior. A divisão e as decisões abaixo estão no plano `12.1-api-da-semana.md`.

| Etapa | Entrega | Arquivos |
| --- | --- | --- |
| 12.1 API da semana | `GET /tasks/this-week`. A resposta da semana vira um objeto com `is_current_week`, `previous_week`, `next_week`, `overdue_outside_week` e `days`. Cada dia ganha `is_today` e `is_past`, e as tarefas vêm como `TaskView` (com `due_date_locked` e `xp_earned`). Só back-end | `backend/app/dates.py`, `backend/app/routers/tasks.py`, `backend/tests/test_dates.py`, `backend/tests/test_tasks.py` |
| 12.2 Ver a semana e trocar de semana (fecha o critério) | Troca "Dia / Semana" no alto da página. O `js/week.js` desenha e busca a semana: dias empilhados no celular e 7 colunas na tela larga, "Hoje" destacado, setas de semana, "Esta semana" e o título "02/11 a 08/11/2026". Os cartões são resumidos (título, ✎, concluída riscada com "+N XP"), ainda sem toque. As recargas passam a recarregar a visão que está na tela (`loadView`): depois de gravar, na volta ao app e na tela de tipos. Estados de carregando, erro e semana vazia | `frontend/index.html`, `frontend/css/style.css`, `frontend/js/week.js` (novo), `frontend/js/day.js`, `frontend/js/task-types.js`, `frontend/js/app.js`, `backend/tests/test_frontend.py`, `CLAUDE.md` |
| 12.3 Caixinha e toque na semana | A caixinha da semana conclui e desmarca pelo `toggleTask` do dia, com o aviso quando a tarefa sai da semana. Tocar numa tarefa abre o dia dela com o cartão já aberto (e "Concluídas" aberta, se ela estiver concluída). Tocar no título de um dia abre esse dia. O preenchimento do cartão (título, ✎, caixinha, concluída) sai do `createTaskCard` para uma função usada pelos dois | `frontend/index.html`, `frontend/css/style.css`, `frontend/js/week.js`, `frontend/js/day.js` |
| 12.4 Atrasadas na semana | A pendente num dia que já passou (`is_past`) ganha o destaque de atrasada, com texto, não só cor. Quando `overdue_outside_week > 0`, uma linha diz "3 tarefas atrasadas fora desta semana.", com o botão "Ver em Hoje" | `frontend/index.html`, `frontend/css/style.css`, `frontend/js/week.js` |

Por que esta ordem: a API vem primeiro, como nas tarefas 10 e 11, para todo o JavaScript da semana nascer sem nenhuma conta de data. A 12.2 fecha o critério e traz a troca de visão, que é a base das outras. A caixinha e o toque vêm depois porque dependem de a semana já estar na tela e de as recargas já respeitarem a visão. As atrasadas ficam por último porque são destaque visual sobre o que já funciona.

**Decisões da divisão da tarefa 12:**

- **Celular e tela larga (decisão minha):** no celular, os sete dias ficam um embaixo do outro, cada um com o título ("Segunda-feira, 02/11", ou "Hoje") e as tarefas, ou "Sem tarefas.". Na tela larga, sete colunas lado a lado, numa grade de CSS. O ponto de troca fica perto de 64rem (1024 px), decidido no plano da 12.2. O HTML é o mesmo nas duas larguras, só uma media query muda, e não há rolagem para o lado. Na semana, o `<main>` ganha uma largura máxima maior, porque os 40rem de hoje dariam colunas de uns 85 px. O texto da seção 6.2 mudou por isso. A linha 12 da tabela acima fica como está, porque registra o pedido original.
- **Os campos da semana (regra 9 do `CLAUDE.md`):** a resposta traz `is_current_week` (hoje, em Brasília, está nesta semana), `previous_week` e `next_week` (as segundas-feiras vizinhas, ou `null` nas pontas do calendário), `overdue_outside_week` e `days`. Cada dia traz `day`, `is_today`, `is_past` (o dia já passou em Brasília) e `tasks`, como `TaskView`.
  - `GET /tasks/this-week` é a semana de hoje, no molde do `/tasks/today`. Com `is_current_week`, a tela volta a recarregar por esse caminho, e a virada de domingo para segunda leva a tela à semana nova.
  - A semana de `9999-12-31` tem 5 dias, e a tela desenha só os que vierem; na grade, as duas últimas colunas ficam vazias.
  - O `due_date_locked` vem junto para a tarefa ter um formato só nas duas listas, mas a semana não o usa, porque o Adiar fica no dia.
  - Sem data sugerida por dia: a semana não tem "Nova tarefa". Tocar no título do dia abre o dia, e o "Nova tarefa" de lá já sugere aquele dia.
  - `is_past` fica no dia, e não no `TaskView`, para não mudar a lista do dia.
  - A resposta deixou de ser uma lista e virou um objeto. Nenhuma tela lia a rota, só os testes; depois do front, a mudança não seria segura.
- **O toque (decisão minha):** na semana, a caixinha conclui e desmarca, e o toque na tarefa abre o dia dela.
  - A caixinha é a do dia: o mesmo `toggleTask`, a mesma gravação única (`saving`, `disableTaskControls`), o mesmo foco (`focusTask`, porque o id `task-check-<id>` continua único) e o mesmo aviso quando a tarefa sai da tela (`showMovedNotice`).
  - Tocar na tarefa abre o dia da coluna (`TODAY_PATH`, se `is_today`), com `openTaskId` na tarefa: o `createTaskCard` já faz o cartão nascer aberto, e o foco vai para o botão do título dele. Para uma concluída, a tela abre o `<details>` das "Concluídas" antes de desenhar. Lá estão as notas, o Editar e o Adiar, sem nada copiado.
  - O cartão da semana tem um `<template>` próprio, porque não abre e não tem Editar nem Adiar, mas usa as mesmas classes do resumo (`.task-title`, `.task-notes-icon`, `.task-checkbox`, `.task-xp`). O pedaço do `createTaskCard` que preenche essas partes vira uma função usada pelos dois.
  - O Adiar, o Editar, o formulário e a confirmação em dois toques ficam só no dia. O formulário só abre a partir do dia, então o `task-form.js` não muda.
- **Trocar entre dia e semana, sem conta de data:**
  - "Dia" e "Semana" são dois botões de 48 px com `aria-pressed`, no alto do `<main>`, sempre à vista. A barra de setas do dia aparece só no dia, e a da semana só na semana.
  - O dia continua guardado no `dayPath`. A semana ganha o `weekPath` (`tasks/this-week` ou `tasks/week/AAAA-MM-DD`).
  - Dia → Semana: a semana do dia da tela. Com o `dayPath` em `TODAY_PATH`, vale `tasks/this-week`; nos outros dias, `tasks/week/` mais o mesmo texto de data do `dayPath`. Quem acha a segunda-feira é o servidor.
  - Semana → Dia (botão "Dia"): volta ao `dayPath` como ficou. Para ir a outro dia, toca-se no título dele ou numa tarefa, o que muda o `dayPath`.
  - As setas usam `tasks/week/` mais `previous_week` ou `next_week`, e o "Esta semana" usa `tasks/this-week`.
  - Uma visão por vez: ao trocar, a lista da visão que sai é esvaziada, e o pedido em andamento dela é ignorado, porque o contador de pedido mais recente sobe. Assim nenhum id de cartão fica repetido na página, e uma resposta atrasada do dia não aparece por cima da semana.
  - `refreshScreen` (depois de gravar e na volta ao app) e a tela de tipos (que fica à vista nas duas visões) chamam `loadView`, que recarrega só a visão da tela.
  - O app abre no dia de hoje, como antes. Nada é guardado no aparelho.
- **As atrasadas:** a pendente atrasada aparece no dia marcado e nunca se repete em hoje; a concluída aparece no dia da conclusão (já era assim desde a etapa 5.6). A pendente de um dia com `is_past` usa a borda de atrasada do dia e o texto "Atrasada", para não depender só da cor. Na semana atual, uma tarefa atrasada desde a semana passada não aparece em nenhuma coluna, e quem olhasse só a semana acharia que está tudo em dia. Por isso o `overdue_outside_week` e a linha "3 tarefas atrasadas fora desta semana.", com o botão "Ver em Hoje", mantidos por decisão minha.
- **`day.js` e `week.js`:** nasce o `js/week.js`, entre o `day.js` e o `task-form.js`. Ele desenha e busca a semana, navega entre semanas e guarda a troca entre as visões (`currentView`, `loadView`), porque carrega depois do `day.js` e conhece as duas. O `day.js` não é dividido: a semana usa dele só a caixinha e o preenchimento do cartão, e o Adiar, o cartão que abre e a navegação de dias continuam só no dia. É o caminho da etapa 11.5, em que a confirmação usada pelo formulário e pela tela de tipos ficou no `day.js`, com um comentário dizendo quem mais a usa. Ordem dos scripts: `api`, `top-bar`, `day`, `week`, `task-form`, `task-types`, `app`.
- **Valem para as etapas 12.2 a 12.4:** nenhuma conta de data ou de regra do jogo no JavaScript; a data de hoje vem do servidor (`is_today`, `is_current_week`), e o JavaScript só formata o texto (`Intl.DateTimeFormat` em `timeZone: "UTC"`); `<template>` com `cloneNode`; dados só por `textContent` e `value`; uma gravação por vez; só o pedido mais recente desenhado; 48 px de toque; foco visível; 360 px sem rolagem para o lado; nada que dependa de passar o mouse.
- **Todo roteiro manual usa um banco só para ele (decisão minha), nas etapas 12.1 a 12.4:** concluir uma tarefa grava XP no histórico, e esse XP não sai nem excluindo a tarefa (etapa 5.7). Por isso, com o servidor desligado, o `agenda.db` de verdade é guardado com outro nome antes do roteiro (`agenda-reserva-<etapa>.db`) e volta no fim, depois de apagar o banco do roteiro.

**Decisões da etapa 12.1 (plano `12.1-api-da-semana.md`):**

- **Semanas vizinhas:** `adjacent_weeks`, em `dates.py`, no molde de `adjacent_days`, a partir de `week_days`. A anterior é a segunda de 7 dias antes, ou `None` quando a semana começa em `0001-01-01` (uma segunda-feira). A seguinte é o dia depois do último da semana, ou `None` quando a semana termina em `9999-12-31`. Assim, nenhuma ponta dá `OverflowError`.
- **Um "hoje" por pedido:** `GET /tasks/this-week` e `GET /tasks/week/{day}` leem o relógio uma vez e passam o valor para `build_week_tasks`, que o usa em `is_current_week`, `is_today`, `is_past`, na trava e na contagem, como o `build_day_tasks`.
- **As consultas:** continua uma por dia, com os filtros da visão do dia (`pending_on` ou `completed_on`), e mais duas para a semana inteira: o `xp_earned_by_task` de todas as tarefas e a contagem do `overdue_outside_week`, feita no banco com `func.count`. As tarefas passam pelo mesmo `task_view` da lista do dia, e um teste confere que a semana e o dia mostram a mesma tarefa igual, com a mesma trava e o mesmo XP.
- **`overdue_outside_week`:** pendentes com `due_date` anterior a hoje e fora dos dias da semana pedida. Vale para qualquer semana: numa semana futura, contam todas as atrasadas; numa passada, as que ficaram depois dela também contam, porque também não aparecem nas colunas.
- **`/tasks/this-week` não é um id:** `PUT` e `DELETE` em `/tasks/this-week` continuam dando 422.
- **Nada muda no banco:** nenhuma tabela nova, então o `agenda.db` fica como está.

**Detalhe sobre testar no celular:** antes da publicação, o teste é pelo cabo USB, abrindo `http://localhost:8000` no celular, como explica a seção 6.7. Como `localhost` é origem segura, o service worker e a instalação já podem ser testados assim. A instalação definitiva vem na tarefa 17.

**Segurança nas tarefas 9 a 14 (regras na seção 6.7):**

- **Tarefa 9:** o `StaticFiles` entrega só a pasta `frontend/`, como resposta padrão do roteador, depois das rotas da API, valendo também para produção (ver as decisões da tarefa 9). A CSP vai por cabeçalho: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'`. Por isso, JavaScript e CSS ficam em arquivos, sem `onclick` no HTML. Um teste do pytest lê os `.js` de `frontend/` e falha se achar `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` ou `eval`.
- **Tarefa 10:** título e notas entram por `textContent`. Teste manual: criar uma tarefa com título em forma de HTML e ver que ele aparece como texto.
- **Tarefa 11:** os campos do formulário usam `value`, o nome do tipo usa `textContent` e a cor usa `style.backgroundColor`.
- **Tarefas 12 e 13:** a mesma regra. Na 13, fontes e ícones são locais.
- **Tarefa 14:** o service worker usa uma lista fechada de arquivos e responde só a `GET` dessa lista. API e `/auth` passam direto, sem cache.

**Divisão da tarefa 15:**

- **Etapa 15.1, configuração:** `APP_ENV`, `APP_PASSWORD` e `APP_ORIGIN`, com o app recusando subir sem senha válida ou, fora do desenvolvimento, sem endereço válido (seção 6.7). O `python-dotenv` entra como dependência nova, autorizada nesta tarefa e só para desenvolvimento, porque o `uvicorn --env-file` exige. O comando passa a ser `uvicorn app.main:app --reload --env-file .env`. Eu escrevo a senha de desenvolvimento no `backend/.env`; `APP_ORIGIN` não precisa estar lá. O `conftest.py` passa a definir valores falsos para os testes, antes de importar o app, com `APP_ORIGIN=https://testserver`.
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
- A primeira migração precisa manter o `sqlite_autoincrement` das tabelas (seção 6.6). Conferir isso na revisão da migração, porque os testes de id usam `create_all` e não veriam a perda.
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
| `backend/app/main.py` | Cria o app FastAPI, cria o banco ao iniciar, registra as rotas, liga a CSP e entrega a pasta `frontend/` quando nenhuma rota casa, com `Cache-Control: no-cache` nos arquivos. | `lifespan`, `GET /health`, `FRONTEND_DIR`, `CONTENT_SECURITY_POLICY`, `FRONTEND_CACHE_CONTROL`, `DOCS_PATHS`, `add_content_security_policy`, `FrontendFiles` | 2, 6.5, 6.7 | `test_health.py`, `test_database.py`, `test_frontend.py` |
| `backend/app/database.py` | Conecta ao banco, entrega a sessão e liga as chaves estrangeiras no SQLite. | `DATABASE_URL`, `create_db_and_tables`, `get_session`, `enable_sqlite_foreign_keys` | 2, 6.6 | `test_database.py` |
| `backend/app/models.py` | Define as três tabelas do banco e a base com os campos da tarefa, reaproveitada pela resposta da visão do dia. | `TaskType`, `TaskBase`, `Task`, `XpEntry`, `utc_now`, `DEFAULT_TASK_COLOR` | 6.1, 6.4, 6.6 | `test_database.py`, `test_tasks.py` |
| `backend/app/dates.py` | Responde "que dia é" no horário de Brasília, quais são o dia anterior e o seguinte, os dias de uma semana e a semana anterior e a seguinte. | `APP_TIMEZONE`, `to_app_date`, `app_today`, `app_day_bounds`, `adjacent_days`, `week_days`, `adjacent_weeks` | 6.4, 6.2 | `test_dates.py` |
| `backend/app/rules/xp.py` | Guarda as regras de XP, adiamento, devolução, nível e barra, com os números no topo, e os textos do histórico. | `task_xp`, `effective_postponements`, `is_due_date_locked`, `postponements_after_date_change`, `postponed_due_date`, `xp_to_refund`, `completion_reason`, `uncompletion_reason`, `xp_to_next_level`, `level_progress`, `progress_percent` | 4.1, 4.2, 4.3, 4.4, 4.5 | `test_xp.py` |
| `backend/app/routers/task_types.py` | API dos tipos de tarefa, com o nome único ignorando maiúsculas, minúsculas e acentos. A lista traz, em cada tipo, quantas tarefas o usam. Também define `SessionDep` e `MAX_ID`, usados em `tasks.py`. | `POST /task-types`, `GET /task-types`, `PATCH /task-types/{task_type_id}`, `DELETE /task-types/{task_type_id}`, `TaskTypeView` (com `task_count`), `task_count_by_type`, `name_key`, `ensure_name_is_free` | 6.1, 6.6 | `test_task_types.py` |
| `backend/app/routers/tasks.py` | API das tarefas: criar, listar hoje, por dia e por semana, editar (inclusive a data, recusando a tela desatualizada), excluir, concluir, desmarcar e adiar. A lista do dia traz a data sugerida para uma tarefa nova e, em cada tarefa, a trava da data e o XP rendido. A semana traz, em cada dia, se ele é hoje e se já passou, em cada tarefa a mesma trava e o mesmo XP rendido, e também se é a semana de hoje, as semanas vizinhas e quantas atrasadas ficam fora dela. | `POST /tasks`, `GET /tasks/today`, `GET /tasks/this-week`, `GET /tasks/day/{day}`, `GET /tasks/week/{day}`, `PUT /tasks/{task_id}`, `DELETE /tasks/{task_id}`, `POST /tasks/{task_id}/complete`, `POST /tasks/{task_id}/uncomplete`, `POST /tasks/{task_id}/postpone`, `STALE_TASK_MESSAGE`, `TaskFields`, `TaskInput`, `TaskUpdate`, `TaskView`, `DayTasks` (com `new_task_due_date`), `build_day_tasks`, `WeekDay`, `WeekTasks`, `build_week_tasks`, `task_view`, `xp_earned_by_task`, `ensure_date_is_not_past`, `ensure_due_date_can_change`, `change_completed` | 6.1, 6.2, 4.2, 4.3, 4.4 | `test_tasks.py` |
| `backend/app/routers/player.py` | API do jogador: soma o histórico e devolve XP total, nível e barra. | `GET /player`, `Player` | 4.4, 4.5, 6.2 | `test_player.py` |
| `frontend/index.html` | A página do app. Carrega os scripts de `js/` na ordem, todos com `defer`, com o `app.js` por último. Tem o topo fixo com nível, XP, barra, o aviso de erro ao salvar e o aviso de que a tarefa saiu da tela; a barra de navegação (setas, calendário e "Hoje"); a lista do dia (o botão "Nova tarefa", atrasadas, pendentes e "Concluídas"), com os estados de carregando, erro e dia vazio; o formulário de criar e editar tarefa, num `<dialog>`, com os campos de mesmo `name` que a API, o "Novo tipo" ao lado do Tipo e a área de criar tipo (campo do nome sem `name`, erro do tipo, texto fixo, Desistir e Criar tipo), os textos das travas e do adiamento, o pedido de confirmação da data nova e, só na edição, a área do Excluir, com o texto sobre o XP; o botão "Tipos de tarefa", no fim da página; a tela de tipos, num `<dialog>` fora do formulário de tarefa (título e "Fechar", texto fixo, aviso, estados de carregando, erro e lista vazia, e a lista); o modelo da linha de tipo, com o nome, a contagem e o "Editar", e a edição (o `<form>` de renomear com "Desistir" e "Salvar nome", e a área do Excluir com o texto sobre as tarefas e a contagem); e o modelo do cartão, com o botão do título e a parte que abre (notas, Editar e Adiar). | `#player-level`, `#player-xp`, `#player-progress`, `#player-message`, `#save-message`, `#notice`, `#day-previous`, `#day-picker`, `#day-next`, `#day-today`, `#day-status`, `#day-error`, `#day-retry`, `#day-view`, `#new-task`, `#overdue-list`, `#pending-title`, `#pending-list`, `#completed-section`, `#completed-list`, `#task-form-dialog`, `#task-form` (`#task-form-heading`, `#task-form-title`, `#task-form-due-date`, `#task-form-date-postpone`, `#task-form-date-locked`, `#task-form-date-completed`, `#task-form-difficulty`, `#task-form-difficulty-completed`, `#task-form-color`, `#task-form-default-color`, `#task-form-type`, `#task-form-new-type`, `#task-form-types-error`, `#task-form-types-kept`, `#task-form-type-gone`, `#task-form-new-type-area`, `#task-form-new-type-name`, `#task-form-new-type-error`, `#task-form-new-type-cancel`, `#task-form-new-type-create`, `#task-form-notes`, `#task-form-error`, `#task-form-confirm`, `#task-form-cancel`, `#task-form-save`, `#task-form-delete-area`, `#task-form-delete-pending`, `#task-form-delete-completed`, `#task-form-delete`), `#open-task-types`, `#task-types-dialog` (`#task-types-close`, `#task-types-notice`, `#task-types-status`, `#task-types-error`, `#task-types-retry`, `#task-types-empty`, `#task-types-list`), `#task-type-row-template` (`.type-view`, `.type-name`, `.type-count`, `.type-edit`, `.type-edit-name`, `.type-editor`, `.type-rename-form`, `.type-name-label`, `.type-name-input`, `.type-rename-error`, `.type-rename-cancel`, `.type-rename-save`, `.type-delete-count`, `.type-delete-error`, `.type-delete`), `#task-card-template` (`.task-toggle`, `.task-details`, `.task-notes`, `.task-actions`, `.task-edit`, `.task-postpone`) | 6.2, 6.3, 6.7 | `test_frontend.py` (inclusive `test_html_has_no_inline_code`, os testes do formulário e os da tela de tipos) |
| `frontend/css/style.css` | O visual: variáveis de cores e espaçamentos, layout de celular, topo, barra, navegação entre os dias, "Nova tarefa", formulário (diálogo, campos, campo bloqueado, cor, Tipo e "Novo tipo" lado a lado, área de criar tipo, textos embaixo dos campos, erros, confirmação da data nova, botões e a área do Excluir), botão de ação perigosa, cartões, botão do título, notas, Editar e Adiar lado a lado, Adiar bloqueado e pedindo confirmação, seções, "Concluídas", o "Tipos de tarefa", a tela de tipos (título e "Fechar" lado a lado, aviso, lista com uma linha fina entre os tipos, nome e contagem ao lado do "Editar", campo da edição), foco e elementos escondidos. | variáveis em `:root`, `[hidden]`, `.visually-hidden`, `.top-bar`, `.xp-bar`, `.day-nav`, `.day-nav-arrow`, `.day-picker`, `.button`, `.button.is-primary`, `.button.is-danger`, `.button.is-confirming`, `.button.is-danger.is-confirming`, `.new-task-button`, `.form-dialog`, `.form-field`, `.form-field :disabled`, `.form-color-row`, `.form-type-row`, `.form-new-type`, `.form-hint`, `.form-error`, `.form-confirm`, `.form-actions`, `.form-delete-area`, `.open-types-button`, `.types-header`, `.types-notice`, `.type-list`, `.type-row`, `.type-view`, `.type-text`, `.type-name`, `.type-count`, `.type-editor`, `.task-card`, `.task-check`, `.task-toggle`, `.task-details`, `.task-notes`, `.task-actions`, `.task-section`, `.completed-section` | 6.3, 6.7 | `test_frontend.py` |
| `frontend/js/api.js` | Carrega primeiro. Faz toda chamada à API, pela função única, que põe no erro o código e o `detail` da resposta e devolve `null` no 204, sem corpo, e formata números e datas que vieram prontos, sem conta. | `API_BASE`, `apiRequest`, `numberFormat`, `formatDueDate`, `formatDayTitle` | 6.5, 6.7 | `test_frontend.py` (entrega, `defer`, nomes repetidos e a proibição de `innerHTML` e parecidos); o resto, pelo roteiro manual |
| `frontend/js/top-bar.js` | O topo fixo: mostra o nível, o XP e a barra como o servidor mandou, sem conta de XP. Escreve a linha de erro ao salvar e o aviso de que a tarefa saiu da tela (adiada, criada em outro dia, concluída, desmarcada ou excluída) ou mudou de data na edição, e de que um tipo foi criado com o formulário já fechado, ou renomeado ou excluído com a tela de tipos já fechada. | `showPlayer`, `loadPlayer`, `showSaveMessage`, `showNotice`, `hideNotice`, `hideMessages` | 6.2, 6.3 | o mesmo do `api.js` |
| `frontend/js/day.js` | A lista do dia, sem conta de data ou de trava. Desenha o dia como o servidor mandou e navega pelas setas, pelo "Hoje" e pelo calendário. Conclui e desmarca pela caixinha e avisa quando a tarefa sai da tela. Abre e fecha o cartão, abre a edição pelo Editar e adia com confirmação. Guarda a confirmação em dois toques, usada pelo Adiar, pelo Excluir do formulário e pelo Excluir da tela de tipos, e o `saving`, que vale também para a tela de tipos. | `createTaskCard`, `createOverdueCard`, `showDay`, `showDayLoading`, `TODAY_PATH`, `dayPath`, `loadDay`, `SAVE_ERROR_TEXT`, `saving`, `toggleTask`, `showMovedNotice`, `focusTask`, `toggleCard`, `setCardOpen`, `closeOpenCard`, `CONFIRM_TIMEOUT_MS`, `DOUBLE_TAP_GUARD_MS`, `handleConfirmClick`, `startConfirmation`, `cancelConfirmation`, `postponeTask`, `reloadDidNotExplain`, `goToDay` | 6.2, 6.3, 6.7 | o mesmo do `api.js` |
| `frontend/js/task-form.js` | O formulário de criar, de editar e de excluir tarefa, sem conta de data e sem número de regra. Abre o `<dialog>` vazio, com a data sugerida pelo servidor, ou preenchido com a tarefa da lista, com as travas que o servidor mandou. Busca os tipos sem perder o tipo da tarefa editada, pede confirmação quando a data muda na edição e grava pelo `POST /tasks` ou pelo `PUT /tasks/{id}` (com `shown_due_date`), com uma gravação por vez. Mostra os erros 422, 409 e 404 em português, sem perder o que foi digitado, e avisa quando a tarefa nasce em outro dia ou muda de data, dizendo se contou como adiamento. Só na edição, exclui pelo `DELETE /tasks/{id}`, com confirmação em dois toques e o texto fixo sobre o XP, e avisa "Excluída: …". Pelo "Novo tipo", cria tipo pelo `POST /task-types`, sem que o Enter no campo do nome salve a tarefa (duas barreiras: `keydown` e o começo do `submit`), mostra os erros do tipo só na área dele e deixa o tipo novo escolhido, também com uma gravação por vez. O `fieldErrorText` e o `CONFIRM_DELETE_LABEL` também servem à tela de tipos. | `openTaskForm`, `editingTask`, `fillTaskForm`, `showLockedFields`, `focusEditedTask`, `colorChosen`, `loadTaskTypes`, `showTaskTypes`, `fieldErrorText`, `showFormErrors`, `clearFormErrors`, `dateChanged`, `startDateConfirmation`, `cancelDateConfirmation`, `taskBody`, `saveTask`, `showCreatedNotice`, `showEditedNotice`, `showDeleteArea`, `CONFIRM_DELETE_LABEL`, `DELETE_ERROR_TEXT`, `deleteTask`, `focusAfterDelete`, `NEW_TYPE_ERROR_TEXT`, `showNewTypeArea`, `hideNewTypeArea`, `clearNewTypeError`, `showNewTypeError`, `createTaskType` | 6.1, 6.2, 6.7 | `test_frontend.py` (os do `api.js` e os testes do formulário); o resto, pelo roteiro manual |
| `frontend/js/task-types.js` | A tela de tipos, sem conta e sem número de regra. Abre o `<dialog>` só a partir da tela principal e busca os tipos com a contagem que o servidor mandou. Uma linha em edição por vez: renomeia pelo `PATCH /task-types/{id}` (sem pedido quando o texto não mudou, e com o Enter no `<form>` da própria linha) e exclui pelo `DELETE /task-types/{id}`, com confirmação em dois toques e o texto de que as tarefas ficam sem tipo. Mostra os erros 422, 409 e 404 junto do tipo, sem perder o que foi digitado, atualiza a lista com a resposta do servidor, recarrega a lista do dia e respeita a gravação única. | `openTypesScreen`, `showTypesNotice`, `hideTypesNotice`, `shownTypes`, `loadTypeList`, `showTypeList`, `taskCountText`, `deleteCountText`, `createTypeRow`, `editingTypeId`, `startTypeEdit`, `stopTypeEdit`, `focusTypeEdit`, `setTypesBusy`, `clearTypeErrors`, `removeShownType`, `TYPE_RENAME_ERROR_TEXT`, `showRenameError`, `renameType`, `TYPE_DELETE_ERROR_TEXT`, `deleteType` | 6.1, 6.2, 6.7 | `test_frontend.py` (os do `api.js` e os testes da tela de tipos); o resto, pelo roteiro manual |
| `frontend/js/app.js` | Carrega por último. Recarrega o dia da tela e o topo juntos, depois de cada gravação e quando o app volta do segundo plano. Liga o "Tentar de novo" e o clique que cancela a confirmação em dois toques (Adiar, Excluir tarefa e Excluir tipo). Faz os primeiros pedidos. | `refreshScreen` | 6.2, 6.5 | o mesmo do `api.js` (inclusive `test_app_js_is_the_last_script`) |
| `backend/tests/conftest.py` | Reúne o que os testes de banco e de API têm em comum. O pytest carrega este arquivo sozinho. | `empty_engine`, `test_engine`, `client` | não se aplica | não se aplica |
| `backend/tests/test_health.py` | Testa a rota `/health`. | `test_health_returns_ok` | 10 (tarefa 1) | não se aplica |
| `backend/tests/test_database.py` | Testa a criação das tabelas ao iniciar, os valores padrão, as chaves estrangeiras e o AUTOINCREMENT só no SQLite. | `test_app_startup_creates_tables`, `test_task_with_unknown_task_type_is_refused`, `test_xp_entry_with_unknown_task_is_refused`, `test_autoincrement_exists_only_on_sqlite` | 6.1, 6.6 | não se aplica |
| `backend/tests/test_dates.py` | Testa o fuso, o "hoje", os limites do dia, os dias vizinhos, a semana e as semanas vizinhas. | testes de `to_app_date`, `app_today`, `app_day_bounds`, `adjacent_days`, `week_days`, `adjacent_weeks` | 6.4 | não se aplica |
| `backend/tests/test_xp.py` | Testa XP, adiamentos, trava da data, data nova do Adiar, devolução, textos do histórico, níveis e barra, inclusive um total enorme. | testes de cada função de `xp.py` | 4.1, 4.2, 4.3, 4.4, 4.5 | não se aplica |
| `backend/tests/test_task_types.py` | Testa a API dos tipos de tarefa. | testes de criar, listar (inclusive a contagem de tarefas de cada tipo), renomear e excluir, de campo desconhecido, de id que não volta, da chave do nome (`test_name_key`), do nome repetido com outra caixa ou outro acento e dos pares antigos de mesma chave, com auxiliares `create_type`, `insert_type`, `insert_task`, `insert_old_duplicates` | 6.1, 6.6 | não se aplica |
| `backend/tests/test_tasks.py` | Testa a API das tarefas, com o "hoje" fixo em todos os testes do arquivo, inclusive a visão de hoje, a trava, o XP rendido e a data sugerida na lista do dia, a semana de hoje, as semanas vizinhas, os dias que são hoje ou já passaram, a mesma tarefa igual no dia e na semana, a contagem das atrasadas fora da semana, e a edição com a tela desatualizada ou no meio de um Concluir ou de um Adiar. | `fixed_today`, auxiliares `set_now`, `insert_task`, `insert_xp_entry`, `update_data`, `complete_task`, `uncomplete_task`, `postpone_task`, `assert_postpone_refused`, `xp_total`, `groups`, `as_listed`, `today_tasks`, `listed_task`, `week_tasks`, `this_week_tasks`, `week_ids`, `day_flags` | 6.1, 6.2, 6.6, 4.2, 4.3, 4.4 | não se aplica |
| `backend/tests/test_player.py` | Testa a API do jogador, com o "hoje" fixo: fronteiras da tabela 4.5, histórico vazio, soma negativa, total enorme e a ligação com concluir, desmarcar e excluir. | `fixed_today`, auxiliares `get_player`, `player`, `insert_xp`, `create_medium_task` | 4.3, 4.4, 4.5, 6.7 | não se aplica |
| `backend/tests/test_frontend.py` | Testa a entrega do front e os scripts. A página e todo `.js` abrem com a CSP, vão com `Cache-Control: no-cache` e respondem 304 quando não mudaram. A API fica sem esse cabeçalho, nada de `backend/` fica acessível, o `/docs` abre sem CSP e a API responde como antes. Os `.js` não usam `innerHTML` e parecidos, e os `.html` não têm script, atributo `on...` nem estilo dentro da página. Todo `<script>` tem `defer` e existe; cada `.js` de `frontend/js` está no `index.html` uma vez só, com o `app.js` por último; nenhum nome é declarado no alto de dois arquivos. O formulário de tarefa tem a cor padrão, as dificuldades e os campos do servidor, cada campo com rótulo, e nenhum limite no HTML; a edição pede exatamente esses campos e mais `shown_due_date`; o único campo sem `name` é o do tipo novo; todo botão do formulário tem `type`, e só o Salvar envia. O 422 do nome do tipo, ao criar e ao renomear, tem o formato que a tela lê, e o limite do nome não aparece nos `.js` nem no `index.html`. Todo `<form>` deixa as regras com o servidor; no de renomear tipo, só o "Salvar nome" envia; e a tela de tipos fica fora do formulário de tarefa, sem `<form>` dentro de outro. | `EXPECTED_CSP`, `JAVASCRIPT_PATHS`, `FORBIDDEN_IN_JAVASCRIPT`, `InlineCodeFinder`, `ScriptFinder`, `index_scripts`, `TaskFormFinder`, `task_form`, `FormsFinder`, `html_forms`, `rename_form`, `test_frontend_files_are_checked_before_use`, `test_unchanged_frontend_file_answers_304`, `test_api_does_not_get_the_frontend_cache_header`, `test_html_has_no_inline_code`, `test_every_script_is_deferred_and_exists`, `test_every_javascript_file_is_loaded_once`, `test_app_js_is_the_last_script`, `test_no_top_level_name_is_declared_twice`, `test_task_form_default_color_matches_the_server`, `test_task_form_difficulties_match_the_server`, `test_task_form_fields_match_the_api`, `test_task_form_fields_match_the_edit_api`, `test_new_type_field_is_not_a_task_field`, `test_only_save_submits_the_task_form`, `test_task_form_leaves_the_rules_to_the_server`, `test_type_name_errors_have_the_shape_the_form_reads`, `test_type_name_limit_is_only_on_the_server`, `test_type_rename_errors_have_the_shape_the_screen_reads`, `test_every_form_leaves_the_rules_to_the_server`, `test_only_save_name_submits_the_rename_form`, `test_types_screen_is_not_inside_the_task_form` | 6.5, 6.7, 10 (tarefa 9 e etapas 10.2, 10.4, 11.2, 11.3, 11.4, 11.5, 11.6 e 11.7) | não se aplica |
| `backend/requirements.txt` | Fixa as versões das dependências. | não se aplica | 2 | não se aplica |
| `backend/pytest.ini` | Faz o pytest encontrar a pasta `app`. | `pythonpath` | não se aplica | não se aplica |
| `.gitignore` | Diz o que fica fora do Git. | não se aplica | não se aplica | não se aplica |
| `.gitattributes` | Trava o fim de linha LF no repositório e na pasta, e marca imagens, fontes e o banco como binários. | `* text=auto eol=lf`, linhas `binary` | não se aplica | não se aplica |
| `.claude/settings.json` | Faz o Claude Code salvar os planos em `docs/planos` e bloqueia a leitura do `.env` e das variações. | `plansDirectory`, `permissions.deny` (regra 14 do `CLAUDE.md`) | não se aplica | não se aplica |
| `CLAUDE.md` | Define como trabalhar comigo, a stack, as convenções e os comandos. | regras 1 a 15, exceções aprovadas | não se aplica | não se aplica |
| `README.md` | Apresenta o projeto no GitHub. | não se aplica | 1 | não se aplica |
| `docs/especificacao.md` | Guarda as regras do jogo, as telas, as decisões de segurança, a lista de tarefas e este mapa. | segurança na 6.7, tarefas na seção 10, mapa na seção 12 | não se aplica | não se aplica |
| `docs/planos/*.md` | Guardam um plano por etapa, como registro histórico. Se um plano divergir da especificação, vale a especificação. | nome dos arquivos na regra 13 do `CLAUDE.md` | não se aplica | não se aplica |
