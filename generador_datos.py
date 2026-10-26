#!/usr/bin/env python3
"""
Generador de reportes SIMULADOS de incidencias de infraestructura.

NINGÚN registro corresponde a un reporte real de la UNACH ni de ETDA. Las
zonas, activos, fechas y textos son inventados para ensayar el prototipo.

Cómo se generan:
1. ESCENARIOS: cada uno define categoría, objetos, problemas y las señales
   verdaderas del hecho (agua, riesgo eléctrico, desprendimiento...).
2. CONTEXTOS opcionales que añaden o niegan señales ("junto al contacto",
   "no hay contactos cerca", "la gente se resbala"...).
3. PLANTILLAS de redacción en cuatro registros (formal, coloquial,
   telegráfico, narrativo). Una plantilla de cada registro se reserva para
   prueba; el resto, para entrenamiento (partición por plantilla).
4. RUIDO: erratas, abreviaturas, minúsculas y acentos omitidos; textos vagos;
   campos faltantes (zona, activo); foto borrosa/oscura/ausente; categoría
   declarada vacía o incorrecta; reportes duplicados.
5. HISTORIAL previo de activos para la regla de reincidencia (R9).
6. REFERENCIA: la prioridad de referencia se calcula aplicando la política
   del equipo (conocimiento.politica_prioridad) a las señales VERDADERAS del
   escenario, no a las que detecta el prototipo.

Uso: python generador_datos.py   (semilla fija 2026)
"""
import csv
import json
import random
import zlib
from datetime import date, timedelta
from pathlib import Path

from mantenimiento_ia.conocimiento import (PARAMETROS, SENALES, es_critico,
                                           politica_prioridad)

SEMILLA = 2026
N_REPORTES = 1400
P_DUPLICADO = 0.06
CARPETA = Path(__file__).resolve().parent / "datos"

PLANTILLAS = {
    "T01": ("formal", "Buen día, se reporta que en {zona} {hecho}{ctx}. Agradeceré su atención."),
    "T02": ("formal", "Por medio de la presente informo que {hecho} en {zona}{ctx}."),
    "T03": ("formal", "Reporte de incidencia: en {zona} {hecho}{ctx}. Favor de revisar."),
    "T04": ("formal", "Solicito apoyo del área de mantenimiento, ya que {hecho}{ctx} ({zona})."),
    "T05": ("coloquial", "oigan en {zona} {hecho}{ctx}, alguien que lo vea porfa"),
    "T06": ("coloquial", "hola!! {hecho} en {zona}{ctx}, ojalá lo puedan ver pronto"),
    "T07": ("coloquial", "chavos de mantenimiento: {hecho}{ctx}, está en {zona}"),
    "T08": ("coloquial", "nada más para avisar que {hecho} en {zona}{ctx} jaja"),
    "T09": ("telegrafico", "{zona}: {hecho}{ctx}"),
    "T10": ("telegrafico", "{hecho}{ctx}. {zona}."),
    "T11": ("telegrafico", "revisar {zona} - {hecho}{ctx}"),
    "T12": ("telegrafico", "{zona} / {hecho}{ctx} / gracias"),
    "T13": ("narrativo", "Hoy en la mañana me di cuenta de que {hecho} en {zona}{ctx}. Lo comento para que lo tomen en cuenta."),
    "T14": ("narrativo", "Estábamos en clase en {zona} y notamos que {hecho}{ctx}; el profe nos pidió reportarlo."),
    "T15": ("narrativo", "Desde hace unos días {hecho} en {zona}{ctx} y nadie ha dicho nada."),
    "T16": ("narrativo", "Al salir de {zona} vi que {hecho}{ctx}, por si no lo tenían reportado."),
}

