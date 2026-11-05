# Product

> Contexto inferido del encargo y de los documentos del proyecto, sin entrevista. Los supuestos estÃ¡n marcados y deben confirmarse.

## Platform
web

## Stack
Streamlit (Python), pandas, desplegado en Streamlit Community Cloud. El estilo se aplica con `.streamlit/config.toml` y CSS inyectado desde `sistema/estilos.py`.

## Users
Personal de Ã¡reas de desarrollo social y de operaciÃ³n territorial que cruza padrones y bases de beneficiarios. Trabajan con Excel todos los dÃ­as y no escriben scripts. (Supuesto: oficina, pantalla de escritorio, luz de dÃ­a, sesiones largas.)

## Product Purpose
Reemplazar los scripts de cruce y limpieza que hoy hace una sola persona tÃ©cnica por herramientas guiadas. El Ã©xito es que cualquier usuario obtenga un cruce correcto y verificable, con las coincidencias dudosas a la vista, sin pedir ayuda.

## Positioning
Herramienta interna de trabajo, no un producto de marketing. Las herramientas se agregan como pestaÃ±as.

## Operating Context
Se usa por episodios: subir dos archivos, ajustar poco, descargar. Las bases contienen datos personales (CURP, domicilios, telÃ©fonos). Los archivos se procesan en la sesiÃ³n y no se guardan.

## Capabilities and Constraints
Archivos Excel/CSV hasta 500 MB. Memoria limitada en Community Cloud. Sin base de datos ni autenticaciÃ³n. (Supuesto: el acceso a la URL se controla desde Streamlit Cloud.)

## Brand Commitments
Imagen corporativa Metrix: negro, verde lima y Barlow, tomada de DashboardElectoral. Ver DESIGN.md.

## Evidence on Hand
`CRMlocal/Ejercicios/RESUMEN_CRUCES_Y_LIMPIEZA.md` (procedimiento de cruce y resultados de referencia) y la app `BaseProgramasSociales` (limpieza).

## Product Principles
- Un resultado debe poder verificarse: cada fila dice cÃ³mo se encontrÃ³, y las coincidencias dudosas las confirma una persona.
- Los valores sugeridos funcionan sin tocar nada; las opciones avanzadas estÃ¡n plegadas.
- Los archivos originales no se modifican y los datos no se pierden al leerlos (todo se lee como texto).
- Lenguaje de oficina, no de programaciÃ³n.

## Accessibility & Inclusion
Contraste AA mÃ­nimo, foco visible, no depender solo del color (la barra de coincidencias lleva leyenda con cifras), respeta `prefers-reduced-motion`.

