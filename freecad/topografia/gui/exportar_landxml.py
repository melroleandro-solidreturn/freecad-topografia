# SPDX-License-Identifier: LGPL-2.1-or-later
"""Exportação LandXML a partir da GUI (um ficheiro por objecto).

Com vários objectos seleccionados o comando antigo escrevia todos no
MESMO caminho — só o último sobrevivia. Aqui o nome é decidido por
função pura (testável): 1 objecto → o nome escolhido; N objectos →
``<base>_<label>_tin.landxml`` / ``<base>_<label>_pontos.landxml``.
"""
import os
import re

from ..i18n import tr


def e_exportavel(obj):
    """Objecto com TIN (ModeloTIN) ou Levantamento."""
    if "ModeloTIN" in obj.PropertiesList and obj.ModeloTIN:
        return "tin"
    if getattr(getattr(obj, "Proxy", None), "Type", "") == "Topografia::Levantamento":
        return "pontos"
    return None


def nome_ficheiro(base, obj):
    """Nome de saída para *obj* dado um caminho-base (função pura)."""
    tipo = e_exportavel(obj)
    rotulo = re.sub(r"[^A-Za-z0-9_.-]+", "_", obj.Label).strip("_") or obj.Name
    raiz, _ = os.path.splitext(base)
    sufixo = {"tin": "tin", "pontos": "pontos"}[tipo]
    return f"{raiz}_{rotulo}_{sufixo}.landxml"


def exportar(obj, caminho):
    """Exporta *obj* para *caminho*; devolve uma mensagem de resultado."""
    import FreeCAD as App

    tipo = e_exportavel(obj)
    if tipo == "tin":
        from ..landxml_export import exporta_tin_landxml
        n = exporta_tin_landxml(obj.ModeloTIN, caminho)
        return f"[Topografia] {obj.Label}: {n} {tr('triangles')} -> {caminho}"
    if tipo == "pontos":
        from ..landxml_export import exporta_pontos_landxml
        n = exporta_pontos_landxml(obj, caminho)
        return f"[Topografia] {obj.Label}: {n} {tr('points')} -> {caminho}"
    return None


def exportar_seleccao(base, objectos):
    """Exporta *objectos* sem sobreposições; devolve (mensagens, erros)."""
    mensagens, erros = [], []
    for obj in objectos:
        tipo = e_exportavel(obj)
        if not tipo:
            erros.append(f"[Topografia] {obj.Label}: {tr('not exportable to LandXML')}")
            continue
        caminho = base if len(objectos) == 1 else nome_ficheiro(base, obj)
        mensagens.append(exportar(obj, caminho))
    return mensagens, erros
