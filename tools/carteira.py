"""
Análise determinística de carteira.

Retorno esperado, volatilidade, índice de Sharpe e sugestão de
rebalanceamento — tudo com numpy. Zero LLM, zero alucinação.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass
class Ativo:
    nome: str
    peso: float        # alocação atual (0-1)
    retorno_aa: float  # retorno esperado a.a. (0-1)
    vol_aa: float      # volatilidade anualizada (0-1)


def _matriz_cov(ativos: List[Ativo], correlacao: Optional[np.ndarray]) -> np.ndarray:
    vols = np.array([a.vol_aa for a in ativos])
    n = len(ativos)
    if correlacao is None:
        corr = np.full((n, n), 0.30)  # correlação moderada entre classes
        np.fill_diagonal(corr, 1.0)
    else:
        corr = np.asarray(correlacao, dtype=float)
    return np.outer(vols, vols) * corr


def analisar(ativos: List[Ativo], taxa_livre_risco_aa: float,
             correlacao: Optional[np.ndarray] = None) -> dict:
    pesos = np.array([a.peso for a in ativos], dtype=float)
    pesos = pesos / pesos.sum()  # normaliza para somar 100%
    retornos = np.array([a.retorno_aa for a in ativos])
    cov = _matriz_cov(ativos, correlacao)

    ret = float(pesos @ retornos)
    vol = float(np.sqrt(pesos @ cov @ pesos))
    sharpe = (ret - taxa_livre_risco_aa) / vol if vol > 0 else 0.0

    return {
        "retorno_esperado_aa": ret,
        "volatilidade_aa": vol,
        "sharpe": sharpe,
        "taxa_livre_risco_aa": taxa_livre_risco_aa,
        "pesos": {a.nome: float(p) for a, p in zip(ativos, pesos)},
    }


def rebalancear(ativos: List[Ativo], alvo: Dict[str, float]) -> Dict[str, float]:
    """
    Compara alocação atual com a alvo e devolve o ajuste por ativo,
    em pontos percentuais (+ comprar / - vender).
    """
    total = sum(a.peso for a in ativos)
    trades = {}
    for a in ativos:
        atual = a.peso / total
        meta = alvo.get(a.nome, atual)
        trades[a.nome] = (meta - atual) * 100
    return trades
