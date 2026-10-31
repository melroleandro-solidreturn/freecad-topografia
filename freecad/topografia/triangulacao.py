# SPDX-License-Identifier: LGPL-2.1-or-later
"""Triangulação Delaunay de pontos topográficos com breaklines impostas.

Estratégia (Fase 1 do plano):

1. Densificação das polilinhas de breakline com passo adaptativo
   (metade da distância mediana ao vizinho mais próximo), interpolando a cota.
2. Delaunay (scipy) sobre todos os vértices.
3. Recuperação de arestas em falta por *flips* locais (caminhada pela faixa
   que cruza o segmento, trocando diagonais de quadriláteros convexos).
4. Se uma aresta continuar em falta, é subdividida ao meio e o processo
   repete-se (limitado a ``rondas``), o que converge na prática.

Módulo livre de dependências do FreeCAD (apenas numpy/scipy) para ser
testado isoladamente.
"""
from __future__ import annotations

import time

import numpy as np
from scipy.spatial import Delaunay, cKDTree

EPS = 1e-12


def _orient(p, q, r) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _cruzam(a, b, p, q) -> bool:
    """Cruzamento estrito dos segmentos ab e pq (2D)."""
    o1 = _orient(a, b, p)
    o2 = _orient(a, b, q)
    if o1 * o2 >= 0:
        return False
    o3 = _orient(p, q, a)
    o4 = _orient(p, q, b)
    return o3 * o4 < 0


class MalhaDelaunay:
    """Delaunay mutável com operação de imposição de arestas por flips."""

    def __init__(self, xy: np.ndarray):
        self.xy = np.asarray(xy, dtype=float)
        delaunay = Delaunay(self.xy)
        self.tris = [tuple(int(i) for i in t) for t in delaunay.simplices]
        self.aresta_tris: dict = {}
        self.vert_tris: dict = {}
        self._indexa()

    # -- indexação ---------------------------------------------------------
    def _indexa(self) -> None:
        self.aresta_tris = {}
        self.vert_tris = {}
        for tid, t in enumerate(self.tris):
            for a, b in self._arestas(t):
                self.aresta_tris.setdefault((min(a, b), max(a, b)), set()).add(tid)
            for v in t:
                self.vert_tris.setdefault(v, set()).add(tid)

    @staticmethod
    def _arestas(t):
        return ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))

    def _remove_tri(self, tid: int) -> None:
        t = self.tris[tid]
        for a, b in self._arestas(t):
            self.aresta_tris[(min(a, b), max(a, b))].discard(tid)
        for v in t:
            self.vert_tris[v].discard(tid)

    def _adiciona_tri(self, tid: int) -> None:
        t = self.tris[tid]
        for a, b in self._arestas(t):
            self.aresta_tris.setdefault((min(a, b), max(a, b)), set()).add(tid)
        for v in t:
            self.vert_tris.setdefault(v, set()).add(tid)

    # -- operações ---------------------------------------------------------
    def tem(self, a: int, b: int) -> bool:
        return (min(a, b), max(a, b)) in self.aresta_tris

    def flip(self, aresta) -> bool:
        """Troca a diagonal do quadrilátero convexo definido pela aresta."""
        chave = (min(aresta), max(aresta))
        tids = self.aresta_tris.get(chave, set())
        if len(tids) != 2:
            return False
        t1, t2 = tuple(tids)
        p, q = chave
        r = (set(self.tris[t1]) - {p, q}).pop()
        s = (set(self.tris[t2]) - {p, q}).pop()
        # convexidade: p e q em lados opostos da nova diagonal rs
        if _orient(self.xy[r], self.xy[s], self.xy[p]) * _orient(self.xy[r], self.xy[s], self.xy[q]) >= 0:
            return False
        if _orient(self.xy[r], self.xy[s], self.xy[p]) == 0:
            return False
        self._remove_tri(t1)
        self._remove_tri(t2)
        self.tris[t1] = (r, s, p)
        self.tris[t2] = (r, s, q)
        self._adiciona_tri(t1)
        self._adiciona_tri(t2)
        return True

    # -- localização -------------------------------------------------------
    def _dentro(self, tid: int, m) -> bool:
        (x1, y1), (x2, y2), (x3, y3) = (tuple(self.xy[i]) for i in self.tris[tid])
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(d) < 1e-18:
            return False
        u = ((y2 - y3) * (m[0] - x3) + (x3 - x2) * (m[1] - y3)) / d
        v = ((y3 - y1) * (m[0] - x3) + (x1 - x3) * (m[1] - y3)) / d
        return u >= -1e-9 and v >= -1e-9 and u + v <= 1 + 1e-9

    def _centroide(self, tid: int):
        t = self.tris[tid]
        return tuple(self.xy[list(t)].mean(axis=0))

    def _localiza(self, tid0: int, m):
        """Caminhada gulosa até ao triângulo que contém m (ou None)."""
        tid = tid0
        visto = set()
        while tid is not None and tid not in visto:
            if self._dentro(tid, m):
                return tid
            visto.add(tid)
            melhor, melhor_d = None, None
            for a, b in self._arestas(self.tris[tid]):
                viz = self.aresta_tris.get((min(a, b), max(a, b)), set()) - {tid}
                if not viz:
                    continue
                for v in viz:
                    if v in visto:
                        continue
                    d = (self._centroide(v)[0] - m[0]) ** 2 + (self._centroide(v)[1] - m[1]) ** 2
                    if melhor_d is None or d < melhor_d:
                        melhor, melhor_d = v, d
            tid = melhor
        return None

    # -- imposição ---------------------------------------------------------
    def impor(self, a: int, b: int) -> bool:
        """Impõe a aresta (a, b) na triangulação por flips; True se conseguiu."""
        if self.tem(a, b):
            return True
        pa, pb = tuple(self.xy[a]), tuple(self.xy[b])
        m = ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
        candidatos = self.vert_tris.get(a, set())
        if not candidatos:
            return False
        tid = min(candidatos, key=lambda t: (self._centroide(t)[0] - m[0]) ** 2 + (self._centroide(t)[1] - m[1]) ** 2)
        for _ in range(4 * len(self.tris) + 16):
            if self.tem(a, b):
                return True
            t = self.tris[tid]
            alvo = None
            for e in self._arestas(t):
                if a in e or b in e:
                    continue
                if _cruzam(pa, pb, tuple(self.xy[e[0]]), tuple(self.xy[e[1]])):
                    alvo = e
                    break
            if alvo is None:
                return self.tem(a, b)
            if not self.flip(alvo):
                return False
            tid = self._localiza(tid, m)
            if tid is None:
                return self.tem(a, b)
        return self.tem(a, b)


