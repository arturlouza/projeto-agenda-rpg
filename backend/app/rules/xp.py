import math
from datetime import date, timedelta

# XP de cada dificuldade de tarefa, concluída sem nenhum adiamento.
TASK_BASE_XP = {"easy": 10, "medium": 25, "hard": 50}

# Cada adiamento tira 25% do XP. Acima de 3 adiamentos, a tarefa vale 0.
# Com 3 ou mais adiamentos efetivos, a data trava.
POSTPONEMENT_PENALTY = 0.25
MAX_POSTPONEMENTS = 3

# O botão Adiar leva a tarefa para este número de dias depois da data marcada.
POSTPONE_DAYS = 1

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


# Soma os adiamentos manuais e os dias de atraso. Data no futuro não desconta adiamento.
def effective_postponements(manual_postponements: int, days_late: int) -> int:
    return manual_postponements + max(days_late, 0)


# Com 3 ou mais adiamentos efetivos, a data não pode mais ser mudada.
def is_due_date_locked(manual_postponements: int, days_late: int) -> bool:
    return effective_postponements(manual_postponements, days_late) >= MAX_POSTPONEMENTS


# Calcula o contador depois de mudar a data. Só mudar para depois conta como adiamento.
# Esta função não confere a trava: quem a chama precisa conferir antes.
def postponements_after_date_change(
    manual_postponements: int, days_late: int, current_due_date: date, new_due_date: date
) -> int:
    if new_due_date <= current_due_date:
        return manual_postponements

    return effective_postponements(manual_postponements, days_late) + 1


# Calcula a data nova do botão Adiar: 1 dia depois da data marcada. Se a tarefa estiver
# atrasada, conta a partir de hoje, então ela vai para amanhã. Devolve None se esse dia não
# existir: o Python não representa nenhuma data depois de 9999-12-31.
def postponed_due_date(due_date: date, today: date) -> date | None:
    try:
        return max(due_date, today) + timedelta(days=POSTPONE_DAYS)
    except OverflowError:
        return None


# Calcula o XP de uma tarefa, descontando os adiamentos manuais e os dias de atraso.
def task_xp(difficulty: str, manual_postponements: int, days_late: int) -> int:
    effective = effective_postponements(manual_postponements, days_late)

    if effective > MAX_POSTPONEMENTS:
        return 0

    multiplier = 1 - POSTPONEMENT_PENALTY * effective
    return math.floor(TASK_BASE_XP[difficulty] * multiplier)


# Calcula o valor da linha de desmarcar: o negativo da soma das linhas da tarefa. Assim, a soma
# de uma tarefa pendente é sempre 0, e a de uma concluída é o XP que ela deu (seção 4.3).
def xp_to_refund(earned_amounts: list[int]) -> int:
    return -sum(earned_amounts)


# Motivo da linha de concluir. Leva o título porque a linha perde o vínculo com a tarefa quando
# ela é excluída. Nenhum código decide nada lendo este texto (seção 4.4).
def completion_reason(title: str) -> str:
    return f"Tarefa concluída: {title}"


# Motivo da linha de desmarcar, com a mesma regra da linha de concluir.
def uncompletion_reason(title: str) -> str:
    return f"Tarefa desmarcada: {title}"


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
