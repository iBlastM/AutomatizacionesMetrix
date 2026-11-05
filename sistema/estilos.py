"""Sistema visual de Automatizaciones Metrix.

Tokens, CSS para los componentes nativos de Streamlit y unos pocos componentes
propios (pasos, fichas de datos, barra de coincidencias). Ver DESIGN.md.
"""

from __future__ import annotations

from html import escape

import streamlit as st

# ── Tokens (imagen corporativa Metrix: negro + verde lima, como DashboardElectoral) ──
FONDO = "#060606"
TARJETA = "#0D0D0D"
SUPERFICIE = "#141414"
ACENTO = "#7BC11D"
ACENTO_2 = "#3EB340"
ACENTO_PROFUNDO = "#267E28"
ACENTO_CLARO = "#A3E635"
TEXTO = "#FFFFFF"

COLORES_TIPO = {
    "exacta": ACENTO,
    "fecha": "#34D399",
    "parcial": "#FCD34D",
    "nombre": "#FB923C",
    "sin": "#52525B",
}

_FUENTES = "".join(
    f"""
@font-face {{
  font-family: "Barlow";
  font-style: normal;
  font-weight: {peso};
  font-display: swap;
  src: url("app/static/barlow-{subconjunto}-{peso}-normal.woff2") format("woff2");
  unicode-range: {rango};
}}"""
    for peso in (400, 500, 600, 700)
    for subconjunto, rango in (
        ("latin", "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"),
        ("latin-ext", "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF"),
    )
)