class _ConjuntoVertices:
    """Vértices únicos com dedup por coordenada arredondada (6 casas)."""

    def __init__(self):
        self.pontos: list = []
        self.indice: dict = {}

    def adiciona(self, p) -> int:
        chave = (round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6))
        idx = self.indice.get(chave)
        if idx is not None:
            return idx
        self.pontos.append((float(p[0]), float(p[1]), float(p[2])))
        self.indice[chave] = len(self.pontos) - 1
        return len(self.pontos) - 1


def _passo_adaptativo(xy: np.ndarray) -> float:
    if len(xy) < 2:
        return 1.0
    kd = cKDTree(xy)
    dist, _ = kd.query(xy, k=2)
    mediana = float(np.median(dist[:, 1]))
    return max(mediana / 2.0, 0.01)


def _densifica_polilinha(poly, passo: int | float):
    """Devolve vértices da polilinha com intermédios espaçados de 'passo' (cota interpolada)."""
    if passo <= 0:
        return list(poly)
    saida = [poly[0]]
    for p, q in zip(poly[:-1], poly[1:]):
        seg = float(np.linalg.norm(np.asarray(q) - np.asarray(p)))
        n = max(1, int(np.ceil(seg / passo)))
        for k in range(1, n + 1):
            saida.append(tuple(np.asarray(p) + (np.asarray(q) - np.asarray(p)) * (k / n)))
    return saida


def _absorve_vertices(poly, fixos_xy, fixos3d, eps=1e-6):
    """Insere na cadeia os vértices fixos que caem sobre a polilinha (2D).

    Necessário porque uma breakline pode passar exactamente por vértices de
    dados colineares (p.ex. grelha na crista de uma pirâmide); sem absorção,
    o segmento da breakline atravessaria um vértice e a imposição degenera.
    """
    if len(fixos_xy) == 0:
        return list(poly)
    cadeia = [tuple(map(float, poly[0]))]
    for p3, q3 in zip(poly[:-1], poly[1:]):
        p, q = np.asarray(p3[:2], float), np.asarray(q3[:2], float)
        d = q - p
        l2 = float((d * d).sum())
        if l2 < 1e-18:
            cadeia.append(tuple(map(float, q3)))
            continue
        t = ((fixos_xy - p) @ d) / l2
        proj = p + t[:, None] * d
        dist2 = ((fixos_xy - proj) ** 2).sum(axis=1)
        mascara = (t > 1e-9) & (t < 1.0 - 1e-9) & (dist2 < eps * eps)
        if mascara.any():
            ordem = np.argsort(t[mascara])
            for i in np.flatnonzero(mascara)[ordem]:
                cadeia.append(tuple(map(float, fixos3d[i])))
        cadeia.append(tuple(map(float, q3)))
    return cadeia


