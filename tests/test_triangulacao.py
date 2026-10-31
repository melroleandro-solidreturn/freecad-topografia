# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes da triangulação com breaklines (exactidão e topologia)."""
from __future__ import annotations

import numpy as np
import pytest

from freecad.topografia.triangulacao import MalhaDelaunay, _cruzam, triangula


def _plano_inclinado(n=21, lado=100.0):
    xs = np.linspace(-lado / 2, lado / 2, n)
    ys = np.linspace(-lado / 2, lado / 2, n)
    return [(x, y, 0.1 * y) for x in xs for y in ys]


def _piramide(n=21, lado=100.0, altura=10.0):
    meio = lado / 2
    xs = np.linspace(-meio, meio, n)
    ys = np.linspace(-meio, meio, n)
    return [(x, y, altura * (1 - max(abs(x), abs(y)) / meio)) for x in xs for y in ys]


def _breaklines_piramide(lado=100.0, altura=10.0):
    m = lado / 2
    return [
        [(-m, -m, 0.0), (0.0, 0.0, altura)],
        [(0.0, 0.0, altura), (m, -m, 0.0)],
        [(-m, m, 0.0), (0.0, 0.0, altura)],
        [(0.0, 0.0, altura), (m, m, 0.0)],
    ]


def _volume_sob_tin(vertices, triangulos, z_base=0.0):
    """Volume entre a superfície TIN e o plano z=z_base.

    Exacto para superfícies univalentes em (x, y): soma, por triângulo,
    da cota média vezes a área projectada.
    """
    v = np.asarray(vertices)
    t = np.asarray(triangulos)
    total = 0.0
    for a, b, c in t:
        pa, pb, pc = v[a], v[b], v[c]
        zm = (pa[2] + pb[2] + pc[2]) / 3.0 - z_base
        area2d = 0.5 * abs(
            (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        )
        total += zm * area2d
    return total


def _segmentos_breakline(breaklines, passo):
    """Segmentos das polilinhas de breakline tal como densificadas."""
    segmentos = []
    for bl in breaklines:
        prev = tuple(map(float, bl[0]))
        for q in map(lambda p: tuple(map(float, p)), bl[1:]):
            seg = float(np.linalg.norm(np.asarray(q) - np.asarray(prev)))
            n = max(1, int(np.ceil(seg / passo)))
            p0 = np.asarray(prev)
            for k in range(1, n + 1):
                destino = tuple(map(float, q)) if k == n else tuple(p0 + (np.asarray(q) - p0) * (k / n))
                segmentos.append((prev, destino))
                prev = destino
    return segmentos


def _verifica_sem_cruzamentos(res, breaklines):
    vertices = res["vertices"]
    passo = res["estatisticas"]["densificacao"]
    segmentos = _segmentos_breakline(breaklines, passo)
    for a, b, c in res["triangulos"]:
        for u, w in ((a, b), (b, c), (c, a)):
            p2, q2 = tuple(vertices[u][:2]), tuple(vertices[w][:2])
            if p2 == q2:
                continue
            for (p, q) in segmentos:
                assert not _cruzam(p2, q2, p[:2], q[:2]), (
                    f"aresta da malha {p2}-{q2} cruza a breakline {p[:2]}-{q[:2]}"
                )


def test_area_do_plano_inclinado_e_exacta():
    from freecad.topografia.objetos.tin import construir_malha

    res = triangula(_plano_inclinado())
    malha = construir_malha(res["vertices"], res["triangulos"])
    analitico = 100.0 * 100.0 * (1 + 0.01) ** 0.5
    assert abs(malha.Area - analitico) / analitico < 1e-3


def test_volume_da_piramide_com_breaklines_erro_menor_que_0_1_porcento():
    pontos = _piramide()
    res = triangula(pontos, breaklines=_breaklines_piramide())
    volume = _volume_sob_tin(res["vertices"], res["triangulos"])
    analitico = 100.0 * 100.0 * 10.0 / 3.0
    erro = abs(volume - analitico) / analitico
    assert erro < 0.001, f"volume={volume:.4f} analitico={analitico} erro={erro:.5%}"
    assert res["estatisticas"]["arestas_falhadas"] == 0


def test_nenhuma_aresta_da_malha_cruza_as_breaklines():
    res = triangula(_piramide(n=11), breaklines=_breaklines_piramide())
    assert res["arestas_impostas"], "esperava-se pelo menos uma aresta imposta"
    _verifica_sem_cruzamentos(res, _breaklines_piramide())


def test_breakline_imposta_num_caso_adverso():
    pontos = [
        (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (10.0, 10.0, 0.0), (-10.0, 10.0, 0.0),
        (0.0, 0.0, 8.0),
        (-6.0, 0.4, 1.0), (6.0, -0.4, 1.0),  # pontos que "roubam" a aresta central
    ]
    breakline = [[(-10.0, -10.0, 0.0), (0.0, 0.0, 8.0), (10.0, 10.0, 0.0)]]
    res = triangula(pontos, breaklines=breakline)
    assert res["estatisticas"]["arestas_falhadas"] == 0
    _verifica_sem_cruzamentos(res, breakline)


def test_flip_e_localizacao_operam_de_forma_limpa():
    xy = np.array([[0.0, 0.0], [1.0, 0.0], [1.1, 1.0], [0.0, 1.0], [0.4, 0.2]])
    malha = MalhaDelaunay(xy)
    assert all(len(t) == 3 for t in malha.tris)
    ok = malha.impor(0, 2)
    assert isinstance(ok, bool)
    if ok:
        assert malha.tem(0, 2)


def test_filtro_aresta_maxima_remove_triangulos_compridos():
    pontos = _plano_inclinado(n=5)
    sem_filtro = triangula(pontos)
    com_filtro = triangula(pontos, aresta_maxima=10.0)
    assert len(com_filtro["triangulos"]) < len(sem_filtro["triangulos"])


def test_desempenho_10000_pontos_com_breakline():
    """Critério de aceitação da Fase 1: TIN de 10.000 pontos em menos de 30 s."""
    import time

    xs = np.linspace(0, 990, 100)
    ys = np.linspace(0, 990, 100)
    pontos = [
        (float(x), float(y), float(100 + 5 * np.sin(x / 200) + 4 * np.cos(y / 250)))
        for x in xs
        for y in ys
    ]
    breakline = [(float(x), 500.0, float(100 + 5 * np.sin(x / 200) + 4 * np.cos(2.0))) for x in xs]
    t0 = time.time()
    res = triangula(pontos, breaklines=[breakline])
    duracao = time.time() - t0
    assert res["estatisticas"]["vertices"] >= 10_000
    assert res["estatisticas"]["triangulos"] > 19_000
    assert duracao < 30.0, f"triangulação demorou {duracao:.1f}s"
