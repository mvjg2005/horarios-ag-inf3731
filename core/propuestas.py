"""
Propuestas de horario y su ciclo de revisión dentro del prototipo.

    pendiente ──aprobar──► aprobada ──aplicar──► aplicada
        └────rechazar────► rechazada

* Una propuesta guarda sólo los CAMBIOS (sesión -> nuevo día/hora/ambiente).
* Antes de aprobar se REEVALÚA contra los datos actuales: sólo puede aprobarse si no
  tiene conflictos obligatorios (no se presenta como válida una alternativa inviable).
* Al aplicar se crea una VERSIÓN reprogramada de cada sesión movida; la original se
  conserva con estado ``reemplazada`` y nunca se cuentan ambas como vigentes.

El sistema no sustituye las decisiones de las autoridades universitarias: "aprobar"
significa aprobar dentro del prototipo.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

from .conflictos import DURAS_DEFECTO, Conflicto, detectar_conflictos
from .genetico import ResultadoAG, reduccion_porcentual
from .modelo import DIAS, Dataset, Sesion, a_hhmm

ESTADOS_PROPUESTA = ["pendiente", "aprobada", "rechazada", "aplicada"]


@dataclass
class Propuesta:
    id: str
    autor: str
    origen: str                       # "AG" | "manual"
    descripcion: str
    escenario: str
    cambios: list[dict]               # {"sesion","dia","inicio","fin","ambiente"}
    duros_antes: int
    duros_despues: int
    blando: Optional[float] = None
    fitness: Optional[float] = None
    semilla: Optional[int] = None
    configuracion: dict = field(default_factory=dict)
    pendientes: list[str] = field(default_factory=list)
    estado: str = "pendiente"
    comentario: str = ""
    revisada_por: str = ""
    creada: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    revisada: str = ""

    @property
    def factible(self) -> bool:
        return self.duros_despues == 0

    @property
    def reduccion(self) -> Optional[float]:
        return reduccion_porcentual(self.duros_antes, self.duros_despues)

    def sesiones_involucradas(self) -> set[str]:
        return {c["sesion"] for c in self.cambios}

    def texto_cambios(self, ds: Dataset) -> list[dict]:
        orig = {s.id: s for s in ds.sesiones}
        filas = []
        for c in self.cambios:
            s = orig.get(c["sesion"])
            filas.append({
                "Sesión": c["sesion"], "Actividad": ds.nombre_sesion(s) if s else "(ya no existe)",
                "Antes": f"{DIAS[s.dia]} {a_hhmm(s.inicio)}–{a_hhmm(s.fin)}" + (f" ({s.ambiente})" if s and s.ambiente else "")
                if s else "", "Propuesta": f"{DIAS[c['dia']]} {a_hhmm(c['inicio'])}–{a_hhmm(c['fin'])}"
                + (f" ({c['ambiente']})" if c.get("ambiente") else "")})
        return filas


# --------------------------------------------------------------------------- #
# Creación
# --------------------------------------------------------------------------- #
def _siguiente_id(existentes: list[Propuesta]) -> str:
    n = max([int(p.id.split("-")[1]) for p in existentes if p.id.startswith("P-")] + [0]) + 1
    return f"P-{n:03d}"


def desde_resultado(r: ResultadoAG, autor: str, descripcion: str, existentes: list[Propuesta]) -> Propuesta:
    """Convierte una ejecución del AG en una propuesta pendiente de revisión."""
    prop_ses = {s.id: s for s in r.sesiones_propuestas}
    cambios = []
    for c in r.cambios:
        s = prop_ses[c["Sesión"]]
        cambios.append({"sesion": s.id, "dia": s.dia, "inicio": s.inicio, "fin": s.fin, "ambiente": s.ambiente})
    cfg = {k: (list(v) if isinstance(v, tuple) else v) for k, v in vars(r.config).items()}
    return Propuesta(_siguiente_id(existentes), autor, "AG", descripcion, r.config.escenario, cambios,
                     r.eval_original.duros, r.eval_mejor.duros, round(r.eval_mejor.blando, 4),
                     r.eval_mejor.fitness, r.config.semilla, cfg, r.restricciones_pendientes())


def aplicar_cambios(ds: Dataset, cambios: list[dict], escenario: str) -> list[Sesion]:
    """Sesiones vigentes resultantes de aplicar los cambios (sin modificar ``ds``)."""
    por_id = {c["sesion"]: c for c in cambios}
    res = []
    for s in ds.sesiones_activas(escenario):
        c = por_id.get(s.id)
        res.append(s.mover(c["dia"], c["inicio"], c.get("ambiente")) if c else s)
    return res


def evaluar_cambios(ds: Dataset, cambios: list[dict], escenario: str,
                    duras: tuple[str, ...] = DURAS_DEFECTO) -> tuple[int, int, list[Conflicto]]:
    """(conflictos obligatorios antes, después, lista de conflictos después)."""
    contar = lambda cs: sum(1 for c in cs if c.severidad in ("obligatorio", "preferencia")  # noqa: E731
                            and c.categoria in duras)
    antes = detectar_conflictos(ds, escenario=escenario)
    despues = detectar_conflictos(ds, aplicar_cambios(ds, cambios, escenario), escenario)
    return contar(antes), contar(despues), despues


def propuesta_manual(ds: Dataset, sesion_id: str, dia: int, inicio: int, ambiente: Optional[str],
                     autor: str, motivo: str, escenario: str, existentes: list[Propuesta]) -> Propuesta:
    """Propuesta de cambio hecha por un docente o auxiliar; se evalúa con las mismas reglas."""
    s = next(x for x in ds.sesiones_activas(escenario) if x.id == sesion_id)
    cambios = [{"sesion": s.id, "dia": dia, "inicio": inicio, "fin": inicio + s.duracion, "ambiente": ambiente}]
    antes, despues, conf = evaluar_cambios(ds, cambios, escenario)
    pend = [c.descripcion for c in conf if c.severidad == "obligatorio" and c.categoria in DURAS_DEFECTO]
    return Propuesta(_siguiente_id(existentes), autor, "manual", motivo, escenario, cambios, antes, despues,
                     pendientes=pend)


# --------------------------------------------------------------------------- #
# Revisión
# --------------------------------------------------------------------------- #
def validar_vigencia(ds: Dataset, p: Propuesta) -> Optional[str]:
    activas = {s.id for s in ds.sesiones_activas(p.escenario)}
    faltan = [c["sesion"] for c in p.cambios if c["sesion"] not in activas]
    if faltan:
        return f"Las sesiones {', '.join(faltan)} ya no están vigentes (los datos cambiaron)."
    return None


def aprobar(ds: Dataset, p: Propuesta, revisor: str, comentario: str = "") -> tuple[bool, str]:
    """Aprueba sólo si, reevaluada con los datos actuales, no tiene conflictos obligatorios."""
    if p.estado != "pendiente":
        return False, f"La propuesta está {p.estado}; sólo se aprueban propuestas pendientes."
    error = validar_vigencia(ds, p)
    if error:
        return False, error
    antes, despues, conf = evaluar_cambios(ds, p.cambios, p.escenario)
    p.duros_antes, p.duros_despues = antes, despues
    if despues > 0:
        return False, (f"No se puede aprobar: con los datos actuales la propuesta tiene {despues} "
                       "conflicto(s) obligatorio(s). Una alternativa inviable no se presenta como válida.")
    p.estado, p.revisada_por, p.comentario = "aprobada", revisor, comentario
    p.revisada = datetime.now().isoformat(timespec="seconds")
    return True, "Propuesta aprobada dentro del prototipo."


def rechazar(p: Propuesta, revisor: str, comentario: str) -> tuple[bool, str]:
    if p.estado not in ("pendiente", "aprobada"):
        return False, f"La propuesta está {p.estado}."
    p.estado, p.revisada_por, p.comentario = "rechazada", revisor, comentario
    p.revisada = datetime.now().isoformat(timespec="seconds")
    return True, "Propuesta rechazada."


def aplicar(ds: Dataset, p: Propuesta) -> Dataset:
    """Devuelve un NUEVO Dataset con la propuesta aplicada como versión reprogramada.

    Para cada sesión movida: la sesión vigente pasa a ``reemplazada`` y se agrega una
    nueva sesión ``<id>-R<n>`` con ``reemplaza = <id>``. El original se conserva.
    """
    if p.estado != "aprobada":
        raise ValueError("Sólo se aplican propuestas aprobadas.")
    error = validar_vigencia(ds, p)
    if error:
        raise ValueError(error)
    nuevo = ds.copia()
    ids = {s.id for s in nuevo.sesiones}
    por_id = {c["sesion"]: c for c in p.cambios}
    agregadas = []
    for s in nuevo.sesiones:
        c = por_id.get(s.id)
        if not c or s.estado == "reemplazada":
            continue
        base = re.sub(r"-R\d+$", "", s.id)
        n = 1
        while f"{base}-R{n}" in ids:
            n += 1
        nueva = replace(s.mover(c["dia"], c["inicio"], c.get("ambiente")), id=f"{base}-R{n}", reemplaza=s.id,
                        origen="reprogramacion",
                        observacion=f"Reprogramada por la propuesta {p.id}. {s.observacion}".strip())
        ids.add(nueva.id)
        s.estado = "reemplazada"
        agregadas.append(nueva)
    nuevo.sesiones.extend(agregadas)
    p.estado = "aplicada"
    return nuevo


# --------------------------------------------------------------------------- #
# Persistencia (archivo separado: nunca toca el horario original)
# --------------------------------------------------------------------------- #
def guardar_propuestas(propuestas: list[Propuesta], carpeta: Path) -> None:
    (Path(carpeta) / "propuestas.json").write_text(
        json.dumps([asdict(p) for p in propuestas], ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_propuestas(carpeta: Path) -> list[Propuesta]:
    f = Path(carpeta) / "propuestas.json"
    if not f.exists():
        return []
    return [Propuesta(**d) for d in json.loads(f.read_text(encoding="utf-8"))]
