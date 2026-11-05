"""Pestaña «Limpieza de bases» (antes: Limpiador de Programas Sociales)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import estilos
from .acomodador import KEY_ORDEN as KEY_ORDEN_COLUMNAS
from .acomodador import mostrar_acomodador
from .archivos import (
    a_csv,
    a_parquet,
    a_xlsx,
    cargar_archivo,
    cargar_estados_municipios,
    contar_duplicados,
    df_a_geojson,
    limpiar_nulos,
)
from .georeferenciacion import (
    CAPAS_GEOJSON,
    COLUMNAS_DISPONIBLES,
    PROVEEDORES,
    GeoReferenciador,
    calcular_secciones_por_colonia,
)
from .limpieza import LimpiadorProgramasSociales
from .mapa import mostrar_mapa_geo

_CLAVES_RESULTADO = (
    "_resultado_procesado",
    "_mapa_correcciones",
    KEY_ORDEN_COLUMNAS,
    "_descarga_datos",
    "_descarga_formato",
)


# ── Paso 1: carga ────────────────────────────────────────────────────────

def _metricas_carga(df: pd.DataFrame) -> None:
    total = len(df)
    duplicados = contar_duplicados(df)
    estilos.ficha(
        [
            ("Total de registros", f"{total:,}", ""),
            ("Registros duplicados", f"{duplicados:,}", ""),
            ("Registros únicos", f"{total - duplicados:,}", ""),
        ]
    )
    with st.expander("Ver vista previa de los datos originales"):
        st.dataframe(df.head(10), hide_index=True, width="stretch")


# ── Paso 2: ajustes ──────────────────────────────────────────────────────

def _columnas_eliminar(df: pd.DataFrame) -> list[str]:
    with st.expander("Columnas a eliminar (opcional)", expanded=False):
        st.caption(
            "Elige las columnas que quieres excluir antes de limpiar. Si eliminas una que otro paso "
            "necesita, se muestra un aviso y el proceso continúa."
        )
        columnas = st.multiselect(
            "Columnas a eliminar",
            options=df.columns.tolist(),
            default=[],
            placeholder="Ninguna: se conservan todas las columnas",
            label_visibility="collapsed",
            key="li_columnas_eliminar",
        )
        if columnas:
            st.warning(f"Se eliminarán {len(columnas)} columna(s): {', '.join(columnas)}")
    return columnas


def _estado_municipio() -> tuple[bool, str, str]:
    """Estado y municipio opcionales para toda la base.

    Devuelve (sobrescribir, estado, municipio). Con `sobrescribir` activo, los valores
    elegidos (en MAYÚSCULAS) reemplazan las columnas ESTADO/MUNICIPIO de la base.
    """
    estado_defecto, municipio_defecto = "Querétaro", "Corregidora"
    catalogo = cargar_estados_municipios()

    with st.expander("Estado y municipio de la base", expanded=False):
        sobrescribir = st.checkbox(
            "Asignar estado y municipio a toda la base",
            value=False,
            key="_usar_estado_municipio",
            help=(
                "Reemplaza las columnas Municipio y Estado, si existen, con el estado y el municipio "
                "elegidos para todos los registros. Si lo dejas apagado, se conservan las columnas del archivo."
            ),
        )
        if not sobrescribir:
            st.caption("Apagado: se conservan las columnas Estado y Municipio que traiga el archivo.")
            return False, "", ""

        if not catalogo:
            st.warning(
                "No se encontró el catálogo de estados y municipios (json/estados_municipios.json). "
                f"Se usarán los valores por defecto: {municipio_defecto}, {estado_defecto}."
            )
            return True, estado_defecto.upper(), municipio_defecto.upper()

        estados = list(catalogo.keys())
        idx_estado = estados.index(estado_defecto) if estado_defecto in estados else 0
        col_estado, col_municipio = st.columns(2)
        with col_estado:
            estado = st.selectbox("Estado", options=estados, index=idx_estado, key="_sel_estado")
        municipios = catalogo.get(estado, [])
        idx_municipio = municipios.index(municipio_defecto) if municipio_defecto in municipios else 0
        with col_municipio:
            municipio = (
                st.selectbox("Municipio", options=municipios, index=idx_municipio, key="_sel_municipio")
                if municipios
                else ""
            )
    return True, str(estado).strip().upper(), str(municipio).strip().upper()


def _mapeo_columnas(df: pd.DataFrame) -> dict:
    mapeo: dict = {}
    with st.expander("Mapeo de columnas (homologación)", expanded=False):
        st.caption("Define cómo se relacionan las columnas de tu archivo con los campos estándar del sistema.")
        modo = st.radio(
            "Detección de columnas",
            options=["Automático", "Manual"],
            horizontal=True,
            key="li_modo_mapeo",
            help=(
                "**Automático:** reconoce columnas por nombre conocido (p. ej. 'NumExt' → NUM\\_EXT). "
                "**Manual:** tú indicas qué columna de tu archivo corresponde a cada campo estándar."
            ),
        )
        if modo == "Manual":
            mapeo = _mapeo_manual(df)
    return mapeo


def _mapeo_manual(df: pd.DataFrame) -> dict:
    mapeo: dict = {}
    opciones = ["—"] + df.columns.tolist()

    campos_persona = {
        "NOMBRE(S)_DE_PILA", "AP_PATERNO", "AP_MATERNO", "CURP",
        "GENERO", "FECHA_NACIMIENTO", "EDAD", "TELEFONO", "CELULAR", "CORREO",
    }
    campos_direccion = {"CALLE", "NUM_EXT", "NUM_INT", "COLONIA", "CODIGO_POSTAL", "DELEGACION", "ESTADO", "MUNICIPIO"}

    objetivo = LimpiadorProgramasSociales.COLUMNAS_OBJETIVO
    items_persona = [(k, v) for k, v in objetivo.items() if k in campos_persona]
    items_direccion = [(k, v) for k, v in objetivo.items() if k in campos_direccion]

    st.caption("Elige qué columna de tu archivo corresponde a cada campo. Las que dejes en «—» se omiten.")

    st.markdown("**Datos de la persona**")
    izq, der = st.columns(2)
    for i, (col_std, desc) in enumerate(items_persona):
        with (izq if i % 2 == 0 else der):
            sel = st.selectbox(desc, options=opciones, key=f"mapeo_{col_std}", help=f"Campo estándar de destino: `{col_std}`")
            if sel != "—":
                mapeo[sel] = col_std

    st.markdown("**Dirección**")
    usar_completa = st.checkbox(
        "Mi archivo trae la dirección completa en una sola columna, separada por comas",
        key="usar_dir_completa",
        help="Formato esperado: CALLE, NUM_EXT, NUM_INT, COLONIA, CODIGO_POSTAL.",
    )
    if usar_completa:
        sel = st.selectbox(
            "Dirección completa", options=opciones, key="mapeo_DIRECCION_COMPLETA",
            help="Columna con la dirección en formato: CALLE, NUM_EXT, NUM_INT, COLONIA, CODIGO_POSTAL",
        )
        if sel != "—":
            mapeo[sel] = "DIRECCION_COMPLETA"
            st.caption(
                f"**{sel}** se usará como `DIRECCION_COMPLETA`. Las columnas CALLE, NUM_EXT, NUM_INT, "
                "COLONIA y CODIGO_POSTAL se generan a partir de ella."
            )
    else:
        izq2, der2 = st.columns(2)
        for i, (col_std, desc) in enumerate(items_direccion):
            with (izq2 if i % 2 == 0 else der2):
                sel = st.selectbox(desc, options=opciones, key=f"mapeo_{col_std}", help=f"Campo estándar de destino: `{col_std}`")
                if sel != "—":
                    mapeo[sel] = col_std

    if mapeo:
        st.info(f"{len(mapeo)} columna(s) mapeada(s): " + ", ".join(f"{k} → {v}" for k, v in mapeo.items()))
    return mapeo


def _config_georeferenciacion() -> tuple[bool, str, list]:
    """Devuelve (aplicar_geo, proveedor, columnas_seleccionadas)."""
    with st.expander("Georreferenciación", expanded=False):
        aplicar = st.checkbox(
            "Aplicar georreferenciación",
            key="li_aplicar_geo",
            help=(
                "Convierte las direcciones en coordenadas y asigna sección electoral y otras capas. "
                "Puede tardar varios minutos según el número de direcciones distintas."
            ),
        )
        proveedor = "ArcGIS"
        columnas = list(COLUMNAS_DISPONIBLES.keys())
        if aplicar:
            proveedor = st.radio(
                "Proveedor de geocodificación",
                options=list(PROVEEDORES.keys()),
                captions=[v["descripcion"] for v in PROVEEDORES.values()],
                index=0,
                horizontal=True,
                key="li_proveedor_geo",
            )
            st.markdown("**Columnas que se agregan por cruce espacial**")
            st.caption(
                "Capas disponibles: "
                + " · ".join(f"**{k}**: {', '.join(v['columnas'].keys())}" for k, v in CAPAS_GEOJSON.items())
            )
            columnas = st.multiselect(
                "Columnas geográficas",
                options=list(COLUMNAS_DISPONIBLES.keys()),
                key="li_columnas_geo",
                help="Quitar las capas que no necesitas acelera el proceso.",
            )
    return aplicar, proveedor, columnas


def _config_cruce_colonias() -> tuple[bool, str]:
    """Devuelve (aplicar_cruce, anio_secciones)."""
    with st.expander("Secciones electorales por colonia", expanded=False):
        aplicar = st.checkbox(
            "Verificar secciones por colonia",
            key="li_aplicar_cruce_colonias",
            help=(
                "Busca en qué secciones electorales cae el polígono de cada colonia. Requiere una columna COLONIA "
                "y agrega SECCIONES_DE_COLONIA con la lista de secciones."
            ),
        )
        anio = "2024"
        if aplicar:
            anio = st.radio(
                "Secciones electorales a usar",
                options=["2024", "2025"],
                horizontal=True,
                key="li_anio_secciones",
                help="Año de las secciones electorales contra las que se cruzan las colonias.",
            )
    return aplicar, anio


# ── Paso 3: procesamiento ────────────────────────────────────────────────

def _ejecutar_procesamiento(
    df, columnas_a_eliminar, mapeo_personalizado, aplicar_geo, proveedor_geo, columnas_geo,
    aplicar_cruce_colonias, anio_secciones, estado, municipio, sobrescribir_estado_municipio,
) -> dict:
    if columnas_a_eliminar:
        df = df.drop(columns=columnas_a_eliminar)

    with st.status("Limpiando los datos…", expanded=True) as status:
        limpiador = LimpiadorProgramasSociales(
            df,
            mapeo_columnas=mapeo_personalizado,
            estado=estado,
            municipio=municipio,
            sobrescribir_estado_municipio=sobrescribir_estado_municipio,
        )
        df, advertencias = limpiador.ejecutar_limpieza()

        registros_antes = len(df)
        subset_dedup = ["CURP"] if "CURP" in df.columns else None
        df = df.drop_duplicates(subset=subset_dedup)
        duplicados_eliminados = registros_antes - len(df)
        status.update(label="Limpieza terminada", state="complete", expanded=False)

    msg_geo = ""
    if aplicar_geo:
        df, msg_geo = _ejecutar_georeferenciacion(df, proveedor_geo, columnas_geo)

    msg_cruce = ""
    if aplicar_cruce_colonias:
        df, msg_cruce = _ejecutar_cruce_colonias(df, anio_secciones)

    return {
        "df": df,
        "geo_aplicado": aplicar_geo,
        "registros_antes": registros_antes,
        "duplicados_eliminados": duplicados_eliminados,
        "advertencias": advertencias,
        "msg_geo": msg_geo,
        "msg_cruce": msg_cruce,
    }


def _ejecutar_georeferenciacion(df: pd.DataFrame, proveedor: str, columnas_deseadas: list[str]):
    st.markdown("**Georreferenciación**")
    progreso_bar = st.progress(0, text="Iniciando geocodificación…")
    texto_progreso = st.empty()

    def _progreso(actual, total, direccion):
        progreso_bar.progress(actual / total, text=f"Geocodificando {actual}/{total}")
        texto_progreso.caption(f"Procesando: {direccion[:80]}…")

    geo = GeoReferenciador(proveedor=proveedor, columnas_deseadas=columnas_deseadas)
    geo.cargar_geojson()
    df = geo.geocodificar_direcciones(df, callback=_progreso)
    progreso_bar.progress(1.0, text="Geocodificación completada")

    texto_progreso.caption("Calculando secciones electorales…")
    df = geo.asignar_seccion_electoral(df)
    texto_progreso.caption("")

    geocodificados = int(df["LATITUD"].notna().sum())
    asignadas = {col: int(df[col].notna().sum()) for col in columnas_deseadas if col in df.columns}
    detalle = ", ".join(f"{col}: {n}" for col, n in asignadas.items())
    msg = (
        f"Georreferenciación completada: {geocodificados}/{len(df)} registros geocodificados. "
        f"Columnas asignadas: {detalle}."
    )
    return df, msg


def _ejecutar_cruce_colonias(df: pd.DataFrame, anio_secciones: str):
    if "COLONIA" not in df.columns:
        return df, "No se encontró la columna COLONIA en la base; se omitió el cruce."

    with st.status("Calculando secciones por colonia…", expanded=True) as status:
        df = calcular_secciones_por_colonia(df, anio_secciones=anio_secciones, col_colonia="COLONIA")
        status.update(label="Cruce de colonias y secciones terminado", state="complete", expanded=False)

    con_secciones = int((df["SECCIONES_DE_COLONIA"] != "").sum())
    multi_seccion = int(df["SECCIONES_DE_COLONIA"].str.contains(",").sum())
    msg = (
        f"Colonias y secciones ({anio_secciones}): {con_secciones}/{len(df)} registros con secciones asignadas. "
        f"{multi_seccion} registros están en colonias que caen en varias secciones."
    )
    return df, msg


# ── Paso 4: resultado ────────────────────────────────────────────────────

def _resultados(res: dict) -> pd.DataFrame:
    """Muestra el resumen y devuelve el DataFrame (con correcciones y orden aplicados)."""
    df = res["df"]

    estilos.ficha(
        [
            ("Registros antes de limpiar", f"{res['registros_antes']:,}", ""),
            ("Duplicados eliminados", f"{res['duplicados_eliminados']:,}", ""),
            ("Registros finales", f"{len(df):,}", ""),
        ]
    )

    if res["advertencias"]:
        with st.expander(f"{len(res['advertencias'])} aviso(s) durante la limpieza", expanded=True):
            for aviso in res["advertencias"]:
                st.warning(aviso)

    if res["geo_aplicado"]:
        if res["msg_geo"]:
            st.success(res["msg_geo"])
        df = mostrar_mapa_geo(df)

    if res.get("msg_cruce"):
        st.info(res["msg_cruce"])

    with st.expander("Ordenar columnas", expanded=False):
        df = mostrar_acomodador(df)
    return df


# ── Paso 5: descarga ─────────────────────────────────────────────────────

_FORMATOS = {
    "CSV (.csv)": "csv",
    "Excel (.xlsx)": "xlsx",
    "Parquet (.parquet)": "parquet",
    "GeoJSON (.geojson)": "geojson",
}
_MIME = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/octet-stream",
    "geojson": "application/geo+json",
}


def _descargas(df_final: pd.DataFrame, df_geo: pd.DataFrame) -> None:
    st.dataframe(df_final.head(10), hide_index=True, width="stretch")
    st.caption("Vista previa de las primeras 10 filas.")

    formato_label = st.selectbox("Formato de descarga", options=list(_FORMATOS.keys()), key="_formato_descarga")
    formato = _FORMATOS[formato_label]

    tiene_geo = {"LATITUD", "LONGITUD"}.issubset(df_geo.columns)
    if formato == "geojson" and not tiene_geo:
        st.warning("Sin coordenadas, las geometrías quedarán vacías. Activa la georreferenciación para obtener un GeoJSON con puntos.")

    if st.button("Generar archivo", icon=":material/inventory_2:", key="_btn_generar_descarga"):
        with st.spinner("Generando archivo…"):
            if formato == "csv":
                datos = a_csv(df_final)
            elif formato == "xlsx":
                datos = a_xlsx(df_final)
            elif formato == "parquet":
                datos = a_parquet(df_final)
            else:
                datos = df_a_geojson(df_geo)
        st.session_state["_descarga_datos"] = datos
        st.session_state["_descarga_formato"] = formato

    if st.session_state.get("_descarga_formato") == formato and "_descarga_datos" in st.session_state:
        st.download_button(
            label=f"Descargar {formato_label}",
            data=st.session_state["_descarga_datos"],
            file_name=f"base_limpia.{formato}",
            mime=_MIME[formato],
            type="primary",
            icon=":material/download:",
            width="stretch",
        )


def _ayuda_csv() -> None:
    with st.expander("Ayuda: cómo abrir un CSV en Excel respetando eñes y acentos"):
        st.markdown(
            """
