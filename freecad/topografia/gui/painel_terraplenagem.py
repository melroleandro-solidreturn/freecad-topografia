# SPDX-License-Identifier: LGPL-2.1-or-later
"""Painel de terraplenagem (corte/aterro por estações + mass haul).

A detecção das entradas é uma varredura do documento por propriedades
(funções puras, testáveis): TIN = objecto com ``ModeloTIN``; Alinhamento =
``AlignmentId`` + ``IPPoints`` (CorridorRoad); Perfil = ``ProfileKind``.
As exportações chamam as funções já existentes do módulo de objectos.
"""
import FreeCAD as App

from ..i18n import tr
from . import Painel


def e_tin(obj):
    return "ModeloTIN" in obj.PropertiesList


def e_alinhamento(obj):
    props = obj.PropertiesList
    return "AlignmentId" in props and "IPPoints" in props


def e_perfil(obj):
    return "ProfileKind" in obj.PropertiesList


def candidatos(doc):
    """Devolve (tins, alinhamentos, perfis) por varredura das propriedades."""
    tins = [o for o in doc.Objects if e_tin(o)]
    alinhamentos = [o for o in doc.Objects if e_alinhamento(o)]
    perfis = [o for o in doc.Objects if e_perfil(o) and not e_alinhamento(o)]
    return tins, alinhamentos, perfis


def corridorroad_disponivel():
    try:
        from freecad.Corridor_Road.v1.services.evaluation import (  # noqa: F401
            alignment_evaluation_service,
        )
        return True
    except Exception:
        return False


