# Plano: Tarefa 2 (regras de XP como funções puras)

## Contexto

A tarefa 2 cria as regras de XP e nível, que as próximas tarefas vão usar para gerar XP e calcular o nível do jogador. Ela fica pronta quando o pytest passar, incluindo os números da tabela 4.5.

A especificação não dizia como tratar XP quebrado (25 × 75% = 18,75). Decisão sua: **inteiro, sempre para baixo, como a regra de arredondamento do D&D**, registrada na seção 4.2.

## O que muda

### 1. `docs/especificacao.md` (seção 4.2)

Registrar a regra e incluir o arredondamento na linha "Em código":

- O resultado é sempre arredondado para baixo, para um número inteiro, como no D&D. Exemplo: 25 × 75% = 18,75 vira 18.
- `XP = arredondar_para_baixo(XP_base × (1 − 0,25 × adiamentos_efetivos))`

### 2. `backend/app/rules/xp.py` (novo)

Constantes no topo:

- `TASK_BASE_XP = {"easy": 10, "medium": 25, "hard": 50}`
- `POSTPONEMENT_PENALTY = 0.25`
- `MAX_POSTPONEMENTS = 3`
- `LEVEL_BASE_XP = 100`
- `LEVEL_GROWTH_FACTOR = 2`
- `LEVEL_GROWTH_EXPONENT = 1.5`
- `LEVEL_GROWTH_CAP = 100` (nível em que o custo para de crescer)

Três funções puras (só recebem valores e devolvem um resultado, sem banco nem data atual):

| Função | O que faz |
| --- | --- |
| `task_xp(difficulty, manual_postponements, days_late)` | XP da tarefa, com desconto e arredondamento para baixo. Acima de 3 adiamentos efetivos, devolve 0. |
| `xp_to_next_level(level)` | XP para subir do nível `level` para o seguinte. Do nível 100 em diante, sempre 2.070. |
| `level_from_total_xp(total_xp)` | Nível atual. Começa no 1 e sobe enquanto o XP restante pagar o próximo nível. |

Usa só `math.floor`, da biblioteca padrão do Python, sem dependência nova.

**Dois arredondamentos diferentes, de propósito:**

- `task_xp` arredonda para baixo (`math.floor`), conforme a seção 4.2.
- `xp_to_next_level` usa o arredondamento normal (`round`), conforme a seção 4.5, porque a tabela e o total de 86.928 XP dependem disso.

Um comentário em português no código vai explicar essa diferença e o motivo.

### 3. `backend/tests/test_xp.py` (novo)

Usa `pytest.mark.parametrize`, que roda o mesmo teste com várias entradas (explico o conceito quando chegar a hora).

| Função | Casos testados |
| --- | --- |
| `task_xp` | As 3 dificuldades com 0, 1, 2 e 3 adiamentos: 10/7/5/2, 25/18/12/6, 50/37/25/12 |
| `task_xp` | Atraso somado a adiamento manual: 1 + 2 = 3 vale 25%; 2 + 2 = 4 vale 0 |
| `task_xp` | Só por atraso, com 4 dias e com 10 dias: vale 0 |
| `xp_to_next_level` | Tabela 4.5: 1→100, 10→154, 30→412, 50→786, 75→1373, 99→2040, 100→2070 |
| `xp_to_next_level` | Depois do 100: 101→2070, 500→2070 |
| `level_from_total_xp` | Início: 0→1, 99→1, 100→2, 201→2, 202→3 |
| `level_from_total_xp` | Chegada ao 100: 86.927→99, 86.928→100 |
| `level_from_total_xp` | Depois do 100: 88.997→100, 88.998→101 |

## Decisões de escopo

- **Sem validação de entrada nas funções.** Dificuldade inválida gera `KeyError` naturalmente. A validação do que chega do usuário fica para as rotas da API (tarefa 5).
- **Sem `__init__.py`.** A pasta `app/` já funciona sem ele, então `rules/` segue o mesmo padrão.
- **Fora desta tarefa:** progresso da barra (tarefa 8), cálculo de `days_late` a partir das datas e bloqueio do botão "Adiar" (tarefa 7). Aqui `days_late` chega pronto como parâmetro.

## Como conferir

Na raiz do projeto, no PowerShell:

```powershell
.venv\Scripts\Activate.ps1
cd backend
pytest -v
```

Todos os testes devem aparecer como `PASSED`, inclusive o `test_health` que já existe. Para ver os números com os próprios olhos, ainda dentro de `backend`:

```powershell
python -c "from app.rules.xp import task_xp, xp_to_next_level, level_from_total_xp; print(task_xp('medium', 1, 0), xp_to_next_level(50), level_from_total_xp(86928))"
```

Resultado esperado: `18 786 100`

Depois de cada alteração, explico em português o que foi feito e por quê. O commit fica com você.
