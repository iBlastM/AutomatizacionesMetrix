# Design

Superficie de trabajo (Operate) con la imagen corporativa de Metrix, tomada de `DashboardElectoral`: fondo negro, verde lima y acentos de datos. El tema vive en `.streamlit/config.toml` y `sistema/estilos.py`.

## Color
| Rol | Valor |
|---|---|
| Fondo | `#060606` |
| Tarjeta / campos | `#0D0D0D` / `#141414` |
| Acento (acciones, foco, selección) | `#7BC11D` |
| Acento hover | `#A3E635` |
| Acento secundario / profundo | `#3EB340` / `#267E28` |
| Texto / texto suave | `#FFFFFF` / blanco al 64 % |
| Borde | verde lima al 18 % (42 % en elementos interactivos) |
| Barra superior | degradado `#000000 → #0A1300 → #061000`, filo inferior de 2 px en acento |

Colores de datos (barra de coincidencias): exacta `#7BC11D`, nombre + fecha `#34D399`, parcial `#FCD34D`, solo nombre `#FB923C`, sin coincidencia `#52525B`. Siempre acompañados de leyenda con cifras.

## Tipografía
Barlow (400, 500, 600, 700) autoalojada en `static/`, igual que el dashboard. La fuente `Asterone DEMO.ttf` no se usa: no incluye letras acentuadas ni eñes y es una versión de demostración.

## Marca
Logotipo `static/logo-metrix.png` (versión oscura, fondo transparente) en la barra superior, e `icono-metrix.png` como favicon. Origen: `DashboardElectoral/images/LogoMetrixOscuro.png`.

## Forma y profundidad
Radio de control 8 px, contenedores 10 a 14 px. Fichas con degradado sutil `#0D0D0D → #141414`. Sin sombras.

## Componentes propios
- **Paso:** número en círculo + título + una línea de ayuda; se rellena de lima al completarse.
- **Ficha:** fila de tres cifras clave con separadores finos.
- **Barra de coincidencias:** barra segmentada proporcional con leyenda.
- **Estado vacío:** recuadro punteado que dice qué falta.

## Movimiento
Un solo momento: la barra de coincidencias se revela de izquierda a derecha en 520 ms. Botones y pestañas: `scale(0.97)` al presionar, 160 ms. Respeta `prefers-reduced-motion`.

## Iconos
Material Symbols de Streamlit (`:material/...:`).
