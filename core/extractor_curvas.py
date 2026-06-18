# core/extractor_curvas.py
# Recibe la imagen de una pagina con graficos/curvas.
# La envia a Claude API y devuelve un dict con los datos extraidos.
# Claude solo ve la imagen de la pagina especifica, nunca el PDF completo.

import base64
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Cargamos el master prompt una sola vez al importar el modulo
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "curvas.txt"
_MASTER_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

_cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def imagen_a_base64(ruta_imagen: str) -> str:
    """Convierte una imagen a base64 para enviarla a Claude."""
    with open(ruta_imagen, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extraer_curvas(ruta_imagen: str) -> dict:
    """
    Recibe la ruta de una imagen (pagina de catalogo con graficos).
    Devuelve un dict con los datos extraidos por Claude.
    Si Claude no puede extraer algo, el campo queda en null.
    """
    imagen_b64 = imagen_a_base64(ruta_imagen)

    # Detectamos el tipo de imagen por extension
    extension = Path(ruta_imagen).suffix.lower()
    tipos = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".webp": "image/webp"}
    media_type = tipos.get(extension, "image/jpeg")

    respuesta = _cliente.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": imagen_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _MASTER_PROMPT
                    }
                ],
            }
        ],
    )

    texto = respuesta.content[0].text.strip()

    # Limpiamos por si Claude agrega backticks de markdown
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {"error": "JSON invalido", "raw": texto}