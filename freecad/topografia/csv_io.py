# SPDX-License-Identifier: LGPL-2.1-or-later
"""Importação de pontos topográficos a partir de CSV/TXT.

Objectivo da Fase 0/1 do plano de estradas: ler ficheiros
``ponto;codigo;X;Y;cota`` (pt-PT, delimitador ';' e decimal vírgula) sem
perda silenciosa de linhas e com o campo ``codigo`` preservado como
cidadão de primeira classe.

O módulo é intencionalmente independente do FreeCAD (numpy não incluido):
recebe um caminho, devolve um :class:`RelatorioImportacao`.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ALIAS_NUMERO = {"ponto", "num", "numero", "n", "nome", "name", "point", "pt", "id", "mark"}
ALIAS_CODIGO = {"codigo", "code", "desc", "descricao", "description", "atributo", "attr"}
ALIAS_X = {"x", "e", "easting", "este"}
ALIAS_Y = {"y", "n", "northing", "norte"}
ALIAS_Z = {"z", "cota", "elev", "elevacao", "elevation", "alt", "altitude", "h", "cotaabs"}

CANDIDATOS_DELIMITADOR = [";", ",", "\t", "|"]
_RE_DECIMAL_VIRGULA = re.compile(r"^-?\d+,\d+$")
_RE_DECIMAL_PONTO = re.compile(r"^-?\d+\.\d+$")
_RE_MILHARES_PONTO = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")
_RE_MILHARES_VIRGULA = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


@dataclass
class PontoTopografico:
    """Um ponto de levantamento: numero, codigo e coordenadas absolutas (E, N, cota)."""

    numero: str
    codigo: str
    x: float
    y: float
    z: float


@dataclass
class RelatorioImportacao:
    """Resultado auditável de uma importação — nada se perde em silêncio."""

    ficheiro: str = ""
    delimitador: str = ""
    decimal: str = "."
    mapeamento: dict = field(default_factory=dict)
    pontos: list = field(default_factory=list)
    rejeitadas: list = field(default_factory=list)  # (nº linha, motivo)

    @property
    def codigos(self) -> dict:
        contagem = {}
        for p in self.pontos:
            contagem[p.codigo] = contagem.get(p.codigo, 0) + 1
        return contagem

    @property
    def resumo(self) -> str:
        return (
            f"{len(self.pontos)} pontos, {len(self.rejeitadas)} linhas rejeitadas "
            f"(delimitador '{self.delimitador}', decimal '{self.decimal}')"
        )


def _sem_acentos(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _normaliza_celula(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _sem_acentos(s).strip().lower())


def _le_linhas(caminho: str) -> list:
    """Lê o ficheiro em utf-8-sig com recurso para latin-1 (exportações PT frequentes)."""
    texto = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = Path(caminho).read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ValueError(f"Não foi possível descodificar o ficheiro: {caminho}")
    return [ln for ln in texto.splitlines() if ln.strip()]


def _divide(linha: str, delimitador: str) -> list:
    if delimitador == " ":
        return linha.split()
    return next(csv.reader([linha], delimiter=delimitador, skipinitialspace=True))


def detecta_delimitador(linhas: list) -> str:
    """Escolhe o delimitador com contagem de colunas mais consistente."""
    melhor, melhor_pontuacao = " ", -1.0
    for d in CANDIDATOS_DELIMITADOR:
        contagens = {}
        for ln in linhas[: min(30, len(linhas))]:
            n = len(_divide(ln, d))
            if n > 1:
                contagens[n] = contagens.get(n, 0) + 1
        if not contagens:
            continue
        n_frequente = max(contagens, key=contagens.get)
        pontuacao = contagens[n_frequente] * n_frequente
        if pontuacao > melhor_pontuacao:
            melhor, melhor_pontuacao = d, pontuacao
    return melhor


def detecta_decimal(linhas: list, delimitador: str, colunas_numericas=(2, 3, 4)) -> str:
    """Detecta ',' ou '.' olhando para as colunas que deverão ser numéricas."""
    virgulas = pontos = 0
    for ln in linhas[: min(50, len(linhas))]:
        cel = _divide(ln, delimitador)
        for c in colunas_numericas:
            if c < len(cel):
                v = cel[c].strip()
                if _RE_DECIMAL_VIRGULA.match(v):
                    virgulas += 1
                elif _RE_DECIMAL_PONTO.match(v):
                    pontos += 1
    if virgulas > pontos:
        return ","
    return "."


def _mapeia_cabecalho(celulas: list) -> dict | None:
    """Devolve {'numero': i, 'codigo': j, 'x': k, 'y': l, 'z': m} a partir do cabeçalho."""
    mapa = {}
    for i, cel in enumerate(celulas):
        n = _normaliza_celula(cel)
        if not n:
            continue
        if n in ALIAS_NUMERO and "numero" not in mapa:
            mapa["numero"] = i
        elif n in ALIAS_CODIGO and "codigo" not in mapa:
            mapa["codigo"] = i
        elif n in ALIAS_X and "x" not in mapa:
            mapa["x"] = i
        elif n in ALIAS_Y and "y" not in mapa:
            mapa["y"] = i
        elif n in ALIAS_Z and "z" not in mapa:
            mapa["z"] = i
    if {"x", "y", "z"} <= set(mapa):
        return mapa
    return None


def _mapeamento_sem_cabecalho(n_colunas: int) -> dict:
    if n_colunas >= 5:
        return {"numero": 0, "codigo": 1, "x": 2, "y": 3, "z": 4}
    if n_colunas == 4:
        return {"numero": 0, "x": 1, "y": 2, "z": 3}
    if n_colunas == 3:
        return {"x": 0, "y": 1, "z": 2}
    return {}


def _numero_ok(s: str) -> bool:
    return bool(re.match(r"^[+-]?\d+$", s.strip()))


def _para_float(celula: str, decimal: str, linha: int) -> float:
    v = celula.strip().replace(" ", "")
    if decimal == ",":
        if _RE_MILHARES_PONTO.match(v):
            v = v.replace(".", "").replace(",", ".")
        else:
            v = v.replace(",", ".")
    else:
        if _RE_MILHARES_VIRGULA.match(v):
            v = v.replace(",", "")
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"linha {linha}: valor não numérico '{celula.strip()}'") from None


def le_pontos(
    caminho: str,
    delimitador: str | None = None,
    decimal: str | None = None,
    mapeamento: dict | None = None,
    tem_cabecalho: bool | None = None,
) -> RelatorioImportacao:
    """Lê um ficheiro de pontos; devolve relatório com pontos e rejeições justificadas."""
    linhas = _le_linhas(caminho)
    if not linhas:
        return RelatorioImportacao(ficheiro=caminho, rejeitadas=[(0, "ficheiro vazio")])

    delimitador = delimitador or detecta_delimitador(linhas)
    decimal = decimal or detecta_decimal(linhas, delimitador)
    rel = RelatorioImportacao(
        ficheiro=str(caminho), delimitador=delimitador, decimal=decimal
    )

    primeira = _divide(linhas[0], delimitador)
    cabecalho_nat = _mapeia_cabecalho(primeira)
    if mapeamento is not None:
        rel.mapeamento = dict(mapeamento)
        consumir = bool(cabecalho_nat) if tem_cabecalho is None else tem_cabecalho
    elif cabecalho_nat is not None:
        rel.mapeamento = cabecalho_nat
        consumir = True
        if tem_cabecalho is False:
            consumir = False
            rel.mapeamento = _mapeamento_sem_cabecalho(len(primeira))
    else:
        rel.mapeamento = _mapeamento_sem_cabecalho(len(primeira))
        consumir = bool(tem_cabecalho)  # sem cabeçalho reconhecido, só consome se ordenado

    if not {"x", "y", "z"} <= set(rel.mapeamento):
        rel.rejeitadas.append((1, "não foi possível identificar as colunas X, Y e cota"))
        return rel

    inicio = 1 if consumir else 0
    for i, linha in enumerate(linhas[inicio:], start=inicio + 1):
        celulas = _divide(linha, delimitador)
        try:
            m = rel.mapeamento
            if max(m.values()) >= len(celulas):
                raise ValueError(f"linha {i}: esperadas {max(m.values()) + 1} colunas, obtidas {len(celulas)}")
            x = _para_float(celulas[m["x"]], decimal, i)
            y = _para_float(celulas[m["y"]], decimal, i)
            z = _para_float(celulas[m["z"]], decimal, i)
            numero = celulas[m["numero"]].strip() if "numero" in m else str(i)
            codigo = (
                _sem_acentos(celulas[m["codigo"]]).strip().upper()
                if "codigo" in m
                else ""
            )
            rel.pontos.append(PontoTopografico(numero, codigo, x, y, z))
        except ValueError as exc:
            rel.rejeitadas.append((i, str(exc)))
    return rel
