# SPDX-License-Identifier: LGPL-2.1-or-later
"""Painel de importação de levantamentos (CSV/TXT) com pré-visualização.

A pré-visualização usa o próprio motor (:func:`le_pontos`) — não uma
réplica — pelo que o utilizador vê o mapeamento detectado, as contagens e
as linhas rejeitadas (com motivo) ANTES de confirmar, e pode sobrepor
delimitador, decimal, cabeçalho e colunas manualmente.
"""
import os

import FreeCAD as App

from ..i18n import tr
from . import Painel

AUTO = "Auto"
_LIMITE_PREVIEW = 50
_LIMITE_REJEICOES = 20


def _novo_documento():
    return App.ActiveDocument or App.newDocument("Topografia")


class PainelImportacao(Painel):
    """Importa um ou mais ficheiros de pontos, um Levantamento por ficheiro."""

    def __init__(self):
        self.form = self._criar_ui()
        self._ligar_sinais()

    # ------------------------------------------------------------------ UI
    def _criar_ui(self):
        from PySide import QtCore, QtWidgets

        widget = QtWidgets.QWidget()
        raiz = QtWidgets.QVBoxLayout(widget)

        topo = QtWidgets.QHBoxLayout()
        # ficheiros
        grupo_ficheiros = QtWidgets.QGroupBox(tr("Files"))
        col = QtWidgets.QVBoxLayout(grupo_ficheiros)
        self.lista = QtWidgets.QListWidget()
        self.lista.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        botoes = QtWidgets.QHBoxLayout()
        self.botao_adicionar = QtWidgets.QPushButton(tr("Add…"))
        self.botao_remover = QtWidgets.QPushButton(tr("Remove"))
        botoes.addWidget(self.botao_adicionar)
        botoes.addWidget(self.botao_remover)
        col.addWidget(self.lista)
        col.addLayout(botoes)

        # opções
        grupo_opcoes = QtWidgets.QGroupBox(tr("Options"))
        formulario = QtWidgets.QFormLayout(grupo_opcoes)
        self.combo_delimitador = QtWidgets.QComboBox()
        self.combo_delimitador.addItems(
            [AUTO, ";", ",", tr("Tab"), "|", tr("Space")])
        self.combo_decimal = QtWidgets.QComboBox()
        self.combo_decimal.addItems([AUTO, ",", "."])
        self.combo_cabecalho = QtWidgets.QComboBox()
        self.combo_cabecalho.addItems([AUTO, tr("Yes"), tr("No")])
        formulario.addRow(tr("Delimiter:"), self.combo_delimitador)
        formulario.addRow(tr("Decimal separator:"), self.combo_decimal)
        formulario.addRow(tr("Header row:"), self.combo_cabecalho)

        grupo_colunas = QtWidgets.QGroupBox(tr("Columns (1-based; Auto = detected)"))
        grelha = QtWidgets.QGridLayout(grupo_colunas)
        self.combos_coluna = {}
        for i, (chave, rotulo) in enumerate([
            ("numero", tr("Point")), ("codigo", tr("Code")), ("x", "E"),
            ("y", "N"), ("z", tr("Elevation")),
        ]):
            combo = QtWidgets.QComboBox()
            combo.addItems([AUTO] + [str(n) for n in range(1, 13)])
            self.combos_coluna[chave] = combo
            grelha.addWidget(QtWidgets.QLabel(rotulo), i // 3, (i % 3) * 2)
            grelha.addWidget(combo, i // 3, (i % 3) * 2 + 1)

        topo.addWidget(grupo_ficheiros)
        topo.addWidget(grupo_opcoes)
        topo.addWidget(grupo_colunas)

        # pré-visualização
        grupo_preview = QtWidgets.QGroupBox(tr("Preview"))
        col = QtWidgets.QVBoxLayout(grupo_preview)
        self.rotulo_info = QtWidgets.QLabel(tr("No file selected"))
        self.rotulo_info.setWordWrap(True)
        self.tabela = QtWidgets.QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(
            [tr("Point"), tr("Code"), "E", "N", tr("Elevation")])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self.rotulo_rejeicoes = QtWidgets.QLabel("")
        self.rotulo_rejeicoes.setWordWrap(True)
        col.addWidget(self.rotulo_info)
        col.addWidget(self.tabela)
        col.addWidget(self.rotulo_rejeicoes)

        raiz.addLayout(topo)
        raiz.addWidget(grupo_preview)
        return widget

    def _ligar_sinais(self):
        self.botao_adicionar.clicked.connect(self.adicionar_ficheiros)
        self.botao_remover.clicked.connect(self.remover_seleccionados)
        # a pré-visualização segue o item CORRENTE (clique simples), não a
        # selecção múltipla (que serve para remover)
        self.lista.currentItemChanged.connect(lambda *_: self._relê())
        for combo in ([self.combo_delimitador, self.combo_decimal,
                       self.combo_cabecalho] + list(self.combos_coluna.values())):
            combo.currentIndexChanged.connect(self._relê)

    # ------------------------------------------------------------ ficheiros
    def adicionar_ficheiros(self, caminhos=None):
        """Adiciona *caminhos* à lista (sem diálogo) ou abre o selector."""
        if caminhos is None:
            from PySide import QtWidgets
            caminhos, _ = QtWidgets.QFileDialog.getOpenFileNames(
                None, tr("Survey files (CSV/TXT)"), "",
                "CSV/TXT (*.csv *.txt *.asc);;" + tr("All files") + " (*)")
        existentes = {self.lista.item(i).data(0x0100)  # QtCore.Qt.UserRole
                      for i in range(self.lista.count())}
        for caminho in caminhos:
            if caminho and caminho not in existentes:
                from PySide import QtCore, QtWidgets
                item = QtWidgets.QListWidgetItem(os.path.basename(caminho))
                item.setData(QtCore.Qt.UserRole, caminho)
                self.lista.addItem(item)
        if self.lista.count() and self.lista.currentRow() < 0:
            self.lista.setCurrentRow(0)
        self._relê()

    def remover_seleccionados(self):
        for item in self.lista.selectedItems():
            self.lista.takeItem(self.lista.row(item))
        self._relê()

    def _caminho_actual(self):
        item = self.lista.currentItem()
        return item.data(0x0100) if item else None

    # -------------------------------------------------------------- opções
    def _opcoes(self):
        """Constrói os kwargs de le_pontos a partir dos combos (Auto=None)."""
        mapa_teclas = {";": ";", ",": ",", "|": "|",
                       tr("Tab"): "\t", tr("Space"): " "}
        delimitador = mapa_teclas.get(self.combo_delimitador.currentText())
        decimal = None
        if self.combo_decimal.currentText() != AUTO:
            decimal = self.combo_decimal.currentText()
        cabecalho = {AUTO: None, tr("Yes"): True, tr("No"): False}[
            self.combo_cabecalho.currentText()]
        mapeamento = {}
        for chave, combo in self.combos_coluna.items():
            if combo.currentText() != AUTO:
                mapeamento[chave] = int(combo.currentText()) - 1
        return {
            "delimitador": delimitador,
            "decimal": decimal,
            "tem_cabecalho": cabecalho,
            "mapeamento": mapeamento or None,
        }

    # ---------------------------------------------------------- pré-visual.
    def _relê(self):
        """Relê o ficheiro seleccionado com as opções actuais e repinta."""
        from PySide import QtWidgets

        caminho = self._caminho_actual()
        self.tabela.setRowCount(0)
        self.rotulo_rejeicoes.setText("")
        if not caminho:
            self.rotulo_info.setText(tr("No file selected"))
            return
        from ..csv_io import le_pontos
        try:
            rel = le_pontos(caminho, **self._opcoes())
        except (ValueError, OSError) as exc:
            self.rotulo_info.setText(f"{caminho}: {exc}")
            return
        self._ultimo_relatorio = rel
        # dicas nos combos Auto com o que foi detectado
        self.combo_delimitador.setToolTip(
            f"{tr('Detected')}: '{rel.delimitador}'")
        self.combo_decimal.setToolTip(f"{tr('Detected')}: '{rel.decimal}'")
        self.rotulo_info.setText(
            f"{os.path.basename(caminho)} — {tr('mapping')} {rel.mapeamento} · "
            f"'{rel.delimitador}' · {tr('decimal')} '{rel.decimal}' · "
            f"{len(rel.pontos)} {tr('points')} · "
            f"{len(rel.rejeitadas)} {tr('rejected rows')}")
        for ponto in rel.pontos[:_LIMITE_PREVIEW]:
            n = self.tabela.rowCount()
            self.tabela.insertRow(n)
            for coluna, valor in enumerate(
                    [ponto.numero, ponto.codigo, f"{ponto.x:.3f}",
                     f"{ponto.y:.3f}", f"{ponto.z:.3f}"]):
                self.tabela.setItem(n, coluna, QtWidgets.QTableWidgetItem(valor))
        if rel.rejeitadas:
            amostra = ";  ".join(
                f"{tr('line')} {n}: {motivo}"
                for n, motivo in rel.rejeitadas[:_LIMITE_REJEICOES])
            self.rotulo_rejeicoes.setText(
                f"{tr('Rejected rows')} ({len(rel.rejeitadas)}): {amostra}")

    # --------------------------------------------------------------- acção
    def accept(self):
        caminhos = [self.lista.item(i).data(0x0100)
                    for i in range(self.lista.count())]
        if not caminhos:
            App.Console.PrintError(
                tr("[Topografia] no files to import") + "\n")
            return False
        from ..csv_io import le_pontos
        from ..objetos.levantamento import Levantamento, definir_relatorio
        doc = _novo_documento()
        opcoes = self._opcoes()
        importados = 0
        for caminho in caminhos:
            try:
                rel = le_pontos(caminho, **opcoes)
            except (ValueError, OSError) as exc:
                App.Console.PrintError(f"{caminho}: {exc}\n")
                continue
            if not rel.pontos:
                App.Console.PrintError(
                    f"{caminho}: {tr('no importable points')} "
                    f"({len(rel.rejeitadas)} {tr('rejected rows')})\n")
                continue
            nome = os.path.splitext(os.path.basename(caminho))[0]
            obj = doc.addObject("Points::FeaturePython", "Levantamento")
            Levantamento(obj)
            definir_relatorio(obj, rel)
            obj.Label = nome
            importados += 1
            App.Console.PrintMessage(
                f"[Topografia] {nome}: {rel.resumo}\n")
        if not importados:
            return False
        doc.recompute()
        import FreeCADGui as Gui
        Gui.Control.closeDialog()
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass  # headless: sem vista activa
        return True