Si al abrir un CSV en Excel las eñes y los acentos aparecen dañados:

1. Abre Excel con un **libro en blanco** (no hagas doble clic sobre el CSV).
2. Ve a **Datos › Obtener datos › Desde un archivo › Desde el texto/CSV**.
3. Elige tu archivo y pulsa **Importar**.
4. En **Origen del archivo** elige **65001: Unicode (UTF-8)**. Si no funciona, prueba **1252: Windows (Europa occidental)**.
5. Comprueba en la vista previa que las eñes y los acentos se vean bien y que el **delimitador** sea el correcto.
6. Pulsa **Cargar**.
            """
        )


# ── Entrada ──────────────────────────────────────────────────────────────

def render() -> None:
    estilos.encabezado_herramienta(
        "Limpieza y georreferenciación",
        "Ordena y normaliza una base de programas sociales (nombres, CURP, teléfonos, direcciones) y, si lo necesitas, le agrega coordenadas y secciones electorales.",
    )

    estilos.paso(1, "Sube la base", "Acepta Excel, CSV o Parquet.", hecho="_resultado_procesado" in st.session_state)
    archivo = st.file_uploader(
        "Archivo a limpiar",
        type=["xlsx", "csv", "parquet"],
        key="li_archivo",
        label_visibility="collapsed",
    )
    if archivo is None:
        estilos.estado_vacio("Falta el archivo", "Sube una base para ver sus datos y elegir cómo limpiarla.")
        _ayuda_csv()
        return

    try:
        nombre = archivo.name
        df = cargar_archivo(nombre, archivo.getvalue())

        if st.session_state.get("_ultimo_archivo") != nombre:
            for clave in _CLAVES_RESULTADO:
                st.session_state.pop(clave, None)
            st.session_state.pop("fuente_base_limpia", None)
            st.session_state["_ultimo_archivo"] = nombre

        st.caption(f"{nombre} · cargado correctamente")
        _metricas_carga(df)

        estilos.paso(2, "Elige los ajustes", "Todo es opcional. Sin cambios, la base se limpia con los valores estándar.")
        columnas_a_eliminar = _columnas_eliminar(df)
        sobrescribir_em, estado_sel, municipio_sel = _estado_municipio()
        mapeo_personalizado = _mapeo_columnas(df)
        aplicar_geo, proveedor_geo, columnas_geo = _config_georeferenciacion()
        aplicar_cruce, anio_secciones = _config_cruce_colonias()

        estilos.paso(3, "Limpia la base", hecho="_resultado_procesado" in st.session_state)
        if st.button("Iniciar limpieza", type="primary", icon=":material/cleaning_services:", key="li_iniciar"):
            resultado = _ejecutar_procesamiento(
                df, columnas_a_eliminar, mapeo_personalizado,
                aplicar_geo, proveedor_geo, columnas_geo,
                aplicar_cruce, anio_secciones,
                estado_sel, municipio_sel, sobrescribir_em,
            )
            st.session_state["_resultado_procesado"] = resultado
            for clave in ("_mapa_correcciones", "_descarga_datos", "_descarga_formato"):
                st.session_state.pop(clave, None)

        if "_resultado_procesado" in st.session_state:
            estilos.paso(4, "Revisa el resultado", hecho=True)
            df_editado = _resultados(st.session_state["_resultado_procesado"])
            df_final = limpiar_nulos(df_editado)
            st.session_state["fuente_base_limpia"] = df_final

            estilos.paso(5, "Descarga la base limpia", "También queda disponible como base en la pestaña Cruces.")
            _descargas(df_final, df_editado)

    except Exception as error:  # noqa: BLE001 - se muestra al usuario en lugar de romper la página
        st.error(f"Ocurrió un error al procesar el archivo: {error}")

    _ayuda_csv()
