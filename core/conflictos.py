"""
Detección automática de conflictos.

Categorías
----------
1. estudiante        – un estudiante INSCRITO en dos actividades simultáneas.
2. docente           – un docente con dos sesiones simultáneas.
3. auxiliar          – un auxiliar con dos sesiones simultáneas.
4. aula              – un aula asignada a dos sesiones simultáneas.
5. laboratorio       – un laboratorio asignado a dos sesiones simultáneas.
6. capacidad         – más inscritos que la capacidad del ambiente.
7. disponibilidad    – fuera de la disponibilidad del responsable o del ambiente,
                       de la franja institucional o de los días permitidos.
8. duracion          – duración de la sesión o carga semanal distinta de la requerida.
9. disp_estudiante   – la sesión cae fuera de la disponibilidad declarada por
                       estudiantes inscritos (por defecto es una restricción BLANDA).
10. estudiante_irregular – choque que sólo afecta a estudiantes (o cohortes) irregulares,
                       que adelantan o arrastran materias (BLANDA por defecto).

Regla clave: dos actividades a la misma hora NO están en conflicto si no comparten
estudiantes inscritos, responsable ni ambiente.

Severidad
---------
* ``obligatorio``     – conflicto real.
* ``no_obligatorio``  – coincidencia de un estudiante con una actividad de asistencia
                        no obligatoria (sólo en la categoría estudiante).
* ``por_confirmar``   – discrepancia causada por un dato pendiente de confirmación.
* ``preferencia``     – incumplimiento de la disponibilidad declarada por estudiantes
                        (blanda por defecto; puede marcarse como dura en la configuración).

Cada par de sesiones se cuenta UNA sola vez por categoría; el campo ``afectados``
indica cuántos estudiantes comparten el choque.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from .modelo import DIAS, Dataset, Sesion, a_hhmm, se_superponen

CATEGORIAS = ["estudiante", "docente", "auxiliar", "aula", "laboratorio", "capacidad",
              "disponibilidad", "duracion", "disp_estudiante", "estudiante_irregular"]
NOMBRE_CATEGORIA = {
    "estudiante": "Estudiantes inscritos", "docente": "Docente", "auxiliar": "Auxiliar",
    "aula": "Aula", "laboratorio": "Laboratorio", "capacidad": "Capacidad del ambiente",
    "disponibilidad": "Disponibilidad (responsable / ambiente / franja)",
    "duracion": "Duración / carga horaria", "disp_estudiante": "Disponibilidad de estudiantes",
    "estudiante_irregular": "Estudiantes irregulares (referencial)",
}
DURAS_DEFECTO = ("estudiante", "docente", "auxiliar", "aula", "laboratorio", "capacidad",
                 "disponibilidad", "duracion")


@dataclass(frozen=True)
class Conflicto:
    categoria: str
    severidad: str
    dia: int
    inicio: int
    fin: int
    sesiones: tuple[str, ...]
    recurso: str
    descripcion: str
    afectados: int = 0          # nº de estudiantes afectados (cuando aplica)


def pares_superpuestos(sesiones: list[Sesion]) -> list[tuple[Sesion, Sesion]]:
    """Todos los pares de sesiones que se superponen (barrido ordenado por día)."""
    por_dia: dict[int, list[Sesion]] = defaultdict(list)
    for s in sesiones:
        por_dia[s.dia].append(s)
    pares = []
    for lista in por_dia.values():
        lista.sort(key=lambda s: (s.inicio, s.id))
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                if b.inicio >= a.fin:
                    break
                if se_superponen(a.inicio, a.fin, b.inicio, b.fin):
                    pares.append((a, b))
    return pares


def detectar_conflictos(ds: Dataset, sesiones: list[Sesion] | None = None,
                        escenario: str = "reprogramado") -> list[Conflicto]:
    """Detecta todos los conflictos del horario.

    Si ``sesiones`` es None se usan las sesiones vigentes del escenario.
    """
    if sesiones is None:
        sesiones = ds.sesiones_activas(escenario)
    nombre = _Nombres(ds, sesiones)
    inscritos = {s.id: ds.inscritos(s) for s in sesiones}
    con_disp = ds.con_disponibilidad()
    irregulares = {e.id for e in ds.estudiantes.values() if e.tipo == "irregular"}
    res: list[Conflicto] = []

    # ---- 1..5: recursos compartidos en sesiones simultáneas -----------------
    for a, b in pares_superpuestos(sesiones):
        ini, fin = max(a.inicio, b.inicio), min(a.fin, b.fin)
        par = tuple(sorted((a.id, b.id)))
        cuando = f"{DIAS[a.dia]} {a_hhmm(ini)}–{a_hhmm(fin)}"
        base = f"{nombre[a.id]} se superpone con {nombre[b.id]} ({cuando})"

        comunes = inscritos[a.id] & inscritos[b.id]
        regulares = {e for e in comunes if e not in irregulares}
        if regulares:
            sev = "obligatorio" if a.obligatoria and b.obligatoria else "no_obligatorio"
            muestra = ", ".join(_nombre_est(ds, e) for e in sorted(regulares)[:3])
            extra = f" y {len(regulares) - 3} más" if len(regulares) > 3 else ""
            res.append(Conflicto("estudiante", sev, a.dia, ini, fin, par, f"{len(regulares)} estudiante(s)",
                                 f"{base} – afecta a {muestra}{extra}", len(regulares)))
        elif comunes:
            res.append(Conflicto("estudiante_irregular", "preferencia", a.dia, ini, fin, par,
                                 f"{len(comunes)} irregular(es)", f"{base} – sólo afecta a estudiantes irregulares",
                                 len(comunes)))
        if a.responsable and a.responsable == b.responsable:
            p = ds.personas.get(a.responsable)
            cat = "auxiliar" if p and p.rol == "auxiliar" else "docente"
            res.append(Conflicto(cat, "obligatorio", a.dia, ini, fin, par, p.nombre if p else a.responsable, base))
        if a.ambiente and a.ambiente == b.ambiente:
            amb = ds.ambientes.get(a.ambiente)
            cat = "laboratorio" if amb and amb.tipo == "laboratorio" else "aula"
            res.append(Conflicto(cat, "obligatorio", a.dia, ini, fin, par, amb.nombre if amb else a.ambiente, base))

    for s in sesiones:
        n_ins = len(inscritos[s.id])
        # ---- 6: capacidad ----------------------------------------------------
        amb = ds.ambientes.get(s.ambiente) if s.ambiente else None
        if amb and amb.capacidad and n_ins > amb.capacidad:
            res.append(Conflicto("capacidad", "obligatorio", s.dia, s.inicio, s.fin, (s.id,), amb.nombre,
                                 f"{nombre[s.id]}: {n_ins} inscritos y {amb.nombre} admite {amb.capacidad}",
                                 n_ins))
        # ---- 7: disponibilidad -----------------------------------------------
        motivos = []
        if s.dia not in ds.dias:
            motivos.append(f"{DIAS[s.dia]} no es un día habilitado")
        if s.inicio < ds.hora_inicio or s.fin > ds.hora_fin:
            motivos.append(f"fuera de la franja institucional {a_hhmm(ds.hora_inicio)}–{a_hhmm(ds.hora_fin)}")
        if s.dias_permitidos and s.dia not in s.dias_permitidos:
            motivos.append(f"{DIAS[s.dia]} no está entre los días permitidos")
        if s.responsable and not ds.disponible(s.responsable, s.dia, s.inicio, s.fin):
            p = ds.personas.get(s.responsable)
            motivos.append(f"{p.nombre if p else s.responsable} no está disponible")
        if s.ambiente and not ds.disponible(s.ambiente, s.dia, s.inicio, s.fin):
            motivos.append(f"el ambiente {amb.nombre if amb else s.ambiente} no está disponible")
        if motivos:
            res.append(Conflicto("disponibilidad", "obligatorio", s.dia, s.inicio, s.fin, (s.id,),
                                 s.responsable or s.ambiente or "franja", f"{nombre[s.id]}: " + "; ".join(motivos)))
        # ---- 9: disponibilidad declarada por estudiantes ----------------------
        no_disp = [e for e in inscritos[s.id] & con_disp if not ds.disponible(e, s.dia, s.inicio, s.fin)]
        if no_disp:
            res.append(Conflicto("disp_estudiante", "preferencia", s.dia, s.inicio, s.fin, (s.id,),
                                 f"{len(no_disp)} estudiante(s)",
                                 f"{nombre[s.id]}: fuera de la disponibilidad de "
                                 + ", ".join(_nombre_est(ds, e) for e in sorted(no_disp)[:3])
                                 + (f" y {len(no_disp) - 3} más" if len(no_disp) > 3 else ""), len(no_disp)))
        # ---- 8a: duración de la sesión ----------------------------------------
        if s.duracion_requerida and s.duracion != s.duracion_requerida:
            sev = "por_confirmar" if s.estado == "pendiente_confirmacion" else "obligatorio"
            res.append(Conflicto("duracion", sev, s.dia, s.inicio, s.fin, (s.id,), s.asignatura,
                                 f"{nombre[s.id]}: dura {s.duracion} min y se requieren {s.duracion_requerida} min"
                                 + (" (dato pendiente de confirmación)" if sev == "por_confirmar" else "")))

    # ---- 8b: carga semanal por asignatura, paralelo y tipo ---------------------
    carga: dict[tuple[str, str, str], int] = defaultdict(int)
    for s in sesiones:
        if s.obligatoria:
            carga[(s.asignatura, s.paralelo, s.tipo)] += s.duracion
    for asig_par in sorted({(a, p) for a, p, _ in carga}):
        asig = ds.asignaturas.get(asig_par[0])
        if not asig:
            continue
        for tipo in ("teoria", "laboratorio", "auxiliatura"):
            req, real = asig.carga_requerida_min(tipo), carga.get((*asig_par, tipo), 0)
            if req and real != req:
                par_txt = f" paralelo {asig_par[1]}" if asig_par[1] else ""
                res.append(Conflicto("duracion", "obligatorio", -1, 0, 0, (f"{asig_par[0]}/{asig_par[1]}/{tipo}",),
                                     asig.nombre, f"Carga semanal de {tipo} de {asig.nombre}{par_txt}: "
                                     f"{real} min programados, {req} min requeridos"))
    return res


class _Nombres:
    """Nombres de sesiones calculados sólo cuando se necesitan (acelera el fitness)."""

    def __init__(self, ds: Dataset, sesiones: list[Sesion]):
        self.ds, self.por_id, self.cache = ds, {s.id: s for s in sesiones}, {}

    def __getitem__(self, sid: str) -> str:
        if sid not in self.cache:
            self.cache[sid] = self.ds.nombre_sesion(self.por_id[sid])
        return self.cache[sid]


def _nombre_est(ds: Dataset, eid: str) -> str:
    e = ds.estudiantes.get(eid)
    return e.nombre if e else eid


# --------------------------------------------------------------------------- #
# Resúmenes
# --------------------------------------------------------------------------- #
SEVERIDAD_TXT = {"obligatorio": "Obligatorio", "no_obligatorio": "Coincidencia no obligatoria",
                 "por_confirmar": "Pendiente de confirmación", "preferencia": "Preferencia (blanda)"}


def conflictos_a_df(ds: Dataset, conflictos: list[Conflicto]) -> pd.DataFrame:
    filas = []
    for c in sorted(conflictos, key=lambda c: (CATEGORIAS.index(c.categoria), c.dia, c.inicio)):
        filas.append({
            "Categoría": NOMBRE_CATEGORIA[c.categoria], "Severidad": SEVERIDAD_TXT[c.severidad],
            "Día": DIAS[c.dia] if c.dia >= 0 else "Semana",
            "Desde": a_hhmm(c.inicio) if c.dia >= 0 else "", "Hasta": a_hhmm(c.fin) if c.dia >= 0 else "",
            "Sesiones": " | ".join(c.sesiones), "Recurso": c.recurso,
            "Estudiantes afectados": c.afectados or None, "Detalle": c.descripcion,
        })
    df = pd.DataFrame(filas, columns=["Categoría", "Severidad", "Día", "Desde", "Hasta", "Sesiones",
                                      "Recurso", "Estudiantes afectados", "Detalle"])
    df["Estudiantes afectados"] = df["Estudiantes afectados"].astype("Int64")
    return df


def resumen_por_categoria(conflictos: list[Conflicto]) -> pd.DataFrame:
    filas = []
    for cat in CATEGORIAS:
        sub = [c for c in conflictos if c.categoria == cat]
        filas.append({"Categoría": NOMBRE_CATEGORIA[cat],
                      "Obligatorios": sum(c.severidad == "obligatorio" for c in sub),
                      "No obligatorios": sum(c.severidad == "no_obligatorio" for c in sub),
                      "Por confirmar": sum(c.severidad == "por_confirmar" for c in sub),
                      "Preferencias": sum(c.severidad == "preferencia" for c in sub)})
    return pd.DataFrame(filas)


def estado_restricciones(conflictos: list[Conflicto], duras: tuple[str, ...] = DURAS_DEFECTO) -> pd.DataFrame:
    """Tabla de restricciones cumplidas / incumplidas / pendientes por categoría."""
    filas = []
    for cat in CATEGORIAS:
        sub = [c for c in conflictos if c.categoria == cat]
        oblig = sum(c.severidad in ("obligatorio", "preferencia") for c in sub)
        pend = sum(c.severidad == "por_confirmar" for c in sub)
        if oblig:
            estado = "Incumplida" if cat in duras else "Preferencia incumplida"
        elif pend:
            estado = "Pendiente de dato"
        else:
            estado = "Cumplida"
        filas.append({"Restricción": NOMBRE_CATEGORIA[cat], "Tipo": "Dura" if cat in duras else "Blanda",
                      "Estado": estado, "Incumplimientos": oblig, "Por confirmar": pend})
    return pd.DataFrame(filas)


def sesiones_en_conflicto(conflictos: list[Conflicto], solo_obligatorios: bool = False,
                          categorias: tuple[str, ...] | None = None) -> set[str]:
    """Ids de sesiones involucradas en conflictos que se pueden resolver moviéndolas."""
    ids = set()
    movibles = categorias or ("estudiante", "docente", "auxiliar", "aula", "laboratorio",
                              "capacidad", "disponibilidad", "disp_estudiante", "estudiante_irregular")
    for c in conflictos:
        if solo_obligatorios and c.severidad not in ("obligatorio", "preferencia"):
            continue
        if c.categoria in movibles:
            ids.update(c.sesiones)
    return ids
