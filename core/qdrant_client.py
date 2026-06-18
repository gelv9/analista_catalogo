# core/qdrant_client.py
# Cliente Qdrant guardado en session_state de Streamlit para que
# sobreviva las re-ejecuciones del script y no haya instancias duplicadas.
# Fuera de Streamlit (scripts, tests) usa un singleton de módulo normal.
from qdrant_client import QdrantClient

_cliente = None

def get_cliente() -> QdrantClient:
    global _cliente
    if _cliente is None:
        _cliente = QdrantClient(host="localhost", port=6333)
    return _cliente