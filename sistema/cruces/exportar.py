"""ExportaciÃ³n del resultado del cruce a Excel y CSV."""

from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from .motor import COL_TIPO, SIN_COINCIDENCIA

COLOR_ENCABEZADO = "#060606"
COLOR_TEXTO_ENCABEZADO = "#7BC11D"
COLOR_TITULO = "#267E28"

_RE_NUMERO = re.compile(r"^-?(0|[1-9]\d*)(\.\d+)?$")


def _columna_es_numerica(serie: pd.Series) -> bool:
    valores = serie[serie != ""]
    if valores.empty:
        return False
    if not valores.str.match(_RE_NUMERO).all():
        return False
    # Los enteros de mÃ¡s de 15 dÃ­gitos pierden precisiÃ³n en Excel: se dejan como texto.
    return bool((valores.str.replace(r"[-.]", "", regex=True).str.len() <= 15).all())


def preparar_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte a nÃºmero las columnas que son nÃºmeros de verdad (no cÃ³digos con ceros a la izquierda)."""
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if s.dtype == object or str(s.dtype).startswith(("str", "string")):
            texto = s.astype(str)
            if _columna_es_numerica(texto):
                out[col] = pd.to_numeric(texto.replace("", pd.NA), errors="coerce")
    return out


def a_csv(df: pd.DataFrame) -> bytes:
    """CSV en UTF-8 con BOM para que Excel respete eÃ±es y acentos."""
    return df.to_csv(index=False).encode("utf-8-sig")


def _escribir_hoja(escritor: pd.ExcelWriter, df: pd.DataFrame, nombre: str, formatos: dict) -> None:
    df_x = preparar_para_excel(df)
    # Los datos empiezan en la fila 2; la fila 1 se escribe a mano con el formato del encabezado.
    df_x.to_excel(escritor, sheet_name=nombre, index=False, startrow=1, header=False)
    hoja = escritor.sheets[nombre]
    for j, col in enumerate(df.columns):
        hoja.write(0, j, col, formatos["encabezado"])
        muestra = df[col].astype(str).head(200)
        ancho = max([len(str(col))] + [len(v) for v in muestra]) if len(df) else len(str(col))
        hoja.set_column(j, j, min(max(ancho + 2, 10), 42))
    hoja.freeze_panes(1, 0)
    if len(df.columns):
        hoja.autofilter(0, 0, max(len(df), 1), len(df.columns) - 1)
    hoja.set_row(0, 22)


def _hoja_resumen(escritor: pd.ExcelWriter, resumen: dict, parametros: list[tuple[str, str]], advertencias: list[str], formatos: dict) -> None:
    libro = escritor.book
    hoja = libro.add_worksheet("Resumen")
    escritor.sheets["Resumen"] = hoja
    hoja.set_column(0, 0, 48)
    hoja.set_column(1, 3, 22)
    fila = 0
    hoja.write(fila, 0, "Resumen del cruce", formatos["titulo"])
    fila += 2

    def tabla(titulo: str, df: pd.DataFrame | None, fila: int) -> int:
        if df is None or df.empty:
            return fila
        hoja.write(fila, 0, titulo, formatos["subtitulo"])
        fila += 1
        for j, col in enumerate(df.columns):
            hoja.write(fila, j, col, formatos["encabezado"])
        for i, registro in enumerate(df.itertuples(index=False), start=1):
            for j, valor in enumerate(registro):
                if isinstance(valor, (int, float)) or hasattr(valor, "item"):
                    hoja.write_number(fila + i, j, float(valor))
                else:
                    hoja.write(fila + i, j, str(valor))
        return fila + len(df) + 2

    hoja.write(fila, 0, "Registros en la base A")
    hoja.write_number(fila, 1, resumen["total"])
    hoja.write(fila + 1, 0, "Encontrados en la base B")
    hoja.write_number(fila + 1, 1, resumen["encontrados"])
    hoja.write(fila + 2, 0, SIN_COINCIDENCIA.capitalize())
    hoja.write_number(fila + 2, 1, resumen["sin_coincidencia"])
    fila += 4

    fila = tabla("Resultado por tipo de coincidencia", resumen["por_tipo"], fila)
    fila = tabla("Registros encontrados segÃºn nÃºmero de programas", resumen["distribucion_programas"], fila)
    fila = tabla("Programas mÃ¡s frecuentes entre los encontrados", resumen["programas_frecuentes"], fila)

    verif = resumen.get("verificacion")
    if verif:
        hoja.write(fila, 0, "VerificaciÃ³n", formatos["subtitulo"])
        hoja.write(
            fila + 1, 0,
            f"NUM_PROGRAMAS coincide con Â«{verif['columna']}Â» en {verif['coinciden']} de {verif['comparados']} filas.",
        )
        fila += 3

    hoja.write(fila, 0, "ParÃ¡metros usados", formatos["subtitulo"])
    for i, (clave, valor) in enumerate(parametros, start=1):
        hoja.write(fila + i, 0, clave)
        hoja.write(fila + i, 1, valor)
    fila += len(parametros) + 2

    if advertencias:
        hoja.write(fila, 0, "Avisos", formatos["subtitulo"])
        for i, aviso in enumerate(advertencias, start=1):
            hoja.write(fila + i, 0, aviso)


def a_excel(
    salida: pd.DataFrame,
    resumen: dict,
    parametros: list[tuple[str, str]],
    advertencias: list[str],
    dudosas: pd.DataFrame | None = None,
) -> bytes:
    """Libro con: Cruce, Encontrados, Sin coincidencia, Resumen (y Coincidencias dudosas si hay)."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as escritor:
        libro = escritor.book
        formatos = {
            "encabezado": libro.add_format(
                {"bold": True, "font_color": COLOR_TEXTO_ENCABEZADO, "bg_color": COLOR_ENCABEZADO,
                 "valign": "vcenter", "border": 0}
            ),
            "titulo": libro.add_format({"bold": True, "font_size": 16, "font_color": COLOR_TITULO}),
            "subtitulo": libro.add_format({"bold": True, "font_size": 12, "font_color": COLOR_TITULO}),
        }
        encontrados = salida[salida[COL_TIPO] != SIN_COINCIDENCIA]
        sin = salida[salida[COL_TIPO] == SIN_COINCIDENCIA]

        _escribir_hoja(escritor, salida, "Cruce", formatos)
        _escribir_hoja(escritor, encontrados, "Encontrados", formatos)
        _escribir_hoja(escritor, sin, "Sin coincidencia", formatos)
        if dudosas is not None and not dudosas.empty:
            _escribir_hoja(escritor, dudosas, "Coincidencias dudosas", formatos)
        _hoja_resumen(escritor, resumen, parametros, advertencias, formatos)
    return buffer.getvalue()

