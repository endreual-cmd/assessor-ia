# CONTEXTO DO PROJETO — Assessor IA (case) + Agente vertical-agnóstico

> Documento de contexto único. Consolida a visão, a arquitetura, as decisões
> de custo e o caminho do case até o produto comercial. Feito para retomar o
> projeto, passar a um colaborador ou servir de contexto a outra IA.
> Fatos de mercado conferidos em setembro/2026 (free tiers mudam — revalidar).

---

## 1. Visão geral

Produto: **agentes de IA para pequenas e médias empresas** que fazem
atendimento e análise automatizados a partir de fontes internas (agentic RAG).

Dois enquadramentos do mesmo produto:

- **Alvo comercial:** agente de WhatsApp de *primeiro atendimento* para
  escritórios de advocacia. O cliente descreve o caso; o agente classifica,
  busca em conhecimento jurídico interno, responde e agenda a consulta.
- **Case / demonstração (este repositório):** *assessor de investimentos*.
  Mesma arquitetura, mas com dados públicos e custo zero — serve para provar a
  tecnologia no LinkedIn e em apresentações a clientes, antes de vender.

**Tese central:** a arquitetura é **vertical-agnóstica**. Troca-se a base de
conhecimento e as ferramentas; o padrão do agente permanece. "Se funciona com
investimentos, funciona com jurídico, imobiliário, saúde etc."

---

## 2. Princípio de arquitetura (o que barateia E dá precisão)

O ponto que define o projeto: **a matemática fica FORA do LLM.**

- Projeção de renda fixa é juros compostos + IR. Balanço de carteira é
  álgebra (retorno, volatilidade, Sharpe). Isso é código determinístico:
  custo zero, resultado auditável e **sem risco de alucinação** — inegociável
  num contexto financeiro/jurídico.
- O LLM faz só duas coisas: **rotear** (entender a intenção) e **sintetizar**
  (transformar números em linguagem). São as duas únicas chamadas pagas, e
  cabem em free tier.
- É o padrão agentic estudado no curso (owshq-mec, ws-1/ws-2):
  **Classificar → Executar ferramentas → Sintetizar**, com tool calling
  (o LLM decide *qual* ferramenta chamar; a ferramenta faz a conta de graça).
- **Degradação graciosa:** o LLM é opcional. Sem chave, o app roteia por
  heurística e redige por template — continua funcionando.

---

## 3. Arquitetura

```
Pergunta do usuário  (Streamlit / WhatsApp / Telegram)
   │
ROTEADOR .................. LLM leve (Gemini Flash) ou heurística — R$0
   │  classifica intenção e escolhe a(s) ferramenta(s)
FERRAMENTAS DETERMINÍSTICAS ...... as CONTAS, em Python puro — R$0
   • projeção de renda fixa   (juros compostos + IR regressivo)
   • análise de carteira      (retorno, volatilidade, Sharpe, rebalance)
   • cotação/fundamentos B3   (brapi.dev)
   • indicadores macro        (Selic, CDI, IPCA)
   │  números + contexto recuperado
RAG LOCAL ................. FAISS/Chroma + embeddings — R$0
   │  (glossário, metodologia, características de produtos)
SINTETIZADOR .............. LLM opcional redige o parecer
   │
Resposta em texto + gráfico
```

Mapeamento para os "cognitive domains" do ws-1:
- **Router** → classificação (Pydantic/structured output).
- **Memory** → RAG local (busca vetorial).
- **Brain** → síntese com LLM.
- **Ledger** → dados estruturados (no case: tools de cálculo; no produto:
  CRM/agenda via SQL).

---

## 4. Este repositório (assessor-ia)

```
assessor-ia/
├── app.py              # UI Streamlit — 3 abas + gráficos
├── agente.py           # roteador + sintetizador (LLM opcional, fallback)
├── tools/
│   ├── renda_fixa.py   # projeção determinística (juros compostos + IR)
│   ├── carteira.py     # retorno, volatilidade, Sharpe, rebalanceamento
│   ├── mercado.py      # cliente brapi.dev (token opcional, degradação graciosa)
│   └── macro.py        # BCB SGS + Focus + Tesouro Direto (dados oficiais, sem token)
├── requirements.txt
├── README.md           # como rodar e fazer deploy
└── CONTEXTO.md         # este arquivo
```

O "Cenário macro" (sidebar) e a taxa de Tesouro IPCA+ nascem com dados oficiais
correntes (BCB SGS + Tesouro Transparente, sem token), não com números digitados
à mão — e seguem editáveis. Um expansor mostra a mediana do Boletim Focus
(projeção de mercado para Selic/IPCA), que também entra no parecer da LLM.
Falha em qualquer fonte oficial cai de volta nos defaults manuais anteriores —
mesma degradação graciosa das demais tools.

O que cada aba entrega:
- **Projeção — Renda Fixa:** compara CDB %CDI, Tesouro IPCA+, LCI/LCA isenta e
  poupança, do bruto ao líquido, com gráfico de evolução e parecer.
