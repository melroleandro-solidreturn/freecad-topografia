# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes do motor de movimento de terras (Fase 3)."""
from __future__ import annotations

import math

import pytest

from freecad.topografia.triangulacao import triangula
from freecad.topografia.terraplenagem import (
    SECCAO_PREDEFINIDA,
    mass_haul,
    seccao_terraplenagem,
    volumes_areas_medias,
)


def _tin_plana(z=0.0, x_min=-30.0, x_max=130.0, y_meio=15.0, passo=6.0):
    """TIN de terreno plano (caso analítico), cobrindo o corredor de testes."""
    xs = []
    v = x_min
    while v <= x_max + 1e-9:
        xs.append(v)
        v += passo
    ys = []
    v = -y_meio
    while v <= y_meio + 1e-9:
        ys.append(v)
        v += passo
    pontos = [(x, y, z) for x in xs for y in ys]
    return triangula(pontos)


PARAMS_ANALITICO = {
    "faixa": 3.5, "ombro": 1.5,
    "caimento_faixa": 0.0, "caimento_ombro": 0.0,
    "espessura_estrutura": 0.0,
    "talude_corte": 2.0, "talude_aterro": 3.0,
    "passo": 0.25, "largura_maxima": 40.0,
}


def test_caso_analitico_plano_areas_exactas():
    """Terreno z=0, plataforma a 2,0 m: aterro = plataforma + 2 taludes 1V:3H."""
    tin = _tin_plana()
    res = seccao_terraplenagem(tin, 0.0, 0.0, 0.0, 2.0, PARAMS_ANALITICO)
    # borda = 5,0; encontro a 5 + 2*3 = 11,0 m; áreas: 10*2 + 2*(2*6/2) = 32 m²
    assert res["dia_esquerdo"] == pytest.approx(-11.0, abs=0.02)
    assert res["dia_direito"] == pytest.approx(11.0, abs=0.02)
    assert res["a_aterro"] == pytest.approx(32.0, rel=0.005)
    assert res["a_corte"] == pytest.approx(0.0, abs=1e-6)


def test_caso_analitico_volume_erro_menor_que_0_5_porcento():
    tin = _tin_plana()
    estacoes = [float(s) for s in range(0, 101, 20)]
    areas = [seccao_terraplenagem(tin, s, 0.0, 0.0, 2.0, PARAMS_ANALITICO) for s in estacoes]
    vols = volumes_areas_medias(
        estacoes,
        [a["a_corte"] for a in areas],
        [a["a_aterro"] for a in areas],
        [a["a_pavimento"] for a in areas],
    )
    analitico = 32.0 * 100.0
    assert vols["volume_aterro"] == pytest.approx(analitico, rel=0.005)
    assert vols["volume_corte"] == pytest.approx(0.0, abs=1e-6)
    assert vols["volume_aterro"] == pytest.approx(
        sum(l["volume_aterro"] for l in vols["linhas"]), rel=1e-9)


def test_corte_e_aterro_coexistem_num_vale():
    """Plataforma ao nível do terreno num vale lateral: um lado corta, outro aterra."""
    xs = [x for x in range(-30, 31, 5)]
    pontos = [(float(x), float(y), 0.05 * y) for x in xs for y in xs]  # plano inclinado
    tin = triangula(pontos)
    res = seccao_terraplenagem(tin, 0.0, 0.0, 0.0, 0.0, PARAMS_ANALITICO)
    assert res["a_corte"] > 0.0 and res["a_aterro"] > 0.0
    # assimetria: lado y>0 (terreno mais alto) corta mais
    assert res["dia_direito"] < abs(res["dia_esquerdo"]) or res["dia_direito"] < 11.0


