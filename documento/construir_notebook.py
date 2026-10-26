"""Construye y ejecuta el notebook del prototipo (salidas guardadas)."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

BASE = Path(__file__).resolve().parent.parent
nb = nbformat.v4.new_notebook()
md, code = nbformat.v4.new_markdown_cell, nbformat.v4.new_code_cell
nb.cells = [
    md("# Proyecto integrador IA · Segunda entrega · Equipo 3\n"
       "**Sistema inteligente para monitoreo, clasificación y priorización del mantenimiento de infraestructura** (caso UNACH, referencia piloto ETDA).\n\n"
       "> Todos los datos de este notebook son **simulados** (generados con `generador_datos.py`, semilla 2026) o **redactados a mano** por el equipo. "
       "No corresponden a reportes reales. Ninguna salida es un dictamen técnico: el prototipo propone una **prioridad preliminar** sujeta a revisión humana."),
    code("import json, warnings\nwarnings.filterwarnings('ignore')\nimport pandas as pd\nfrom IPython.display import Image, display\n"
         "pd.set_option('display.max_colwidth', 90); pd.set_option('display.width', 200)\n"
         "from evaluar import cargar, ejecutar_todo\nfrom mantenimiento_ia import AgenteMantenimiento, crear_naive_bayes, detectar_senales"),
    md("## 1. Datos simulados y casos externos"),
    code("d, historial, ext = cargar()\nprint('Reportes simulados:', len(d), '| entrenamiento:', (d.grupo=='entrenamiento').sum(), '| prueba:', (d.grupo=='prueba').sum(), '| externos:', len(ext))\n"
         "d[['id','fecha','zona','texto','foto_calidad','categoria_declarada','activo_id','plantilla','categoria_ref','prioridad_ref']].head(8)"),
    code("pd.crosstab(d.plantilla, d.grupo)"),
    code("ext[['id','texto','categoria_ref','senales_ref','prioridad_ref']].head(8)"),
    md("## 2. Entrenamiento y evaluación completa\n`ejecutar_todo()` repite exactamente el protocolo de `evaluar.py`. Se comprueba que las cifras coincidan con `resultados/metricas.json`."),
    code("m, pruebas, res_te, res_ex, nb = ejecutar_todo(guardar=False)\nguardado = json.load(open('resultados/metricas.json', encoding='utf-8'))\n"
         "print('¿Cifras idénticas a resultados/metricas.json?', json.dumps(m, sort_keys=True, default=str) == json.dumps(guardado, sort_keys=True, default=str))\n"
         "print('alpha NB:', m['seleccion']['alpha_nb'], '| C LR:', m['seleccion']['C_lr'], '| umbral:', m['umbral']['valor'])"),
    md("## 3. Clasificador de categoría"),
    code("filas = []\nfor conj in ('prueba', 'externos', 'aleatoria'):\n    for mod in ('palabras_clave', 'naive_bayes', 'regresion_logistica'):\n"
         "        x = m['clasificador'][conj][mod]; filas.append({'conjunto': conj, 'modelo': mod, **{k: round(v, 3) for k, v in x.items() if k != 'n'}, 'n': x['n']})\npd.DataFrame(filas)"),
    code("display(Image('resultados/figuras/matriz_nb_prueba.png', width=430)); display(Image('resultados/figuras/matriz_nb_externos.png', width=430))"),
    code("print(m['umbral']); display(Image('resultados/figuras/umbral_validacion.png', width=560))"),
    md("## 4. Señales de riesgo detectadas en el texto (lexicón)"),
    code("pd.DataFrame({c: {s: (round(v['recall'], 3) if v['recall'] is not None else None) for s, v in m['senales'][c].items()} for c in ('prueba', 'externos')}).rename(columns=lambda c: 'recall_' + c)"),
    md("## 5. Prioridad preliminar: prototipo frente a líneas base"),
    code("cols = ['exactitud_prioridad','recall_criticos','falsos_negativos_criticos','fn_criticos_sin_revision','falsas_alarmas','proporcion_revision_humana','subestimacion']\n"
         "for conj in ('prueba', 'externos'):\n    print('==', conj)\n    display(pd.DataFrame(m['prioridad'][conj]).T[cols])"),
    code("display(Image('resultados/figuras/comparacion_sistemas.png', width=640))\nprint('R4 duplicados (prueba):', m['duplicados_R4_prueba'])"),
    md("## 6. Pruebas con resultado esperado definido antes de ejecutar"),
    code("pd.DataFrame([{'id': p['id'], 'regla': p['regla'], 'correcto': p['correcto'], 'fallas': p['fallas'], 'prioridad': p['obtenido']['prioridad'], 'reglas': p['obtenido']['reglas']} for p in pruebas['pruebas']])"),
    md("## 7. El agente en acción: percibir → interpretar → decidir → actuar → retroalimentar"),
    code("tr = d[d.grupo=='entrenamiento']\nagente = AgenteMantenimiento(nb, m['umbral']['valor'], historial, tr.texto.values)\n"
         "salida = agente.procesar({'id': 'NB1', 'fecha': '2026-10-25', 'zona': 'Biblioteca', 'foto_calidad': 'legible',\n"
         "                          'texto': 'Se está filtrando agua por el plafón justo arriba del tablero eléctrico'})\n"
         "for etapa in ('interpretacion', 'decision', 'accion'):\n    print(etapa.upper(), {k: v for k, v in salida[etapa].items() if k != 'senales_efectivas'})"),
    code("salida2 = agente.procesar({'id': 'NB2', 'fecha': '2026-10-25', 'zona': 'Aula 203', 'foto_calidad': 'legible', 'texto': 'La pintura de la pared está descarapelada'})\n"
         "caso = agente.retroalimentar(salida2['accion']['caso_id'], 'Responsable (simulado)', '2026-10-26', solo_estetico=True)\n"
         "print('Prioridad tras confirmación R5:', caso.prioridad)\nprint(agente.correcciones[-1])\npd.DataFrame(agente.panel('2026-10-26'))"),
    md("## 8. Ejemplos de error (casos externos)"),
    code("e = res_ex[res_ex.categoria_ref != res_ex.categoria_pred][['id','texto','categoria_ref','categoria_pred','confianza','palabras_clave']]\ne.head(10)"),
    code("res_ex[(res_ex.critico_ref) & ~((res_ex.prioridad_pred=='Inmediata') | res_ex.escalamiento_pred)][['id','texto','senales_ref','senales_detectadas','prioridad_ref','prioridad_pred']]"),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
ruta = BASE / "prototipo_mantenimiento_EQ3.ipynb"
NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(BASE)}}).execute()
nbformat.write(nb, ruta)
print("Notebook ejecutado:", ruta)
