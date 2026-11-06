"""
Catálogo de produtos de renda fixa vendidos por bancos e corretoras no Brasil
+ projeção determinística do bruto ao líquido.

Mesmo princípio do resto do projeto: nada de LLM aqui. As regras (IR, IOF,
FGC, carência, custódia, come-cotas) são dados e código auditáveis.

Regras conferidas em nov/2026 (ver FONTES no fim do arquivo). Mudanças de
tributação e de carência acontecem com frequência — revalidar a cada semestre.

Convenções de taxa em `projetar_produto(..., taxa=...)`:
  POS_CDI   -> % do CDI            (ex.: 105  = 105% do CDI)
  CDI_MAIS  -> spread % a.a.       (ex.: 1.5  = CDI + 1,5% a.a.)
  PRE       -> taxa % a.a.         (ex.: 13.2 = 13,2% a.a.)
  IPCA_MAIS -> juro real % a.a.    (ex.: 7.4  = IPCA + 7,4% a.a.)
  SELIC     -> spread % a.a.       (ex.: 0.05 = Selic + 0,05%; Tesouro Selic ~0)
  POUPANCA  -> ignorada (regra oficial da poupança)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from tools.renda_fixa import aliquota_ir, taxa_poupanca_aa


# --------------------------------------------------------------------------- #
# Tipos
# --------------------------------------------------------------------------- #
class Indexador(str, Enum):
    POS_CDI = "pos_cdi"
    CDI_MAIS = "cdi_mais"
    PRE = "pre"
    IPCA_MAIS = "ipca_mais"
    SELIC = "selic"
    POUPANCA = "poupanca"


ROTULO_INDEXADOR = {
    Indexador.POS_CDI: "% do CDI",
    Indexador.CDI_MAIS: "CDI + spread",
    Indexador.PRE: "Prefixado",
    Indexador.IPCA_MAIS: "IPCA + juro real",
    Indexador.SELIC: "Selic + spread",
    Indexador.POUPANCA: "Regra da poupança",
}


class Tributacao(str, Enum):
    REGRESSIVA = "regressiva"            # 22,5% -> 15% conforme o prazo
    ISENTA_PF = "isenta_pf"              # isenta para pessoa física
    COME_COTAS_LP = "come_cotas_lp"      # fundo longo prazo: 15% semestral + regressiva
    COME_COTAS_CP = "come_cotas_cp"      # fundo curto prazo: 20% semestral; 22,5%/20%


@dataclass(frozen=True)
class ProdutoRF:
    codigo: str
    nome: str
    categoria: str                       # Bancário | Tesouro Direto | Crédito privado | Fundo | Poupança
    emissor: str
    indexadores: Tuple[Indexador, ...]
    tributacao: Tributacao
    fgc: Optional[bool]                  # None = fontes divergem, confirmar
    garantia: str
    carencia_min_meses: Dict[Indexador, int] = field(default_factory=dict)  # mínimo regulatório
    liquidez: str = ""
    aplicacao_minima: Optional[float] = None
    aplicacao_minima_obs: str = ""
    custodia_aa: float = 0.0             # taxa B3 (Tesouro Direto)
    custodia_isencao_ate: float = 0.0    # saldo isento de custódia (Tesouro Selic)
    iof: bool = True                     # IOF regressivo em resgates < 30 dias
    observacoes: str = ""

    @property
    def isento_ir(self) -> bool:
        return self.tributacao == Tributacao.ISENTA_PF


I = Indexador
_BANCARIO_IDX = (I.POS_CDI, I.PRE, I.IPCA_MAIS)
_CREDITO_IDX = (I.CDI_MAIS, I.POS_CDI, I.PRE, I.IPCA_MAIS)

# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
CATALOGO: List[ProdutoRF] = [
    # ---------------- Bancários ----------------
    ProdutoRF(
        "CDB", "CDB — Certificado de Depósito Bancário", "Bancário",
        "Bancos comerciais, múltiplos e de investimento", _BANCARIO_IDX,
        Tributacao.REGRESSIVA, True, "FGC até R$ 250 mil por CPF por conglomerado",
        liquidez="Diária ou só no vencimento (definido pelo emissor)",
        aplicacao_minima=1.0, aplicacao_minima_obs="Em geral de R$ 1 a R$ 1.000",
        observacoes="Produto de referência para comparar os demais.",
    ),
    ProdutoRF(
        "RDB", "RDB — Recibo de Depósito Bancário", "Bancário",
        "Bancos e financeiras", _BANCARIO_IDX,
        Tributacao.REGRESSIVA, True, "FGC até R$ 250 mil por CPF por conglomerado",
        liquidez="Diária ou no vencimento; não pode ser vendido a terceiros",
        aplicacao_minima=1.0, aplicacao_minima_obs="Em geral baixo (bancos digitais)",
        observacoes="Igual ao CDB na prática, mas intransferível.",
    ),
    ProdutoRF(
        "LC", "LC — Letra de Câmbio", "Bancário",
        "Financeiras (sociedades de crédito, financiamento e investimento)", _BANCARIO_IDX,
        Tributacao.REGRESSIVA, True, "FGC até R$ 250 mil por CPF por conglomerado",
        liquidez="Em geral só no vencimento",
        aplicacao_minima=1000.0, aplicacao_minima_obs="Varia por emissor",
        observacoes="Emissores menores costumam pagar taxas mais altas que CDB de grandes bancos.",
    ),
    ProdutoRF(
        "LCI", "LCI — Letra de Crédito Imobiliário", "Bancário",
        "Bancos (lastro em crédito imobiliário)", _BANCARIO_IDX,
        Tributacao.ISENTA_PF, True, "FGC até R$ 250 mil por CPF por conglomerado",
        carencia_min_meses={I.POS_CDI: 6, I.PRE: 6, I.IPCA_MAIS: 36},
        liquidez="Após a carência pode ter liquidez diária (pós/pré)",
        aplicacao_minima=1000.0, aplicacao_minima_obs="Varia por emissor",
        observacoes="Isenta de IR para PF. Carência mínima CMN: 6 meses (pós/pré), 36 meses (IPCA).",
    ),
    ProdutoRF(
        "LCA", "LCA — Letra de Crédito do Agronegócio", "Bancário",
        "Bancos (lastro em crédito do agronegócio)", _BANCARIO_IDX,
        Tributacao.ISENTA_PF, True, "FGC até R$ 250 mil por CPF por conglomerado",
        carencia_min_meses={I.POS_CDI: 6, I.PRE: 6, I.IPCA_MAIS: 12},
        liquidez="Após a carência pode ter liquidez diária (pós/pré)",
        aplicacao_minima=1000.0, aplicacao_minima_obs="Varia por emissor",
        observacoes="Isenta de IR para PF. Carência mínima CMN: 6 meses (pós/pré), 12 meses (IPCA).",
    ),
    ProdutoRF(
        "LCD", "LCD — Letra de Crédito do Desenvolvimento", "Bancário",
        "Bancos de desenvolvimento (BNDES e outros)", (I.POS_CDI, I.PRE, I.IPCA_MAIS),
        Tributacao.ISENTA_PF, True,
        "FGC até R$ 250 mil por CPF por conglomerado (segundo fontes de mercado; confirmar no regulamento do FGC)",
        carencia_min_meses={I.POS_CDI: 12, I.PRE: 12, I.IPCA_MAIS: 12},
        liquidez="Sem resgate antecipado; após 12 meses só no mercado secundário",
        aplicacao_minima=1000.0, aplicacao_minima_obs="Varia por emissor",
        observacoes="Criada pela Lei 14.937/2024 (Res. CMN 5.169). Prazos de 1 a 5 anos.",
    ),
    ProdutoRF(
        "LIG", "LIG — Letra Imobiliária Garantida", "Bancário",
        "Bancos (carteira de crédito imobiliário segregada)", _BANCARIO_IDX,
        Tributacao.ISENTA_PF, False, "Carteira de ativos segregada do banco (covered bond); sem FGC",
        carencia_min_meses={I.POS_CDI: 12, I.PRE: 12, I.IPCA_MAIS: 12},
        liquidez="Em geral só no vencimento",
        aplicacao_minima=None, aplicacao_minima_obs="Varia; ofertas costumam ter mínimos altos",
        observacoes="Isenta de IR para PF, mas não tem FGC.",
    ),
    ProdutoRF(
        "LF", "LF — Letra Financeira", "Bancário",
        "Bancos", _BANCARIO_IDX,
        Tributacao.REGRESSIVA, False, "Risco do banco emissor; sem FGC",
        carencia_min_meses={I.POS_CDI: 24, I.PRE: 24, I.IPCA_MAIS: 24},
        liquidez="Sem resgate antecipado; só mercado secundário",
        aplicacao_minima=50000.0,
        aplicacao_minima_obs="R$ 50 mil (sênior, prazo mín. 24 meses); R$ 300 mil (subordinada, 60 meses)",
        observacoes="Paga mais que CDB por não ter FGC e ter prazo longo.",
    ),
    # ---------------- Poupança ----------------
    ProdutoRF(
        "POUPANCA", "Poupança", "Poupança", "Bancos", (I.POUPANCA,),
        Tributacao.ISENTA_PF, True, "FGC até R$ 250 mil por CPF por conglomerado",
        liquidez="Diária; rende só no aniversário mensal",
        aplicacao_minima=0.0, iof=False,
        observacoes="Selic > 8,5%: 0,5% a.m. + TR; senão 70% da Selic + TR.",
    ),
    # ---------------- Tesouro Direto ----------------
    ProdutoRF(
        "TESOURO_SELIC", "Tesouro Selic (LFT)", "Tesouro Direto", "Tesouro Nacional", (I.SELIC,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária (D+0 em dias úteis)", aplicacao_minima=30.0,
        aplicacao_minima_obs="1% do preço do título, mínimo ~R$ 30",
        custodia_aa=0.002, custodia_isencao_ate=10000.0,
        observacoes="Custódia B3 0,20% a.a. só sobre o saldo acima de R$ 10 mil.",
    ),
    ProdutoRF(
        "TESOURO_RESERVA", "Tesouro Reserva (LFT-TD1)", "Tesouro Direto", "Tesouro Nacional", (I.SELIC,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="24 horas, 7 dias por semana; sem marcação a mercado",
        aplicacao_minima=1.0,
        observacoes="Lançado em 11/05/2026; inicialmente só para clientes do Banco do Brasil. "
                    "Taxa de custódia não divulgada nas fontes consultadas (projeção usa 0).",
    ),
    ProdutoRF(
        "TESOURO_PREFIXADO", "Tesouro Prefixado (LTN)", "Tesouro Direto", "Tesouro Nacional", (I.PRE,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado (pode haver perda antes do vencimento)",
        aplicacao_minima=30.0, aplicacao_minima_obs="1% do preço do título, mínimo ~R$ 30",
        custodia_aa=0.002,
    ),
    ProdutoRF(
        "TESOURO_PREFIXADO_JUROS", "Tesouro Prefixado com Juros Semestrais (NTN-F)", "Tesouro Direto",
        "Tesouro Nacional", (I.PRE,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado", aplicacao_minima=30.0,
        custodia_aa=0.002,
        observacoes="Paga cupons semestrais (IR retido em cada cupom). Projeção simplificada reinveste os cupons.",
    ),
    ProdutoRF(
        "TESOURO_IPCA", "Tesouro IPCA+ (NTN-B Principal)", "Tesouro Direto", "Tesouro Nacional", (I.IPCA_MAIS,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado (pode haver perda antes do vencimento)",
        aplicacao_minima=30.0, custodia_aa=0.002,
    ),
    ProdutoRF(
        "TESOURO_IPCA_JUROS", "Tesouro IPCA+ com Juros Semestrais (NTN-B)", "Tesouro Direto",
        "Tesouro Nacional", (I.IPCA_MAIS,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado", aplicacao_minima=30.0, custodia_aa=0.002,
        observacoes="Paga cupons semestrais. Projeção simplificada reinveste os cupons.",
    ),
    ProdutoRF(
        "TESOURO_RENDA", "Tesouro Renda+ Aposentadoria Extra (NTN-B1)", "Tesouro Direto",
        "Tesouro Nacional", (I.IPCA_MAIS,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado; renda em 240 parcelas mensais após a data de conversão",
        aplicacao_minima=30.0,
        observacoes="Custódia zero se mantido até o vencimento; 0,10% sobre resgates acima de 6 salários mínimos. "
                    "Projeção cobre só a fase de acumulação.",
    ),
    ProdutoRF(
        "TESOURO_EDUCA", "Tesouro Educa+ (NTN-B1)", "Tesouro Direto", "Tesouro Nacional", (I.IPCA_MAIS,),
        Tributacao.REGRESSIVA, False, "Tesouro Nacional (risco soberano); não usa FGC",
        liquidez="Diária, a preço de mercado; renda em 60 parcelas mensais",
        aplicacao_minima=30.0,
        observacoes="Custódia zero se mantido até o vencimento; 0,10% sobre resgates acima de 4 salários mínimos. "
                    "Projeção cobre só a fase de acumulação.",
    ),
    # ---------------- Crédito privado ----------------
    ProdutoRF(
        "DEBENTURE", "Debênture comum", "Crédito privado", "Empresas (S.A.)", _CREDITO_IDX,
        Tributacao.REGRESSIVA, False, "Risco da empresa emissora; sem FGC",
        liquidez="Mercado secundário (baixa liquidez)", aplicacao_minima=1000.0,
        aplicacao_minima_obs="Em geral ~R$ 1.000 por unidade",
    ),
    ProdutoRF(
        "DEBENTURE_INCENTIVADA", "Debênture incentivada (Lei 12.431)", "Crédito privado",
        "Empresas de infraestrutura", _CREDITO_IDX,
        Tributacao.ISENTA_PF, False, "Risco da empresa emissora; sem FGC",
        liquidez="Mercado secundário (baixa liquidez)", aplicacao_minima=1000.0,
        observacoes="Isenta de IR para PF. Prazos longos, muito comum em IPCA+.",
    ),
    ProdutoRF(
        "DEBENTURE_INFRA", "Debênture de infraestrutura (Lei 14.801/2024)", "Crédito privado",
        "Empresas de infraestrutura", _CREDITO_IDX,
        Tributacao.REGRESSIVA, False, "Risco da empresa emissora; sem FGC",
        liquidez="Mercado secundário (baixa liquidez)", aplicacao_minima=1000.0,
        observacoes="Benefício fiscal é do emissor; para PF segue a tabela regressiva.",
    ),
    ProdutoRF(
        "CRI", "CRI — Certificado de Recebíveis Imobiliários", "Crédito privado", "Securitizadoras",
        _CREDITO_IDX, Tributacao.ISENTA_PF, False, "Recebíveis imobiliários + garantias da operação; sem FGC",
        liquidez="Mercado secundário (baixa liquidez)", aplicacao_minima=1000.0,
        observacoes="Isento de IR para PF.",
    ),
    ProdutoRF(
        "CRA", "CRA — Certificado de Recebíveis do Agronegócio", "Crédito privado", "Securitizadoras",
        _CREDITO_IDX, Tributacao.ISENTA_PF, False, "Recebíveis do agronegócio + garantias da operação; sem FGC",
        liquidez="Mercado secundário (baixa liquidez)", aplicacao_minima=1000.0,
        observacoes="Isento de IR para PF.",
    ),
    # ---------------- Fundos ----------------
    ProdutoRF(
        "FUNDO_RF_LP", "Fundo de renda fixa — longo prazo", "Fundo", "Gestoras", (I.POS_CDI, I.CDI_MAIS),
        Tributacao.COME_COTAS_LP, False, "Patrimônio segregado do fundo; sem FGC",
        liquidez="D+0 a D+30 (conforme regulamento)", aplicacao_minima=100.0,
        observacoes="Come-cotas de 15% em maio e novembro; complemento pela tabela regressiva no resgate. "
                    "Informe a taxa já líquida de taxa de administração.",
    ),
    ProdutoRF(
        "FUNDO_RF_CP", "Fundo de renda fixa — curto prazo", "Fundo", "Gestoras", (I.POS_CDI,),
        Tributacao.COME_COTAS_CP, False, "Patrimônio segregado do fundo; sem FGC",
        liquidez="D+0", aplicacao_minima=100.0,
        observacoes="Come-cotas de 20%; IR final 22,5% (até 180 dias) ou 20%.",
    ),
]

POR_CODIGO: Dict[str, ProdutoRF] = {p.codigo: p for p in CATALOGO}

FGC_LIMITE_POR_INSTITUICAO = 250_000.0
FGC_TETO_GLOBAL_4_ANOS = 1_000_000.0


# --------------------------------------------------------------------------- #
# Impostos e taxas
# --------------------------------------------------------------------------- #
# IOF regressivo (Decreto 6.306/2007): % do rendimento por dia corrido, dia 1..29.
_IOF_TABELA = [96, 93, 90, 86, 83, 80, 76, 73, 70, 66, 63, 60, 56, 53, 50,
               46, 43, 40, 36, 33, 30, 26, 23, 20, 16, 13, 10, 6, 3]


def aliquota_iof(dias: int) -> float:
    if dias <= 0:
        return 1.0
    if dias >= 30:
        return 0.0
    return _IOF_TABELA[dias - 1] / 100


def _aliquota_final_fundo_cp(dias: int) -> float:
    return 0.225 if dias <= 180 else 0.20


def taxa_aa(indexador: Indexador, taxa: float, cenario: dict) -> float:
    """Converte a taxa contratada em taxa nominal a.a. (decimal). cenario em decimais."""
    cdi, ipca, selic = cenario.get("cdi", 0.0), cenario.get("ipca", 0.0), cenario.get("selic", 0.0)
    if indexador == I.POS_CDI:
        return cdi * taxa / 100
    if indexador == I.CDI_MAIS:
        return (1 + cdi) * (1 + taxa / 100) - 1
    if indexador == I.PRE:
        return taxa / 100
    if indexador == I.IPCA_MAIS:
        return (1 + ipca) * (1 + taxa / 100) - 1
    if indexador == I.SELIC:
        return (1 + selic) * (1 + taxa / 100) - 1
    if indexador == I.POUPANCA:
        return taxa_poupanca_aa(selic, cenario.get("tr", 0.0))
    raise ValueError(f"Indexador desconhecido: {indexador}")


# --------------------------------------------------------------------------- #
# Projeção
# --------------------------------------------------------------------------- #
@dataclass
class ResultadoProduto:
    produto: ProdutoRF
    indexador: Indexador
    taxa_contratada: float
    taxa_aa: float
    principal: float
    meses: int
    valor_bruto: float
    iof: float
    custodia: float
    ir: float
    valor_liquido: float
    serie: List[Tuple[int, float]]
    alertas: List[str]

    @property
    def nome(self) -> str:
        return self.produto.nome

    @property
    def rendimento_liquido(self) -> float:
        return self.valor_liquido - self.principal

    @property
    def rentabilidade_liquida_pct(self) -> float:
        return (self.valor_liquido / self.principal - 1) * 100

    @property
    def liquido_aa_equivalente(self) -> float:
        return (self.valor_liquido / self.principal) ** (12 / self.meses) - 1


def validar(produto: ProdutoRF, indexador: Indexador, principal: float, meses: int) -> List[str]:
    alertas = []
    carencia = produto.carencia_min_meses.get(indexador, 0)
    if meses < carencia:
        alertas.append(
            f"Prazo de {meses} meses abaixo da carência mínima de {carencia} meses para "
            f"{produto.codigo} ({ROTULO_INDEXADOR[indexador]})."
        )
    if produto.aplicacao_minima and principal < produto.aplicacao_minima:
        alertas.append(
            f"Valor abaixo da aplicação mínima típica (R$ {produto.aplicacao_minima:,.2f}). "
            f"{produto.aplicacao_minima_obs}".strip()
        )
    if produto.fgc and principal > FGC_LIMITE_POR_INSTITUICAO:
        alertas.append(
            f"R$ {principal - FGC_LIMITE_POR_INSTITUICAO:,.2f} acima do limite do FGC "
            f"(R$ 250 mil por CPF por conglomerado)."
        )
    if produto.fgc is False and produto.categoria != "Tesouro Direto":
        alertas.append(f"Sem FGC: {produto.garantia}.")
    if produto.iof and meses * 30 < 30:
        alertas.append("Resgate antes de 30 dias paga IOF regressivo sobre o rendimento.")
    return alertas


def projetar_produto(codigo: str, principal: float, meses: int,
                     indexador: Indexador | str, taxa: float, cenario: dict) -> ResultadoProduto:
    """
    Projeção bruto -> líquido com IOF, custódia B3, IR (regressivo, isento ou
    come-cotas). Prazo em meses de 30 dias, como o resto do projeto.
    """
    produto = POR_CODIGO[codigo]
    indexador = Indexador(indexador)
    if indexador not in produto.indexadores:
        raise ValueError(f"{codigo} não aceita indexador {indexador.value}")

    t_aa = taxa_aa(indexador, taxa, cenario)
    t_am = (1 + t_aa) ** (1 / 12) - 1
    custodia_am = (1 + produto.custodia_aa) ** (1 / 12) - 1 if produto.custodia_aa else 0.0
    come_cotas = {Tributacao.COME_COTAS_LP: 0.15, Tributacao.COME_COTAS_CP: 0.20}.get(produto.tributacao)

    valor = principal
    custodia = 0.0
    ir_antecipado = 0.0
    base_come_cotas = principal
    serie = [(0, principal)]
    for m in range(1, meses + 1):
        valor *= 1 + t_am
        if custodia_am:
            custodia += max(0.0, valor - produto.custodia_isencao_ate) * custodia_am
        if come_cotas and m % 6 == 0 and m < meses:
            ganho = valor - base_come_cotas
            if ganho > 0:
                cobrado = ganho * come_cotas
                ir_antecipado += cobrado
                valor -= cobrado
            base_come_cotas = valor
        serie.append((m, valor))

    bruto = valor + ir_antecipado          # bruto = antes de qualquer imposto
    dias = meses * 30
    rendimento = bruto - principal
    iof = max(0.0, rendimento) * aliquota_iof(dias) if produto.iof else 0.0
    base_ir = max(0.0, rendimento - iof - custodia)

    if produto.tributacao == Tributacao.ISENTA_PF:
        ir = 0.0
    elif produto.tributacao == Tributacao.REGRESSIVA:
        ir = base_ir * aliquota_ir(dias)
    elif produto.tributacao == Tributacao.COME_COTAS_LP:
        ir = max(base_ir * aliquota_ir(dias), ir_antecipado)
    else:  # COME_COTAS_CP
        ir = max(base_ir * _aliquota_final_fundo_cp(dias), ir_antecipado)

    liquido = bruto - iof - custodia - ir
    return ResultadoProduto(
        produto=produto, indexador=indexador, taxa_contratada=taxa, taxa_aa=t_aa,
        principal=principal, meses=meses, valor_bruto=bruto, iof=iof, custodia=custodia,
        ir=ir, valor_liquido=liquido, serie=serie,
        alertas=validar(produto, indexador, principal, meses),
    )


def taxa_tributada_equivalente(taxa_isenta_aa: float, meses: int) -> float:
    """
    Gross-up: taxa a.a. que um produto tributado (tabela regressiva) precisaria
    pagar para empatar, no mesmo prazo, com um produto isento.
    """
    t = meses / 12
    ganho_isento = (1 + taxa_isenta_aa) ** t - 1
    ganho_bruto = ganho_isento / (1 - aliquota_ir(meses * 30))
    return (1 + ganho_bruto) ** (1 / t) - 1


def tabela_catalogo() -> List[dict]:
    """Linhas prontas para exibir (pandas/streamlit)."""
    def fgc_txt(p):
        return "Sim" if p.fgc else ("Não" if p.fgc is False else "Confirmar")

    def ir_txt(p):
        return {
            Tributacao.REGRESSIVA: "Regressivo 22,5%→15%",
            Tributacao.ISENTA_PF: "Isento (PF)",
            Tributacao.COME_COTAS_LP: "Come-cotas 15% + regressivo",
            Tributacao.COME_COTAS_CP: "Come-cotas 20% + 22,5%/20%",
        }[p.tributacao]

    def carencia_txt(p):
        if not p.carencia_min_meses:
            return "Livre"
        vals = sorted(set(p.carencia_min_meses.values()))
        if len(vals) == 1:
            return f"{vals[0]} meses"
        return " / ".join(f"{ROTULO_INDEXADOR[k]}: {v}m" for k, v in p.carencia_min_meses.items())

    return [{
        "Código": p.codigo,
        "Produto": p.nome,
        "Categoria": p.categoria,
        "Emissor": p.emissor,
        "Indexadores": ", ".join(ROTULO_INDEXADOR[i] for i in p.indexadores),
        "IR (PF)": ir_txt(p),
        "FGC": fgc_txt(p),
        "Carência mínima": carencia_txt(p),
        "Liquidez": p.liquidez,
        "Mínimo": p.aplicacao_minima_obs or (f"R$ {p.aplicacao_minima:,.2f}" if p.aplicacao_minima else "—"),
        "Custódia": f"{p.custodia_aa*100:.2f}% a.a." if p.custodia_aa else "—",
        "Observações": p.observacoes,
    } for p in CATALOGO]


FONTES = [
    "Isenção LCI/LCA e carências 2026 — https://investnews.com.br/investimentos/isencao-de-ir-nas-lci-e-lca-o-que-realmente-esta-valendo-nas-regras-dos-titulos-bancarios/amp/",
    "CMN reduz carência LCI/LCA para 6 meses (mai/2025) — https://www.seudinheiro.com/2025/renda-fixa/cmn-reduz-prazo-de-carencia-de-lcis-e-lcas-de-nove-para-seis-meses-julw/",
    "MP 1.303 caducou; isenções mantidas — https://blog.mycapital.com.br/reforma-tributaria-2026-imposto-de-renda-investimentos/",
    "LCD em 2026 — https://www.meelion.com/blog/?p=2987",
    "Letra Financeira (B3) — https://b3.com.br/pt_br/produtos-e-servicos/registro/renda-fixa-e-valores-mobiliarios/letra-financeira.htm",
    "Tarifas do Tesouro Direto (B3) — https://b3.com.br/pt_br/produtos-e-servicos/tarifas/tarifas-de-tesouro-direto/",
    "Tesouro Reserva — https://www.seudinheiro.com/2026/renda-fixa/tesouro-reserva-investimento-mais-barato-seguro-e-com-negociacao-24-horas-diz-secretario-do-tesouro-quais-sao-as-regras-do-novo-titulo-publico-giov/",
    "Comunicado FGC 2026 — https://www.bocombbm.com.br/bbm-content./uploads/2026/05/comunicado-fgc-2026.pdf",
]
