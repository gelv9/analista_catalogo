# core/comparador.py
# Motor de comparacion y sustitucion.
# Soporta dos modos de entrada:
#   A) JSON ya extraido de un PDF nuevo (via pipeline)
#   B) Consulta en texto libre del usuario
# En ambos casos busca candidatos en Qdrant y Claude compara JSON vs JSON.

import os
import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastembed import TextEmbedding
from qdrant_client import QdrantClient

load_dotenv()

_COLECCION = "productos"
_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "comparador.txt"

_cliente_anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_embedder():
    return TextEmbedding(model_name=_EMBEDDING_MODEL)


def _get_qdrant():
    from core.qdrant_client import get_cliente
    return get_cliente()


def buscar_candidatos(vector: list, top_k: int = 3) -> list[dict]:
    """
    Busca los productos mas similares en Qdrant por similitud de vector.
    Devuelve lista de payloads ordenados por score.
    """
    cliente = _get_qdrant()
    resultados = cliente.query_points(
        collection_name=_COLECCION,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {"score": r.score, "producto": r.payload}
        for r in resultados.points
    ]

def vectorizar_texto(texto: str) -> list:
    """Convierte texto libre a vector para buscar en Qdrant."""
    embedder = _get_embedder()
    return list(embedder.embed([texto]))[0].tolist()


def vectorizar_producto(producto_json: dict) -> list:
    """
    Convierte un producto extraido de PDF a vector.
    Usa el mismo formato que el indexador para que los vectores sean comparables.
    """
    partes = []
    modelo = producto_json.get("modelo", "")
    if modelo:
        partes.append(f"modelo {modelo}")

    for g in producto_json.get("graficos", []):
        datos = g.get("datos", g)
        for eje in datos.get("ejes", []):
            partes.append(f"{eje.get('etiqueta','')} {' '.join(eje.get('unidades',[]))}")
        for serie in datos.get("series", []):
            if serie.get("etiqueta"):
                partes.append(serie["etiqueta"])

    for t in producto_json.get("tablas", []):
        partes.extend(t.get("columnas", []))

    texto = " | ".join(p for p in partes if p and p.strip())
    embedder = _get_embedder()
    return list(embedder.embed([texto]))[0].tolist()


def comparar_con_claude(producto_nuevo: dict, candidato: dict) -> str:
    """
    Claude compara el producto nuevo contra el candidato de la base.
    Recibe dos JSONs, devuelve un reporte de sustitucion en texto.
    Claude no ve ningun PDF — solo los datos ya extraidos.
    """
    prompt_base = _PROMPT_PATH.read_text(encoding="utf-8")

    contenido = f"""{prompt_base}

## PRODUCTO SOLICITADO / NUEVO:
```json
{json.dumps(producto_nuevo, ensure_ascii=False, indent=2)}
```

## CANDIDATO EN BASE DE CONOCIMIENTO:
```json
{json.dumps(candidato, ensure_ascii=False, indent=2)}
```
"""

    respuesta = _cliente_anthropic.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": contenido}],
    )
    return respuesta.content[0].text


def comparar_desde_texto(consulta: str, top_k: int = 3) -> list[dict]:
    """
    Caso B: el usuario describe el producto en texto libre.
    Busca candidatos en Qdrant y compara cada uno con Claude.
    """
    vector = vectorizar_texto(consulta)
    candidatos = buscar_candidatos(vector, top_k=top_k)

    resultados = []
    for c in candidatos:
        reporte = comparar_con_claude(
            {"descripcion_consulta": consulta},
            c["producto"]
        )
        resultados.append({
            "modelo": c["producto"]["modelo"],
            "score_similitud": round(c["score"], 3),
            "reporte": reporte,
        })
    return resultados


def comparar_desde_json(producto_nuevo: dict, top_k: int = 3) -> list[dict]:
    """
    Caso A: el producto nuevo ya fue extraido de un PDF (es un JSON).
    Busca candidatos en Qdrant y compara cada uno con Claude.
    """
    vector = vectorizar_producto(producto_nuevo)
    candidatos = buscar_candidatos(vector, top_k=top_k)

    resultados = []
    for c in candidatos:
        reporte = comparar_con_claude(producto_nuevo, c["producto"])
        resultados.append({
            "modelo": c["producto"]["modelo"],
            "score_similitud": round(c["score"], 3),
            "reporte": reporte,
        })
    return resultados
