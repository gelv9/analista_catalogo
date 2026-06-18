# indexar.py
# Indexa el PDF del catalogo con ColPali, con diagnostico por etapa.

import sys
print("1. arrancando script", flush=True)

import glob
print("2. importando detector (carga byaldi/torch, puede tardar)...", flush=True)

from core.detector import indexar_pdf
print("3. detector importado OK", flush=True)

pdf = glob.glob("fixtures/*.pdf")[0]
print("4. PDF encontrado:", pdf, flush=True)

print("5. indexando (la primera vez descarga el modelo, varios GB)...", flush=True)
indexar_pdf(pdf)
print("6. Indexado OK — indice en .byaldi/", flush=True)