"""
Experimento E4: planificación completa de la carrera (data/carrera_2026_2).

Compara, con las semillas 1–5:
  A. AG con población inicial 100 % aleatoria.
  B. Sólo la heurística voraz (mejor de 24 individuos heurísticos, sin evolución).
  C. Heurística (30 % de la población) + AG  [configuración de planificación por defecto].

    python scripts/experimento_carrera.py      (~8 min)
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from core.datos import RAIZ_DATOS, cargar_carpeta, exportar_excel  # noqa: E402
from core.genetico import config_planificacion, construir_problema, ejecutar_ag, evaluar, individuo_heuristico  # noqa: E402

SALIDA = RAIZ / "resultados"
SEMILLAS = [1, 2, 3, 4, 5]


def main():
    ds = cargar_carpeta(RAIZ_DATOS / "carrera_2026_2")
    base = config_planificacion()
    filas, curvas = [], {}
    prob = construir_problema(ds)
    for sem in SEMILLAS:
        rA = ejecutar_ag(ds, replace(base, semilla=sem, frac_heuristica=0.0))
        rng = random.Random(sem)
        heur = [evaluar(prob, individuo_heuristico(prob, rng), base) for _ in range(24)]
        mejorB = min(heur, key=lambda e: e.clave)
        rC = ejecutar_ag(ds, replace(base, semilla=sem))
        for nombre, duros, blando, t, gens in (
                ("A · AG aleatorio", rA.eval_mejor.duros, rA.eval_mejor.blando, rA.tiempo, rA.generaciones),
                ("B · sólo heurística", mejorB.duros, mejorB.blando, None, 0),
                ("C · heurística + AG", rC.eval_mejor.duros, rC.eval_mejor.blando, rC.tiempo, rC.generaciones)):
            filas.append({"Configuración": nombre, "Semilla": sem, "Conflictos obligatorios": duros,
                          "Penalización blanda": round(blando, 2), "Generaciones": gens,
                          "Tiempo (s)": None if t is None else round(t, 1)})
        if sem == 1:
            curvas = {"A": rA.historial, "C": rC.historial, "C_det": rC.eval_mejor.detalle_blando,
                      "B_det": mejorB.detalle_blando}
        print(f"semilla {sem}: A={rA.eval_mejor.duros}/{rA.eval_mejor.blando:.1f}  "
              f"B={mejorB.duros}/{mejorB.blando:.1f}  C={rC.eval_mejor.duros}/{rC.eval_mejor.blando:.1f}")
    det = pd.DataFrame(filas)
    res = []
    for nombre, g in det.groupby("Configuración", sort=False):
        res.append({"Configuración": nombre,
                    "Horarios sin conflictos obligatorios": f"{int((g['Conflictos obligatorios'] == 0).sum())}/{len(g)}",
                    "Conflictos oblig. (media)": round(g["Conflictos obligatorios"].mean(), 1),
                    "Penalización blanda (media)": round(g["Penalización blanda"].mean(), 2),
                    "Penalización blanda (desv.)": round(statistics.pstdev(g["Penalización blanda"]), 2),
                    "Tiempo medio (s)": None if g["Tiempo (s)"].isna().all() else round(g["Tiempo (s)"].mean(), 1)})
    res = pd.DataFrame(res)
    print(res.to_string())
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "resultados_carrera.xlsx").write_bytes(exportar_excel({"resumen": res, "detalle": det}))
    resumen = {"sesiones": len(ds.sesiones), "paralelos": len({(s.asignatura, s.paralelo) for s in ds.sesiones}),
               "docentes": len(ds.personas), "cohortes_regulares": sum(e.tipo == "regular" for e in ds.estudiantes.values()),
               "cohortes_irregulares": sum(e.tipo == "irregular" for e in ds.estudiantes.values()),
               "resumen": res.to_dict(orient="records"), "detalle_blando_semilla1": {
                   "B": {k: round(v, 2) for k, v in curvas["B_det"].items()},
                   "C": {k: round(v, 2) for k, v in curvas["C_det"].items()}}}
    (SALIDA / "resumen_carrera.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    # gráfico
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    hA, hC = pd.DataFrame(curvas["A"]), pd.DataFrame(curvas["C"])
    a1.plot(hA.generacion, hA.mejor_duros, color="#A63D3D", lw=2, label="A · AG aleatorio")
    a1.plot(hC.generacion, hC.mejor_duros, color="#2F6B6B", lw=2, label="C · heurística + AG")
    a1.set_title("Conflictos obligatorios del mejor horario"); a1.set_xlabel("Generación"); a1.legend(); a1.grid(alpha=.3)
    a2.plot(hC.generacion, hC.mejor_blando, color="#B08D3C", lw=2)
    a2.set_title("C · penalización por preferencias (0 conflictos)"); a2.set_xlabel("Generación"); a2.grid(alpha=.3)
    fig.suptitle("Planificación de la carrera (369 sesiones), semilla 1")
    fig.tight_layout(); fig.savefig(SALIDA / "carrera_convergencia.png", dpi=150)


if __name__ == "__main__":
    main()
