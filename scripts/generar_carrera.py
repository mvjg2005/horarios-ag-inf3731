"""
Construye el conjunto de datos REAL de planificación de la carrera (data/carrera_2026_2/)
a partir de:

* data/catalogo/plan_estudios.csv  -> planes de estudio oficiales de las 5 menciones
                                      (extraídos con scripts/extraer_planes.py)
* data/catalogo/plantel_docente.csv -> materias y paralelos de cada docente según
                                      https://www.sisinf.fni.uto.edu.bo/docentes/ (20/11/2026)

    python scripts/generar_carrera.py

Modelo (los supuestos se registran en meta.json -> pendientes):
* Sólo materias SIS/INF (las organiza la carrera). Las de otros departamentos (MAT, FIS,
  QMC, IND, ELT...) no se programan aquí porque no se conoce su horario.
* Una "hora" del plan = periodo académico de 45 min (SUPUESTO). Las horas se dividen en
  sesiones de 90 min (2 periodos); si sobra un periodo, una sesión de 45 min.
  T -> clases teóricas (docente del plantel), P -> auxiliatura, L -> laboratorio.
* Cohortes curriculares (estudiantes tipo): para cada mención, semestre y paralelo, las
  materias SIS/INF obligatorias de ese semestre no deben coincidir (restricción dura).
  Si una materia no tiene el paralelo de la cohorte, se usa el paralelo A.
* Cohortes con electiva: cada electiva ofertada no debe chocar con las materias del
  semestre que tiene el espacio de electiva en esa mención (dura).
* Cohortes irregulares: semestres consecutivos de una mención (blanda), para reducir
  choques de estudiantes que arrastran o adelantan materias.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.datos import RAIZ_DATOS, guardar_carpeta  # noqa: E402
from core.modelo import Asignatura, Dataset, Estudiante, Inscripcion, Persona, Sesion  # noqa: E402

PERIODO = 45
CORRECCIONES = {  # sigla publicada -> sigla del plan (mismo nombre de materia); se informan como pendientes
    ("SIS 1210", "CH"): "INF 1210",   # "Análisis Discreto" figura en los planes como INF 1210
    ("SIS 3430", "CH"): "SIS 2430",   # "Programación Gráfica" figura en los planes como SIS 2430
}
NOMBRE_MENCION = {"INF-TEL": "Inf. Telemática", "INF-DSW": "Inf. Desarrollo de Software",
                  "SIS-MOR": "Sis. Modelamiento y Optimización", "SIS-GIN": "Sis. Gestión de la Información",
                  "SIS-DGE": "Sis. Dirección y Gestión Empresarial"}


def titulo(txt: str) -> str:
    menores = {"de", "la", "del", "y", "en", "a", "los", "las", "e"}
    romanos = {"i", "ii", "iii", "iv", "v"}
    pal = txt.lower().split()
    return " ".join(p.upper() if p in romanos else p if (i and p in menores) else p[:1].upper() + p[1:]
                    for i, p in enumerate(pal))


def bloques(periodos: int) -> list[int]:
    out = [2 * PERIODO] * (periodos // 2)
    if periodos % 2:
        out.append(PERIODO)
    return out


def construir() -> Dataset:
    plan = pd.read_csv(RAIZ_DATOS / "catalogo" / "plan_estudios.csv")
    plantel = pd.read_csv(RAIZ_DATOS / "catalogo" / "plantel_docente.csv", keep_default_na=False)
    pendientes = [
        "Fuente de materias y paralelos: plantel docente publicado en sisinf.fni.uto.edu.bo/docentes (consultado el "
        "20/11/2026). Fuente de horas y semestres: planes de estudio oficiales de las 5 menciones.",
        "Horario inicial: SIN ASIGNAR. El algoritmo genético genera la propuesta completa (modo planificación).",
        "Duración de una hora académica: 45 min (SUPUESTO, confirmar). Sesiones de 90 min.",
        "Auxiliares y responsables de laboratorio: no publicados; esas sesiones no tienen responsable.",
        "Aulas, laboratorios y capacidades: no publicados; no se asignan ambientes.",
        "Disponibilidad de docentes: no publicada; cada docente puede registrarla con su rol.",
        "Inscripciones reales: no disponibles; se usan cohortes curriculares (estudiantes tipo) por mención, "
        "semestre y paralelo.",
        "Materias de otros departamentos (MAT, FIS, QMC, IND, ELT...): no incluidas; su horario es externo.",
        "Franja 07:00–21:00, lunes a sábado (SUPUESTO); se penaliza programar en sábado.",
    ]
    # ---- oferta: (sigla, paralelo) -> docente --------------------------------
    oferta: dict[tuple[str, str], str] = {}
    personas: dict[str, Persona] = {}
    ids_doc: dict[str, str] = {}
    for _, r in plantel.iterrows():
        nombre = r["docente"]
        if nombre not in ids_doc:
            ids_doc[nombre] = f"DOC-{len(ids_doc) + 1:02d}"
            personas[ids_doc[nombre]] = Persona(ids_doc[nombre], nombre, "docente")
        sigla, par = r["sigla"], r["paralelo"]
        if sigla.startswith("LAB"):
            continue
        if not par:
            pendientes.append(f"{nombre}: {r['materia_web']} {sigla} publicado sin paralelo; no se programa.")
            continue
        if (sigla, par) in CORRECCIONES:
            nueva = CORRECCIONES[(sigla, par)]
            pendientes.append(f"{r['materia_web']} {sigla} {par} ({nombre}): la sigla no figura en los planes; se usó "
                              f"{nueva} por coincidir el nombre de la materia. Confirmar.")
            sigla = nueva
        if (sigla, par) in oferta:
            pendientes.append(f"{sigla} {par} aparece con dos docentes; se usó el primero.")
            continue
        oferta[(sigla, par)] = ids_doc[nombre]
    ofertadas = {s for s, _ in oferta}
    sis_inf = plan[plan.sigla.str.match(r"^(SIS|INF) ")]
    no_ofertadas = sorted(set(sis_inf[sis_inf.tipo != "no_curricular"].sigla) - ofertadas)
    pendientes.append(f"Materias SIS/INF de los planes sin docente publicado en la gestión (no se programan): "
                      f"{len(no_ofertadas)} ({', '.join(no_ofertadas)}).")

    ds = Dataset(
        nombre="Carrera – planificación gestión 2026/2", tipo_datos="real", modo="planificacion",
        descripcion=("Oferta SIS/INF de Ingeniería de Sistemas e Informática (5 menciones) construida con los planes de "
                     "estudio oficiales y el plantel docente publicado. El algoritmo genera el horario completo "
                     "evitando choques entre materias del mismo semestre de cada mención y de cada docente."),
        dias=list(range(6)), hora_inicio=7 * 60, hora_fin=21 * 60, resolucion=PERIODO, pendientes=pendientes,
        personas=personas,
    )
    info = plan.drop_duplicates("sigla").set_index("sigla")
    for sigla in sorted(ofertadas):
        f = info.loc[sigla]
        sems = sorted({int(x) for x in plan[(plan.sigla == sigla) & (plan.semestre > 0)].semestre})
        ds.asignaturas[sigla] = Asignatura(
            sigla, titulo(f["nombre"]), sigla, ",".join(map(str, sems)) or "electiva",
            horas_teoria=f["horas_t"] * PERIODO / 60, horas_laboratorio=f["horas_l"] * PERIODO / 60,
            horas_auxiliatura=f["horas_p"] * PERIODO / 60)

    # ---- sesiones -------------------------------------------------------------
    for (sigla, par), doc in sorted(oferta.items()):
        f = info.loc[sigla]
        base = sigla.replace(" ", "")
        for tipo, periodos, resp in (("teoria", f["horas_t"], doc), ("auxiliatura", f["horas_p"], None),
                                     ("laboratorio", f["horas_l"], None)):
            for k, dur in enumerate(bloques(int(periodos)), 1):
                pref = {"teoria": "T", "auxiliatura": "AUX", "laboratorio": "LAB"}[tipo]
                ds.sesiones.append(Sesion(
                    id=f"{base}-{par}-{pref}{k}", asignatura=sigla, tipo=tipo, paralelo=par, dia=0,
                    inicio=7 * 60, fin=7 * 60 + dur, responsable=resp, fija=False, origen="oficial",
                    observacion="Sede Challapata" if par == "CH" else ""))

    # ---- cohortes curriculares --------------------------------------------------
    paralelos = defaultdict(list)
    for s, p in oferta:
        paralelos[s].append(p)

    def elegir(sigla, letra):
        ps = paralelos.get(sigla, [])
        if letra == "CH":
            return "CH" if "CH" in ps else None
        if letra in ps:
            return letra
        principales = sorted(p for p in ps if p != "CH")
        return "A" if "A" in principales else (principales[0] if principales else None)

    def cohorte(cid, nombre, sem, tipo, materias):
        if len(materias) < 2:
            return
        ds.estudiantes[cid] = Estudiante(cid, nombre, sem, tipo)
        for sigla, par in materias:
            ds.inscripciones.append(Inscripcion(cid, sigla, par))

    oblig = sis_inf[sis_inf.tipo == "obligatoria"]
    for mid in NOMBRE_MENCION:
        pm = oblig[oblig.mencion_id == mid]
        electivas = [s for s in sis_inf[(sis_inf.mencion_id == mid) & (sis_inf.tipo == "electiva")].sigla if s in ofertadas]
        slots_elec = set(plan[(plan.mencion_id == mid) & (plan.sigla.str.startswith("ELEC"))].semestre)
        for k in range(1, 11):
            mats = [s for s in pm[pm.semestre == k].sigla if s in ofertadas]
            letras = sorted({p for s in mats for p in paralelos[s] if p != "CH"})
            for letra in letras + (["CH"] if any("CH" in paralelos[s] for s in mats) else []):
                sel = [(s, elegir(s, letra)) for s in mats]
                cohorte(f"COH-{mid}-{k:02d}-{letra}", f"{NOMBRE_MENCION[mid]} · {k}.º sem. · paralelo {letra}",
                        str(k), "regular", [x for x in sel if x[1]])
            if k in slots_elec:
                base_sel = [(s, elegir(s, "A")) for s in mats]
                for e in electivas:
                    cohorte(f"COH-{mid}-{k:02d}-E-{e.replace(' ', '')}",
                            f"{NOMBRE_MENCION[mid]} · {k}.º sem. · con electiva {e}", str(k), "regular",
                            [x for x in base_sel if x[1]] + [(e, elegir(e, "A"))])
            if k < 10:
                sig = [s for s in pm[pm.semestre == k + 1].sigla if s in ofertadas]
                sel = [(s, elegir(s, "A")) for s in mats + sig]
                cohorte(f"IRR-{mid}-{k:02d}", f"{NOMBRE_MENCION[mid]} · irregular {k}.º–{k + 1}.º sem.",
                        f"{k}-{k + 1}", "irregular", [x for x in sel if x[1]])
    ds._cache_inscritos = {}
    return ds


def main() -> None:
    ds = construir()
    guardar_carpeta(ds, RAIZ_DATOS / "carrera_2026_2")
    reg = sum(e.tipo == "regular" for e in ds.estudiantes.values())
    print(f"carrera_2026_2: {len(ds.asignaturas)} materias, {len({(s.asignatura, s.paralelo) for s in ds.sesiones})} "
          f"paralelos, {len(ds.sesiones)} sesiones, {len(ds.personas)} docentes, {reg} cohortes regulares, "
          f"{len(ds.estudiantes) - reg} irregulares")


if __name__ == "__main__":
    main()
