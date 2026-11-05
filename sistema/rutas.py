"""Rutas del proyecto, resueltas desde la ubicación de este archivo."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GEOJSON = RAIZ / "GEOJSON"
JSON = RAIZ / "json"
ESTATICOS = RAIZ / "static"
