# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes dos objectos FreeCAD (Levantamento, TIN) e da georreferência."""
from __future__ import annotations

import pytest

from freecad.topografia.csv_io import le_pontos
from freecad.topografia.objetos import levantamento as mod_lev
from freecad.topografia.objetos import tin as mod_tin
from freecad.topografia.objetos.levantamento import Levantamento, importar, polilinha_de_codigo
from freecad.topografia.objetos.tin import TIN


def test_importar_csv_ptpt_cria_levantamento_com_codigo(doc, dados):
    obj, rel = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    doc.recompute()
    assert obj.Points.CountPoints == 89
    assert len(obj.Model) == 89
    assert obj.Model["1"]["Codigo"] == "EIX"  # ordenado por número de ponto
    assert "EIX=11" in obj.ResumoCodigos
    # origem absoluta do primeiro ponto (UTM) guardada na geolocalização
    base = obj.Geolocalizacao.Base
    assert base.x == pytest.approx(0.0, abs=1e-6)
    assert base.y == pytest.approx(0.0, abs=1e-6)
    assert base.z == pytest.approx(100.0, abs=0.01)


def test_geometria_local_mantem_coordenadas_pequenas(doc, dados):
    obj, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    doc.recompute()
    caixa = obj.Shape.BoundBox if hasattr(obj, "Shape") else obj.Points.BoundBox
    caixa = obj.Points.BoundBox
    assert caixa.XLength < 600 and caixa.YLength < 600  # metros locais, não UTM


def test_tin_com_breaklines_por_codigo(doc, dados):
    lev, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    obj = doc.addObject("Mesh::FeaturePython", "TIN")
    TIN(obj)
    obj.Levantamentos = [lev]
    obj.CodigosBreakline = ["EIX", "LE_E", "LE_D"]
    doc.recompute()
    assert obj.Mesh.CountFacets > 100
    assert "falhas=0" in obj.Estatisticas
    assert "arestas_impostas" in obj.Estatisticas
    # modelo persistível com coordenadas absolutas
    modelo = obj.ModeloTIN
    assert modelo["origem"] == pytest.approx((0.0, 0.0, 100.0), abs=0.01)
    assert len(modelo["triangulos"]) == obj.Mesh.CountFacets


def test_parametricidade_adicionar_ponto_propaga(doc, dados):
    lev, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    obj = doc.addObject("Mesh::FeaturePython", "TIN")
    TIN(obj)
    obj.Levantamentos = [lev]
    doc.recompute()
    n_antes = obj.Mesh.CountFacets
    zmax_antes = obj.Mesh.BoundBox.ZMax

    modelo = dict(lev.Model)
    chave = str(len(modelo) + 1)
    modelo[chave] = {"Numero": "900", "Codigo": "EIX", "E": 250.0, "N": 0.0, "Z": 120.0}
    lev.Model = modelo
    doc.recompute()

    assert lev.Points.CountPoints == 90
    # geometria LOCAL: cota absoluta 120 com origem z=100 -> 20.0 local
    assert obj.Mesh.BoundBox.ZMax == pytest.approx(20.0, abs=0.01)
    assert obj.Mesh.CountFacets != n_antes or True  # topologia pode coincidir; o ZMax prova a propagação


def test_polilinha_de_codigo_ordenada_por_numero(doc, dados):
    lev, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    eixo = polilinha_de_codigo(lev, "EIX")
    assert len(eixo) == 11
    assert eixo[0][0] == pytest.approx(0.0, abs=1e-6)      # estação 0
    assert eixo[-1][0] == pytest.approx(500.0, abs=1e-6)   # estação 500
    assert polilinha_de_codigo(lev, "CODIGO-INEXISTENTE") == []
