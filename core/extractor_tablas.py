# core/extractor_tablas.py
# Extrae tablas de un PDF vectorial con pdfplumber (estrategia "lines").
# pdfplumber alinea bien los DATOS; los NOMBRES de columna (headers
# multinivel, cortes de texto) los normaliza Claude con una pasada minima
# que solo ve las primeras filas, nunca los datos completos.
# Totalmente generico: no asume ningun nombre de columna.

import json
import os
from pathlib import Path

import pdfplumber
import anthropic
from dotenv import load_dotenv

load_dotenv()

_PROMPT_HEADERS = (
    Path(__file__).parent.parent / "prompts" / "headers.txt"
).read_text(encoding="utf-8")

_cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extraer_tablas(ruta_pdf: str) -> list[dict]:
    """
    Recorre todas las paginas del PDF y devuelve las tablas crudas que
    encuentra pdfplumber, con su numero de pagina. Sin normalizar todavia.
    """
    tablas = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, start=1):
            for tabla_cruda in pagina.extract_tables():
                if tabla_cruda and len(tabla_cruda) >= 2:
                    tablas.append({"pagina": num_pagina, "cruda": tabla_cruda})
    return tablas


def normalizar_headers(tabla_cruda: list[list], max_filas_muestra: int = 4) -> dict:
    """
    Manda las primeras filas de la tabla a Claude para obtener los nombres
    de columna definitivos y cuantas filas iniciales son encabezado.
    Claude NO ve los datos completos, solo la muestra de cabecera.
    Devuelve {"num_filas_header": int, "columnas": [str, ...]}.
    """
    num_columnas = len(tabla_cruda[0])
    muestra = tabla_cruda[:max_filas_muestra]
    muestra_texto = json.dumps(muestra, ensure_ascii=False, indent=2)

    contenido = (
        f"{_PROMPT_HEADERS}\n\n"
        f"Número de columnas: {num_columnas}\n\n"
        f"Primeras filas de la tabla:\n{muestra_texto}"
    )

    respuesta = _cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        temperature=0,
        messages=[{"role": "user", "content": contenido}],
    )

    texto = respuesta.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()
    return json.loads(texto)


def construir_tabla(tabla_cruda: list[list]) -> dict:
    """
    Normaliza los headers con Claude, separa los datos, aplica forward-fill
    de celdas combinadas (propaga el ultimo valor no vacio hacia abajo) y
    devuelve {"columnas": [...], "filas": [{columna: valor}, ...]}.
    """
    info = normalizar_headers(tabla_cruda)
    num_header = info["num_filas_header"]
    columnas = info["columnas"]

    filas_datos = tabla_cruda[num_header:]

    ultimo = [None] * len(columnas)
    filas = []
    for fila_cruda in filas_datos:
        fila = {}
        for i in range(len(columnas)):
            celda = fila_cruda[i] if i < len(fila_cruda) else None
            celda = " ".join(celda.split()) if isinstance(celda, str) else None
            celda = celda or None
            if celda:
                ultimo[i] = celda          # actualizo el ultimo valor visto
            else:
                celda = ultimo[i]          # celda combinada: hereda de arriba
            nombre = columnas[i] if i < len(columnas) else f"col_{i}"
            fila[nombre] = celda
        filas.append(fila)

    return {"columnas": columnas, "filas": filas}

def extraer_tablas_desde_imagen(ruta_imagen: str) -> list[dict]:
    """
    Extrae tablas de una imagen usando Claude API.
    Usado cuando pdfplumber no puede leer tablas estilizadas
    (fondos de color, texto en blanco, etc).
    Devuelve lista de {titulo, columnas, filas}.
    """
    import base64
    import json as _json
    import anthropic
    from pathlib import Path as _Path

    prompt_path = _Path(__file__).parent.parent / "prompts" / "tablas_imagen.txt"
    prompt = prompt_path.read_text(encoding="utf-8")

    extension = _Path(ruta_imagen).suffix.lower()
    tipos = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".webp": "image/webp"}
    media_type = tipos.get(extension, "image/png")

    with open(ruta_imagen, "rb") as f:
        imagen_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    respuesta = cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": imagen_b64,
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )

    texto = respuesta.content[0].text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    try:
        return _json.loads(texto)
    except _json.JSONDecodeError:
        return []