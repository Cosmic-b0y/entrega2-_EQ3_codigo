"""Prototipo del Equipo 3: clasificación y priorización preliminar de
incidencias de infraestructura (datos simulados, uso académico)."""
from .agente import AgenteMantenimiento
from .clasificador import (ClasificadorPalabrasClave, crear_naive_bayes,
                           crear_regresion_logistica, explicar_naive_bayes)
from .conocimiento import (CATEGORIAS, LISTA_CATEGORIAS, PRIORIDADES, detectar_senales,
                           es_critico, normalizar, politica_prioridad)
from .reglas import MotorReglas
