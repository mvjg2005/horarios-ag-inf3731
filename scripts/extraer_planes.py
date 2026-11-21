"""
Extrae los planes de estudio oficiales (PDF en fuentes/) a data/catalogo/plan_estudios.csv.

    python scripts/extraer_planes.py

Columnas: mencion, programa, semestre (0 = electiva, -1 = no curricular), sigla, nombre,
horas_t, horas_p, horas_l, prerrequisito, tipo (obligatoria | electiva | no_curricular).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "fuentes"
SALIDA = RAIZ / "data" / "catalogo"

MENCIONES = {
    "Ingenieria_Informatica_Telematica": ("INF-TEL", "Ingeniería Informática", "Telemática"),
    "Ingenieria_Informatica_Mencion_DesarroloSoftware": ("INF-DSW", "Ingeniería Informática", "Desarrollo de Software"),
    "Ingenieria_Sistemas_Mencion_ModelamientoyOptimizaciondeRecursos": (
        "SIS-MOR", "Ingeniería de Sistemas", "Modelamiento y Optimización de Recursos-Procesos"),
    "Ingenieria_Sistemas_Mencion_Gestion_Informacion": ("SIS-GIN", "Ingeniería de Sistemas", "Gestión de la Información"),
    "Ingenieria_Sistemas_Mencion_Gestion_Empresarial": (
        "SIS-DGE", "Ingeniería de Sistemas", "Dirección y Gestión de Sistemas Empresariales"),
}
SIGLA = r"(?:[A-Z]{2,4} ?\d{4}|ELEC \d)"
FILA = re.compile(rf"^\s*(?:(\d{{1,2}})\s+)?({SIGLA})\s+(.*?)\s{{2,}}(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*(.*)$")


def extraer(pdf: Path) -> list[dict]:
    texto = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    lineas = texto.splitlines()
    seccion, filas = "plan", []
    for i, linea in enumerate(lineas):
        if re.search(r"^\s*ELECTIVAS\b", linea):
            seccion = "electiva"
        elif "NO CURRICULAR" in linea:
            seccion = "no_curricular"
        m = FILA.match(linea)
        if not m or "TOTAL" in linea:
            continue
        sem, sigla, nombre, t, p, l, total, pre = m.groups()
        nombre = nombre.strip()
        if not nombre:   # nombre partido en dos líneas: la anterior y la siguiente
            antes = lineas[i - 1].strip() if i else ""
            despues = lineas[i + 1].strip() if i + 1 < len(lineas) else ""
            nombre = f"{antes} {despues}".strip()
        tipo = "obligatoria" if seccion == "plan" else seccion
        filas.append({
            "semestre": int(sem) if sem else (0 if tipo == "electiva" else -1),
            "sigla": sigla.replace("  ", " "), "nombre": re.sub(r"\s+", " ", nombre),
            "horas_t": int(t), "horas_p": int(p), "horas_l": int(l),
            "prerrequisito": pre.strip(), "tipo": tipo,
        })
        assert int(t) + int(p) + int(l) == int(total), (pdf.name, linea)
    return filas


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    todas = []
    for clave, (mid, programa, mencion) in MENCIONES.items():
        pdf = FUENTES / f"Plan_de_Estudios-{clave}.pdf"
        filas = extraer(pdf)
        for f in filas:
            f.update(mencion_id=mid, programa=programa, mencion=mencion)
        print(f"{mid}: {len(filas)} filas ({sum(f['tipo'] == 'obligatoria' for f in filas)} obligatorias)")
        todas += filas
    df = pd.DataFrame(todas, columns=["mencion_id", "programa", "mencion", "semestre", "sigla", "nombre", "horas_t",
                                      "horas_p", "horas_l", "prerrequisito", "tipo"])
    df.to_csv(SALIDA / "plan_estudios.csv", index=False, encoding="utf-8")
    print("Guardado", SALIDA / "plan_estudios.csv", len(df))


if __name__ == "__main__":
    sys.exit(main())
