# core/exportador.py
# Exporta los datos extraidos de un catalogo a Excel y JSON descargable.
# Una hoja por tipo de contenido. Generico: usa los nombres de columna
# que traiga cada tabla, sin asumir estructura de ningun producto.

import json
from pathlib import Path

import pandas as pd


def _curvas_a_dataframe(graficos: list) -> pd.DataFrame:
    """
    Convierte la lista de graficos a una tabla plana para Excel.
    Una fila por serie de cada grafico.
    """
    filas = []
    for g in graficos:
        pagina = g.get("pagina")
        datos = g.get("datos", {})
        titulo = datos.get("titulo", "")

        # Ejes como string resumido
        ejes = "; ".join(
            f"{e.get('etiqueta','')} [{','.join(e.get('unidades',[]))}]"
            for e in datos.get("ejes", [])
        )

        for serie in datos.get("series", []):
            filas.append({
                "Pagina": pagina,
                "Titulo": titulo,
                "Ejes": ejes,
                "Serie": serie.get("etiqueta", ""),
                "Tipo": serie.get("tipo", ""),
                "Num Puntos": len(serie.get("puntos", [])),
                "Puntos (x,y)": str([
                    (p["x"], p["y"]) for p in serie.get("puntos", [])
                ]),
            })

    return pd.DataFrame(filas) if filas else pd.DataFrame()


def exportar_excel(ruta_json: str, ruta_salida: str = None) -> str:
    """
    Lee el JSON de un catalogo procesado y genera un Excel con:
    - Hoja 'Graficos': todas las series de todas las curvas
    - Una hoja por cada tipo de tabla encontrada (por sus columnas)
    Devuelve la ruta del Excel generado.
    """
    catalogo = json.loads(Path(ruta_json).read_text(encoding="utf-8"))

    if ruta_salida is None:
        stem = Path(ruta_json).stem
        ruta_salida = str(Path(ruta_json).parent / f"{stem}.xlsx")

    with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:

        # Hoja de graficos/curvas
        df_curvas = _curvas_a_dataframe(catalogo.get("graficos", []))
        if not df_curvas.empty:
            df_curvas.to_excel(writer, sheet_name="Graficos", index=False)

        # Hojas de tablas — una por tipo (agrupadas por sus columnas)
        tablas = catalogo.get("tablas", [])
        grupos: dict[str, list] = {}
        for tabla in tablas:
            # Clave del grupo: primeras 3 columnas (identifica el tipo de tabla)
            clave = tuple(tabla.get("columnas", [])[:3])
            if clave not in grupos:
                grupos[clave] = []
            grupos[clave].extend(tabla.get("filas", []))

        for i, (clave, filas) in enumerate(grupos.items()):
            if not filas:
                continue
            df = pd.DataFrame(filas)
            # Nombre de hoja: primeras dos columnas de la clave
            nombre_hoja = " - ".join(str(c) for c in clave[:2])[:31]
            nombre_hoja = nombre_hoja or f"Tabla {i+1}"
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)

    print(f"Excel generado: {ruta_salida}")
    return ruta_salida


def exportar_json_productos(ruta_json: str, ruta_salida: str = None) -> str:
    """
    Exporta el JSON de productos separados por modelo (descargable).
    """
    from core.indexador import _separar_por_modelo

    catalogo = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    productos = _separar_por_modelo(catalogo)

    if ruta_salida is None:
        ruta_salida = str(Path(ruta_json).parent / "productos.json")

    Path(ruta_salida).write_text(
        json.dumps(productos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"JSON productos generado: {ruta_salida}")
    return ruta_salida


def exportar_excel_bytes(ruta_json: str) -> bytes:
    """
    Genera el Excel en memoria y devuelve los bytes.
    Evita conflictos de permisos si el archivo ya esta abierto en Excel.
    """
    import io
    catalogo = json.loads(Path(ruta_json).read_text(encoding="utf-8"))

    buffer = io.BytesIO()
    hojas_escritas = 0

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

        df_curvas = _curvas_a_dataframe(catalogo.get("graficos", []))
        if not df_curvas.empty:
            df_curvas.to_excel(writer, sheet_name="Graficos", index=False)
            hojas_escritas += 1

        tablas = catalogo.get("tablas", [])
        grupos: dict[str, list] = {}
        for tabla in tablas:
            clave = tuple(tabla.get("columnas", [])[:3])
            if clave not in grupos:
                grupos[clave] = []
            grupos[clave].extend(tabla.get("filas", []))

        for i, (clave, filas) in enumerate(grupos.items()):
            if not filas:
                continue
            df = pd.DataFrame(filas)
            nombre_hoja = " - ".join(str(c) for c in clave[:2])[:31]
            nombre_hoja = nombre_hoja or f"Tabla {i+1}"
            df.to_excel(writer, sheet_name=nombre_hoja, index=False)
            hojas_escritas += 1

        # Garantia: si no habia datos, crear una hoja minima
        if hojas_escritas == 0:
            pd.DataFrame([{"info": "sin datos"}]).to_excel(
                writer, sheet_name="Sin datos", index=False
            )

    return buffer.getvalue()
