"""
Agente de mantenimiento: ciclo percibir -> interpretar -> decidir -> actuar ->
retroalimentar (modelo REAS/PAMA de la primera entrega).

El agente NO repara, NO cierra casos por sí solo y NO reentrena el modelo:
registra sugerencias y deja la decisión final al personal responsable.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .clasificador import explicar_naive_bayes
from .conocimiento import (NIVEL, PARAMETROS, PRIORIDADES, detectar_senales,
                           normalizar, politica_prioridad)
from .reglas import MotorReglas


def _a_fecha(valor) -> date:
    if isinstance(valor, date):
        return valor
    return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()


@dataclass
class Caso:
    id: str
    fecha_apertura: date
    zona: str
    activo_id: str
    categoria: str
    prioridad: str
    escalamiento: bool
    revision_humana: bool
    reportes: list = field(default_factory=list)
    estado: str = "pendiente_revision"   # pendiente_revision | validado | atendido | cerrado
    bitacora: list = field(default_factory=list)
    texto_base: str = ""


class AgenteMantenimiento:
    def __init__(self, clasificador, umbral_confianza: float, historial: dict | None = None,
                 textos_referencia=None):
        self.clasificador = clasificador
        self.motor = MotorReglas(umbral_confianza, historial)
        self.casos: dict[str, Caso] = {}
        self.correcciones: list[dict] = []
        self._contador = 0
        # Vectorizador para comparar reportes (R4); se ajusta con textos de entrenamiento
        self.vec_sim = TfidfVectorizer(preprocessor=normalizar)
        self.vec_sim.fit(textos_referencia if textos_referencia is not None else ["reporte"])

    # 1. PERCIBIR -----------------------------------------------------------
    def percibir(self, reporte: dict) -> dict:
        p = dict(reporte)
        p["fecha"] = _a_fecha(reporte.get("fecha", date.today()))
        p["texto"] = (reporte.get("texto") or "").strip()
        p["zona"] = (reporte.get("zona") or "").strip()
        p["activo_id"] = (reporte.get("activo_id") or "").strip()
        p["categoria_declarada"] = (reporte.get("categoria_declarada") or "").strip()
        p["foto_calidad"] = reporte.get("foto_calidad") or "sin_foto"
        p["campos_faltantes"] = [c for c in ("texto", "zona") if not p[c]]
        return p

    # 2. INTERPRETAR --------------------------------------------------------
    def interpretar(self, percepcion: dict) -> dict:
        texto = percepcion["texto"]
        proba = self.clasificador.predict_proba([texto])[0]
        clases = self.clasificador.classes_
        orden = np.argsort(proba)[::-1]
        categoria = str(clases[orden[0]])
        senales = detectar_senales(texto)
        return {
            "categoria": categoria,
            "confianza": float(proba[orden[0]]),
            "alternativas": [(str(clases[i]), round(float(proba[i]), 3)) for i in orden[:3]],
            "palabras_clave": explicar_naive_bayes(self.clasificador, texto, categoria),
            "senales_texto": senales["flags"],
            "evidencia": senales["evidencia"],
        }

    # 3. DECIDIR ------------------------------------------------------------
    def decidir(self, percepcion: dict, interpretacion: dict) -> dict:
        return self.motor.decidir(percepcion, interpretacion["categoria"],
                                  interpretacion["confianza"], interpretacion["senales_texto"])

    # 4. ACTUAR -------------------------------------------------------------
    def _buscar_duplicado(self, percepcion: dict, categoria: str):
        ventana = PARAMETROS["ventana_duplicado_dias"]
        candidatos = [c for c in self.casos.values()
                      if c.estado != "cerrado" and c.categoria == categoria
                      and 0 <= (percepcion["fecha"] - c.fecha_apertura).days <= ventana]
        if not candidatos:
            return None
        if percepcion["activo_id"]:
            for c in candidatos:
                if c.activo_id == percepcion["activo_id"]:
                    return c
        mismos = [c for c in candidatos if percepcion["zona"] and c.zona == percepcion["zona"]
                  and not (percepcion["activo_id"] and c.activo_id)]
        if not mismos:
            return None
        v = self.vec_sim.transform([percepcion["texto"]] + [c.texto_base for c in mismos])
        sims = cosine_similarity(v[0], v[1:])[0]
        j = int(np.argmax(sims))
        return mismos[j] if sims[j] >= PARAMETROS["similitud_duplicado"] else None

    def actuar(self, percepcion: dict, interpretacion: dict, decision: dict) -> dict:
        existente = self._buscar_duplicado(percepcion, decision["categoria"])
        registro = {"reporte_id": percepcion.get("id"), "fecha": str(percepcion["fecha"]),
                    "texto": percepcion["texto"], "decision": decision}
        if existente is not None:  # R4: se vincula sin perder evidencia
            existente.reportes.append(registro)
            existente.bitacora.append((str(percepcion["fecha"]), "agente", "R4: reporte vinculado"))
            if NIVEL[decision["prioridad"]] > NIVEL[existente.prioridad]:
                existente.prioridad = decision["prioridad"]
            existente.escalamiento = existente.escalamiento or decision["escalamiento"]
            return {"caso_id": existente.id, "vinculado": True, "acciones": ["vincular_a_caso_abierto"]}
        self._contador += 1
        caso = Caso(id=f"C{self._contador:04d}", fecha_apertura=percepcion["fecha"],
                    zona=percepcion["zona"], activo_id=percepcion["activo_id"],
                    categoria=decision["categoria"], prioridad=decision["prioridad"],
                    escalamiento=decision["escalamiento"],
                    revision_humana=decision["revision_humana"],
                    reportes=[registro], texto_base=percepcion["texto"])
        caso.bitacora.append((str(percepcion["fecha"]), "agente",
                              "caso creado: " + ", ".join(decision["acciones"])))
        self.casos[caso.id] = caso
        return {"caso_id": caso.id, "vinculado": False, "acciones": decision["acciones"]}

    # 5. RETROALIMENTAR -----------------------------------------------------
    def retroalimentar(self, caso_id: str, autor: str, fecha, categoria: str | None = None,
                       prioridad: str | None = None, solo_estetico: bool | None = None,
                       estado: str | None = None, nota: str = "") -> Caso:
        """Registra la corrección humana con autor y fecha. No reentrena el modelo:
        las correcciones quedan disponibles para una evaluación posterior."""
        caso = self.casos[caso_id]
        antes = {"categoria": caso.categoria, "prioridad": caso.prioridad, "estado": caso.estado}
        if categoria:
            caso.categoria = categoria
        if solo_estetico:  # R5: el responsable confirma que es solo estético
            ultima = caso.reportes[-1]["decision"]
            pol = politica_prioridad(ultima["senales_efectivas"], ultima["reincidencia"],
                                     estetico_confirmado=True)
            if "R5" in pol["reglas"]:
                caso.prioridad = pol["prioridad"]
        if prioridad:
            caso.prioridad = prioridad
        caso.estado = estado or "validado"
        caso.revision_humana = False
        despues = {"categoria": caso.categoria, "prioridad": caso.prioridad, "estado": caso.estado}
        entrada = {"caso_id": caso_id, "autor": autor, "fecha": str(_a_fecha(fecha)),
                   "antes": antes, "despues": despues, "nota": nota}
        self.correcciones.append(entrada)
        caso.bitacora.append((entrada["fecha"], autor, f"corrección: {antes} -> {despues} {nota}".strip()))
        return caso

    # Panel de mantenimiento (R6) -------------------------------------------
    def panel(self, fecha_actual) -> list[dict]:
        hoy = _a_fecha(fecha_actual)
        filas = []
        for c in self.casos.values():
            if c.estado in ("cerrado", "atendido"):
                continue
            dias = (hoy - c.fecha_apertura).days
            filas.append({"caso": c.id, "zona": c.zona, "categoria": c.categoria,
                          "prioridad": c.prioridad, "estado": c.estado, "dias_abierto": dias,
                          "aviso_antiguedad": c.estado == "validado" and dias >= PARAMETROS["antiguedad_aviso_dias"],
                          "reportes_vinculados": len(c.reportes)})
        filas.sort(key=lambda r: (-NIVEL[r["prioridad"]], -r["dias_abierto"]))
        return filas

    # Ciclo completo --------------------------------------------------------
    def procesar(self, reporte: dict) -> dict:
        p = self.percibir(reporte)
        i = self.interpretar(p)
        d = self.decidir(p, i)
        a = self.actuar(p, i, d)
        return {"percepcion": p, "interpretacion": i, "decision": d, "accion": a}