- **Análise de Carteira:** métricas da carteira + alocação e risco×retorno em
  gráfico + parecer.
- **Consulta de Ativo (B3):** preço e fundamentos via brapi.

Insight de demonstração (validado no cálculo): uma **LCI/LCA isenta a 90% do
CDI rende mais líquido que um CDB a 100% do CDI**, porque a isenção de IR supera
a taxa bruta maior. É o gancho que justifica manter a matemática fora do LLM —
precisão que um chatbot puro não garante.

---

## 5. Stack de menor custo (números reais, set/2026)

| Camada | Escolha | Custo | Observação |
|---|---|---|---|
| Contas | Python puro (numpy/pandas) | R$ 0 | Determinístico, auditável |
| LLM | Gemini Flash (free tier) | R$ 0 | Permanente, só modelos Flash, limitado por RPM/RPD |
| LLM (alternativas) | Ollama local / Groq | R$ 0 | Ollama = offline total; Groq = free tier rápido |
| LLM (pago barato) | Claude Haiku | centavos/chamada | Se quiser ficar no ecossistema Anthropic |
| Dados BR (B3) | brapi.dev (free) | R$ 0 | 15.000 req/mês; cotações e fundamentos |
| Dados oficiais (macro) | BCB SGS + Expectativas (Focus) + Tesouro Transparente | R$ 0 | Sem token; Selic/CDI/IPCA correntes, projeção de mercado e taxas reais do Tesouro Direto — `tools/macro.py` |
| Dados (backup) | yfinance | R$ 0 | Fonte gratuita independente |
| Vetor/RAG | FAISS/Chroma local | R$ 0 | Não precisa de banco hospedado no case |
| Hospedagem | Streamlit Community Cloud | R$ 0 | Gera URL pública `*.streamlit.app` |

Sem token, a brapi já responde PETR4/VALE3/ITUB4/MGLU3 — dá pra demonstrar ao
vivo sem cadastro. **Custo total do case: R$ 0.**

Chaves opcionais (variáveis de ambiente):
- `GEMINI_API_KEY` — ativa o LLM (aistudio.google.com).
- `BRAPI_TOKEN` — libera todos os ativos da B3.

---

## 6. Do case ao produto (advocacia)

O que muda ao adaptar este case para o produto vendável:

| Elemento | No case (investimentos) | No produto (advocacia) |
|---|---|---|
| Base de conhecimento | Glossário/metodologia | Jurisprudência + pareceres do escritório (RAG) |
| Canal | Streamlit/Telegram | WhatsApp Business API |
| Ferramentas | Cálculo financeiro | Agendamento, CRM, notificação ao advogado |
| Dados estruturados | Tools de cálculo | Clientes/agenda em SQL |

Custos operacionais estimados do **produto** (faixas a validar, não são preços
fechados): WhatsApp Business API, LLM, banco vetorial, hospedagem e manutenção
somam algo em torno de **R$ 2.700–5.400/mês** para 100–500 conversas/mês. O peso
some rápido acima disso porque a maior parte da inteligência é determinística.

Faixas de preço cogitadas (hipóteses de posicionamento, a testar com clientes
reais — não tratar como projeção garantida): Starter ~R$ 2.990, Profissional
~R$ 6.990, Enterprise ~R$ 14.990 por mês, escalando por volume de conversas e
número de áreas atendidas.

---

## 7. Enquadramento regulatório (relevante porque vai a público)

- **Investimentos:** recomendação personalizada de valores mobiliários é
  atividade regulada pela CVM (análise → Resolução CVM 20; robo-advisor tem
  regramento próprio). O case deve se posicionar como **análise/projeção
  informativa e educacional**, com disclaimer explícito de "não constitui
  recomendação de investimento". Já embutido na UI e nos pareceres.
- **Advocacia:** atenção a regras de publicidade da OAB e à LGPD (dados
  sensíveis de clientes). O agente faz *primeiro atendimento e triagem*; a
  decisão jurídica é sempre do advogado.

Além de correto, esse cuidado sinaliza maturidade de produto — recrutador de
fintech e cliente sério reparam.

---

## 8. Roadmap / próximos passos

1. Rodar o case localmente e fazer deploy no Streamlit Cloud (link público).
2. Diagrama de arquitetura (imagem) para o post/apresentação.
3. Texto do post de LinkedIn apresentando o case.
4. Adaptar a mesma arquitetura para a vertical alvo (advocacia): trocar RAG,
   canal e ferramentas.

---

## 9. Como retomar (resumo operacional)

```bash
# rodar local
pip install -r requirements.txt
streamlit run app.py            # abre em http://localhost:8501, sem chaves

# opcional
export GEMINI_API_KEY="..."     # parecer em linguagem natural
export BRAPI_TOKEN="..."        # todos os ativos da B3
```

Decisões que não devem regredir:
- Matemática **sempre** determinística (fora do LLM).
- LLM **sempre** opcional (degradação graciosa).
- Fontes de dados **gratuitas** no case.
- Disclaimer informativo **sempre** presente na saída.
