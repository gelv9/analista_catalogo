# buscar.py
from core.detector import cargar_indice, buscar_paginas

print("Cargando indice y modelo...", flush=True)
modelo = cargar_indice("catalogo")

res = buscar_paginas(modelo, "performance curve chart with axes and grid lines", k=32)
print("\nTodas las paginas ordenadas por score:\n", flush=True)
for r in res:
    print(f"  pagina {r['pagina']:>2}   score {r['score']:.3f}", flush=True)