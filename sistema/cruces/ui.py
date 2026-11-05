"""Pestaña «Cruces de información»."""

from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from .. import estilos
from . import deteccion, exportar, lectura, motor
from .motor import (
    MODO_CURP,
    MODO_LLAVE,
    SIN_COINCIDENCIA,
    T_NOMBRE_CURP,
    T_PARCIAL,
    T_SOLO_NOMBRE,
)

FUENTE_LIMPIA = "Base limpia (pestaña Limpieza)"
FUENTE_RESULTADO = "Resultado del último cruce"
_LIMITE_FILAS_VISTA = 2000
_OPCION_NINGUNA = "— Ninguna —"


# ── Utilidades de estado ─────────────────────────────────────────────────

def _memo(clave, calcular):
    """Guarda resultados costosos (detecciones) por sesión."""
    memo = st.session_state.setdefault("cr_memo", {})
    if clave not in memo:
        memo[clave] = calcular()
    return memo[clave]


def _corto(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()[:8]


def _nombre_seguro(texto: str) -> str:
    base = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", texto)
    return re.sub(r"[^\w\-]+", "_", base).strip("_")[:40] or "base"


def _fuentes_disponibles() -> dict[str, pd.DataFrame]:
    fuentes: dict[str, pd.DataFrame] = {}
    limpia = st.session_state.get("fuente_base_limpia")
    if isinstance(limpia, pd.DataFrame) and not limpia.empty:
        fuentes[FUENTE_LIMPIA] = lectura.dataframe_a_texto(limpia)
    previo = st.session_state.get("cr_fuente_resultado")
    if isinstance(previo, pd.DataFrame) and not previo.empty:
        fuentes[FUENTE_RESULTADO] = previo
    return fuentes


# ── Paso 1: cargar bases ─────────────────────────────────────────────────

def _bloque_base(clave: str, titulo: str, ayuda: str, fuentes: dict[str, pd.DataFrame]):
    """Devuelve (DataFrame | None, firma, etiqueta) de la base elegida."""
    st.markdown(f"**{titulo}**")
    st.caption(ayuda)

    origen = "Subir archivo"
    if fuentes:
        origen = st.selectbox(
            "Origen de la base",
            ["Subir archivo", *fuentes.keys()],
            key=f"cr_origen_{clave}",
        )
    if origen != "Subir archivo":
        df = fuentes[origen]
        return df, f"fuente|{origen}|{len(df)}|{len(df.columns)}", origen

    archivo = st.file_uploader(
        f"Archivo de la {titulo.lower()}",
        type=[e.lstrip(".") for e in lectura.EXTENSIONES_VALIDAS],
        key=f"cr_archivo_{clave}",
        label_visibility="collapsed",
    )
    if archivo is None:
        return None, "", ""

    fid = getattr(archivo, "file_id", None) or f"{archivo.name}-{archivo.size}"
    hojas = _memo(("hojas", fid), lambda: lectura.listar_hojas(archivo.name, archivo.getvalue()))
    elegidas = [hojas[0]]
    if len(hojas) > 1:
        elegidas = st.multiselect(
            "Hojas a usar",
            hojas,
            default=[hojas[0]],
            key=f"cr_hojas_{clave}_{_corto(fid)}",
            help="Si eliges varias hojas se juntan en una sola tabla y se agrega la columna HOJA_ORIGEN.",
        )
        if not elegidas:
            st.warning("Elige al menos una hoja.")
            return None, "", ""

    firma = f"{fid}|{'/'.join(elegidas)}"
    guardadas = st.session_state.setdefault("cr_bases", {})
    if guardadas.get(clave, {}).get("firma") != firma:
        guardadas.pop(clave, None)  # libera memoria antes de leer la nueva
        with st.spinner(f"Leyendo {archivo.name}…"):
            datos = archivo.getvalue()
            tablas = []
            for hoja in elegidas:
                t = lectura.leer_tabla(archivo.name, datos, hoja if lectura.es_excel(archivo.name) else None)
                if len(elegidas) > 1:
                    t["HOJA_ORIGEN"] = hoja
                tablas.append(t)
            df = tablas[0] if len(tablas) == 1 else pd.concat(tablas, ignore_index=True).fillna("")
        guardadas[clave] = {"firma": firma, "df": df}
    return guardadas[clave]["df"], firma, archivo.name


def _paso_cargar():
    estilos.paso(1, "Carga las dos bases", "La base A es la lista que quieres revisar. La base B es donde se busca a esas personas.")
    fuentes = _fuentes_disponibles()
    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        a, firma_a, nombre_a = _bloque_base(
            "a", "Base A", "Por ejemplo, un padrón de afines o una lista de solicitantes.", fuentes
        )
    with col_b:
        b, firma_b, nombre_b = _bloque_base(
            "b", "Base B", "Por ejemplo, la base de trazabilidad con los programas recibidos.", fuentes
        )
    for df, col, nombre in ((a, col_a, nombre_a), (b, col_b, nombre_b)):
        if df is not None:
            with col:
                st.caption(f"{nombre} · {len(df):,} filas · {len(df.columns)} columnas")
                with st.expander("Ver primeras filas"):
                    st.dataframe(df.head(8), hide_index=True, width="stretch")
    return a, firma_a, nombre_a, b, firma_b, nombre_b


# ── Paso 2: llaves ───────────────────────────────────────────────────────

def _indice(opciones: list[str], preferida: str | None) -> int:
    return opciones.index(preferida) if preferida in opciones else 0


def _estadistica_curp(df: pd.DataFrame, columna: str, firma: str) -> tuple[int, int]:
    def calcular():
        from .normalizacion import normalizar_curp, serie_normalizada

        limpias = serie_normalizada(df[columna], normalizar_curp)
        return len(limpias), int(limpias.map(motor._curp_utilizable).sum())

    return _memo(("curp", firma, columna), calcular)


def _paso_llaves(a, firma_a, b, firma_b):
    estilos.paso(
        2,
        "Indica cómo se identifican las personas",
        "Elige la columna que se usa para encontrar a cada persona en la otra base.",
    )
    sfx_a, sfx_b = _corto(firma_a), _corto(firma_b)
    modo_txt = st.radio(
        "Tipo de llave",
        ["CURP", "Otra llave"],
        horizontal=True,
        key="cr_modo",
        captions=[
            "Recomendado para personas. Tolera errores de captura usando el nombre y la fecha de nacimiento.",
            "Folio, RFC, clave de elector, teléfono… Solo coincide cuando el valor es idéntico.",
        ],
    )
    modo = MODO_CURP if modo_txt == "CURP" else MODO_LLAVE
    cols_a, cols_b = list(a.columns), list(b.columns)
    col_izq, col_der = st.columns(2, gap="large")

    if modo == MODO_CURP:
        sug_a = _memo(("sug_curp", firma_a), lambda: deteccion.sugerir_columna_curp(a))
        sug_b = _memo(("sug_curp", firma_b), lambda: deteccion.sugerir_columna_curp(b))
        with col_izq:
            curp_a = st.selectbox("Columna de CURP en la base A", cols_a, index=_indice(cols_a, sug_a), key=f"cr_curp_a_{sfx_a}")
            total, ok = _estadistica_curp(a, curp_a, firma_a)
            st.caption(f"{ok:,} de {total:,} filas tienen una CURP utilizable.")
        with col_der:
            curp_b = st.selectbox("Columna de CURP en la base B", cols_b, index=_indice(cols_b, sug_b), key=f"cr_curp_b_{sfx_b}")
            total, ok = _estadistica_curp(b, curp_b, firma_b)
            st.caption(f"{ok:,} de {total:,} filas tienen una CURP utilizable.")
        llave_a, llave_b = [curp_a], [curp_b]
    else:
        with col_izq:
            llave_a = st.multiselect(
                "Columna(s) llave en la base A", cols_a, key=f"cr_llave_a_{sfx_a}",
                help="Si eliges varias columnas se combinan en una sola llave.",
            )
        with col_der:
            llave_b = st.multiselect(
                "Columna(s) llave en la base B", cols_b, key=f"cr_llave_b_{sfx_b}",
                help="Elige el mismo número de columnas y en el mismo orden que en la base A.",
            )

    sug_nom_a = _memo(("sug_nom", firma_a), lambda: deteccion.sugerir_columnas_nombre(a))
    sug_nom_b = _memo(("sug_nom", firma_b), lambda: deteccion.sugerir_columnas_nombre(b))
    requiere_nombre = modo == MODO_CURP
    etiqueta = "Columnas del nombre" + ("" if requiere_nombre else " (opcional)")
    with col_izq:
        nom_a = st.multiselect(
            f"{etiqueta} en la base A", cols_a, default=sug_nom_a, key=f"cr_nom_a_{sfx_a}",
            help="Se comparan sin importar el orden ni los acentos. Puedes elegir nombre y apellidos por separado.",
        )
    with col_der:
        nom_b = st.multiselect(
            f"{etiqueta} en la base B", cols_b, default=sug_nom_b, key=f"cr_nom_b_{sfx_b}",
            help="Se comparan sin importar el orden ni los acentos. Puedes elegir nombre y apellidos por separado.",
        )
    return modo, llave_a, llave_b, nom_a, nom_b


# ── Paso 3: opciones ─────────────────────────────────────────────────────

def _paso_opciones(b, firma_b, modo, nombre_b):
    estilos.paso(3, "Ajusta la búsqueda", "Los valores sugeridos funcionan para la mayoría de los cruces.")
    sfx_b = _corto(firma_b)
    opciones = {}

    with st.expander("Opciones de búsqueda", expanded=False):
        if modo == MODO_CURP:
            opciones["buscar_nombre_y_fecha"] = st.checkbox(
                "Buscar por nombre + fecha de nacimiento cuando la CURP tiene errores",
                value=True, key="cr_etapa2",
                help="Encuentra personas cuyo CURP está mal escrito pero el nombre y la fecha de nacimiento coinciden.",
            )
            opciones["buscar_fecha_nombre_similar"] = st.checkbox(
                "Buscar por fecha de nacimiento + nombre parecido",
                value=True, key="cr_etapa3",
                help="Para nombres con abreviaturas o letras de más. Estas coincidencias se muestran para que las confirmes.",
            )
            opciones["umbral_similitud"] = st.slider(
                "Parecido mínimo entre nombres", 60, 100, 85, 1, format="%d%%",
                key="cr_umbral", disabled=not opciones["buscar_fecha_nombre_similar"],
            ) / 100
        else:
            opciones.update(buscar_nombre_y_fecha=False, buscar_fecha_nombre_similar=False, umbral_similitud=0.85)
        opciones["buscar_solo_nombre"] = st.checkbox(
            "Buscar solo por nombre (menos seguro)",
            value=False, key="cr_etapa4",
            help="Empareja nombres idénticos aunque la CURP no coincida. Puede confundir homónimos, por eso queda sin aceptar hasta que lo confirmes.",
        )

        st.divider()
        cols_b = list(b.columns)
        sug_desempate = _memo(("sug_desempate", firma_b), lambda: deteccion.sugerir_columna_desempate(b))
        opciones_desempate = [_OPCION_NINGUNA, *cols_b]
        elegido = st.selectbox(
            "Si una persona aparece varias veces en la base B, quedarme con la fila más completa y, en empate, la de mayor…",
            opciones_desempate,
            index=opciones_desempate.index(sug_desempate) if sug_desempate in opciones_desempate else 0,
            key=f"cr_desempate_{sfx_b}",
        )
        opciones["col_desempate_b"] = None if elegido == _OPCION_NINGUNA else elegido

        st.divider()
        todas = st.radio(
            "Columnas de la base B que se agregan al resultado",
            ["Todas", "Elegir columnas"], horizontal=True, key=f"cr_todas_{sfx_b}",
        )
        opciones["cols_traer_b"] = None
        if todas == "Elegir columnas":
            opciones["cols_traer_b"] = st.multiselect(
                "Columnas a traer", cols_b, default=[], key=f"cr_traer_{sfx_b}",
                label_visibility="collapsed", placeholder="Elige las columnas que quieres traer",
            )

        etiqueta = st.text_input(
            "Etiqueta para columnas repetidas",
            value="BASE_B", key="cr_etiqueta", max_chars=24,
            help="Si las dos bases tienen una columna con el mismo nombre, la de la base B lleva esta etiqueta. Ejemplo: CURP_BASE_B.",
        )
        opciones["etiqueta_b"] = etiqueta or "BASE_B"

        progs = _memo(("progs", firma_b), lambda: deteccion.detectar_columnas_programas(b))
        opciones["resumir_programas"] = False
        opciones["cols_programas_b"] = []
        opciones["incluir_cols_programas"] = True
        opciones["col_total_b"] = None
        if len(progs) >= 3:
            st.divider()
            st.markdown(f"**Programas**  \nSe detectaron {len(progs)} columnas con valores SI / NO en la base B.")
            resumir = st.checkbox(
                "Resumir en PROGRAMAS_BENEFICIARIO y NUM_PROGRAMAS",
                value=True, key=f"cr_resumir_{sfx_b}",
                help="Agrega la lista de programas en los que aparece cada persona y cuántos son.",
            )
            opciones["resumir_programas"] = resumir
            if resumir:
                opciones["cols_programas_b"] = st.multiselect(
                    "Columnas que cuentan como programas", progs, default=progs, key=f"cr_progs_{sfx_b}",
                )
                opciones["incluir_cols_programas"] = st.checkbox(
                    "Conservar también las columnas SI / NO una por una",
                    value=True, key=f"cr_conservar_progs_{sfx_b}",
                )
                sug_total = _memo(("sug_total", firma_b), lambda: deteccion.sugerir_columna_total(b))
                opc_total = [_OPCION_NINGUNA, *cols_b]
                total = st.selectbox(
                    "Columna con el total de apoyos (para verificar el conteo)",
                    opc_total,
                    index=opc_total.index(sug_total) if sug_total in opc_total else 0,
                    key=f"cr_total_{sfx_b}",
                )
                opciones["col_total_b"] = None if total == _OPCION_NINGUNA else total
    return opciones


def _construir_configuracion(modo, llave_a, llave_b, nom_a, nom_b, opciones) -> motor.Configuracion:
    return motor.Configuracion(
        modo=modo,
        cols_llave_a=list(llave_a),
        cols_llave_b=list(llave_b),
        cols_nombre_a=list(nom_a),
        cols_nombre_b=list(nom_b),
        buscar_nombre_y_fecha=opciones["buscar_nombre_y_fecha"],
        buscar_fecha_nombre_similar=opciones["buscar_fecha_nombre_similar"],
        umbral_similitud=opciones["umbral_similitud"],
        buscar_solo_nombre=opciones["buscar_solo_nombre"],
        col_desempate_b=opciones["col_desempate_b"],
        etiqueta_b=opciones["etiqueta_b"],
        cols_traer_b=opciones["cols_traer_b"],
        resumir_programas=opciones["resumir_programas"],
        cols_programas_b=opciones["cols_programas_b"],
        incluir_cols_programas=opciones["incluir_cols_programas"],
        col_total_b=opciones["col_total_b"],
    )


# ── Paso 4: ejecutar ─────────────────────────────────────────────────────

def _paso_ejecutar(a, b, cfg, firma_actual, nombre_a, nombre_b):
    hecho = "cr_resultado" in st.session_state
    estilos.paso(4, "Cruza las bases", "El cruce se hace en tu sesión; los archivos no se guardan en ningún lado.", hecho=hecho)
    problemas = motor.validar_configuracion(a, b, cfg)
    for p in problemas:
        st.warning(p)
    if st.button("Cruzar bases", type="primary", icon=":material/join_inner:", disabled=bool(problemas), key="cr_ejecutar"):
        with st.spinner("Buscando coincidencias…"):
            try:
                res = motor.ejecutar_cruce(a, b, cfg)
            except ValueError as error:
                st.error(str(error))
                return
        ejecuciones = st.session_state.get("cr_ejecuciones", 0) + 1
        st.session_state["cr_ejecuciones"] = ejecuciones
        st.session_state["cr_resultado"] = {
            "res": res, "firma": firma_actual, "nombre_a": nombre_a, "nombre_b": nombre_b, "n": ejecuciones,
        }
        st.session_state.pop("cr_descarga", None)
        st.session_state.pop("cr_salida_cache", None)


def _etiqueta(tipo: str) -> str:
    return tipo.capitalize().replace("Curp", "CURP")


# ── Paso 5: resultado ────────────────────────────────────────────────────

def _tabla_revision(res: motor.ResultadoCruce, n_ejecucion: int) -> set[int] | None:
    emp = res.emparejamientos
    rev = emp[emp["revisar"]]
    if rev.empty:
        return None
    st.markdown(f"**Coincidencias por confirmar ({len(rev)})**")
    st.caption(
        "Estas filas se emparejaron por nombre parecido o solo por nombre. "
        "Compara los datos y desmarca las que no sean la misma persona."
    )
    tabla = pd.DataFrame(
        {
            "Aceptar": rev["aceptar_defecto"].to_numpy(),
            "Fila en A": rev["fila_a"].to_numpy(),
            "Tipo": rev["tipo"].to_numpy(),
            "Parecido": (rev["similitud"] * 100).round().astype(int).to_numpy(),
            "Nombre en A": rev["nombre_a"].to_numpy(),
            "Nombre en B": rev["nombre_b"].to_numpy(),
            "Llave en A": rev["llave_a"].to_numpy(),
            "Llave en B": rev["llave_b"].to_numpy(),
            "Fila en B": rev["fila_b"].to_numpy(),
        }
    )
    editada = st.data_editor(
        tabla,
        hide_index=True,
        width="stretch",
        disabled=[c for c in tabla.columns if c != "Aceptar"],
        column_config={
            "Aceptar": st.column_config.CheckboxColumn("Aceptar", width="small"),
            "Parecido": st.column_config.NumberColumn("Parecido", format="%d%%", width="small"),
        },
        key=f"cr_editor_{n_ejecucion}",
    )
    return set(int(f) for f in editada.loc[editada["Aceptar"], "Fila en A"])


def _vista_tabla(salida: pd.DataFrame, n_ejecucion: int):
    vista = st.segmented_control(
        "Ver", ["Cruce completo", "Encontrados", "Sin coincidencia"],
        default="Cruce completo", key=f"cr_vista_{n_ejecucion}", label_visibility="collapsed",
    ) or "Cruce completo"
    if vista == "Encontrados":
        df = salida[salida[motor.COL_TIPO] != SIN_COINCIDENCIA]
    elif vista == "Sin coincidencia":
        df = salida[salida[motor.COL_TIPO] == SIN_COINCIDENCIA]
    else:
        df = salida
    st.dataframe(df.head(_LIMITE_FILAS_VISTA), hide_index=True, width="stretch", height=380)
    if len(df) > _LIMITE_FILAS_VISTA:
        st.caption(f"Se muestran las primeras {_LIMITE_FILAS_VISTA:,} de {len(df):,} filas. El archivo descargado trae todas.")
    else:
        st.caption(f"{len(df):,} filas.")


def _mostrar_resultado(r: dict, firma_actual: str):
    res: motor.ResultadoCruce = r["res"]
    n = r["n"]
    estilos.paso(5, "Revisa el resultado", "Confirma las coincidencias dudosas y descarga el archivo.", hecho=True)
    if r["firma"] != firma_actual:
        st.info("Cambiaste algo después del último cruce. Vuelve a cruzar para actualizar el resultado.")

    resumen_contenedor = st.container()
    aceptados = _tabla_revision(res, n)
    clave_cache = (n, None if aceptados is None else frozenset(aceptados))
    cache = st.session_state.get("cr_salida_cache")
    if cache and cache["clave"] == clave_cache:
        salida, resumen = cache["salida"], cache["resumen"]
    else:
        salida = motor.construir_salida(res, aceptados)
        resumen = motor.resumir(res, salida)
        st.session_state["cr_salida_cache"] = {"clave": clave_cache, "salida": salida, "resumen": resumen}
        st.session_state["cr_fuente_resultado"] = salida

    with resumen_contenedor:
        total = resumen["total"]
        estilos.ficha(
            [
                ("Registros en la base A", f"{total:,}", ""),
                ("Encontrados en la base B", f"{resumen['encontrados']:,}", f"{resumen['encontrados'] / max(total, 1):.0%}"),
                ("Sin coincidencia", f"{resumen['sin_coincidencia']:,}", f"{resumen['sin_coincidencia'] / max(total, 1):.0%}"),
            ]
        )

        colores = estilos.COLORES_TIPO
        mapa_color = {
            res.cfg.tipo_exacto: colores["exacta"],
            T_NOMBRE_CURP: colores["fecha"],
            T_PARCIAL: colores["parcial"],
            T_SOLO_NOMBRE: colores["nombre"],
            SIN_COINCIDENCIA: colores["sin"],
        }
        por_tipo = resumen["por_tipo"]
        estilos.barra_segmentada(
            "Cómo se encontró cada registro",
            [(_etiqueta(fila["Tipo de coincidencia"]), int(fila["Registros"]), mapa_color[fila["Tipo de coincidencia"]]) for _, fila in por_tipo.iterrows()],
        )

        if res.advertencias:
            with st.expander(f"Avisos del cruce ({len(res.advertencias)})", expanded=True):
                for aviso in res.advertencias:
                    st.markdown(f"- {aviso}")

    st.markdown("&nbsp;")
    _vista_tabla(salida, n)

    if resumen["distribucion_programas"] is not None:
        st.markdown("**Programas de las personas encontradas**")
        izq, der = st.columns(2, gap="large")
        with izq:
            st.caption("Número de programas por persona")
            st.dataframe(resumen["distribucion_programas"], hide_index=True, width="stretch")
        with der:
            st.caption("Programas más frecuentes")
            if resumen["programas_frecuentes"] is not None:
                st.dataframe(resumen["programas_frecuentes"].head(15), hide_index=True, width="stretch")
        verif = resumen["verificacion"]
        if verif:
            texto = f"NUM_PROGRAMAS coincide con «{verif['columna']}» en {verif['coinciden']:,} de {verif['comparados']:,} filas."
            if verif["coinciden"] == verif["comparados"]:
                st.success(texto, icon=":material/check_circle:")
            else:
                st.warning(texto + " Revisa las filas que no coinciden.", icon=":material/warning:")

    _descargas(res, salida, resumen, r, clave_cache)


def _descargas(res, salida, resumen, r, clave_cache):
    st.markdown("**Descargar**")
    nombre = f"Cruce_{_nombre_seguro(r['nombre_a'])}_con_{_nombre_seguro(r['nombre_b'])}"
    firma = clave_cache
    listo = st.session_state.get("cr_descarga")
    if not listo or listo["firma"] != firma:
        if st.button("Preparar archivos", icon=":material/inventory_2:", key="cr_preparar"):
            with st.spinner("Armando el Excel…"):
                emp = motor.emparejamientos_finales(res, None if clave_cache[1] is None else set(clave_cache[1]))
                dudosas = salida[res.emparejamientos["revisar"].to_numpy()]
                excel = exportar.a_excel(
                    salida, resumen, motor.parametros_legibles(res), res.advertencias, dudosas
                )
                csv = exportar.a_csv(salida)
            st.session_state["cr_descarga"] = {"firma": firma, "excel": excel, "csv": csv, "nombre": nombre}
            st.rerun()
        st.caption("El Excel trae las hojas Cruce, Encontrados, Sin coincidencia y Resumen.")
        return
    izq, der = st.columns(2)
    with izq:
        st.download_button(
            "Descargar Excel (todas las hojas)", listo["excel"], file_name=f"{listo['nombre']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", icon=":material/download:", width="stretch", key="cr_dl_excel",
        )
    with der:
        st.download_button(
            "Descargar CSV (cruce completo)", listo["csv"], file_name=f"{listo['nombre']}.csv",
            mime="text/csv", icon=":material/download:", width="stretch", key="cr_dl_csv",
        )


# ── Entrada ──────────────────────────────────────────────────────────────

def _ayuda():
    with st.expander("¿Cómo funciona el cruce?"):
        st.markdown(
            """
**Base A** es la lista que quieres revisar y **base B** es donde se busca. El resultado conserva todas las
filas de A y agrega las columnas de B cuando encuentra a la persona.

Cada fila de A se busca en B por etapas, de la más segura a la más flexible:

1. **CURP exacta.** Las dos CURP son iguales.
2. **Nombre + fecha de nacimiento.** El nombre es el mismo y la fecha de nacimiento del CURP también (sirve cuando el resto del CURP tiene errores).
3. **Fecha de nacimiento + nombre parecido.** Para nombres abreviados o con letras de más. Tú confirmas cada caso.
4. **Solo nombre.** Apagada por defecto. Tú confirmas cada caso.

Si una persona aparece varias veces en B, se usa la fila más completa. Ninguno de los archivos que subes se modifica.
            """
        )


def render() -> None:
    estilos.encabezado_herramienta(
        "Cruces de información",
        "Compara una lista de personas contra otra base y trae los datos que falten, por ejemplo qué programas recibe cada persona.",
    )
    _ayuda()
    a, firma_a, nombre_a, b, firma_b, nombre_b = _paso_cargar()

    if a is None or b is None:
        estilos.estado_vacio(
            "Faltan archivos",
            "Sube la base A y la base B (o elige una base ya cargada) para seguir con las llaves y la búsqueda.",
        )
        return

    modo, llave_a, llave_b, nom_a, nom_b = _paso_llaves(a, firma_a, b, firma_b)
    opciones = _paso_opciones(b, firma_b, modo, nombre_b)
    cfg = _construir_configuracion(modo, llave_a, llave_b, nom_a, nom_b, opciones)
    firma_actual = _corto(f"{firma_a}|{firma_b}|{cfg!r}")
    _paso_ejecutar(a, b, cfg, firma_actual, nombre_a, nombre_b)

    resultado = st.session_state.get("cr_resultado")
    if resultado:
        _mostrar_resultado(resultado, firma_actual)
