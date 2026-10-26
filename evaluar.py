#!/usr/bin/env python3
"""
Entrena y evalúa el prototipo. Todas las cifras del documento salen de aquí
(resultados/metricas.json). Semilla fija: 2026.

Protocolo:
1. Partición por plantilla de redacción (fijada en el generador): 12 plantillas
   de entrenamiento, 4 de prueba (una por registro).
2. Hiperparámetros y umbral de confianza: validación cruzada agrupada por
   plantilla (GroupKFold, 4 pliegues) DENTRO del entrenamiento. El conjunto de
   prueba y los casos externos no se usan para ninguna elección.
3. Evaluación en: (a) prueba por plantilla, (b) casos externos redactados
   aparte, (c) partición aleatoria (solo para mostrar el efecto de inflado).
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)
from sklearn.model_selection import GroupKFold, train_test_split

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from mantenimiento_ia import (AgenteMantenimiento, ClasificadorPalabrasClave,
                              LISTA_CATEGORIAS, PRIORIDADES, crear_naive_bayes,
                              crear_regresion_logistica, detectar_senales,
                              es_critico, politica_prioridad)
from mantenimiento_ia.conocimiento import NIVEL, SENALES
from mantenimiento_ia.reglas import MotorReglas

SEMILLA = 2026
RES = BASE / "resultados"
FIG = RES / "figuras"
GRID_ALPHA = [0.05, 0.1, 0.3, 0.5, 1.0]
GRID_C = [1.0, 2.0, 5.0, 10.0, 20.0]
GRID_UMBRAL = [round(x, 2) for x in np.arange(0.20, 1.00, 0.01)]
ERROR_MAX_ACEPTADOS = 0.10   # criterio fijado antes de ejecutar
AZUL, VERDE, GRIS = "#1B2A41", "#1F6F78", "#9AA5B1"


# ---------------------------------------------------------------------------
def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cargar():
    d = pd.read_csv(BASE / "datos/reportes_simulados.csv", keep_default_na=False)
    for c in ("texto_vago", "reincidencia_ref", "escalamiento_ref", "critico_ref"):
        d[c] = d[c].astype(str) == "True"
    hist = pd.read_csv(BASE / "datos/historial_activos_simulado.csv")
    historial = {}
    for a, f in zip(hist.activo_id, hist.fecha):
        historial.setdefault(a, []).append(datetime.strptime(f, "%Y-%m-%d").date())
    ext = json.loads((BASE / "datos/casos_externos_redactados.json").read_text(encoding="utf-8"))["casos"]
    filas = []
    for c in ext:
        f = {s: s in c["senales_ref"] for s in SENALES}
        ref = politica_prioridad(f, reincidencia=False, estetico_confirmado=f["estetico"])
        filas.append({"id": c["id"], "fecha": "2026-10-20", "zona": c["zona"], "texto": c["texto"],
                      "foto_calidad": "legible", "categoria_declarada": "", "activo_id": "",
                      "duplicado_de": "", "categoria_ref": c["categoria_ref"],
                      "senales_ref": "|".join(sorted(c["senales_ref"])), "reincidencia_ref": False,
                      "prioridad_ref": ref["prioridad"], "escalamiento_ref": ref["escalamiento"],
                      "critico_ref": es_critico(ref["prioridad"], ref["escalamiento"])})
    return d, historial, pd.DataFrame(filas)


def metricas_clasif(y, p):
    pr, rc, f1, _ = precision_recall_fscore_support(y, p, labels=LISTA_CATEGORIAS, average="macro", zero_division=0)
    return {"exactitud": float(accuracy_score(y, p)), "precision_macro": float(pr),
            "recall_macro": float(rc), "f1_macro": float(f1), "n": int(len(y))}


def por_clase(y, p):
    pr, rc, f1, sop = precision_recall_fscore_support(y, p, labels=LISTA_CATEGORIAS, zero_division=0)
    return {c: {"precision": float(a), "recall": float(b), "f1": float(e), "soporte": int(s)}
            for c, a, b, e, s in zip(LISTA_CATEGORIAS, pr, rc, f1, sop)}


def cv_agrupada(fabrica, X, y, grupos, k=4):
    gkf = GroupKFold(n_splits=k)
    f1s = []
    for tr, va in gkf.split(X, y, grupos):
        m = fabrica().fit(X[tr], y[tr])
        f1s.append(metricas_clasif(y[va], m.predict(X[va]))["f1_macro"])
    return float(np.mean(f1s)), float(np.std(f1s))


def proba_oof(fabrica, X, y, grupos, k=4):
    gkf = GroupKFold(n_splits=k)
    proba = np.zeros((len(X), len(LISTA_CATEGORIAS)))
    for tr, va in gkf.split(X, y, grupos):
        m = fabrica().fit(X[tr], y[tr])
        orden = [list(m.classes_).index(c) for c in LISTA_CATEGORIAS]
        proba[va] = m.predict_proba(X[va])[:, orden]
    return proba


def elegir_umbral(proba, y):
    pred = np.array(LISTA_CATEGORIAS)[proba.argmax(1)]
    conf = proba.max(1)
    curva = []
    for t in GRID_UMBRAL:
        acept = conf >= t
        err = float((pred[acept] != y[acept]).mean()) if acept.any() else 0.0
        curva.append({"umbral": t, "cobertura": float(acept.mean()), "error_aceptados": err})
    validos = [c for c in curva if c["error_aceptados"] <= ERROR_MAX_ACEPTADOS]
    elegido = min(validos, key=lambda c: c["umbral"]) if validos else curva[-1]
    return elegido, curva


# ---------------------------------------------------------------------------
def evaluar_senales(df):
    out = {}
    det = [detectar_senales(t)["flags"] for t in df.texto]
    for s in SENALES:
        y = np.array([s in str(r).split("|") for r in df.senales_ref])
        p = np.array([d[s] for d in det])
        tp, fp, fn = int((y & p).sum()), int((~y & p).sum()), int((y & ~p).sum())
        out[s] = {"soporte": int(y.sum()), "vp": tp, "fp": fp, "fn": fn,
                  "precision": tp / (tp + fp) if tp + fp else None,
                  "recall": tp / (tp + fn) if tp + fn else None}
    return out


def metricas_prioridad(ref_p, ref_esc, pred_p, pred_esc, pred_rev):
    ref_p, pred_p = np.array(ref_p), np.array(pred_p)
    ref_esc, pred_esc, pred_rev = np.array(ref_esc, bool), np.array(pred_esc, bool), np.array(pred_rev, bool)
    crit_ref = np.array([es_critico(a, b) for a, b in zip(ref_p, ref_esc)])
    crit_pred = np.array([es_critico(a, b) for a, b in zip(pred_p, pred_esc)])
    niv_ref = np.array([NIVEL[x] for x in ref_p]); niv_pred = np.array([NIVEL[x] for x in pred_p])
    n_crit, n_no = int(crit_ref.sum()), int((~crit_ref).sum())
    fn = int((crit_ref & ~crit_pred).sum())
    fp = int((~crit_ref & crit_pred).sum())
    return {
        "n": int(len(ref_p)), "n_criticos": n_crit,
        "exactitud_prioridad": float((ref_p == pred_p).mean()),
        "recall_criticos": float(crit_pred[crit_ref].mean()) if n_crit else None,
        "falsos_negativos_criticos": fn,
        "fn_criticos_sin_revision": int((crit_ref & ~crit_pred & ~pred_rev).sum()),
        "falsas_alarmas": fp,
        "tasa_falsas_alarmas": fp / n_no if n_no else None,
        "proporcion_revision_humana": float(pred_rev.mean()),
        "subestimacion": float((niv_pred < niv_ref).mean()),
        "sobreestimacion": float((niv_pred > niv_ref).mean()),
        "matriz": confusion_matrix(ref_p, pred_p, labels=PRIORIDADES).tolist(),
    }


def correr_agente(df, modelo, umbral, historial, textos_ref):
    """Procesa los reportes en orden cronológico con el ciclo completo del agente."""
    ag = AgenteMantenimiento(modelo, umbral, historial, textos_ref)
    filas = []
    for r in df.sort_values(["fecha", "id"]).to_dict("records"):
        out = ag.procesar(r)
        d, i = out["decision"], out["interpretacion"]
        # Retroalimentación R5 simulada: el responsable confirma solo si la
        # referencia indica un problema exclusivamente estético.
        senales_ref = set(str(r["senales_ref"]).split("|")) - {""}
        ref_estetico = "estetico" in senales_ref and not (senales_ref & {"agua", "riesgo_electrico", "desprendimiento", "estructural", "circulacion", "sin_servicio"})
        p_conf = d["prioridad"]
        if d["candidato_estetico"] and ref_estetico:
            p_conf = politica_prioridad(d["senales_efectivas"], d["reincidencia"], estetico_confirmado=True)["prioridad"]
        filas.append({"id": r["id"], "categoria_pred": i["categoria"], "confianza": i["confianza"],
                      "prioridad_pred": d["prioridad"], "prioridad_tras_R5": p_conf,
                      "escalamiento_pred": d["escalamiento"], "revision_pred": d["revision_humana"],
                      "reglas": " ".join(d["reglas"]), "acciones": " ".join(d["acciones"]),
                      "caso_id": out["accion"]["caso_id"], "vinculado": out["accion"]["vinculado"],
                      "senales_detectadas": "|".join(s for s, v in i["senales_texto"].items() if v),
                      "palabras_clave": "; ".join(f"{p} ({v})" for p, v in i["palabras_clave"])})
    res = df.merge(pd.DataFrame(filas), on="id")
    return res, ag


def correr_motor_con_categoria(df, categorias, confianzas, umbral, historial):
    motor = MotorReglas(umbral, historial)
    pp, pe, pr = [], [], []
    for r, c, conf in zip(df.to_dict("records"), categorias, confianzas):
        rep = dict(r); rep["fecha"] = datetime.strptime(str(r["fecha"]), "%Y-%m-%d").date()
        d = motor.decidir(rep, c, conf, detectar_senales(r["texto"])["flags"])
        pp.append(d["prioridad"]); pe.append(d["escalamiento"]); pr.append(d["revision_humana"])
    return pp, pe, pr


TABLA_FIJA = {"ELECTRICO": ("Alta", True), "HUMEDAD": ("Media", False), "PUERTAS": ("Media", False),
              "PISOS": ("Media", False), "MUROS": ("Media", False), "SANITARIO": ("Media", False),
              "MOBILIARIO": ("Baja", False), "NO_CLASIFICADO": ("Media", False)}


def comparar_sistemas(df, res_agente, kw, umbral, historial):
    out = {}
    n = len(df)
    out["B0_todo_media_orden_llegada"] = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref,
                                                           ["Media"] * n, [False] * n, [False] * n)
    cat_kw = kw.predict(df.texto.values)
    tabla = [TABLA_FIJA[c] for c in cat_kw]
    out["B1_palabras_clave_tabla_fija"] = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref,
                                                            [t[0] for t in tabla], [t[1] for t in tabla], [False] * n)
    conf_kw = [0.0 if c == "NO_CLASIFICADO" else 1.0 for c in cat_kw]
    pp, pe, pr = correr_motor_con_categoria(df, cat_kw, conf_kw, umbral, historial)
    out["A1_reglas_con_palabras_clave"] = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref, pp, pe, pr)
    pp, pe, pr = correr_motor_con_categoria(df, df.categoria_ref.values, [1.0] * n, umbral, historial)
    out["A2_reglas_con_categoria_real"] = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref, pp, pe, pr)
    r = res_agente.set_index("id").loc[df.id]
    out["PROTOTIPO_NB_mas_reglas"] = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref, r.prioridad_pred,
                                                       r.escalamiento_pred, r.revision_pred)
    tras = metricas_prioridad(df.prioridad_ref, df.escalamiento_ref, r.prioridad_tras_R5,
                              r.escalamiento_pred, r.revision_pred)
    out["PROTOTIPO_tras_confirmacion_R5"] = tras
    return out


def evaluar_duplicados(res):
    ids = set(res.id)
    caso_de = dict(zip(res.id, res.caso_id))
    dup = res[(res.duplicado_de != "") & res.duplicado_de.isin(ids)]
    correctos = int(sum(caso_de[r.id] == caso_de[r.duplicado_de] and r.vinculado for r in dup.itertuples()))
    no_dup = res[res.duplicado_de == ""]
    falsos = int(no_dup.vinculado.sum())
    vinculados = int(res.vinculado.sum())
    return {"duplicados_reales": int(len(dup)), "vinculados_correctamente": correctos,
            "recall_duplicados": correctos / len(dup) if len(dup) else None,
            "vinculaciones_totales": vinculados, "vinculaciones_incorrectas": falsos,
            "precision_vinculacion": correctos / vinculados if vinculados else None}


# ---------------------------------------------------------------------------
def ejecutar_pruebas(modelo, umbral, textos_ref):
    spec_path = BASE / "pruebas_definidas.json"
    huella = sha256(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    resultados = []
    for p in spec["pruebas"]:
        hist = {}
        for a, f in p.get("historial", []):
            hist.setdefault(a, []).append(datetime.strptime(f, "%Y-%m-%d").date())
        ag = AgenteMantenimiento(modelo, umbral, hist, textos_ref)
        salidas = [ag.procesar(r) for r in p["reportes"]]
        o = salidas[0]; d = o["decision"]
        obtenido = {"categoria": d["categoria"], "confianza": round(o["interpretacion"]["confianza"], 3),
                    "prioridad": d["prioridad"], "escalamiento": d["escalamiento"],
                    "revision_humana": d["revision_humana"], "reglas": d["reglas"], "acciones": d["acciones"]}
        if len(salidas) > 1:
            obtenido["segundo_vinculado"] = salidas[1]["accion"]["vinculado"]
        if "retroalimentacion" in p:
            rf = p["retroalimentacion"]
            caso = ag.retroalimentar(o["accion"]["caso_id"], rf["autor"], rf["fecha"],
                                     solo_estetico=rf.get("solo_estetico"), estado=rf.get("estado"))
            obtenido["prioridad_tras_retroalimentacion"] = caso.prioridad
            panel = ag.panel(spec["fecha_referencia_panel"])
            fila = next(f for f in panel if f["caso"] == caso.id) if any(f["caso"] == caso.id for f in panel) else {}
            obtenido["panel_dias_abierto"] = fila.get("dias_abierto")
            obtenido["panel_aviso_antiguedad"] = fila.get("aviso_antiguedad")
        esp = p["esperado"]; fallas = []
        for k, v in esp.items():
            if k == "categoria":
                ok = obtenido["categoria"] in v
            elif k == "reglas_incluye":
                ok = all(x in obtenido["reglas"] for x in v)
            elif k == "reglas_excluye":
                ok = not any(x in obtenido["reglas"] for x in v)
            elif k == "acciones_incluye":
                ok = all(x in obtenido["acciones"] for x in v)
            else:
                ok = obtenido.get(k) == v
            if not ok:
                fallas.append(k)
        resultados.append({"id": p["id"], "regla": p["regla"], "descripcion": p["descripcion"],
                           "texto": p["reportes"][-1]["texto"] if len(p["reportes"]) > 1 else p["reportes"][0]["texto"],
                           "esperado": esp, "obtenido": obtenido, "correcto": not fallas, "fallas": fallas})
    return {"sha256_especificacion": huella, "pruebas": resultados,
            "aprobadas": sum(r["correcto"] for r in resultados), "total": len(resultados)}


# ---------------------------------------------------------------------------
def figuras(m, cm_test, cm_ext, curva, umbral):
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    etiquetas = ["Humedad", "Eléctrico", "Puertas", "Pisos", "Muros", "Sanitario", "Mobiliario"]
    for nombre, cm, titulo in (("matriz_nb_prueba", cm_test, "Prueba por plantilla"),
                               ("matriz_nb_externos", cm_ext, "Casos externos")):
        fig, ax = plt.subplots(figsize=(5.2, 4.4))
        cm = np.array(cm)
        ax.imshow(cm, cmap="BuGn")
        ax.set_xticks(range(7)); ax.set_xticklabels(etiquetas, rotation=40, ha="right")
        ax.set_yticks(range(7)); ax.set_yticklabels(etiquetas)
        ax.set_xlabel("Categoría predicha (Naive Bayes)"); ax.set_ylabel("Categoría de referencia")
        lim = cm.max() / 2
        for a in range(7):
            for b in range(7):
                ax.text(b, a, cm[a, b], ha="center", va="center", fontsize=8,
                        color="white" if cm[a, b] > lim else AZUL)
        ax.set_title(f"Matriz de confusión · {titulo}", color=AZUL, fontsize=10)
        fig.tight_layout(); fig.savefig(FIG / f"{nombre}.png", dpi=200); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    u = [c["umbral"] for c in curva]
    ax.plot(u, [c["cobertura"] for c in curva], color=VERDE, label="Casos aceptados sin revisión")
    ax.plot(u, [c["error_aceptados"] for c in curva], color=AZUL, label="Error entre aceptados")
    ax.axhline(ERROR_MAX_ACEPTADOS, color=GRIS, ls="--", lw=1, label="Error máximo permitido (10 %)")
    ax.axvline(umbral, color="#B4483C", ls=":", lw=1.2, label=f"Umbral elegido ({umbral:.2f})")
    ax.set_xlabel("Umbral de confianza"); ax.set_ylabel("Proporción"); ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=7, frameon=False, loc="center left"); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Selección del umbral (validación cruzada agrupada, solo entrenamiento)", color=AZUL, fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "umbral_validacion.png", dpi=200); plt.close(fig)
    # comparación de sistemas (prueba y externos)
    sistemas = [("B0_todo_media_orden_llegada", "B0\nTodo Media"), ("B1_palabras_clave_tabla_fija", "B1 Palabras\nclave + tabla"),
                ("A1_reglas_con_palabras_clave", "A1 Reglas +\npalabras clave"), ("PROTOTIPO_NB_mas_reglas", "Prototipo\nNB + reglas")]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, conj, tit in ((axes[0], "prueba", "Prueba por plantilla"), (axes[1], "externos", "Casos externos")):
        x = np.arange(len(sistemas)); w = 0.38
        rec = [m["prioridad"][conj][k]["recall_criticos"] for k, _ in sistemas]
        exa = [m["prioridad"][conj][k]["exactitud_prioridad"] for k, _ in sistemas]
        b1 = ax.bar(x - w / 2, rec, w, color=AZUL, label="Recall de casos críticos")
        b2 = ax.bar(x + w / 2, exa, w, color=VERDE, label="Exactitud de prioridad")
        for barra in list(b1) + list(b2):
            ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height() + 0.015, f"{barra.get_height():.2f}",
                    ha="center", va="bottom", fontsize=6.5, color=AZUL)
        ax.set_xticks(x); ax.set_xticklabels([s for _, s in sistemas], fontsize=7)
        ax.set_title(tit, color=AZUL, fontsize=9); ax.set_ylim(0, 1.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False, loc="upper left", ncol=2)
    fig.tight_layout(); fig.savefig(FIG / "comparacion_sistemas.png", dpi=200); plt.close(fig)


# ---------------------------------------------------------------------------
def ejecutar_todo(guardar=True):
    np.random.seed(SEMILLA)
    d, historial, ext = cargar()
    tr, te = d[d.grupo == "entrenamiento"].reset_index(drop=True), d[d.grupo == "prueba"].reset_index(drop=True)
    Xtr, ytr, gtr = tr.texto.values, tr.categoria_ref.values, tr.plantilla.values
    m = {"semilla": SEMILLA,
         "huellas_sha256": {"pruebas_definidas.json": sha256(BASE / "pruebas_definidas.json"),
                            "casos_externos_redactados.json": sha256(BASE / "datos/casos_externos_redactados.json"),
                            "reportes_simulados.csv": sha256(BASE / "datos/reportes_simulados.csv")}}
    m["datos"] = {
        "n_total": int(len(d)), "n_entrenamiento": int(len(tr)), "n_prueba": int(len(te)), "n_externos": int(len(ext)),
        "plantillas_entrenamiento": sorted(tr.plantilla.unique().tolist()),
        "plantillas_prueba": sorted(te.plantilla.unique().tolist()),
        "por_categoria": {c: int(v) for c, v in d.categoria_ref.value_counts().sort_index().items()},
        "por_prioridad_ref": {p: int((d.prioridad_ref == p).sum()) for p in PRIORIDADES},
        "por_prioridad_ref_prueba": {p: int((te.prioridad_ref == p).sum()) for p in PRIORIDADES},
        "por_prioridad_ref_externos": {p: int((ext.prioridad_ref == p).sum()) for p in PRIORIDADES},
        "criticos_total": int(d.critico_ref.sum()), "criticos_prueba": int(te.critico_ref.sum()),
        "criticos_externos": int(ext.critico_ref.sum()),
        "zona_vacia": int((d.zona == "").sum()), "activo_vacio": int((d.activo_id == "").sum()),
        "textos_vagos": int(d.texto_vago.sum()), "duplicados": int((d.duplicado_de != "").sum()),
        "reincidencia_ref": int(d.reincidencia_ref.sum()),
        "foto": {k: int(v) for k, v in d.foto_calidad.value_counts().items()},
        "categoria_declarada_vacia": int((d.categoria_declarada == "").sum()),
        "categoria_declarada_incorrecta": int(((d.categoria_declarada != "") & (d.categoria_declarada != d.categoria_ref)).sum()),
        "historial_registros": int(sum(len(v) for v in historial.values())),
        "palabras_promedio": float(d.texto.str.split().str.len().mean()),
    }
    # --- selección de hiperparámetros (solo entrenamiento) ---
    sel = {"naive_bayes": {}, "regresion_logistica": {}}
    for a in GRID_ALPHA:
        sel["naive_bayes"][str(a)] = cv_agrupada(lambda: crear_naive_bayes(a), Xtr, ytr, gtr)
    for c in GRID_C:
        sel["regresion_logistica"][str(c)] = cv_agrupada(lambda: crear_regresion_logistica(c, SEMILLA), Xtr, ytr, gtr)
    alpha = float(max(sel["naive_bayes"], key=lambda k: sel["naive_bayes"][k][0]))
    C = float(max(sel["regresion_logistica"], key=lambda k: sel["regresion_logistica"][k][0]))
    m["seleccion"] = {"alpha_nb": alpha, "C_lr": C,
                      "cv_f1_macro": {k: {kk: {"media": v[0], "desv": v[1]} for kk, v in g.items()} for k, g in sel.items()}}
    # --- umbral (OOF agrupado, solo entrenamiento) ---
    oof = proba_oof(lambda: crear_naive_bayes(alpha), Xtr, ytr, gtr)
    elegido, curva = elegir_umbral(oof, ytr)
    umbral = elegido["umbral"]
    m["umbral"] = {"criterio": f"menor umbral con error <= {ERROR_MAX_ACEPTADOS:.2f} entre los casos aceptados (validación agrupada en entrenamiento)",
                   "valor": umbral, "cobertura_validacion": elegido["cobertura"],
                   "error_aceptados_validacion": elegido["error_aceptados"],
                   "exactitud_oof": float((np.array(LISTA_CATEGORIAS)[oof.argmax(1)] == ytr).mean())}
    # --- modelos finales ---
    nb = crear_naive_bayes(alpha).fit(Xtr, ytr)
    lr = crear_regresion_logistica(C, SEMILLA).fit(Xtr, ytr)
    kw = ClasificadorPalabrasClave()
    m["modelo"] = {"vocabulario_nb": int(len(nb.named_steps["vectorizador"].vocabulary_))}
    cl = {}
    preds = {}
    for nombre, conj in (("prueba", te), ("externos", ext)):
        cl[nombre] = {}
        for mn, mod in (("palabras_clave", kw), ("naive_bayes", nb), ("regresion_logistica", lr)):
            p = mod.predict(conj.texto.values)
            preds[(nombre, mn)] = p
            cl[nombre][mn] = metricas_clasif(conj.categoria_ref.values, p)
        cl[nombre]["no_clasificados_palabras_clave"] = int((preds[(nombre, "palabras_clave")] == "NO_CLASIFICADO").sum())
        cl[nombre]["naive_bayes_por_clase"] = por_clase(conj.categoria_ref.values, preds[(nombre, "naive_bayes")])
    # partición aleatoria (solo para mostrar el efecto de inflado)
    a_tr, a_te = train_test_split(d, test_size=len(te), random_state=SEMILLA, stratify=d.categoria_ref)
    cl["aleatoria"] = {
        "palabras_clave": metricas_clasif(a_te.categoria_ref.values, kw.predict(a_te.texto.values)),
        "naive_bayes": metricas_clasif(a_te.categoria_ref.values, crear_naive_bayes(alpha).fit(a_tr.texto.values, a_tr.categoria_ref.values).predict(a_te.texto.values)),
        "regresion_logistica": metricas_clasif(a_te.categoria_ref.values, crear_regresion_logistica(C, SEMILLA).fit(a_tr.texto.values, a_tr.categoria_ref.values).predict(a_te.texto.values)),
    }
    m["clasificador"] = cl
    cm_te = confusion_matrix(te.categoria_ref, preds[("prueba", "naive_bayes")], labels=LISTA_CATEGORIAS).tolist()
    cm_ex = confusion_matrix(ext.categoria_ref, preds[("externos", "naive_bayes")], labels=LISTA_CATEGORIAS).tolist()
    m["matrices_nb"] = {"prueba": cm_te, "externos": cm_ex, "etiquetas": LISTA_CATEGORIAS}
    # confianza en los aciertos y errores
    conf_te = nb.predict_proba(te.texto.values).max(1); conf_ex = nb.predict_proba(ext.texto.values).max(1)
    err_te = preds[("prueba", "naive_bayes")] != te.categoria_ref.values
    err_ex = preds[("externos", "naive_bayes")] != ext.categoria_ref.values
    m["confianza"] = {
        "prueba_errores": int(err_te.sum()), "prueba_errores_bajo_umbral": int((err_te & (conf_te < umbral)).sum()),
        "externos_errores": int(err_ex.sum()), "externos_errores_bajo_umbral": int((err_ex & (conf_ex < umbral)).sum()),
        "externos_bajo_umbral": int((conf_ex < umbral).sum()), "prueba_bajo_umbral": int((conf_te < umbral).sum()),
    }
    # Análisis EXPLORATORIO posterior (no se usó para elegir el umbral): qué
    # pasaría con otros umbrales en los casos externos.
    m["exploratorio_post_hoc_umbral_externos"] = [
        {"umbral": t, "enviados_a_revision": int((conf_ex < t).sum()),
         "errores_capturados": int((err_ex & (conf_ex < t)).sum()), "errores_totales": int(err_ex.sum())}
        for t in (0.5, 0.7, 0.9, 0.99)]
    # --- señales de riesgo (lexicón) ---
    m["senales"] = {"prueba": evaluar_senales(te), "externos": evaluar_senales(ext)}
    # --- agente completo + reglas ---
    res_te, ag_te = correr_agente(te, nb, umbral, historial, Xtr)
    res_ex, _ = correr_agente(ext, nb, umbral, {}, Xtr)
    m["prioridad"] = {"prueba": comparar_sistemas(te, res_te, kw, umbral, historial),
                      "externos": comparar_sistemas(ext, res_ex, kw, umbral, {})}
    m["reglas_disparadas"] = {
        "prueba": dict(Counter(x for r in res_te.reglas for x in r.split())),
        "externos": dict(Counter(x for r in res_ex.reglas for x in r.split()))}
    m["duplicados_R4_prueba"] = evaluar_duplicados(res_te)
    m["casos_creados_prueba"] = int(len(ag_te.casos))
    # --- pruebas predefinidas ---
    pruebas = ejecutar_pruebas(nb, umbral, Xtr)
    m["pruebas"] = {"aprobadas": pruebas["aprobadas"], "total": pruebas["total"],
                    "sha256_especificacion": pruebas["sha256_especificacion"]}
    if guardar:
        RES.mkdir(exist_ok=True)
        (RES / "metricas.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        (RES / "pruebas_resultados.json").write_text(json.dumps(pruebas, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        res_te.to_csv(RES / "decisiones_prueba.csv", index=False)
        res_ex.to_csv(RES / "decisiones_externos.csv", index=False)
        pd.DataFrame(curva).to_csv(RES / "curva_umbral.csv", index=False)
        figuras(m, cm_te, cm_ex, curva, umbral)
    return m, pruebas, res_te, res_ex, nb


if __name__ == "__main__":
    m, pruebas, *_ = ejecutar_todo()
    print(json.dumps({"umbral": m["umbral"], "clasificador": {k: {kk: (vv["f1_macro"] if isinstance(vv, dict) and "f1_macro" in vv else vv) for kk, vv in v.items() if kk != "naive_bayes_por_clase"} for k, v in m["clasificador"].items()},
                      "pruebas": m["pruebas"]}, ensure_ascii=False, indent=1))
