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
| Hospedagem | Front no GitHub Pages; back-end num serviço gratuito, escolhido na hora de publicar |

Durante o desenvolvimento, o próprio FastAPI entrega os arquivos do front-end, então tudo roda no computador com um único comando. Na publicação, o front vai para o GitHub Pages e o back para o serviço escolhido.

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
- Cada adiamento tira 25%: 1 adiamento vale 75%, 2 valem 50% e 3 valem 25%.
- Um adiamento acontece de duas formas: quando você muda a data da tarefa para depois, ou quando o dia passa sem ela ser concluída (cada dia de atraso conta como um adiamento).
- Depois de 3 adiamentos, a tarefa **perde o XP**: ainda dá para concluí-la, mas ela vale 0. O botão "Adiar" fica bloqueado.

Em código: `adiamentos_efetivos = adiamentos_manuais + dias_de_atraso`. Se for maior que 3, o XP é 0; senão, `XP = XP_base × (1 − 0,25 × adiamentos_efetivos)`.

### 4.3 Desmarcar

Desmarcar uma tarefa concluída devolve exatamente o XP que ela deu. Assim não dá para "farmar" XP marcando e desmarcando.

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
  id, name

Task (tarefa)
  id, title, notes (opcional), due_date (data),
  difficulty ("easy" | "medium" | "hard"),
  color (cor em hexadecimal, com um padrão),
  task_type_id (opcional),
  completed (verdadeiro/falso), completed_at (opcional),
  postponements (0 a 3), created_at

XpEntry (histórico de XP)
  id, amount (pode ser negativo), reason, task_id (opcional), created_at
```

O nível e o XP do jogador não são tabelas: são calculados a partir do `XpEntry`.

### 6.2 Telas

- **Topo fixo:** nível atual e barra de XP (quanto falta para o próximo nível).
- **Dia:** lista das tarefas da data escolhida, no estilo Google Tarefas. As tarefas atrasadas aparecem em destaque no topo.
- **Semana:** sete colunas, de segunda a domingo, com as tarefas de cada dia, e setas para navegar entre semanas. É a visão ampla que falta no Google Tarefas.
- **Criar/editar tarefa:** título, data, dificuldade, cor, tipo e notas.
- **Ao subir de nível:** uma comemoração curta na tela.

### 6.3 Aparência

- A cor escolhida pelo usuário é o **fundo do cartão**.
- A dificuldade aparece na **moldura e num ícone**, sem mexer na cor. Tarefas: fácil com moldura simples, médio com moldura prateada, difícil com moldura dourada. Missões (V2) seguem a escada bronze, prata, ouro, rubi, brilho roxo (semideus) e um efeito animado discreto (deus).
- Regra geral: nada pode confundir a vista. Efeitos sutis, nunca piscando.

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
| 1 | Esqueleto do back-end: FastAPI com a rota `/health` | Abrir `http://localhost:8000/health` responde "ok" |
| 2 | Regras de XP como funções puras em `rules/xp.py`: XP da tarefa (com adiamentos), XP necessário por nível, nível a partir do XP total | Os testes do pytest passam, incluindo os números da tabela 4.5 |
| 3 | Banco SQLite e modelos `TaskType`, `Task` e `XpEntry` com SQLModel | O banco é criado ao iniciar o app |
| 4 | API dos tipos de tarefa: criar, listar, renomear, excluir | Funciona pela documentação automática do FastAPI (`/docs`) |
| 5 | API das tarefas: criar, editar, excluir, listar por dia e por semana | Funciona pelo `/docs` |
| 6 | Concluir e desmarcar tarefa, gerando e devolvendo XP no histórico | Concluir e desmarcar deixa o XP total igual ao de antes |
| 7 | Adiar tarefa e calcular o atraso, com bloqueio após 3 adiamentos | Os testes cobrem 0, 1, 2, 3 e 4 adiamentos |
| 8 | API do jogador: XP total, nível e progresso da barra | `/player` devolve nível e porcentagem corretos |
| 9 | Front-end base entregue pelo FastAPI, com o topo de nível e barra de XP | A página abre no navegador mostrando o nível real |
| 10 | Visão do dia, com atrasadas em destaque | Dá para ver, concluir e desmarcar as tarefas do dia |
| 11 | Formulário de criar e editar tarefa | Dá para criar uma tarefa completa pela tela |
| 12 | Visão da semana em sete colunas, com navegação | Dá para ver a semana inteira e trocar de semana |
| 13 | Aparência: cor no fundo, moldura e ícone por dificuldade, comemoração de nível | Cada dificuldade é reconhecível de longe |
| 14 | PWA: `manifest.json`, ícone e service worker | O Chrome reconhece o app como instalável |
| 15 | Proteção por senha única no back-end | Sem a senha, a API recusa os pedidos |
| 16 | Publicação: front no GitHub Pages, back e PostgreSQL num serviço gratuito | O app abre e instala no celular, fora de casa |

**Detalhe sobre testar no celular:** antes da publicação, dá para abrir o app no celular Android pelo Wi-Fi de casa (usando o IP do computador), mas o botão de instalar só aparece com HTTPS. A instalação de verdade vem na tarefa 16.

## 11. Fica para depois

- Notificações no celular (lembrete de tarefa).
- Sincronizar com o Google Agenda.
- Login de várias pessoas, caso um dia o app seja aberto ao público.
