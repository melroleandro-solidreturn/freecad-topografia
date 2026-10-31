# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes das curvas de nível paramétricas."""
from __future__ import annotations

import FreeCAD

from freecad.topografia.objetos.curvas import CurvasDeNivel
from freecad.topografia.objetos.levantamento import importar
from freecad.topografia.objetos.tin import TIN


def _cenario(doc, dados):
    lev, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    tin = doc.addObject("Mesh::FeaturePython", "TIN")
    TIN(tin)
    tin.Levantamentos = [lev]
    curvas = doc.addObject("Part::FeaturePython", "Curvas")
    CurvasDeNivel(curvas)
    curvas.TIN = tin
    return tin, curvas


def test_curvas_geram_wires_por_nivel(doc, dados):
    tin, curvas = _cenario(doc, dados)
    curvas.Intervalo = 1.0
    curvas.IntervaloMaior = 5.0
    doc.recompute()
    assert not curvas.Shape.isNull()
    assert "níveis=" in curvas.Resumo
    assert int(curvas.Resumo.split("wires=")[1].split("(")[0]) >= 1


def test_mudar_intervalo_regenera_as_curvas(doc, dados):
    tin, curvas = _cenario(doc, dados)
    curvas.Intervalo = 5.0
    curvas.IntervaloMaior = 5.0
    doc.recompute()
    wires_grossas = len(curvas.Shape.Wires)
    resumo_grosso = curvas.Resumo

    curvas.Intervalo = 1.0
    doc.recompute()
    assert curvas.Resumo != resumo_grosso
    assert len(curvas.Shape.Wires) >= wires_grossas


def test_curvas_dentro_da_amplitude_da_tin(doc, dados):
    tin, curvas = _cenario(doc, dados)
    curvas.Intervalo = 1.0
    doc.recompute()
    zb = curvas.Shape.BoundBox
    zt = tin.Mesh.BoundBox
    assert zb.ZMin >= zt.ZMin - 1e-6
    assert zb.ZMax <= zt.ZMax + 1e-6


def test_sem_tin_shape_vazia(doc):
    curvas = doc.addObject("Part::FeaturePython", "Curvas")
    CurvasDeNivel(curvas)
    doc.recompute()
    assert curvas.Shape.isNull()
    assert curvas.Resumo == "sem TIN"
