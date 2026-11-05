"""Automatizaciones Metrix: herramientas de datos para quien no programa.

Para correrlo en local:   streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Automatizaciones Metrix",
    page_icon="static/icono-metrix.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from sistema import estilos  # noqa: E402
from sistema.cruces import ui as cruces  # noqa: E402
from sistema.limpieza import ui as limpieza  # noqa: E402

estilos.aplicar_estilos()

tab_cruces, tab_limpieza = st.tabs(
    [":material/join_inner: Cruces de información", ":material/cleaning_services: Limpieza y georreferenciación"]
)

# Limpieza se ejecuta primero para que su resultado esté disponible como fuente en Cruces.
with tab_limpieza:
    limpieza.render()
with tab_cruces:
    cruces.render()

