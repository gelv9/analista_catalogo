# core/indexador.py
# Toma el JSON de un catalogo ya procesado, separa los productos por modelo,
# genera embeddings con fastembed (local, $0) y los indexa en Qdrant.
# Un punto en Qdrant por modelo de producto.

import re
import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_COLECCION = "productos"
_DIM = 384


def _limpiar_nombre(nombre: str) -> str:
    """Normaliza el nombre del modelo para usarlo como clave de agrupacion."""
    nombre = nombre.strip().upper()
    nombre = re.sub(r"\s+", " ", nombre)
    nombre = nombre.replace("DESEMPEÑO", "").strip()
    return nombre


def _texto_producto(modelo: str, curvas: list, tablas: list) -> str:
    """
    Construye un texto descriptivo del producto para generar el embedding.
    Captura las caracteristicas funcionales sin asumir vocabulario fijo.
    """
    partes = [f"modelo {modelo}"]

    for c in curvas:
        datos = c.get("datos", {})
        if datos.get("titulo"):
            partes.append(datos["titulo"])
        for eje in datos.get("ejes", []):
            etiqueta = eje.get("etiqueta", "")
            unidades = " ".join(eje.get("unidades", []))
            partes.append(f"{etiqueta} {unidades}".strip())
        for serie in datos.get("series", []):
            if serie.get("etiqueta"):
                partes.append(serie["etiqueta"])

    for t in tablas:
        partes.extend(t.get("columnas", []))
        for fila in t.get("filas", []):
            for v in fila.values():
                if v and len(str(v)) < 50:
                    partes.append(str(v))

    return " | ".join(p for p in partes if p and p.strip())


def _separar_por_modelo(catalogo: dict) -> dict[str, dict]:
    """
    Agrupa curvas y tablas por modelo de producto.
    Estrategia 1: extrae el modelo del titulo del grafico (FPS style).
    Estrategia 2: si el titulo no identifica modelo, usa las etiquetas
                  de las series del grafico (Czerweny style).
    Estrategia 3: si hay tablas con columna MODELO, crea un producto
                  por cada modelo distinto encontrado.
    """
    productos = {}

    for grafico in catalogo.get("graficos", []):
        datos = grafico.get("datos", {})
        titulo = datos.get("titulo", "")
        series = datos.get("series", [])

        # Estrategia 1: titulo corto que identifica modelo
        nombre_titulo = _limpiar_nombre(titulo) if titulo else ""

        # Heuristica: si el titulo tiene mas de 5 palabras, probablemente
        # es un titulo descriptivo, no un nombre de modelo
        es_titulo_descriptivo = len(nombre_titulo.split()) > 5

        if not es_titulo_descriptivo and nombre_titulo:
            # Estrategia 1: un grafico = un modelo
            if nombre_titulo not in productos:
                productos[nombre_titulo] = {"curvas": [], "tablas": []}
            productos[nombre_titulo]["curvas"].append(grafico)
        else:
            # Estrategia 2: las series del grafico son los modelos
            modelos_en_series = [
                s.get("etiqueta", "").strip()
                for s in series
                if s.get("etiqueta") and len(s.get("etiqueta", "")) > 2
            ]
            if modelos_en_series:
                for nombre in modelos_en_series:
                    nombre_limpio = nombre.upper()
                    if nombre_limpio not in productos:
                        productos[nombre_limpio] = {"curvas": [], "tablas": []}
                    # Cada modelo recibe el grafico completo (tiene sus series)
                    if grafico not in productos[nombre_limpio]["curvas"]:
                        productos[nombre_limpio]["curvas"].append(grafico)
            else:
                # Fallback: titulo completo como clave
                if nombre_titulo not in productos:
                    productos[nombre_titulo] = {"curvas": [], "tablas": []}
                productos[nombre_titulo]["curvas"].append(grafico)

    # Tablas con columna MODELO: asociar por modelo
    tablas_con_modelo = []
    tablas_con_serie = []
    tablas_generales = []

    for tabla in catalogo.get("tablas", []):
        columnas = tabla.get("columnas", [])
        if "MODELO" in columnas:
            tablas_con_modelo.append(tabla)
        elif "Serie" in columnas:
            tablas_con_serie.append(tabla)
        else:
            tablas_generales.append(tabla)

    # Tablas con columna MODELO
    for tabla in tablas_con_modelo:
        modelos_en_tabla = set()
        for fila in tabla.get("filas", []):
            modelo = fila.get("MODELO", "")
            if modelo:
                modelos_en_tabla.add(modelo.upper())
        for nombre in modelos_en_tabla:
            if nombre in productos:
                productos[nombre]["tablas"].append(tabla)
            else:
                # Modelo en tabla que no está en graficos: crear igual
                productos[nombre] = {"curvas": [], "tablas": [tabla]}

    # Tablas con columna Serie (estilo FPS)
    for tabla in tablas_con_serie:
        series_en_tabla = set()
        for fila in tabla.get("filas", []):
            serie = fila.get("Serie", "")
            if serie:
                series_en_tabla.add(_limpiar_nombre(serie))
        for nombre in series_en_tabla:
            if nombre in productos:
                productos[nombre]["tablas"].append(tabla)

    # Tablas generales: agregar a todos
    for nombre in productos:
        productos[nombre]["tablas"].extend(tablas_generales)

    return productos

def indexar_catalogo(ruta_json: str):
    """
    Lee el JSON de un catalogo procesado, separa por modelo,
    genera embeddings y los guarda en Qdrant.
    """
    # Inicializar embedder dentro de la funcion para evitar
    # conflictos al importar junto con otras librerias del proyecto
    embedder = TextEmbedding(model_name=_EMBEDDING_MODEL)

    catalogo = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    fuente = catalogo.get("fuente", {})

    productos = _separar_por_modelo(catalogo)
    print(f"Modelos identificados: {list(productos.keys())}")

    from core.qdrant_client import get_cliente
    cliente = get_cliente()

    colecciones = [c.name for c in cliente.get_collections().collections]
    if _COLECCION not in colecciones:
        cliente.create_collection(
            collection_name=_COLECCION,
            vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE),
        )
        print(f"Coleccion '{_COLECCION}' creada en Qdrant")

# Traer el maximo ID existente para no pisar productos ya indexados
    existentes = cliente.scroll(_COLECCION, limit=1000, with_payload=False, with_vectors=False)
    ids_existentes = {p.id for p in existentes[0]}
    proximo_id = max(ids_existentes) + 1 if ids_existentes else 0

    puntos = []
    for i, (nombre, datos) in enumerate(productos.items()):
        texto = _texto_producto(nombre, datos["curvas"], datos["tablas"])
        vector = list(embedder.embed([texto]))[0].tolist()

        payload = {
            "modelo": nombre,
            "fuente": fuente,
            "num_curvas": len(datos["curvas"]),
            "num_tablas": len(datos["tablas"]),
            "curvas": datos["curvas"],
            "tablas": datos["tablas"],
        }

        puntos.append(PointStruct(id=proximo_id + i, vector=vector, payload=payload))
        print(f"  Vectorizado: {nombre} ({len(texto)} chars)")

    if not puntos:
        print("Sin productos para indexar — archivo omitido", flush=True)
        return 0
    cliente.upsert(collection_name=_COLECCION, points=puntos)
    print(f"\nIndexados {len(puntos)} productos en Qdrant", flush=True)
    return len(puntos)