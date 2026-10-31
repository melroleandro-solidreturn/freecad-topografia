# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objecto Levantamento: pontos topográficos com código, em coordenadas locais.

O ``Model`` guarda os pontos ABSOLUTOS (E, N, cota) com número e código;
``obj.Points`` é a geometria LOCAL (absoluto - ``Geolocalizacao.Base``).
A origem é definida no momento da importação (primeiro ponto), o que impede
coordenadas UTM grandes dentro da malha (kernel Mesh em float).
"""
from __future__ import annotations

import FreeCAD
import Points

from ..csv_io import RelatorioImportacao, le_pontos


class Levantamento:
    """Proxy do objecto Points::FeaturePython com semântica de levantamento."""

    def __init__(self, obj):
        self.Type = "Topografia::Levantamento"

        obj.addProperty(
            "App::PropertyString", "Ficheiro", "Importação",
            "Ficheiro CSV de origem").Ficheiro = ""

        obj.addProperty(
            "App::PropertyPythonObject", "Model", "Pontos",
            "Pontos absolutos {chave: {Numero, Codigo, E, N, Z}}").Model = {}

        obj.addProperty(
            "App::PropertyPythonObject", "Rejeitadas", "Importação",
            "Linhas rejeitadas (nº linha, motivo)").Rejeitadas = []

        obj.addProperty(
            "App::PropertyString", "ResumoCodigos", "Importação",
            "Contagem de pontos por código").ResumoCodigos = ""

        obj.addProperty(
            "App::PropertyPlacement", "Geolocalizacao", "Georreferência",
            "Origem absoluta (E, N, cota) do sistema local"
        ).Geolocalizacao = FreeCAD.Placement()

        obj.Proxy = self

    def onChanged(self, obj, prop):
        if prop == "Model":
            self._reconstruir_pontos(obj)

    def execute(self, obj):
        self._reconstruir_pontos(obj)

    def _reconstruir_pontos(self, obj):
        origem = obj.Geolocalizacao.Base
        locais = []
        for p in obj.Model.values():
            locais.append(
                FreeCAD.Vector(p["E"] - origem.x, p["N"] - origem.y, p["Z"] - origem.z)
            )
        if locais:
            obj.Points = Points.Points(locais)


def _chave_ordenacao(numero: str):
    return (0, int(numero)) if numero.isdigit() else (1, numero)


def definir_relatorio(obj, relatorio: RelatorioImportacao) -> None:
    """Carrega um RelatorioImportacao no objecto, fixando a origem local."""
    if not relatorio.pontos:
        raise ValueError("relatório de importação sem pontos")
    primeiro = relatorio.pontos[0]
    obj.Ficheiro = relatorio.ficheiro
    obj.Geolocalizacao.Base = FreeCAD.Vector(primeiro.x, primeiro.y, primeiro.z)
    model = {}
    for i, p in enumerate(pontos_ordenados(relatorio.pontos), start=1):
        model[str(i)] = {
            "Numero": p.numero,
            "Codigo": p.codigo,
            "E": p.x,
            "N": p.y,
            "Z": p.z,
        }
    obj.Rejeitadas = list(relatorio.rejeitadas)
    contagens = relatorio.codigos
    obj.ResumoCodigos = "; ".join(f"{c}={n}" for c, n in sorted(contagens.items()))
    obj.Model = model


def pontos_ordenados(pontos):
    """Ordena os pontos por número de ponto (numérico quando possível)."""
    return sorted(pontos, key=lambda p: _chave_ordenacao(p.numero))


def importar(caminho: str, doc=None, nome: str = "Levantamento", **kwargs):
    """Importa um CSV e cria o objecto Levantamento no documento activo."""
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument("Topografia")
    obj = doc.addObject("Points::FeaturePython", nome)
    Levantamento(obj)
    relatorio = le_pontos(caminho, **kwargs)
    definir_relatorio(obj, relatorio)
    doc.recompute()
    return obj, relatorio


def polilinha_de_codigo(obj, codigo: str):
    """Devolve a polilinha absoluta (lista de E,N,Z) dos pontos de um código,
    ordenada por número de ponto — a base das breaklines automáticas."""
    pontos = [p for p in obj.Model.values() if p["Codigo"].upper() == codigo.upper()]
    pontos.sort(key=lambda p: _chave_ordenacao(p["Numero"]))
    return [(p["E"], p["N"], p["Z"]) for p in pontos]
