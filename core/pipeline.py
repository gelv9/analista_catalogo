# core/pipeline.py
# Orquestador: conecta detector + extractores en un solo flujo.
# Detecta paginas de curvas (ColPali), extrae esas curvas (Claude) y las
# tablas del resto (pdfplumber + Claude para headers). Devuelve un JSON
# por catalogo. Generico: no asume nada del tipo de producto.

from datetime import date
from pathlib import Path

from core.detector import cargar_indice, detectar_paginas_curva
from core.render import pagina_a_imagen
from core.extractor_curvas import extraer_curvas
from core.extractor_tablas import extraer_tablas, construir_tabla


def es_tabla_real(tabla_cruda: list[list]) -> bool:
    """
    Una tabla real tiene al menos una fila con 2+ celdas con contenido.
    Descarta banners (1 sola celda por fila, p.ej. el titulo de la pagina).
    """
    max_celdas = 0
    for fila in tabla_cruda:
        con_contenido = sum(1 for c in fila if c and str(c).strip())
        max_celdas = max(max_celdas, con_contenido)
    return max_celdas >= 2


def procesar_catalogo(
    ruta_pdf: str,
    nombre_indice: str = "catalogo",
    limite_curvas: int | None = None,
    limite_tablas: int | None = None,
) -> dict:
    """
    Procesa un catalogo completo y devuelve un dict (un JSON por catalogo).
    limite_curvas / limite_tablas: para pruebas, limitan cuantas se procesan
    y asi no gastar tokens de mas. En None procesa todo.
    """
    # 1. Detectar paginas de curvas
    modelo = cargar_indice(nombre_indice)
    paginas_curva = detectar_paginas_curva(modelo)
    print(f"Paginas de curvas detectadas: {paginas_curva}", flush=True)

    a_procesar = paginas_curva[:limite_curvas] if limite_curvas else paginas_curva

    # 2. Extraer curvas (una llamada a Claude por pagina)
    graficos = []
    for pag in a_procesar:
        print(f"  Extrayendo curva de pagina {pag}...", flush=True)
        imagen = pagina_a_imagen(ruta_pdf, pag)
        graficos.append({"pagina": pag, "datos": extraer_curvas(imagen)})

    # 3. Extraer tablas del resto de paginas
    print("Buscando tablas...", flush=True)
    from core.extractor_tablas import extraer_tablas_desde_imagen

    crudas = extraer_tablas(ruta_pdf)
    paginas_con_tablas_reales = set()

    # filtrar: fuera las paginas-curva (grillas) y los banners
    candidatas = [
        t for t in crudas
        if t["pagina"] not in paginas_curva and es_tabla_real(t["cruda"])
    ]
    if limite_tablas:
        candidatas = candidatas[:limite_tablas]

    tablas = []
    for t in candidatas:
        print(f"  Procesando tabla de pagina {t['pagina']}...", flush=True)
        construida = construir_tabla(t["cruda"])
        tablas.append({"pagina": t["pagina"], **construida})
        paginas_con_tablas_reales.add(t["pagina"])

    # Paginas sin tablas legibles por pdfplumber → intentar con vision
    import fitz
    doc = fitz.open(ruta_pdf)
    total_paginas = len(doc)
    doc.close()

    paginas_sin_tablas = [
        p for p in range(1, total_paginas + 1)
        if p not in paginas_curva and p not in paginas_con_tablas_reales
    ]

    if paginas_sin_tablas:
        print(f"  Paginas sin tablas legibles: {paginas_sin_tablas}", flush=True)
        print("  Intentando extraccion visual con Claude...", flush=True)
        for pag in paginas_sin_tablas:
            imagen = pagina_a_imagen(ruta_pdf, pag)
            tablas_visuals = extraer_tablas_desde_imagen(imagen)
            for tv in tablas_visuals:
                if tv.get("filas"):
                    print(f"    Tabla visual encontrada en pag {pag}: "
                          f"{len(tv['filas'])} filas", flush=True)
                    tablas.append({"pagina": pag, **tv})

    # 4. Armar el JSON del catalogo
    return {
        "fuente": {
            "archivo": Path(ruta_pdf).name,
            "fecha_extraccion": str(date.today()),
            "paginas_curva": paginas_curva,
        },
        "graficos": graficos,
        "tablas": tablas,
    }