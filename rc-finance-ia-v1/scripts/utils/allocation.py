from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Tuple
import logging
import numpy as np
import pandas as pd

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Goal:
    id: int
    name: str
    remaining: float
    due_date: date
    impact: float  # 0.0 a 1.0
    priority_user: float  # 0.0 a 1.0
    funded_pct: float  # 0.0 a 1.0
    stability_hint: float  # 0.0 a 1.0 (maior = mais estável, menos urgente)

    def __post_init__(self):
        if not (0.0 <= self.impact <= 1.0):
            raise ValueError("Impact must be between 0.0 and 1.0")
        if not (0.0 <= self.priority_user <= 1.0):
            raise ValueError("Priority_user must be between 0.0 and 1.0")
        if not (0.0 <= self.funded_pct <= 1.0):
            raise ValueError("Funded_pct must be between 0.0 and 1.0")
        if not (0.0 <= self.stability_hint <= 1.0):
            raise ValueError("Stability_hint must be between 0.0 and 1.0")

def compute_scores(goals: List[Goal], today: date, w: Dict[str, float]) -> List[Tuple[Goal, float]]:
    """
    Calcula o score para cada meta com base em pesos fornecidos.
    score = w1*urgency + w2*impact + w3*priority_user + w4*stability - w5*funded_pct
    """
    logger.info("Calculando scores para as metas.")

    # Pesos padrão se não forem fornecidos ou estiverem incompletos
    default_weights = {
        "urgency": 0.3,
        "impact": 0.2,
        "priority_user": 0.2,
        "stability": 0.1,
        "funded_pct": 0.2
    }
    weights = {**default_weights, **w}

    scored_goals: List[Tuple[Goal, float]] = []
    for goal in goals:
        # Urgência: quanto mais perto da data de vencimento, maior a urgência
        # Normaliza para 0 a 1.0. Metas vencidas têm urgência máxima (1.0).
        days_to_due = (goal.due_date - today).days
        if days_to_due <= 0:
            urgency = 1.0
        else:
            # Exemplo: urgência decai linearmente em 365 dias. Ajuste conforme necessário.
            urgency = max(0.0, 1.0 - (days_to_due / 365.0))
        
        # Score
        score = (
            weights["urgency"] * urgency +
            weights["impact"] * goal.impact +
            weights["priority_user"] * goal.priority_user +
            weights["stability"] * (1.0 - goal.stability_hint) - # Inverso da estabilidade: menos estável = maior score
            weights["funded_pct"] * goal.funded_pct
        )
        
        # Garante que o score não seja negativo (opcional, dependendo da lógica de negócio)
        score = max(0.0, score)
        
        scored_goals.append((goal, score))
    
    # Ordena as metas por score em ordem decrescente
    scored_goals.sort(key=lambda x: x[1], reverse=True)
    
    logger.info("Scores calculados e metas ordenadas.")
    return scored_goals

