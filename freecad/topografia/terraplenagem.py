# SPDX-License-Identifier: LGPL-2.1-or-later
"""Movimento de terras (Fase 3): corte/aterro por estações sobre a TIN.

Motor puro (sem FreeCAD) que fecha a lacuna auditada no CorridorRoad v1.1.1:
o encontro dos taludes com o terreno (daylight) é calculado aqui, secção a
secção, por marcha + bissecção sobre a TIN da Topografia.

Modelo por estação:
- plataforma (topo) a partir da cota do perfil e caimentos por segmento;
- datum = topo - espessura de estrutura;
- taludes do bordo do datum até interceptar a linha de terreno existente;
- áreas corte/aterro entre EG e datum (trapézios, passo configurável);
- volumes por áreas-médias entre estações; mass haul cumulativo.
"""
from __future__ import annotations

import math

SECCAO_PREDEFINIDA = {
    "faixa": 3.5,               # largura de faixa de rodagem por lado (m)
    "ombro": 1.5,               # largura de ombro por lado (m)
    "caimento_faixa": -0.02,    # dz/d|o|
    "caimento_ombro": -0.04,
    "espessura_estrutura": 0.45,  # topo -> datum (m)
    "talude_corte": 2.0,        # 1V:2H (horizontal por vertical)
    "talude_aterro": 3.0,       # 1V:3H
    "passo": 0.25,              # passo de integração lateral (m)
    "largura_maxima": 40.0,     # limite de procura do encontro (m)
}


def interp_z(modelo_tin: dict, x: float, y: float):
    """Interpolação barycêntrica sobre o ModeloTIN (coordenadas absolutas)."""
    verts = modelo_tin["vertices"]
    melhor, melhor_d2 = None, None
    for a, b, c in modelo_tin["triangulos"]:
        pa, pb, pc = verts[a], verts[b], verts[c]
        d = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
        if abs(d) < 1e-15:
            continue
        u = ((pb[1] - pc[1]) * (x - pc[0]) + (pc[0] - pb[0]) * (y - pc[1])) / d
        if u < -1e-9:
            continue
        v = ((pc[1] - pa[1]) * (x - pc[0]) + (pa[0] - pc[0]) * (y - pc[1])) / d
        if v < -1e-9 or u + v > 1 + 1e-9:
            continue
        return u * pa[2] + v * pb[2] + (1 - u - v) * pc[2]
    return None


def normal_de(direcao_deg: float):
    rad = math.radians(direcao_deg)
    return -math.sin(rad), math.cos(rad)


def _plataforma(z_eixo: float, params: dict):
    """Offsets e cotas do TOPO da plataforma (do bordo esquerdo ao direito)."""
    f, o = params["faixa"], params["ombro"]
    cf, co = -abs(params["caimento_faixa"]), -abs(params["caimento_ombro"])
    borda = f + o
    pts = [
        (-borda, z_eixo + f * abs(cf) + o * abs(co)),   # borda esquerda do ombro
        (-f, z_eixo + f * abs(cf)),                      # borda esquerda da faixa
        (0.0, z_eixo),                                   # eixo
        (f, z_eixo + f * abs(cf)),
        (borda, z_eixo + f * abs(cf) + o * abs(co)),
    ]
    return pts, borda


def _linha_linear(pts, o):
    """Avalia a polilinha (offsets crescentes) em o."""
    if o <= pts[0][0]:
        return pts[0][1]
    if o >= pts[-1][0]:
        return pts[-1][1]
    for (o0, z0), (o1, z1) in zip(pts[:-1], pts[1:]):
        if o0 <= o <= o1:
            if o1 == o0:
                return z0
            t = (o - o0) / (o1 - o0)
            return z0 + t * (z1 - z0)
    return pts[-1][1]


def _encontra_talude(modelo_tin, x0, y0, normal, borda, z_borda, params, lado):
    """Marcha + bissecção do encontro do talude com o terreno.

    ``lado``: -1 (esquerdo) ou +1 (direito); offset = borda + lado*dist.
    Devolve (offset_encontro, z_encontro) ou None se não encontrou.
    """
    passo, lmax = params["passo"], params["largura_maxima"]
    eg_borda = interp_z(modelo_tin, x0 + normal[0] * borda, y0 + normal[1] * borda)
    if eg_borda is None:
        return None
    corte = eg_borda > z_borda
    n = params["talude_corte"] if corte else params["talude_aterro"]
    sinal = 1.0 if corte else -1.0  # corte: talude sobe; aterro: desce

    def f(dist):
        o = lado * (borda + dist)
        z_t = z_borda + sinal * dist / n
        eg = interp_z(modelo_tin, x0 + normal[0] * o, y0 + normal[1] * o)
        if eg is None:
            return None
        return z_t - eg, z_t

    d = passo
    f0 = (z_borda - eg_borda, z_borda)
    while d <= lmax:
        atual = f(d)
        if atual is not None and (atual[0] * f0[0]) <= 0:
            lo, hi, flo = d - passo, d, f0[0]
            for _ in range(60):
                mid = (lo + hi) / 2.0
                fm = f(mid)
                if fm is None:
                    break
                if fm[0] * flo <= 0:
                    hi = mid
                else:
                    lo, flo = mid, fm[0]
            o = lado * (borda + (lo + hi) / 2.0)
            zf = f((lo + hi) / 2.0)
            return o, (zf[1] if zf else z_borda)
        if atual is not None:
            f0 = atual
        d += passo
    return None


