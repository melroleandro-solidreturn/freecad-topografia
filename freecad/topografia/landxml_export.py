# SPDX-License-Identifier: LGPL-2.1-or-later
"""Exportação LandXML (interoperabilidade com Civil 3D / CorridorRoad).

Gera LandXML 1.2 com:
- ``<Surfaces><Surface><Definition surfType="TIN">`` — a TIN da Topografia
  em coordenadas ABSOLUTAS (locais + origem de ``ModeloTIN``);
- ``<CgPoints>`` — os pontos do levantamento com o código no ``desc``
  (equivalente funcional dos Point Groups do Civil 3D).

O formato é validado por round-trip contra o importador LandXML do
CorridorRoad (ver tests/test_landxml_export.py).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

NAMESPACE = "http://www.landxml.org/schema/LandXML-1.2"


def exporta_tin_landxml(modelo_tin: dict, caminho: str, nome: str = "Terreno existente",
                        descricao: str = "TIN gerada pelo módulo Topografia") -> int:
    """Escreve a TIN em LandXML; devolve o número de triângulos."""
    ox, oy, oz = modelo_tin["origem"]
    root = ET.Element(f"{{{NAMESPACE}}}LandXML", {
        "version": "1.2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": f"{NAMESPACE} LandXML-1.2.xsd",
        "language": "pt-PT",
    })
    ET.SubElement(ET.SubElement(root, f"{{{NAMESPACE}}}Units"),
                  f"{{{NAMESPACE}}}Metric",
                  {"linearUnit": "meter", "areaUnit": "squareMeter",
                   "volumeUnit": "cubicMeter", "temperatureUnit": "celsius"})
    app = ET.SubElement(root, f"{{{NAMESPACE}}}Application",
                        {"name": "FreeCAD Topografia", "version": "0.1"})
    del app  # apenas metadados de produtor
    surfaces = ET.SubElement(root, f"{{{NAMESPACE}}}Surfaces")
    surface = ET.SubElement(surfaces, f"{{{NAMESPACE}}}Surface",
                            {"name": nome, "desc": descricao})
    definition = ET.SubElement(surface, f"{{{NAMESPACE}}}Definition",
                               {"surfType": "TIN"})
    pnts = ET.SubElement(definition, f"{{{NAMESPACE}}}Pnts")
    ids = {}
    for i, (x, y, z) in enumerate(modelo_tin["vertices"], start=1):
        ids[i - 1] = i
        P = ET.SubElement(pnts, f"{{{NAMESPACE}}}P", {"id": str(i)})
        P.text = f"{x + ox:.4f} {y + oy:.4f} {z + oz:.4f}"
    faces = ET.SubElement(definition, f"{{{NAMESPACE}}}Faces")
    for (a, b, c) in modelo_tin["triangulos"]:
        F = ET.SubElement(faces, f"{{{NAMESPACE}}}F")
        F.text = f"{ids[a]} {ids[b]} {ids[c]}"
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(caminho, encoding="UTF-8", xml_declaration=True)
    return len(modelo_tin["triangulos"])


def exporta_pontos_landxml(levantamento, caminho: str, nome: str = "Levantamento") -> int:
    """Escreve os pontos do Levantamento como CgPoints (código no desc)."""
    root = ET.Element(f"{{{NAMESPACE}}}LandXML", {
        "version": "1.2",
        "language": "pt-PT",
    })
    ET.SubElement(root, f"{{{NAMESPACE}}}Units").append(
        ET.Element(f"{{{NAMESPACE}}}Metric", {"linearUnit": "meter"}))
    cg = ET.SubElement(root, f"{{{NAMESPACE}}}CgPoints", {"name": nome})
    n = 0
    for chave in sorted(levantamento.Model, key=lambda k: int(k) if k.isdigit() else 10**9):
        p = levantamento.Model[chave]
        n += 1
        ET.SubElement(cg, f"{{{NAMESPACE}}}CgPoint",
                      {"id": p["Numero"], "desc": p["Codigo"]}).text = (
            f"{p['E']:.4f} {p['N']:.4f} {p['Z']:.4f}")
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(caminho, encoding="UTF-8", xml_declaration=True)
    return n
