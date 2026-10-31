# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bootstrap para os testes do módulo Topografia (correr dentro do FreeCADCmd).

    build/debug/bin/FreeCADCmd tests/run_all.py
"""
from __future__ import annotations

import sys
import types
import pkgutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# stubs de módulos GUI indisponíveis em consola
_STUB = types.ModuleType("FreeCADGui")


class _Dummy:
    def __getattr__(self, nome):
        return _Dummy()

    def __call__(self, *a, **k):
        return _Dummy()

    def children(self):
        return []


_STUB.getMainWindow = lambda: _Dummy()
for _nome in ("FreeCADGui", "MeshGui", "PointsGui"):
    sys.modules.setdefault(_nome, _STUB)

sys.path.insert(0, str(RAIZ))

import freecad  # noqa: E402

freecad.__path__ = pkgutil.extend_path(freecad.__path__, freecad.__name__)

import pytest  # noqa: E402


@pytest.fixture()
def doc():
    import FreeCAD

    documento = FreeCAD.newDocument("TesteTopografia")
    yield documento
    FreeCAD.closeDocument(documento.Name)


@pytest.fixture()
def dados():
    return Path(__file__).resolve().parent / "samples"
