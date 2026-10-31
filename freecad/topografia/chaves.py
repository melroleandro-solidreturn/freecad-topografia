# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chaves de descrição (equivalente funcional das Description Keys do Civil 3D).

Cada regra associa um padrão de código (com '*' à escolha, tipo ``"EP*"``) a
um grupo, uma cor e à qualidade de breakline. A primeira regra que casa ganha.
"""
from __future__ import annotations

import fnmatch

CHAVES_PREDEFINIDAS = {
    "EIX*": {"grupo": "Eixo", "cor": (1.0, 0.0, 0.0), "breakline": True},
    "EP*": {"grupo": "Pavimento", "cor": (0.9, 0.9, 0.2), "breakline": True},
    "LE*": {"grupo": "Linha de água", "cor": (0.2, 0.5, 1.0), "breakline": True},
    "TAL*": {"grupo": "Talude", "cor": (0.6, 0.4, 0.1), "breakline": True},
    "VAL*": {"grupo": "Vala", "cor": (0.2, 0.7, 0.7), "breakline": True},
    "MURO*": {"grupo": "Muros", "cor": (0.5, 0.5, 0.5), "breakline": False},
    "ARV*": {"grupo": "Vegetação", "cor": (0.1, 0.8, 0.2), "breakline": False},
    "CER*": {"grupo": "Cercas", "cor": (0.8, 0.5, 0.8), "breakline": False},
    "GRE*": {"grupo": "Grelhas", "cor": (0.0, 0.0, 0.0), "breakline": False},
    "CAS*": {"grupo": "Edificações", "cor": (0.7, 0.3, 0.3), "breakline": False},
}


def classifica(codigo: str, chaves: dict | None = None) -> dict:
    """Devolve a regra que casa com o código (ou regra neutra)."""
    chaves = chaves or CHAVES_PREDEFINIDAS
    cod = (codigo or "").strip().upper()
    for padrao, regra in chaves.items():
        if fnmatch.fnmatchcase(cod, padrao.upper()):
            return {"padrao": padrao, **regra}
    return {"padrao": "*", "grupo": cod or "Sem código", "cor": (0.8, 0.8, 0.8), "breakline": False}


def agrupa_por_codigo(pontos: list) -> dict:
    """Índice código -> lista de posições na sequência de importação."""
    grupos = {}
    for i, p in enumerate(pontos):
        grupos.setdefault(p.codigo, []).append(i)
    return grupos
