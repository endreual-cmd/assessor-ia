"""
Camada de agente: roteador + sintetizador.

O LLM é OPCIONAL. Sem chave, o roteamento cai numa heurística e a redação
do parecer usa um template — o app roda 100% de graça, sem cadastro.
Com GEMINI_API_KEY, o Gemini Flash (free tier) cuida do roteamento e da
redação. Esse é o padrão de degradação graciosa: a inteligência melhora
quando há chave, mas nunca é pré-requisito para funcionar.
"""
import os

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
INTENCOES = {"projecao_rf", "balanco_carteira", "analise_ativo", "conceitual"}


def tem_llm() -> bool:
    return bool(GEMINI_KEY)


# --------------------------------------------------------------------------- #
# Roteamento
# --------------------------------------------------------------------------- #
def rotear(pergunta: str) -> str:
    if tem_llm():
        try:
            return _rotear_llm(pergunta)
        except Exception:
            pass
    return _rotear_heuristica(pergunta)


def _rotear_heuristica(pergunta: str) -> str:
    p = pergunta.lower()
    if any(k in p for k in ["carteira", "balanç", "alocaç", "rebalance", "sharpe", "diversif"]):
        return "balanco_carteira"
    if any(k in p for k in ["cdb", "tesouro", "renda fixa", "lci", "lca", "poupanç", "projet"]):
        return "projecao_rf"
    if any(k in p for k in ["ação", "acao", "papel", "p/l", "dividend", "ticker", "petr", "vale"]):
        return "analise_ativo"
    return "conceitual"


def _gemini():
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_KEY)
    return genai.GenerativeModel("gemini-1.5-flash")


def _rotear_llm(pergunta: str) -> str:
    prompt = (
        "Classifique a pergunta do usuário em UMA destas categorias e responda "
        "somente com o rótulo, sem pontuação:\n"
        "projecao_rf, balanco_carteira, analise_ativo, conceitual\n\n"
        f"Pergunta: {pergunta}"
    )
    label = _gemini().generate_content(prompt).text.strip().lower()
    return label if label in INTENCOES else "conceitual"


# --------------------------------------------------------------------------- #
# Síntese do parecer
# --------------------------------------------------------------------------- #
def sintetizar(contexto: str) -> str:
    """
    Recebe um bloco de texto com os números já calculados pelas tools e
    devolve um parecer em linguagem de assessor.
    """
    if tem_llm():
        try:
            return _sintetizar_llm(contexto)
        except Exception:
            pass
    return _sintetizar_template(contexto)


def _sintetizar_llm(contexto: str) -> str:
    prompt = (
        "Você é um assessor de investimentos escrevendo para um cliente leigo. "
        "Com base EXCLUSIVAMENTE nos números abaixo (não invente valores), "
        "escreva um parecer curto, claro e objetivo, em português. "
        "Não recomende compra/venda; apenas compare e explique os trade-offs. "
        "Feche lembrando que é conteúdo informativo, não recomendação.\n\n"
        f"{contexto}"
    )
    return _gemini().generate_content(prompt).text.strip()


def _sintetizar_template(contexto: str) -> str:
    return (
        "**Parecer (gerado sem LLM — modo demonstração)**\n\n"
        + contexto
        + "\n\n_Adicione uma `GEMINI_API_KEY` para que o agente redija este "
        "parecer em linguagem natural. Conteúdo informativo, não constitui "
        "recomendação de investimento._"
    )
