"""Motor de cruce entre dos bases. No depende de Streamlit.

Dado un padrón (base A) y una base de referencia (base B), busca para cada fila
de A su equivalente en B en etapas, de la más segura a la más flexible, y trae
las columnas de B. Las etapas reproducen el procedimiento documentado en
`RESUMEN_CRUCES_Y_LIMPIEZA.md`:

1. Llave exacta (CURP normalizada, o la llave que se elija).
2. Nombre + fecha de nacimiento del CURP (dígitos 5 a 10), para CURP con error de captura.
3. Fecha de nacimiento del CURP + nombre similar (queda para revisión).
4. Solo nombre exacto, apagada por defecto (queda para revisión).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import numpy as np
import pandas as pd

from .normalizacion import (
    quitar_acentos,
    llave_compuesta,
    nombre_canonico,
    normalizar_curp,
    normalizar_texto,
    serie_normalizada,
    unir_columnas,
)

# ── Tipos de coincidencia ────────────────────────────────────────────────
SIN_COINCIDENCIA = "SIN COINCIDENCIA"
T_LLAVE = "LLAVE EXACTA"
T_CURP = "CURP EXACTA"
T_NOMBRE_CURP = "NOMBRE + CURP CON ERROR DE CAPTURA"
T_PARCIAL = "CURP PARCIAL + NOMBRE SIMILAR"
T_SOLO_NOMBRE = "SOLO NOMBRE (REVISAR)"

TIPOS_REVISION = (T_PARCIAL, T_SOLO_NOMBRE)

COL_TIPO = "TIPO_COINCIDENCIA"
COL_PROGRAMAS = "PROGRAMAS_BENEFICIARIO"
COL_NUM_PROGRAMAS = "NUM_PROGRAMAS"

MODO_CURP = "curp"
MODO_LLAVE = "llave"

_RE_PREFIJO_CURP = re.compile(r"^[A-Z]{4}\d{6}")
_RE_FECHA6 = re.compile(r"^\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")
_RE_INICIALES = re.compile(r"^[A-Z]{4}$")


@dataclass
class Configuracion:
    """Todo lo que el usuario decide antes de cruzar."""

    modo: str = MODO_CURP
    cols_llave_a: list[str] = field(default_factory=list)
    cols_llave_b: list[str] = field(default_factory=list)
    cols_nombre_a: list[str] = field(default_factory=list)
    cols_nombre_b: list[str] = field(default_factory=list)
    buscar_nombre_y_fecha: bool = True
    buscar_fecha_nombre_similar: bool = True
    umbral_similitud: float = 0.85
    buscar_solo_nombre: bool = False
    col_desempate_b: str | None = None
    etiqueta_b: str = "BASE_B"
    cols_traer_b: list[str] | None = None
    resumir_programas: bool = False
    cols_programas_b: list[str] = field(default_factory=list)
    incluir_cols_programas: bool = True
    col_total_b: str | None = None

    @property
    def tipo_exacto(self) -> str:
        return T_CURP if self.modo == MODO_CURP else T_LLAVE


@dataclass
class ResultadoCruce:
    a: pd.DataFrame
    b_unica: pd.DataFrame
    emparejamientos: pd.DataFrame
    estadisticas: dict
    advertencias: list[str]
    cfg: Configuracion


# ── Utilidades ───────────────────────────────────────────────────────────

def validar_configuracion(a: pd.DataFrame, b: pd.DataFrame, cfg: Configuracion) -> list[str]:
    """Devuelve la lista de problemas que impiden cruzar (vacía si todo está bien)."""
    problemas: list[str] = []
    if a.empty:
        problemas.append("La base A no tiene filas.")
    if b.empty:
        problemas.append("La base B no tiene filas.")
    if not cfg.cols_llave_a or not cfg.cols_llave_b:
        problemas.append("Elige la columna llave en las dos bases.")
    if cfg.modo == MODO_CURP and (len(cfg.cols_llave_a) > 1 or len(cfg.cols_llave_b) > 1):
        problemas.append("En modo CURP la llave es una sola columna por base.")
    if len(cfg.cols_llave_a) != len(cfg.cols_llave_b):
        problemas.append("Las dos bases deben usar el mismo número de columnas en la llave.")
    faltan_a = [c for c in cfg.cols_llave_a + cfg.cols_nombre_a if c not in a.columns]
    faltan_b = [c for c in cfg.cols_llave_b + cfg.cols_nombre_b if c not in b.columns]
    if faltan_a:
        problemas.append(f"Columnas que no existen en la base A: {', '.join(faltan_a)}.")
    if faltan_b:
        problemas.append(f"Columnas que no existen en la base B: {', '.join(faltan_b)}.")
    usa_nombre = cfg.buscar_solo_nombre or (
        cfg.modo == MODO_CURP and (cfg.buscar_nombre_y_fecha or cfg.buscar_fecha_nombre_similar)
    )
    if usa_nombre and (not cfg.cols_nombre_a or not cfg.cols_nombre_b):
        problemas.append(
            "Las etapas que usan el nombre necesitan las columnas de nombre de las dos bases. "
            "Elígelas o apaga esas etapas."
        )
    return problemas


def _curp_utilizable(curp: str) -> bool:
    """CURP lo bastante completa para compararse de forma exacta sin falsos positivos."""
    return len(curp) >= 16 and bool(_RE_PREFIJO_CURP.match(curp))


def _curp_posicional(valor) -> str:
    """CURP en mayúsculas conservando las posiciones: los caracteres raros pasan a '?'."""
    texto = quitar_acentos("" if valor is None or (not isinstance(valor, str) and pd.isna(valor)) else str(valor))
    return re.sub(r"[^A-Z0-9]", "?", re.sub(r"\s+", "", texto.upper()))


def _fecha6(valor) -> str:
    """Dígitos 5 a 10 del CURP (AAMMDD) si forman una fecha posible."""
    f = _curp_posicional(valor)[4:10]
    return f if _RE_FECHA6.match(f) else ""


def _iniciales4(valor) -> str:
    i = _curp_posicional(valor)[:4]
    return i if _RE_INICIALES.match(i) else ""


def _contencion(a: str, b: str) -> float:
    """Proporción de palabras del nombre más corto que están en el otro."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _texto_visible(df: pd.DataFrame, columnas: list[str]) -> pd.Series:
    if not columnas:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    partes = [df[c].astype("object").where(df[c].notna(), "").astype(str).str.strip() for c in columnas]
    unido = partes[0]
    for p in partes[1:]:
        unido = unido + " " + p
    return unido.str.replace(r"\s+", " ", regex=True).str.strip()


