# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes das chaves de descrição (equivalente Description Keys)."""
from __future__ import annotations

from freecad.topografia.chaves import CHAVES_PREDEFINIDAS, agrupa_por_codigo, classifica


def test_prefixo_casa_com_variacoes():
    assert classifica("EP")["grupo"] == "Pavimento"
    assert classifica("EP2")["grupo"] == "Pavimento"
    assert classifica("ep3")["grupo"] == "Pavimento"  # maiúsculas irrelevantes
    assert classifica("TAL-INFERIOR")["grupo"] == "Talude"
    assert classifica("TAL-INFERIOR")["breakline"] is True


def test_codigo_desconhecido_devolve_regra_neutra():
    r = classifica("XYZ")
    assert r["breakline"] is False
    assert r["grupo"] == "XYZ"


def test_sem_codigo():
    r = classifica("")
    assert r["grupo"] == "Sem código"


def test_primeira_regra_que_casa_ganha():
    chaves = {"A*": {"grupo": "Primeiro", "cor": (0, 0, 0), "breakline": False},
              "AB*": {"grupo": "Segundo", "cor": (1, 1, 1), "breakline": True}}
    assert classifica("AB1", chaves)["grupo"] == "Primeiro"


def test_agrupamento_por_codigo():
    from freecad.topografia.csv_io import PontoTopografico

    pontos = [
        PontoTopografico("1", "EIX", 0, 0, 0),
        PontoTopografico("2", "EP", 1, 0, 0),
        PontoTopografico("3", "EIX", 2, 0, 0),
    ]
    grupos = agrupa_por_codigo(pontos)
    assert grupos["EIX"] == [0, 2]
    assert grupos["EP"] == [1]


def test_chaves_predefinidas_cobrem_codigos_do_piloto():
    for codigo in ("EIX", "EP", "LE", "TAL", "MURO", "ARV", "CER", "GRE"):
        assert classifica(codigo)["padrao"] != "*"
