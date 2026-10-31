# SPDX-License-Identifier: LGPL-2.1-or-later
"""InitGui do addon Topografia (ponte para o pacote namespaced).

O FreeCAD executa os InitGui.py com exec() dentro de uma função, pelo que
nomes de nível de módulo definidos aqui não são visíveis dentro de corpos
de classe/função. Todo o código GUI vive portanto em
``freecad.topografia.init_gui`` (módulo normal); este ficheiro apenas o
importa. A raiz do addon já está no sys.path (colocada pelo FreeCAD).
"""
import FreeCAD as App

try:
    import freecad.topografia.init_gui  # noqa: F401  (regista workbench+comandos)
except Exception:  # não matar o arranque do FreeCAD; registar para diagnóstico
    import traceback
    App.Console.PrintError(
        "[Topografia] falha ao carregar a GUI:\n" + traceback.format_exc()
    )
