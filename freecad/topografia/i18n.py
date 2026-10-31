# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tradução da interface do addon (contexto ``Topografia``).

``FreeCAD.Qt.translate`` existe tanto na GUI como em ``FreeCADCmd``, pelo
que os módulos de UI continuam testáveis headless: sem catálogo carregado,
``tr`` devolve a própria chave (o texto inglês de origem).
"""
import FreeCAD


def tr(texto: str) -> str:
    """Traduz *texto* no contexto "Topografia"; sem tradução, devolve-o."""
    return FreeCAD.Qt.translate("Topografia", texto)
