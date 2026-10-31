# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI do addon Topografia: workbench e comandos.

Só é carregado na GUI; todo o cálculo vive no pacote aplicacional
(``freecad.topografia``) e é testável em FreeCADCmd.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui

RAIZ = os.path.dirname(__file__)  # módulo normal: __file__ é fiável


def _doc():
    return App.ActiveDocument or App.newDocument("Topografia")


class CmdImportarLevantamento:
    """Importa CSV de pontos (ponto;codigo;X;Y;cota) com delimitador/decimal automáticos."""

    def GetResources(self):
        return {
            "MenuText": "Importar levantamento (CSV)",
            "ToolTip": "Importa pontos topográficos com código; cria o objecto Levantamento",
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "levantamento.svg"),
            "Accel": "T,L",
        }

    def IsActive(self):
        return True

    def Activated(self):
        from PySide import QtWidgets

        from freecad.topografia.csv_io import le_pontos
        from freecad.topografia.objetos.levantamento import definir_relatorio
        from freecad.topografia.objetos.levantamento import Levantamento

        caminhos, _ = QtWidgets.QFileDialog.getOpenFileNames(
            None, "Levantamento (CSV/TXT)", "", "CSV/TXT (*.csv *.txt *.asc);;Todos (*)")
        doc = _doc()
        for caminho in caminhos:
            relatorio = le_pontos(caminho)
            nome = os.path.splitext(os.path.basename(caminho))[0]
            obj = doc.addObject("Points::FeaturePython", "Levantamento")
            Levantamento(obj)
            definir_relatorio(obj, relatorio)
            doc.recompute()
            App.Console.PrintMessage(
                f"[Topografia] {nome}: {relatorio.resumo}\n")
            if relatorio.rejeitadas:
                App.Console.PrintWarning(
                    "Linhas rejeitadas: " + "; ".join(f"{n}: {m}" for n, m in relatorio.rejeitadas[:20]) + "\n")


class CmdCriarTIN:
    """Cria a TIN (Delaunay com breaklines) a partir dos levantamentos seleccionados."""

    def GetResources(self):
        return {
            "MenuText": "Criar TIN do terreno",
            "ToolTip": "Triangulação Delaunay com breaklines por código",
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "tin.svg"),
        }

    def IsActive(self):
        return bool(Gui.Selection.getSelection())

    def Activated(self):
        from freecad.topografia.objetos.tin import TIN

        seleccionados = [o for o in Gui.Selection.getSelection()
                         if getattr(o, "Proxy", None) and o.Proxy.Type == "Topografia::Levantamento"]
        if not seleccionados:
            App.Console.PrintError("[Topografia] seleccione um ou mais Levantamentos\n")
            return
        doc = _doc()
        obj = doc.addObject("Mesh::FeaturePython", "TIN")
        TIN(obj)
        obj.Levantamentos = seleccionados
        obj.CodigosBreakline = ["EIX"]
        doc.recompute()
        App.Console.PrintMessage(f"[Topografia] TIN: {obj.Estatisticas}\n")


class CmdCurvasDeNivel:
    """Curvas de nível paramétricas sobre a TIN seleccionada."""

    def GetResources(self):
        return {
            "MenuText": "Curvas de nível",
            "ToolTip": "Curvas principais/intercalares paramétricas sobre a TIN",
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "curvas.svg"),
        }

    def IsActive(self):
        sel = Gui.Selection.getSelection()
        return len(sel) == 1 and hasattr(sel[0], "Mesh")

    def Activated(self):
        from freecad.topografia.objetos.curvas import CurvasDeNivel

        doc = _doc()
        obj = doc.addObject("Part::FeaturePython", "Curvas")
        CurvasDeNivel(obj)
        obj.TIN = Gui.Selection.getSelection()[0]
        doc.recompute()
        App.Console.PrintMessage(f"[Topografia] {obj.Resumo}\n")