def test_validacao_cruzada_com_corridorroad():
    """As nossas áreas alimentam o SectionEarthworkVolumeService do PRW."""
    pytest.importorskip(
        "freecad.Corridor_Road.v1.services.evaluation.section_earthwork_volume_service")
    from freecad.Corridor_Road.v1.models.result.quantity_model import QuantityFragment
    from freecad.Corridor_Road.v1.services.evaluation.section_earthwork_volume_service import (
        SectionEarthworkVolumeService,
    )

    estacoes = [0.0, 20.0, 40.0, 60.0]
    corte = [10.0, 20.0, 30.0, 10.0]
    aterro = [0.0, 5.0, 10.0, 5.0]
    fragmentos = []
    for i, s in enumerate(estacoes):
        fragmentos.append(QuantityFragment(
            fragment_id=f"c{i}", quantity_kind="cut_area", measurement_kind="section_area",
            value=corte[i], unit="m2", station_start=s))
        fragmentos.append(QuantityFragment(
            fragment_id=f"f{i}", quantity_kind="fill_area", measurement_kind="section_area",
            value=aterro[i], unit="m2", station_start=s))
    resultado = SectionEarthworkVolumeService().build(
        fragmentos, station_values=estacoes, fragment_id_prefix="tp")
    nosso = volumes_areas_medias(estacoes, corte, aterro)
    por_tipo = {}
    for row in resultado.rows:
        por_tipo[row.quantity_kind] = por_tipo.get(row.quantity_kind, 0.0) + row.value
    assert por_tipo["cut"] == pytest.approx(nosso["volume_corte"], rel=1e-9)
    assert por_tipo["fill"] == pytest.approx(nosso["volume_aterro"], rel=1e-9)


def test_validacao_cruzada_com_mesh_volume_do_nucleo():
    """Sólido fechado (design vs EG plana) via Mesh.Volume ≈ soma das fatias (<2%)."""
    import FreeCAD
    import Mesh

    tin = _tin_plana()
    estacoes = [float(s) for s in range(0, 101, 20)]
    areas = [seccao_terraplenagem(tin, s, 0.0, 0.0, 2.0, PARAMS_ANALITICO) for s in estacoes]
    vols = volumes_areas_medias(estacoes, [a["a_corte"] for a in areas], [a["a_aterro"] for a in areas])

    # malha fechada: topo = projecto (plataforma + taludes), base = z=0, paredes nas pontas
    def anel(s):
        res = seccao_terraplenagem(tin, s, 0.0, 0.0, 2.0, PARAMS_ANALITICO)
        borda, dia = 5.0, res["dia_direito"]
        pts = [(-dia, 0.0), (-borda, 2.0), (0.0, 2.0), (borda, 2.0), (dia, 0.0)]
        return [(s, o, z) for o, z in pts], [(s, o, 0.0) for o, z in pts]

    topo_anéis, base_anéis = zip(*(anel(s) for s in estacoes))
    facetas = []

    # superfície superior entre anéis consecutivos
    for r1, r2 in zip(topo_anéis[:-1], topo_anéis[1:]):
        for i in range(len(r1) - 1):
            facetas.append((r1[i], r1[i + 1], r2[i + 1]))
            facetas.append((r1[i], r2[i + 1], r2[i]))
    # base (orientação oposta)
    for r1, r2 in zip(base_anéis[:-1], base_anéis[1:]):
        for i in range(len(r1) - 1):
            facetas.append((r1[i], r2[i + 1], r1[i + 1]))
            facetas.append((r1[i], r2[i], r2[i + 1]))
    # tampas nas extremidades
    for anel, sinal in ((topo_anéis[0], 1), (topo_anéis[-1], -1)):
        base = base_anéis[0] if sinal == 1 else base_anéis[-1]
        for i in range(len(anel) - 1):
            facetas.append((anel[i], anel[i + 1], base[i]))
            facetas.append((anel[i + 1], base[i + 1], base[i]))

    malha = Mesh.Mesh()
    for fa, fb, fc in facetas:
        malha.addFacet(
            FreeCAD.Vector(*fa), FreeCAD.Vector(*fb), FreeCAD.Vector(*fc))
    volume_malha = malha.Volume
    erro = abs(volume_malha - vols["volume_aterro"]) / vols["volume_aterro"]
    assert erro < 0.02, f"Mesh.Volume={volume_malha:.1f} fatias={vols['volume_aterro']:.1f} erro={erro:.3%}"


def test_mass_haul_ponto_de_balanceamento():
    estacoes = [0.0, 20.0, 40.0, 60.0, 80.0]
    corte = [10.0, 10.0, 10.0, 0.0, 0.0]
    aterro = [0.0, 0.0, 10.0, 10.0, 10.0]
    mh = mass_haul(estacoes, corte, aterro)
    # sobe 200, desce 200: termina equilibrado
    assert mh["curva"][-1]["cumulativo"] == pytest.approx(0.0, abs=1e-9)
    assert any(abs(p - 80.0) < 1e-6 for p in mh["pontos_balanceamento"])
