"""
Assessor IA — demo de agente de investimentos (case).

Arquitetura de menor custo possível:
- A matemática (projeção RF, métricas de carteira) roda em Python puro: R$0
  e sem risco de alucinação.
- O LLM (opcional, Gemini Flash free tier) só roteia e redige o parecer.
- Dados de mercado via brapi.dev (plano gratuito), token opcional.

Rodar:  streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import agente
from tools import carteira as ct
from tools import mercado as mkt
from tools import renda_fixa as rf

st.set_page_config(page_title="Assessor IA — Demo", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------- #
# Barra lateral: arquitetura + cenário macro
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Arquitetura")
    st.markdown(
        "```\n"
        "Pergunta\n"
        "   │\n"
        "ROTEADOR (LLM leve / heurística)\n"
        "   │  escolhe a tool\n"
        "TOOLS DETERMINÍSTICAS  ← as contas\n"
        "  • projeção renda fixa   (R$0)\n"
        "  • análise de carteira   (R$0)\n"
        "  • cotação B3 (brapi)    (R$0)\n"
        "   │  números\n"
        "SINTETIZADOR (LLM opcional)\n"
        "   │\n"
        "Parecer + gráfico\n"
        "```"
    )
    st.caption(
        "LLM ativo" if agente.tem_llm()
        else "Modo demo: sem LLM (defina GEMINI_API_KEY para ativar)"
    )

    st.divider()
    st.subheader("Cenário macro")
    cdi = st.number_input("CDI (% a.a.)", value=10.5, step=0.25) / 100
    ipca = st.number_input("IPCA (% a.a.)", value=4.0, step=0.25) / 100
    selic = st.number_input("Selic (% a.a.)", value=10.5, step=0.25) / 100

st.title("📈 Assessor IA")
st.caption(
    "Agente de análise e projeção de investimentos • case demonstrativo. "
    "**Conteúdo informativo — não constitui recomendação de investimento.**"
)

aba_rf, aba_cart, aba_ativo = st.tabs(
    ["Projeção — Renda Fixa", "Análise de Carteira", "Consulta de Ativo (B3)"]
)

# --------------------------------------------------------------------------- #
# ABA 1 — Projeção de renda fixa
# --------------------------------------------------------------------------- #
with aba_rf:
    c1, c2, c3 = st.columns(3)
    principal = c1.number_input("Valor inicial (R$)", value=10000.0, step=1000.0)
    meses = c2.number_input("Prazo (meses)", value=24, step=6, min_value=1)
    pct_cdi = c3.number_input("CDB — % do CDI", value=100.0, step=5.0)
    juro_real = c3.number_input("Tesouro IPCA+ — juro real (% a.a.)", value=6.0, step=0.25) / 100

    resultados = [
        rf.projetar("CDB pós (% CDI)", principal, rf.taxa_cdb(pct_cdi, cdi), meses),
        rf.projetar("Tesouro IPCA+", principal, rf.taxa_ipca_mais(ipca, juro_real), meses),
        rf.projetar("LCI/LCA (90% CDI, isento)", principal, rf.taxa_cdb(90, cdi), meses, isento_ir=True),
        rf.projetar("Poupança", principal, rf.taxa_poupanca_aa(selic), meses, isento_ir=True),
    ]
    resultados.sort(key=lambda r: r.valor_liquido, reverse=True)

    tabela = pd.DataFrame([{
        "Produto": r.nome,
        "Taxa a.a.": f"{r.taxa_aa*100:.2f}%",
        "Bruto": f"R$ {r.valor_bruto:,.2f}",
        "IR": f"R$ {r.ir:,.2f}",
        "Líquido": f"R$ {r.valor_liquido:,.2f}",
        "Rent. líq.": f"{r.rentabilidade_liquida_pct:.2f}%",
        "Líq. a.a. equiv.": f"{r.liquido_aa_equivalente*100:.2f}%",
    } for r in resultados])
    st.dataframe(tabela, use_container_width=True, hide_index=True)

    fig = go.Figure()
    for r in resultados:
        fig.add_trace(go.Scatter(
            x=[m for m, _ in r.serie],
            y=[v for _, v in r.serie],
            mode="lines", name=r.nome,
        ))
    fig.update_layout(
        title="Evolução do valor bruto acumulado",
        xaxis_title="Meses", yaxis_title="R$", height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    melhor = resultados[0]
    dif = melhor.valor_liquido - resultados[-1].valor_liquido
    contexto = (
        f"Cenário: CDI {cdi*100:.2f}% a.a., IPCA {ipca*100:.2f}% a.a., "
        f"Selic {selic*100:.2f}% a.a. Aporte R$ {principal:,.2f} por {meses} meses.\n"
        + "\n".join(
            f"- {r.nome}: líquido R$ {r.valor_liquido:,.2f} "
            f"({r.rentabilidade_liquida_pct:.2f}%)"
            for r in resultados
        )
        + f"\nMaior líquido: {melhor.nome}. Diferença para o pior: R$ {dif:,.2f}."
    )
    st.markdown("#### Parecer")
    st.markdown(agente.sintetizar(contexto))

# --------------------------------------------------------------------------- #
# ABA 2 — Análise de carteira
# --------------------------------------------------------------------------- #
with aba_cart:
    st.write("Edite a carteira (pesos são normalizados para 100%):")
    base = pd.DataFrame({
        "Ativo": ["Renda Fixa", "Ações BR", "FIIs", "Exterior"],
        "Peso %": [50.0, 25.0, 15.0, 10.0],
        "Retorno esp. % a.a.": [10.5, 14.0, 11.0, 12.0],
        "Volatilidade % a.a.": [1.0, 25.0, 15.0, 18.0],
    })
    editada = st.data_editor(base, use_container_width=True, hide_index=True, num_rows="dynamic")

    ativos = [
        ct.Ativo(row["Ativo"], row["Peso %"] / 100,
                 row["Retorno esp. % a.a."] / 100, row["Volatilidade % a.a."] / 100)
        for _, row in editada.iterrows()
        if str(row["Ativo"]).strip()
    ]

    if ativos:
        res = ct.analisar(ativos, taxa_livre_risco_aa=cdi)
        m1, m2, m3 = st.columns(3)
        m1.metric("Retorno esperado", f"{res['retorno_esperado_aa']*100:.2f}% a.a.")
        m2.metric("Volatilidade", f"{res['volatilidade_aa']*100:.2f}% a.a.")
        m3.metric("Índice de Sharpe", f"{res['sharpe']:.2f}")

        g1, g2 = st.columns(2)
        pie = px.pie(
            names=list(res["pesos"].keys()),
            values=[p * 100 for p in res["pesos"].values()],
            title="Alocação",
        )
        g1.plotly_chart(pie, use_container_width=True)

        scatter = px.scatter(
            x=[a.vol_aa * 100 for a in ativos],
            y=[a.retorno_aa * 100 for a in ativos],
            text=[a.nome for a in ativos],
            labels={"x": "Volatilidade % a.a.", "y": "Retorno % a.a."},
            title="Risco × Retorno por ativo",
        )
        scatter.update_traces(textposition="top center", marker=dict(size=12))
        g2.plotly_chart(scatter, use_container_width=True)

        contexto = (
            f"Carteira com {len(ativos)} classes. "
            f"Retorno esperado {res['retorno_esperado_aa']*100:.2f}% a.a., "
            f"volatilidade {res['volatilidade_aa']*100:.2f}% a.a., "
            f"Sharpe {res['sharpe']:.2f} (livre de risco = CDI {cdi*100:.2f}%).\n"
            + "\n".join(f"- {a.nome}: {res['pesos'][a.nome]*100:.1f}% da carteira"
                        for a in ativos)
        )
        st.markdown("#### Parecer")
        st.markdown(agente.sintetizar(contexto))

# --------------------------------------------------------------------------- #
# ABA 3 — Consulta de ativo (brapi)
# --------------------------------------------------------------------------- #
with aba_ativo:
    st.write("Cotação e fundamentos da B3. Sem token: PETR4, VALE3, ITUB4, MGLU3.")
    ticker = st.text_input("Ticker", value="PETR4").strip().upper()
    if st.button("Consultar"):
        dados = mkt.resumo(ticker)
        if not dados:
            st.warning(
                "Não foi possível obter os dados agora (rede, ticker inválido "
                "ou limite do plano). As demais abas seguem funcionando — "
                "degradação graciosa por design."
            )
        else:
            st.subheader(f"{dados['ticker']} — {dados.get('nome') or ''}")
            k1, k2, k3, k4 = st.columns(4)
            preco = dados.get("preco")
            k1.metric("Preço", f"R$ {preco:,.2f}" if preco else "—")
            var = dados.get("variacao_pct")
            k2.metric("Variação", f"{var:.2f}%" if var is not None else "—")
            pl = dados.get("pl")
            k3.metric("P/L", f"{pl:.2f}" if pl else "—")
            dy = dados.get("dy")
            k4.metric("Dividend Yield", f"{dy:.2f}%" if dy else "—")
            if dados.get("sandbox"):
                st.caption("Ticker de sandbox (não exige token).")

st.divider()
st.caption(
    "Demo de arquitetura agentic. As contas são determinísticas; o LLM apenas "
    "roteia e redige. Conteúdo informativo — não constitui recomendação de "
    "investimento (análise regulada pela CVM)."
)
