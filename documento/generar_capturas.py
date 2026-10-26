#!/usr/bin/env python3
"""
Ejecuta el prototipo y genera capturas PNG de la ejecución real:
- terminal: se ejecuta cada comando, se guarda su salida completa en
  resultados/capturas/*.txt y se dibuja tal cual en una ventana de terminal;
- notebook: se convierte el notebook ejecutado a HTML y se capturan celdas.
Requiere playwright (Chromium) y nbconvert.
"""
import html
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import nbformat
from nbconvert import HTMLExporter
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "resultados" / "capturas"
OUT.mkdir(parents=True, exist_ok=True)

COMANDOS = [
    ("01_generador", ["python3", "generador_datos.py"]),
    ("02_evaluacion", ["python3", "evaluar.py"]),
    ("03_demo", ["python3", "demo_consola.py"]),
    ("04_demo_texto_libre", ["python3", "demo_consola.py", "--texto",
                             "El apagador del aula 204 echa chispas cuando lo prendes", "--zona", "Aula 204"]),
]

CSS = """
body{margin:0;background:#e9edf0;font-family:'DejaVu Sans Mono',monospace;}
.win{margin:18px;border-radius:9px;overflow:hidden;box-shadow:0 6px 22px rgba(0,0,0,.25);width:1060px;}
.bar{background:#2b3440;color:#cfd8dc;font:13px 'DejaVu Sans',sans-serif;padding:8px 12px;display:flex;align-items:center;gap:7px}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block}
.term{background:#111820;color:#e3e8ec;padding:14px 16px;font-size:12.6px;line-height:1.42;white-space:pre-wrap;word-break:break-word}
.p{color:#7fd1b9}.c{color:#ffffff;font-weight:bold}.ok{color:#9ad48a}.dim{color:#8a97a3}
"""


def terminal_html(cmd_txt, salida, inicio, segundos, codigo):
    cuerpo = (f'<span class="p">~/entrega2_EQ3 $</span> <span class="c">{html.escape(cmd_txt)}</span>\n'
              f'{html.escape(salida.rstrip())}\n'
              f'<span class="dim">[{inicio:%Y-%m-%d %H:%M:%S} · {segundos:.1f} s · código de salida {codigo}]</span>\n'
              f'<span class="p">~/entrega2_EQ3 $</span> ')
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='win'>"
            f"<div class='bar'><span class='dot' style='background:#ff5f56'></span><span class='dot' style='background:#ffbd2e'></span>"
            f"<span class='dot' style='background:#27c93f'></span>&nbsp; Terminal — entrega2_EQ3</div>"
            f"<div class='term'>{cuerpo}</div></div></body></html>")


def main():
    registros = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pagina = nav.new_page(viewport={"width": 1100, "height": 800}, device_scale_factor=2)
        for nombre, cmd in COMANDOS:
            inicio = datetime.now()
            t0 = time.time()
            r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
            seg = time.time() - t0
            salida = r.stdout + r.stderr
            cmd_txt = " ".join(f'"{c}"' if " " in c else c for c in cmd)
            (OUT / f"{nombre}.txt").write_text(f"$ {cmd_txt}\n{salida}\n[{inicio:%Y-%m-%d %H:%M:%S} · {seg:.1f} s · código {r.returncode}]\n", encoding="utf-8")
            pagina.set_content(terminal_html(cmd_txt, salida, inicio, seg, r.returncode))
            pagina.locator(".win").screenshot(path=str(OUT / f"{nombre}.png"))
            registros.append((nombre, r.returncode, round(seg, 1)))
            if r.returncode != 0:
                print("ERROR en", nombre, salida[-500:]); sys.exit(1)
        # Notebook ejecutado -> HTML -> capturas de celdas
        nb = nbformat.read(BASE / "prototipo_mantenimiento_EQ3.ipynb", as_version=4)
        cuerpo, _ = HTMLExporter(template_name="lab").from_notebook_node(nb)
        (OUT / "notebook.html").write_text(cuerpo, encoding="utf-8")
        pagina.set_viewport_size({"width": 1150, "height": 900})
        pagina.goto((OUT / "notebook.html").as_uri())
        pagina.wait_for_timeout(800)
        celdas = pagina.locator(".jp-Cell")
        grupos = {"05_notebook_reproduce": [6, 7], "06_notebook_clasificador": [8, 9],
                  "07_notebook_pruebas": [17, 18], "08_notebook_agente": [19, 20, 21]}
        for nombre, idx in grupos.items():
            cajas = [celdas.nth(i).bounding_box() for i in idx]
            x0 = min(c["x"] for c in cajas); y0 = min(c["y"] for c in cajas)
            x1 = max(c["x"] + c["width"] for c in cajas); y1 = max(c["y"] + c["height"] for c in cajas)
            pagina.screenshot(path=str(OUT / f"{nombre}.png"), full_page=True,
                              clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
            registros.append((nombre, 0, 0))
        nav.close()
    for r in registros:
        print(r)


if __name__ == "__main__":
    main()