def seccao_terraplenagem(modelo_tin, x0, y0, direcao_deg, z_eixo, params=None):
    """Uma sample line: EG + projecto e áreas de corte/aterro da estação."""
    p = dict(SECCAO_PREDEFINIDA)
    p.update(params or {})
    normal = normal_de(direcao_deg)
    topo, borda = _plataforma(z_eixo, p)
    esp = p["espessura_estrutura"]
    datum_plat = [(o, z - esp) for o, z in topo]

    # encontros de talude a partir do bordo do datum
    encontros = {}
    for lado, borda_pts in ((-1, datum_plat[0]), (1, datum_plat[-1])):
        encontro = _encontra_talude(
            modelo_tin, x0, y0, normal, abs(borda_pts[0]), borda_pts[1], p, lado)
        if encontro is None:
            # sem encontro: integra até à largura máxima com o talude teórico
            o_lim = abs(borda_pts[0]) + p["largura_maxima"]
            corte = True
            eg_b = interp_z(modelo_tin, x0 + normal[0] * borda_pts[0], y0 + normal[1] * borda_pts[0])
            if eg_b is not None and eg_b <= borda_pts[1]:
                corte = False
            n = p["talude_corte"] if corte else p["talude_aterro"]
            sinal = 1.0 if corte else -1.0
            encontro = (lado * o_lim, borda_pts[1] + sinal * (o_lim - abs(borda_pts[0])) / n)
        encontros[lado] = encontro

    dia_e, dia_d = encontros[-1][0], encontros[1][0]

    # polilinha do datum: plataforma + taludes até aos encontros
    datum_linha = [(o, z) for o, z in datum_plat]
    datum_linha.insert(0, (dia_e, encontros[-1][1]))
    datum_linha.append((dia_d, encontros[1][1]))

    def datum_em(o):
        return _linha_linear(datum_linha, o)

    def topo_em(o):
        return _linha_linear(topo, o)

    def eg_em(o):
        return interp_z(modelo_tin, x0 + normal[0] * o, y0 + normal[1] * o)

    # integração por trapézios de dia_e a dia_d
    passo = p["passo"]
    n_passos = max(2, int(math.ceil((dia_d - dia_e) / passo)))
    a_corte = a_aterro = 0.0
    anterior = None
    for i in range(n_passos + 1):
        o = dia_e + (dia_d - dia_e) * i / n_passos
        eg = eg_em(o)
        dz = datum_em(o) - eg if eg is not None else 0.0
        if anterior is not None:
            do = o - anterior[0]
            if anterior[1] >= 0 and dz >= 0:
                a_aterro += 0.5 * (anterior[1] + dz) * do
            elif anterior[1] <= 0 and dz <= 0:
                a_corte += -0.5 * (anterior[1] + dz) * do
            else:  # cruzamento dentro do passo: divide no zero
                t = anterior[1] / (anterior[1] - dz)
                z0 = 0.0
                do1, do2 = do * t, do * (1 - t)
                if anterior[1] > 0:
                    a_aterro += 0.5 * anterior[1] * do1
                    a_corte += -0.5 * dz * do2
                else:
                    a_corte += -0.5 * anterior[1] * do1
                    a_aterro += 0.5 * dz * do2
        anterior = (o, dz)

    a_pavimento = 2.0 * borda * esp
    return {
        "dia_esquerdo": dia_e, "dia_direito": dia_d,
        "a_corte": a_corte, "a_aterro": a_aterro, "a_pavimento": a_pavimento,
        "largura_plataforma": 2.0 * borda,
        "topo_polilinha": list(topo),
        "datum_polilinha": list(datum_linha),
    }


def volumes_areas_medias(estacoes, areas_corte, areas_aterro, areas_pavimento=None):
    """Volumes por áreas-médias entre estações consecutivas."""
    linhas, corte_total, aterro_total, pav_total = [], 0.0, 0.0, 0.0
    for i in range(len(estacoes) - 1):
        L = estacoes[i + 1] - estacoes[i]
        vc = 0.5 * (areas_corte[i] + areas_corte[i + 1]) * L
        va = 0.5 * (areas_aterro[i] + areas_aterro[i + 1]) * L
        vp = 0.5 * ((areas_pavimento or [0] * len(estacoes))[i]
                    + (areas_pavimento or [0] * len(estacoes))[i + 1]) * L if areas_pavimento else 0.0
        corte_total += vc
        aterro_total += va
        pav_total += vp
        linhas.append({
            "estacao_ini": estacoes[i], "estacao_fim": estacoes[i + 1], "comprimento": L,
            "volume_corte": vc, "volume_aterro": va, "volume_pavimento": vp,
        })
    return {
        "linhas": linhas,
        "volume_corte": corte_total, "volume_aterro": aterro_total,
        "volume_pavimento": pav_total,
        "liquido": corte_total - aterro_total,
    }


def mass_haul(estacoes, areas_corte, areas_aterro):
    """Curva de massas cumulativa (corte positivo, aterro negativo) por estação."""
    curva, acumulado = [], 0.0
    curva.append({"estacao": estacoes[0], "cumulativo": 0.0})
    for i in range(len(estacoes) - 1):
        L = estacoes[i + 1] - estacoes[i]
        acumulado += 0.5 * (areas_corte[i] + areas_corte[i + 1]) * L
        acumulado -= 0.5 * (areas_aterro[i] + areas_aterro[i + 1]) * L
        curva.append({"estacao": estacoes[i + 1], "cumulativo": acumulado})
    pontos_balanço = []
    for a, b in zip(curva[:-1], curva[1:]):
        if a["cumulativo"] == 0 or a["cumulativo"] * b["cumulativo"] < 0:
            t = abs(a["cumulativo"]) / (abs(a["cumulativo"]) + abs(b["cumulativo"]) or 1)
            pontos_balanço.append(a["estacao"] + t * (b["estacao"] - a["estacao"]))
        elif b["cumulativo"] == 0:
            pontos_balanço.append(b["estacao"])
    return {"curva": curva, "pontos_balanceamento": pontos_balanço}