def _completitud(df: pd.DataFrame) -> np.ndarray:
    return (df != "").sum(axis=1).to_numpy()


def _desempate(df: pd.DataFrame, columna: str | None) -> np.ndarray:
    if not columna or columna not in df.columns:
        return np.zeros(len(df))
    numeros = pd.to_numeric(df[columna].astype(str).str.replace(",", "", regex=False), errors="coerce")
    return numeros.fillna(-1).to_numpy(dtype=float)


# ── Cruce ────────────────────────────────────────────────────────────────

def ejecutar_cruce(a: pd.DataFrame, b: pd.DataFrame, cfg: Configuracion) -> ResultadoCruce:
    problemas = validar_configuracion(a, b, cfg)
    if problemas:
        raise ValueError(" ".join(problemas))

    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    advertencias: list[str] = []

    # 1) Llaves y nombres normalizados
    if cfg.modo == MODO_CURP:
        llave_a = serie_normalizada(a[cfg.cols_llave_a[0]], normalizar_curp)
        llave_b = serie_normalizada(b[cfg.cols_llave_b[0]], normalizar_curp)
        llave_a = llave_a.where(llave_a.map(_curp_utilizable), "")
        llave_b = llave_b.where(llave_b.map(_curp_utilizable), "")
        c10_a = serie_normalizada(a[cfg.cols_llave_a[0]], _fecha6)
        c10_b = serie_normalizada(b[cfg.cols_llave_b[0]], _fecha6)
        ini_a = serie_normalizada(a[cfg.cols_llave_a[0]], _iniciales4)
        ini_b = serie_normalizada(b[cfg.cols_llave_b[0]], _iniciales4)
    else:
        llave_a = llave_compuesta(a, cfg.cols_llave_a)
        llave_b = llave_compuesta(b, cfg.cols_llave_b)
        c10_a = pd.Series([""] * len(a), dtype="object")
        c10_b = pd.Series([""] * len(b), dtype="object")
        ini_a = c10_a
        ini_b = c10_b

    usa_nombres = bool(cfg.cols_nombre_a and cfg.cols_nombre_b)
    nom_a = unir_columnas(a, cfg.cols_nombre_a, nombre_canonico) if usa_nombres else pd.Series([""] * len(a), dtype="object")
    nom_b = unir_columnas(b, cfg.cols_nombre_b, nombre_canonico) if usa_nombres else pd.Series([""] * len(b), dtype="object")

    # 2) Una sola fila por llave en B: la más completa, y en empate la de mayor desempate
    completitud = _completitud(b)
    desempate = _desempate(b, cfg.col_desempate_b)
    orden = np.lexsort((-desempate, -completitud))  # estable; lo último es el criterio principal
    llave_ordenada = llave_b.iloc[orden]
    es_repetida = llave_ordenada.duplicated(keep="first") & (llave_ordenada != "")
    conservar = orden[~es_repetida.to_numpy()]
    conservar = np.sort(np.array(conservar))  # conservar el orden original de B

    pool = b.iloc[conservar].reset_index(drop=True)
    fila_origen_b = pd.Series(conservar + 2)  # número de fila en Excel (encabezado = 1)
    k_b = llave_b.iloc[conservar].reset_index(drop=True)
    c10_pool = c10_b.iloc[conservar].reset_index(drop=True)
    ini_pool = ini_b.iloc[conservar].reset_index(drop=True)
    nom_pool = nom_b.iloc[conservar].reset_index(drop=True)

    n = len(a)
    pos_b = np.full(n, -1, dtype=np.int64)
    tipo = np.array([SIN_COINCIDENCIA] * n, dtype=object)
    similitud = np.zeros(n, dtype=float)

    # ── Etapa 1: llave exacta ────────────────────────────────────────────
    mapa_llave: dict[str, int] = {}
    for i, k in enumerate(k_b.to_numpy()):
        if k and k not in mapa_llave:
            mapa_llave[k] = i
    for i, k in enumerate(llave_a.to_numpy()):
        j = mapa_llave.get(k, -1) if k else -1
        if j >= 0:
            pos_b[i], tipo[i], similitud[i] = j, cfg.tipo_exacto, 1.0

    # ── Etapa 2: nombre + fecha de nacimiento del CURP ───────────────────
    if cfg.modo == MODO_CURP and cfg.buscar_nombre_y_fecha and usa_nombres:
        mapa_nc: dict[tuple[str, str], int] = {}
        for j, (c, nm) in enumerate(zip(c10_pool.to_numpy(), nom_pool.to_numpy())):
            if c and nm:
                mapa_nc.setdefault((c, nm), j)
        for i, (c, nm) in enumerate(zip(c10_a.to_numpy(), nom_a.to_numpy())):
            if pos_b[i] >= 0 or not c or not nm:
                continue
            j = mapa_nc.get((c, nm), -1)
            if j >= 0:
                pos_b[i], tipo[i], similitud[i] = j, T_NOMBRE_CURP, 1.0

    # ── Etapa 3: fecha de nacimiento del CURP + nombre similar ───────────
    if cfg.modo == MODO_CURP and cfg.buscar_fecha_nombre_similar and usa_nombres:
        grupos: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
        for j, (c, nm, ini) in enumerate(zip(c10_pool.to_numpy(), nom_pool.to_numpy(), ini_pool.to_numpy())):
            if c and nm:
                grupos[c].append((j, nm, ini))
        for i, (c, nm, ini_i) in enumerate(zip(c10_a.to_numpy(), nom_a.to_numpy(), ini_a.to_numpy())):
            if pos_b[i] >= 0 or not c or not nm or c not in grupos:
                continue
            mejor_j, mejor = -1, 0.0
            for j, nm_b, ini_j in grupos[c]:
                r = SequenceMatcher(None, nm, nm_b).ratio()
                # Nombre incompleto en una de las bases: se acepta si las iniciales del CURP coinciden.
                if ini_i and ini_i == ini_j:
                    r = max(r, 0.9 * _contencion(nm, nm_b))
                if r > mejor:
                    mejor_j, mejor = j, r
            if mejor_j >= 0 and mejor >= cfg.umbral_similitud:
                pos_b[i], tipo[i], similitud[i] = mejor_j, T_PARCIAL, round(mejor, 3)

    # ── Etapa 4: solo nombre exacto (único en B) ─────────────────────────
    ambiguos_nombre = 0
    if cfg.buscar_solo_nombre and usa_nombres:
        por_nombre: dict[str, list[int]] = defaultdict(list)
        for j, nm in enumerate(nom_pool.to_numpy()):
            if nm and len(nm.split()) >= 2:
                por_nombre[nm].append(j)
        for i, nm in enumerate(nom_a.to_numpy()):
            if pos_b[i] >= 0 or not nm or len(nm.split()) < 2:
                continue
            candidatos = por_nombre.get(nm, [])
            if len(candidatos) == 1:
                pos_b[i], tipo[i], similitud[i] = candidatos[0], T_SOLO_NOMBRE, 1.0
            elif len(candidatos) > 1:
                ambiguos_nombre += 1

    # 3) Tabla de emparejamientos
    pos_serie = pd.Series(pos_b).where(pos_b >= 0, other=pd.NA).astype("Int64")
    revisar = np.isin(tipo, TIPOS_REVISION)
    llave_visible_a = _texto_visible(a, cfg.cols_llave_a)
    llave_visible_b = _texto_visible(pool, cfg.cols_llave_b)
    nombre_visible_a = _texto_visible(a, cfg.cols_nombre_a)
    nombre_visible_b = _texto_visible(pool, cfg.cols_nombre_b)

    pos_validos = np.where(pos_b >= 0, pos_b, 0)
    emp = pd.DataFrame(
        {
            "fila_a": np.arange(n) + 2,
            "pos_b": pos_serie,
            "tipo": tipo,
            "similitud": similitud,
            "revisar": revisar,
            # Por defecto se aceptan las parciales por encima del umbral; "solo nombre" queda fuera.
            "aceptar_defecto": revisar & (tipo == T_PARCIAL),
            "nombre_a": nombre_visible_a.to_numpy(),
            "nombre_b": np.where(pos_b >= 0, nombre_visible_b.to_numpy()[pos_validos], ""),
            "llave_a": llave_visible_a.to_numpy(),
            "llave_b": np.where(pos_b >= 0, llave_visible_b.to_numpy()[pos_validos], ""),
            "fila_b": np.where(pos_b >= 0, fila_origen_b.to_numpy()[pos_validos], 0),
        }
    )

    # 4) Avisos y estadísticas
    n_sin_llave_a = int((llave_a == "").sum())
    n_sin_llave_b = int((llave_b == "").sum())
    repetidas_b = int((llave_b[llave_b != ""].duplicated(keep=False)).sum())
    filas_descartadas_b = int(len(b) - len(pool))
    if n_sin_llave_a:
        etiqueta = "CURP utilizable" if cfg.modo == MODO_CURP else "llave"
        advertencias.append(
            f"{n_sin_llave_a} fila(s) de la base A no tienen {etiqueta}. "
            "Solo podrán encontrarse por las etapas que usan el nombre."
        )
    if filas_descartadas_b:
        advertencias.append(
            f"La base B tenía {filas_descartadas_b} fila(s) con llave repetida. "
            "Se conservó la más completa de cada llave."
        )
    if ambiguos_nombre:
        advertencias.append(
            f"{ambiguos_nombre} fila(s) coinciden por nombre con más de una persona de B "
            "y no se emparejaron para evitar errores."
        )

    estadisticas = {
        "filas_a": int(n),
        "filas_b": int(len(b)),
        "filas_b_unicas": int(len(pool)),
        "filas_b_descartadas": filas_descartadas_b,
        "llaves_repetidas_b": repetidas_b,
        "a_sin_llave": n_sin_llave_a,
        "b_sin_llave": n_sin_llave_b,
        "ambiguos_nombre": ambiguos_nombre,
    }
    return ResultadoCruce(a=a, b_unica=pool, emparejamientos=emp, estadisticas=estadisticas, advertencias=advertencias, cfg=cfg)


