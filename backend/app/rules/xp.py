import math

# XP de cada dificuldade de tarefa, concluída sem nenhum adiamento.
TASK_BASE_XP = {"easy": 10, "medium": 25, "hard": 50}

# Cada adiamento tira 25% do XP. Acima de 3 adiamentos, a tarefa vale 0.
POSTPONEMENT_PENALTY = 0.25
MAX_POSTPONEMENTS = 3

# Números da fórmula do nível: 100 + 2 × (nível − 1) ^ 1,5.
LEVEL_BASE_XP = 100
LEVEL_GROWTH_FACTOR = 2
LEVEL_GROWTH_EXPONENT = 1.5

# Nível em que o custo para de crescer. Daí em diante, todo nível custa o mesmo.
LEVEL_GROWTH_CAP = 100


# Atenção: os dois cálculos de XP abaixo arredondam de formas diferentes, de propósito.
# - task_xp arredonda sempre para baixo, como no D&D (seção 4.2 da especificação).
# - xp_to_next_level usa o arredondamento normal (seção 4.5), porque a tabela de níveis
#   e o total de 86.928 XP até o nível 100 dependem dele.


# Calcula o XP de uma tarefa, descontando os adiamentos manuais e os dias de atraso.
def task_xp(difficulty: str, manual_postponements: int, days_late: int) -> int:
    effective_postponements = manual_postponements + days_late

    if effective_postponements > MAX_POSTPONEMENTS:
        return 0

    multiplier = 1 - POSTPONEMENT_PENALTY * effective_postponements
    return math.floor(TASK_BASE_XP[difficulty] * multiplier)


# Calcula o XP necessário para subir do nível informado para o seguinte.
def xp_to_next_level(level: int) -> int:
    capped_level = min(level, LEVEL_GROWTH_CAP)
    growth = LEVEL_GROWTH_FACTOR * (capped_level - 1) ** LEVEL_GROWTH_EXPONENT
    return round(LEVEL_BASE_XP + growth)


# Descobre o nível a partir do XP total: começa no 1 e "paga" um nível de cada vez.
def level_from_total_xp(total_xp: int) -> int:
    level = 1
    remaining_xp = total_xp

    while remaining_xp >= xp_to_next_level(level):
        remaining_xp -= xp_to_next_level(level)
        level += 1

    return level
