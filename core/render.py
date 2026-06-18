# core/render.py
# Renderiza una pagina especifica de un PDF a imagen PNG.
# Permite pasarle al extractor de curvas solo la pagina que el detector
# marco como grafico, sacandola del PDF, sin depender de imagenes sueltas.

import fitz  # pymupdf
from pathlib import Path


def pagina_a_imagen(
    ruta_pdf: str,
    num_pagina: int,
    dpi: int = 150,
    carpeta_salida: str = "temp",
) -> str:
    """
    Renderiza la pagina num_pagina (contada desde 1) del PDF a un PNG.
    Devuelve la ruta del PNG generado.
    """
    Path(carpeta_salida).mkdir(exist_ok=True)
    doc = fitz.open(ruta_pdf)
    pagina = doc[num_pagina - 1]          # fitz cuenta desde 0
    pix = pagina.get_pixmap(dpi=dpi)
    ruta_salida = str(Path(carpeta_salida) / f"pagina_{num_pagina}.png")
    pix.save(ruta_salida)
    doc.close()
    return ruta_salida