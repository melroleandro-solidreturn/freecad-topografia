# SPDX-License-Identifier: LGPL-2.1-or-later
"""Topografia — base de dados topográficos para projectos de estradas (FreeCAD).

Fase 1 do plano: importação CSV semântica (ponto, código, X, Y, cota),
TIN com breaklines e curvas de nível paramétricas, em coordenadas locais
com georreferência em metadados. Objectos de aplicação (sem GUI).

Convenção de unidades e coordenadas:
- ``Model``/relatórios guardam coordenadas ABSOLUTAS (E, N, cota) em metros;
- a geometria (Points/Mesh/Shape) é LOCAL: absoluto - ``Geolocalizacao.Base``;
- isto mitiga a precisão float do kernel Mesh com coordenadas UTM grandes.
"""

__version__ = "0.1.0"
