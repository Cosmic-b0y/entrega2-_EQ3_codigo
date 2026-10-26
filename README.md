# Proyecto integrador IA · Segunda entrega · Equipo 3

Prototipo del **Sistema Inteligente para Monitoreo, Clasificación y Priorización del Mantenimiento de Infraestructura** (caso UNACH, referencia piloto ETDA).

> Todos los datos son **simulados** o redactados fuera del generador; no son reportes reales de la UNACH ni de ETDA.
> Ninguna salida es un dictamen técnico: el prototipo propone una **prioridad preliminar** sujeta a revisión humana.

Repositorio: https://github.com/Cosmic-b0y/entrega2_EQ3_codigo

## Componentes
- **Clasificador de categoría**: Naive Bayes multinomial sobre la descripción (comparado con regresión logística TF-IDF y una línea base de palabras clave).
- **Motor de reglas** R1–R12: combina categoría, confianza, señales de riesgo del texto, calidad de la foto e historial para proponer prioridad (Inmediata/Alta/Media/Baja), escalamiento y revisión humana.
- **Agente** (`AgenteMantenimiento`): percibir → interpretar → decidir → actuar → retroalimentar, más panel de casos abiertos (R6).

## Reproducir
```bash
pip install -r requirements.txt
python generador_datos.py           # datos/ (semilla 2026)
python evaluar.py                   # resultados/metricas.json, figuras, pruebas
python demo_consola.py              # demostración
python demo_consola.py --texto "el contacto echa chispas" --zona "Aula 101"
python demo_consola.py --interactivo
python documento/construir_notebook.py   # reejecuta el notebook
python documento/construir_pdf.py        # reconstruye el PDF desde resultados/
python documento/generar_capturas.py     # ejecuta y genera capturas PNG
python documento/verificar_cifras.py     # comprueba cada cifra del PDF
```
Probado con Python 3.13 y las versiones de `requirements.txt`. Con otras versiones de scikit-learn las cifras pueden variar ligeramente.

## Estructura
| Ruta | Contenido |
|---|---|
| `generador_datos.py` | Escenarios, plantillas, ruido, historial y referencia simulada |
| `mantenimiento_ia/conocimiento.py` | Taxonomía, normalización, lexicón de señales, política de prioridad |
| `mantenimiento_ia/clasificador.py` | Naive Bayes, regresión logística, palabras clave, explicación |
| `mantenimiento_ia/reglas.py` | Motor de reglas |
| `mantenimiento_ia/agente.py` | Agente y ciclo completo |
| `evaluar.py` | Protocolo de evaluación (partición por plantilla, casos externos, umbral sin datos de prueba) |
| `pruebas_definidas.json` | Resultados esperados escritos antes de ejecutar |
| `prototipo_mantenimiento_EQ3.ipynb` | Notebook ejecutado |
| `datos/` | Reportes simulados, historial, casos externos, metadatos |
| `resultados/` | Métricas, decisiones por reporte, pruebas, figuras, salida de la demo |
| `documento/` | PDF, scripts que lo generan y verificación de cifras |
