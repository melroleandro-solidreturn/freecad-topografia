# SPDX-License-Identifier: LGPL-2.1-or-later
"""Init do addon Topografia (aplicação — seguro em consola).

Regista o formato de importação CSV topográfico no FreeCAD:
    ponto;codigo;X;Y;cota  (delimitador e decimal configuráveis)

Sem manipulação de sys.path: o FreeCAD coloca a raiz de cada addon no
sys.path no arranque e o pacote-namespaced ``freecad.topografia`` resolve
naturalmente (boas práticas do Addon Index).
"""
import FreeCAD

FreeCAD.addImportType("Levantamento topográfico (*.csv *.txt)", "topografia")

# valida o carregamento do pacote no arranque (consola incluída)
from freecad.topografia.csv_io import le_pontos  # noqa: E402,F401
