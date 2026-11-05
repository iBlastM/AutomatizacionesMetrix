"""Sugerencias automáticas de columnas, para que el usuario no tenga que buscarlas."""

from __future__ import annotations

import re

import pandas as pd

from .normalizacion import normalizar_texto

_RE_CURP_FLOJO = re.compile(r"^[A-Z]{4}\d{6}")
_EXCLUIR_NOMBRE = ("CALLE", "COLONIA", "PROGRAMA", "MUNICIPIO", "ESTADO", "DEPENDENCIA", "COORDINADOR")


def _porcentaje_curp(serie: pd.Series) -> float:
    valores = serie.astype("object").where(serie.notna(), "")
    muestra = valores[valores != ""].head(500)
    if muestra.empty:
        return 0.0
    limpios = muestra.map(lambda v: normalizar_texto(v).replace(" ", ""))
    return float(limpios.map(lambda v: bool(_RE_CURP_FLOJO.match(v))).mean())


def sugerir_columna_curp(df: pd.DataFrame) -> str | None:
    """Columna con mayor proporción de valores que parecen CURP (con desempate por nombre)."""
    mejor, mejor_puntaje = None, 0.0
    for col in df.columns:
        puntaje = _porcentaje_curp(df[col])
        if "CURP" in normalizar_texto(col):
            puntaje += 0.25
        if puntaje > mejor_puntaje and puntaje >= 0.5:
            mejor, mejor_puntaje = col, puntaje
    return mejor


def sugerir_columnas_nombre(df: pd.DataFrame) -> list[str]:
    """Columnas que componen el nombre: una de nombre completo o nombre + apellidos."""
    normalizadas = {c: normalizar_texto(c) for c in df.columns}

    for col, n in normalizadas.items():
        if "COMPLETO" in n and "NOMBRE" in n:
            return [col]

    def buscar(*patrones: str, excluir: tuple[str, ...] = ()) -> str | None:
        for col, n in normalizadas.items():
            if any(x in n for x in excluir):
                continue
            if any(p in n for p in patrones):
                return col
        return None

    nombre = buscar("NOMBRE", "PILA", excluir=_EXCLUIR_NOMBRE + ("PATERNO", "MATERNO", "APELLIDO"))
    paterno = buscar("PATERNO", "APELLIDO PATERNO", "AP PATERNO")
    materno = buscar("MATERNO", "APELLIDO MATERNO", "AP MATERNO")
    return [c for c in (nombre, paterno, materno) if c]


def _es_si_no(serie: pd.Series) -> bool:
    valores = serie.astype("object").where(serie.notna(), "")
    no_vacios = valores[valores != ""]
    if no_vacios.empty:
        return False
    limpios = no_vacios.astype(str).str.strip().str.upper().str.replace("Í", "I", regex=False)
    return bool(limpios.isin(["SI", "NO"]).all())


def detectar_columnas_programas(df: pd.DataFrame) -> list[str]:
    """Columnas cuyos valores son únicamente SI / NO (o vacío)."""
    return [c for c in df.columns if _es_si_no(df[c])]


def sugerir_columna_total(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        n = normalizar_texto(col)
        if "TOTAL" in n and ("APOYO" in n or "PROGRAMA" in n or "BENEFICIO" in n):
            return col
    return None


def sugerir_columna_desempate(df: pd.DataFrame) -> str | None:
    return sugerir_columna_total(df)

