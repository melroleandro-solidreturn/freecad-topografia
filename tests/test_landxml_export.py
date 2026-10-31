# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes do exporter LandXML, com round-trip contra o CorridorRoad."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from freecad.topografia.landxml_export import exporta_pontos_landxml, exporta_tin_landxml
from freecad.topografia.terraplenagem import interp_z
from freecad.topografia.triangulacao import triangula


@pytest.fixture()
def modelo_com_origem():
    xs = [x for x in range(-30, 31, 10)]
    pontos = [(float(x), float(y), 0.1 * y) for x in xs for y in xs]
    res = triangula(pontos)
    # simula origem absoluta UTM (a geometria é local)
    return {
        "origem": (353000.0, 4168000.0, 100.0),
        "vertices": [tuple(map(float, v)) for v in res["vertices"]],
        "triangulos": [tuple(map(int, t)) for t in res["triangulos"]],
    }


def test_exporta_tin_com_coordenadas_absolutas(tmp_path, modelo_com_origem):
    ficheiro = tmp_path / "tin.xml"
    n = exporta_tin_landxml(modelo_com_origem, str(ficheiro))
    assert n == len(modelo_com_origem["triangulos"]) > 0
    root = ET.parse(str(ficheiro)).getroot()
    assert root.tag.endswith("LandXML") and root.attrib["version"] == "1.2"
    pontos = [e for e in root.iter() if e.tag.endswith("}P") or e.tag == "P"]
    textos = [p.text.split() for p in pontos]
    xs = [float(t[0]) for t in textos]
    ys = [float(t[1]) for t in textos]
    # absolutas: dentro da envolvente UTM esperada, não da local
    assert min(xs) > 352960.0 and max(xs) < 353040.0
    assert min(ys) > 4167960.0 and max(ys) < 4168040.0
    zs = [float(t[2]) for t in textos]
    assert min(zs) >= 96.5 and max(zs) <= 103.5  # 100 + (−3..3)


def test_round_trip_atraves_do_importador_do_corridorroad(tmp_path, modelo_com_origem):
    """A TIN exportada é lida pelo LandXML importer do PRW e amostra igual."""
    prw = pytest.importorskip(
        "freecad.Corridor_Road.v1.exchange.landxml_import",
        reason="CorridorRoad não disponível")
    from freecad.Corridor_Road.v1.exchange.landxml_import import scan_landxml_root
    from freecad.Corridor_Road.v1.exchange.landxml_surface_mapper import (
        tin_surface_from_landxml_candidate,
    )
    from freecad.Corridor_Road.v1.services.evaluation.tin_sampling_service import (
        TinSamplingService,
    )

    ficheiro = tmp_path / "tin.xml"
    exporta_tin_landxml(modelo_com_origem, str(ficheiro))
    resultado = scan_landxml_root(ET.parse(str(ficheiro)).getroot(), source_path=str(ficheiro))
    assert resultado.surfaces, "o importador do PRW não encontrou a superfície"
    superficie = tin_surface_from_landxml_candidate(resultado.surfaces[0])

    ox, oy, oz = modelo_com_origem["origem"]
    servico = TinSamplingService()
    for (lx, ly) in [(-13.3, 7.7), (12.1, -4.5), (0.0, 0.0), (20.0, 20.0)]:
        esperado = interp_z(modelo_com_origem, lx, ly)
        amostra = servico.sample_xy(surface=superficie, x=lx + ox, y=ly + oy)
        assert amostra.found
        assert amostra.z == pytest.approx(esperado + oz, abs=1e-6)


def test_exporta_pontos_com_codigo_no_desc(tmp_path, doc, dados):
    from freecad.topografia.objetos.levantamento import importar

    lev, _ = importar(str(dados / "levantamento_ptpt_v2.csv"), doc)
    ficheiro = tmp_path / "pontos.xml"
    n = exporta_pontos_landxml(lev, str(ficheiro))
    assert n == 89
    root = ET.parse(str(ficheiro)).getroot()
    cgpoints = [e for e in root.iter() if e.tag.endswith("}CgPoint") or e.tag == "CgPoint"]
    codigos = {p.attrib.get("desc", "") for p in cgpoints}
    assert "EIX" in codigos and "LE_E" in codigos
    primeiro = cgpoints[0]
    assert primeiro.attrib["id"].upper().startswith("P")
    assert len(primeiro.text.split()) == 3
