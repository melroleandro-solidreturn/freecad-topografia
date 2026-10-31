# SPDX-License-Identifier: LGPL-2.1-or-later
"""Testes dos painéis de tarefa da GUI (Qt offscreen, FreeCADCmd).

Os painéis são instanciados directamente (sem diálogo do FreeCAD) e os
botões substituídos por chamadas aos métodos; os diálogos de ficheiro são
evitados passando caminhos explícitos.
"""
from __future__ import annotations

import pytest

from freecad.topografia.gui.exportar_landxml import (
    e_exportavel,
    exportar_seleccao,
    nome_ficheiro,
)
from freecad.topografia.gui.painel_importacao import PainelImportacao
from freecad.topografia.gui.painel_terraplenagem import (
    PainelTerraplenagem,
    candidatos,
)
from freecad.topografia.gui.painel_tin import PainelTIN, codigos_dos
from freecad.topografia.i18n import tr

AMOSTRA = "levantamento_ptpt_v2.csv"


def _amostra(dados):
    return str(dados / AMOSTRA)


def _levantamento(doc, dados):
    from freecad.topografia.objetos.levantamento import importar

    lev, _ = importar(_amostra(dados), doc)
    return lev


def _tin(doc, lev):
    from freecad.topografia.objetos.tin import TIN

    tin = doc.addObject("Mesh::FeaturePython", "TIN")
    TIN(tin)
    tin.Levantamentos = [lev]
    doc.recompute()
    return tin


# ------------------------------------------------------------------- i18n
def test_tr_sem_traducao_devolve_a_chave():
    assert tr("Preview") == "Preview"
    assert tr("No file selected") == "No file selected"


# --------------------------------------------------------- painel importação
def test_importacao_preview_mostra_mapeamento_e_contagens_ptpt(qapp, doc, dados):
    painel = PainelImportacao()
    painel.adicionar_ficheiros([_amostra(dados)])
    info = painel.rotulo_info.text()
    assert "89 points" in info and "0 rejected rows" in info
    assert "';'" in info and "','" in info  # delimitador e decimal detectados
    assert "{'numero': 0, 'codigo': 1, 'x': 2, 'y': 3, 'z': 4}" in info
    assert painel.tabela.rowCount() == 50  # limite de pré-visualização
    assert painel.tabela.item(0, 0).text() == "P001"


def test_importacao_override_do_delimitador_rele_a_preview(qapp, doc, dados):
    painel = PainelImportacao()
    painel.adicionar_ficheiros([_amostra(dados)])
    painel.combo_delimitador.setCurrentText(",")
    assert "0 points" in painel.rotulo_info.text()
    painel.combo_delimitador.setCurrentText(";")
    assert "89 points" in painel.rotulo_info.text()


def test_importacao_rejeicoes_visiveis_antes_de_aceitar(qapp, doc, dados, tmp_path):
    lixo = tmp_path / "lixo.csv"
    lixo.write_text(
        "ponto;codigo;X;Y;cota\nA;EIX;1;2;3\nB;EIX;xx;4;5\nC;;7;8\n",
        encoding="utf-8")
    painel = PainelImportacao()
    painel.adicionar_ficheiros([str(lixo)])
    rejeicoes = painel.rotulo_rejeicoes.text()
    assert "Rejected rows (2)" in rejeicoes
    assert "line 3" in rejeicoes and "line 4" in rejeicoes
    assert "valor não numérico" in rejeicoes
    assert painel.tabela.rowCount() == 1  # só o ponto A


def test_importacao_accept_cria_levantamentos_com_rejeitadas(qapp, doc, dados, tmp_path):
    lixo = tmp_path / "lixo.csv"
    lixo.write_text(
        "ponto;codigo;X;Y;cota\nA;EIX;1;2;3\nB;EIX;xx;4;5\n", encoding="utf-8")
    painel = PainelImportacao()
    painel.adicionar_ficheiros([_amostra(dados), str(lixo)])
    assert painel.accept() is True
    levs = [o for o in doc.Objects
            if getattr(getattr(o, "Proxy", None), "Type", "") ==
            "Topografia::Levantamento"]
    assert len(levs) == 2
    por_label = {o.Label: o for o in levs}
    assert len(por_label["levantamento_ptpt_v2"].Model) == 89
    assert len(por_label["levantamento_ptpt_v2"].Rejeitadas) == 0
    assert len(por_label["lixo"].Model) == 1
    assert len(por_label["lixo"].Rejeitadas) == 1


def test_importacao_ficheiro_desaparecido_nao_rebenta(qapp, doc, tmp_path):
    painel = PainelImportacao()
    painel.adicionar_ficheiros([str(tmp_path / "nao_existe.csv")])
    assert "nao_existe.csv" in painel.rotulo_info.text()
    assert painel.accept() is False  # nada importável, sem excepção


# ------------------------------------------------------------------ painel TIN
def test_tin_codigos_dos_e_precodigo_por_chaves(qapp, doc, dados):
    lev = _levantamento(doc, dados)
    assert codigos_dos([lev])["EIX"] == 11
    painel = PainelTIN(doc)
    from PySide import QtCore

    painel.lista.item(0).setCheckState(QtCore.Qt.Checked)
    marcados = sorted(c for c, cx in painel.caixas_codigo.items() if cx.isChecked())
    desmarcados = sorted(c for c, cx in painel.caixas_codigo.items()
                         if not cx.isChecked())
    assert marcados == ["EIX", "EP_D", "EP_E", "LE_D", "LE_E", "TAL_D", "TAL_E"]
    assert desmarcados == ["ARV", "CER", "GRE", "MURO"]


