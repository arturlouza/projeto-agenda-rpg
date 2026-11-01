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
| Hospedagem | Front no GitHub Pages; back-end num serviço gratuito, escolhido na hora de publicar. Critério obrigatório: um banco gratuito que não expira |

Durante o desenvolvimento, o próprio FastAPI entrega os arquivos do front-end, então tudo roda no computador com um único comando. Na publicação, o front vai para o GitHub Pages e o back para o serviço escolhido.

A partir da tarefa 16, a URL do banco vem da variável de ambiente `DATABASE_URL`. Sem a variável, vale o SQLite local, e o desenvolvimento continua rodando com um comando só.

**Atenção:** como não há login, antes de publicar o back-end na internet ele precisa de uma proteção simples (uma senha única guardada em variável de ambiente). Sem isso, qualquer pessoa com o endereço mexeria nos dados.

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

- **422:** dado inválido, ou seja, os casos da lista de campos e a data nova anterior a hoje.
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

- Caminhos relativos em tudo, inclusive no `manifest.json` e no registro do service worker, porque o GitHub Pages publica numa subpasta.
- O endereço da API fica numa constante única.
- Todas as chamadas à API passam por uma única função, que na tarefa 15 recebe a senha.

A V1 precisa de internet:

- O service worker guarda só os arquivos do app, nunca dados da API.
- O cache tem um número de versão que muda a cada publicação, para o celular receber a versão nova.

### 6.6 Diferenças conhecidas entre os bancos

- **Ids:** o SQLite reaproveita ids quando os maiores são excluídos (uma tabela vazia volta ao id 1); o PostgreSQL não. Por isso vale a regra de ids da seção 6.1.

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
| 9 | Front-end base entregue pelo FastAPI, com o topo de nível e barra de XP | A página abre no navegador mostrando o nível real |
| 10 | Visão do dia, com atrasadas em destaque | Dá para ver, concluir e desmarcar as tarefas do dia |
| 11 | Formulário de criar e editar tarefa | Dá para criar uma tarefa completa pela tela |
| 12 | Visão da semana em sete colunas, com navegação | Dá para ver a semana inteira e trocar de semana |
| 13 | Aparência: cor no fundo, moldura e ícone por dificuldade, comemoração de nível | Cada dificuldade é reconhecível de longe |
| 14 | PWA: `manifest.json`, ícone e service worker | O Chrome reconhece o app como instalável |
| 15 | Proteção por senha única no back-end | Sem a senha, a API recusa os pedidos |
| 16 | Dados reais: migrações com Alembic (dependência nova, autorizada nesta tarefa), URL do banco em variável de ambiente, rota de exportação e restauração a partir do arquivo exportado | As migrações criam um banco novo, e exportar, apagar e restaurar devolve os mesmos dados e o mesmo XP total |
| 17 | Publicação: front no GitHub Pages, back e PostgreSQL num serviço gratuito cujo banco não expira, com o CORS do back liberado para o endereço do GitHub Pages | O app abre e instala no celular, fora de casa |

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
- **Pronto quando:** um teste prova que a ordem vem do `created_at` (um tipo com id maior e data mais antiga vem primeiro) e que o empate cai no id; `GET /task-types` mostra o `created_at`; todos os testes passam.
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

- **Entrega:** `POST /tasks` com as regras de campos da seção 6.1 e a regra da data nova. A entrada não aceita `postponements` nem `completed`.
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

**Etapa 5.7: excluir tarefa**

