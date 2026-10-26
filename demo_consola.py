#!/usr/bin/env python3
"""
Demostración en consola del agente.

    python demo_consola.py                     # procesa reportes de ejemplo
    python demo_consola.py --texto "..." --zona "Aula 101" [--foto borrosa]
    python demo_consola.py --interactivo       # escribe reportes uno por uno

El modelo se entrena con las plantillas de ENTRENAMIENTO y usa el umbral
elegido en validación (resultados/metricas.json). Todo es prioridad
PRELIMINAR sujeta a revisión humana; no es un dictamen técnico.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from evaluar import cargar
from mantenimiento_ia import AgenteMantenimiento, crear_naive_bayes

EJEMPLOS = [
    {"id": "D1", "fecha": "2026-10-25", "zona": "Laboratorio de cómputo 1",
     "texto": "Se está filtrando agua por el plafón justo arriba del tablero eléctrico", "foto_calidad": "legible"},
    {"id": "D2", "fecha": "2026-10-25", "zona": "Aula 203",
     "texto": "La pintura de la pared está descarapelada", "foto_calidad": "legible"},
    {"id": "D3", "fecha": "2026-10-25", "zona": "",
     "texto": "la chapa de la puerta no cierra", "foto_calidad": "borrosa"},
]


def preparar():
    m = json.loads((BASE / "resultados/metricas.json").read_text(encoding="utf-8"))
    d, historial, _ = cargar()
    tr = d[d.grupo == "entrenamiento"]
    nb = crear_naive_bayes(m["seleccion"]["alpha_nb"]).fit(tr.texto.values, tr.categoria_ref.values)
    return AgenteMantenimiento(nb, m["umbral"]["valor"], historial, tr.texto.values)


def mostrar(salida):
    i, d, a = salida["interpretacion"], salida["decision"], salida["accion"]
    print("-" * 78)
    print("Reporte:", salida["percepcion"]["texto"])
    print(f"  Zona: {salida['percepcion']['zona'] or '(sin zona)'} | Foto: {salida['percepcion']['foto_calidad']}")
    print(f"  INTERPRETAR  categoría sugerida: {i['categoria']} (confianza {i['confianza']:.2f})")
    print(f"               alternativas: {i['alternativas']}")
    print(f"               palabras que más pesaron: {i['palabras_clave']}")
    print(f"               señales en el texto: {[s for s, v in i['senales_texto'].items() if v]}")
    print(f"  DECIDIR      PRIORIDAD PRELIMINAR: {d['prioridad']} | escalamiento: {'sí' if d['escalamiento'] else 'no'}"
          f" | revisión humana: {'sí' if d['revision_humana'] else 'no'}")
    print(f"               reglas: {d['reglas'] or ['ninguna (prioridad base)']}")
    print(f"               motivos: {d['motivos_prioridad']}")
    if d["motivos_revision"]:
        print(f"               revisión por: {d['motivos_revision']}")
    print(f"  ACTUAR       {a['caso_id']} {'(vinculado a caso abierto, R4)' if a['vinculado'] else ''} acciones: {a['acciones']}")
    print("  Aviso: sugerencia preliminar; la decisión corresponde al personal responsable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texto"); ap.add_argument("--zona", default="")
    ap.add_argument("--foto", default="legible"); ap.add_argument("--interactivo", action="store_true")
    args = ap.parse_args()
    agente = preparar()
    if args.texto:
        mostrar(agente.procesar({"id": "U1", "fecha": str(date.today()), "texto": args.texto,
                                 "zona": args.zona, "foto_calidad": args.foto}))
    elif args.interactivo:
        n = 0
        while True:
            texto = input("\nDescripción (vacío para salir): ").strip()
            if not texto:
                break
            zona = input("Zona: ").strip()
            n += 1
            mostrar(agente.procesar({"id": f"U{n}", "fecha": str(date.today()), "texto": texto,
                                     "zona": zona, "foto_calidad": "legible"}))
    else:
        for r in EJEMPLOS:
            mostrar(agente.procesar(r))
        # Retroalimentación: un responsable confirma que D2 es solo estético (R5)
        caso = agente.retroalimentar("C0002", "Responsable de mantenimiento (simulado)", "2026-10-25", solo_estetico=True)
        print("-" * 78)
        print(f"RETROALIMENTAR  C0002 confirmado como estético -> prioridad {caso.prioridad} (R5)")
        print("PANEL (R6)")
        print(pd.DataFrame(agente.panel("2026-10-25")).to_string(index=False))


if __name__ == "__main__":
    main()
