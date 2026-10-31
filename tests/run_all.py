# SPDX-License-Identifier: LGPL-2.1-or-later
"""Corre a suite completa dentro do FreeCADCmd:

    build/debug/bin/FreeCADCmd tests/run_all.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

import freecad  # noqa: E402
import pkgutil

freecad.__path__ = pkgutil.extend_path(freecad.__path__, freecad.__name__)

import pytest  # noqa: E402

rc = pytest.main(["-v", "--no-header", "--tb=short", "tests"])
print("PYTEST_RC", rc, flush=True)
