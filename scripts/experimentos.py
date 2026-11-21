"""
Ejecuta los experimentos reportados en el informe y guarda los resultados en resultados/.

    python scripts/experimentos.py

Todos los valores provienen de ejecuciones reales del algoritmo (no se escriben a mano).
"""
from __future__ import annotations

import json
import platform
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from core.conflictos import conflictos_a_df, detectar_conflictos, resumen_por_categoria  # noqa: E402
from core.datos import RAIZ_DATOS, cargar_carpeta, exportar_excel  # noqa: E402
from core.evaluacion import CONFIGS_REFERENCIA, comparar_configuraciones, indicadores, tabla_antes_despues  # noqa: E402
from core.genetico import ConfigAG, ejecutar_ag  # noqa: E402

SALIDA = RAIZ / "resultados"
SEMILLAS = [1, 2, 3, 4, 5]


def grafico(historial, titulo, archivo):
    h = pd.DataFrame(historial)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    a1.plot(h.generacion, h.mejor_fitness, color="#0B1F3A", lw=2.2, label="Mejor fitness")
    a1.plot(h.generacion, h.fitness_promedio, color="#C9A227", lw=1.4, label="Fitness promedio")
    a1.set_ylabel("Fitness"); a1.legend(); a1.grid(alpha=.3); a1.set_title(titulo)
    a2.plot(h.generacion, h.mejor_duros, color="#C62828", lw=2.2, label="Conflictos obligatorios (mejor)")
    a2.plot(h.generacion, h.duros_promedio, color="#E8A0A0", ls=":", label="Conflictos obligatorios (promedio)")
    a2.set_xlabel("Generación"); a2.set_ylabel("Conflictos"); a2.legend(); a2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(archivo, dpi=150); plt.close(fig)


def main():
    SALIDA.mkdir(exist_ok=True)
    resumen = {"fecha": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(),
               "semillas": SEMILLAS, "experimentos": {}}
    hojas = {}

    # --- E1: caso real, ambos escenarios -----------------------------------
    real = cargar_carpeta(RAIZ_DATOS / "caso_real_2026_2")
    for esc in ("original", "reprogramado"):
        conf = detectar_conflictos(real, escenario=esc)
        hojas[f"real_{esc}_conflictos"] = conflictos_a_df(real, conf)
        r = ejecutar_ag(real, ConfigAG(escenario=esc, semilla=42))
        ind = indicadores(r)
        hojas[f"real_{esc}_cambios"] = pd.DataFrame(r.cambios)
        resumen["experimentos"][f"E1_real_{esc}"] = {"indicadores": ind, "cambios": r.cambios,
                                                    "pendientes": r.restricciones_pendientes()}
        grafico(r.historial, f"Caso real 2026/2 – escenario {esc}", SALIDA / f"fitness_real_{esc}.png")

    # --- E2: demo pequeño (solución conocida) y demo infactible -------------
    for nombre in ("demo_pequeno", "demo_infactible"):
        ds = cargar_carpeta(RAIZ_DATOS / nombre)
        rs = [ejecutar_ag(ds, ConfigAG(semilla=s)) for s in SEMILLAS]
        resumen["experimentos"][f"E2_{nombre}"] = {
            "validos": f"{sum(r.factible for r in rs)}/{len(rs)}",
            "duros_antes": rs[0].eval_original.duros, "duros_despues": [r.eval_mejor.duros for r in rs],
            "mensaje": rs[0].mensaje(), "diagnostico": rs[0].diagnostico}

    # --- E3: demo semestre, comparación de configuraciones -----------------
    sem = cargar_carpeta(RAIZ_DATOS / "demo_semestre")
    hojas["semestre_resumen_categorias"] = resumen_por_categoria(detectar_conflictos(sem))
    det, res, resultados = comparar_configuraciones(sem, CONFIGS_REFERENCIA, SEMILLAS,
                                                    lambda n, s: print(f"  {n} · semilla {s}"))
    hojas["comparacion_resumen"], hojas["comparacion_detalle"] = res, det
    base = resultados["C1 · base"][0]
    hojas["semestre_antes_despues"] = tabla_antes_despues(base)
    grafico(base.historial, "Demo semestre (simulado) – configuración C1, semilla 1", SALIDA / "fitness_semestre_C1.png")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for (n, rs), c in zip(resultados.items(), ["#0B1F3A", "#C9A227", "#2E7D5B", "#C62828"]):
        h = pd.DataFrame(rs[0].historial)
        ax.plot(h.generacion, h.mejor_duros + h.mejor_blando / 1000, color=c, label=n)
    ax.set_yscale("log"); ax.set_xlabel("Generación"); ax.set_ylabel("Costo = duros + blando/1000")
    ax.set_title("Demo semestre (simulado): convergencia por configuración (semilla 1)")
    ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(SALIDA / "comparacion_configuraciones.png", dpi=150)
    resumen["experimentos"]["E3_semestre"] = {"resumen": res.to_dict(orient="records")}

    (SALIDA / "resumen_experimentos.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str),
                                                      encoding="utf-8")
    (SALIDA / "resultados_experimentos.xlsx").write_bytes(exportar_excel(hojas))
    print(res.to_string())
    print("Resultados guardados en", SALIDA)


if __name__ == "__main__":
    main()