ZONAS = {
    "aulas": ["Aula 101", "Aula 102", "Aula 203", "Aula 204", "Aula 305"],
    "labs": ["Laboratorio de cómputo 1", "Laboratorio de cómputo 2", "Laboratorio de redes"],
    "circulaciones": ["Pasillo planta baja", "Pasillo primer piso", "Escaleras edificio A", "Explanada", "Entrada principal"],
    "sanitarios": ["Sanitarios hombres PB", "Sanitarios mujeres PB", "Sanitarios primer piso"],
    "otros": ["Biblioteca", "Sala de maestros", "Auditorio", "Cafetería", "Dirección"],
}
PREFERENCIA_ZONA = {  # probabilidad de cada grupo de zonas según la categoría
    "HUMEDAD": {"aulas": .35, "labs": .15, "circulaciones": .2, "sanitarios": .1, "otros": .2},
    "ELECTRICO": {"aulas": .35, "labs": .25, "circulaciones": .15, "sanitarios": .05, "otros": .2},
    "PUERTAS": {"aulas": .4, "labs": .15, "circulaciones": .1, "sanitarios": .15, "otros": .2},
    "PISOS": {"aulas": .25, "labs": .1, "circulaciones": .45, "sanitarios": .05, "otros": .15},
    "MUROS": {"aulas": .35, "labs": .1, "circulaciones": .3, "sanitarios": .05, "otros": .2},
    "SANITARIO": {"aulas": 0, "labs": 0, "circulaciones": .05, "sanitarios": .85, "otros": .1},
    "MOBILIARIO": {"aulas": .35, "labs": .2, "circulaciones": .1, "sanitarios": 0, "otros": .35},
}

CONTEXTOS = {
    "elec_cerca": ([", junto al contacto", ", cerca del tablero eléctrico", ", justo arriba de la lámpara",
                    ", a un lado del enchufe del proyector"], {"electrico"}),
    "agua_cae": ([", y le cae agua cuando llueve", ", y está mojado por una gotera"], {"agua"}),
    "neg_elec": ([", no hay contactos cerca", ", sin cables cerca", ", lejos de los enchufes"], set()),
    "circ": ([", la gente se resbala al pasar", ", está en pleno paso de los alumnos",
              ", ya alguien se tropezó ahí"], {"circulacion"}),
    "sin_serv": ([", ninguno de los baños se puede usar", ", así no se puede usar el espacio"], {"sin_servicio"}),
    "irrelevante": ([", desde el lunes", ", lo vimos varios compañeros", ", desde la semana pasada", ""], set()),
}

