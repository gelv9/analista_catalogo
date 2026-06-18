# core/indexador.py
# Toma el JSON de un catalogo ya procesado, separa los productos por modelo,
# genera embeddings con fastembed (local, $0, sin conflictos de numpy) y
# los indexa en Qdrant. Un punto por modelo de producto.

import re
import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
import streamlit as st
# indexar_catalogo.py
import glob
from core.indexador import indexar_catalogo

@st.cache_resource
def get_qdrant_client():
    return QdrantClient(path="./qdrant_catalogo_storage")

ruta = glob.glob("outputs/*.json")[0]
print(f"Indexando: {ruta}", flush=True)
indexar_catalogo(ruta)

# Modelo liviano, corre en CPU, compatible con numpy 1.26
_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_COLECCION = "productos"
_DIM = 384

_embedder = TextEmbedding(model_name=_EMBEDDING_MODEL)


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
    El nombre del modelo se extrae del titulo de cada grafico.
    """
    productos = {}

    for grafico in catalogo.get("graficos", []):
        titulo = grafico.get("datos", {}).get("titulo", "")
        if not titulo:
            continue
        nombre = _limpiar_nombre(titulo)
        if nombre not in productos:
            productos[nombre] = {"curvas": [], "tablas": []}
        productos[nombre]["curvas"].append(grafico)

    tablas_con_serie = []
    tablas_generales = []

    for tabla in catalogo.get("tablas", []):
        if "Serie" in tabla.get("columnas", []):
            tablas_con_serie.append(tabla)
        else:
            tablas_generales.append(tabla)

    for tabla in tablas_con_serie:
        series_en_tabla = set()
        for fila in tabla.get("filas", []):
            serie = fila.get("Serie", "")
            if serie:
                nombre = _limpiar_nombre(serie)
                series_en_tabla.add(nombre)
        for nombre in series_en_tabla:
            if nombre in productos:
                productos[nombre]["tablas"].append(tabla)

    for nombre in productos:
        productos[nombre]["tablas"].extend(tablas_generales)

    return productos


def indexar_catalogo(ruta_json: str):
    """
    Lee el JSON de un catalogo procesado, separa por modelo,
    genera embeddings y los guarda en Qdrant.
    """
    catalogo = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    fuente = catalogo.get("fuente", {})

    productos = _separar_por_modelo(catalogo)
    print(f"Modelos identificados: {list(productos.keys())}")

    cliente = QdrantClient(path="./qdrant_storage")

    colecciones = [c.name for c in cliente.get_collections().collections]
    if _COLECCION not in colecciones:
        cliente.create_collection(
            collection_name=_COLECCION,
            vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE),
        )
        print(f"Coleccion '{_COLECCION}' creada en Qdrant")

    puntos = []
    for i, (nombre, datos) in enumerate(productos.items()):
        texto = _texto_producto(nombre, datos["curvas"], datos["tablas"])
        vector = list(_embedder.embed([texto]))[0].tolist()

        payload = {
            "modelo": nombre,
            "fuente": fuente,
            "num_curvas": len(datos["curvas"]),
            "num_tablas": len(datos["tablas"]),
            "curvas": datos["curvas"],
            "tablas": datos["tablas"],
        }

        puntos.append(PointStruct(id=i, vector=vector, payload=payload))
        print(f"  Vectorizado: {nombre} ({len(texto)} chars)")

    cliente.upsert(collection_name=_COLECCION, points=puntos)
    print(f"\nIndexados {len(puntos)} productos en Qdrant")
    return len(puntos)