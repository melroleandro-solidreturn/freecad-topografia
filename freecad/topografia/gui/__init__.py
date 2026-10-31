# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pacote GUI do addon Topografia.

Painéis de tarefa e auxiliares de interface. Toda a lógica de cálculo vive
no pacote aplicacional (:mod:`freecad.topografia`) e continua testável em
``FreeCADCmd``; os módulos deste pacote importam ``FreeCADGui`` apenas
dentro dos métodos que o exigem, pelo que as classes são instanciáveis
headless (Qt offscreen) para teste.
"""


class Painel:
    """Base comum dos painéis de tarefa (padrão TaskPanel do FreeCAD).

    Subclasses definem ``self.form`` (widget Qt) e os métodos de acção; o
    FreeCAD chama ``accept``/``reject`` nos botões OK/Cancelar do diálogo.
    """

    def __init__(self, widget=None):
        self.form = widget

    def accept(self):
        return True

    def reject(self):
        return True

    def clicked(self, index):
        pass

    def open(self):
        pass

    def helpRequested(self):
        pass

    def needsFullSpace(self):
        return True

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def isAllowedAlterDocument(self):
        return True