def triangula(
    pontos,
    breaklines=None,
    densificacao: float | None = None,
    aresta_maxima: float = 0.0,
    rondas: int = 6,
) -> dict:
    """Triangula pontos 3D com breaklines impostas.

    ``pontos``: sequência (n, 3) de coordenadas absolutas.
    ``breaklines``: polilinhas (sequências de vértices 3D) a impor na malha.
    ``densificacao``: passo de densificação das breaklines (0/None = auto).
    ``aresta_maxima``: descarta triângulos com aresta 2D maior (0 = não filtra).

    Devolve dicionário com ``vertices`` (m,3), ``triangulos`` (t,3),
    ``arestas_impostas`` (lista de pares), ``falhas`` e ``estatisticas``.
    """
    t0 = time.time()
    breaklines = list(breaklines or [])
    vertices = _ConjuntoVertices()
    for p in pontos:
        vertices.adiciona(p)

    xy = np.array([(p[0], p[1]) for p in vertices.pontos])
    passo = float(densificacao) if densificacao else _passo_adaptativo(xy)

    # vértices "fixos" (dados + polilinhas já processadas) para atracamento
    fixos3d = [tuple(map(float, p)) for p in pontos]

    arestas: set = set()

    def processa_polilinha(poly):
        fixos_xy = np.array([(p[0], p[1]) for p in fixos3d])
        cadeia = _absorve_vertices(poly, fixos_xy, fixos3d)
        prev = vertices.adiciona(cadeia[0])
        for c, d in zip(cadeia[:-1], cadeia[1:]):
            sub = _densifica_polilinha([c, d], passo)
            for v in sub[1:]:
                idx = vertices.adiciona(v)
                if idx != prev:
                    arestas.add((min(prev, idx), max(prev, idx)))
                    prev = idx
        # vértices originais da polilinha passam a fixos (breaklines cruzam-se)
        for v in poly:
            fixos3d.append(tuple(map(float, v)))

    for polilinha in breaklines:
        if len(polilinha) >= 2:
            processa_polilinha(polilinha)

    malha = None
    falhas = []
    for _ in range(max(1, rondas + 1)):
        xy = np.array([(p[0], p[1]) for p in vertices.pontos])
        malha = MalhaDelaunay(xy)
        falhas = []
        for (a, b) in sorted(arestas):
            if not malha.impor(a, b):
                falhas.append((a, b))
        faltam = [e for e in arestas if not malha.tem(*e)]
        if not faltam:
            break
        # subdivide ao meio as arestas que resistiram e repete
        novas = set()
        for (a, b) in arestas:
            novas.add((a, b))
        for (a, b) in faltam:
            novas.discard((a, b))
            meio = (
                (vertices.pontos[a][0] + vertices.pontos[b][0]) / 2.0,
                (vertices.pontos[a][1] + vertices.pontos[b][1]) / 2.0,
                (vertices.pontos[a][2] + vertices.pontos[b][2]) / 2.0,
            )
            m = vertices.adiciona(meio)
            novas.add((min(a, m), max(a, m)))
            novas.add((min(m, b), max(m, b)))
        arestas = novas

    triangulos = list(malha.tris)
    if aresta_maxima and aresta_maxima > 0:
        limite = float(aresta_maxima) ** 2
        xyv = np.array([(p[0], p[1]) for p in vertices.pontos])
        filtrados = []
        for (a, b, c) in triangulos:
            ok = True
            for u, v in ((a, b), (b, c), (c, a)):
                if float(((xyv[u] - xyv[v]) ** 2).sum()) > limite:
                    ok = False
                    break
            if ok:
                filtrados.append((a, b, c))
        triangulos = filtrados

    impostas = sorted(e for e in arestas if malha.tem(*e))
    dt = time.time() - t0
    estatisticas = {
        "vertices": len(vertices.pontos),
        "triangulos": len(triangulos),
        "breaklines": len(breaklines),
        "arestas_impostas": len(impostas),
        "arestas_falhadas": len([e for e in arestas if not malha.tem(*e)]),
        "densificacao": passo,
        "segundos": round(dt, 3),
    }
    return {
        "vertices": np.array(vertices.pontos),
        "triangulos": np.array(triangulos, dtype=int),
        "arestas_impostas": impostas,
        "falhas": [e for e in arestas if not malha.tem(*e)],
        "estatisticas": estatisticas,
    }
