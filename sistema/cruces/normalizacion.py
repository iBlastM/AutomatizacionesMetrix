"""Normalización de textos, CURP y llaves para poder compararlos entre bases."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# Partículas que no aportan a la comparación de nombres ("MARIA DE LOS ANGELES").
_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E", "MC", "MAC", "VON", "VAN"}

_RE_NO_ALFANUM = re.compile(r"[^A-Z0-9]+")
_RE_FLOAT_EXCEL = re.compile(r"^(-?\d+)\.0+$")

PATRON_CURP = re.compile(r"^[A-Z]{4}\d{6}[HMX][A-Z]{2}[A-Z]{3}[A-Z0-9]\d$")


def quitar_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_texto(valor) -> str:
    """MAYÚSCULAS, sin acentos ni signos, con espacios simples."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    texto = quitar_acentos(str(valor)).upper()
    return _RE_NO_ALFANUM.sub(" ", texto).strip()


def normalizar_curp(valor) -> str:
    """CURP en mayúsculas y sin espacios ni signos."""
    return normalizar_texto(valor).replace(" ", "")


def normalizar_llave(valor) -> str:
    """Llave genérica: sin espacios, sin acentos, sin el '.0' que Excel agrega a números."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    texto = _RE_FLOAT_EXCEL.sub(r"\1", texto)
    return normalizar_texto(texto).replace(" ", "")


def nombre_canonico(valor) -> str:
    """Nombre comparable sin importar el orden ni los acentos.

    "Gonzalez Martinez Jose Francisco" y "JOSE FRANCISCO GONZALEZ MARTINEZ"
    producen el mismo resultado.
    """
    tokens = [t for t in normalizar_texto(valor).split() if t not in _PARTICULAS]
    return " ".join(sorted(tokens))


def curp_parece_valida(curp: str) -> bool:
    return bool(PATRON_CURP.match(curp))


def serie_normalizada(serie: pd.Series, funcion) -> pd.Series:
    """Aplica `funcion` sobre los valores únicos y los reparte; evita repetir trabajo."""
    valores = serie.astype("object").where(serie.notna(), "")
    unicos = pd.unique(valores)
    tabla = {v: funcion(v) for v in unicos}
    return valores.map(tabla).astype("object")


def unir_columnas(df: pd.DataFrame, columnas: list[str], funcion) -> pd.Series:
    """Normaliza y concatena varias columnas (p. ej. nombre + paterno + materno)."""
    if not columnas:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    partes = [serie_normalizada(df[c], normalizar_texto) for c in columnas]
    unido = partes[0]
    for p in partes[1:]:
        unido = unido + " " + p
    return serie_normalizada(unido, funcion)


def llave_compuesta(df: pd.DataFrame, columnas: list[str]) -> pd.Series:
    """Llave a partir de una o varias columnas, separadas por '|' si hay más de una."""
    if not columnas:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    partes = [serie_normalizada(df[c], normalizar_llave) for c in columnas]
    if len(partes) == 1:
        return partes[0]
    unido = partes[0]
    for p in partes[1:]:
        unido = unido + "|" + p
    # Si alguna parte quedó vacía, la llave no es confiable.
    hay_vacia = pd.concat([p == "" for p in partes], axis=1).any(axis=1)
    return unido.where(~hay_vacia, "")
