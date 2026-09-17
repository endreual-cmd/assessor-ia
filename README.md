# Assessor IA — demo de agente de investimentos

Agente de **análise e projeção** de investimentos construído com o princípio de
menor custo possível: a matemática roda em Python puro (custo zero, sem
alucinação) e o LLM entra só para rotear e redigir o parecer.

> Conteúdo informativo. Não constitui recomendação de investimento
> (recomendação personalizada de valores mobiliários é regulada pela CVM).

## O que ele faz

- **Projeção de renda fixa** — compara CDB %CDI, Tesouro IPCA+, LCI/LCA isenta e
  poupança com juros compostos + tabela regressiva de IR, bruto → líquido, com gráfico.
- **Análise de carteira** — retorno esperado, volatilidade, índice de Sharpe e
  rebalanceamento, com alocação e risco × retorno em gráfico.
- **Consulta de ativo (B3)** — preço e fundamentos via brapi.dev (token opcional).

## Arquitetura

```
Pergunta
   │
ROTEADOR ............ LLM leve (Gemini Flash) ou heurística — R$0
   │  escolhe a ferramenta
TOOLS DETERMINÍSTICAS ... as CONTAS (Python puro) — R$0, auditável
   • projeção renda fixa
   • análise de carteira
   • cotação B3 (brapi)
   │  números
SINTETIZADOR ........ LLM opcional redige o parecer
   │
Parecer + gráfico
```

O LLM é **opcional**: sem chave, o app roda em modo demonstração (roteamento por
heurística + parecer por template). Com chave, o parecer sai em linguagem natural.
É o padrão de degradação graciosa — a inteligência melhora, mas nunca é
pré-requisito para funcionar.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`. Funciona sem nenhuma chave de API.

## Chaves opcionais (variáveis de ambiente)

- `GEMINI_API_KEY` — ativa o LLM (Gemini Flash, free tier permanente). Chave em
  aistudio.google.com.
- `BRAPI_TOKEN` — libera todos os ativos da B3 (plano gratuito: 15.000 req/mês).
  Sem token, PETR4/VALE3/ITUB4/MGLU3 já funcionam.

```bash
export GEMINI_API_KEY="sua-chave"   # opcional
export BRAPI_TOKEN="seu-token"      # opcional
```

## Deploy gratuito (link para o LinkedIn)

1. Suba esta pasta para um repositório no GitHub.
2. Entre em share.streamlit.io, conecte o repo e aponte para `app.py`.
3. (Opcional) Em *Settings → Secrets*, adicione `GEMINI_API_KEY` e `BRAPI_TOKEN`.
4. Você recebe uma URL pública `*.streamlit.app` — é o link do case.

## Custo

| Item | Custo |
|---|---|
| Contas (renda fixa, carteira) | R$ 0 — Python puro |
| Dados B3 (brapi free) | R$ 0 até 15.000 req/mês |
| LLM (Gemini Flash free) | R$ 0 (rate-limited) |
| Hospedagem (Streamlit Cloud) | R$ 0 |
| **Total do case** | **R$ 0** |

## Estrutura

```
assessor-ia/
├── app.py              # UI Streamlit (3 abas + gráficos)
├── agente.py           # roteador + sintetizador (LLM opcional)
├── tools/
│   ├── renda_fixa.py   # projeção determinística
│   ├── carteira.py     # métricas de carteira
│   └── mercado.py      # cliente brapi.dev
└── requirements.txt
```