def test_tin_accept_impoe_breaklines_escolhidas(qapp, doc, dados):
    lev = _levantamento(doc, dados)
    painel = PainelTIN(doc)
    from PySide import QtCore

    painel.lista.item(0).setCheckState(QtCore.Qt.Checked)
    painel.caixas_codigo["MURO"].setChecked(True)  # acrescento manual
    painel.caixas_codigo["TAL_D"].setChecked(False)
    assert painel.accept() is True
    tin = [o for o in doc.Objects if hasattr(o, "ModeloTIN") and o.ModeloTIN][0]
    assert sorted(tin.CodigosBreakline) == [
        "EIX", "EP_D", "EP_E", "LE_D", "LE_E", "MURO", "TAL_E"]
    assert len(tin.ModeloTIN["arestas_impostas"]) > 0


# ---------------------------------------------------------- exportação LandXML
def test_export_landxml_multi_seleccao_gera_ficheiros_distintos(doc, dados, tmp_path):
    lev = _levantamento(doc, dados)
    tin = _tin(doc, lev)
    base = tmp_path / "exp"
    mensagens, erros = exportar_seleccao(str(base), [tin, lev])
    assert not erros and len(mensagens) == 2
    f_tin = tmp_path / "exp_TIN_tin.landxml"
    f_pts = tmp_path / "exp_Levantamento_pontos.landxml"
    assert f_tin.exists() and f_tin.stat().st_size > 0
    assert f_pts.exists() and f_pts.stat().st_size > 0
    assert "155 triangles" in mensagens[0] or "triangles" in mensagens[0]


def test_export_nome_ficheiro_saneia_o_rotulo(doc, dados):
    lev = _levantamento(doc, dados)
    lev.Label = "Lev campo 1 (2026)"
    nome = nome_ficheiro("/tmp/exp", lev)
    assert " " not in nome and "(" not in nome
    assert nome.endswith("_pontos.landxml")
    assert e_exportavel(lev) == "pontos"


# -------------------------------------------------------- painel terraplenagem
def test_terraplenagem_varredura_detecta_o_trio_por_propriedades(qapp, doc):
    t = doc.addObject("Mesh::FeaturePython", "T")
    t.addProperty("App::PropertyPythonObject", "ModeloTIN", "T", "").ModeloTIN = {}
    a = doc.addObject("App::FeaturePython", "A")
    a.addProperty("App::PropertyString", "AlignmentId", "A", "")
    a.addProperty("App::PropertyVectorList", "IPPoints", "A", "")
    p = doc.addObject("App::FeaturePython", "P")
    p.addProperty("App::PropertyString", "ProfileKind", "P", "")
    doc.recompute()
    tins, alinhamentos, perfis = candidatos(doc)
    assert [o.Name for o in tins] == ["T"]
    assert [o.Name for o in alinhamentos] == ["A"]
    assert [o.Name for o in perfis] == ["P"]


def test_terraplenagem_accept_cria_e_exporta_csv_e_png(qapp, doc, dados, tmp_path):
    pytest.importorskip(
        "freecad.Corridor_Road.v1.objects.obj_alignment",
        reason="CorridorRoad não disponível")
    import FreeCAD as App
    from freecad.Corridor_Road.objects.obj_project import (
        CorridorRoadProject,
        ensure_project_tree,
    )
    from freecad.Corridor_Road.v1.objects.obj_alignment import (
        create_sample_v1_alignment,
    )
    from freecad.Corridor_Road.v1.objects.obj_profile import create_sample_v1_profile

    lev = _levantamento(doc, dados)
    tin = _tin(doc, lev)
    project = doc.addObject("App::FeaturePython", "CorridorRoadProject")
    CorridorRoadProject(project)
    ensure_project_tree(project, include_references=False)
    alignment = create_sample_v1_alignment(doc, project=project)
    alignment.AlignmentId = "alignment:main"
    alignment.ElementIds = ["alignment:main:tangent:1"]
    alignment.ElementKinds = ["tangent"]
    alignment.StationStarts = [0.0]
    alignment.StationEnds = [400.0]
    alignment.ElementLengths = [400.0]
    alignment.XValueRows = ["0.0,400.0"]
    alignment.YValueRows = ["0.0,0.0"]
    alignment.IPPoints = [App.Vector(0, 0, 0), App.Vector(400, 0, 0)]
    alignment.TotalLength = 400.0
    doc.recompute()
    profile = create_sample_v1_profile(doc, project=project, alignment=alignment)
    doc.recompute()

    painel = PainelTerraplenagem(doc)
    assert painel.combo_tin.count() >= 1
    assert painel.combo_alinhamento.count() >= 1
    assert painel.combo_perfil.count() >= 1
    painel.combo_tin.setCurrentIndex(0)
    painel.combo_alinhamento.setCurrentIndex(0)
    painel.combo_perfil.setCurrentIndex(0)
    assert painel.criar() is True
    assert "estações=" in painel.objecto_criado.Estatisticas
    f_csv = tmp_path / "terr.csv"
    f_png = tmp_path / "terr.png"
    assert painel.exportar_csv(str(f_csv)) is True
    assert painel.exportar_grafico(str(f_png)) is True
    assert f_csv.exists() and f_csv.stat().st_size > 0
    assert f_png.exists() and f_png.stat().st_size > 0
