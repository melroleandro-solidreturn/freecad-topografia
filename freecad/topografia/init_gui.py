# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI do addon Topografia: workbench e comandos.

Só é carregado na GUI; todo o cálculo vive no pacote aplicacional
(``freecad.topografia``) e é testável em FreeCADCmd.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui

from freecad.topografia.i18n import tr

RAIZ = os.path.dirname(__file__)  # módulo normal: __file__ é fiável


def _doc():
    return App.ActiveDocument or App.newDocument("Topografia")


class CmdImportarLevantamento:
    """Importa CSV de pontos (ponto;codigo;X;Y;cota) com delimitador/decimal automáticos."""

    def GetResources(self):
        return {
            "MenuText": tr("Import survey (CSV)"),
            "ToolTip": tr("Import coded survey points (CSV/TXT); creates a Levantamento object"),
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "levantamento.svg"),
            "Accel": "T,L",
        }

    def IsActive(self):
        return True

    def Activated(self):
        from freecad.topografia.gui.painel_importacao import PainelImportacao

        Gui.Control.showDialog(PainelImportacao())


class CmdCriarTIN:
    """Cria a TIN (Delaunay com breaklines) a partir dos levantamentos seleccionados."""

    def GetResources(self):
        return {
            "MenuText": tr("Create terrain TIN"),
            "ToolTip": tr("Delaunay triangulation with breaklines by code"),
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "tin.svg"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from freecad.topografia.gui.painel_tin import PainelTIN

        Gui.Control.showDialog(PainelTIN())


class CmdCurvasDeNivel:
    """Curvas de nível paramétricas sobre a TIN seleccionada."""

    def GetResources(self):
        return {
            "MenuText": tr("Contour lines"),
            "ToolTip": tr("Parametric major/minor contours over the TIN"),
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
            "MenuText": tr("Earthworks (volumes and mass haul)"),
            "ToolTip": tr("Cut/fill by average end area with slope-to-terrain daylight"),
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "terras.svg"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from freecad.topografia.gui.painel_terraplenagem import PainelTerraplenagem

        Gui.Control.showDialog(PainelTerraplenagem())


class CmdExportarLandXML:
    """Exporta a TIN e os pontos seleccionados para LandXML 1.2."""

    def GetResources(self):
        return {
            "MenuText": tr("Export LandXML"),
            "ToolTip": tr("TIN surface and/or points as LandXML 1.2 (Civil 3D)"),
            "Pixmap": os.path.join(RAIZ, "freecad", "topografia", "resources", "icons", "landxml.svg"),
        }

    def IsActive(self):
        return bool(Gui.Selection.getSelection())

    def Activated(self):
        from PySide import QtWidgets

        from freecad.topografia.gui.exportar_landxml import e_exportavel, exportar_seleccao

        objectos = [o for o in Gui.Selection.getSelection() if e_exportavel(o)]
        if not objectos:
            App.Console.PrintWarning(
                tr("[Topografia] select a TIN or a survey") + "\n")
            return
        titulo = ("Export LandXML" if len(objectos) == 1
                  else "Export LandXML (one file per object)")
        base, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, titulo, "", "LandXML (*.landxml)")
        if not base:
            return
        mensagens, erros = exportar_seleccao(base, objectos)
        for m in mensagens:
            App.Console.PrintMessage(m + "\n")
        for e in erros:
            App.Console.PrintWarning(e + "\n")


class TopografiaWorkbench(Gui.Workbench):
    """Workbench de base topográfica para projectos de estradas."""

    MenuText = "Topografia"
    ToolTip = tr("Surveys, breakline TIN, contour lines and earthworks")
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
