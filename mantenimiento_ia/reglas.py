"""
Motor de reglas SI-ENTONCES (sistema basado en conocimiento).

Combina la categoría sugerida por el clasificador, su confianza, las señales de
riesgo detectadas en el texto, la calidad de la foto y el historial del activo
para proponer una PRIORIDAD PRELIMINAR, el escalamiento y la revisión humana.
Ninguna salida es un dictamen técnico.
"""
from datetime import date, timedelta

from .conocimiento import AREA_COMPETENTE, PARAMETROS, normalizar, politica_prioridad

FOTO_ILEGIBLE = {"borrosa", "oscura"}


def contar_incidencias_previas(historial, activo_id, fecha: date,
                               ventana: int = PARAMETROS["ventana_reincidencia_dias"]) -> int:
    """historial: dict {activo_id: [fechas]}"""
    if not activo_id or historial is None:
        return 0
    desde = fecha - timedelta(days=ventana)
    return sum(1 for f in historial.get(activo_id, []) if desde <= f < fecha)


class MotorReglas:
    def __init__(self, umbral_confianza: float, historial: dict | None = None):
        self.umbral = umbral_confianza
        self.historial = historial or {}

    def senales_efectivas(self, senales_texto: dict, categoria: str) -> dict:
        """R1 conservadora: la categoría sugerida aporta contexto a las señales."""
        f = dict(senales_texto)
        if categoria == "ELECTRICO":
            f["electrico"] = True
        if categoria == "HUMEDAD" and f["electrico"]:
            f["agua"] = True
        return f

    def decidir(self, reporte: dict, categoria: str, confianza: float,
                senales_texto: dict) -> dict:
        f = self.senales_efectivas(senales_texto, categoria)
        fecha = reporte["fecha"]
        previas = contar_incidencias_previas(self.historial, reporte.get("activo_id"), fecha)
        reincidencia = previas >= PARAMETROS["min_incidencias_reincidencia"]
        pol = politica_prioridad(f, reincidencia=reincidencia, estetico_confirmado=False)

        reglas = list(pol["reglas"])
        acciones = ["crear_caso"]
        motivos_revision = []

        if pol["escalamiento"]:
            motivos_revision.append("señal de riesgo que exige valoración competente")
            acciones.append("alertar_area_competente")
            if "R2" in reglas:
                acciones.append("solicitar_inspeccion_especializada")
        # R3: incertidumbre del clasificador y calidad de la evidencia
        if confianza < self.umbral:
            reglas.append("R3")
            motivos_revision.append(f"confianza {confianza:.2f} menor al umbral {self.umbral:.2f}")
        foto = reporte.get("foto_calidad", "legible")
        if foto in FOTO_ILEGIBLE:
            if "R3" not in reglas:
                reglas.append("R3")
            acciones.append("solicitar_nueva_foto")
        elif foto == "sin_foto":
            acciones.append("solicitar_foto")
        # R7: datos mínimos
        n_palabras = len(normalizar(reporte.get("texto", "")).split())
        if not reporte.get("zona"):
            reglas.append("R7"); acciones.append("solicitar_zona")
            motivos_revision.append("falta la zona del reporte")
        elif n_palabras < PARAMETROS["min_palabras_descripcion"]:
            reglas.append("R7"); acciones.append("solicitar_descripcion")
            motivos_revision.append("descripción insuficiente")
        # R8: conflicto entre categoría declarada y sugerida
        declarada = reporte.get("categoria_declarada") or ""
        if declarada and declarada != categoria:
            reglas.append("R8")
            motivos_revision.append(f"categoría declarada ({declarada}) distinta de la sugerida ({categoria})")
        # R5 (fase de retroalimentación): solo se marca como candidato
        if pol["candidato_estetico"]:
            acciones.append("confirmar_si_es_solo_estetico")

        return {
            "categoria": categoria,
            "area": AREA_COMPETENTE.get(categoria, "Por asignar"),
            "prioridad": pol["prioridad"],
            "escalamiento": pol["escalamiento"],
            "revision_humana": bool(motivos_revision),
            "motivos_revision": motivos_revision,
            "reglas": reglas,
            "motivos_prioridad": pol["motivos"] or ["sin señales de riesgo detectadas: prioridad base"],
            "acciones": acciones,
            "candidato_estetico": pol["candidato_estetico"],
            "reincidencia": reincidencia,
            "incidencias_previas": previas,
            "senales_efectivas": f,
        }