# ── Salida ───────────────────────────────────────────────────────────────

def emparejamientos_finales(res: ResultadoCruce, aceptados: set[int] | None = None) -> pd.DataFrame:
    """Aplica las decisiones de revisión. `aceptados` contiene `fila_a` aceptadas (None = valores por defecto)."""
    emp = res.emparejamientos.copy()
    if aceptados is None:
        aceptar = emp["aceptar_defecto"]
    else:
        aceptar = emp["fila_a"].isin(aceptados)
    rechazar = emp["revisar"] & ~aceptar
    emp.loc[rechazar, "pos_b"] = pd.NA
    emp.loc[rechazar, "tipo"] = SIN_COINCIDENCIA
    emp.loc[rechazar, "similitud"] = 0.0
    return emp


def _nombres_salida_b(res: ResultadoCruce, columnas_b: list[str]) -> dict[str, str]:
    reservados = set(res.a.columns) | {COL_TIPO, COL_PROGRAMAS, COL_NUM_PROGRAMAS}
    sufijo = res.cfg.etiqueta_b.strip().upper().replace(" ", "_") or "BASE_B"
    renombres = {}
    usados = set(reservados)
    for c in columnas_b:
        nuevo = c
        if nuevo in usados:
            nuevo = f"{c}_{sufijo}"
            k = 2
            while nuevo in usados:
                nuevo = f"{c}_{sufijo}{k}"
                k += 1
        usados.add(nuevo)
        renombres[c] = nuevo
    return renombres


