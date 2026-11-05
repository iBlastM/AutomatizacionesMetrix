"""
mapa.py
Componente de Streamlit que muestra el mapa de geocodificacion y permite
editar las coordenadas de los puntos que cayeron fuera del municipio.

Uso:
    from sistema.limpieza.mapa import mostrar_mapa_geo

    df = mostrar_mapa_geo(df)   # devuelve el df con las correcciones aplicadas
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from shapely.geometry import Point, shape

from .. import estilos
from ..rutas import GEOJSON

_RUTA_GEOJSON = str(GEOJSON / "Corregidora.geojson")

# Clave de session_state donde se guardan las correcciones pendientes
_KEY_CORRECCIONES = "_mapa_correcciones"


@st.cache_resource
def _cargar_geojson_y_poligono():
    """Carga el GeoJSON del municipio y construye el polígono Shapely.
    Cacheado como recurso global: sólo se ejecuta una vez por sesión del servidor.
    """
    with open(_RUTA_GEOJSON, encoding="utf-8") as f:
        geojson = json.load(f)
    poligono = shape(geojson["features"][0]["geometry"])
    return geojson, poligono


def mostrar_mapa_geo(df: pd.DataFrame) -> pd.DataFrame:
    """Muestra mapa Plotly, dashboard de estadísticas y editor de correcciones.

    - Clasifica los puntos geocodificados como dentro / fuera del municipio.
    - Renderiza un mapa interactivo con Plotly.
    - Ofrece una tabla editable para corregir las coordenadas de los puntos
      que cayeron fuera del municipio.
    - Persiste las correcciones en st.session_state para sobrevivir reruns.

    Retorna el DataFrame con cualquier corrección ya aplicada.
    """
    if not os.path.exists(_RUTA_GEOJSON):
        st.warning(
            "No se encontró el GeoJSON del municipio "
            f"({os.path.relpath(_RUTA_GEOJSON)})."
        )
        return df

    geojson, poligono = _cargar_geojson_y_poligono()

    # Aplicar correcciones almacenadas en sesiones anteriores
    df = _aplicar_correcciones(df)

    cols_req = {"LATITUD", "LONGITUD", "DIRECCION_HOMOLOGADA"}
    if not cols_req.issubset(df.columns):
        st.warning(
            "El DataFrame no contiene las columnas necesarias: "
            + ", ".join(cols_req - set(df.columns))
        )
        return df

    # Puntos únicos geocodificados
    df_coords = (
        df[df["LATITUD"].notna() & df["LONGITUD"].notna()]
        [["LATITUD", "LONGITUD", "DIRECCION_HOMOLOGADA"]]
        .drop_duplicates(subset=["LATITUD", "LONGITUD"])
        .copy()
    )

    if df_coords.empty:
        st.warning("No hay puntos geocodificados para mostrar.")
        return df

    df_coords["DENTRO"] = df_coords.apply(
        lambda r: poligono.contains(
            Point(float(r["LONGITUD"]), float(r["LATITUD"]))
        ),
        axis=1,
    )
    dentro = df_coords[df_coords["DENTRO"]]
    fuera  = df_coords[~df_coords["DENTRO"]]
    total  = len(df_coords)

    # --- Resumen ---
    st.markdown("**Análisis de la geocodificación**")
    estilos.ficha(
        [
            ("Puntos geocodificados", f"{total:,}", ""),
            ("Dentro del municipio", f"{len(dentro):,}", f"{len(dentro) / total:.1%}"),
            ("Fuera del municipio", f"{len(fuera):,}", f"{len(fuera) / total:.1%}"),
        ]
    )

    # --- Mapa ---
    fig = _construir_mapa(geojson, dentro, fuera)
    st.plotly_chart(fig, width="stretch")

    # --- Editor de puntos fuera del municipio ---
    if not fuera.empty:
        df = _editor_puntos_fuera(df, fuera)

    return df


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _aplicar_correcciones(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica al df las correcciones guardadas en session_state."""
    correcciones = st.session_state.get(_KEY_CORRECCIONES, [])
    if not correcciones:
        return df
    df = df.copy()
    for c in correcciones:
        mask = (
            (df["DIRECCION_HOMOLOGADA"] == c["dir"])
            & (df["LATITUD"].round(6)  == round(c["lat_orig"], 6))
            & (df["LONGITUD"].round(6) == round(c["lon_orig"], 6))
        )
        df.loc[mask, "LATITUD"]  = c["lat_nueva"]
        df.loc[mask, "LONGITUD"] = c["lon_nueva"]
    return df