# id, categoría, objetos, problemas, señales verdaderas, contextos posibles {nombre: prob}
ESCENARIOS = [
    # HUMEDAD
    ("H1", "HUMEDAD", ["el techo", "el plafón", "la losa del pasillo"],
     ["tiene goteras", "está goteando cuando llueve", "tiene una filtración de agua", "deja caer agua"],
     {"agua"}, {"elec_cerca": .2, "neg_elec": .1}),
    ("H2", "HUMEDAD", ["la pared del fondo", "el muro lateral", "la pared junto a la ventana"],
     ["tiene una mancha de humedad que va creciendo", "está húmeda y con moho", "se ve mojada"],
     {"agua"}, {"elec_cerca": .2, "neg_elec": .1}),
    ("H3", "HUMEDAD", ["la pared", "el techo"],
     ["tiene una mancha vieja de humedad, ya seca", "tiene marcas de una gotera antigua que ya no gotea"],
     {"estetico"}, {}),
    ("H4", "HUMEDAD", ["el piso del pasillo", "la entrada del salón"],
     ["se encharca cuando llueve", "tiene un charco de agua que entra por la puerta"],
     {"agua"}, {"circ": .35}),
    ("H5", "HUMEDAD", ["la parte baja del muro"],
     ["tiene salitre y la pintura se está inflando", "está con humedad y se está botando la pintura"],
     {"agua"}, {"elec_cerca": .15}),
    # ELÉCTRICO
    ("E1", "ELECTRICO", ["una lámpara", "dos lámparas", "el foco del pasillo", "la luminaria del pizarrón"],
     ["no prende", "está fundida", "parpadea todo el tiempo", "hace un zumbido y prende a ratos"],
     {"electrico"}, {"agua_cae": .1}),
    ("E2", "ELECTRICO", ["el contacto de la mesa 3", "los contactos de la pared", "el enchufe del proyector"],
     ["no tiene corriente", "no funciona", "está flojo y se salen las clavijas"],
     {"electrico"}, {"agua_cae": .1}),
    ("E3", "ELECTRICO", ["el contacto junto a la puerta", "el apagador", "el tablero eléctrico", "una extensión fija"],
     ["echa chispas al conectar algo", "huele a quemado", "tiene los cables expuestos",
      "está sin tapa y se ven los cables", "da toques al tocarlo"],
     {"electrico", "riesgo_electrico"}, {}),
    ("E4", "ELECTRICO", ["todo el laboratorio", "el salón completo"],
     ["se quedó sin luz", "no tiene energía desde la mañana"],
     {"electrico", "sin_servicio"}, {}),
    # PUERTAS
    ("P1", "PUERTAS", ["la chapa de la puerta", "la cerradura del salón", "el cerrojo"],
     ["no cierra", "está atorada", "se trabó y no abre con la llave"], set(), {}),
    ("P2", "PUERTAS", ["la puerta", "una de las hojas de la puerta"],
     ["está descolgada de una bisagra", "rechina y no cierra bien", "se arrastra en el piso"], set(), {}),
    ("P3", "PUERTAS", ["el vidrio de la ventana", "un cristal de la puerta"],
     ["está estrellado", "está roto", "está quebrado"], set(), {}),
    ("P4", "PUERTAS", ["la ventana", "las ventanas corredizas"],
     ["no cierra bien", "está atascada y no abre", "tiene el riel dañado"], set(), {}),
    ("P5", "PUERTAS", ["la puerta de salida de emergencia", "la puerta del pasillo de salida"],
     ["no abre", "está trabada"], {"circulacion"}, {}),
    # PISOS
    ("F1", "PISOS", ["una loseta", "varias losetas", "el piso"],
     ["está rota", "está quebrada", "está despegada"], set(), {"circ": .15}),
    ("F2", "PISOS", ["el piso del pasillo", "una loseta de la entrada", "el piso de la escalera"],
     ["está levantado y la gente se tropieza", "tiene un hoyo", "tiene un hueco donde uno se puede doblar el pie"],
     {"circulacion"}, {}),
    ("F3", "PISOS", ["el piso de la entrada", "el piso de la escalera"],
     ["está muy resbaloso", "está liso y la gente se resbala"], {"circulacion"}, {}),
    ("F4", "PISOS", ["el piso", "el piso del salón"],
     ["está muy desgastado y manchado", "está rayado y se ve feo"], {"estetico"}, {}),
    ("F5", "PISOS", ["un escalón", "la orilla de un escalón"],
     ["está despostillado", "tiene la nariz rota"], {"circulacion"}, {}),
    # MUROS
    ("M1", "MUROS", ["la pintura de la pared", "el muro del pasillo", "la fachada"],
     ["está descarapelada", "está rayada con grafiti", "está despintada"], {"estetico"}, {}),
    ("M2", "MUROS", ["la pared", "el muro"],
     ["tiene una grieta delgada", "tiene una fisura pequeña"], set(), {}),
    ("M3", "MUROS", ["la pared junto a la columna", "el muro de carga", "la losa", "la trabe del pasillo"],
     ["tiene una grieta grande que va creciendo", "tiene una grieta diagonal ancha",
      "tiene una cuarteadura que se está abriendo"], {"estructural"}, {}),
    ("M4", "MUROS", ["un pedazo del plafón", "el aplanado del techo", "un panel del falso plafón"],
     ["se cayó", "está a punto de caerse", "se está desprendiendo", "está colgando"], {"desprendimiento"}, {}),
    ("M5", "MUROS", ["un panel del plafón"], ["está roto", "está manchado y deformado"], set(), {}),
    # SANITARIO
    ("S1", "SANITARIO", ["el lavabo", "la llave del lavabo", "el tubo debajo del lavabo"],
     ["tiene una fuga", "gotea todo el día", "no deja de tirar agua"], {"agua"}, {"elec_cerca": .1, "neg_elec": .1}),
    ("S2", "SANITARIO", ["el inodoro", "el mingitorio", "uno de los baños"],
     ["está tapado", "no le baja el agua", "está atascado"], {"agua"}, {"sin_serv": .15}),
    ("S3", "SANITARIO", ["los baños", "los sanitarios de mujeres", "los lavabos"],
     ["no tienen agua", "se quedaron sin agua"], {"sin_servicio"}, {}),
    ("S4", "SANITARIO", ["una tubería", "el tubo del tinaco"],
     ["se rompió y está inundando el baño", "revienta y sale mucha agua"], {"agua"}, {"circ": .2, "elec_cerca": .1}),
    ("S5", "SANITARIO", ["la tapa del inodoro", "la palanca del tanque"], ["está rota", "no sirve"], set(), {}),
    # MOBILIARIO
    ("B1", "MOBILIARIO", ["una butaca del auditorio", "las bancas fijas", "una mesa de laboratorio"],
     ["está floja", "tiene una pata rota", "se tambalea"], set(), {}),
    ("B2", "MOBILIARIO", ["el pizarrón", "el pintarrón"],
     ["está flojo de la pared", "está despegado de un lado"], set(), {}),
    ("B3", "MOBILIARIO", ["el anaquel de la biblioteca", "una repisa", "el soporte del proyector"],
     ["está a punto de caerse", "se está desprendiendo de la pared", "está colgando de un solo tornillo"],
     {"desprendimiento"}, {}),
    ("B4", "MOBILIARIO", ["las mesas", "las butacas"], ["están rayadas", "están sucias y pintadas"], {"estetico"}, {}),
    ("B5", "MOBILIARIO", ["los lockers", "la puerta del gabinete"], ["no cierran", "tienen la chapa rota"], set(), {}),
]

