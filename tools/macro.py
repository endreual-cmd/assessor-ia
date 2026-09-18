"""
Cliente de dados oficiais — Banco Central (BCB) e Tesouro Nacional.

Três fontes públicas, gratuitas e sem necessidade de token:
  - BCB SGS (Sistema Gerenciador de Séries Temporais): Selic, CDI, IPCA correntes.
  - BCB Expectativas de Mercado (Boletim Focus, API Olinda/OData): mediana das
    projeções de +100 instituições para Selic e IPCA nos próximos anos.
  - Tesouro Transparente: preços e taxas reais dos títulos do Tesouro Direto.

Substituem números digitados/chutados manualmente por dados correntes e
auditáveis — mesmo princípio das outras tools: zero LLM, zero alucinação.

Degradação graciosa: qualquer falha (rede, mudança de formato na fonte)
devolve None: o app.py cai nos defaults manuais anteriores. Nada quebra.
"""
from datetime import datetime
from urllib.parse import quote

import requests

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
FOCUS_URL = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
TESOURO_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

# Códigos das séries no SGS.
SGS_SELIC_META = 432
SGS_CDI = 4389
SGS_IPCA_12M = 13522  # IPCA acumulado em 12 meses (não a variação mensal)


def _sgs_valor(codigo: int) -> float | None:
    try:
        r = requests.get(SGS_URL.format(codigo=codigo, n=1), timeout=10)
        r.raise_for_status()
        dados = r.json()
        item = dados[-1] if isinstance(dados, list) else dados
        return float(item["valor"].replace(",", "."))
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def cenario_atual() -> dict | None:
    """Selic (meta), CDI e IPCA (acum. 12m) correntes — BCB SGS."""
    selic, cdi, ipca = _sgs_valor(SGS_SELIC_META), _sgs_valor(SGS_CDI), _sgs_valor(SGS_IPCA_12M)
    if selic is None and cdi is None and ipca is None:
        return None
    return {"selic": selic, "cdi": cdi, "ipca": ipca}


def expectativas_focus() -> dict | None:
    """
    Mediana das projeções de mercado (Boletim Focus) para Selic e IPCA,
    ano corrente e seguinte.
    """
    ano_atual = datetime.now().year
    resultado = {}
    try:
        for indicador, chave in (("Selic", "selic"), ("IPCA", "ipca")):
            # Monta a query manualmente: requests.get(params=...) usa "+" para
            # espaço, mas a API OData do BCB só aceita "%20" (senão dá 400).
            filtro = quote(f"Indicador eq '{indicador}'")
            qs = f"$filter={filtro}&$orderby=Data%20desc&$top=20&$format=json"
            r = requests.get(f"{FOCUS_URL}?{qs}", timeout=12)
            r.raise_for_status()
            por_ano = {}
            for linha in r.json().get("value", []):
                ano = linha.get("DataReferencia")
                if ano and ano not in por_ano:  # já ordenado por Data desc: 1º = mais recente
                    por_ano[ano] = linha
            atual = por_ano.get(str(ano_atual))
            seguinte = por_ano.get(str(ano_atual + 1))
            resultado[chave] = {
                "ano_atual_num": ano_atual,
                "ano_atual": atual["Mediana"] if atual else None,
                "ano_seguinte_num": ano_atual + 1,
                "ano_seguinte": seguinte["Mediana"] if seguinte else None,
                "data_referencia": atual["Data"] if atual else None,
            }
        return resultado if any(v["ano_atual"] is not None for v in resultado.values()) else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def tesouro_direto_taxas() -> dict | None:
    """
    Taxas reais dos títulos do Tesouro Direto (Tesouro Transparente).

    O CSV oficial traz 20+ anos de histórico (~14 MB), mas as linhas do dia
    mais recente vêm primeiro — lemos em streaming e paramos assim que a
    "Data Base" muda, sem baixar o arquivo inteiro.
    """
    try:
        with requests.get(TESOURO_CSV_URL, stream=True, timeout=15) as r:
            r.raise_for_status()
            titulos, primeira_data = [], None
            for linha in r.iter_lines(decode_unicode=True):
                if not linha or linha.startswith("Tipo Titulo"):
                    continue
                campos = linha.split(";")
                if len(campos) < 5:
                    continue
                tipo, venc, data_base, _taxa_compra, taxa_venda = campos[:5]
                if primeira_data is None:
                    primeira_data = data_base
                if data_base != primeira_data:
                    break  # saiu do dia mais recente: já temos tudo que precisamos
                if "Juros Semestrais" in tipo:
                    continue  # foco nos títulos "simples", mais comparáveis ao CDB/LCI
                try:
                    titulos.append({
                        "tipo": tipo,
                        "vencimento": venc,
                        "taxa_venda_aa": float(taxa_venda.replace(",", ".")),
                    })
                except ValueError:
                    continue
        return {"data": primeira_data, "titulos": titulos} if titulos else None
    except requests.RequestException:
        return None


def titulo_ipca_mais_proximo(dados_tesouro: dict | None, meses: int) -> dict | None:
    """Entre os Tesouro IPCA+ do dia, escolhe o vencimento mais próximo do prazo pedido."""
    if not dados_tesouro:
        return None
    candidatos = [t for t in dados_tesouro["titulos"] if t["tipo"] == "Tesouro IPCA+"]
    if not candidatos:
        return None
    hoje, anos_alvo = datetime.now(), meses / 12

    def diferenca(titulo):
        vencimento = datetime.strptime(titulo["vencimento"], "%d/%m/%Y")
        return abs((vencimento - hoje).days / 365 - anos_alvo)

    return min(candidatos, key=diferenca)
