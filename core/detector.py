# core/detector.py
# Detector visual de paginas con ColPali (via byaldi).
# Indexa el PDF una vez y permite localizar paginas por similitud visual.
# Sirve para encontrar las paginas con graficos/curvas sin abrir cada una.

from byaldi import RAGMultiModalModel

_MODELO = "vidore/colpali-v1.2"


def indexar_pdf(ruta_pdf: str, nombre_indice: str = "catalogo"):
    """
    Indexa todas las paginas del PDF con ColPali.
    La primera vez descarga el modelo (varios GB) y tarda.
    El indice queda guardado en disco (carpeta .byaldi/).
    """
    modelo = RAGMultiModalModel.from_pretrained(_MODELO)
    modelo.index(
        input_path=ruta_pdf,
        index_name=nombre_indice,
        store_collection_with_index=False,  # no guardamos imagenes en el indice
        overwrite=True,
    )
    return modelo


def cargar_indice(nombre_indice: str = "catalogo"):
    """Carga un indice ya creado desde disco, para buscar sin re-indexar."""
    return RAGMultiModalModel.from_index(nombre_indice)


def buscar_paginas(modelo, consulta: str, k: int = 5) -> list[dict]:
    """
    Busca las paginas mas parecidas a la consulta visual.
    Devuelve lista de {pagina, score} ordenada por relevancia.
    """
    resultados = modelo.search(consulta, k=k)
    return [{"pagina": r.page_num, "score": r.score} for r in resultados]

def detectar_paginas_curva(
    modelo,
    consulta: str = "performance curve chart with axes and grid lines",
    factor_prominencia: float = 2.0,
) -> list[int]:
    """
    Detecta automaticamente que paginas son graficos/curvas.

    Ordena las paginas por score y corta en el salto (gap) mas grande:
    las paginas por encima del salto son las curvas.

    Salvaguarda: el salto elegido debe SOBRESALIR claramente respecto al
    salto promedio del documento (al menos factor_prominencia veces). Si
    ningun salto sobresale (scores parejos, p.ej. un catalogo sin curvas),
    devuelve [] en lugar de inventar un corte. El criterio es relativo al
    propio documento, no usa umbrales de score absolutos.
    """
    res = buscar_paginas(modelo, consulta, k=1000)
    res.sort(key=lambda r: r["score"], reverse=True)

    if len(res) < 2:
        return [r["pagina"] for r in res]

    # Saltos entre scores consecutivos
    gaps = [res[i]["score"] - res[i + 1]["score"] for i in range(len(res) - 1)]
    promedio_gap = sum(gaps) / len(gaps)
    mayor_gap = max(gaps)
    corte = gaps.index(mayor_gap) + 1

    # Salvaguarda de prominencia: el salto debe destacar del promedio
    if promedio_gap == 0 or mayor_gap < factor_prominencia * promedio_gap:
        return []  # no hay un bloque de curvas claramente diferenciado

    return sorted(r["pagina"] for r in res[:corte])