TEXTOS_VAGOS = ["está dañado, revisen", "no sirve, urge", "hay un problema aquí", "ya se descompuso otra vez"]
FOTO = [("legible", .72), ("borrosa", .10), ("oscura", .06), ("sin_foto", .12)]


def elegir_ponderado(rng, pares):
    r, acum = rng.random(), 0.0
    for valor, p in pares:
        acum += p
        if r < acum:
            return valor
    return pares[-1][0]


def errata(rng, palabra):
    if len(palabra) < 5:
        return palabra
    i = rng.randrange(1, len(palabra) - 2)
    op = rng.choice(["intercambiar", "omitir", "duplicar"])
    if op == "intercambiar":
        return palabra[:i] + palabra[i + 1] + palabra[i] + palabra[i + 2:]
    if op == "omitir":
        return palabra[:i] + palabra[i + 1:]
    return palabra[:i] + palabra[i] + palabra[i:]


def quitar_acentos(t):
    return t.translate(str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU"))


def aplicar_ruido(rng, texto, registro):
    if registro in ("coloquial", "telegrafico") and rng.random() < .5:
        texto = texto.lower()
    if rng.random() < (.45 if registro != "formal" else .1):
        texto = quitar_acentos(texto)
    if registro == "coloquial" and rng.random() < .35:
        for largo, corto in ((" que ", " q "), ("por favor", "xfa"), ("también", "tmb"), ("salón", "salon")):
            texto = texto.replace(largo, corto)
    if rng.random() < .18:
        palabras = texto.split()
        for _ in range(rng.choice([1, 2])):
            j = rng.randrange(len(palabras))
            palabras[j] = errata(rng, palabras[j])
        texto = " ".join(palabras)
    return texto


def construir_texto(rng, plantilla, objeto, problema, zona_txt, ctx_txt):
    hecho = f"{objeto} {problema}"
    return PLANTILLAS[plantilla][1].format(zona=zona_txt, hecho=hecho, ctx=ctx_txt)


def generar(semilla=SEMILLA, n=N_REPORTES):
    rng = random.Random(semilla)
    # Partición por plantilla: una plantilla de cada registro va a PRUEBA
    registros = sorted({r for r, _ in PLANTILLAS.values()})
    plantillas_prueba = sorted(rng.choice([t for t, (r, _) in PLANTILLAS.items() if r == reg]) for reg in registros)
    grupo_de = {t: ("prueba" if t in plantillas_prueba else "entrenamiento") for t in PLANTILLAS}
    por_grupo = {g: [t for t in PLANTILLAS if grupo_de[t] == g] for g in ("entrenamiento", "prueba")}

    por_categoria = {}
    for esc in ESCENARIOS:
        por_categoria.setdefault(esc[1], []).append(esc)
    categorias = list(por_categoria)
    inicio = date(2026, 8, 10)

    n_dup = round(n * P_DUPLICADO)
    n_base = n - n_dup
    reportes = []
    for k in range(n_base):
        cat = categorias[k % len(categorias)]
        esc_id, _, objetos, problemas, flags_base, ctx_probs = rng.choice(por_categoria[cat])
        plantilla = rng.choice(list(PLANTILLAS))
        grupo_zona = elegir_ponderado(rng, list(PREFERENCIA_ZONA[cat].items()))
        zona = rng.choice(ZONAS[grupo_zona])
        activo_real = f"{zona.split()[0][:3].upper()}{zlib.crc32(zona.encode()) % 97:02d}-{cat[:3]}-{rng.randint(1, 15):02d}"
        reportes.append(dict(
            escenario=esc_id, categoria_ref=cat, objeto=rng.choice(objetos), problemas=problemas,
            flags_base=set(flags_base), ctx_probs=ctx_probs, plantilla=plantilla, zona_real=zona,
            activo_real=activo_real, fecha=inicio + timedelta(days=rng.randrange(0, 72)), duplicado_de=""))
    # Duplicados: mismo hecho y activo, otra redacción del MISMO grupo, 1-5 días después
    for _ in range(n_dup):
        orig = rng.choice(reportes[:n_base])
        grupo = grupo_de[orig["plantilla"]]
        nuevo = dict(orig)
        nuevo["plantilla"] = rng.choice([t for t in por_grupo[grupo] if t != orig["plantilla"]])
        nuevo["fecha"] = orig["fecha"] + timedelta(days=rng.randint(1, 5))
        nuevo["duplicado_de"] = "PENDIENTE"
        nuevo["_orig"] = orig
        reportes.append(nuevo)
    reportes.sort(key=lambda r: r["fecha"])
    for i, r in enumerate(reportes, 1):
        r["id"] = f"S{i:04d}"
    for r in reportes:
        if r["duplicado_de"] == "PENDIENTE":
            r["duplicado_de"] = r.pop("_orig")["id"]

    # Historial previo de activos (para R9)
    historial = []
    for r in reportes:
        if r["duplicado_de"]:
            continue
        u = rng.random()
        if u < .12:      # reincidencia real: 2-3 incidencias en los 90 días previos
            for _ in range(rng.choice([2, 3])):
                historial.append((r["activo_real"], r["fecha"] - timedelta(days=rng.randint(5, 85)), r["categoria_ref"]))
        elif u < .22:    # una sola incidencia reciente (no es reincidencia)
            historial.append((r["activo_real"], r["fecha"] - timedelta(days=rng.randint(5, 85)), r["categoria_ref"]))
        elif u < .27:    # incidencias antiguas, fuera de la ventana
            for _ in range(2):
                historial.append((r["activo_real"], r["fecha"] - timedelta(days=rng.randint(120, 300)), r["categoria_ref"]))
    hist_idx = {}
    for activo, f, _ in historial:
        hist_idx.setdefault(activo, []).append(f)

    filas = []
    for r in reportes:
        ctx_nombre = "irrelevante"
        u, acum = rng.random(), 0.0
        for nombre, p in r["ctx_probs"].items():
            acum += p
            if u < acum:
                ctx_nombre = nombre
                break
        ctx_frases, ctx_flags = CONTEXTOS[ctx_nombre]
        flags = set(r["flags_base"]) | ctx_flags
        registro = PLANTILLAS[r["plantilla"]][0]
        zona_vacia = rng.random() < .05
        zona_txt = r["zona_real"] if not (zona_vacia and rng.random() < .5) else "aquí"
        texto = construir_texto(rng, r["plantilla"], r["objeto"], rng.choice(r["problemas"]),
                                zona_txt, rng.choice(ctx_frases))
        vago = rng.random() < .03
        if vago:
            texto = rng.choice(TEXTOS_VAGOS) + f" ({zona_txt})"
            flags = set()  # el texto ya no expresa las señales del hecho
        texto = aplicar_ruido(rng, texto, registro)
        u = rng.random()
        if u < .55:
            declarada = ""
        elif u < .93:
            declarada = r["categoria_ref"]
        else:
            declarada = rng.choice([c for c in categorias if c != r["categoria_ref"]])
        activo_reportado = r["activo_real"] if rng.random() < .65 else ""
        desde = r["fecha"] - timedelta(days=PARAMETROS["ventana_reincidencia_dias"])
        previas = sum(1 for f in hist_idx.get(r["activo_real"], []) if desde <= f < r["fecha"])
        reincidencia = previas >= PARAMETROS["min_incidencias_reincidencia"]
        f_dict = {s: (s in flags) for s in SENALES}
        ref = politica_prioridad(f_dict, reincidencia=reincidencia,
                                 estetico_confirmado=f_dict["estetico"])
        filas.append({
            "id": r["id"], "fecha": r["fecha"].isoformat(),
            "zona": "" if zona_vacia else r["zona_real"],
            "texto": texto, "foto_calidad": elegir_ponderado(rng, FOTO),
            "categoria_declarada": declarada, "activo_id": activo_reportado,
            # --- columnas de control (no las ve el prototipo) ---
            "plantilla": r["plantilla"], "registro": registro, "grupo": grupo_de[r["plantilla"]],
            "escenario": r["escenario"], "contexto": ctx_nombre, "texto_vago": vago,
            "activo_real": r["activo_real"], "zona_real": r["zona_real"],
            "duplicado_de": r["duplicado_de"],
            "categoria_ref": r["categoria_ref"], "senales_ref": "|".join(sorted(flags)),
            "reincidencia_ref": reincidencia, "prioridad_ref": ref["prioridad"],
            "escalamiento_ref": ref["escalamiento"],
            "critico_ref": es_critico(ref["prioridad"], ref["escalamiento"]),
        })
    return filas, historial, plantillas_prueba


def main():
    CARPETA.mkdir(exist_ok=True)
    filas, historial, plantillas_prueba = generar()
    with open(CARPETA / "reportes_simulados.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    with open(CARPETA / "historial_activos_simulado.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["activo_id", "fecha", "categoria"])
        for a, f, c in sorted(historial, key=lambda x: (x[0], x[1])):
            w.writerow([a, f.isoformat(), c])
    meta = {"semilla": SEMILLA, "n_reportes": len(filas), "n_historial": len(historial),
            "plantillas_prueba": plantillas_prueba,
            "nota": "Datos SIMULADOS. No corresponden a reportes reales de la UNACH ni de ETDA."}
    (CARPETA / "metadatos_generacion.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