def calcular_programas(bloque_b: pd.DataFrame, columnas: list[str]) -> tuple[pd.Series, pd.Series]:
    """Texto con los programas marcados SI y su conteo, fila por fila."""
    if not columnas:
        vacio = pd.Series([""] * len(bloque_b), index=bloque_b.index, dtype="object")
        return vacio, vacio
    marcas = pd.DataFrame(
        {c: bloque_b[c].astype(str).str.strip().str.upper().isin(["SI", "SÍ"]) for c in columnas}
    ).to_numpy()
    nombres = np.array(columnas, dtype=object)
    lista = pd.Series(["; ".join(nombres[fila]) for fila in marcas], index=bloque_b.index, dtype="object")
    conteo = pd.Series(marcas.sum(axis=1).astype(str), index=bloque_b.index, dtype="object")
    return lista, conteo


def construir_salida(res: ResultadoCruce, aceptados: set[int] | None = None) -> pd.DataFrame:
    """Base A completa + TIPO_COINCIDENCIA + (programas) + columnas de B."""
    cfg = res.cfg
    emp = emparejamientos_finales(res, aceptados)
    pos = emp["pos_b"]
    hay = pos.notna().to_numpy()

    columnas_b = list(cfg.cols_traer_b) if cfg.cols_traer_b is not None else list(res.b_unica.columns)
    for c in cfg.cols_llave_b:  # la llave de B siempre viaja, para poder verificar el cruce
        if c not in columnas_b:
            columnas_b.insert(0, c)
    columnas_programas = [c for c in cfg.cols_programas_b if c in res.b_unica.columns]
    for c in columnas_programas + ([cfg.col_total_b] if cfg.col_total_b else []):
        if c and c not in columnas_b and c in res.b_unica.columns:
            columnas_b.append(c)

    indices = np.where(hay, pos.fillna(0).astype(int).to_numpy(), 0)
    bloque = res.b_unica[columnas_b].iloc[indices].reset_index(drop=True).copy()
    bloque.loc[~hay, :] = ""

    partes = [res.a.reset_index(drop=True), pd.DataFrame({COL_TIPO: emp["tipo"].to_numpy()})]

    mostrar_programas = bool(cfg.resumir_programas and columnas_programas)
    if mostrar_programas:
        lista, conteo = calcular_programas(bloque, columnas_programas)
        lista = lista.where(hay, "")
        conteo = conteo.where(hay, "")
        partes.append(pd.DataFrame({COL_PROGRAMAS: lista.to_numpy(), COL_NUM_PROGRAMAS: conteo.to_numpy()}))

    if mostrar_programas and not cfg.incluir_cols_programas:
        bloque = bloque.drop(columns=[c for c in columnas_programas if c != cfg.col_total_b])

    bloque = bloque.rename(columns=_nombres_salida_b(res, list(bloque.columns)))
    partes.append(bloque)
    return pd.concat(partes, axis=1)