- **Entrega:** `DELETE /tasks/{id}`. As linhas da tarefa no histórico ficam com `task_id` nulo e mantêm o valor, tudo na mesma transação.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`.
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, excluir uma tarefa e ver que ela sumiu da lista.
- **Pronto quando:** 204 ao excluir, 404 para id desconhecido, 422 para id fora do intervalo; com um `XpEntry` inserido direto no banco (gerar XP é da tarefa 6), a soma do XP não muda e as linhas de outras tarefas ficam intactas.
- **Reaproveita:** o padrão de `delete_task_type`, com `flush` antes de excluir.

**Etapa 5.8: editar tarefa, ainda sem mudar a data**

- **Entrega:** rota de edição de título, notas, cor, dificuldade e tipo, com as mesmas validações da criação. Em tarefa concluída, mudar a dificuldade dá 409 e mandar o mesmo valor passa.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`.
- **Como testar:** `pytest tests/test_tasks.py`. No `/docs`, editar uma tarefa e listar para conferir.
- **Pronto quando:** cada campo é editado e validado; o pedido recusado não grava nada; tarefa concluída aceita título, notas, cor e tipo; 404 e 422 de id funcionam.
- **A decidir no plano desta etapa:** o que acontece com um campo ausente na edição. Recomendação: exigir todos os campos, já que o formulário envia todos. Assim, esquecer um campo não apaga as notas nem volta a cor ao padrão.

**Etapa 5.9: mudança de data na edição (fecha a tarefa 5)**

- **Entrega:** a edição passa a aceitar `due_date`, com as regras da seção 4.2 e a regra do "mesmo valor". A lógica fica numa função que a tarefa 7 vai reaproveitar. A rota do botão Adiar não entra aqui.
- **Arquivos:** `app/routers/tasks.py`, `tests/test_tasks.py`.
- **Como testar:** `pytest`. No `/docs`, criar uma tarefa, mudar a data para depois três vezes (`postponements` chega a 3), ver a quarta tentativa dar 409 e ver que editar só o título, mandando a mesma data, ainda funciona.
- **Pronto quando:** este é o critério da tarefa 5 na tabela, "funciona pelo `/docs` e os testes cobrem as regras". Casos testados: data anterior a hoje dá 422; atrasada com 0 adiamentos e 2 dias de atraso fica com contador 3; antecipar não conta; travada por atraso ou por adiamento manual recusa até antecipar (409); concluída recusa mudar a data (409); travada ou atrasada aceita editar o título; o pedido recusado não grava nada.
- **A decidir no plano desta etapa:** qual recusa vale quando 422 e 409 se aplicam ao mesmo pedido. Recomendação: o 422 primeiro, porque o dado é conferido antes do estado da tarefa.

**Fora da tarefa 5:**

- Concluir e desmarcar (tarefa 6), rota do Adiar (tarefa 7), front-end (tarefas 9 em diante).
- Campo que diz à tela se a data está travada: as tarefas 10 e 11 vão precisar dele para bloquear o botão e o formulário sem repetir a regra em JavaScript. Ele entra quando a tela precisar, para não adiantar tarefa.

**Detalhe sobre testar no celular:** antes da publicação, dá para abrir o app no celular Android pelo Wi-Fi de casa (usando o IP do computador), mas o botão de instalar só aparece com HTTPS. A instalação de verdade vem na tarefa 17.

**Detalhes sobre a tarefa 16:**

- O Alembic passa a criar e alterar as tabelas no lugar do `create_all` ao iniciar o app, porque os dois juntos colidem. O teste `test_app_startup_creates_tables` muda nessa tarefa.
- A restauração mantém os `created_at`, de que a ordem depende.
- A restauração não passa pela regra da data nova, senão tarefas antigas seriam recusadas.
- A restauração não grava os ids do arquivo: o banco gera ids novos e as referências são traduzidas. Gravar ids à mão não avança o contador do PostgreSQL, e o próximo registro criado colidiria.
- Substituir tudo ou aceitar só banco vazio é decidido nessa tarefa.

## 11. Fica para depois

- Notificações no celular (lembrete de tarefa).
- Sincronizar com o Google Agenda.
- Modo offline (a V1 precisa de internet; ver seção 6.5).
- Login de várias pessoas, caso um dia o app seja aberto ao público.
