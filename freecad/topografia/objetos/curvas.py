# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objecto CurvasDeNivel: curvas de nível paramétricas sobre uma TIN.

Recomputa a partir da malha da TIN sempre que o intervalo muda — o
equivalente funcional das curvas dinâmicas do Civil 3D (propriedade da
superfície, não objecto solto).
"""
from __future__ import annotations

import math

import FreeCAD
import Part


class CurvasDeNivel:
    """Proxy do objecto Part::FeaturePython com curvas major/minor."""

    def __init__(self, obj):
        self.Type = "Topografia::CurvasDeNivel"

        obj.addProperty(
            "App::PropertyLink", "TIN", "Curvas",
            "Superfície TIN de origem").TIN = None

        obj.addProperty(
            "App::PropertyFloat", "Intervalo", "Curvas",
            "Intervalo entre curvas de nível em m").Intervalo = 1.0

        obj.addProperty(
            "App::PropertyFloat", "IntervaloMaior", "Curvas",
            "Intervalo das curvas principais em m").IntervaloMaior = 5.0

        obj.addProperty(
            "App::PropertyString", "Resumo", "Curvas",
            "Resumo da última geração").Resumo = ""

        obj.Proxy = self

    def execute(self, obj):
        tin = obj.TIN
        if tin is None or not hasattr(tin, "Mesh") or tin.Mesh.CountFacets == 0:
            obj.Shape = Part.Shape()
            obj.Resumo = "sem TIN"
            return

        intervalo = max(float(obj.Intervalo), 1e-6)
        maior = max(float(obj.IntervaloMaior), intervalo)
        malha = tin.Mesh
        zmin, zmax = malha.BoundBox.ZMin, malha.BoundBox.ZMax

        menores, maiores, niveis = [], [], 0
        nivel = math.floor(zmin / intervalo + 1e-9) * intervalo
        while nivel <= zmax + intervalo * 1e-6:
            cortes = malha.crossSections([((0, 0, nivel), (0, 0, 1))], 1e-7)
            for lista_pontos in (cortes[0] if cortes else []):
                if len(lista_pontos) > 3:
                    fio = Part.makePolygon(lista_pontos)
                    # curva principal quando o nível é múltiplo do intervalo maior
                    if abs(round(nivel / maior) * maior - nivel) < intervalo * 1e-6:
                        maiores.append(fio)
                    else:
                        menores.append(fio)
            nivel += intervalo
            niveis += 1

        obj.Shape = Part.makeCompound(
            [Part.makeCompound(maiores), Part.makeCompound(menores)]
        )
        obj.Resumo = (
            f"níveis={niveis} wires={len(maiores) + len(menores)} "
            f"(principais={len(maiores)}, intercalares={len(menores)})"
        )