def allocate(balance_free: float, scored: List[Tuple[Goal, float]]) -> Dict[int, float]:
    """
    Distribui o saldo livre entre as metas proporcionalmente ao score, respeitando o remaining.
    Redistribui sobras se uma meta for totalmente financiada.
    """
    logger.info(f"Iniciando alocação de {balance_free:.2f} entre {len(scored)} metas.")
    
    allocation_plan: Dict[int, float] = {}
    total_allocated = 0.0
    
    # Filtra metas com remaining > 0 e score > 0
    allocatable_goals = [(g, s) for g, s in scored if g.remaining > 0 and s > 0]

    if not allocatable_goals:
        logger.info("Nenhuma meta elegível para alocação (remaining <= 0 ou score <= 0).")
        return {}

    # Loop para distribuir e redistribuir
    while balance_free > 0.01 and allocatable_goals: # Usar um pequeno epsilon para float comparison
        current_total_score = sum(s for g, s in allocatable_goals)
        if current_total_score == 0:
            logger.warning("Soma total dos scores elegíveis é zero, impossível alocar mais.")
            break

        remaining_balance_to_distribute = balance_free
        newly_allocated_this_round = 0.0
        
        next_allocatable_goals = []
        for goal, score in allocatable_goals:
            if score == 0: # Evita divisão por zero
                continue

            # Proporção do score em relação ao total de scores elegíveis
            proportion = score / current_total_score
            
            # Valor proposto para esta meta
            proposed_amount = remaining_balance_to_distribute * proportion
            
            # Limita o valor ao remaining da meta
            actual_amount = min(proposed_amount, goal.remaining)
            
            # Adiciona ao plano de alocação
            allocation_plan[goal.id] = allocation_plan.get(goal.id, 0.0) + actual_amount
            total_allocated += actual_amount
            newly_allocated_this_round += actual_amount
            
            # Atualiza o remaining da meta para a próxima iteração (se houver)
            goal.remaining -= actual_amount
            
            # Se a meta ainda não foi totalmente financiada, mantém para a próxima rodada
            if goal.remaining > 0.01: # Epsilon para float comparison
                next_allocatable_goals.append((goal, score))
            else:
                logger.info(f"Meta {goal.name} (ID: {goal.id}) totalmente financiada.")
        
        # Se nada foi alocado nesta rodada, significa que não há mais metas elegíveis ou saldo
        if newly_allocated_this_round < 0.01: # Epsilon para float comparison
            logger.info("Nenhuma alocação significativa nesta rodada. Encerrando.")
            break

        balance_free -= newly_allocated_this_round
        allocatable_goals = next_allocatable_goals

    logger.info(f"Alocação concluída. Total alocado: {total_allocated:.2f}.")
    return allocation_plan

def update_weights(history_df: pd.DataFrame, w: Dict[str, float], lr: float = 0.05) -> Dict[str, float]:
    """
    Ajusta os pesos para reduzir o erro entre o planejado e o realizado.
    history_df deve conter colunas como 'goal_id', 'month', 'planned_amount', 'actual_amount'.
    """
    logger.info("Iniciando ajuste de pesos.")
    updated_weights = w.copy()

    if history_df.empty or len(history_df.columns.intersection(["goal_id", "month", "planned_amount", "actual_amount"])) < 4:
        logger.warning("Dados históricos insuficientes para ajustar pesos. Retornando pesos originais.")
        return updated_weights

    # Exemplo simplificado: ajustar pesos com base no erro médio
    # Isso é um placeholder. Um ajuste real exigiria um modelo de otimização mais complexo.
    # Por exemplo, se o 'funded_pct' estiver sempre muito alto e as metas não forem atingidas,
    # talvez o peso de 'funded_pct' deva ser reduzido ou o de 'urgency' aumentado.

    # Para demonstração, vamos simular um ajuste baseado em um erro fictício
    # Suponha que queremos que o funded_pct seja mais influente se as metas não estiverem sendo atingidas
    # E que a urgência seja mais influente se metas com due_date próximo estiverem falhando

    # Calcular um "erro" geral (exemplo)
    history_df["error"] = history_df["planned_amount"] - history_df["actual_amount"]
    mean_error = history_df["error"].mean()

    # Ajuste de exemplo: se o erro médio for positivo (planejado > realizado), significa que estamos superestimando
    # a capacidade de alocação ou subestimando a dificuldade. Podemos tentar aumentar o peso de funded_pct
    # ou diminuir o de urgência/impacto.
    
    # Este é um algoritmo de ajuste de pesos muito simplificado e heurístico.
    # Em um cenário real, você usaria algoritmos de otimização (e.g., gradiente descendente)
    # para minimizar uma função de custo que mede o erro de previsão/alocação.
    
    # Apenas para garantir que os pesos não explodam ou fiquem negativos
    for key in updated_weights:
        if key == "funded_pct": # Exemplo: se o erro é positivo, aumentamos o peso de funded_pct
            updated_weights[key] = np.clip(updated_weights[key] + lr * mean_error, 0.0, 1.0)
        else:
            updated_weights[key] = np.clip(updated_weights[key] - lr * mean_error, 0.0, 1.0)

    # Normaliza os pesos para que a soma seja 1 (se desejado, dependendo da interpretação dos pesos)
    # total_w = sum(updated_weights.values())
    # if total_w > 0:
    #     updated_weights = {k: v / total_w for k, v in updated_weights.items()}

    logger.info(f"Pesos ajustados: {updated_weights}")
    return updated_weights


