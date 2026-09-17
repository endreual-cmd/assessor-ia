"""
Cliente brapi.dev — cotações e fundamentos da B3.

Token opcional: PETR4, VALE3, ITUB4 e MGLU3 respondem sem token (sandbox),
então o app demonstra ao vivo mesmo sem cadastro. Com BRAPI_TOKEN no ambiente,
todos os ativos ficam disponíveis (plano gratuito: 15.000 req/mês).

Degradação graciosa: qualquer falha de rede ou de plano devolve None e o
app continua funcionando com as tools determinísticas.
"""
import os
import requests

BASE = "https://brapi.dev/api"
SANDBOX = {"PETR4", "VALE3", "ITUB4", "MGLU3"}


def _headers() -> dict:
    token = os.getenv("BRAPI_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def cotacao(ticker: str) -> dict | None:
    ticker = ticker.strip().upper()
    try:
        r = requests.get(
            f"{BASE}/quote/{ticker}",
            headers=_headers(),
            params={"modules": "defaultKeyStatistics,financialData"},
            timeout=8,
        )
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        return results[0] if results else None
    except requests.RequestException:
        return None


def resumo(ticker: str) -> dict | None:
    """Extrai um punhado de campos úteis da resposta bruta da brapi."""
    dado = cotacao(ticker)
    if not dado:
        return None
    stats = dado.get("defaultKeyStatistics") or {}
    fin = dado.get("financialData") or {}
    return {
        "ticker": dado.get("symbol"),
        "nome": dado.get("longName") or dado.get("shortName"),
        "preco": dado.get("regularMarketPrice"),
        "variacao_pct": dado.get("regularMarketChangePercent"),
        "pl": stats.get("priceEarnings") or dado.get("priceEarnings"),
        "dy": stats.get("dividendYield"),
        "roe": fin.get("returnOnEquity"),
        "sandbox": ticker.strip().upper() in SANDBOX,
    }
