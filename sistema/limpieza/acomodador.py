"""Reordenado de columnas del resultado de Limpieza."""

from __future__ import annotations

import pandas as pd
import streamlit as st

KEY_ORDEN = "_acomodador_orden"


def mostrar_acomodador(df: pd.DataFrame) -> pd.DataFrame:
    """Panel para reordenar las columnas del DataFrame.

    - Persiste el orden en st.session_state para sobrevivir reruns.
    - Sincroniza automáticamente si el conjunto de columnas cambia (p. ej. tras
      una nueva georreferenciación).
    - Retorna el DataFrame con las columnas en el orden seleccionado.
    """
    columnas_base = df.columns.tolist()

    orden_guardado = st.session_state.get(KEY_ORDEN, [])
    columnas_guardadas = set(orden_guardado)
    columnas_actuales = set(columnas_base)

    if columnas_guardadas != columnas_actuales:
        # Conservar el orden relativo de las columnas que ya estaban y
        # agregar al final las nuevas.
        conocidas = [c for c in orden_guardado if c in columnas_actuales]
        nuevas = [c for c in columnas_base if c not in columnas_guardadas]
        st.session_state[KEY_ORDEN] = conocidas + nuevas

    orden = st.session_state[KEY_ORDEN]

    st.caption(
        "Elige una columna y muévela con los botones. El orden se refleja en la vista previa y en los archivos descargados."
    )

    col_sel, col_botones = st.columns([3, 2], vertical_alignment="bottom")

    with col_sel:
        columna_sel = st.selectbox("Columna", options=orden, key="_acomodador_sel")

    idx = orden.index(columna_sel)

    with col_botones:
        b1, b2, b3 = st.columns(3)
        with b1:
            subir = st.button(
                "Subir", icon=":material/arrow_upward:", disabled=(idx == 0),
                help="Mover arriba", key="_acomodador_up", width="stretch",
            )
        with b2:
            bajar = st.button(
                "Bajar", icon=":material/arrow_downward:", disabled=(idx == len(orden) - 1),
                help="Mover abajo", key="_acomodador_down", width="stretch",
            )
        with b3:
            reset = st.button(
                "Original", icon=":material/restart_alt:",
                help="Restablecer el orden original", key="_acomodador_reset", width="stretch",
            )

    if subir:
        orden[idx], orden[idx - 1] = orden[idx - 1], orden[idx]
        st.session_state[KEY_ORDEN] = orden
        st.rerun()

    if bajar:
        orden[idx], orden[idx + 1] = orden[idx + 1], orden[idx]
        st.session_state[KEY_ORDEN] = orden
        st.rerun()

    if reset:
        st.session_state[KEY_ORDEN] = columnas_base.copy()
        st.rerun()

    with st.expander("Ver el orden actual", expanded=False):
        filas = [{"#": i + 1, "Columna": col} for i, col in enumerate(orden)]
        st.dataframe(
            pd.DataFrame(filas),
            hide_index=True,
            width="stretch",
            height=min(35 * len(orden) + 38, 400),
        )

    return df[orden]
