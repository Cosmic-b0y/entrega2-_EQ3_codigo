"""
Base de conocimiento del prototipo.

Contiene la taxonomía de categorías, los niveles de prioridad, el lexicón de
señales de riesgo y la política de prioridad (reglas R1-R12) que comparten el
motor de reglas y el generador de datos simulados.

IMPORTANTE: todo lo aquí definido es una propuesta del Equipo 3 para un piloto
académico. Los criterios NO han sido validados por personal técnico y ninguna
salida equivale a un dictamen profesional.
"""
import re
import unicodedata

# ---------------------------------------------------------------------------
# Taxonomía (derivada del alcance de la primera entrega)
# ---------------------------------------------------------------------------
CATEGORIAS = {
    "HUMEDAD": "Humedad y filtraciones",
    "ELECTRICO": "Eléctrico y luminarias",
    "PUERTAS": "Puertas, ventanas y cerraduras",
    "PISOS": "Pisos y circulaciones",
    "MUROS": "Muros, plafones y acabados",
    "SANITARIO": "Sanitario e hidráulico",
    "MOBILIARIO": "Mobiliario fijo",
}
LISTA_CATEGORIAS = list(CATEGORIAS)

AREA_COMPETENTE = {
    "HUMEDAD": "Mantenimiento general / impermeabilización",
    "ELECTRICO": "Personal electricista",
    "PUERTAS": "Mantenimiento general / herrería y cerrajería",
    "PISOS": "Mantenimiento general / obra civil",
    "MUROS": "Mantenimiento general / obra civil",
    "SANITARIO": "Plomería",
    "MOBILIARIO": "Mantenimiento general / carpintería",
}

PRIORIDADES = ["Baja", "Media", "Alta", "Inmediata"]
NIVEL = {p: i for i, p in enumerate(PRIORIDADES)}

SENALES = [
    "agua",              # agua o humedad activa
    "electrico",         # presencia de un elemento eléctrico
    "riesgo_electrico",  # indicio de riesgo eléctrico directo (chispas, quemado...)
    "desprendimiento",   # algo cayó o puede caer
    "estructural",       # indicio potencialmente estructural
    "circulacion",       # afecta el paso o la evacuación de personas
    "sin_servicio",      # un espacio completo queda sin servicio
    "estetico",          # problema de apariencia
]
SENALES_DE_RIESGO = ["agua", "riesgo_electrico", "desprendimiento",
                     "estructural", "circulacion", "sin_servicio"]

# Parámetros fijados por el equipo ANTES de evaluar (no son plazos normativos)
PARAMETROS = {
    "min_palabras_descripcion": 4,      # R7
    "ventana_reincidencia_dias": 90,    # R9
    "min_incidencias_reincidencia": 2,  # R9
    "ventana_duplicado_dias": 7,        # R4
    "similitud_duplicado": 0.35,        # R4 (cuando no hay identificador de activo)
    "antiguedad_aviso_dias": 15,        # R6 (solo para resaltar en el panel)
}

# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------
ABREVIATURAS = {
    "q": "que", "k": "que", "xq": "porque", "pq": "porque", "xfa": "por favor",
    "porfa": "por favor", "tmb": "tambien", "tb": "tambien", "d": "de",
    "lab": "laboratorio", "sal": "salon", "wc": "inodoro",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin signos, con abreviaturas comunes expandidas."""
    if not isinstance(texto, str):
        return ""
    t = texto.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    tokens = [ABREVIATURAS.get(tok, tok) for tok in t.split()]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Lexicón de señales (redactado por el equipo a partir del dominio).
# Se congeló antes de redactar los casos externos y no se ajustó con ellos.
# ---------------------------------------------------------------------------
LEXICON = {
    "agua": r"\bagua\b|gote|filtr|\bmoja|charc|encharc|escurr|chorre|inund|\bfuga|humed|salitre|\bmoho",
    "electrico": r"contacto|enchufe|tomacorriente|\bcable|tablero|lampara|luminaria|\bfoco|apagador|interruptor|balastr|electric|clavija|extension|corriente|energia|\bluz\b",
    "riesgo_electrico": r"chispa|chispe|quemad|\bhumo\b|\btoques?\b|descarga|corto ?circuito|flamazo|cables? (expuest|pelad|suelt|colgand)|se ven los cables|sin tapa|se calienta",
    "desprendimiento": r"se cayo|se cae\b|caerse|a punto de caer|desprend|colgando|se vino abajo|pedazo|trozo|se esta cayendo",
    "circulacion": r"resbal|tropez|tropiez|\bhoyo|\bhueco|levantad|escalon|doblar el pie|salida de emergencia|bloque|obstru|paso de",
    "sin_servicio": r"ningun[oa]? .*(sirve|funciona|se puede usar)|no se puede usar|sin luz|sin agua|no tienen? agua|no tiene energia|sin energia|se quedo sin|inservible|clausurad",
    "estetico": r"pintura|despint|descarapel|rayad|grafiti|graffiti|manchad|se ve feo|sucio|desgastad|\bvieja\b|estetic",
}
# La señal estructural exige una palabra de grieta + un indicador de severidad,
# o un indicio de hundimiento/deformación.
GRIETA = r"grieta|fisura|cuarteadura"
SEVERIDAD = r"grande|ancha|profunda|diagonal|crec|abri|columna|trabe|viga|\blosa|carga"
HUNDIMIENTO = r"hundimiento|se esta hundiendo|pandead"

NEGADORES = {"no", "sin", "ni", "nunca", "ningun", "ninguna", "ninguno", "tampoco"}
SENALES_NEGABLES = {"agua", "electrico", "riesgo_electrico", "desprendimiento"}
VENTANA_NEGACION = 3  # tokens previos que se revisan


def _negada(texto_norm: str, inicio: int) -> bool:
    previos = texto_norm[:inicio].split()[-VENTANA_NEGACION:]
    return any(tok in NEGADORES for tok in previos)


def detectar_senales(texto: str) -> dict:
    """Devuelve {senal: bool} y la evidencia textual de cada señal detectada."""
    t = normalizar(texto)
    flags = {s: False for s in SENALES}
    evidencia = {}
    for senal, patron in LEXICON.items():
        for m in re.finditer(patron, t):
            if senal in SENALES_NEGABLES and _negada(t, m.start()):
                evidencia.setdefault(senal + "_negada", []).append(m.group(0))
                continue
            flags[senal] = True
            evidencia.setdefault(senal, []).append(m.group(0))
    if (re.search(GRIETA, t) and re.search(SEVERIDAD, t)) or re.search(HUNDIMIENTO, t):
        flags["estructural"] = True
        evidencia["estructural"] = [x for x in re.findall(GRIETA + "|" + SEVERIDAD + "|" + HUNDIMIENTO, t)]
    return {"flags": flags, "evidencia": evidencia}


# ---------------------------------------------------------------------------
# Política de prioridad (R1, R2, R5, R9, R10, R11, R12)
# Se aplica igual a las señales verdaderas (para construir la referencia
# simulada) y a las señales percibidas por el prototipo.
# ---------------------------------------------------------------------------
def politica_prioridad(f: dict, reincidencia: bool = False,
                       estetico_confirmado: bool = False) -> dict:
    nivel = NIVEL["Media"]
    escalar = False
    reglas = []
    motivos = []
    if f.get("agua") and f.get("electrico"):
        nivel = max(nivel, NIVEL["Inmediata"]); escalar = True
        reglas.append("R1"); motivos.append("agua o humedad cerca de un elemento eléctrico")
    if f.get("riesgo_electrico"):
        nivel = max(nivel, NIVEL["Inmediata"]); escalar = True
        reglas.append("R11"); motivos.append("indicio de riesgo eléctrico directo")
    if f.get("desprendimiento"):
        nivel = max(nivel, NIVEL["Inmediata"]); escalar = True
        reglas.append("R2"); motivos.append("indicio de desprendimiento: requiere inspección especializada")
    if f.get("estructural"):
        nivel = max(nivel, NIVEL["Alta"]); escalar = True
        if "R2" not in reglas:
            reglas.append("R2")
        motivos.append("indicio potencialmente estructural: requiere inspección especializada")
    if f.get("circulacion"):
        nivel = max(nivel, NIVEL["Alta"])
        reglas.append("R10"); motivos.append("afecta la circulación o evacuación de personas")
    if f.get("sin_servicio"):
        nivel = max(nivel, NIVEL["Alta"])
        reglas.append("R12"); motivos.append("un espacio completo queda sin servicio")
    hay_riesgo = any(f.get(s) for s in SENALES_DE_RIESGO)
    candidato_estetico = bool(f.get("estetico")) and not hay_riesgo
    if candidato_estetico and estetico_confirmado:
        nivel = NIVEL["Baja"]
        reglas.append("R5"); motivos.append("responsable confirmó problema exclusivamente estético")
    if reincidencia and nivel < NIVEL["Alta"]:
        nivel += 1
        reglas.append("R9"); motivos.append("reincidencia en el mismo activo según el historial")
    return {
        "prioridad": PRIORIDADES[nivel],
        "escalamiento": escalar,
        "reglas": reglas,
        "motivos": motivos,
        "candidato_estetico": candidato_estetico,
    }


def es_critico(prioridad: str, escalamiento: bool) -> bool:
    """Un caso es crítico si su prioridad es Inmediata o requiere escalamiento."""
    return prioridad == "Inmediata" or bool(escalamiento)
