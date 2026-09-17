"""
Projeção determinística de renda fixa.

Nada de LLM aqui: juros compostos + tabela regressiva de IR.
Resultado auditável, reproduzível e de custo zero — que é exatamente
o que se espera de um assessor. O LLM entra depois, só para explicar.
"""
from dataclasses import dataclass
from typing import List, Tuple


def aliquota_ir(dias: int) -> float:
    """Tabela regressiva do IR sobre renda fixa. Incide só sobre o rendimento."""
    if dias <= 180:
        return 0.225
    if dias <= 360:
        return 0.20
    if dias <= 720:
        return 0.175
    return 0.15


def taxa_poupanca_aa(selic_aa: float, tr_aa: float = 0.0) -> float:
    """
    Regra vigente da poupança:
      - Selic > 8,5% a.a.  -> 0,5% a.m. + TR  (~6,17% a.a. + TR)
      - Selic <= 8,5% a.a. -> 70% da Selic + TR
    """
    if selic_aa > 0.085:
        base_aa = (1 + 0.005) ** 12 - 1
    else:
        base_aa = 0.70 * selic_aa
    return base_aa + tr_aa


def taxa_cdb(percent_cdi: float, cdi_aa: float) -> float:
    """CDB/LCI/LCA pós-fixado: % do CDI."""
    return cdi_aa * (percent_cdi / 100.0)


def taxa_ipca_mais(ipca_aa: float, juro_real_aa: float) -> float:
    """Tesouro IPCA+ / CDB IPCA+: composição correta (não é só somar)."""
    return (1 + ipca_aa) * (1 + juro_real_aa) - 1


@dataclass
class ResultadoRF:
    nome: str
    taxa_aa: float
    isento_ir: bool
    principal: float
    meses: int
    valor_bruto: float
    ir: float
    valor_liquido: float
    serie: List[Tuple[int, float]]  # [(mes, valor_bruto)] para o gráfico

    @property
    def rendimento_liquido(self) -> float:
        return self.valor_liquido - self.principal

    @property
    def rentabilidade_liquida_pct(self) -> float:
        return (self.valor_liquido / self.principal - 1) * 100

    @property
    def liquido_aa_equivalente(self) -> float:
        return (self.valor_liquido / self.principal) ** (12 / self.meses) - 1


def projetar(nome: str, principal: float, taxa_aa: float,
             meses: int, isento_ir: bool = False) -> ResultadoRF:
    taxa_am = (1 + taxa_aa) ** (1 / 12) - 1
    valor = principal
    serie = [(0, principal)]
    for m in range(1, meses + 1):
        valor *= (1 + taxa_am)
        serie.append((m, valor))

    bruto = valor
    rendimento = bruto - principal
    ir = 0.0 if isento_ir else rendimento * aliquota_ir(meses * 30)
    liquido = bruto - ir

    return ResultadoRF(
        nome=nome, taxa_aa=taxa_aa, isento_ir=isento_ir,
        principal=principal, meses=meses, valor_bruto=bruto,
        ir=ir, valor_liquido=liquido, serie=serie,
    )