class CmdTerraplenagem:
    """Volumes corte/aterro por estações (requer Alinhamento+Perfil do CorridorRoad)."""

    def GetResources(self):
        return {
            "MenuText": "Terraplenagem (volumes e mass haul)",
            "ToolTip": "Cut/fill por áreas-médias com encontro de taludes na TIN",
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "terras.svg"),
        }

    def IsActive(self):
        return bool(Gui.Selection.getSelection())

    def Activated(self):
        from freecad.topografia.objetos.terraplenagem import Terraplenagem

        doc = _doc()
        obj = doc.addObject("App::FeaturePython", "Terraplenagem")
        Terraplenagem(obj)
        por_tipo = {}
        for o in Gui.Selection.getSelection():
            tipo = str(getattr(getattr(o, "Proxy", None), "Type", "") or "")
            if tipo == "Topografia::Levantamento":
                continue
            if "ModeloTIN" in o.PropertiesList:
                por_tipo["tin"] = o
            elif str(o.Name).startswith("V1Alignment") or "AlignmentId" in o.PropertiesList and "IPPoints" in o.PropertiesList:
                por_tipo["alinhamento"] = o
            elif str(o.Name).startswith("V1Profile") or "ProfileKind" in o.PropertiesList:
                por_tipo["perfil"] = o
        if "tin" in por_tipo:
            obj.TIN = por_tipo["tin"]
        if "alinhamento" in por_tipo:
            obj.Alinhamento = por_tipo["alinhamento"]
        if "perfil" in por_tipo:
            obj.Perfil = por_tipo["perfil"]
        doc.recompute()
        App.Console.PrintMessage(f"[Topografia] {obj.Estatisticas}\n")


class CmdExportarLandXML:
    """Exporta a TIN e os pontos seleccionados para LandXML 1.2."""

    def GetResources(self):
        return {
            "MenuText": "Exportar LandXML",
            "ToolTip": "Superfície TIN e/ou pontos em LandXML 1.2 (Civil 3D)",
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "landxml.svg"),
        }

    def IsActive(self):
        return bool(Gui.Selection.getSelection())

    def Activated(self):
        from PySide import QtWidgets

        from freecad.topografia.landxml_export import exporta_pontos_landxml, exporta_tin_landxml

        caminho, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, "Exportar LandXML", "", "LandXML (*.xml)")
        if not caminho:
            return
        for o in Gui.Selection.getSelection():
            if "ModeloTIN" in o.PropertiesList and o.ModeloTIN:
                n = exporta_tin_landxml(o.ModeloTIN, caminho)
                App.Console.PrintMessage(f"[Topografia] {o.Label}: {n} triângulos -> {caminho}\n")
            elif getattr(getattr(o, "Proxy", None), "Type", "") == "Topografia::Levantamento":
                n = exporta_pontos_landxml(o, caminho)
                App.Console.PrintMessage(f"[Topografia] {o.Label}: {n} pontos -> {caminho}\n")


class TopografiaWorkbench(Gui.Workbench):
    """Workbench de base topográfica para projectos de estradas."""

    MenuText = "Topografia"
    ToolTip = "Levantamentos, TIN com breaklines, curvas de nível e terraplenagem"
    Icon = os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "topografia.svg")

    def Initialize(self):
        self.appendToolbar("Topografia", [
            "Topografia_ImportarLevantamento",
            "Topografia_CriarTIN",
            "Topografia_CurvasDeNivel",
            "Topografia_Terraplenagem",
            "Topografia_ExportarLandXML",
        ])
        self.appendMenu("Topografia", [
            "Topografia_ImportarLevantamento",
            "Topografia_CriarTIN",
            "Topografia_CurvasDeNivel",
            "Topografia_Terraplenagem",
            "Topografia_ExportarLandXML",
        ])

    def ContextMenu(self, recipient):
        self.appendContextMenu("Topografia", ["Topografia_ExportarLandXML"])


Gui.addCommand("Topografia_ImportarLevantamento", CmdImportarLevantamento())
Gui.addCommand("Topografia_CriarTIN", CmdCriarTIN())
Gui.addCommand("Topografia_CurvasDeNivel", CmdCurvasDeNivel())
Gui.addCommand("Topografia_Terraplenagem", CmdTerraplenagem())
Gui.addCommand("Topografia_ExportarLandXML", CmdExportarLandXML())
Gui.addWorkbench(TopografiaWorkbench())
