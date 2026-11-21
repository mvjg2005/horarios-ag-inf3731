"""
Evaluación de resultados y comparación de configuraciones del algoritmo genético.
Todos los indicadores se calculan a partir de ejecuciones reales.
"""
from __future__ import annotations

import statistics
from dataclasses import replace
from typing import Callable

import pandas as pd

from .conflictos import CATEGORIAS, NOMBRE_CATEGORIA
from .genetico import ConfigAG, ResultadoAG, ejecutar_ag, reduccion_porcentual
from .modelo import Dataset


def conteo_por_categoria(ev, cfg: ConfigAG) -> dict[str, int]:
    return {cat: sum(1 for c in ev.conflictos if c.categoria == cat and c.severidad in ("obligatorio", "preferencia"))
            for cat in CATEGORIAS}


def primera_valida(r: ResultadoAG):
    """Primera generación en la que el mejor individuo no tiene conflictos obligatorios
    (0 si ya lo cumplía la población inicial; None si nunca se alcanzó)."""
    if r.eval_original.duros == 0 and r.config.incluir_original:
        return 0
    for h in r.historial:
        if h["mejor_duros"] == 0:
            return h["generacion"]
    return 0 if r.factible else None


def indicadores(r: ResultadoAG) -> dict:
    """Indicadores del módulo 6 para una ejecución."""
    antes, despues = r.eval_original.duros, r.eval_mejor.duros
    red = reduccion_porcentual(antes, despues)
    total_duras = len(r.config.categorias_duras)
    duras_ok = sum(1 for cat, n in conteo_por_categoria(r.eval_mejor, r.config).items()
                   if cat in r.config.categorias_duras and n == 0)
    return {
        "Conflictos obligatorios antes": antes,
        "Conflictos obligatorios después": despues,
        "Reducción (%)": None if red is None else round(red, 1),
        "Coincidencias no obligatorias después": sum(c.severidad == "no_obligatorio" for c in r.eval_mejor.conflictos),
        "Mejor fitness": round(r.eval_mejor.fitness, 6),
        "Penalización blanda": round(r.eval_mejor.blando, 2),
        "Generaciones": r.generaciones,
        "Gen. primera solución válida": primera_valida(r),
        "Tiempo (s)": round(r.tiempo, 2),
        "Sesiones movidas": len(r.cambios),
        "Categorías obligatorias satisfechas": f"{duras_ok}/{total_duras}",
        "Restricciones pendientes": len(r.restricciones_pendientes()),
        "Horario válido": "Sí" if r.factible else "No",
        "Motivo de parada": r.motivo_parada,
    }


def tabla_antes_despues(r: ResultadoAG) -> pd.DataFrame:
    a = conteo_por_categoria(r.eval_original, r.config)
    d = conteo_por_categoria(r.eval_mejor, r.config)
    return pd.DataFrame([{"Categoría": NOMBRE_CATEGORIA[c], "Antes": a[c], "Después": d[c]} for c in CATEGORIAS])


def comparar_configuraciones(ds: Dataset, configs: dict[str, ConfigAG], semillas: list[int],
                             progreso: Callable[[str, int], None] | None = None
                             ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[ResultadoAG]]]:
    """Ejecuta cada configuración con varias semillas.

    Devuelve (detalle por ejecución, resumen por configuración, resultados).
    """
    filas, resultados = [], {}
    for nombre, cfg in configs.items():
        resultados[nombre] = []
        for sem in semillas:
            r = ejecutar_ag(ds, replace(cfg, semilla=sem))
            resultados[nombre].append(r)
            fila = {"Configuración": nombre, "Semilla": sem, "Población": cfg.poblacion,
                    "Generaciones máx.": cfg.generaciones, "Pc": cfg.prob_cruce, "Pm": cfg.prob_mutacion,
                    "Cruce": cfg.tipo_cruce, "Elitismo": cfg.elitismo, "Torneo k": cfg.torneo_k,
                    "Mut. dirigida": "Sí" if cfg.mutacion_dirigida else "No"}
            fila.update(indicadores(r))
            filas.append(fila)
            if progreso:
                progreso(nombre, sem)
    det = pd.DataFrame(filas)
    res = []
    for nombre, rs in resultados.items():
        duros = [r.eval_mejor.duros for r in rs]
        blandos = [r.eval_mejor.blando for r in rs]
        res.append({
            "Configuración": nombre, "Ejecuciones": len(rs),
            "Horarios válidos": f"{sum(d == 0 for d in duros)}/{len(rs)}",
            "Conflictos oblig. (media)": round(statistics.mean(duros), 2),
            "Penalización blanda (media)": round(statistics.mean(blandos), 2),
            "Penalización blanda (desv.)": round(statistics.pstdev(blandos), 2),
            "Mejor fitness (máx.)": round(max(r.eval_mejor.fitness for r in rs), 6),
            "Generaciones (media)": round(statistics.mean(r.generaciones for r in rs), 1),
            "Gen. 1ª sol. válida (media)": (round(statistics.mean(v), 1) if (v := [primera_valida(r) for r in rs
                                            if primera_valida(r) is not None]) else None),
            "Tiempo s (media)": round(statistics.mean(r.tiempo for r in rs), 2),
        })
    return det, pd.DataFrame(res), resultados


CONFIGS_REFERENCIA = {
    "C1 · base": ConfigAG(),
    "C2 · con mutación dirigida": ConfigAG(mutacion_dirigida=True),
    "C3 · población pequeña (30)": ConfigAG(poblacion=30),
    "C4 · cruce un punto, Pm alta": ConfigAG(tipo_cruce="un_punto", prob_mutacion=0.2),
}
