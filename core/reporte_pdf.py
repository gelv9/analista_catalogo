# core/reporte_pdf.py
# Genera un PDF descargable con el reporte de comparacion.
# Usa reportlab, sin dependencias externas complicadas.

import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


# ── Estilos ────────────────────────────────────────────────────────────────

def _estilos():
    base = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "titulo",
        parent=base["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a3a5c"),
        spaceAfter=4,
    )
    subtitulo = ParagraphStyle(
        "subtitulo",
        parent=base["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#2e6da4"),
        spaceBefore=12,
        spaceAfter=4,
    )
    cuerpo = ParagraphStyle(
        "cuerpo",
        parent=base["Normal"],
        fontSize=9,
        leading=14,
        spaceAfter=4,
    )
    veredicto_compatible = ParagraphStyle(
        "veredicto_compatible",
        parent=base["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#1a6e1a"),
        backColor=colors.HexColor("#e8f5e9"),
        borderPad=6,
        spaceAfter=8,
    )
    veredicto_incompatible = ParagraphStyle(
        "veredicto_incompatible",
        parent=base["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#8b0000"),
        backColor=colors.HexColor("#fdecea"),
        borderPad=6,
        spaceAfter=8,
    )
    veredicto_revisar = ParagraphStyle(
        "veredicto_revisar",
        parent=base["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#7a4f00"),
        backColor=colors.HexColor("#fff8e1"),
        borderPad=6,
        spaceAfter=8,
    )
    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "cuerpo": cuerpo,
        "veredicto_compatible": veredicto_compatible,
        "veredicto_incompatible": veredicto_incompatible,
        "veredicto_revisar": veredicto_revisar,
    }


def _estilo_veredicto(texto: str, estilos: dict) -> ParagraphStyle:
    """Elige el estilo del veredicto según el texto."""
    texto_up = texto.upper()
    if "INCOMPATIBLE" in texto_up:
        return estilos["veredicto_incompatible"]
    if "COMPATIBLE" in texto_up:
        return estilos["veredicto_compatible"]
    return estilos["veredicto_revisar"]


def _parsear_secciones(reporte_md: str) -> list[tuple[str, str]]:
    """
    Divide el reporte markdown en secciones (titulo, contenido).
    Cada sección empieza con ### en el markdown.
    """
    secciones = []
    seccion_actual = None
    lineas_actuales = []

    for linea in reporte_md.split("\n"):
        if linea.startswith("### "):
            if seccion_actual is not None:
                secciones.append((seccion_actual, "\n".join(lineas_actuales).strip()))
            seccion_actual = linea[4:].strip()
            lineas_actuales = []
        else:
            lineas_actuales.append(linea)

    if seccion_actual is not None:
        secciones.append((seccion_actual, "\n".join(lineas_actuales).strip()))

    return secciones


def _contenido_a_parrafos(texto, estilo):
    import re
    elementos = []
    for linea in texto.split("\n"):
        linea = linea.strip()
        if not linea:
            elementos.append(Spacer(1, 4))
            continue
        # Bullet
        if linea.startswith("* ") or linea.startswith("- "):
            linea = "• " + linea[2:]
        # Eliminar TODO el markdown y tags HTML — texto plano
        linea = re.sub(r'\*\*(.+?)\*\*', r'\1', linea)  # **negrita** → negrita
        linea = re.sub(r'\*(.+?)\*', r'\1', linea)        # *italica* → italica
        linea = re.sub(r'<[^>]+>', '', linea)              # <cualquier tag> → nada
        linea = linea.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if linea.strip():
            elementos.append(Paragraph(linea, estilo))
    return elementos

def generar_reporte_pdf(
    consulta: str,
    modelo_candidato: str,
    score_similitud: float,
    reporte_md: str,
) -> bytes:
    """
    Genera el PDF del reporte de comparacion en memoria.
    Devuelve bytes listos para descargar desde Streamlit.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
    )

    estilos = _estilos()
    elementos = []

    # ── Encabezado ──────────────────────────────────────────────────────────
    elementos.append(Paragraph("Reporte de Sustitución", estilos["titulo"]))
    elementos.append(Paragraph(
        f"Analista de Catálogos Industriales · {date.today().strftime('%d/%m/%Y')}",
        estilos["cuerpo"]
    ))
    elementos.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#2e6da4")))
    elementos.append(Spacer(1, 8))

    # ── Datos del análisis ──────────────────────────────────────────────────
    tabla_datos = Table(
        [
            ["Consulta / producto solicitado:", consulta],
            ["Candidato propuesto:", modelo_candidato],
            ["Similitud en base:", f"{score_similitud:.1%}"],
        ],
        colWidths=[5*cm, 12*cm],
    )
    tabla_datos.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#f0f4f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 12))

    # ── Secciones del reporte ───────────────────────────────────────────────
    secciones = _parsear_secciones(reporte_md)

    for titulo_sec, contenido in secciones:
        if titulo_sec == "VEREDICTO":
            import re
            elementos.append(Paragraph("VEREDICTO", estilos["subtitulo"]))
            contenido_limpio = re.sub(r'\*+', '', contenido).replace("\n", " ").strip()
            elementos.append(Paragraph(contenido_limpio, _estilo_veredicto(contenido, estilos)))
        else:
            elementos.append(Paragraph(titulo_sec, estilos["subtitulo"]))
            elementos.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#cccccc")
            ))
            elementos.append(Spacer(1, 4))
            for elem in _contenido_a_parrafos(contenido, estilos["cuerpo"]):
                elementos.append(elem)

    # ── Pie de página ───────────────────────────────────────────────────────
    elementos.append(Spacer(1, 16))
    elementos.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#cccccc")))
    elementos.append(Paragraph(
        "La decisión económica y final de sustitución es responsabilidad del ingeniero a cargo.",
        ParagraphStyle("pie", parent=estilos["cuerpo"],
                       fontSize=8, textColor=colors.grey)
    ))

    doc.build(elementos)
    return buffer.getvalue()