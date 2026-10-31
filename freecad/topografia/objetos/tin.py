# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objecto TIN: superfície de terreno triangulada com breaklines.

Entradas: um ou mais Levantamentos + lista de códigos cujos pontos
(ordenados por número de ponto) formam polilinhas de breakline — o fluxo
clássico de levantamento codificado em sequência.

Saídas: ``obj.Mesh`` (malha LOCAL em metros), ``obj.ModeloTIN`` (dict com
vértices/triângulos absolutos, consumível por outros módulos, p.ex. o
CorridorRoad via TINSurface) e ``obj.Estatisticas``.
"""
from __future__ import annotations

import time

import FreeCAD
import Mesh

from ..triangulacao import triangula
from .levantamento import polilinha_de_codigo


class TIN:
    """Proxy do objecto Mesh::FeaturePython com breaklines."""

    def __init__(self, obj):
        self.Type = "Topografia::TIN"

        obj.addProperty(
            "App::PropertyLinkList", "Levantamentos", "Terreno",
            "Levantamentos de origem").Levantamentos = []

        obj.addProperty(
            "App::PropertyStringList", "CodigosBreakline", "Terreno",
            "Códigos cujos pontos formam polilinhas de breakline"
        ).CodigosBreakline = []

        obj.addProperty(
            "App::PropertyFloat", "Densificacao", "Terreno",
            "Passo de densificação das breaklines em m (0 = automático)"
        ).Densificacao = 0.0

        obj.addProperty(
            "App::PropertyFloat", "ArestaMaxima", "Terreno",
            "Descarta triângulos com aresta 2D maior que este valor em m (0 = não filtra)"
        ).ArestaMaxima = 0.0

        obj.addProperty(
            "App::PropertyPlacement", "Geolocalizacao", "Georreferência",
            "Origem absoluta (E, N, cota) do sistema local"
        ).Geolocalizacao = FreeCAD.Placement()

        obj.addProperty(
            "App::PropertyString", "Estatisticas", "Terreno",
            "Estatísticas da última triangulação").Estatisticas = ""

        obj.addProperty(
            "App::PropertyPythonObject", "ModeloTIN", "Terreno",
            "Modelo persistível: vertices/triangulos absolutos + origem"
        ).ModeloTIN = {}

        obj.Proxy = self

    def execute(self, obj):
        t0 = time.time()
        levantamentos = [l for l in obj.Levantamentos if l.Model]
        if not levantamentos:
            obj.Mesh = Mesh.Mesh()
            obj.ModeloTIN = {}
            obj.Estatisticas = "sem levantamentos"
            return

        origem = levantamentos[0].Geolocalizacao.Base
        obj.Geolocalizacao.Base = origem

        pontos = []
        for lev in levantamentos:
            pontos.extend((p["E"], p["N"], p["Z"]) for p in lev.Model.values())

        breaklines = []
        for lev in levantamentos:
            for codigo in obj.CodigosBreakline:
                polilinha = polilinha_de_codigo(lev, codigo)
                if len(polilinha) >= 2:
                    breaklines.append(polilinha)

        resultado = triangula(
            pontos,
            breaklines=breaklines,
            densificacao=obj.Densificacao or None,
            aresta_maxima=obj.ArestaMaxima,
        )

        vertices = resultado["vertices"]
        triangulos = resultado["triangulos"]
        locais = [
            (v[0] - origem.x, v[1] - origem.y, v[2] - origem.z) for v in vertices
        ]
        obj.Mesh = construir_malha(locais, triangulos)
        obj.ModeloTIN = {
            "origem": (origem.x, origem.y, origem.z),
            "vertices": [tuple(float(c) for c in v) for v in vertices],
            "triangulos": [tuple(int(i) for i in t) for t in triangulos],
            "arestas_impostas": [tuple(e) for e in resultado["arestas_impostas"]],
        }
        est = resultado["estatisticas"]
        obj.Estatisticas = (
            f"pontos={est['vertices']} triangulos={est['triangulos']} "
            f"breaklines={est['breaklines']} arestas_impostas={est['arestas_impostas']} "
            f"falhas={est['arestas_falhadas']} densificacao={est['densificacao']:.3f}m "
            f"triangulacao={est['segundos']:.2f}s total={time.time() - t0:.2f}s"
        )


def construir_malha(vertices, triangulos):
    """Constrói Mesh::Mesh a partir de vértices e triângulos (índices)."""
    facetas = []
    for a, b, c in triangulos:
        facetas.append((vertices[a], vertices[b], vertices[c]))
    malha = Mesh.Mesh()
    for fa, fb, fc in facetas:
        malha.addFacet(
            FreeCAD.Vector(*fa), FreeCAD.Vector(*fb), FreeCAD.Vector(*fc)
        )
    return malha
