#!/usr/bin/env python3
"""
Construye el documento PDF de la segunda entrega.

Todas las cifras de resultados se leen de resultados/*.json y *.csv y se
registran en documento/cifras_insertadas.json para que verificar_cifras.py
pueda comprobarlas una por una.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import evaluar as EV
REPO = "https://github.com/Cosmic-b0y/entrega2_EQ3_codigo"
LINK = f'<a href="{REPO}" color="#1F6F78"><u>{REPO.replace("https://", "")}</u></a>'
import generador_datos as GEN
from mantenimiento_ia.conocimiento import PARAMETROS

# ---------------------------------------------------------------------------
# Fuentes y estilos
# ---------------------------------------------------------------------------
LIB = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("Sans", LIB + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Sans-B", LIB + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-I", LIB + "LiberationSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans-BI", LIB + "LiberationSans-BoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans-I", boldItalic="Sans-BI")

AZUL = colors.HexColor("#1B2A41")
VERDE = colors.HexColor("#1F6F78")
CLARO = colors.HexColor("#E6F0F1")
ALTERNO = colors.HexColor("#F3F6F7")
BORDE = colors.HexColor("#C9D3D6")
GRIS = colors.HexColor("#5B6770")

st = {
    "body": ParagraphStyle("body", fontName="Sans", fontSize=10, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=7),
    "h1": ParagraphStyle("h1", fontName="Sans-B", fontSize=15, leading=19, textColor=AZUL, spaceBefore=10, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Sans-B", fontSize=11.5, leading=15, textColor=AZUL, spaceBefore=8, spaceAfter=5),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8.3, leading=10.6),
    "cellb": ParagraphStyle("cellb", fontName="Sans-B", fontSize=8.3, leading=10.6),
    "cellh": ParagraphStyle("cellh", fontName="Sans-B", fontSize=8.3, leading=10.6, textColor=colors.white),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=7.4, leading=9.3),
    "smallh": ParagraphStyle("smallh", fontName="Sans-B", fontSize=7.4, leading=9.3, textColor=colors.white),
    "cap": ParagraphStyle("cap", fontName="Sans", fontSize=8.3, leading=11, textColor=GRIS, spaceBefore=3, spaceAfter=10),
    "nota": ParagraphStyle("nota", fontName="Sans-I", fontSize=8.8, leading=12, textColor=GRIS, alignment=TA_LEFT),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=6.9, leading=8.6, textColor=AZUL),
    "ref": ParagraphStyle("ref", fontName="Sans", fontSize=9.4, leading=13, leftIndent=22, firstLineIndent=-22, spaceAfter=6),
    "toc1": ParagraphStyle("toc1", fontName="Sans", fontSize=10.5, leading=17),
}

# ---------------------------------------------------------------------------
# Registro de cifras
# ---------------------------------------------------------------------------
M = json.loads((BASE / "resultados/metricas.json").read_text(encoding="utf-8"))
PR = json.loads((BASE / "resultados/pruebas_resultados.json").read_text(encoding="utf-8"))
PR_ID = {p["id"]: p for p in PR["pruebas"]}
DEX = pd.read_csv(BASE / "resultados/decisiones_externos.csv", keep_default_na=False).set_index("id")
DTE = pd.read_csv(BASE / "resultados/decisiones_prueba.csv", keep_default_na=False).set_index("id")
REGISTRO = []


def formatear(v, f):
    if v is None:
        return "—"
    if f == "dec3":
        return f"{v:.3f}"
    if f == "dec2":
        return f"{v:.2f}"
    if f == "pct1":
        return f"{v * 100:.1f} %"
    if f == "int":
        return str(int(v))
    return str(v)


def obtener(ruta):
    v = M
    for k in (ruta if isinstance(ruta, list) else ruta.split(".")):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def m(ruta, f="dec3"):
    """Cifra de resultados/metricas.json."""
    t = formatear(obtener(ruta), f)
    REGISTRO.append({"fuente": "metricas.json", "ruta": ruta, "formato": f, "texto": t})
    return t


def p(prueba, campo, f="raw"):
    """Valor de resultados/pruebas_resultados.json."""
    t = formatear(PR_ID[prueba]["obtenido"][campo], f)
    REGISTRO.append({"fuente": "pruebas_resultados.json", "ruta": f"{prueba}.obtenido.{campo}", "formato": f, "texto": t})
    return t


def x(conj, rid, col, f="dec2"):
    """Valor de resultados/decisiones_<conj>.csv."""
    df = DEX if conj == "externos" else DTE
    t = formatear(df.loc[rid, col] if f == "raw" else float(df.loc[rid, col]), f)
    REGISTRO.append({"fuente": f"decisiones_{conj}.csv", "ruta": f"{rid}.{col}", "formato": f, "texto": t})
    return t


def prm(nombre, f="raw"):
    """Parámetro fijado en el código (no es un resultado)."""
    fuentes = {**{f"PARAMETROS.{k}": v for k, v in PARAMETROS.items()},
               "ERROR_MAX_ACEPTADOS": EV.ERROR_MAX_ACEPTADOS, "GRID_UMBRAL_MIN": EV.GRID_UMBRAL[0],
               "GRID_UMBRAL_MAX": EV.GRID_UMBRAL[-1], "SEMILLA": EV.SEMILLA, "N_ESCENARIOS": len(GEN.ESCENARIOS),
               "N_PLANTILLAS": len(GEN.PLANTILLAS), "P_DUPLICADO": GEN.P_DUPLICADO}
    t = formatear(fuentes[nombre], f)
    REGISTRO.append({"fuente": "parametro", "ruta": nombre, "formato": f, "texto": t})
    return t


# ---------------------------------------------------------------------------
# Utilidades de maquetación
# ---------------------------------------------------------------------------
def P(t, s="body"):
    return Paragraph(t, s if isinstance(s, ParagraphStyle) else st[s])


def tabla(filas, anchos, cabecera=True, chico=False, primera_col_negrita=False):
    sc = st["small"] if chico else st["cell"]
    sh = st["smallh"] if chico else st["cellh"]
    datos = []
    for i, fila in enumerate(filas):
        nueva = []
        for j, c in enumerate(fila):
            if isinstance(c, str):
                estilo = sh if (cabecera and i == 0) else (st["cellb"] if primera_col_negrita and j == 0 and not chico else sc)
                c = Paragraph(c, estilo)
            nueva.append(c)
        datos.append(nueva)
    t = Table(datos, colWidths=anchos, repeatRows=1 if cabecera else 0)
    estilo = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
              ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if cabecera:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), AZUL))
    for i in range(1 if cabecera else 0, len(datos)):
        if (i % 2 == 0) == cabecera:
            estilo.append(("BACKGROUND", (0, i), (-1, i), ALTERNO))
    t.setStyle(TableStyle(estilo))
    return t


def figura(ruta, ancho, pie):
    img = Image(str(ruta))
    r = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = ancho, ancho * r
    return KeepTogether([img, P(pie, "cap")])


def nota(texto):
    t = Table([[Paragraph(texto, st["nota"])]], colWidths=[6.9 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CLARO), ("LINEBEFORE", (0, 0), (0, -1), 3, VERDE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def codigo(texto):
    t = Table([[Preformatted(texto, st["code"])]], colWidths=[6.9 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8F9")),
                           ("BOX", (0, 0), (-1, -1), 0.5, BORDE), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def diagrama_flujo(cajas, ancho_total=6.9 * inch, alto=120, retro=None):
    n = len(cajas)
    gap = 14
    w = (ancho_total - gap * (n - 1)) / n
    d = Drawing(ancho_total, alto + (26 if retro else 0))
    y0 = 26 if retro else 0
    for i, (titulo, lineas, resaltar) in enumerate(cajas):
        x0 = i * (w + gap)
        d.add(Rect(x0, y0, w, alto, rx=4, ry=4, fillColor=AZUL if resaltar else CLARO,
                   strokeColor=VERDE, strokeWidth=1))
        color_t = colors.white if resaltar else AZUL
        d.add(String(x0 + w / 2, y0 + alto - 15, titulo, fontName="Sans-B", fontSize=7.6,
                     fillColor=color_t, textAnchor="middle"))
        for k, linea in enumerate(lineas):
            d.add(String(x0 + w / 2, y0 + alto - 30 - k * 10.2, linea, fontName="Sans", fontSize=6.7,
                         fillColor=color_t, textAnchor="middle"))
        if i < n - 1:
            xa = x0 + w + 2
            d.add(Line(xa, y0 + alto / 2, xa + gap - 6, y0 + alto / 2, strokeColor=VERDE, strokeWidth=1.2))
            d.add(Polygon([xa + gap - 6, y0 + alto / 2 + 3, xa + gap - 2, y0 + alto / 2, xa + gap - 6, y0 + alto / 2 - 3],
                          fillColor=VERDE, strokeColor=VERDE))
    if retro:
        x_ini = (n - 1) * (w + gap) + w / 2
        x_fin = w / 2
        d.add(Line(x_ini, y0, x_ini, 10, strokeColor=GRIS, strokeWidth=1, strokeDashArray=[3, 2]))
        d.add(Line(x_ini, 10, x_fin, 10, strokeColor=GRIS, strokeWidth=1, strokeDashArray=[3, 2]))
        d.add(Line(x_fin, 10, x_fin, y0 - 4, strokeColor=GRIS, strokeWidth=1, strokeDashArray=[3, 2]))
        d.add(Polygon([x_fin - 3, y0 - 6, x_fin, y0 - 1, x_fin + 3, y0 - 6], fillColor=GRIS, strokeColor=GRIS))
        d.add(String((x_ini + x_fin) / 2, 13, retro, fontName="Sans", fontSize=6.8, fillColor=GRIS, textAnchor="middle"))
    return d


class Documento(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "h1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))


def encabezado(canvas, doc):
    canvas.saveState()
    canvas.setFont("Sans", 7.8)
    canvas.setFillColor(GRIS)
    canvas.drawRightString(letter[0] - 0.8 * inch, letter[1] - 0.5 * inch, "UNACH  |  INTELIGENCIA ARTIFICIAL  |  EQUIPO 3")
    canvas.setStrokeColor(BORDE)
    canvas.line(0.8 * inch, 0.62 * inch, letter[0] - 0.8 * inch, 0.62 * inch)
    canvas.drawRightString(letter[0] - 0.8 * inch, 0.45 * inch, f"Proyecto integrador · Segunda entrega  |  {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------
def construir():
    W = 6.9 * inch
    s = []
    D = "datos"
    C = "clasificador"

    # ---------------- Portada ----------------
    s += [Spacer(1, 30),
          P("UNIVERSIDAD AUTÓNOMA DE CHIAPAS", ParagraphStyle("p1", fontName="Sans-B", fontSize=13, alignment=TA_CENTER, textColor=AZUL, leading=17)),
          P("Escuela de Tecnologías Digitales Aplicadas (ETDA)", ParagraphStyle("p2", fontName="Sans", fontSize=10.5, alignment=TA_CENTER, leading=15)),
          P("Licenciatura en Desarrollo de Tecnologías de Software", ParagraphStyle("p2b", fontName="Sans", fontSize=10.5, alignment=TA_CENTER, leading=15)),
          Spacer(1, 26),
          P("PROYECTO INTEGRADOR", ParagraphStyle("p3", fontName="Sans-B", fontSize=12, alignment=TA_CENTER, textColor=VERDE, leading=16)),
          P("Segunda entrega parcial de Inteligencia Artificial", ParagraphStyle("p4", fontName="Sans", fontSize=10.5, alignment=TA_CENTER, leading=15)),
          Spacer(1, 16),
          P("Sistema Inteligente para Monitoreo, Clasificación y Priorización del Mantenimiento de Infraestructura",
            ParagraphStyle("p5", fontName="Sans-B", fontSize=19, alignment=TA_CENTER, textColor=AZUL, leading=24)),
          Spacer(1, 8),
          P("Prototipo funcional: clasificación de reportes con Naive Bayes y priorización preliminar con reglas SI–ENTONCES",
            ParagraphStyle("p6", fontName="Sans", fontSize=11, alignment=TA_CENTER, leading=15, textColor=GRIS)),
          P("Caso de estudio en la UNACH con referencia piloto a ETDA",
            ParagraphStyle("p7", fontName="Sans-I", fontSize=10, alignment=TA_CENTER, leading=15, textColor=GRIS)),
          Spacer(1, 26)]
    integrantes = ("Jhovanny Yuca Hernández<br/>Edgar Yahir Altunar Gómez<br/>Isaac Hernández Molina<br/>"
                   "Jesús Gabriel Gómez Domínguez<br/>Alfredo Emiliano Pinto Velasco")
    s.append(tabla([["Datos de entrega", "Información"], ["Equipo", "Equipo 3"], ["Integrantes", integrantes],
                    ["Docente", "Dr. Daniel González Scarpulli"], ["Semestre y grupo", "7.º semestre, grupo 7M"],
                    ["Lugar y fecha", "Tuxtla Gutiérrez, Chiapas · 25 de octubre de 2026"],
                    ["Repositorio del código", LINK]],
                   [1.8 * inch, 5.1 * inch], primera_col_negrita=True))
    s += [Spacer(1, 18), nota("Prototipo académico con datos simulados. No se presenta como diagnóstico de edificios ni como "
                              "sistema en operación. Ninguna salida del prototipo es un dictamen técnico: todas son prioridades "
                              "preliminares sujetas a revisión humana."), PageBreak()]

    # ---------------- Índice ----------------
    toc = TableOfContents()
    toc.levelStyles = [st["toc1"]]
    toc.dotsMinLevel = 0
    s += [P("Índice", ParagraphStyle("indice", parent=st["h1"])), Spacer(1, 4), toc, PageBreak()]

    # ---------------- 1 Introducción ----------------
    s.append(P("1. Introducción", "h1"))
    s.append(P("En la primera entrega el equipo delimitó una necesidad operativa: reunir reportes heterogéneos de incidencias de "
               "infraestructura, con ubicación, evidencia y estado de atención, y ordenarlos de forma revisable en un caso piloto "
               "universitario (UNACH, con ETDA como referencia). Se propuso combinar visión artificial con reglas SI–ENTONCES "
               "(R1–R6) y supervisión humana, sin emitir dictámenes."))
    s.append(P("Esta segunda entrega construye y evalúa una primera versión funcional del componente inteligente. El equipo no "
               "cuenta con fotografías ni reportes reales autorizados, por lo que el prototipo trabaja con datos simulados, "
               "documentados como tales, y traslada el aprendizaje automático de la imagen al texto del reporte, que ya formaba "
               "parte de las entradas del sistema. El prototipo tiene tres piezas: un clasificador Naive Bayes multinomial que "
               "sugiere la categoría de la incidencia a partir de la descripción; un motor de reglas que combina esa categoría con "
               "señales de riesgo del texto, calidad de la foto e historial para proponer prioridad preliminar, escalamiento y "
               "revisión humana; y una clase agente que integra el ciclo percibir, interpretar, decidir, actuar y retroalimentar."))
    s.append(P("La evaluación se diseñó para no inflar resultados: los datos de prueba usan plantillas de redacción que el modelo "
               "nunca vio, se añadió un conjunto de casos redactados fuera del generador con vocabulario distinto, el umbral de "
               "confianza se eligió sin tocar el conjunto de prueba y todas las cifras se reproducen con la semilla "
               f"{prm('SEMILLA')}. El documento informa tanto lo que funciona como lo que no: el desempeño cae de forma "
               "importante con vocabulario nuevo, y esa caída orienta las mejoras para la tercera entrega."))

    # ---------------- 2 Resumen ----------------
    s.append(P("2. Resumen de la primera entrega y ajustes", "h1"))
    s.append(tabla([
        ["Aspecto", "Respuesta del equipo"],
        ["1. Nombre del proyecto", "Sistema Inteligente para Monitoreo, Clasificación y Priorización del Mantenimiento de Infraestructura (caso UNACH, referencia piloto ETDA)."],
        ["2. Problema específico", "¿Cómo apoyar el registro, la clasificación inicial y la priorización revisable de incidencias visibles y reportadas en infraestructura educativa de un piloto universitario de la UNACH?"],
        ["3. Población o usuarios", "Reportantes (estudiantes, docentes y trabajadores), personal operativo de mantenimiento y responsables administrativos. Beneficiarios indirectos: la comunidad universitaria."],
        ["4. Entradas del sistema", "Fotografía, descripción, zona, fecha, categoría declarada, identificador del activo e historial autorizado."],
        ["5. Resultado o acción esperada", "Categoría sugerida, prioridad preliminar, motivos de la recomendación, solicitud de revisión humana, registro e historial del caso."],
        ["6. Técnica inicial", "Visión artificial para sugerir clases visibles en la foto y sistema experto de reglas SI–ENTONCES (R1–R6) con revisión humana."],
    ], [1.75 * inch, 5.15 * inch], primera_col_negrita=True))
    s.append(Spacer(1, 8))
    s.append(tabla([
        ["Pregunta", "Respuesta del equipo"],
        ["¿El problema continúa siendo el mismo?", "Sí. Se conservan la necesidad, la población, el piloto UNACH/ETDA y el principio de prioridad preliminar revisable."],
        ["¿Se modificó el alcance? ¿Por qué?", "Se acotó el componente de aprendizaje: en esta etapa se clasifica la <b>descripción escrita</b> y no la fotografía. No hay imágenes autorizadas ni etiquetas de especialistas, y entrenar un modelo visual con imágenes inventadas no demostraría nada. La foto se conserva como atributo de calidad (legible, borrosa, oscura, sin foto) que activa R3."],
        ["¿La técnica inicial sigue siendo adecuada?", "Parcialmente. Las reglas SI–ENTONCES siguen siendo adecuadas y se implementaron. La visión artificial sigue siendo pertinente para una fase con fotos autorizadas, pero hoy no puede entrenarse ni evaluarse con honestidad; se sustituye temporalmente por clasificación de texto."],
        ["¿Qué cambios se hicieron?", "(1) Naive Bayes multinomial sobre el texto en lugar de visión. (2) R1–R6 se conservan con su sentido original y se agregan R7–R12 (datos faltantes, conflicto de categoría, reincidencia, circulación, riesgo eléctrico directo y espacio sin servicio). (3) R5 solo actúa en la retroalimentación, cuando un responsable confirma. (4) Se agregó un detector de señales de riesgo basado en un lexicón. (5) Se fijó una taxonomía de siete categorías derivada del alcance original."],
    ], [1.75 * inch, 5.15 * inch], primera_col_negrita=True))

    # ---------------- 3 Datos ----------------
    s.append(P("3. Preparación de los datos y del conocimiento", "h1"))
    s.append(P("El prototipo usa cuatro insumos, todos elaborados por el equipo: reportes simulados, un historial simulado de "
               "activos, casos externos redactados fuera del generador y una base de conocimiento (taxonomía, lexicón y reglas). "
               "Ningún dato proviene de la UNACH ni de ETDA; las zonas y activos son inventados."))
    dd = M["datos"]
    s.append(tabla([
        ["Elemento", "Descripción"],
        ["Fuente de los datos o conocimiento", f"<b>generador_datos.py</b> (semilla {prm('SEMILLA')}): reportes simulados a partir de {prm('N_ESCENARIOS')} escenarios y {prm('N_PLANTILLAS')} plantillas de redacción. Historial simulado de activos. Casos externos redactados aparte (JSON). Base de conocimiento redactada por el equipo (<b>conocimiento.py</b>)."],
        ["Cantidad disponible", f"{m('datos.n_total', 'int')} reportes simulados: {m('datos.n_entrenamiento', 'int')} de entrenamiento y {m('datos.n_prueba', 'int')} de prueba. {m('datos.n_externos', 'int')} casos externos. {m('datos.historial_registros', 'int')} registros de historial."],
        ["Variables o atributos", "Visibles para el prototipo: texto, zona, fecha, calidad de foto, categoría declarada e identificador del activo. De control (no visibles): plantilla, registro, escenario, señales verdaderas, reincidencia, prioridad y escalamiento de referencia, duplicado de."],
        ["Variable objetivo", "Categoría de la incidencia (7 clases) para el clasificador. Prioridad de referencia (Baja, Media, Alta, Inmediata) y escalamiento para el motor de reglas."],
        ["Formato", "CSV UTF-8 (reportes e historial); JSON (casos externos y pruebas); texto libre en español."],
        ["Datos faltantes o inconsistentes", f"Zona vacía: {m('datos.zona_vacia', 'int')}. Activo sin identificador: {m('datos.activo_vacio', 'int')}. Categoría declarada vacía: {m('datos.categoria_declarada_vacia', 'int')}; incorrecta: {m('datos.categoria_declarada_incorrecta', 'int')}. Foto borrosa: {m('datos.foto.borrosa', 'int')}; oscura: {m('datos.foto.oscura', 'int')}; sin foto: {m('datos.foto.sin_foto', 'int')}. Textos vagos: {m('datos.textos_vagos', 'int')}. Duplicados: {m('datos.duplicados', 'int')}. Erratas, abreviaturas, minúsculas y acentos omitidos."],
        ["Preparación o transformación", "Normalización (minúsculas, sin acentos ni signos), expansión de abreviaturas (q→que, xfa→por favor, lab→laboratorio), palabras vacías eliminadas salvo “no” y “sin”, unigramas y bigramas. Para las reglas: detección de señales con expresiones regulares y negación en los tres tokens previos."],
        ["Riesgos de privacidad o sesgo", "Los datos simulados no contienen datos personales. Sesgos: el generador y el lexicón los escribió el mismo equipo, lo que vuelve optimista la prueba simulada; hay correlaciones artificiales entre zona y categoría; el vocabulario refleja a quien redactó. Con datos reales aparecerían nombres, rostros en fotos y ubicaciones sensibles."],
        ["Limitaciones de los datos", "La prioridad de referencia se calcula con la misma política que codifican las reglas: la evaluación mide si el prototipo <b>percibe</b> bien las condiciones en texto ruidoso, no si la política es correcta. No hay etiquetas de especialistas. Las categorías están balanceadas artificialmente."],
    ], [1.75 * inch, 5.15 * inch], primera_col_negrita=True))

    s.append(P("3.1 Cómo se generaron los datos simulados", "h2"))
    s.append(P(f"Cada <b>escenario</b> ({prm('N_ESCENARIOS')} en total) define una categoría, objetos y problemas posibles y las "
               "señales verdaderas del hecho; por ejemplo, “filtración activa en techo” lleva la señal agua, y “tablero con cables "
               "expuestos” lleva riesgo eléctrico. Un <b>contexto</b> opcional añade o niega señales (“junto al contacto”, “no hay "
               "contactos cerca”, “la gente se resbala al pasar”). El texto se arma con una de "
               f"{prm('N_PLANTILLAS')} <b>plantillas</b> en cuatro registros: formal, coloquial, telegráfico y narrativo. "
               f"El generador reserva para prueba una plantilla de cada registro ({', '.join(M['datos']['plantillas_prueba'])}). "
               "Después se aplica <b>ruido</b>: erratas, minúsculas, acentos omitidos y abreviaturas según el "
               f"registro, textos vagos, zona o activo faltantes, foto de mala calidad y categoría declarada vacía o equivocada. "
               f"Con probabilidad {prm('P_DUPLICADO')} un reporte es un duplicado del mismo hecho, redactado con otra plantilla del "
               "mismo grupo y fechado entre uno y cinco días después. El historial previo simula activos con dos o tres "
               "incidencias recientes (reincidencia real), una sola o incidencias antiguas."))
    s.append(P("La <b>prioridad de referencia</b> se obtiene aplicando la política del equipo a las señales verdaderas del "
               "escenario, con R5 ya confirmada cuando el problema es exclusivamente estético. El prototipo nunca ve estas "
               "columnas: debe inferir las señales del texto ruidoso."))
    pref = M["datos"]
    s.append(tabla([
        ["Prioridad de referencia", "Total simulado", "Prueba", "Casos externos"],
        *[[pp, m(f"datos.por_prioridad_ref.{pp}", "int"), m(f"datos.por_prioridad_ref_prueba.{pp}", "int"),
           m(f"datos.por_prioridad_ref_externos.{pp}", "int")] for pp in ["Inmediata", "Alta", "Media", "Baja"]],
        ["Casos críticos (Inmediata o escalamiento)", m("datos.criticos_total", "int"), m("datos.criticos_prueba", "int"), m("datos.criticos_externos", "int")],
    ], [2.9 * inch, 1.35 * inch, 1.3 * inch, 1.35 * inch]))
    s.append(P("Tabla 1. Distribución de la prioridad de referencia. Fuente: resultados/metricas.json.", "cap"))

    s.append(P("3.2 Evidencia del conjunto utilizado", "h2"))
    datos_csv = pd.read_csv(BASE / "datos/reportes_simulados.csv", keep_default_na=False).set_index("id")
    ejemplos = ["S0048", "S0201", "S0639", "S0799", "S0145", "S0917"]
    filas = [["ID", "Texto (tal como lo ve el prototipo)", "Zona", "Foto", "Cat. ref.", "Prior. ref."]]
    for rid in ejemplos:
        r = datos_csv.loc[rid]
        filas.append([rid, r.texto, r.zona or "(vacía)", r.foto_calidad, r.categoria_ref, r.prioridad_ref])
    s.append(tabla(filas, [0.5 * inch, 3.25 * inch, 1.05 * inch, 0.6 * inch, 0.8 * inch, 0.7 * inch], chico=True))
    s.append(P("Tabla 2. Fragmento de datos/reportes_simulados.csv (datos simulados). S0917 es un texto vago generado a propósito.", "cap"))
    ext = json.loads((BASE / "datos/casos_externos_redactados.json").read_text(encoding="utf-8"))["casos"]
    ext_id = {c["id"]: c for c in ext}
    filas = [["ID", "Caso externo (vocabulario distinto)", "Categoría ref.", "Señales ref."]]
    for rid in ["X05", "X12", "X25", "X33", "X40", "X56"]:
        c = ext_id[rid]
        filas.append([rid, c["texto"], c["categoria_ref"], ", ".join(c["senales_ref"]) or "—"])
    s.append(tabla(filas, [0.5 * inch, 4.0 * inch, 1.0 * inch, 1.4 * inch], chico=True))
    s.append(P("Tabla 3. Fragmento de datos/casos_externos_redactados.json. Se redactaron después de congelar el lexicón y no se "
               "usaron para ajustar nada.", "cap"))

    s.append(P("3.3 Base de conocimiento: reglas", "h2"))
    s.append(P("Las reglas R1–R6 conservan el sentido de la primera entrega. Las reglas R7–R12 se agregaron para cubrir "
               "situaciones que aparecieron al diseñar el flujo. Los parámetros son decisiones del equipo, fijadas antes de "
               "evaluar; no son plazos normativos y deberán acordarse con personal técnico."))
    s.append(tabla([
        ["ID", "Regla SI–ENTONCES implementada", "Origen"],
        ["R1", "SI hay agua o humedad y un elemento eléctrico ENTONCES prioridad Inmediata, escalar a personal competente y revisión humana. (Si la categoría sugerida es Humedad y se menciona un elemento eléctrico, se asume agua; si es Eléctrico, se asume elemento eléctrico.)", "1.ª entrega"],
        ["R2", "SI hay indicio de desprendimiento ENTONCES Inmediata; SI hay indicio potencialmente estructural ENTONCES al menos Alta. En ambos casos: solicitar inspección especializada y no emitir diagnóstico.", "1.ª entrega"],
        ["R3", "SI la confianza del clasificador es menor que el umbral ENTONCES revisión humana; SI la foto es borrosa u oscura ENTONCES solicitar nueva foto.", "1.ª entrega"],
        ["R4", f"SI un reporte coincide con un caso abierto de la misma categoría en los últimos {prm('PARAMETROS.ventana_duplicado_dias')} días (mismo activo, o misma zona y similitud de texto ≥ {prm('PARAMETROS.similitud_duplicado')}) ENTONCES vincularlo sin perder evidencia.", "1.ª entrega"],
        ["R5", "SI un responsable confirma que el problema es solo estético y no hay otras señales de riesgo ENTONCES prioridad Baja. El agente solo marca el caso como candidato.", "1.ª entrega"],
        ["R6", f"SI un caso validado sigue abierto ENTONCES mostrar su antigüedad en el panel; se resalta desde {prm('PARAMETROS.antiguedad_aviso_dias')} días (parámetro del equipo).", "1.ª entrega"],
        ["R7", f"SI falta la zona o la descripción tiene menos de {prm('PARAMETROS.min_palabras_descripcion')} palabras ENTONCES solicitar datos y revisión humana.", "Nueva"],
        ["R8", "SI la categoría declarada por el reportante difiere de la sugerida ENTONCES revisión humana.", "Nueva"],
        ["R9", f"SI el activo tiene al menos {prm('PARAMETROS.min_incidencias_reincidencia')} incidencias en los {prm('PARAMETROS.ventana_reincidencia_dias')} días previos ENTONCES subir un nivel de prioridad (máximo Alta).", "Nueva"],
        ["R10", "SI la incidencia afecta la circulación o la evacuación (resbalón, hoyo, escalón, salida bloqueada) ENTONCES al menos Alta.", "Nueva"],
        ["R11", "SI hay indicio de riesgo eléctrico directo (chispas, olor a quemado, cables expuestos, toques) ENTONCES Inmediata, escalar y revisión humana.", "Nueva"],
        ["R12", "SI un espacio completo queda sin servicio (sin luz, sin agua, ningún baño utilizable) ENTONCES al menos Alta.", "Nueva"],
    ], [0.45 * inch, 5.55 * inch, 0.9 * inch], primera_col_negrita=True))
    s.append(P("Si ninguna regla de riesgo se activa, la prioridad base es Media. Las reglas se aplican en conjunto: se conserva "
               "el nivel más alto y todas las reglas activadas quedan en la explicación del caso.", "cap"))

    # ---------------- 4 Técnica ----------------
    s.append(P("4. Justificación de la técnica de Inteligencia Artificial", "h1"))
    sel = M["seleccion"]["cv_f1_macro"]
    s.append(tabla([
        ["Pregunta", "Respuesta"],
        ["¿Qué técnica de IA utilizarán?", "Principal: clasificación supervisada de texto con <b>Naive Bayes multinomial</b>. Complemento: <b>sistema basado en conocimiento</b> (reglas SI–ENTONCES con un lexicón de señales de riesgo). Ambos se integran en una clase agente."],
        ["¿Qué tarea realizará?", "Naive Bayes sugiere la categoría de la incidencia entre siete clases y entrega una confianza. Las reglas proponen prioridad preliminar, escalamiento, revisión humana y acciones, con la traza de reglas activadas."],
        ["¿Por qué es apropiada para el problema?", "Las descripciones son cortas y cada categoría tiene vocabulario característico (lámpara, gotera, chapa). Naive Bayes funciona bien con textos cortos y pocos datos, se entrena en segundos y permite explicar qué palabras pesaron (McCallum y Nigam, 1998; Manning et al., 2008). La prioridad, en cambio, debe ser auditable y acordada con técnicos, y no existen etiquetas de expertos para aprenderla; por eso se expresa con reglas explícitas."],
        ["¿Qué entradas necesita?", "Clasificador: el texto de la descripción. Reglas: categoría sugerida y su confianza, señales detectadas en el texto, calidad de la foto, zona, categoría declarada e historial del activo."],
        ["¿Qué resultado produce?", "Categoría, confianza, tres alternativas y palabras más influyentes; prioridad preliminar, escalamiento, revisión humana, acciones (crear o vincular caso, alertar, pedir datos o foto) y motivos."],
        ["¿Qué otras técnicas podrían utilizarse?", "Regresión logística con TF-IDF y una línea base de palabras clave (ambas comparadas aquí); SVM lineal o árboles de decisión; embeddings o modelos de lenguaje; y, con fotos autorizadas, visión artificial (CNN, MobileNet, YOLO)."],
        ["¿Por qué se eligió esta opción?", f"En validación cruzada agrupada por plantilla, dentro del entrenamiento, Naive Bayes (α = {m('seleccion.alpha_nb', 'raw')}) obtuvo F1 macro {m(['seleccion', 'cv_f1_macro', 'naive_bayes', str(M['seleccion']['alpha_nb']), 'media'])} y la regresión logística (C = {m('seleccion.C_lr', 'raw')}) {m(['seleccion', 'cv_f1_macro', 'regresion_logistica', str(M['seleccion']['C_lr']), 'media'])}. Con desempeño equivalente, se prefirió Naive Bayes por su simplicidad y su explicación por palabra. Los casos externos mostraron después una debilidad de esta elección, que se analiza en las secciones 9 y 10."],
    ], [1.85 * inch, 5.05 * inch], primera_col_negrita=True))

    # ---------------- 5 Diseño ----------------
    s.append(P("5. Diseño del componente inteligente", "h1"))
    s.append(diagrama_flujo([
        ("ENTRADAS", ["Descripción (texto)", "Zona y fecha", "Calidad de foto", "Categoría declarada", "Activo e historial"], False),
        ("PREPROCESAMIENTO", ["Validar campos", "Normalizar texto", "Expandir abreviaturas", "Unigramas y bigramas", "Consultar historial"], False),
        ("COMPONENTE DE IA", ["Naive Bayes:", "categoría + confianza", "Lexicón: señales", "Reglas R1–R12:", "prioridad y revisión"], True),
        ("RESULTADO", ["Prioridad preliminar", "Escalamiento", "Revisión humana", "Motivos y reglas", "Palabras clave"], False),
        ("ACCIÓN", ["Crear o vincular caso", "Alertar al área", "Pedir datos o foto", "Panel de casos", "Registrar corrección"], False),
    ], alto=118, retro="Retroalimentación: correcciones con autor y fecha (R5, historial); no se reentrena en automático"))
    s.append(P("Figura 1. Flujo del prototipo: ENTRADAS → PREPROCESAMIENTO → IA → RESULTADO → ACCIÓN. Fuente: elaboración propia.", "cap"))
    s.append(P("El sistema recibe un reporte con descripción, zona, fecha, calidad de la foto, categoría declarada e identificador "
               "del activo. Antes de razonar valida los campos mínimos, normaliza el texto y consulta cuántas incidencias tuvo el "
               f"activo en los últimos {prm('PARAMETROS.ventana_reincidencia_dias')} días. La inteligencia artificial interviene en dos puntos: el clasificador Naive Bayes, "
               "aprendido de datos, propone la categoría y su confianza; el motor de reglas, construido con conocimiento explícito, "
               "combina esa categoría con las señales que el lexicón encuentra en el texto (agua, elemento eléctrico, chispas, "
               "desprendimiento, grieta grave, circulación, falta de servicio, estética) y con la calidad de la evidencia."))
    s.append(P("El resultado se presenta como prioridad <b>preliminar</b>, acompañada de las reglas que la justifican, del motivo "
               "de la revisión humana y de las palabras que más pesaron en la clasificación. La acción consiste en registrar: "
               "crear un caso o vincularlo a uno abierto, marcar alertas para el área competente y pedir datos o una nueva foto. "
               "El personal responsable confirma o corrige; esa corrección queda en la bitácora del caso con autor y fecha, y en "
               "el caso de R5 es la que permite bajar la prioridad a Baja."))

    # ---------------- 6 Implementación ----------------
    s.append(P("6. Implementación del prototipo", "h1"))
    s.append(P("El prototipo está escrito en Python con scikit-learn, pandas, NumPy y matplotlib (Pedregosa et al., 2011). "
               f"Se ejecuta desde consola o desde el notebook incluido. El código completo está en {LINK}; el anexo A explica cómo reproducirlo."))
    s.append(tabla([
        ["Archivo", "Contenido", "¿Componente de IA?"],
        ["generador_datos.py", "Escenarios, plantillas, ruido, historial y referencia simulada.", "No (datos)"],
        ["mantenimiento_ia/conocimiento.py", "Taxonomía, normalización, lexicón de señales con negación y política de prioridad.", "Sí: conocimiento"],
        ["mantenimiento_ia/clasificador.py", "Naive Bayes, regresión logística, línea base de palabras clave y explicación por palabra.", "Sí: aprendizaje"],
        ["mantenimiento_ia/reglas.py", "MotorReglas.decidir(): combina categoría, confianza, señales, foto, datos y historial.", "Sí: razonamiento"],
        ["mantenimiento_ia/agente.py", "AgenteMantenimiento: percibir, interpretar, decidir, actuar, retroalimentar y panel (R6).", "Integra la IA"],
        ["evaluar.py", "Protocolo de evaluación, métricas, líneas base, figuras y pruebas predefinidas.", "No (evaluación)"],
        ["demo_consola.py · notebook", "Demostración paso a paso; el notebook comprueba que reproduce metricas.json.", "No (evidencia)"],
    ], [2.15 * inch, 3.65 * inch, 1.1 * inch]))
    s.append(P("<b>¿Dónde está la inteligencia artificial?</b> En <b>interpretar()</b>, que llama a <b>predict_proba</b> del "
               "Naive Bayes entrenado: es la parte aprendida de los datos. En <b>decidir()</b>, que ejecuta el motor de reglas: "
               "es la parte basada en conocimiento. El resto del código prepara datos, registra casos o mide resultados. El "
               f"hiperparámetro α se eligió entre {', '.join(str(a) for a in EV.GRID_ALPHA)} y C entre "
               f"{', '.join(str(c) for c in EV.GRID_C)} con validación cruzada agrupada por plantilla (4 pliegues) en el "
               "conjunto de entrenamiento."))
    s.append(codigo(
        "def procesar(self, reporte):                 # agente.py\n"
        "    p = self.percibir(reporte)               # valida campos, fecha, foto\n"
        "    i = self.interpretar(p)                  # Naive Bayes + lexicón de señales\n"
        "    d = self.decidir(p, i)                   # motor de reglas R1-R12\n"
        "    a = self.actuar(p, i, d)                 # crea o vincula caso (R4), alertas\n"
        "    return {'percepcion': p, 'interpretacion': i, 'decision': d, 'accion': a}\n\n"
        "# conocimiento.py · fragmento de la política de prioridad\n"
        "if f.get('agua') and f.get('electrico'):\n"
        "    nivel = max(nivel, NIVEL['Inmediata']); escalar = True; reglas.append('R1')\n"
        "if f.get('desprendimiento'):\n"
        "    nivel = max(nivel, NIVEL['Inmediata']); escalar = True; reglas.append('R2')\n"
        "if candidato_estetico and estetico_confirmado:   # R5 solo con confirmación humana\n"
        "    nivel = NIVEL['Baja']; reglas.append('R5')\n"
        "if reincidencia and nivel < NIVEL['Alta']:      # R9\n"
        "    nivel += 1; reglas.append('R9')"))
    s.append(P("Fragmento 1. Ciclo del agente y parte de la política de prioridad. El código completo está en la carpeta entregada.", "cap"))

    # ---------------- 7 Evidencias ----------------
    s.append(P("7. Evidencias de funcionamiento", "h1"))
    s.append(P("Las capturas siguientes corresponden a una ejecución real del código entregado (Python 3.13 en Linux), "
               "hecha con documento/generar_capturas.py: el script corre cada comando, guarda su salida completa en "
               "resultados/capturas/*.txt y la presenta tal cual en una ventana de terminal; la última línea de cada captura "
               "indica fecha, duración y código de salida. Las capturas del notebook provienen del archivo "
               "prototipo_mantenimiento_EQ3.ipynb ya ejecutado. Ninguna salida fue editada."))
    capturas = [
        ("01_generador.png", "Captura 1. Generación de los datos simulados con semilla fija."),
        ("02_evaluacion.png", "Captura 2. Entrenamiento y evaluación completa (evaluar.py): umbral, F1 macro por conjunto y pruebas."),
        ("03_demo.png", "Captura 3. Demostración del agente: tres reportes, retroalimentación R5 y panel de casos (R6)."),
        ("04_demo_texto_libre.png", "Captura 4. Reporte escrito en el momento: el agente aplica R11 y escala el caso."),
        ("05_notebook_reproduce.png", "Captura 5. El notebook reproduce exactamente resultados/metricas.json."),
        ("06_notebook_clasificador.png", "Captura 6. Notebook: métricas del clasificador por conjunto y modelo."),
        ("07_notebook_pruebas.png", "Captura 7. Notebook: resultado de las doce pruebas predefinidas."),
        ("08_notebook_agente.png", "Captura 8. Notebook: ciclo del agente con retroalimentación y panel."),
    ]
    for archivo, pie in capturas:
        ruta = BASE / "resultados/capturas" / archivo
        img = Image(str(ruta))
        ancho = 6.6 * inch
        alto = ancho * img.imageHeight / img.imageWidth
        if alto > 7.9 * inch:
            ancho, alto = ancho * 7.9 * inch / alto, 7.9 * inch
        img.drawWidth, img.drawHeight = ancho, alto
        s.append(KeepTogether([img, P(pie, "cap")]))
    s.append(P("Además, todas las decisiones por reporte están en resultados/decisiones_prueba.csv y "
               "decisiones_externos.csv, y la salida completa de la demostración en resultados/demo_salida.txt."))

    # ---------------- 8 Pruebas ----------------
    s.append(P("8. Pruebas del prototipo", "h1"))
    s.append(P(f"Se definieron {m('pruebas.total', 'int')} pruebas, una por regla más casos de negación y circulación. El "
               "resultado esperado se escribió en pruebas_definidas.json <b>antes</b> de ejecutar el prototipo; evaluar.py "
               f"registra la huella SHA-256 del archivo ({M['pruebas']['sha256_especificacion'][:16]}…). Se aprobaron "
               f"{m('pruebas.aprobadas', 'int')} de {m('pruebas.total', 'int')}."))
    obs = {
        "P01": "R1 se activa por agua y contactos.", "P02": "Pide inspección especializada, sin diagnóstico.",
        "P03": f"Falla: confianza {p('P03', 'confianza', 'dec2')} supera el umbral {m('umbral.valor', 'dec2')}; pidió foto, pero no revisión. Ver sección 10.",
        "P04": "El segundo reporte se vincula al caso abierto.", "P05": "Baja solo tras la confirmación del responsable.",
        "P06": "El panel muestra la antigüedad y la resalta.", "P07": "Pide la zona y marca revisión.",
        "P08": "La negación evita una falsa alarma R1.", "P09": "Media sube a Alta por reincidencia.",
        "P10": "Conflicto entre lo declarado y lo sugerido.", "P11": "Riesgo eléctrico directo.",
        "P12": "Vocabulario no visto (“aceite”), pero el lexicón capta “resbala”.",
    }
    filas = [["Prueba", "Entrada", "Resultado esperado", "Resultado obtenido", "¿Correcto?", "Observaciones"]]
    for pr in PR["pruebas"]:
        e, o = pr["esperado"], pr["obtenido"]
        esp = "; ".join(f"{k.replace('_', ' ')}: {', '.join(v) if isinstance(v, list) else v}" for k, v in e.items())
        claves = [k for k in ("categoria", "prioridad", "escalamiento", "revision_humana", "reglas", "segundo_vinculado",
                              "prioridad_tras_retroalimentacion", "panel_dias_abierto", "panel_aviso_antiguedad")
                  if k in o and (k in e or k in ("categoria", "prioridad", "reglas"))]
        obt = "; ".join(f"{k.replace('_', ' ')}: {', '.join(o[k]) if isinstance(o[k], list) else o[k]}" for k in claves)
        REGISTRO.append({"fuente": "pruebas_resultados.json", "ruta": f"{pr['id']}.correcto", "formato": "raw", "texto": "Sí" if pr["correcto"] else "No", "valor": pr["correcto"]})
        filas.append([f"{pr['id']}<br/>({pr['regla']})", pr["texto"], esp, obt, "Sí" if pr["correcto"] else "<b>No</b>", obs[pr["id"]]])
    s.append(tabla(filas, [0.55 * inch, 1.55 * inch, 1.45 * inch, 1.55 * inch, 0.5 * inch, 1.3 * inch], chico=True))
    s.append(P("Tabla 4. Pruebas con resultado esperado definido antes de ejecutar. Fuente: resultados/pruebas_resultados.json.", "cap"))

    # ---------------- 9 Evaluación ----------------
    s.append(P("9. Evaluación del desempeño", "h1"))
    s.append(P("Se evaluó por separado cada parte del componente inteligente: el clasificador de categoría, el umbral de "
               "confianza, el detector de señales y el resultado final de prioridad. Cada parte se midió en tres situaciones: "
               "la <b>prueba por plantilla</b>, que usa redacciones nunca vistas pero el mismo vocabulario de escenarios; los "
               "<b>casos externos</b>, con vocabulario distinto; y una <b>partición aleatoria</b>, que solo sirve para mostrar "
               "cuánto se inflan los resultados si se mezclan plantillas."))
    s.append(P("9.1 Clasificador de categoría", "h2"))
    filas = [["Conjunto", "Modelo", "Exactitud", "Precisión macro", "Recall macro", "F1 macro"]]
    nombres = {"palabras_clave": "Palabras clave (sin IA)", "naive_bayes": "Naive Bayes", "regresion_logistica": "Regresión logística"}
    conj_n = {"prueba": f"Prueba por plantilla (n = {m('clasificador.prueba.naive_bayes.n', 'int')})",
              "externos": f"Casos externos (n = {m('clasificador.externos.naive_bayes.n', 'int')})",
              "aleatoria": f"Partición aleatoria (n = {m('clasificador.aleatoria.naive_bayes.n', 'int')})"}
    for cj in ("prueba", "externos", "aleatoria"):
        for mo in ("palabras_clave", "naive_bayes", "regresion_logistica"):
            filas.append([conj_n[cj] if mo == "palabras_clave" else "", nombres[mo],
                          m(f"{C}.{cj}.{mo}.exactitud"), m(f"{C}.{cj}.{mo}.precision_macro"),
                          m(f"{C}.{cj}.{mo}.recall_macro"), m(f"{C}.{cj}.{mo}.f1_macro")])
    s.append(tabla(filas, [1.9 * inch, 1.5 * inch, 0.85 * inch, 0.95 * inch, 0.85 * inch, 0.85 * inch]))
    s.append(P(f"Tabla 5. Desempeño del clasificador. La línea base de palabras clave no clasificó {m('clasificador.prueba.no_clasificados_palabras_clave', 'int')} "
               f"textos de prueba y {m('clasificador.externos.no_clasificados_palabras_clave', 'int')} externos (cuentan como error).", "cap"))
    s.append(P(f"En la prueba por plantilla, Naive Bayes alcanza F1 macro {m(C + '.prueba.naive_bayes.f1_macro')}, frente a "
               f"{m(C + '.prueba.palabras_clave.f1_macro')} de las palabras clave: el modelo generaliza a redacciones nuevas mejor "
               f"que una lista fija. La partición aleatoria da {m(C + '.aleatoria.naive_bayes.f1_macro')}, apenas por encima; el "
               "inflado por mezclar plantillas es pequeño porque las plantillas solo cambian la estructura de la frase, no el "
               f"vocabulario. El dato decisivo está en los casos externos: Naive Bayes baja a {m(C + '.externos.naive_bayes.f1_macro')}, "
               f"la regresión logística a {m(C + '.externos.regresion_logistica.f1_macro')} y la línea base de palabras clave "
               f"obtiene {m(C + '.externos.palabras_clave.f1_macro')}, la mejor de las tres. El modelo aprendió el vocabulario del "
               "generador, no el dominio en general; con vocabulario nuevo, una lista escrita con conocimiento del dominio resulta "
               "más robusta."))
    s.append(Table([[Image(str(BASE / "resultados/figuras/matriz_nb_prueba.png"), width=3.35 * inch, height=3.35 * inch * 4.4 / 5.2),
                     Image(str(BASE / "resultados/figuras/matriz_nb_externos.png"), width=3.35 * inch, height=3.35 * inch * 4.4 / 5.2)]],
                   colWidths=[3.45 * inch, 3.45 * inch]))
    s.append(P("Figura 2. Matrices de confusión de Naive Bayes en la prueba por plantilla y en los casos externos. "
               "Fuente: resultados/figuras.", "cap"))
    s.append(P(f"En los casos externos, Humedad tiene recall {m(C + '.externos.naive_bayes_por_clase.HUMEDAD.recall')} y Muros "
               f"{m(C + '.externos.naive_bayes_por_clase.MUROS.recall')}: "
               "varias descripciones de humedad se clasificaron como eléctrico, muros, pisos o mobiliario porque "
               "mencionan el techo, la pared o la entrada sin las palabras que el generador asociaba a la humedad (“gotera”, "
               "“filtración”)."))

    s.append(P("9.2 Umbral de confianza para la revisión humana (R3)", "h2"))
    s.append(P(f"El criterio se fijó antes de ejecutar: el menor umbral con error de {prm('ERROR_MAX_ACEPTADOS', 'pct1')} o menos "
               "entre los casos que no van a revisión, medido con predicciones fuera de pliegue de una validación cruzada "
               f"agrupada por plantilla dentro del entrenamiento (rejilla de {prm('GRID_UMBRAL_MIN', 'dec2')} a "
               f"{prm('GRID_UMBRAL_MAX', 'dec2')}). En validación, el error fue de {m('umbral.error_aceptados_validacion', 'pct1')} "
               f"incluso sin filtrar, así que el criterio se cumplió en toda la rejilla y el umbral quedó en "
               f"{m('umbral.valor', 'dec2')}, con cobertura de {m('umbral.cobertura_validacion', 'pct1')}."))
    s.append(figura(BASE / "resultados/figuras/umbral_validacion.png", 5.2 * inch,
                    "Figura 3. Curva de cobertura y error entre aceptados (validación agrupada, solo entrenamiento)."))
    s.append(P(f"La consecuencia es que R3 por confianza nunca se activó: {m('confianza.prueba_bajo_umbral', 'int')} casos de "
               f"prueba y {m('confianza.externos_bajo_umbral', 'int')} externos quedaron bajo el umbral. Ninguno de los "
               f"{m('confianza.externos_errores', 'int')} errores externos ni de los {m('confianza.prueba_errores', 'int')} de "
               "prueba se habría enviado a revisión por baja confianza. Naive Bayes asigna probabilidades muy cercanas a 1 "
               "incluso cuando se equivoca, un sesgo conocido del modelo (Niculescu-Mizil y Caruana, 2005). La tabla 6 es un "
               "análisis exploratorio posterior: no se usó para elegir el umbral y solo sirve para dimensionar la mejora."))
    filas = [["Umbral (exploratorio)", "Externos enviados a revisión", "Errores externos capturados"]]
    for k, e in enumerate(M["exploratorio_post_hoc_umbral_externos"]):
        filas.append([m(f"exploratorio_post_hoc_umbral_externos.{k}.umbral", "dec2"),
                      f"{m(f'exploratorio_post_hoc_umbral_externos.{k}.enviados_a_revision', 'int')} de {m('datos.n_externos', 'int')}",
                      f"{m(f'exploratorio_post_hoc_umbral_externos.{k}.errores_capturados', 'int')} de {m(f'exploratorio_post_hoc_umbral_externos.{k}.errores_totales', 'int')}"])
    s.append(tabla(filas, [2.0 * inch, 2.45 * inch, 2.45 * inch]))
    s.append(P("Tabla 6. Sensibilidad posterior del umbral en los casos externos. No se usó para ninguna decisión del prototipo.", "cap"))

    s.append(P("9.3 Detector de señales de riesgo", "h2"))
    filas = [["Señal", "Prueba: soporte", "Prueba: precisión", "Prueba: recall", "Externos: soporte", "Externos: precisión", "Externos: recall"]]
    for sn in ["agua", "electrico", "riesgo_electrico", "desprendimiento", "estructural", "circulacion", "sin_servicio", "estetico"]:
        filas.append([sn.replace("_", " "), m(f"senales.prueba.{sn}.soporte", "int"), m(f"senales.prueba.{sn}.precision"),
                      m(f"senales.prueba.{sn}.recall"), m(f"senales.externos.{sn}.soporte", "int"),
                      m(f"senales.externos.{sn}.precision"), m(f"senales.externos.{sn}.recall")])
    s.append(tabla(filas, [1.3 * inch, 0.9 * inch, 0.95 * inch, 0.9 * inch, 0.95 * inch, 1.0 * inch, 0.9 * inch]))
    s.append(P("Tabla 7. Precisión y recall de cada señal frente a las señales de referencia.", "cap"))
    s.append(P(f"En la prueba simulada las señales de riesgo grave se detectan casi siempre (recall de desprendimiento "
               f"{m('senales.prueba.desprendimiento.recall')}, riesgo eléctrico {m('senales.prueba.riesgo_electrico.recall')}), "
               "lo cual es esperable porque el generador y el lexicón comparten autor. En los casos externos el recall de "
               f"desprendimiento cae a {m('senales.externos.desprendimiento.recall')}, el de circulación a "
               f"{m('senales.externos.circulacion.recall')} y el de riesgo eléctrico a {m('senales.externos.riesgo_electrico.recall')}. "
               "Este es el cuello de botella del sistema completo."))

    s.append(P("9.4 Prioridad preliminar: prototipo frente a líneas base", "h2"))
    s.append(P("Se compararon cinco configuraciones con la misma referencia. <b>B0</b>: sin IA, todo entra como Media en orden "
               "de llegada. <b>B1</b>: sin IA, categoría por palabras clave y una tabla fija por categoría (Eléctrico → Alta con "
               "escalamiento; Mobiliario → Baja; resto → Media). <b>A1</b>: reglas con la categoría de palabras clave. "
               "<b>A2</b>: reglas con la categoría real, como cota superior. <b>Prototipo</b>: Naive Bayes, señales y reglas. "
               "Un caso es <b>crítico</b> si su referencia es Inmediata o requiere escalamiento; un falso negativo crítico es un "
               "caso crítico que el sistema no marcó como Inmediata ni escaló."))
    claves = [("B0_todo_media_orden_llegada", "B0 Todo Media"), ("B1_palabras_clave_tabla_fija", "B1 Palabras clave + tabla"),
              ("A1_reglas_con_palabras_clave", "A1 Reglas + palabras clave"), ("A2_reglas_con_categoria_real", "A2 Reglas + categoría real"),
              ("PROTOTIPO_NB_mas_reglas", "Prototipo NB + reglas"), ("PROTOTIPO_tras_confirmacion_R5", "Prototipo tras confirmar R5")]
    for cj, titulo in (("prueba", "Prueba por plantilla"), ("externos", "Casos externos")):
        filas = [["Sistema", "Exactitud prioridad", "Recall críticos", "FN críticos", "FN sin revisión", "Falsas alarmas", "Revisión humana", "Subestima"]]
        for k, nom in claves:
            b = f"prioridad.{cj}.{k}"
            filas.append([nom, m(b + ".exactitud_prioridad"), m(b + ".recall_criticos"), m(b + ".falsos_negativos_criticos", "int"),
                          m(b + ".fn_criticos_sin_revision", "int"), m(b + ".falsas_alarmas", "int"),
                          m(b + ".proporcion_revision_humana", "pct1"), m(b + ".subestimacion", "pct1")])
        s.append(KeepTogether([P(f"{titulo} (n = {m(f'prioridad.{cj}.PROTOTIPO_NB_mas_reglas.n', 'int')}; críticos = {m(f'prioridad.{cj}.PROTOTIPO_NB_mas_reglas.n_criticos', 'int')})", "cellb"),
                               Spacer(1, 3),
                               tabla(filas, [1.75 * inch, 0.75 * inch, 0.7 * inch, 0.62 * inch, 0.68 * inch, 0.68 * inch, 0.82 * inch, 0.7 * inch], chico=True),
                               Spacer(1, 6)]))
    s.append(P("Tabla 8. Métricas de prioridad. “FN sin revisión” son casos críticos no detectados que además no fueron a revisión "
               "humana; “Subestima” es la proporción de casos con prioridad menor que la de referencia.", "cap"))
    s.append(figura(BASE / "resultados/figuras/comparacion_sistemas.png", 6.2 * inch,
                    "Figura 4. Recall de casos críticos y exactitud de prioridad por sistema."))
    pt, pe = "prioridad.prueba.PROTOTIPO_NB_mas_reglas", "prioridad.externos.PROTOTIPO_NB_mas_reglas"
    s.append(P(f"En la prueba por plantilla el prototipo detecta todos los casos críticos (recall {m(pt + '.recall_criticos')}, "
               f"{m(pt + '.falsos_negativos_criticos', 'int')} falsos negativos) con {m(pt + '.falsas_alarmas', 'int')} falsa "
               f"alarma, y envía a revisión humana {m(pt + '.proporcion_revision_humana', 'pct1')} de los casos. Sin IA, B0 no "
               f"detecta ninguno y B1 solo {m('prioridad.prueba.B1_palabras_clave_tabla_fija.recall_criticos')}. La exactitud de "
               f"prioridad sube de {m(pt + '.exactitud_prioridad')} a "
               f"{m('prioridad.prueba.PROTOTIPO_tras_confirmacion_R5.exactitud_prioridad')} cuando el responsable confirma los "
               "casos estéticos: el prototipo no baja sola la prioridad a Baja, como exige R5. A1 y A2 dan casi lo mismo que "
               "el prototipo porque la prioridad depende sobre todo de las señales del texto, no de la categoría."))
    s.append(P(f"En los casos externos el recall de críticos baja a {m(pe + '.recall_criticos')}: "
               f"{m(pe + '.falsos_negativos_criticos', 'int')} de {m(pe + '.n_criticos', 'int')} casos críticos quedaron como "
               f"Media o Alta sin escalamiento, y {m(pe + '.fn_criticos_sin_revision', 'int')} de ellos tampoco pasaron por "
               f"revisión humana. Incluso con la categoría real (A2) el recall solo llega a "
               f"{m('prioridad.externos.A2_reglas_con_categoria_real.recall_criticos')}, lo que confirma que la limitación está en "
               "el lexicón de señales y no en el clasificador."))
    dup = "duplicados_R4_prueba"
    s.append(P("9.5 Vinculación de duplicados (R4)", "h2"))
    s.append(P(f"En el flujo de prueba procesado en orden cronológico había {m(dup + '.duplicados_reales', 'int')} duplicados "
               f"reales; R4 vinculó correctamente {m(dup + '.vinculados_correctamente', 'int')} (recall "
               f"{m(dup + '.recall_duplicados')}). De {m(dup + '.vinculaciones_totales', 'int')} vinculaciones, "
               f"{m(dup + '.vinculaciones_incorrectas', 'int')} unieron reportes distintos (precisión "
               f"{m(dup + '.precision_vinculacion')}). Como R4 conserva toda la evidencia, un vínculo incorrecto no borra "
               "información, pero puede ocultar un problema distinto dentro de otro caso."))
    s.append(P("9.6 ¿Qué significan los resultados para el problema real?", "h2"))
    s.append(P("Con el vocabulario que conoce, el prototipo ordena los reportes como lo haría la política del equipo y no deja "
               f"pasar casos críticos, a cambio de enviar a revisión {m(pt + '.proporcion_revision_humana', 'pct1')} de los reportes. Eso cumple el "
               "objetivo de la primera entrega: una bandeja ordenada y explicable que el personal revisa. Pero con descripciones "
               f"escritas de otra forma, dos de cada tres casos críticos externos ({m(pe + '.falsos_negativos_criticos', 'int')} de "
               f"{m(pe + '.n_criticos', 'int')}) quedarían en la cola normal. En un plantel real eso significaría, por ejemplo, un "
               "apagador que “saca chispitas” atendido como una lámpara fundida. Por lo tanto, el prototipo todavía no puede "
               "usarse para decidir qué se atiende primero sin que una persona lea todos los reportes; puede usarse como apoyo "
               "para ordenar y explicar, y como base para medir mejoras con reportes reales."))

    # ---------------- 10 Errores ----------------
    s.append(P("10. Análisis de errores", "h1"))
    vinc = DTE.loc["S0665"]
    assert str(vinc.vinculado) == "True" and DTE.loc["S0564", "caso_id"] == vinc.caso_id
    s.append(tabla([
        ["Caso", "¿Qué ocurrió?", "Posible causa", "¿Cómo podría mejorarse?"],
        [f"1. Texto vago (P03 y S0917)",
         f"“está dañado, por favor revisen” se clasificó como {p('P03', 'categoria')} con confianza {p('P03', 'confianza', 'dec2')} y no fue a revisión. El texto vago S0917 se clasificó como {x('prueba', 'S0917', 'categoria_pred', 'raw')} con confianza {x('prueba', 'S0917', 'confianza')}.",
         f"El umbral quedó en {m('umbral.valor', 'dec2')} porque la validación comparte vocabulario con el entrenamiento; Naive Bayes da probabilidades extremas aunque el texto no tenga información.",
         "Calibrar las probabilidades; elegir el umbral con casos redactados por otras personas; agregar una regla: si el texto no contiene términos del dominio, revisión humana."],
        ["2. La zona pesa más que el objeto (X10, X25)",
         f"“Se botó el foco del baño de hombres” → {x('externos', 'X10', 'categoria_pred', 'raw')} ({x('externos', 'X10', 'confianza')}). “El cerrojo del baño de mujeres no sirve” → {x('externos', 'X25', 'categoria_pred', 'raw')} ({x('externos', 'X25', 'confianza')}).",
         "En la simulación, las zonas de sanitarios se asociaron casi solo con la categoría Sanitario; el modelo aprendió la palabra “baño” como atajo.",
         "Quitar los nombres de zona del texto antes de clasificar (la zona ya es un campo estructurado) y equilibrar zonas por categoría en los datos."],
        ["3. Falsos negativos críticos por vocabulario (X12, X40, X18)",
         f"“saca chispitas”, “caen pedacitos” y “se le ven los fusibles” quedaron en prioridad {x('externos', 'X12', 'prioridad_pred', 'raw')}, sin escalamiento ni revisión.",
         "El lexicón es cerrado: no reconoce diminutivos (chispitas, pedacitos) ni descripciones indirectas de exposición eléctrica. La regla solo sabe lo que el lexicón nombra.",
         "Usar raíces (chisp, pedac), ampliar el lexicón con personal de mantenimiento y Protección Civil y, con datos reales, entrenar un clasificador de riesgo que complemente al lexicón."],
        ["4. Falsas alarmas por palabras ambiguas (X33, X34)",
         f"“ya se cayó una maestra” activó desprendimiento y “coladera sin tapa” activó riesgo eléctrico; ambos quedaron como {x('externos', 'X33', 'prioridad_pred', 'raw')}.",
         "Los patrones buscan palabras sueltas sin considerar a qué objeto se refieren (“se cayó” una persona, no un plafón).",
         "Exigir que el verbo de riesgo aparezca junto a un objeto del dominio; mantener revisión humana en todo escalamiento."],
        ["5. R4 vincula reportes distintos (S0665)",
         f"“la pared tiene una fisura pequeña” (S0665) se vinculó al caso de “pintura rayada con grafiti” (S0564) de la misma zona. Precisión de R4: {m(dup + '.precision_vinculacion')}.",
         "La similitud de texto incluye las fórmulas de la plantilla (“Reporte de incidencia… Favor de revisar”), que hacen parecer iguales reportes distintos.",
         "Calcular la similitud solo con palabras de contenido, exigir el identificador del activo y pedir confirmación humana antes de vincular."],
    ], [1.15 * inch, 2.0 * inch, 1.85 * inch, 1.9 * inch], chico=True))
    s.append(P("Tabla 9. Casos en los que el prototipo no se comportó como se esperaba. Fuente: resultados/decisiones_*.csv y "
               "pruebas_resultados.json.", "cap"))

    # ---------------- 11 REAS/PAMA ----------------
    s.append(P("11. Relación con el agente inteligente: REAS/PAMA", "h1"))
    s.append(tabla([
        ["Elemento", "Primera entrega", "¿Está implementado?", "Evidencia"],
        ["Percepciones / sensores", "Foto, descripción, zona, fecha, tipo de espacio, categoría propuesta, historial.", "Parcial", "percibir() recibe texto, zona, fecha, calidad de foto, categoría declarada, activo e historial. La imagen no se analiza."],
        ["Procesamiento / razonamiento", "Visión artificial para clases visibles y reglas transparentes de prioridad.", "Sí, con cambio de técnica", "interpretar(): Naive Bayes y lexicón. decidir(): reglas R1–R12 con traza de reglas y motivos."],
        ["Acciones / actuadores", "Pedir datos, sugerir categoría y prioridad, marcar incertidumbre, alertar, crear reporte, actualizar estado, historial, revisión.", "Sí, como registros", "actuar() crea o vincula casos y marca alertas y solicitudes; retroalimentar() y panel(). No envía notificaciones reales."],
        ["Meta", "Detectar, ordenar, priorizar y seguir incidencias, preservando corrección y atención profesional.", "Parcial", "Ordena y prioriza; el seguimiento vive en memoria durante la ejecución; la corrección humana queda en bitácora."],
        ["Conocimiento", "Taxonomía, relaciones edificio-zona-activo, reglas provisionales, evidencia técnica, antecedentes.", "Parcial", "conocimiento.py: taxonomía, lexicón y política. Historial simulado por activo. Sin procedimientos institucionales."],
        ["Medida de desempeño", "Exactitud por categoría, recall y falsos negativos críticos, concordancia de prioridad, escalamiento, tiempo, correcciones.", "Sí, con datos simulados", "Sección 9. No se midieron tiempo por reporte ni proporción de correcciones reales."],
    ], [1.25 * inch, 2.0 * inch, 1.05 * inch, 2.6 * inch], chico=True))
    s.append(P("<b>¿El prototipo puede considerarse ya un agente inteligente?</b> En sentido técnico básico, sí. Según Russell y "
               "Norvig (2021), un agente percibe su entorno mediante sensores y actúa sobre él mediante actuadores. El prototipo "
               "percibe reportes, mantiene un estado interno (casos abiertos e historial), decide con reglas y actúa sobre su "
               "entorno de casos al crearlos, vincularlos o pedir información. Correspondería a un agente reactivo basado en "
               "modelo con una base de conocimiento. No es todavía un agente autónomo desplegado: su entorno es simulado, sus "
               "acciones son registros, no planifica hacia metas ni aprende de las correcciones (estas se guardan para "
               "evaluarlas después). Esa limitación es deliberada, porque las decisiones finales corresponden al personal "
               "responsable."))

    # ---------------- 12 Riesgos ----------------
    s.append(P("12. Riesgos, supervisión humana y uso responsable", "h1"))
    s.append(tabla([
        ["Aspecto", "Análisis"],
        ["Posibles errores", f"Falsos negativos críticos con vocabulario nuevo ({m(pe + '.falsos_negativos_criticos', 'int')} de {m(pe + '.n_criticos', 'int')} en casos externos); falsas alarmas por palabras ambiguas; categoría equivocada por la zona; confianza alta en textos vagos; vinculación de reportes distintos."],
        ["Personas que podrían verse afectadas", "Estudiantes, docentes y trabajadores expuestos a un riesgo que se atiende tarde; personal de mantenimiento, por la carga de falsas alarmas; reportantes cuyo caso queda dentro de otro."],
        ["Sesgos posibles", "Se entienden mejor las redacciones parecidas a las de quien escribió los datos y el lexicón; regionalismos, diminutivos o reportes de personas con menos práctica para describir fallas reciben peor atención. Ciertas zonas pueden quedar sobrerrepresentadas."],
        ["Privacidad de los datos", "El prototipo no usa datos personales. Con datos reales: nombres de reportantes, rostros o placas en fotos y ubicaciones sensibles. Se requiere autorización institucional, minimización, control de acceso, retención limitada y anonimización."],
        ["Decisiones que NO debe tomar automáticamente", "Declarar un espacio seguro o inseguro; emitir diagnósticos estructurales o eléctricos; cerrar casos; bajar un caso a Baja sin confirmación (R5); descartar un reporte por duplicado; clausurar o reabrir espacios."],
        ["Supervisión humana necesaria", "Revisar todo caso escalado (R1, R2, R11) y los marcados por R3, R7 y R8; confirmar R5; validar antes de cerrar. Mientras el recall externo sea bajo, revisar también una muestra periódica de casos Media sin revisión."],
        ["Información que debe darse al usuario", "Que la prioridad es preliminar, las reglas y motivos que la producen, la confianza de la categoría, a qué área se escaló y cómo corregir. La interfaz no debe mostrar “seguro” ni “diagnóstico”."],
    ], [1.85 * inch, 5.05 * inch], primera_col_negrita=True))
    s.append(Spacer(1, 6))
    s.append(nota("El prototipo no sustituye la decisión de un profesional. Ingeniería, arquitectura, electricidad, mantenimiento y "
                  "Protección Civil conservan la evaluación y la decisión final según su competencia."))

    # ---------------- 13 Mejoras ----------------
    s.append(P("13. Propuestas de mejora para la entrega final", "h1"))
    s.append(tabla([
        ["Mejora", "Problema que pretende resolver", "Acción propuesta"],
        ["1. Señales de riesgo más robustas", f"Recall de críticos de {m(pe + '.recall_criticos')} en casos externos; el lexicón no reconoce diminutivos ni descripciones indirectas.", "Ampliar el lexicón con raíces y sinónimos validados por mantenimiento y Protección Civil; exigir objeto + verbo; entrenar un clasificador de riesgo con reportes reales etiquetados."],
        ["2. Umbral de confianza útil", f"El umbral quedó en {m('umbral.valor', 'dec2')} y no envió ningún caso a revisión; las probabilidades de Naive Bayes son extremas.", "Calibrar probabilidades; elegir el umbral con un conjunto de validación redactado por personas ajenas al equipo; regla de texto sin términos del dominio."],
        ["3. Clasificador que generalice", f"F1 macro externo de Naive Bayes {m(C + '.externos.naive_bayes.f1_macro')}, por debajo de las palabras clave ({m(C + '.externos.palabras_clave.f1_macro')}).", "Reunir reportes reales autorizados o redactados por usuarios; quitar la zona del texto; probar n-gramas de caracteres y combinar el lexicón como atributos del modelo."],
        ["4. Duplicados más precisos", f"Precisión de R4 de {m(dup + '.precision_vinculacion')}.", "Similitud solo con palabras de contenido; identificador de activo (código QR); confirmación humana del vínculo."],
        ["5. Retomar la visión artificial", "La foto solo se usa como atributo simulado.", "Con fotos autorizadas: primero un verificador de nitidez e iluminación para R3; después, un clasificador visual comparado con el de texto."],
    ], [1.5 * inch, 2.45 * inch, 2.95 * inch], chico=True))

    # ---------------- 14 IA generativa ----------------
    s.append(P("14. Uso de inteligencia artificial generativa", "h1"))
    s.append(tabla([
        ["Herramienta", "¿Para qué se utilizó?", "¿Qué produjo?", "¿Qué definió o modificó el equipo?", "¿Cómo se verificó?"],
        ["Claude (Anthropic)", "Proponer la técnica y el protocolo de evaluación, programar y ejecutar el prototipo, redactar los casos externos y el borrador de este documento.",
         "Código del generador, del módulo, de la evaluación, la demostración y el notebook; casos externos; capturas de la ejecución; borrador del documento.",
         "El equipo fijó el problema, el alcance y las reglas R1–R6; exigió datos simulados documentados, partición por plantilla, casos externos, umbral sin datos de prueba y cifras reproducibles; aprobó la propuesta antes de construir.",
         "Ejecución del código con semilla fija; el notebook reproduce metricas.json; un script compara cada cifra del PDF con los resultados; pruebas con resultado esperado previo."],
    ], [0.9 * inch, 1.5 * inch, 1.35 * inch, 1.65 * inch, 1.5 * inch], chico=True))
    s.append(P("Conforme a la guía, cada integrante debe poder explicar el código, ejecutar una prueba e interpretar los "
               "resultados. Las anotaciones de los casos externos (categoría y señales de referencia) deben ser revisadas por el "
               "equipo, porque de ellas dependen las métricas externas.", "cap"))

    # ---------------- 15 Conclusiones ----------------
    s.append(P("15. Conclusiones", "h1"))
    s.append(P("Se construyó un prototipo funcional con dos componentes de IA, un clasificador Naive Bayes y un sistema de "
               "reglas, integrados en un agente con ciclo completo, y se evaluó con un protocolo que separa redacciones, "
               "vocabulario y elección de parámetros. Las reglas R1–R6 de la primera entrega se implementaron con su sentido "
               "original, y la supervisión humana quedó incorporada en el flujo: escalamientos, baja confianza, datos faltantes, "
               "conflicto de categoría y confirmación de casos estéticos."))
    s.append(P(f"Con redacciones nuevas pero vocabulario conocido, el prototipo clasifica con F1 macro "
               f"{m(C + '.prueba.naive_bayes.f1_macro')} y detecta todos los casos críticos, frente a ninguno de la línea base "
               f"sin IA. Con vocabulario distinto, el F1 baja a {m(C + '.externos.naive_bayes.f1_macro')} y el recall de casos "
               f"críticos a {m(pe + '.recall_criticos')}. El hallazgo principal no es el puntaje alto, sino esa diferencia: el "
               "sistema aprende y razona bien dentro del lenguaje que conoce y falla fuera de él, y su umbral de confianza no "
               "lo advierte. Por eso, en esta etapa, no debe decidir sin una persona que lea los reportes."))
    s.append(P("Para la tercera entrega, la prioridad es mejorar la percepción de señales de riesgo y calibrar la confianza, "
               "validar las reglas y categorías con personal técnico y, si se obtiene autorización, probar con reportes reales "
               "y retomar la visión artificial."))

    # ---------------- 16 Referencias ----------------
    s.append(P("16. Referencias", "h1"))
    refs = [
        "Instituto Nacional de la Infraestructura Física Educativa. (2021). <i>Normas y especificaciones para estudios, proyectos, construcción e instalaciones: Volumen 7, tomo III, conservación</i>. https://www.inifed.gob.mx/doc/pdf/2021/Normatividad/VOLUMEN_7_TOMO_III_2021.pdf",
        "Kapoor, S., &amp; Narayanan, A. (2023). Leakage and the reproducibility crisis in machine-learning-based science. <i>Patterns, 4</i>(9), 100804. https://doi.org/10.1016/j.patter.2023.100804",
        "Manning, C. D., Raghavan, P., &amp; Schütze, H. (2008). <i>Introduction to information retrieval</i>. Cambridge University Press.",
        "McCallum, A., &amp; Nigam, K. (1998). A comparison of event models for naive Bayes text classification. En <i>AAAI-98 Workshop on Learning for Text Categorization</i> (pp. 41–48). AAAI Press.",
        "Niculescu-Mizil, A., &amp; Caruana, R. (2005). Predicting good probabilities with supervised learning. En <i>Proceedings of the 22nd International Conference on Machine Learning</i> (pp. 625–632). https://doi.org/10.1145/1102351.1102430",
        "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., &amp; Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. <i>Journal of Machine Learning Research, 12</i>, 2825–2830.",
        "Russell, S. J., &amp; Norvig, P. (2021). <i>Artificial intelligence: A modern approach</i> (4th ed.). Pearson.",
        "Yuan, Q., Shi, Y., &amp; Li, M. (2024). A review of computer vision-based crack detection methods in civil infrastructure: Progress and challenges. <i>Remote Sensing, 16</i>(16), 2910. https://doi.org/10.3390/rs16162910",
    ]
    s += [P(r, "ref") for r in refs]

    # ---------------- Anexo ----------------
    s.append(P("Anexo A. Código y reproducción", "h1"))
    s.append(P(f"El código completo está publicado en {LINK} y también se entrega en la carpeta <b>entrega2_EQ3</b> "
               "(archivo .zip adjunto a este documento). Para reproducir todos los resultados:"))
    s.append(codigo(f"git clone {REPO}.git\ncd entrega2_EQ3_codigo"))
    s.append(codigo(
        "pip install -r requirements.txt\n"
        "python generador_datos.py        # regenera datos/ (semilla 2026)\n"
        "python evaluar.py                # entrena, evalúa y escribe resultados/\n"
        "python demo_consola.py           # demostración del agente\n"
        "python demo_consola.py --texto \"el contacto echa chispas\" --zona \"Aula 101\"\n"
        "python documento/generar_capturas.py   # ejecuta y genera las capturas de la sección 7\n"
        "python documento/verificar_cifras.py   # compara cada cifra del PDF con resultados/"))
    s.append(codigo(
        "entrega2_EQ3/\n"
        "├── generador_datos.py            datos simulados documentados\n"
        "├── evaluar.py                    protocolo de evaluación\n"
        "├── demo_consola.py               demostración en consola\n"
        "├── prototipo_mantenimiento_EQ3.ipynb   notebook ejecutado\n"
        "├── pruebas_definidas.json        resultados esperados (antes de ejecutar)\n"
        "├── requirements.txt\n"
        "├── mantenimiento_ia/  conocimiento.py · clasificador.py · reglas.py · agente.py\n"
        "├── datos/             reportes_simulados.csv · historial_activos_simulado.csv ·\n"
        "│                      casos_externos_redactados.json · metadatos_generacion.json\n"
        "├── resultados/        metricas.json · pruebas_resultados.json · decisiones_*.csv ·\n"
        "│                      curva_umbral.csv · demo_salida.txt · figuras/ · capturas/\n"
        "└── documento/         construir_pdf.py · construir_notebook.py · generar_capturas.py ·\n"
        "                       verificar_cifras.py"))
    s.append(P("Huellas SHA-256 de los insumos evaluados:", "body"))
    filas = [["Archivo", "SHA-256"]] + [[k, v] for k, v in M["huellas_sha256"].items()]
    s.append(tabla(filas, [2.1 * inch, 4.8 * inch], chico=True))
    s.append(KeepTogether([P("Fragmento del motor de reglas (mantenimiento_ia/reglas.py):", "body"), codigo(
        "def decidir(self, reporte, categoria, confianza, senales_texto):\n"
        "    f = self.senales_efectivas(senales_texto, categoria)       # contexto de la categoría para R1\n"
        "    previas = contar_incidencias_previas(self.historial, reporte.get('activo_id'), reporte['fecha'])\n"
        "    pol = politica_prioridad(f, reincidencia=previas >= 2, estetico_confirmado=False)\n"
        "    if pol['escalamiento']:  motivos_revision.append('señal de riesgo ...')   # R1, R2, R11\n"
        "    if confianza < self.umbral:  reglas.append('R3')                       # incertidumbre\n"
        "    if foto in ('borrosa', 'oscura'):  acciones.append('solicitar_nueva_foto')\n"
        "    if not reporte.get('zona'):  reglas.append('R7'); acciones.append('solicitar_zona')\n"
        "    if declarada and declarada != categoria:  reglas.append('R8')\n"
        "    if pol['candidato_estetico']:  acciones.append('confirmar_si_es_solo_estetico')   # R5\n"
        "    return {'prioridad': pol['prioridad'], 'escalamiento': pol['escalamiento'],\n"
        "            'revision_humana': bool(motivos_revision), 'reglas': reglas, ...}")]))
    return s


def main():
    salida = BASE / "documento" / "Proyecto_Integrador_IA_Equipo3_Segunda_Entrega.pdf"
    doc = Documento(str(salida), pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                    topMargin=0.75 * inch, bottomMargin=0.8 * inch,
                    title="Proyecto integrador IA · Segunda entrega · Equipo 3",
                    author="Equipo 3 · UNACH ETDA", subject="Segunda entrega parcial de Inteligencia Artificial")
    historia = construir()
    doc.multiBuild(historia, onFirstPage=encabezado, onLaterPages=encabezado)
    (BASE / "documento/cifras_insertadas.json").write_text(json.dumps(REGISTRO, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PDF:", salida, "| cifras registradas:", len(REGISTRO))


if __name__ == "__main__":
    main()
