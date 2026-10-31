# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes do importador CSV semântico (Fase 0/1)."""
from __future__ import annotations

from pathlib import Path

from freecad.topografia.csv_io import le_pontos


def _escreve(tmp_path, nome, linhas, encoding="utf-8"):
    f = tmp_path / nome
    f.write_text("\n".join(linhas) + "\n", encoding=encoding)
    return str(f)


def test_csv_ptpt_delimitador_ponto_e_virgula_decimal_virgula(tmp_path):
    f = _escreve(tmp_path, "pt.csv", [
        "ponto;codigo;X;Y;cota",
        "1;EIX;353000,5;4168000,25;83,402",
        "2;EP;353010,0;4168010,0;84,1",
    ])
    rel = le_pontos(f)
    assert rel.delimitador == ";"
    assert rel.decimal == ","
    assert len(rel.pontos) == 2 and not rel.rejeitadas
    assert rel.pontos[0].codigo == "EIX"
    assert abs(rel.pontos[0].x - 353000.5) < 1e-9
    assert abs(rel.pontos[0].z - 83.402) < 1e-9


def test_csv_en_cabecalho_ingles(tmp_path):
    f = _escreve(tmp_path, "en.csv", [
        "point,code,Easting,Northing,Elevation",
        "1,EIX,10.5,20.25,30.125",
    ])
    rel = le_pontos(f)
    assert rel.delimitador == "," and rel.decimal == "."
    assert rel.pontos[0].numero == "1"
    assert rel.pontos[0].y == 20.25


def test_csv_sem_cabecalho_cinco_colunas(tmp_path):
    f = _escreve(tmp_path, "nc.csv", [
        "1;EIX;0;0;100",
        "2;EP;5;5;101",
    ])
    rel = le_pontos(f)
    assert rel.mapeamento["codigo"] == 1
    assert len(rel.pontos) == 2
    assert rel.pontos[1].codigo == "EP"


def test_linhas_invalidas_sao_rejeitadas_com_numero_e_motivo(tmp_path):
    f = _escreve(tmp_path, "mau.csv", [
        "ponto;codigo;X;Y;cota",
        "1;EIX;0;0;100",
        "linha sem numeross suficiente",
        "3;EP;abc;0;100",
    ])
    rel = le_pontos(f)
    assert len(rel.pontos) == 1
    assert len(rel.rejeitadas) == 2
    assert rel.rejeitadas[0][0] == 3  # nº da linha no ficheiro
    assert "colunas" in rel.rejeitadas[0][1]
    assert rel.rejeitadas[1][0] == 4
    assert "não numérico" in rel.rejeitadas[1][1]


def test_ficheiro_real_ptpt_do_piloto(dados):
    rel = le_pontos(str(dados / "levantamento_ptpt.csv"))
    assert len(rel.pontos) == 89
    assert not rel.rejeitadas
    codigos = rel.codigos
    assert codigos["EIX"] == 11 and codigos["EP"] == 22 and codigos["TAL"] == 22


def test_bom_e_latin1(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_bytes(
        "ponto;codigo;X;Y;cota\n1;EIX;1,5;2,5;3,5\n".replace(";", ";").encode("utf-8-sig")
    )
    rel = le_pontos(str(f))
    assert len(rel.pontos) == 1

    g = tmp_path / "lat.csv"
    g.write_text(
        "ponto;codigo;X;Y;cota\n1;MURÓ;1,5;2,5;3,5\n", encoding="latin-1"
    )
    rel2 = le_pontos(str(g))
    assert rel2.pontos[0].codigo == "MURÓ" or rel2.pontos[0].codigo == "MURO"


def test_tab_com_decimal_ponto(tmp_path):
    f = _escreve(tmp_path, "tab.csv", [
        "ponto\tcodigo\tX\tY\tZ",
        "1\tEIX\t10.5\t20.5\t30.5",
    ])
    rel = le_pontos(f)
    assert rel.delimitador == "\t"
    assert rel.pontos[0].x == 10.5


def test_mapeamento_forcado_por_indices(tmp_path):
    f = _escreve(tmp_path, "ordem.csv", [
        "1;0;10,0;20,0;30,0",
    ])
    rel = le_pontos(f, mapeamento={"x": 2, "y": 3, "z": 4})
    assert rel.pontos[0].x == 10.0
    assert rel.pontos[0].z == 30.0