_CSS = f"""
<style>
{_FUENTES}

:root {{
  --fondo: {FONDO};
  --tarjeta: {TARJETA};
  --superficie: {SUPERFICIE};
  --acento: {ACENTO};
  --acento-2: {ACENTO_2};
  --acento-profundo: {ACENTO_PROFUNDO};
  --acento-claro: {ACENTO_CLARO};
  --texto: {TEXTO};
  --texto-suave: rgba(255, 255, 255, 0.64);
  --borde: rgba(123, 193, 29, 0.18);
  --borde-fuerte: rgba(123, 193, 29, 0.42);
  --salida: cubic-bezier(0.23, 1, 0.32, 1);
}}

.stApp :is(p, li, label, h1, h2, h3, h4, input, textarea, button, a, dt, dd, small, strong, td, th, summary, [data-baseweb="tab"]) {{
  font-family: "Barlow", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}}
[data-testid="stIconMaterial"], .material-symbols-rounded {{
  font-family: "Material Symbols Rounded" !important;
}}
.stApp {{
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
}}
::selection {{ background: rgba(123, 193, 29, 0.38); color: #fff; }}
input, textarea {{ caret-color: var(--acento); }}
* {{ scrollbar-width: thin; scrollbar-color: #33451a transparent; }}

/* ── Barra superior con el logotipo ─────────────────────────────── */
[data-testid="stHeader"] {{
  background: linear-gradient(135deg, #000000 0%, #0a1300 70%, #061000 100%);
  height: 3.5rem;
  border-bottom: 2px solid var(--acento);
}}
[data-testid="stHeader"]::before {{
  content: "";
  position: absolute;
  left: max(1.5rem, calc((100vw - 1180px) / 2 + 1rem));
  top: 50%;
  transform: translateY(-50%);
  width: 8.6rem;
  height: 2.55rem;
  background: url("app/static/logo-metrix.png") no-repeat left center / contain;
  pointer-events: none;
}}
[data-testid="stHeader"] * {{ color: rgba(255, 255, 255, 0.78) !important; }}
[data-testid="stToolbar"] button:hover {{ background: rgba(123, 193, 29, 0.14); }}

/* ── Contenedor ─────────────────────────────────────────────────── */
[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1180px;
  padding: 5.25rem 1rem 4rem;
}}
h1, h2, h3, h4 {{ color: var(--texto); letter-spacing: -0.01em; text-wrap: balance; }}
p, li, label {{ text-wrap: pretty; }}
[data-testid="stCaptionContainer"], .stCaption,
[data-testid="stCaptionContainer"] * {{ color: var(--texto-suave) !important; opacity: 1 !important; }}

/* ── Pestañas principales ───────────────────────────────────────── */
[data-baseweb="tab-list"] {{ gap: 0.25rem; border-bottom: 1px solid var(--borde); }}
button[data-baseweb="tab"] {{
  height: 3rem;
  padding: 0 1.1rem;
  font-weight: 600;
  color: var(--texto-suave);
  transition: color 160ms var(--salida), background-color 160ms var(--salida), transform 160ms var(--salida);
}}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--acento); }}
@media (hover: hover) and (pointer: fine) {{
  button[data-baseweb="tab"]:hover {{ background: rgba(123, 193, 29, 0.08); color: var(--acento); }}
}}
button[data-baseweb="tab"]:active {{ transform: scale(0.97); }}
[data-baseweb="tab-highlight"] {{ background-color: var(--acento) !important; height: 3px !important; }}
[data-baseweb="tab-border"] {{ display: none; }}

/* ── Botones ────────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {{
  border-radius: 8px;
  font-weight: 600;
  min-height: 2.5rem;
  border: 1px solid var(--borde-fuerte);
  background: var(--superficie);
  color: var(--texto);
  transition: transform 160ms var(--salida), background-color 160ms var(--salida), border-color 160ms var(--salida), color 160ms var(--salida);
}}
.stButton > button:active, .stDownloadButton > button:active {{ transform: scale(0.97); }}
@media (hover: hover) and (pointer: fine) {{
  .stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--acento); color: var(--acento); }}
}}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
  background: var(--acento);
  border-color: var(--acento);
  color: #060606;
}}
.stButton > button[kind="primary"] *, .stDownloadButton > button[kind="primary"] * {{ color: #060606 !important; }}
@media (hover: hover) and (pointer: fine) {{
  .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {{
    background: var(--acento-claro); border-color: var(--acento-claro);
  }}
}}
.stButton > button:disabled, .stDownloadButton > button:disabled {{ opacity: 0.4; }}
:is(button, a, input, textarea, [role="tab"], [role="radio"], [data-baseweb="select"]):focus-visible {{
  outline: 2px solid var(--acento);
  outline-offset: 2px;
}}

/* ── Campos ─────────────────────────────────────────────────────── */
[data-baseweb="tag"] {{ background: rgba(123, 193, 29, 0.2) !important; border-radius: 6px; }}
[data-baseweb="tag"], [data-baseweb="tag"] * {{ color: #d4f5a0 !important; }}
[data-testid="stFileUploaderDropzone"] {{
  background: var(--tarjeta);
  border: 1.5px dashed var(--borde-fuerte);
  border-radius: 10px;
  transition: border-color 160ms var(--salida), background-color 160ms var(--salida);
}}
@media (hover: hover) and (pointer: fine) {{
  [data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--acento); background: #0f1608; }}
}}
[data-testid="stExpander"] details {{
  border: 1px solid var(--borde);
  border-radius: 10px;
  background: var(--tarjeta);
}}
[data-testid="stExpander"] summary {{ font-weight: 600; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border-radius: 10px; }}
hr {{ border-color: var(--borde); }}

/* ── Deslizador: el valor no debe partirse en varias líneas ────── */
[data-testid="stSliderThumbValue"],
[data-testid="stSliderTickBarMin"],
[data-testid="stSliderTickBarMax"] {{
  white-space: nowrap;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}}
[data-testid="stSliderThumbValue"] {{ color: var(--acento) !important; overflow: visible; }}
[data-testid="stSliderThumbValue"] > * {{
  width: max-content;
  position: relative;
  left: 50%;
  transform: translateX(-50%);
}}
[data-testid="stSliderThumbValue"] :is(div, p) {{
  overflow-wrap: normal !important;
  word-break: keep-all !important;
  white-space: nowrap !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] > div {{ overflow: visible; }}

/* ── Encabezado de la herramienta ───────────────────────────────── */
.herramienta {{ margin: 0.25rem 0 1.5rem; max-width: 66ch; }}
.herramienta h2 {{ font-size: 1.7rem; font-weight: 700; margin: 0 0 0.35rem; padding: 0; line-height: 1.2; color: var(--texto); }}
.herramienta p {{ color: var(--texto-suave); margin: 0; font-size: 1rem; line-height: 1.55; }}

/* ── Pasos ──────────────────────────────────────────────────────── */
.paso {{
  display: flex; gap: 0.9rem; align-items: flex-start;
  margin: 2.25rem 0 0.9rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--borde);
}}
.paso.primero {{ border-top: 0; padding-top: 0; margin-top: 1rem; }}
.paso-n {{
  flex: none; width: 1.9rem; height: 1.9rem; border-radius: 999px;
  display: grid; place-items: center;
  font-weight: 700; font-size: 0.92rem;
  background: rgba(123, 193, 29, 0.16); color: var(--acento);
}}
.paso.hecho .paso-n {{ background: var(--acento); color: #060606; }}
.paso h3 {{ margin: 0; padding: 0; font-size: 1.25rem; font-weight: 650; line-height: 1.3; color: var(--texto); }}
.paso p {{ margin: 0.2rem 0 0; color: var(--texto-suave); font-size: 0.95rem; max-width: 64ch; line-height: 1.5; }}

/* ── Ficha de datos ─────────────────────────────────────────────── */
.ficha {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin: 0.5rem 0 1rem; padding: 0;
  border: 1px solid var(--borde); border-radius: 14px;
  background: linear-gradient(160deg, #0d0d0d 0%, #141414 100%);
  overflow: hidden;
}}
.ficha > div {{ padding: 0.9rem 1.15rem; border-left: 1px solid var(--borde); min-width: 0; }}
.ficha > div:first-child {{ border-left: 0; }}
.ficha dt {{ font-size: 0.85rem; color: var(--texto-suave); font-weight: 500; margin: 0; }}
.ficha dd {{ margin: 0.1rem 0 0; font-size: 1.7rem; font-weight: 700; color: var(--texto); line-height: 1.2; }}
.ficha dd small {{ font-size: 0.88rem; font-weight: 600; color: var(--acento); margin-left: 0.4rem; }}
@media (max-width: 640px) {{
  .ficha > div {{ border-left: 0; border-top: 1px solid var(--borde); }}
  .ficha > div:first-child {{ border-top: 0; }}
}}

/* ── Barra de coincidencias ─────────────────────────────────────── */
.barra-titulo {{ font-weight: 600; font-size: 1rem; margin: 1.1rem 0 0.55rem; color: var(--texto); }}
.barra {{
  display: flex; height: 2.1rem; border-radius: 8px; overflow: hidden; gap: 2px;
  animation: revelar 520ms var(--salida) both;
}}
.barra > span {{ display: block; min-width: 3px; }}
.leyenda {{
  list-style: none; margin: 0.7rem 0 1.25rem; padding: 0;
  display: flex; flex-wrap: wrap; gap: 0.35rem 1.4rem;
}}
.leyenda li {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; color: var(--texto); }}
.leyenda i {{ width: 0.8rem; height: 0.8rem; border-radius: 3px; flex: none; }}
.leyenda b {{ font-weight: 700; }}
.leyenda small {{ color: var(--texto-suave); font-size: 0.85rem; }}
@keyframes revelar {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}

/* ── Notas ──────────────────────────────────────────────────────── */
.nota {{
  background: rgba(252, 211, 77, 0.1); border-radius: 10px; padding: 0.7rem 0.95rem;
  font-size: 0.95rem; line-height: 1.5; color: #fde68a;
}}
.vacio {{
  border: 1.5px dashed var(--borde-fuerte); border-radius: 12px; padding: 1.4rem 1.2rem;
  color: var(--texto-suave); font-size: 1rem;
}}
.vacio strong {{ color: var(--texto); }}

@media (prefers-reduced-motion: reduce) {{
  .barra {{ animation: none; }}
  * {{ transition-duration: 0.01ms !important; }}
}}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def encabezado_herramienta(titulo: str, descripcion: str) -> None:
    st.markdown(
        f'<div class="herramienta"><h2>{escape(titulo)}</h2><p>{escape(descripcion)}</p></div>',
        unsafe_allow_html=True,
    )


def paso(numero: int, titulo: str, descripcion: str = "", hecho: bool = False) -> None:
    clase = "paso" + (" hecho" if hecho else "") + (" primero" if numero == 1 else "")
    desc = f"<p>{escape(descripcion)}</p>" if descripcion else ""
    st.markdown(
        f'<div class="{clase}"><div class="paso-n">{numero}</div>'
        f"<div><h3>{escape(titulo)}</h3>{desc}</div></div>",
        unsafe_allow_html=True,
    )


def ficha(items: list[tuple[str, str, str]]) -> None:
    """Fila de datos clave. Cada item es (etiqueta, valor, nota opcional)."""
    celdas = "".join(
        f"<div><dt>{escape(e)}</dt><dd>{escape(v)}"
        + (f"<small>{escape(n)}</small>" if n else "")
        + "</dd></div>"
        for e, v, n in items
    )
    st.markdown(f'<dl class="ficha">{celdas}</dl>', unsafe_allow_html=True)


def barra_segmentada(titulo: str, segmentos: list[tuple[str, int, str]]) -> None:
    """Barra proporcional. Cada segmento es (etiqueta, cantidad, color)."""
    total = sum(c for _, c, _ in segmentos) or 1
    visibles = [(e, c, col) for e, c, col in segmentos if c > 0]
    barras = "".join(
        f'<span style="flex:{c};background:{col}" title="{escape(e)}: {c:,}"></span>' for e, c, col in visibles
    )
    leyenda = "".join(
        f'<li><i style="background:{col}"></i><span>{escape(e)}</span> <b>{c:,}</b>'
        f"<small>{c / total:.1%}</small></li>"
        for e, c, col in segmentos
    )
    resumen = "; ".join(f"{e}: {c:,}" for e, c, _ in segmentos)
    st.markdown(
        f'<div class="barra-titulo">{escape(titulo)}</div>'
        f'<div class="barra" role="img" aria-label="{escape(resumen)}">{barras}</div>'
        f'<ul class="leyenda">{leyenda}</ul>',
        unsafe_allow_html=True,
    )


def estado_vacio(titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="vacio"><strong>{escape(titulo)}</strong><br>{escape(texto)}</div>',
        unsafe_allow_html=True,
    )


def nota(texto: str) -> None:
    st.markdown(f'<div class="nota">{escape(texto)}</div>', unsafe_allow_html=True)
