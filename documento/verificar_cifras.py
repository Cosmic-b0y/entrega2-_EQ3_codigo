#!/usr/bin/env python3
"""
Verifica que cada cifra del PDF coincida con los resultados ejecutados.

1. Reejecuta la evaluación (semilla fija) y comprueba que reproduce
   resultados/metricas.json exactamente.
2. Recalcula cada cifra registrada al construir el PDF desde su fuente
   (metricas.json, pruebas_resultados.json, decisiones_*.csv o parámetros
   del código) y comprueba que el texto insertado sea el mismo.
3. Extrae el texto del PDF y comprueba que cada cifra registrada aparezca.
4. Lista los números del PDF que no provienen del registro (identificadores,
   fechas, años, numeración, referencias) para revisión manual.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pdfplumber

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "documento"))
import evaluar as EV
import generador_datos as GEN
from mantenimiento_ia.conocimiento import PARAMETROS

PDF = BASE / "documento/Proyecto_Integrador_IA_Equipo3_Segunda_Entrega.pdf"


def formatear(v, f):
    if v is None:
        return "—"
    return {"dec3": lambda: f"{v:.3f}", "dec2": lambda: f"{v:.2f}", "pct1": lambda: f"{v * 100:.1f} %",
            "int": lambda: str(int(v))}.get(f, lambda: str(v))()


def main():
    informe = []
    # 1. Reproducibilidad
    m_nuevo, *_ = EV.ejecutar_todo(guardar=False)
    m = json.loads((BASE / "resultados/metricas.json").read_text(encoding="utf-8"))
    reproducible = json.dumps(m_nuevo, sort_keys=True, default=str) == json.dumps(m, sort_keys=True, default=str)
    informe.append(f"1. Reejecución con semilla {EV.SEMILLA} reproduce metricas.json: {'SÍ' if reproducible else 'NO'}")

    # 2. Recalcular cada cifra registrada
    reg = json.loads((BASE / "documento/cifras_insertadas.json").read_text(encoding="utf-8"))
    pr = {p["id"]: p for p in json.loads((BASE / "resultados/pruebas_resultados.json").read_text(encoding="utf-8"))["pruebas"]}
    dec = {c: pd.read_csv(BASE / f"resultados/decisiones_{c}.csv", keep_default_na=False).set_index("id")
           for c in ("prueba", "externos")}
    params = {**{f"PARAMETROS.{k}": v for k, v in PARAMETROS.items()},
              "ERROR_MAX_ACEPTADOS": EV.ERROR_MAX_ACEPTADOS, "GRID_UMBRAL_MIN": EV.GRID_UMBRAL[0],
              "GRID_UMBRAL_MAX": EV.GRID_UMBRAL[-1], "SEMILLA": EV.SEMILLA, "N_ESCENARIOS": len(GEN.ESCENARIOS),
              "N_PLANTILLAS": len(GEN.PLANTILLAS), "P_DUPLICADO": GEN.P_DUPLICADO}
    discrepancias = []
    for e in reg:
        f, ruta = e["formato"], e["ruta"]
        if e["fuente"] == "metricas.json":
            v = m
            for k in (ruta if isinstance(ruta, list) else ruta.split(".")):
                v = v[int(k)] if isinstance(v, list) else v[k]
            esperado = formatear(v, f)
        elif e["fuente"] == "pruebas_resultados.json":
            pid, *resto = ruta.split(".")
            if resto == ["correcto"]:
                esperado = "Sí" if pr[pid]["correcto"] else "No"
            else:
                esperado = formatear(pr[pid]["obtenido"][resto[-1]], f)
        elif e["fuente"].startswith("decisiones_"):
            conj = e["fuente"][len("decisiones_"):-4]
            rid, col = ruta.split(".")
            val = dec[conj].loc[rid, col]
            esperado = formatear(val if f == "raw" else float(val), f)
        else:
            esperado = formatear(params[ruta], f)
        if esperado != e["texto"]:
            discrepancias.append((e, esperado))
    informe.append(f"2. Cifras registradas al construir el PDF: {len(reg)}; recalculadas desde su fuente con discrepancias: {len(discrepancias)}")
    for e, esp in discrepancias:
        informe.append(f"   DISCREPANCIA {e['fuente']} {e['ruta']}: PDF={e['texto']} fuente={esp}")

    # 3. Presencia en el PDF
    with pdfplumber.open(PDF) as pdf:
        paginas = [pg.extract_text() or "" for pg in pdf.pages]
    texto = re.sub(r"[ \t]+", " ", "\n".join(paginas))
    plano = texto.replace("\n", " ")
    ausentes = sorted({e["texto"] for e in reg if e["texto"] not in plano and e["texto"] not in ("Sí", "No")})
    informe.append(f"3. Páginas del PDF: {len(paginas)}; cifras registradas ausentes del texto extraído: {len(ausentes)}")
    for a in ausentes:
        informe.append(f"   AUSENTE: {a}")
    # conteo: cada aparición de una cifra de resultados debe estar respaldada por un registro
    n_reg = Counter(e["texto"] for e in reg)

    # 4. Números del PDF que no provienen del registro
    permitidos = set()
    for e in reg:
        permitidos.update(re.findall(r"\d+(?:\.\d+)?", e["texto"]))
    patrones_estructurales = [
        r"\b[SXPCT]\d{2,4}\b", r"\bR\d{1,2}\b", r"\b20\d\d\b", r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b[0-9a-f]{16,64}\b", r"\bdoi\.org/\S+", r"https?://\S+", r"\bAula \d+", r"\bmesa \d+",
        r"\bp\. ?\d+|pp\. \d+[–-]\d+", r"\b\d+[–-]\d+\b", r"\b\d+\(\d+\)", r"\b[A-Z]{3}\d{2}-[A-Z]{3}-\d{2}\b",
        r"Proyecto integrador · Segunda entrega \| \d+", r"^\d+\. ", r"\b\d+\.\d+ [A-ZÁÉÍÓÚ¿]",
    ]
    restante = texto
    for pat in patrones_estructurales:
        restante = re.sub(pat, " ", restante, flags=re.M)
    sin_respaldo = []
    for linea in restante.split("\n"):
        for num in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", linea):
            if num not in permitidos:
                sin_respaldo.append((num, linea.strip()[:110]))
    informe.append(f"4. Números del PDF sin registro (requieren revisión manual): {len(sin_respaldo)}")
    for num, ctx in sin_respaldo:
        informe.append(f"   [{num}] {ctx}")
    salida = "\n".join(informe)
    (BASE / "documento/verificacion_cifras.txt").write_text(salida, encoding="utf-8")
    print(salida)
    ok = reproducible and not discrepancias and not ausentes
    print("\nRESULTADO:", "TODAS LAS CIFRAS REGISTRADAS COINCIDEN" if ok else "HAY PROBLEMAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