def _construir_mapa(
    geojson: dict,
    dentro: pd.DataFrame,
    fuera: pd.DataFrame,
) -> go.Figure:
    """Construye la figura Plotly con el contorno del municipio y los puntos."""
    fig = go.Figure()

    geom_type = geojson["features"][0]["geometry"]["type"]
    coords     = geojson["features"][0]["geometry"]["coordinates"]

    if geom_type == "Polygon":
        rings = [coords[0]]
    elif geom_type == "MultiPolygon":
        rings = [poly[0] for poly in coords]
    else:
        rings = []

    for i, ring in enumerate(rings):
        fig.add_trace(
            go.Scattermap(
                lon=[c[0] for c in ring],
                lat=[c[1] for c in ring],
                mode="lines",
                line=dict(width=2.5, color="#267E28"),
                name="Límite Corregidora",
                showlegend=(i == 0),
                hoverinfo="skip",
            )
        )

    if not dentro.empty:
        fig.add_trace(
            go.Scattermap(
                lat=dentro["LATITUD"],
                lon=dentro["LONGITUD"],
                mode="markers",
                marker=dict(size=6, color="#3EB340", opacity=0.8),
                text=dentro["DIRECCION_HOMOLOGADA"],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Lat: %{lat:.5f}<br>"
                    "Lon: %{lon:.5f}"
                    "<extra>Dentro</extra>"
                ),
                name=f"Dentro ({len(dentro)})",
            )
        )

    if not fuera.empty:
        fig.add_trace(
            go.Scattermap(
                lat=fuera["LATITUD"],
                lon=fuera["LONGITUD"],
                mode="markers",
                marker=dict(size=9, color="#EF4444", opacity=0.95),
                text=fuera["DIRECCION_HOMOLOGADA"],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Lat: %{lat:.5f}<br>"
                    "Lon: %{lon:.5f}"
                    "<extra>Fuera</extra>"
                ),
                name=f"Fuera ({len(fuera)})",
            )
        )

    all_lats = (
        pd.concat([dentro["LATITUD"], fuera["LATITUD"]])
        if not fuera.empty
        else dentro["LATITUD"]
    )
    all_lons = (
        pd.concat([dentro["LONGITUD"], fuera["LONGITUD"]])
        if not fuera.empty
        else dentro["LONGITUD"]
    )

    fig.update_layout(
        title=dict(
            text=(
                f"Geocodificación — {len(dentro) + len(fuera)} puntos únicos&nbsp;|&nbsp;"
                f"<span style='color:#7BC11D'>{len(dentro)} dentro</span>&nbsp;|&nbsp;"
                f"<span style='color:#F87171'>{len(fuera)} fuera</span>"
            ),
            font=dict(size=15, family="Barlow, system-ui, sans-serif", color="#FFFFFF"),
        ),
        map=dict(
            style="open-street-map",
            center=dict(
                lat=float(all_lats.mean()),
                lon=float(all_lons.mean()),
            ),
            zoom=11.5,
        ),
        legend=dict(
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(6,6,6,0.88)", font=dict(color="#FFFFFF"),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=650,
    )
    return fig


def _editor_puntos_fuera(df: pd.DataFrame, fuera: pd.DataFrame) -> pd.DataFrame:
    """Muestra la tabla editable de puntos fuera y gestiona las correcciones."""
    n_correcciones = len(st.session_state.get(_KEY_CORRECCIONES, []))

    with st.expander(
        f"Corregir coordenadas — {len(fuera)} punto(s) fuera del municipio",
        expanded=True,
    ):
        st.caption(
            "Edita las columnas **Lat nueva** y **Lon nueva** para los registros "
            "que cayeron fuera del municipio. "
            "Pulsa **Aplicar correcciones** para actualizar el resultado y el mapa."
        )

        df_editor = fuera[["DIRECCION_HOMOLOGADA", "LATITUD", "LONGITUD"]].copy()
        df_editor["LATITUD_NUEVA"]  = df_editor["LATITUD"]
        df_editor["LONGITUD_NUEVA"] = df_editor["LONGITUD"]
        df_editor = df_editor.reset_index(drop=True)

        # La clave incluye el número de correcciones aplicadas para que el
        # widget se reinicie tras cada aplicacion (evita que Streamlit restaure
        # los valores anteriores desde session_state).
        editor_key = f"_editor_fuera_v{n_correcciones}"

        edited = st.data_editor(
            df_editor,
            column_config={
                "DIRECCION_HOMOLOGADA": st.column_config.TextColumn(
                    "Dirección", disabled=True
                ),
                "LATITUD": st.column_config.NumberColumn(
                    "Lat original", disabled=True, format="%.6f"
                ),
                "LONGITUD": st.column_config.NumberColumn(
                    "Lon original", disabled=True, format="%.6f"
                ),
                "LATITUD_NUEVA": st.column_config.NumberColumn(
                    "Lat nueva", format="%.6f"
                ),
                "LONGITUD_NUEVA": st.column_config.NumberColumn(
                    "Lon nueva", format="%.6f"
                ),
            },
            width="stretch",
            hide_index=True,
            key=editor_key,
        )

        if st.button(
            "Aplicar correcciones",
            type="primary",
            key=f"_btn_aplicar_v{n_correcciones}",
        ):
            nuevas = []
            for _, fila in edited.iterrows():
                lat_nueva = fila["LATITUD_NUEVA"]
                lon_nueva = fila["LONGITUD_NUEVA"]
                if pd.notna(lat_nueva) and pd.notna(lon_nueva) and (
                    lat_nueva != fila["LATITUD"] or lon_nueva != fila["LONGITUD"]
                ):
                    nuevas.append(
                        {
                            "dir":      fila["DIRECCION_HOMOLOGADA"],
                            "lat_orig": fila["LATITUD"],
                            "lon_orig": fila["LONGITUD"],
                            "lat_nueva": lat_nueva,
                            "lon_nueva": lon_nueva,
                        }
                    )

            # Fusionar con correcciones anteriores (preservar puntos ya
            # corregidos que siguen dentro del municipio y no aparecen en
            # 'fuera' esta vez).
            previas = {
                c["dir"]: c
                for c in st.session_state.get(_KEY_CORRECCIONES, [])
            }
            for c in nuevas:
                previas[c["dir"]] = c
            st.session_state[_KEY_CORRECCIONES] = list(previas.values())

            if nuevas:
                st.success(
                    f"Correcciones guardadas para {len(nuevas)} punto(s). "
                    "Actualizando mapa…"
                )
                st.rerun()
            else:
                st.info("No se detectaron cambios en las coordenadas.")

    return df
