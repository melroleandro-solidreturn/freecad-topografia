# SPDX-License-Identifier: LGPL-2.1-or-later
"""Painel de criação da TIN do terreno.

Substitui o ``CodigosBreakline = ["EIX"]`` fixo do comando: os códigos de
breakline são escolhidos na interface, pré-marcados pelo motor de chaves
de descrição (:func:`freecad.topografia.chaves.classifica`).
"""
import FreeCAD as App

from .. import chaves
from ..i18n import tr
from . import Painel


def codigos_dos(levantamentos):
    """Contagem de códigos nos *levantamentos* (função pura, testável)."""
    contagem = {}
    for obj in levantamentos:
        for ponto in obj.Model.values():
            codigo = ponto.get("Codigo", "")
            if codigo:
                contagem[codigo] = contagem.get(codigo, 0) + 1
    return contagem


def _levantamentos_do_documento(doc):
    return [o for o in doc.Objects
            if getattr(getattr(o, "Proxy", None), "Type", "") ==
            "Topografia::Levantamento"]


class PainelTIN(Painel):
    """Cria a TIN a partir dos levantamentos marcados e códigos escolhidos."""

    def __init__(self, doc=None):
        self.doc = doc or App.ActiveDocument or App.newDocument("Topografia")
        self.form = self._criar_ui()
        self._ligar_sinais()
        self._pre_seleccionar()

    # ------------------------------------------------------------------ UI
    def _criar_ui(self):
        from PySide import QtCore, QtWidgets

        widget = QtWidgets.QWidget()
        raiz = QtWidgets.QVBoxLayout(widget)

        topo = QtWidgets.QHBoxLayout()
        grupo_inquiridos = QtWidgets.QGroupBox(tr("Surveys"))
        col = QtWidgets.QVBoxLayout(grupo_inquiridos)
        self.lista = QtWidgets.QListWidget()
        for obj in _levantamentos_do_documento(self.doc):
            item = QtWidgets.QListWidgetItem(obj.Label)
            item.setData(QtCore.Qt.UserRole, obj.Name)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.lista.addItem(item)
        col.addWidget(self.lista)

        grupo_breaklines = QtWidgets.QGroupBox(tr("Breaklines (by code)"))
        self.grelha_codigos = QtWidgets.QGridLayout(grupo_breaklines)
        self.rotulo_sem_codigos = QtWidgets.QLabel(
            tr("Check a survey to list its codes"))
        self.grelha_codigos.addWidget(self.rotulo_sem_codigos, 0, 0)

        topo.addWidget(grupo_inquiridos)
        topo.addWidget(grupo_breaklines)

        parametros = QtWidgets.QFormLayout()
        self.campo_densificacao = QtWidgets.QDoubleSpinBox()
        self.campo_densificacao.setRange(0.0, 1000.0)
        self.campo_densificacao.setDecimals(2)
        self.campo_densificacao.setSuffix(" m")
        self.campo_densificacao.setSpecialValueText(tr("0 = automatic"))
        self.campo_aresta = QtWidgets.QDoubleSpinBox()
        self.campo_aresta.setRange(0.0, 10000.0)
        self.campo_aresta.setDecimals(2)
        self.campo_aresta.setSuffix(" m")
        self.campo_aresta.setSpecialValueText(tr("0 = no limit"))
        parametros.addRow(tr("Refinement step:"), self.campo_densificacao)
        parametros.addRow(tr("Maximum edge:"), self.campo_aresta)

        raiz.addLayout(topo)
        raiz.addLayout(parametros)
        return widget

    def _ligar_sinais(self):
        self.lista.itemChanged.connect(lambda _item: self._actualiza_codigos())

    def _pre_seleccionar(self):
        """Marca os levantamentos presentemente seleccionados na GUI."""
        from PySide import QtCore
        try:
            import FreeCADGui as Gui
            seleccionados = {o.Name for o in Gui.Selection.getSelection()}
        except Exception:
            seleccionados = set()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.data(0x0100) in seleccionados:
                item.setCheckState(QtCore.Qt.Checked)
        self._actualiza_codigos()

    # ------------------------------------------------------------ códigos
    def _levantamentos_marcados(self):
        from PySide import QtCore

        marcados = []
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                marcados.append(self.doc.getObject(item.data(0x0100)))
        return marcados

    def _actualiza_codigos(self):
        """Repinta as checkboxes de código com a pré-marcação das chaves."""
        from PySide import QtCore, QtWidgets

        while self.grelha_codigos.count():
            item = self.grelha_codigos.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.caixas_codigo = {}
        contagem = codigos_dos(self._levantamentos_marcados())
        if not contagem:
            self.grelha_codigos.addWidget(
                QtWidgets.QLabel(tr("Check a survey to list its codes")), 0, 0)
            return
        for i, (codigo, n) in enumerate(sorted(contagem.items())):
            caixa = QtWidgets.QCheckBox(f"{codigo} ({n})")
            caixa.setChecked(chaves.classifica(codigo)["breakline"])
            self.caixas_codigo[codigo] = caixa
            self.grelha_codigos.addWidget(caixa, i // 3, i % 3)

    # --------------------------------------------------------------- acção
    def accept(self):
        marcados = self._levantamentos_marcados()
        if not marcados:
            App.Console.PrintError(
                tr("[Topografia] check at least one survey") + "\n")
            return False
        codigos = [c for c, caixa in self.caixas_codigo.items() if caixa.isChecked()]
        from ..objetos.tin import TIN
        obj = self.doc.addObject("Mesh::FeaturePython", "TIN")
        TIN(obj)
        obj.Levantamentos = marcados
        obj.CodigosBreakline = codigos
        obj.Densificacao = self.campo_densificacao.value()
        obj.ArestaMaxima = self.campo_aresta.value()
        self.doc.recompute()
        App.Console.PrintMessage(f"[Topografia] TIN: {obj.Estatisticas}\n")
        import FreeCADGui as Gui
        Gui.Control.closeDialog()
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass  # headless: sem vista activa
        return True
