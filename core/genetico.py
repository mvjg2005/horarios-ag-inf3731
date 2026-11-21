"""
Algoritmo genético para la generación y optimización de horarios académicos.

Implementado desde cero (sólo biblioteca estándar de Python). Cada operador es una
función independiente para poder explicarlo y probarlo por separado.

Codificación
------------
* Un INDIVIDUO (cromosoma) es una propuesta completa de horario.
* Cada GEN corresponde a una sesión MODIFICABLE y vale ``(dia, inicio, ambiente)``.
* Las sesiones FIJAS no forman parte del cromosoma: se copian sin cambios en
  todos los individuos, por lo que nunca se alteran.
* La asignatura, el paralelo (y por tanto sus inscritos), el responsable y la DURACIÓN de cada sesión se
  conservan siempre: el gen sólo decide cuándo y dónde.

Restricciones garantizadas por construcción (dominio del gen)
-------------------------------------------------------------
Días habilitados, días permitidos de la sesión, franja institucional, duración
exacta, disponibilidad del responsable y tipo de ambiente compatible.

Restricciones evaluadas por la función fitness
----------------------------------------------
Duras  : choques entre actividades obligatorias de un mismo ESTUDIANTE INSCRITO,
         docente, auxiliar, aula y laboratorio; capacidad; disponibilidad del
         responsable y del ambiente; duración y carga.
Blandas: estabilidad (pocos cambios respecto al original), huecos de cada
         estudiante, franjas no preferidas, sábado, carga diaria excesiva,
         disponibilidad declarada por estudiantes y coincidencias no obligatorias.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .conflictos import DURAS_DEFECTO, NOMBRE_CATEGORIA, Conflicto, detectar_conflictos, sesiones_en_conflicto
from .modelo import DIAS, SAB, Dataset, Sesion, a_hhmm

Gen = tuple[int, int, Optional[str]]          # (día, inicio en minutos, ambiente)
Cromosoma = list[Gen]
PESO_DURO = 1000.0                             # para el valor escalar de fitness


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
PESOS_DEFECTO = {
    "cambio_dia": 3.0,         # mover una sesión a otro día
    "cambio_hora": 1.0,        # mover una sesión de hora en el mismo día
    "cambio_ambiente": 0.5,    # cambiar de aula/laboratorio
    "hueco": 0.1,              # por cada 30 min de hueco de un estudiante (promedio por estudiante)
    "franja": 2.0,             # sesión fuera de la franja preferida
    "sabado": 2.0,             # sesión modificable programada en sábado
    "carga_diaria": 1.0,       # por cada 30 min sobre el máximo diario de un estudiante
    "disp_estudiante": 1.0,    # por cada estudiante cuya disponibilidad declarada no se respeta
    "no_obligatorio": 2.0,     # coincidencia con actividad no obligatoria
    "relajada": 20.0,          # conflicto de una categoría que el usuario marcó como no obligatoria
    "irregular": 0.5,          # por cada estudiante/cohorte irregular afectado por un choque
    "mismo_dia": 4.0,          # dos clases teóricas de la misma materia y paralelo el mismo día
}


@dataclass
class ConfigAG:
    poblacion: int = 80
    generaciones: int = 300
    prob_cruce: float = 0.85
    prob_mutacion: float = 0.08       # probabilidad por gen
    elitismo: int = 2
    torneo_k: int = 3
    tipo_cruce: str = "uniforme"      # uniforme | un_punto | dos_puntos
    mutacion_dirigida: bool = False   # opcional: los genes en conflicto mutan con mayor probabilidad
    factor_dirigida: float = 4.0
    incluir_original: bool = True     # el horario original se incluye en la población inicial
    frac_heuristica: float = 0.1      # fracción de la población inicial construida con la heurística voraz
    tiempo_limite: float = 60.0       # segundos
    paciencia: int = 80               # generaciones sin mejora antes de detenerse
    umbral_blando: float = 0.0        # condición satisfactoria: 0 duros y blando <= umbral
    max_reinicios: int = 3            # inmigración aleatoria si se estanca sin solución válida
    semilla: Optional[int] = 42
    categorias_duras: tuple[str, ...] = DURAS_DEFECTO
    solo_sesiones: Optional[tuple[str, ...]] = None   # optimizar sólo estas sesiones (el resto queda fijo)
    pesos: dict = field(default_factory=lambda: dict(PESOS_DEFECTO))
    franja_preferida: tuple[int, int] = (7 * 60, 20 * 60)
    max_min_dia: int = 8 * 60         # carga diaria máxima preferida por estudiante
    escenario: str = "reprogramado"


def config_planificacion(**kw) -> ConfigAG:
    """Configuración por defecto para generar un horario COMPLETO (modo planificación).

    * No hay horario original que conservar: pesos de cambio en 0 y sin incluir el original.
    * Cromosomas largos (cientos de genes): mutación baja por gen (0,005 ≈ 2 genes por hijo).
    * 30 % de la población inicial se construye con la heurística voraz.
    Valores elegidos con ejecuciones de prueba sobre data/carrera_2026_2 (ver docs).
    """
    pesos = dict(PESOS_DEFECTO, cambio_dia=0.0, cambio_hora=0.0, cambio_ambiente=0.0)
    base = dict(prob_mutacion=0.005, frac_heuristica=0.3, incluir_original=False, pesos=pesos,
                generaciones=500, paciencia=150, tiempo_limite=180.0)
    base.update(kw)
    return ConfigAG(**base)


# --------------------------------------------------------------------------- #
# Problema: separa sesiones fijas y modificables y construye los dominios
# --------------------------------------------------------------------------- #
@dataclass
class Dominio:
    franjas: list[tuple[int, int]]           # pares válidos (día, inicio)
    ambientes: list[Optional[str]]


@dataclass
class Problema:
    ds: Dataset
    fijas: list[Sesion]
    modificables: list[Sesion]
    dominios: list[Dominio]
    escenario: str
    patrones: list[tuple[tuple[int, ...], int]] = field(default_factory=list)

    @property
    def original(self) -> Cromosoma:
        return [(s.dia, s.inicio, s.ambiente) for s in self.modificables]


def construir_dominio(ds: Dataset, s: Sesion) -> Dominio:
    """Todas las asignaciones (día, inicio, ambiente) que cumplen las restricciones
    unarias de la sesión: días, franja, duración exacta, disponibilidad del
    responsable, tipo de ambiente y capacidad suficiente para los inscritos."""
    dias = [d for d in ds.dias if not s.dias_permitidos or d in s.dias_permitidos]
    disp = ds.disponibilidad_de(s.responsable) if s.responsable else []
    franjas = []
    for d in dias:
        inicio = ds.hora_inicio
        while inicio + s.duracion <= ds.hora_fin:
            fin = inicio + s.duracion
            if not disp or any(x.dia == d and x.inicio <= inicio and fin <= x.fin for x in disp):
                franjas.append((d, inicio))
            inicio += ds.resolucion
    tipo = s.tipo_ambiente or (ds.ambientes[s.ambiente].tipo if s.ambiente in ds.ambientes else None)
    n_inscritos = len(ds.inscritos(s))
    if tipo is None:
        ambientes: list[Optional[str]] = [s.ambiente]       # sin dato de ambiente: se conserva
    else:
        ambientes = [a.id for a in ds.ambientes.values()
                     if a.tipo == tipo and (not a.capacidad or a.capacidad >= n_inscritos)] or [s.ambiente]
    return Dominio(franjas, ambientes)


def construir_problema(ds: Dataset, escenario: str = "reprogramado",
                       solo: Optional[tuple[str, ...]] = None) -> Problema:
    """Separa sesiones fijas y modificables. Si ``solo`` se indica, únicamente esas
    sesiones (y sólo si no son fijas) forman el cromosoma; las demás se mantienen."""
    activas = ds.sesiones_activas(escenario)
    es_gen = lambda s: not s.fija and (solo is None or s.id in solo)  # noqa: E731
    fijas = [s for s in activas if not es_gen(s)]
    modificables = [s for s in activas if es_gen(s)]
    return Problema(ds, fijas, modificables, [construir_dominio(ds, s) for s in modificables], escenario,
                    patrones_de_asistencia(ds, fijas + modificables))


def patrones_de_asistencia(ds: Dataset, orden: list[Sesion]) -> list[tuple[tuple[int, ...], int]]:
    """Agrupa a los estudiantes que asisten exactamente a las mismas sesiones obligatorias.

    Ej.: si 20 estudiantes regulares de 8A cursan las mismas 9 sesiones, sus huecos son
    idénticos y se calculan una sola vez con peso 20 (mismo resultado, mucho más rápido).
    """
    por_est: dict[str, list[int]] = {}
    irregulares = {e.id for e in ds.estudiantes.values() if e.tipo == "irregular"}
    for i, s in enumerate(orden):
        if s.obligatoria:
            for e in ds.inscritos(s) - irregulares:
                por_est.setdefault(e, []).append(i)
    conteo: dict[tuple[int, ...], int] = {}
    for idx in por_est.values():
        conteo[tuple(idx)] = conteo.get(tuple(idx), 0) + 1
    return list(conteo.items())


def decodificar(problema: Problema, crom: Cromosoma) -> list[Sesion]:
    """Cromosoma -> lista completa de sesiones (fijas + modificables reubicadas)."""
    return problema.fijas + [s.mover(d, i, a) for s, (d, i, a) in zip(problema.modificables, crom)]


# --------------------------------------------------------------------------- #
# B. Población inicial
# --------------------------------------------------------------------------- #
def gen_aleatorio(dom: Dominio, rng: random.Random) -> Gen:
    d, i = rng.choice(dom.franjas)
    return (d, i, rng.choice(dom.ambientes))


def poblacion_inicial(problema: Problema, n: int, rng: random.Random,
                      incluir_original: bool = True, n_heuristicos: int = 0) -> list[Cromosoma]:
    """Genera ``n`` horarios candidatos válidos respecto a las restricciones unarias:
    el horario original (opcional), ``n_heuristicos`` construidos con la heurística
    voraz y el resto aleatorios."""
    pob: list[Cromosoma] = []
    if incluir_original and problema.modificables:
        pob.append(list(problema.original))
    for _ in range(min(n_heuristicos, n - len(pob))):
        pob.append(individuo_heuristico(problema, rng))
    while len(pob) < n:
        pob.append([gen_aleatorio(dom, rng) for dom in problema.dominios])
    return pob


def individuo_heuristico(problema: Problema, rng: random.Random, muestras: int = 60) -> Cromosoma:
    """Construcción voraz aleatorizada (inicialización heurística de la población).

    1. Ordena las sesiones movibles de la más "difícil" a la más fácil (las que
       comparten más estudiantes/docente con otras sesiones van primero).
    2. Coloca cada una en la franja de su dominio que menos choques produce con las
       ya colocadas (entre ``muestras`` franjas al azar), desempatando al azar.
    No garantiza 0 conflictos: sólo da al AG mejores puntos de partida.
    """
    ds = problema.ds
    irregulares = {e.id for e in ds.estudiantes.values() if e.tipo == "irregular"}

    def recursos(s):
        ins = ds.inscritos(s)
        r = {("e", e) for e in ins - irregulares}
        if s.responsable:
            r.add(("p", s.responsable))
        return r, {("i", e) for e in ins & irregulares}

    ocupado: dict[tuple, list[tuple[int, int, int]]] = {}   # recurso -> [(día, inicio, fin)]

    def ocupar(rs, d, i, f):
        for r in rs:
            ocupado.setdefault(r, []).append((d, i, f))

    def choques(rs, d, i, f):
        return sum(1 for r in rs for (dd, a, b) in ocupado.get(r, ()) if dd == d and a < f and i < b)

    for s in problema.fijas:
        r, ir = recursos(s)
        ocupar(r | ir, s.dia, s.inicio, s.fin)
    info = [recursos(s) for s in problema.modificables]
    grado = [len(r) for r, _ in info]
    orden = sorted(range(len(problema.modificables)), key=lambda j: (-grado[j], rng.random()))
    crom: list = [None] * len(problema.modificables)
    dias_teoria: dict[tuple, set] = {}
    for j in orden:
        s, dom = problema.modificables[j], problema.dominios[j]
        reg, irr = info[j]
        cand = dom.franjas if len(dom.franjas) <= muestras else rng.sample(dom.franjas, muestras)
        clave = (s.asignatura, s.paralelo)
        mejor, mejor_costo = None, None
        for d, i in cand:
            f = i + s.duracion
            costo = 1000 * choques(reg, d, i, f) + 0.5 * choques(irr, d, i, f) + (2 if d == 5 else 0)
            if s.tipo == "teoria" and d in dias_teoria.get(clave, ()):
                costo += 4
            costo += rng.random() * 0.01
            if mejor_costo is None or costo < mejor_costo:
                mejor, mejor_costo = (d, i), costo
        d, i = mejor
        crom[j] = (d, i, rng.choice(dom.ambientes))
        ocupar(reg | irr, d, i, i + s.duracion)
        if s.tipo == "teoria":
            dias_teoria.setdefault(clave, set()).add(d)
    return crom


# --------------------------------------------------------------------------- #
# C. Función fitness
# --------------------------------------------------------------------------- #
@dataclass
class Evaluacion:
    duros: int                     # nº de conflictos obligatorios (restricciones duras)
    blando: float                  # penalización por preferencias
    fitness: float                 # 1 / (1 + 1000·duros + blando)  -> 1.0 = ideal
    conflictos: list[Conflicto]
    detalle_blando: dict
    en_conflicto: set[str]

    @property
    def clave(self) -> tuple[int, float]:
        """Orden lexicográfico: primero sin conflictos obligatorios, luego preferencias."""
        return (self.duros, round(self.blando, 6))


def _huecos_y_carga(problema: "Problema", sesiones: list[Sesion], max_min: int) -> tuple[float, float]:
    """Minutos de hueco y de exceso de carga diaria, PROMEDIADOS por estudiante regular
    (la escala no depende del número de inscritos). Usa los patrones de asistencia."""
    return _huecos_y_carga_arr(problema.patrones, [s.dia for s in sesiones], [s.inicio for s in sesiones],
                               [s.fin for s in sesiones], max_min)


def _huecos_y_carga_arr(patrones, dia, ini, fin, max_min) -> tuple[float, float]:
    huecos = exceso = 0.0
    total_est = 0
    for indices, n in patrones:
        por_dia: dict[int, list[tuple[int, int]]] = {}
        for i in indices:
            por_dia.setdefault(dia[i], []).append((ini[i], fin[i]))
        h = e = 0
        for intervalos in por_dia.values():
            intervalos.sort()
            fin_actual = intervalos[0][1]
            for a, b in intervalos:
                if a > fin_actual:
                    h += a - fin_actual
                fin_actual = max(fin_actual, b)
            e += max(0, sum(b - a for a, b in intervalos) - max_min)
        huecos += h * n
        exceso += e * n
        total_est += n
    total_est = total_est or 1
    return huecos / total_est, exceso / total_est


def evaluar(problema: Problema, crom: Cromosoma, cfg: ConfigAG) -> Evaluacion:
    """Evalúa un individuo usando la MISMA función de detección de conflictos del
    módulo 3, y le suma las penalizaciones blandas."""
    sesiones = decodificar(problema, crom)
    conflictos = detectar_conflictos(problema.ds, sesiones, problema.escenario)
    p = cfg.pesos
    duros = 0
    det = {k: 0.0 for k in DETALLE}
    for c in conflictos:
        if c.severidad in ("obligatorio", "preferencia"):
            if c.categoria in cfg.categorias_duras:
                duros += 1
            elif c.categoria == "disp_estudiante":
                det["disp_estudiante"] += p["disp_estudiante"] * max(1, c.afectados)
            elif c.categoria == "estudiante_irregular":
                det["irregulares"] += p["irregular"] * max(1, c.afectados)
            else:
                det["relajadas"] += p["relajada"]
        elif c.severidad == "no_obligatorio":
            det["no_obligatorio"] += p["no_obligatorio"]
        # "por_confirmar": se informa pero no se penaliza (el AG no puede resolverlo)
    for s, (d, i, a) in zip(problema.modificables, crom):
        if d != s.dia:
            det["cambios"] += p["cambio_dia"]
        elif i != s.inicio:
            det["cambios"] += p["cambio_hora"]
        if a != s.ambiente:
            det["cambios"] += p["cambio_ambiente"]
        if i < cfg.franja_preferida[0] or i + s.duracion > cfg.franja_preferida[1]:
            det["franja"] += p["franja"]
        if d == SAB:
            det["sabado"] += p["sabado"]
    huecos, exceso = _huecos_y_carga(problema, sesiones, cfg.max_min_dia)
    det["huecos"] = p["hueco"] * huecos / 30
    det["carga_diaria"] = p["carga_diaria"] * exceso / 30
    det["mismo_dia"] = p["mismo_dia"] * _mismo_dia([(s.dia, s.asignatura, s.paralelo, s.tipo, s.obligatoria)
                                                    for s in sesiones])
    blando = sum(det.values())
    return Evaluacion(duros, blando, 1.0 / (1.0 + PESO_DURO * duros + blando), conflictos, det,
                      sesiones_en_conflicto(conflictos))


DETALLE = ("relajadas", "no_obligatorio", "disp_estudiante", "irregulares", "cambios", "huecos", "franja",
           "sabado", "carga_diaria", "mismo_dia")


def _mismo_dia(filas) -> int:
    """Pares de clases TEÓRICAS de la misma materia y paralelo programadas el mismo día."""
    conteo: dict[tuple, int] = {}
    for dia, asig, par, tipo, oblig in filas:
        if tipo == "teoria" and oblig:
            k = (asig, par, dia)
            conteo[k] = conteo.get(k, 0) + 1
    return sum(n * (n - 1) // 2 for n in conteo.values())


# --------------------------------------------------------------------------- #
# D. Selección por torneo
# --------------------------------------------------------------------------- #
def seleccion_torneo(pob: list[Cromosoma], evals: list[Evaluacion], k: int,
                     rng: random.Random) -> Cromosoma:
    """Elige k individuos al azar y devuelve el mejor según (duros, blando).

    Se prefiere el torneo a la ruleta porque: (1) trabaja con la comparación
    lexicográfica duros/blando sin necesidad de escalar el fitness, (2) no se ve
    afectado por la gran diferencia numérica entre penalizaciones duras y blandas,
    que en la ruleta haría que un solo individuo acapare toda la probabilidad, y
    (3) la presión selectiva se regula con un único parámetro k.
    """
    indices = rng.sample(range(len(pob)), min(k, len(pob)))
    ganador = min(indices, key=lambda i: evals[i].clave)
    return pob[ganador]


# --------------------------------------------------------------------------- #
# E. Cruzamiento
# --------------------------------------------------------------------------- #
def cruce(p1: Cromosoma, p2: Cromosoma, tipo: str, rng: random.Random) -> tuple[Cromosoma, Cromosoma]:
    """Combina dos horarios. Cada gen es la asignación completa de una sesión, por lo
    que los hijos siempre conservan todas las sesiones y sus duraciones."""
    n = len(p1)
    if n < 2:
        return list(p1), list(p2)
    if tipo == "un_punto":
        c = rng.randint(1, n - 1)
        return p1[:c] + p2[c:], p2[:c] + p1[c:]
    if tipo == "dos_puntos":
        a, b = sorted(rng.sample(range(1, n), 2)) if n > 2 else (1, 1)
        return p1[:a] + p2[a:b] + p1[b:], p2[:a] + p1[a:b] + p2[b:]
    h1, h2 = [], []                       # uniforme
    for g1, g2 in zip(p1, p2):
        if rng.random() < 0.5:
            h1.append(g1); h2.append(g2)  # noqa: E702
        else:
            h1.append(g2); h2.append(g1)  # noqa: E702
    return h1, h2


# --------------------------------------------------------------------------- #
# F. Mutación controlada
# --------------------------------------------------------------------------- #
def mutar_gen(gen: Gen, dom: Dominio, rng: random.Random) -> Gen:
    """Cambia el DÍA, la HORA o el AMBIENTE de una sesión, dentro de su dominio."""
    d, i, a = gen
    ops = ["dia", "hora"] + (["ambiente"] if len(dom.ambientes) > 1 else [])
    op = rng.choice(ops)
    if op == "ambiente":
        return (d, i, rng.choice([x for x in dom.ambientes if x != a] or dom.ambientes))
    if op == "dia":
        otros = [f for f in dom.franjas if f[0] != d]
        misma_hora = [f for f in otros if f[1] == i]
        opciones = misma_hora or otros or dom.franjas
    else:
        opciones = [f for f in dom.franjas if f[0] == d and f[1] != i] or dom.franjas
    nd, ni = rng.choice(opciones)
    if a not in dom.ambientes:
        a = rng.choice(dom.ambientes)
    return (nd, ni, a)


def mutacion(crom: Cromosoma, problema: Problema, pm: float, rng: random.Random,
             en_conflicto: set[str] | None = None, factor: float = 1.0) -> Cromosoma:
    """Recorre los genes y muta cada uno con probabilidad pm (o pm·factor si la
    sesión participa en un conflicto y la mutación dirigida está activa)."""
    nuevo = list(crom)
    for j, (s, dom) in enumerate(zip(problema.modificables, problema.dominios)):
        prob = pm * factor if en_conflicto and s.id in en_conflicto else pm
        if rng.random() < min(1.0, prob):
            nuevo[j] = mutar_gen(nuevo[j], dom, rng)
    return nuevo


# --------------------------------------------------------------------------- #
# Diagnóstico de restricciones imposibles
# --------------------------------------------------------------------------- #
def clasificar_conflicto(c: Conflicto, ids_fijas: set[str]) -> str:
    """Explica por qué un conflicto obligatorio puede no tener solución."""
    if c.categoria == "duracion":
        return "no resoluble por el AG: las duraciones y la carga se conservan"
    if set(c.sesiones) <= ids_fijas:
        return "involucra sólo actividades fijas o no incluidas en la optimización"
    return "no resuelto con la configuración usada"


def diagnosticar(problema: Problema, cfg: ConfigAG) -> list[str]:
    """Detecta, antes de optimizar, restricciones que ningún horario puede cumplir:
    sesiones sin franjas válidas, conflictos entre actividades fijas y
    discrepancias de duración/carga (que el AG no altera por diseño)."""
    avisos = []
    for s, dom in zip(problema.modificables, problema.dominios):
        if not dom.franjas:
            avisos.append(f"La sesión {s.id} ({problema.ds.nombre_sesion(s)}) no tiene ninguna franja "
                          f"válida: revise la disponibilidad del responsable, los días permitidos o la franja.")
    ids_fijas = {s.id for s in problema.fijas}
    todas = decodificar(problema, problema.original)
    for c in detectar_conflictos(problema.ds, todas, problema.escenario):
        if c.severidad not in ("obligatorio", "preferencia") or c.categoria not in cfg.categorias_duras:
            continue
        motivo = clasificar_conflicto(c, ids_fijas)
        if motivo != "no resuelto con la configuración usada":
            avisos.append(f"[{NOMBRE_CATEGORIA[c.categoria]}] {c.descripcion} — {motivo}.")
    return avisos


# --------------------------------------------------------------------------- #
# Resultado y bucle principal
# --------------------------------------------------------------------------- #
@dataclass
class ResultadoAG:
    config: ConfigAG
    mejor: Cromosoma
    eval_mejor: Evaluacion
    eval_original: Evaluacion
    historial: list[dict]
    generaciones: int
    tiempo: float
    motivo_parada: str
    diagnostico: list[str]
    sesiones_propuestas: list[Sesion]
    cambios: list[dict]

    @property
    def factible(self) -> bool:
        return self.eval_mejor.duros == 0

    def mensaje(self) -> str:
        if self.factible:
            return ("Se obtuvo un horario SIN conflictos obligatorios para los datos y restricciones "
                    f"configurados (penalización por preferencias: {self.eval_mejor.blando:.2f}).")
        return (f"NO se encontró un horario válido: persisten {self.eval_mejor.duros} conflicto(s) "
                "obligatorio(s). Revise las restricciones pendientes.")

    def restricciones_pendientes(self) -> list[str]:
        ids_fijas = {s.id for s in self.sesiones_propuestas if s.fija}
        lista = []
        for c in self.eval_mejor.conflictos:
            if c.severidad in ("obligatorio", "preferencia") and c.categoria in self.config.categorias_duras:
                causa = clasificar_conflicto(c, ids_fijas)
                lista.append(f"[{NOMBRE_CATEGORIA[c.categoria]}] {c.descripcion} — {causa}")
            elif c.severidad == "por_confirmar":
                lista.append(f"[Por confirmar] {c.descripcion}")
        return lista


def ejecutar_ag(ds: Dataset, cfg: ConfigAG,
                progreso: Callable[[int, dict], None] | None = None) -> ResultadoAG:
    """Ejecuta el algoritmo genético completo y devuelve el mejor horario encontrado."""
    t0 = time.perf_counter()
    rng = random.Random(cfg.semilla)
    problema = construir_problema(ds, cfg.escenario, cfg.solo_sesiones)
    diagnostico = diagnosticar(problema, cfg)
    cache: dict[tuple, Evaluacion] = {}
    from .evaluador_rapido import EvaluadorRapido
    rapido = EvaluadorRapido(problema, cfg)   # mismo resultado que evaluar(), sin textos

    def ev(c: Cromosoma) -> Evaluacion:
        k = tuple(c)
        if k not in cache:
            cache[k] = rapido.evaluar(c)
        return cache[k]

    eval_original = evaluar(problema, problema.original, cfg)
    if not problema.modificables or any(not d.franjas for d in problema.dominios):
        motivo = ("No hay sesiones modificables: el horario no puede optimizarse."
                  if not problema.modificables else "Existe una sesión sin franjas válidas.")
        return _resultado(problema, cfg, problema.original, eval_original, eval_original, [], 0,
                          time.perf_counter() - t0, motivo, diagnostico)

    pob = poblacion_inicial(problema, cfg.poblacion, rng, cfg.incluir_original,
                            int(round(cfg.frac_heuristica * cfg.poblacion)))
    evals = [ev(c) for c in pob]
    mejor_idx = min(range(len(pob)), key=lambda i: evals[i].clave)
    mejor, eval_mejor = list(pob[mejor_idx]), evals[mejor_idx]
    historial: list[dict] = []
    sin_mejora, motivo, gen, reinicios = 0, "Se alcanzó el número máximo de generaciones.", 0, 0

    for gen in range(1, cfg.generaciones + 1):
        # --- G. elitismo --------------------------------------------------------
        orden = sorted(range(len(pob)), key=lambda i: evals[i].clave)
        nueva: list[Cromosoma] = []
        vistos = set()
        for i in orden:
            if len(nueva) >= cfg.elitismo:
                break
            if tuple(pob[i]) not in vistos:
                nueva.append(list(pob[i])); vistos.add(tuple(pob[i]))  # noqa: E702
        # --- D, E, F: selección, cruce y mutación --------------------------------
        while len(nueva) < cfg.poblacion:
            p1 = seleccion_torneo(pob, evals, cfg.torneo_k, rng)
            p2 = seleccion_torneo(pob, evals, cfg.torneo_k, rng)
            h1, h2 = cruce(p1, p2, cfg.tipo_cruce, rng) if rng.random() < cfg.prob_cruce else (list(p1), list(p2))
            for h, padre in ((h1, p1), (h2, p2)):
                conf = ev(padre).en_conflicto if cfg.mutacion_dirigida else None
                nueva.append(mutacion(h, problema, cfg.prob_mutacion, rng, conf, cfg.factor_dirigida))
        pob = nueva[:cfg.poblacion]
        evals = [ev(c) for c in pob]

        i_best = min(range(len(pob)), key=lambda i: evals[i].clave)
        if evals[i_best].clave < eval_mejor.clave:
            mejor, eval_mejor, sin_mejora = list(pob[i_best]), evals[i_best], 0
        else:
            sin_mejora += 1
        fits = [e.fitness for e in evals]
        registro = {
            "generacion": gen, "mejor_fitness": eval_mejor.fitness,
            "fitness_promedio": sum(fits) / len(fits), "peor_fitness": min(fits),
            "mejor_duros": eval_mejor.duros, "mejor_blando": round(eval_mejor.blando, 4),
            "duros_promedio": sum(e.duros for e in evals) / len(evals),
            "diversidad": len({tuple(c) for c in pob}) / len(pob),
        }
        historial.append(registro)
        if progreso:
            progreso(gen, registro)

        # --- H. criterios de parada -------------------------------------------
        if eval_mejor.duros == 0 and eval_mejor.blando <= cfg.umbral_blando + 1e-9:
            motivo = "Condición satisfactoria: sin conflictos obligatorios y preferencias dentro del umbral."
            break
        if time.perf_counter() - t0 >= cfg.tiempo_limite:
            motivo = f"Se alcanzó el límite de tiempo ({cfg.tiempo_limite:.0f} s)."
            break
        if sin_mejora >= cfg.paciencia:
            if eval_mejor.duros > 0 and reinicios < cfg.max_reinicios:
                # Inmigración aleatoria: se conserva la mitad mejor y se reemplaza el resto por
                # individuos nuevos para escapar de un óptimo local SIN solución válida.
                orden = sorted(range(len(pob)), key=lambda i: evals[i].clave)
                mitad = [pob[i] for i in orden[: len(pob) // 2]]
                nuevos = poblacion_inicial(problema, len(pob) - len(mitad), rng, incluir_original=False)
                pob = mitad + nuevos
                evals = [ev(c) for c in pob]
                reinicios += 1
                sin_mejora = 0
                registro["reinicio"] = reinicios
                continue
            motivo = f"Estancamiento: {cfg.paciencia} generaciones sin mejora."
            if reinicios:
                motivo += f" Se aplicaron {reinicios} inmigraciones aleatorias."
            break

    eval_final = evaluar(problema, mejor, cfg)        # reporte con el detector completo
    return _resultado(problema, cfg, mejor, eval_final, eval_original, historial, gen,
                      time.perf_counter() - t0, motivo, diagnostico)


def _resultado(problema, cfg, mejor, eval_mejor, eval_original, historial, gen, tiempo, motivo,
               diagnostico) -> ResultadoAG:
    sesiones = decodificar(problema, mejor)
    cambios = []
    for s, (d, i, a) in zip(problema.modificables, mejor):
        if (d, i, a) != (s.dia, s.inicio, s.ambiente):
            cambios.append({
                "Sesión": s.id, "Actividad": problema.ds.nombre_sesion(s),
                "Original": f"{DIAS[s.dia]} {a_hhmm(s.inicio)}–{a_hhmm(s.fin)}"
                            + (f" ({s.ambiente})" if s.ambiente else ""),
                "Propuesta": f"{DIAS[d]} {a_hhmm(i)}–{a_hhmm(i + s.duracion)}" + (f" ({a})" if a else ""),
            })
    return ResultadoAG(cfg, mejor, eval_mejor, eval_original, historial, gen, tiempo, motivo,
                       diagnostico, sesiones, cambios)


def reduccion_porcentual(antes: int, despues: int) -> Optional[float]:
    """Porcentaje de reducción de conflictos; None cuando no corresponde (antes = 0)."""
    if antes <= 0:
        return None
    return 100.0 * (antes - despues) / antes


__all__ = ["ConfigAG", "PESOS_DEFECTO", "Problema", "construir_problema", "construir_dominio",
           "poblacion_inicial", "evaluar", "seleccion_torneo", "cruce", "mutar_gen", "mutacion",
           "diagnosticar", "ejecutar_ag", "ResultadoAG", "reduccion_porcentual"]
