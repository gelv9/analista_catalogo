# procesar.py
import glob, json
from pathlib import Path
from core.pipeline import procesar_catalogo

pdf = glob.glob("fixtures/*.pdf")[0]

# Primera corrida LIMITADA para validar el flujo sin gastar de mas.
resultado = procesar_catalogo(pdf)

Path("outputs").mkdir(exist_ok=True)
salida = Path("outputs") / (Path(pdf).stem + ".json")
with open(salida, "w", encoding="utf-8") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False)

print(f"\nGuardado en {salida}")
print(f"Graficos: {len(resultado['graficos'])}  Tablas: {len(resultado['tablas'])}")