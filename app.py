# app.py
# Interfaz principal del sistema analista_catalogo.
# Cuatro secciones: cargar catalogo, exportar datos, comparar, base de datos.

import glob
import json
import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Analista de Catálogos",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Analista de Catálogos Industriales")
st.caption("Extracción, indexado y comparación de productos técnicos")

# ── Sidebar: estado de la base ──────────────────────────────────────────────
with st.sidebar:
    st.header("Base de conocimiento")
    try:
        from core.qdrant_client import get_cliente
        cliente = get_cliente()
        info = cliente.get_collection("productos")
        st.success(f"{info.points_count} productos indexados")
        res = cliente.scroll("productos", limit=50, with_payload=True, with_vectors=False)
        modelos = [p.payload["modelo"] for p in res[0]]
        for m in modelos:
            st.caption(f"• {m}")
    except Exception:
        st.warning("Base vacía o no inicializada")

# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📥 Cargar catálogo",
    "📤 Exportar datos",
    "🔍 Comparar productos"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CARGAR CATÁLOGO
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Cargar catálogo PDF")
    st.info(
        "Subí el PDF de un catálogo industrial. El sistema detecta automáticamente "
        "las páginas con gráficos/curvas y las páginas con tablas, las procesa y "
        "las indexa en la base para futuras comparaciones."
    )

    pdf_file = st.file_uploader("Seleccioná el PDF", type="pdf")

    if pdf_file:
        st.write(f"**Archivo:** {pdf_file.name} ({pdf_file.size/1024:.0f} KB)")

        nombre_indice = st.text_input(
            "Nombre del índice ColPali",
            value=Path(pdf_file.name).stem[:20].strip().replace(" ", "_"),
            help="Identificador único para este catálogo en el índice visual"
        )

        col1, col2 = st.columns(2)
        with col1:
            procesar = st.button("🚀 Procesar e indexar", type="primary")

        if procesar:
            # Guardar PDF temporalmente
            tmp_dir = Path("temp")
            tmp_dir.mkdir(exist_ok=True)
            ruta_pdf = tmp_dir / pdf_file.name
            ruta_pdf.write_bytes(pdf_file.read())

            Path("outputs").mkdir(exist_ok=True)
            ruta_json = Path("outputs") / f"{Path(pdf_file.name).stem}.json"

            with st.status("Procesando catálogo...", expanded=True) as status:

                st.write("🔍 Detectando páginas con curvas (ColPali)...")
                from core.detector import indexar_pdf, cargar_indice, detectar_paginas_curva
                modelo_colpali = indexar_pdf(str(ruta_pdf), nombre_indice)
                paginas_curva = detectar_paginas_curva(modelo_colpali)
                st.write(f"✅ Páginas con curvas: {paginas_curva}")

                st.write("📈 Extrayendo curvas (Claude API)...")
                from core.render import pagina_a_imagen
                from core.extractor_curvas import extraer_curvas
                graficos = []
                prog = st.progress(0)
                for i, pag in enumerate(paginas_curva):
                    imagen = pagina_a_imagen(str(ruta_pdf), pag)
                    graficos.append({"pagina": pag, "datos": extraer_curvas(imagen)})
                    prog.progress((i + 1) / len(paginas_curva))
                st.write(f"✅ {len(graficos)} curvas extraídas")

                st.write("📋 Extrayendo tablas (pdfplumber)...")
                from core.extractor_tablas import extraer_tablas, construir_tabla
                from core.pipeline import es_tabla_real
                crudas = extraer_tablas(str(ruta_pdf))
                candidatas = [
                    t for t in crudas
                    if t["pagina"] not in paginas_curva and es_tabla_real(t["cruda"])
                ]
                tablas = []
                prog2 = st.progress(0)
                for i, t in enumerate(candidatas):
                    construida = construir_tabla(t["cruda"])
                    tablas.append({"pagina": t["pagina"], **construida})
                    prog2.progress((i + 1) / len(candidatas))
                st.write(f"✅ {len(tablas)} tablas extraídas")

                st.write("💾 Guardando JSON...")
                from datetime import date
                catalogo = {
                    "fuente": {
                        "archivo": pdf_file.name,
                        "fecha_extraccion": str(date.today()),
                        "paginas_curva": paginas_curva,
                    },
                    "graficos": graficos,
                    "tablas": tablas,
                }
                ruta_json.write_text(
                    json.dumps(catalogo, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

                st.write("🗄️ Indexando en Qdrant...")
                from core.indexador import indexar_catalogo
                n = indexar_catalogo(str(ruta_json))
                st.write(f"✅ {n} productos indexados")

                status.update(label="✅ Catálogo procesado e indexado", state="complete")

            st.success(f"Catálogo listo. JSON guardado en `{ruta_json}`")
            st.session_state["ultimo_json"] = str(ruta_json)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — EXPORTAR DATOS
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Exportar datos del catálogo")

    jsons = glob.glob("outputs/*.json")
    if not jsons:
        st.warning("No hay catálogos procesados todavía.")
    else:
        catalogo_sel = st.selectbox(
            "Seleccioná el catálogo",
            jsons,
            format_func=lambda x: Path(x).stem
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 Generar Excel"):
                from core.exportador import exportar_excel_bytes
                nombre_archivo = Path(catalogo_sel).stem + ".xlsx"
                datos_xlsx = exportar_excel_bytes(catalogo_sel)
                st.download_button(
                    label="⬇️ Descargar Excel",
                    data=datos_xlsx,
                    file_name=nombre_archivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        with col2:
            if st.button("📄 Generar JSON productos"):
                from core.exportador import exportar_json_productos
                ruta_prod = exportar_json_productos(catalogo_sel)
                with open(ruta_prod, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="⬇️ Descargar JSON",
                        data=f.read(),
                        file_name="productos.json",
                        mime="application/json"
                    )

        # Preview del catálogo seleccionado
        with st.expander("Vista previa del catálogo"):
            datos = json.loads(Path(catalogo_sel).read_text(encoding="utf-8"))
            st.write(f"**Gráficos:** {len(datos.get('graficos',[]))}")
            st.write(f"**Tablas:** {len(datos.get('tablas',[]))}")
            for g in datos.get("graficos", []):
                titulo = g.get("datos", {}).get("titulo", "sin título")
                st.caption(f"• Pág {g['pagina']}: {titulo}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPARAR PRODUCTOS
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Comparar productos")

    modo = st.radio(
        "Modo de entrada",
        ["📝 Consulta en texto libre", "📄 PDF nuevo"],
        horizontal=True,
        key="modo_comparacion"
    )

    # ── Modo texto libre ─────────────────────────────────────────────────
    if modo == "📝 Consulta en texto libre":

        # Limpiar resultados del modo PDF si los hubiera
        if "resultados_pdf" in st.session_state:
            del st.session_state["resultados_pdf"]

        consulta = st.text_area(
            "Describí el producto que necesitás",
            placeholder=(
                "Ej: Bomba centrífuga, caudal 100 GPM, carga 150 pies, "
                "conexión roscada 2 pulgadas, motor trifásico 5HP, 3600 RPM."
            ),
            height=120,
            key="consulta_input"
        )
        top_k = st.slider("Cantidad de candidatos a comparar", 1, 5, 2, key="topk_texto")

        if st.button("🔍 Buscar y comparar", type="primary", key="btn_texto"):
            if not consulta.strip():
                st.warning("Escribí una descripción del producto.")
            else:
                with st.spinner("Buscando candidatos y generando reportes..."):
                    from core.comparador import comparar_desde_texto
                    st.session_state["resultados_texto"] = comparar_desde_texto(consulta, top_k=top_k)
                    st.session_state["consulta_texto"] = consulta

        if "resultados_texto" in st.session_state:
            st.divider()
            for r in st.session_state["resultados_texto"]:
                with st.expander(
                    f"**{r['modelo']}** — Similitud: {r['score_similitud']}",
                    expanded=True
                ):
                    st.markdown(r["reporte"])
                    from core.reporte_pdf import generar_reporte_pdf
                    pdf_bytes = generar_reporte_pdf(
                        consulta=st.session_state.get("consulta_texto", ""),
                        modelo_candidato=r["modelo"],
                        score_similitud=r["score_similitud"],
                        reporte_md=r["reporte"],
                    )
                    st.download_button(
                        label="⬇️ Descargar reporte PDF",
                        data=pdf_bytes,
                        file_name=f"reporte_{r['modelo'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_texto_{r['modelo']}"
                    )

    # ── Modo PDF nuevo ───────────────────────────────────────────────────
    else:

        # Limpiar resultados del modo texto si los hubiera
        if "resultados_texto" in st.session_state:
            del st.session_state["resultados_texto"]

        pdf_nuevo = st.file_uploader(
            "Subí el PDF del producto alternativo",
            type="pdf",
            key="pdf_comparar"
        )

        if pdf_nuevo:
            nombre_indice_nuevo = st.text_input(
                "Nombre del índice para este PDF",
                value=f"nuevo_{Path(pdf_nuevo.name).stem[:15].strip().replace(' ', '_')}",
                key="indice_nuevo"
            )
            top_k2 = st.slider("Cantidad de candidatos", 1, 5, 2, key="topk2")

            if st.button("🔍 Procesar y comparar", type="primary", key="btn_pdf"):
                tmp_dir = Path("temp")
                tmp_dir.mkdir(exist_ok=True)
                ruta_nuevo = tmp_dir / pdf_nuevo.name
                ruta_nuevo.write_bytes(pdf_nuevo.read())

                with st.status("Procesando PDF nuevo...", expanded=True) as status:
                    st.write("🔍 Detectando curvas...")
                    from core.detector import indexar_pdf, detectar_paginas_curva
                    modelo_nuevo = indexar_pdf(str(ruta_nuevo), nombre_indice_nuevo)
                    paginas_curva_nuevo = detectar_paginas_curva(modelo_nuevo)
                    st.write(f"✅ Páginas con curvas: {paginas_curva_nuevo}")

                    st.write("📈 Extrayendo curvas...")
                    from core.render import pagina_a_imagen
                    from core.extractor_curvas import extraer_curvas
                    graficos_nuevo = []
                    for pag in paginas_curva_nuevo:
                        imagen = pagina_a_imagen(str(ruta_nuevo), pag)
                        graficos_nuevo.append({
                            "pagina": pag,
                            "datos": extraer_curvas(imagen)
                        })

                    st.write("📋 Extrayendo tablas...")
                    from core.extractor_tablas import extraer_tablas, construir_tabla
                    from core.pipeline import es_tabla_real
                    crudas_nuevo = extraer_tablas(str(ruta_nuevo))
                    candidatas_nuevo = [
                        t for t in crudas_nuevo
                        if t["pagina"] not in paginas_curva_nuevo
                        and es_tabla_real(t["cruda"])
                    ]
                    tablas_nuevo = []
                    for t in candidatas_nuevo:
                        construida = construir_tabla(t["cruda"])
                        tablas_nuevo.append({"pagina": t["pagina"], **construida})

                    producto_nuevo = {
                        "fuente": pdf_nuevo.name,
                        "graficos": graficos_nuevo,
                        "tablas": tablas_nuevo,
                    }

                    st.write("⚖️ Comparando con base de conocimiento...")
                    from core.comparador import comparar_desde_json
                    st.session_state["resultados_pdf"] = comparar_desde_json(
                        producto_nuevo, top_k=top_k2
                    )
                    st.session_state["consulta_pdf"] = pdf_nuevo.name
                    status.update(label="✅ Comparación lista", state="complete")

        if "resultados_pdf" in st.session_state:
            st.divider()
            for r in st.session_state["resultados_pdf"]:
                with st.expander(
                    f"**{r['modelo']}** — Similitud: {r['score_similitud']}",
                    expanded=True
                ):
                    st.markdown(r["reporte"])
                    from core.reporte_pdf import generar_reporte_pdf
                    pdf_bytes = generar_reporte_pdf(
                        consulta=st.session_state.get("consulta_pdf", ""),
                        modelo_candidato=r["modelo"],
                        score_similitud=r["score_similitud"],
                        reporte_md=r["reporte"],
                    )
                    st.download_button(
                        label="⬇️ Descargar reporte PDF",
                        data=pdf_bytes,
                        file_name=f"reporte_{r['modelo'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{r['modelo']}"
                    )