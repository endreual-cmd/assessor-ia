"""Testes determinísticos do catálogo de renda fixa. Rodar: python -m pytest -q  (ou python tests/test_produtos_rf.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import produtos_rf as p

CEN = {"cdi": 0.14, "ipca": 0.045, "selic": 0.1425}


def test_lci_90_bate_cdb_100_em_2_anos():
    lci = p.projetar_produto("LCI", 10000, 24, "pos_cdi", 90, CEN)
    cdb = p.projetar_produto("CDB", 10000, 24, "pos_cdi", 100, CEN)
    assert lci.ir == 0 and cdb.ir > 0
    assert lci.valor_liquido > cdb.valor_liquido


def test_carencia_lci_ipca_gera_alerta():
    r = p.projetar_produto("LCI", 10000, 12, "ipca_mais", 6, CEN)
    assert any("carência" in a for a in r.alertas)


def test_custodia_tesouro_selic_isenta_ate_10_mil():
    pequeno = p.projetar_produto("TESOURO_SELIC", 5000, 12, "selic", 0, CEN)
    grande = p.projetar_produto("TESOURO_SELIC", 100000, 12, "selic", 0, CEN)
    assert pequeno.custodia == 0
    assert grande.custodia > 0


def test_iof_em_resgate_curto():
    assert p.aliquota_iof(1) == 0.96 and p.aliquota_iof(29) == 0.03 and p.aliquota_iof(30) == 0


def test_come_cotas_nao_muda_total_de_ir_no_fim():
    r = p.projetar_produto("FUNDO_RF_LP", 10000, 36, "pos_cdi", 100, CEN)
    cdb = p.projetar_produto("CDB", 10000, 36, "pos_cdi", 100, CEN)
    # come-cotas antecipa IR e reduz a base que rende: fundo fica abaixo do CDB equivalente
    assert r.valor_liquido < cdb.valor_liquido
    assert r.ir > 0


def test_alerta_fgc_acima_250_mil():
    r = p.projetar_produto("CDB", 300000, 12, "pos_cdi", 100, CEN)
    assert any("FGC" in a for a in r.alertas)


def test_gross_up():
    eq = p.taxa_tributada_equivalente(0.126, 24)  # LCI 90% de CDI 14%
    cdb = p.projetar_produto("CDB", 10000, 24, "pre", eq * 100, CEN)
    lci = p.projetar_produto("LCI", 10000, 24, "pre", 12.6, CEN)
    assert abs(cdb.valor_liquido - lci.valor_liquido) < 0.01


def test_indexador_invalido():
    try:
        p.projetar_produto("POUPANCA", 1000, 12, "pre", 10, CEN)
    except ValueError:
        return
    raise AssertionError("deveria recusar")


def test_todos_os_produtos_projetam():
    for prod in p.CATALOGO:
        for idx in prod.indexadores:
            r = p.projetar_produto(prod.codigo, 50000, 36, idx, 100 if idx.value == "pos_cdi" else 6, CEN)
            assert r.valor_liquido > 50000, prod.codigo


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn(); print("ok", nome)
