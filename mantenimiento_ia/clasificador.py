"""
Componente de aprendizaje automático: clasificación de la categoría de la
incidencia a partir de la descripción escrita por el reportante.

- Técnica principal: Naive Bayes multinomial (unigramas + bigramas).
- Comparación: regresión logística con TF-IDF.
- Línea base sin aprendizaje: conteo de palabras clave por categoría.
"""
import re

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from .conocimiento import LISTA_CATEGORIAS, normalizar

# Palabras vacías (ya normalizadas, sin acentos). "no" y "sin" se conservan
# porque cambian el sentido de la descripción.
STOPWORDS = [
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
    "en", "y", "o", "que", "se", "por", "con", "para", "es", "esta", "estan",
    "lo", "le", "les", "su", "sus", "ya", "me", "mi", "nos", "hay", "muy",
    "como", "pero", "mas", "este", "esto", "eso", "ese", "fue", "son", "tiene",
    "tienen", "favor", "gracias", "hola", "buen", "dia", "reporta", "reporte",
]
TOKEN = r"(?u)\b[a-z][a-z0-9]+\b"


def crear_naive_bayes(alpha: float = 0.5) -> Pipeline:
    return Pipeline([
        ("vectorizador", CountVectorizer(preprocessor=normalizar, token_pattern=TOKEN,
                                         stop_words=STOPWORDS, ngram_range=(1, 2))),
        ("modelo", MultinomialNB(alpha=alpha)),
    ])


def crear_regresion_logistica(C: float = 5.0, semilla: int = 2026) -> Pipeline:
    return Pipeline([
        ("vectorizador", TfidfVectorizer(preprocessor=normalizar, token_pattern=TOKEN,
                                         stop_words=STOPWORDS, ngram_range=(1, 2),
                                         sublinear_tf=True)),
        ("modelo", LogisticRegression(C=C, max_iter=5000, random_state=semilla)),
    ])


class ClasificadorPalabrasClave:
    """Línea base sin aprendizaje: cuenta raíces de palabras por categoría.
    Si no encuentra ninguna, devuelve 'NO_CLASIFICADO' (se cuenta como error)."""

    RAICES = {
        "HUMEDAD": ["humedad", "humed", "filtr", "gotera", "gotea", "moho", "salitre", "charco", "encharc", "mojad"],
        "ELECTRICO": ["lampara", "luminaria", "foco", "contacto", "enchufe", "apagador", "cable", "tablero", "luz", "corriente", "electric"],
        "PUERTAS": ["puerta", "ventana", "chapa", "cerradura", "cerrojo", "bisagra", "vidrio", "cristal"],
        "PISOS": ["piso", "loseta", "mosaico", "escalon", "escalera", "rampa"],
        "MUROS": ["pared", "muro", "pintura", "grieta", "fisura", "plafon", "aplanado", "techo", "fachada"],
        "SANITARIO": ["bano", "inodoro", "mingitorio", "lavabo", "tuberia", "tubo", "drenaje", "sanitario", "tinaco"],
        "MOBILIARIO": ["butaca", "banca", "mesa", "silla", "pizarron", "pintarron", "anaquel", "repisa", "locker", "casillero", "librero", "soporte"],
    }

    def fit(self, X=None, y=None):
        return self

    def predecir_uno(self, texto: str) -> str:
        tokens = normalizar(texto).split()
        puntajes = {c: sum(1 for tok in tokens for r in raices if tok.startswith(r))
                    for c, raices in self.RAICES.items()}
        mejor = max(puntajes, key=puntajes.get)
        return mejor if puntajes[mejor] > 0 else "NO_CLASIFICADO"

    def predict(self, X):
        return np.array([self.predecir_uno(t) for t in X])


def explicar_naive_bayes(pipe: Pipeline, texto: str, clase: str, k: int = 3):
    """Palabras del reporte que más favorecen la clase predicha frente al
    promedio de las demás clases (diferencia de log-probabilidades)."""
    vec = pipe.named_steps["vectorizador"]
    nb = pipe.named_steps["modelo"]
    x = vec.transform([texto])
    idx_clase = list(nb.classes_).index(clase)
    logp = nb.feature_log_prob_
    otras = np.delete(logp, idx_clase, axis=0).mean(axis=0)
    diferencia = logp[idx_clase] - otras
    nombres = vec.get_feature_names_out()
    contribuciones = [(nombres[j], float(x[0, j] * diferencia[j])) for j in x.nonzero()[1]]
    contribuciones.sort(key=lambda par: par[1], reverse=True)
    return [(p, round(v, 2)) for p, v in contribuciones[:k] if v > 0]
