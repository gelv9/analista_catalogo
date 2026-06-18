# estadisticas.py
import json, glob
from collections import Counter

ruta = glob.glob("outputs/*.json")[0]
d = json.load(open(ruta, encoding="utf-8"))

print(f"Graficos: {len(d['graficos'])} paginas")
for g in d["graficos"]:
    titulo = g["datos"].get("titulo", "sin titulo")
    series = len(g["datos"].get("series", []))
    ejes = [e["etiqueta"] for e in g["datos"].get("ejes", [])]
    print(f"  pag {g['pagina']:>2} | {titulo} | {series} series | ejes: {ejes}")

print(f"\nTablas: {len(d['tablas'])} encontradas")
for t in d["tablas"]:
    print(f"  pag {t['pagina']:>2} | {len(t['filas'])} filas | cols: {t['columnas'][:4]}...")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   