class PainelTerraplenagem(Painel):
    """Cria o objecto Terraplenagem e exporta CSV / gráfico de mass haul."""

    def __init__(self, doc=None):
        self.doc = doc or App.ActiveDocument or App.newDocument("Topografia")
        self.objecto_criado = None
        self.form = self._criar_ui()
        self._ligar_sinais()
        self._pre_seleccionar()

    # ------------------------------------------------------------------ UI
    def _criar_ui(self):
        from PySide import QtWidgets

        widget = QtWidgets.QWidget()
        raiz = QtWidgets.QVBoxLayout(widget)

        entradas = QtWidgets.QFormLayout()
        self.combo_tin = QtWidgets.QComboBox()
        self.combo_alinhamento = QtWidgets.QComboBox()
        self.combo_perfil = QtWidgets.QComboBox()
        entradas.addRow(tr("Terrain (TIN):"), self.combo_tin)
        entradas.addRow(tr("Alignment:"), self.combo_alinhamento)
        entradas.addRow(tr("Profile:"), self.combo_perfil)

        estacoes = QtWidgets.QFormLayout()
        self.campo_inicio = QtWidgets.QDoubleSpinBox()
        self.campo_inicio.setRange(0.0, 1e7)
        self.campo_fim = QtWidgets.QDoubleSpinBox()
        self.campo_fim.setRange(0.0, 1e7)
        self.campo_fim.setValue(0.0)
        self.campo_fim.setSpecialValueText(tr("0 = to the end"))
        self.campo_espacamento = QtWidgets.QDoubleSpinBox()
        self.campo_espacamento.setRange(0.1, 500.0)
        self.campo_espacamento.setValue(20.0)
        self.campo_espacamento.setSuffix(" m")
        estacoes.addRow(tr("Start station:"), self.campo_inicio)
        estacoes.addRow(tr("End station:"), self.campo_fim)
        estacoes.addRow(tr("Station spacing:"), self.campo_espacamento)

        self.rotulo_aviso = QtWidgets.QLabel("")
        self.rotulo_aviso.setWordWrap(True)
        self.rotulo_seccao = QtWidgets.QLabel(tr(
            "Section parameters are edited in the property editor "
            "(lane width, slopes, pavement…)"))
        self.rotulo_seccao.setWordWrap(True)

        botoes = QtWidgets.QHBoxLayout()
        self.botao_criar = QtWidgets.QPushButton(tr("Create earthworks"))
        self.botao_csv = QtWidgets.QPushButton(tr("Export CSV"))
        self.botao_grafico = QtWidgets.QPushButton(tr("Mass haul chart"))
        self.botao_csv.setEnabled(False)
        self.botao_grafico.setEnabled(False)
        botoes.addWidget(self.botao_criar)
        botoes.addWidget(self.botao_csv)
        botoes.addWidget(self.botao_grafico)
        botoes.addStretch()

        raiz.addLayout(entradas)
        raiz.addLayout(estacoes)
        raiz.addWidget(self.rotulo_seccao)
        raiz.addWidget(self.rotulo_aviso)
        raiz.addLayout(botoes)

        self._povoar_combos()
        if not corridorroad_disponivel():
            self.rotulo_aviso.setText(tr(
                "CorridorRoad is not installed: alignment and profile "
                "objects cannot be evaluated."))
            for combo in (self.combo_tin, self.combo_alinhamento,
                          self.combo_perfil, self.botao_criar):
                combo.setEnabled(False)
        return widget

    def _povoar_combos(self):
        from PySide import QtCore

        self._objectos = {}
        tins, alinhamentos, perfis = candidatos(self.doc)
        for combo, lista in ((self.combo_tin, tins),
                             (self.combo_alinhamento, alinhamentos),
                             (self.combo_perfil, perfis)):
            combo.clear()
            for obj in lista:
                combo.addItem(obj.Label, obj.Name)
            self._objectos[combo.objectName()] = lista

    def _ligar_sinais(self):
        self.botao_criar.clicked.connect(lambda: self.criar())
        self.botao_csv.clicked.connect(
            lambda: self.exportar_csv(None))
        self.botao_grafico.clicked.connect(
            lambda: self.exportar_grafico(None))

    def _pre_seleccionar(self):
        try:
            import FreeCADGui as Gui
            seleccionados = {o.Name for o in Gui.Selection.getSelection()}
        except Exception:
            seleccionados = set()
        for combo in (self.combo_tin, self.combo_alinhamento, self.combo_perfil):
            for i in range(combo.count()):
                if combo.itemData(i) in seleccionados:
                    combo.setCurrentIndex(i)
                    break

    # ------------------------------------------------------------ helpers
    def _objecto(self, combo):
        nome = combo.currentData()
        return self.doc.getObject(nome) if nome else None

    # --------------------------------------------------------------- acção
    def criar(self):
        """Cria o objecto Terraplenagem (sem fechar o painel)."""
        tin = self._objecto(self.combo_tin)
        alinhamento = self._objecto(self.combo_alinhamento)
        perfil = self._objecto(self.combo_perfil)
        if not (tin and alinhamento and perfil):
            App.Console.PrintError(
                tr("[Topografia] terrain, alignment and profile are "
                   "all required") + "\n")
            return False
        from ..objetos.terraplenagem import Terraplenagem
        obj = self.doc.addObject("App::FeaturePython", "Terraplenagem")
        Terraplenagem(obj)
        obj.TIN = tin
        obj.Alinhamento = alinhamento
        obj.Perfil = perfil
        obj.EstacaoInicio = self.campo_inicio.value()
        obj.EstacaoFim = self.campo_fim.value()
        obj.IntervaloEstacoes = self.campo_espacamento.value()
        self.doc.recompute()
        self.objecto_criado = obj
        self.botao_csv.setEnabled(bool(obj.Resultados))
        self.botao_grafico.setEnabled(bool(obj.Resultados))
        App.Console.PrintMessage(f"[Topografia] {obj.Estatisticas}\n")
        return bool(obj.Resultados)

    def accept(self):
        if self.objecto_criado is None and not self.criar():
            return False
        import FreeCADGui as Gui
        Gui.Control.closeDialog()
        return True

    # ---------------------------------------------------------- exportações
    def exportar_csv(self, caminho=None):
        if not (self.objecto_criado and self.objecto_criado.Resultados):
            return False
        if caminho is None:
            from PySide import QtWidgets
            caminho, _ = QtWidgets.QFileDialog.getSaveFileName(
                None, tr("Export earthworks CSV"), "",
                "CSV (*.csv)")
            if not caminho:
                return False
        from ..objetos.terraplenagem import exportar_csv as _exportar
        _exportar(self.objecto_criado.Resultados, caminho)
        App.Console.PrintMessage(f"[Topografia] {caminho}\n")
        return True

    def exportar_grafico(self, caminho=None):
        if not (self.objecto_criado and self.objecto_criado.Resultados):
            return False
        if caminho is None:
            from PySide import QtWidgets
            caminho, _ = QtWidgets.QFileDialog.getSaveFileName(
                None, tr("Export mass haul chart"), "",
                "PNG (*.png)")
            if not caminho:
                return False
        from ..objetos.terraplenagem import grafico_mass_haul
        grafico_mass_haul(self.objecto_criado.Resultados, caminho)
        App.Console.PrintMessage(f"[Topografia] {caminho}\n")
        return True
