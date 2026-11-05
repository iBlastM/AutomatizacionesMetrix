"""Lectura de archivos Excel/CSV para cruces. Todo se lee como texto.

Leer como texto evita que pandas convierta CURP, teléfonos, códigos postales o
columnas SI/NO en números (el error que borró los programas en el primer cruce
del resumen de octubre).
"""

from __future__ import annotations

import csv
from io import BytesIO, StringIO

import pandas as pd

EXTENSIONES_EXCEL = (".xlsx", ".xlsm", ".xls")
EXTENSIONES_VALIDAS = EXTENSIONES_EXCEL + (".csv",)
_CODIFICACIONES = ("utf-8-sig", "cp1252", "latin-1")


def es_excel(nombre: str) -> bool:
    return nombre.lower().endswith(EXTENSIONES_EXCEL)


def _abrir_excel(datos: bytes) -> pd.ExcelFile:
    """Abre con calamine (rápido) y, si no está disponible, con openpyxl."""
    try:
        return pd.ExcelFile(BytesIO(datos), engine="calamine")
    except ImportError:
        return pd.ExcelFile(BytesIO(datos), engine="openpyxl")


def listar_hojas(nombre: str, datos: bytes) -> list[str]:
    if not es_excel(nombre):
        return ["(archivo CSV)"]
    with _abrir_excel(datos) as libro:
        return list(libro.sheet_names)


def _decodificar(datos: bytes) -> str:
    for codificacion in _CODIFICACIONES:
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1", errors="replace")


def _detectar_separador(texto: str) -> str:
    muestra = "\n".join(texto.splitlines()[:5])
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _limpiar_encabezados(df: pd.DataFrame) -> pd.DataFrame:
    vistos: dict[str, int] = {}
    nuevos = []
    for col in df.columns:
        base = " ".join(str(col).split()) or "SIN_NOMBRE"
        n = vistos.get(base, 0)
        vistos[base] = n + 1
        nuevos.append(base if n == 0 else f"{base}.{n}")
    df.columns = nuevos
    return df


def leer_tabla(nombre: str, datos: bytes, hoja: str | None = None) -> pd.DataFrame:
    """Devuelve la hoja (o el CSV) como DataFrame de texto, sin celdas nulas."""
    if es_excel(nombre):
        with _abrir_excel(datos) as libro:
            df = libro.parse(hoja or libro.sheet_names[0], dtype=str, keep_default_na=False)
    else:
        texto = _decodificar(datos)
        df = pd.read_csv(
            StringIO(texto),
            sep=_detectar_separador(texto),
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip",
        )
    df = _limpiar_encabezados(df)
    # Filas totalmente vacías (típico al final de una hoja de Excel).
    vacias = (df == "").all(axis=1)
    return df.loc[~vacias].reset_index(drop=True)


def dataframe_a_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte una tabla cualquiera (p. ej. la salida de Limpieza) al formato de cruces."""
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].astype("object").where(out[col].notna(), "").astype(str)
    out.columns = [str(c) for c in out.columns]
    return _limpiar_encabezados(out).reset_index(drop=True)
