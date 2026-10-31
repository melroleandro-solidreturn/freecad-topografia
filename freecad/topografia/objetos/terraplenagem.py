# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objecto Terraplenagem: volumes cut/fill paramétricos sobre a cadeia Fase 2.

Liga a TIN da Topografia ao Alinhamento e Perfil do CorridorRoad (v1) e
recalcula, a cada recompute, as secções de terraplenagem (com encontro de
taludes na TIN — a peça que o CorridorRoad v1.1.1 não materializa), os
volumes por áreas-médias e a curva de massas.
"""
from __future__ import annotations

import FreeCAD

from .. import terraplenagem as motor
from ..terraplenagem import SECCAO_PREDEFINIDA


class Terraplenagem:
    """Proxy de App::FeaturePython com resultados por estação."""

    def __init__(self, obj):
        self.Type = "Topografia::Terraplenagem"

        obj.addProperty(
            "App::PropertyLink", "TIN", "Entradas",
            "Superfície de terreno (Topografia)").TIN = None
        obj.addProperty(
            "App::PropertyLink", "Alinhamento", "Entradas",
            "Alinhamento (CorridorRoad v1)").Alinhamento = None
        obj.addProperty(
            "App::PropertyLink", "Perfil", "Entradas",
            "Perfil projectado (CorridorRoad v1)").Perfil = None
        obj.addProperty(
            "App::PropertyFloat", "IntervaloEstacoes", "Entradas",
            "Intervalo entre estações (m)").IntervaloEstacoes = 20.0
        obj.addProperty(
            "App::PropertyFloat", "EstacaoInicio", "Entradas",
            "Estação inicial (0 = início do alinhamento)").EstacaoInicio = 0.0
        obj.addProperty(
            "App::PropertyFloat", "EstacaoFim", "Entradas",
            "Estação final (0 = fim do alinhamento)").EstacaoFim = 0.0
        obj.addProperty(
            "App::PropertyPythonObject", "Parametros", "Secção",
            "Parâmetros da secção tipo (ver terraplenagem.SECCAO_PREDEFINIDA)"
        ).Parametros = dict(SECCAO_PREDEFINIDA)
        obj.addProperty(
            "App::PropertyPythonObject", "Resultados", "Saídas",
            "Secções, volumes e curva de massas").Resultados = {}
        obj.addProperty(
            "App::PropertyString", "Estatisticas", "Saídas",
            "Resumo do último cálculo").Estatisticas = ""

        obj.Proxy = self

    def execute(self, obj):
        from freecad.Corridor_Road.v1.objects.obj_alignment import to_alignment_model
        from freecad.Corridor_Road.v1.objects.obj_profile import to_profile_model
        from freecad.Corridor_Road.v1.services.evaluation.alignment_evaluation_service import (
            AlignmentEvaluationService,
        )
        from freecad.Corridor_Road.v1.services.evaluation.profile_evaluation_service import (
            ProfileEvaluationService,
        )

        if not (obj.TIN and obj.Alinhamento and obj.Perfil and obj.TIN.ModeloTIN):
            obj.Resultados = {}
            obj.Estatisticas = "entradas incompletas"
            return

        modelo_al = to_alignment_model(obj.Alinhamento)
        modelo_pf = to_profile_model(obj.Perfil)
        modelo_tin = obj.TIN.ModeloTIN
        params = dict(motor.SECCAO_PREDEFINIDA)
        params.update(obj.Parametros or {})

        comprimento = float(getattr(obj.Alinhamento, "TotalLength", 0.0) or 0.0)
        fim = obj.EstacaoFim if obj.EstacaoFim > 0 else comprimento
        inicio = obj.EstacaoInicio or 0.0
        intervalo = max(float(obj.IntervaloEstacoes), 0.5)
        estacoes = []
        s = inicio
        while s <= fim + 1e-6:
            estacoes.append(round(s, 6))
            s += intervalo
        if estacoes[-1] < fim:
            estacoes.append(fim)

        serv_al = AlignmentEvaluationService()
        serv_pf = ProfileEvaluationService()
        seccoes = []
        for s in estacoes:
            frame = serv_al.evaluate_station(modelo_al, s)
            perfil = serv_pf.evaluate_station(modelo_pf, s)
            if getattr(frame, "status", "") != "ok" or getattr(perfil, "status", "") != "ok":
                continue
            sec = motor.seccao_terraplenagem(
                modelo_tin, frame.x, frame.y, frame.tangent_direction_deg,
                perfil.elevation, params)
            sec["estacao"] = s
            seccoes.append(sec)

        est = [sec["estacao"] for sec in seccoes]
        volumes = motor.volumes_areas_medias(
            est, [x["a_corte"] for x in seccoes], [x["a_aterro"] for x in seccoes],
            [x["a_pavimento"] for x in seccoes])
        curva = motor.mass_haul(est, [x["a_corte"] for x in seccoes], [x["a_aterro"] for x in seccoes])

        obj.Resultados = {
            "estacoes": est, "seccoes": seccoes, "volumes": volumes, "mass_haul": curva,
        }
        obj.Estatisticas = (
            f"estações={len(est)} corte={volumes['volume_corte']:.1f} m³ "
            f"aterro={volumes['volume_aterro']:.1f} m³ pavimento={volumes['volume_pavimento']:.1f} m³ "
            f"líquido={volumes['liquido']:.1f} m³ "
            f"balanceamentos={len(curva['pontos_balanceamento'])}"
        )


def exportar_csv(resultados: dict, caminho: str) -> None:
    """Tabela por estação + intervalos para CSV."""
    linhas = ["estacao;a_corte_m2;a_aterro_m2;a_pavimento_m2;dia_esq_m;dia_dir_m"]
    for sec in resultados["seccoes"]:
        linhas.append(
            f"{sec['estacao']:.1f};{sec['a_corte']:.3f};{sec['a_aterro']:.3f};"
            f"{sec['a_pavimento']:.3f};{sec['dia_esquerdo']:.3f};{sec['dia_direito']:.3f}")
    linhas.append("")
    linhas.append("estacao_ini;estacao_fim;comprimento;volume_corte;volume_aterro;volume_pavimento")
    for l in resultados["volumes"]["linhas"]:
        linhas.append(
            f"{l['estacao_ini']:.1f};{l['estacao_fim']:.1f};{l['comprimento']:.1f};"
            f"{l['volume_corte']:.3f};{l['volume_aterro']:.3f};{l['volume_pavimento']:.3f}")
    with open(caminho, "w") as f:
        f.write("\n".join(linhas) + "\n")


def grafico_mass_haul(resultados: dict, caminho: str) -> None:
    """Curva de massas em PNG (matplotlib em modo Agg)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curva = resultados["mass_haul"]["curva"]
    x = [p["estacao"] for p in curva]
    y = [p["cumulativo"] for p in curva]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x, y, "b-", lw=1.6)
    ax.axhline(0, color="k", lw=0.8)
    ax.fill_between(x, y, 0, where=[v >= 0 for v in y], color="tab:orange", alpha=0.35,
                    label="excesso (transportar)")
    ax.fill_between(x, y, 0, where=[v < 0 for v in y], color="tab:blue", alpha=0.35,
                    label="necessidade (emprestar)")
    for p in resultados["mass_haul"]["pontos_balanceamento"]:
        ax.axvline(p, color="g", ls="--", lw=0.9)
    ax.set_xlabel("Estação (m)")
    ax.set_ylabel("Volume cumulativo (m³)")
    ax.set_title("Curva de massas")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)
    plt.close(fig)