# ── Resumen ──────────────────────────────────────────────────────────────

def resumir(res: ResultadoCruce, salida: pd.DataFrame) -> dict:
    cfg = res.cfg
    n = len(salida)
    orden_tipos = [cfg.tipo_exacto, T_NOMBRE_CURP, T_PARCIAL, T_SOLO_NOMBRE, SIN_COINCIDENCIA]
    conteo = salida[COL_TIPO].value_counts()
    filas = [(t, int(conteo.get(t, 0))) for t in orden_tipos if conteo.get(t, 0) > 0 or t in (cfg.tipo_exacto, SIN_COINCIDENCIA)]
    por_tipo = pd.DataFrame(filas, columns=["Tipo de coincidencia", "Registros"])
    por_tipo["% del total"] = (por_tipo["Registros"] / max(n, 1) * 100).round(1)

    encontrados = int((salida[COL_TIPO] != SIN_COINCIDENCIA).sum())
    resumen = {
        "total": n,
        "encontrados": encontrados,
        "sin_coincidencia": n - encontrados,
        "por_tipo": por_tipo,
        "distribucion_programas": None,
        "programas_frecuentes": None,
        "verificacion": None,
    }

    if COL_NUM_PROGRAMAS in salida.columns:
        hallados = salida[salida[COL_TIPO] != SIN_COINCIDENCIA]
        dist = pd.to_numeric(hallados[COL_NUM_PROGRAMAS], errors="coerce").dropna().astype(int).value_counts().sort_index()
        resumen["distribucion_programas"] = pd.DataFrame(
            {"Programas": dist.index, "Registros": dist.to_numpy()}
        )
        cols_prog = [c for c in cfg.cols_programas_b if c in res.b_unica.columns]
        if cols_prog:
            conteo_prog = (
                hallados[COL_PROGRAMAS].astype(str).str.split("; ").explode().value_counts()
            )
            filas_top = [(c, int(conteo_prog.get(c, 0))) for c in cols_prog if conteo_prog.get(c, 0)]
            top = pd.DataFrame(filas_top, columns=["Programa", "Registros"]).sort_values(
                ["Registros", "Programa"], ascending=[False, True]
            )
            resumen["programas_frecuentes"] = top.reset_index(drop=True)

        if cfg.col_total_b:
            nombre_total = _nombres_salida_b(res, [cfg.col_total_b])[cfg.col_total_b] if cfg.col_total_b in res.b_unica.columns else None
            if nombre_total and nombre_total in salida.columns:
                total = pd.to_numeric(hallados[nombre_total], errors="coerce")
                num = pd.to_numeric(hallados[COL_NUM_PROGRAMAS], errors="coerce")
                comparables = total.notna() & num.notna()
                resumen["verificacion"] = {
                    "columna": cfg.col_total_b,
                    "comparados": int(comparables.sum()),
                    "coinciden": int((total[comparables] == num[comparables]).sum()),
                }
    return resumen


