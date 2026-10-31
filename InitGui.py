# SPDX-License-Identifier: LGPL-2.1-or-later
"""InitGui do addon Topografia (ponte para o pacote namespaced).

O FreeCAD executa os InitGui.py com exec() dentro de uma função, pelo que
nomes de nível de módulo definidos aqui não são visíveis dentro de corpos
de classe/função. Todo o código GUI vive portanto em
``freecad.topografia.init_gui`` (módulo normal); este ficheiro apenas o
importa. A raiz do addon já está no sys.path (colocada pelo FreeCAD).
"""
import os

import FreeCAD as App

try:
    # catálogo de traduções (contexto "Topografia"); sem GUI é inofensivo
    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets

    _TRAD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "freecad", "topografia", "resources", "translations")
    Gui.addLanguagePath(_TRAD)
    _idioma = App.ParamGet("User parameter:BaseApp/Preferences/General").GetString(
        "Language", "") or QtCore.QLocale.system().name()
    _tradutor = QtCore.QTranslator()
    if _tradutor.load("topografia_" + _idioma.replace("-", "_"), _TRAD):
        _app = QtWidgets.QApplication.instance()
        if _app:
            _app.installTranslator(_tradutor)
except Exception:
    pass

try:
    import freecad.topografia.init_gui  # noqa: F401  (regista workbench+comandos)
except Exception:  # não matar o arranque do FreeCAD; registar para diagnóstico
    import traceback
    App.Console.PrintError(
        "[Topografia] falha ao carregar a GUI:\n" + traceback.format_exc()
    )
