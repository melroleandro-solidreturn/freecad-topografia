# SPDX-License-Identifier: LGPL-2.1-or-later
"""Handoff: TIN da Topografia consumida pelo CorridorRoad (Fase 2 à vista).

Prova que a superfície construída pelo nosso módulo pode alimentar os
serviços do CorridorRoad sem passar por ficheiro intermédio.
"""
from __future__ import annotations

import numpy as np
import pytest

pkg_prw = pytest.importorskip(
    "freecad.Corridor_Road.v1.services.evaluation.tin_sampling_service",
    reason="CorridorRoad não disponível",
)

from freecad.Corridor_Road.v1.models.result.tin_surface import (
    TINSurface,
    TINTriangle,
    TINVertex,
)
from freecad.Corridor_Road.v1.services.evaluation.tin_sampling_service import (
    TinSamplingService,
)
from freecad.topografia.triangulacao import triangula


def _plano_inclinado():
    xs = np.linspace(-50, 50, 11)
    ys = np.linspace(-50, 50, 11)
    return [(x, y, 0.1 * y) for x in xs for y in ys]


def _para_tin_surface(res, projecto="teste", surface_id="eg-topografia"):
    vertices = [
        TINVertex(vertex_id=f"v{i}", x=float(v[0]), y=float(v[1]), z=float(v[2]))
        for i, v in enumerate(res["vertices"])
    ]
    triangulos = [
        TINTriangle(triangle_id=f"t{i}", v1=f"v{a}", v2=f"v{b}", v3=f"v{c}")
        for i, (a, b, c) in enumerate(res["triangulos"])
    ]
    return TINSurface(
        schema_version=1,
        project_id=projecto,
        surface_id=surface_id,
        surface_kind="existing_ground_tin",
        label="Terreno existente (Topografia)",
        vertex_rows=vertices,
        triangle_rows=triangulos,
    )


def test_tin_do_modulo_e_amostravel_pelo_corridorroad():
    res = triangula(_plano_inclinado())
    superficie = _para_tin_surface(res)
    servico = TinSamplingService()
    amostra = servico.sample_xy(surface=superficie, x=7.0, y=23.0)
    assert amostra.found
    assert amostra.status == "ok"
    assert amostra.z == pytest.approx(2.3, abs=1e-6)  # z = 0.1 * y


def test_amostra_fora_do_dominio_nao_e_encontrada():
    res = triangula(_plano_inclinado())
    superficie = _para_tin_surface(res)
    amostra = TinSamplingService().sample_xy(surface=superficie, x=500.0, y=500.0)
    assert not amostra.found
