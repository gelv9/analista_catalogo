# schemas/producto.py
# Schema universal para cualquier producto de catálogo industrial.
# No nombra campos de ningún subtipo (nada de "impulsor", "caudal", etc).
# Captura los datos tal como aparecen en el documento: etiquetas, unidades
# y valores originales. El LLM razona sobre esto en la comparación.

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class Fuente(BaseModel):
    archivo: str
    paginas_usadas: list[int] = Field(default_factory=list)
    fecha_extraccion: date = Field(default_factory=date.today)


class Producto(BaseModel):
    # Solo identificación; nada técnico-específico de un rubro
    fabricante: Optional[str] = None
    serie: Optional[str] = None
    modelo: str                          # único campo obligatorio
    categoria: Optional[str] = None      # lo que el documento/LLM indique


# --- Datos de gráficos/curvas (genérico) ---

class Eje(BaseModel):
    etiqueta: Optional[str] = None                      # "CARGA", "HEAD"...
    unidades: list[str] = Field(default_factory=list)   # ["metros", "pies"]
    rango: Optional[dict] = None                        # {"min":0,"max":250}


class Serie(BaseModel):
    etiqueta: Optional[str] = None                      # '6.437" (10 hp)'...
    tipo: Optional[str] = None                          # lo que infiera el LLM
    puntos: list[dict] = Field(default_factory=list)    # [{"x":.., "y":..}]


class DatosGrafico(BaseModel):
    titulo: Optional[str] = None
    ejes: list[Eje] = Field(default_factory=list)
    series: list[Serie] = Field(default_factory=list)
    texto_visible: list[str] = Field(default_factory=list)


# --- Datos de tablas/texto (genérico) ---
# Diccionario abierto: las claves son los nombres que trae el documento.

class TablaGenerica(BaseModel):
    titulo: Optional[str] = None
    columnas: list[str] = Field(default_factory=list)   # headers originales
    filas: list[dict] = Field(default_factory=list)     # {header: valor}


# --- Imágenes crudas de las páginas usadas ---

class RawPaginas(BaseModel):
    graficos: Optional[str] = None       # base64 de la imagen
    tablas: Optional[str] = None         # base64 de la imagen


# --- Schema raíz ---

class ProductoSchema(BaseModel):
    fuente: Fuente
    producto: Producto

    # Datos genéricos, sin estructura fija por subtipo
    graficos: list[DatosGrafico] = Field(default_factory=list)
    tablas: list[TablaGenerica] = Field(default_factory=list)
    atributos: dict = Field(default_factory=dict)   # clave→valor abiertos

    # Reservado para cuando exista el módulo de planos isométricos
    punto_operacion: Optional[dict] = None

    etiquetas: list[str] = Field(default_factory=list)
    raw_paginas: RawPaginas = Field(default_factory=RawPaginas)