def parametros_legibles(res: ResultadoCruce) -> list[tuple[str, str]]:
    cfg = res.cfg
    est = res.estadisticas
    filas = [
        ("Modo de llave", "CURP (con coincidencias aproximadas)" if cfg.modo == MODO_CURP else "Llave exacta"),
        ("Llave en base A", ", ".join(cfg.cols_llave_a)),
        ("Llave en base B", ", ".join(cfg.cols_llave_b)),
    ]
    if cfg.cols_nombre_a:
        filas.append(("Nombre en base A", " + ".join(cfg.cols_nombre_a)))
    if cfg.cols_nombre_b:
        filas.append(("Nombre en base B", " + ".join(cfg.cols_nombre_b)))
    if cfg.modo == MODO_CURP:
        filas.append(("Etapa nombre + fecha de nacimiento del CURP", "Sí" if cfg.buscar_nombre_y_fecha else "No"))
        filas.append(("Etapa fecha del CURP + nombre similar", f"Sí (similitud mínima {cfg.umbral_similitud:.0%})" if cfg.buscar_fecha_nombre_similar else "No"))
    filas.append(("Etapa solo nombre", "Sí" if cfg.buscar_solo_nombre else "No"))
    filas.append(("Desempate en llaves repetidas de B", cfg.col_desempate_b or "Solo la fila más completa"))
    filas.append(("Filas en base A", f"{est['filas_a']:,}"))
    filas.append(("Filas en base B", f"{est['filas_b']:,}"))
    filas.append(("Filas de B descartadas por llave repetida", f"{est['filas_b_descartadas']:,}"))
    return filas
