"""
Genera los conjuntos de datos del proyecto en data/.

    python scripts/generar_datos.py

* caso_real_2026_2 -> DATOS REALES: auxiliaturas y laboratorios informados y la
                      reprogramación del Lab. de IA. Las clases teóricas del horario
                      oficial quedan PENDIENTES hasta transcribir la captura.
* demo_pequeno     -> SIMULADO, 8 estudiantes, con solución factible conocida.
* demo_infactible  -> SIMULADO, dos teóricas FIJAS comparten estudiantes a la misma hora.
* demo_semestre    -> SIMULADO, 86 estudiantes con inscripciones individuales (regulares
                      e irregulares), docentes, auxiliares, capacidades y disponibilidades.

Ningún dato simulado representa a personas, aulas u horarios reales de la UTO.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.datos import RAIZ_DATOS, guardar_carpeta  # noqa: E402
from core.modelo import (Ambiente, Asignatura, Dataset, Disponibilidad, Estudiante,  # noqa: E402
                         Inscripcion, Persona, Sesion, a_minutos as m, se_superponen)

LUN, MAR, MIE, JUE, VIE, SAB = range(6)


# --------------------------------------------------------------------------- #
# 1. CASO REAL – Gestión 2026/2
# --------------------------------------------------------------------------- #
def caso_real() -> Dataset:
    ds = Dataset(
        nombre="Caso de estudio – Gestión 2026/2", tipo_datos="real",
        descripcion=("Horario de una estudiante de Ingeniería de Sistemas e Informática (UTO-FNI): "
                     "auxiliaturas y laboratorios adicionales informados y la reprogramación del Lab. de IA. "
                     "Las clases teóricas del horario oficial deben transcribirse desde la captura del "
                     "sistema académico."),
        dias=[LUN, MAR, MIE, JUE, VIE, SAB], hora_inicio=m("07:00"), hora_fin=m("21:00"),
        pendientes=[
            "Clases teóricas del horario oficial: PENDIENTES (no se recibió la captura del sistema académico).",
            "Paralelos: se usa A, único paralelo publicado para estas materias en el plantel docente (20/11/2026).",
            "Docentes, auxiliares y ambientes de cada actividad: no informados (no se inventan).",
            "Disponibilidad de docentes, auxiliares, ambientes y de la estudiante: no informada.",
            "Otros estudiantes inscritos: no informados; el caso considera sólo a la estudiante.",
            "Franja institucional 07:00–21:00, lunes a sábado: SUPUESTO, confirmar.",
            "Auxiliaturas y laboratorios se consideran reprogramables; su horario actual no implica que sean fijos.",
            "Todas las actividades se consideran de asistencia obligatoria: SUPUESTO, confirmar.",
            "Lab. de IA reprogramado (lunes 10:00–10:30): DURACIÓN POR CONFIRMAR (el original duraba 90 min).",
        ],
    )
    # Códigos verificados en los planes de estudio oficiales (data/catalogo/plan_estudios.csv);
    # paralelo A: es el único paralelo publicado para estas materias en el plantel docente.
    for clave, nombre, codigo in [
        ("GCAL", "Gestión de Calidad", "SIS 2830"), ("RNAC", "Realidad Nacional", "SIS 4940"),
        ("CELE", "Comercio Electrónico", "SIS 3662"), ("IA", "Inteligencia Artificial", "INF 3731"),
        ("GPRO", "Gestión de Proyectos", "SIS 2820"), ("IO4", "Investigación Operativa IV", "SIS 3843"),
        ("AUD", "Auditoría de Sistemas", "SIS 3930"),
    ]:
        ds.asignaturas[clave] = Asignatura(clave, nombre, codigo)
        ds.inscripciones.append(Inscripcion("EST", clave, "A"))
    ds.estudiantes["EST"] = Estudiante("EST", "Estudiante – caso de estudio")

    def ses(id_, asig, tipo, dia, ini, fin, **kw):
        base = dict(paralelo="A", fija=False, origen="adicional")
        base.update(kw)
        return Sesion(id=id_, asignatura=asig, tipo=tipo, dia=dia, inicio=m(ini), fin=m(fin), **base)

    ds.sesiones = [
        ses("AUX-GCAL", "GCAL", "auxiliatura", LUN, "14:30", "16:00"),
        ses("AUX-RNAC", "RNAC", "auxiliatura", MAR, "12:30", "14:00"),
        ses("AUX-CELE", "CELE", "auxiliatura", MAR, "16:30", "18:00",
            observacion="El martes 16:30–18:00 corresponde exclusivamente a Comercio Electrónico."),
        ses("AUX-IA", "IA", "auxiliatura", MIE, "10:30", "12:00",
            observacion="Aclaración: la auxiliatura de IA se realiza solamente el miércoles 10:30–12:00."),
        ses("AUX-GPRO", "GPRO", "auxiliatura", MIE, "16:30", "18:00"),
        ses("AUX-IO4", "IO4", "auxiliatura", MIE, "16:30", "18:00"),
        ses("LAB-AUD", "AUD", "laboratorio", MIE, "16:30", "18:00"),
        ses("LAB-IA-ORIG", "IA", "laboratorio", MIE, "16:30", "18:00", estado="reemplazada",
            observacion="Horario originalmente programado; reemplazado por LAB-IA-REPRO."),
        ses("LAB-IA-REPRO", "IA", "laboratorio", LUN, "10:00", "10:30", estado="pendiente_confirmacion",
            reemplaza="LAB-IA-ORIG", origen="reprogramacion", duracion_requerida=90,
            observacion="Reprogramación informada por conflictos. Duración de 30 min POR CONFIRMAR."),
        ses("AUX-AUD", "AUD", "auxiliatura", VIE, "14:30", "16:00"),
    ]
    return ds


# --------------------------------------------------------------------------- #
# 2. DEMO PEQUEÑO con solución factible conocida
# --------------------------------------------------------------------------- #
SOLUCION_CONOCIDA_DEMO = {   # sesión -> (día, inicio, ambiente)  [0 conflictos obligatorios]
    "LAB-BD-A": (LUN, m("10:00"), "LAB1"),
    "LAB-RED-B": (MAR, m("10:00"), "LAB1"),
    "AUX-PRG-A": (MIE, m("08:00"), "A2"),
    "AUX-RED-B": (MIE, m("10:00"), "A2"),
}


def demo_pequeno() -> Dataset:
    ds = Dataset(
        nombre="Demo pequeño (solución conocida)", tipo_datos="simulado",
        descripcion=("Datos SIMULADOS de verificación: 7 sesiones (3 fijas, 4 reprogramables) y 8 estudiantes. "
                     "E7 es irregular: cursa Programación (A) y Redes (B). Existe al menos una solución sin "
                     "conflictos obligatorios."),
        dias=[LUN, MAR, MIE], hora_inicio=m("08:00"), hora_fin=m("12:00"),
    )
    ds.asignaturas = {
        "BD": Asignatura("BD", "Base de Datos (sim.)", "SIM-101", horas_teoria=1.5, horas_laboratorio=1.5),
        "RED": Asignatura("RED", "Redes (sim.)", "SIM-102", horas_teoria=1.5, horas_laboratorio=1.5,
                          horas_auxiliatura=1.5),
        "PRG": Asignatura("PRG", "Programación (sim.)", "SIM-103", horas_teoria=1.5, horas_auxiliatura=1.5),
    }
    for i in range(1, 9):
        ds.estudiantes[f"E{i}"] = Estudiante(f"E{i}", f"Estudiante {i} (sim.)", "5")
    for e in ("E1", "E2", "E3"):
        ds.inscripciones += [Inscripcion(e, "BD", "A"), Inscripcion(e, "PRG", "A")]
    for e in ("E4", "E5", "E6", "E8"):
        ds.inscripciones.append(Inscripcion(e, "RED", "B"))
    ds.inscripciones += [Inscripcion("E7", "PRG", "A"), Inscripcion("E7", "RED", "B")]
    ds.inscripciones.append(Inscripcion("E8", "BD", "A", ["laboratorio"]))  # sólo recursa el laboratorio
    ds.personas = {"D1": Persona("D1", "Docente 1 (sim.)", "docente"),
                   "D2": Persona("D2", "Docente 2 (sim.)", "docente"),
                   "X1": Persona("X1", "Auxiliar 1 (sim.)", "auxiliar")}
    ds.ambientes = {"A1": Ambiente("A1", "Aula 1 (sim.)", "aula", 40),
                    "A2": Ambiente("A2", "Aula 2 (sim.)", "aula", 40),
                    "A3": Ambiente("A3", "Aula 3 pequeña (sim.)", "aula", 3),
                    "LAB1": Ambiente("LAB1", "Laboratorio 1 (sim.)", "laboratorio", 25)}
    ds.disponibilidad = [Disponibilidad("D1", LUN, m("08:00"), m("12:00")),
                         Disponibilidad("D1", MAR, m("08:00"), m("12:00")),
                         Disponibilidad("E5", LUN, m("08:00"), m("12:00")),   # preferencia (blanda)
                         Disponibilidad("E5", MAR, m("08:00"), m("12:00"))]
    S = lambda **kw: Sesion(**{"origen": "simulado", **kw})  # noqa: E731
    ds.sesiones = [
        S(id="TEO-BD-A", asignatura="BD", tipo="teoria", paralelo="A", dia=LUN, inicio=m("08:00"),
          fin=m("09:30"), responsable="D1", ambiente="A1", fija=True, origen="oficial"),
        S(id="TEO-RED-B", asignatura="RED", tipo="teoria", paralelo="B", dia=LUN, inicio=m("08:00"),
          fin=m("09:30"), responsable="D2", ambiente="A2", fija=True, origen="oficial"),
        S(id="TEO-PRG-A", asignatura="PRG", tipo="teoria", paralelo="A", dia=MAR, inicio=m("08:00"),
          fin=m("09:30"), responsable="D2", ambiente="A1", fija=True, origen="oficial"),
        S(id="LAB-BD-A", asignatura="BD", tipo="laboratorio", paralelo="A", dia=LUN, inicio=m("08:00"),
          fin=m("09:30"), responsable="D1", ambiente="LAB1", fija=False),
        S(id="LAB-RED-B", asignatura="RED", tipo="laboratorio", paralelo="B", dia=LUN, inicio=m("08:30"),
          fin=m("10:00"), responsable="D2", ambiente="LAB1", fija=False),
        S(id="AUX-PRG-A", asignatura="PRG", tipo="auxiliatura", paralelo="A", dia=MAR, inicio=m("08:00"),
          fin=m("09:30"), responsable="X1", ambiente="A2", fija=False),
        S(id="AUX-RED-B", asignatura="RED", tipo="auxiliatura", paralelo="B", dia=MAR, inicio=m("08:30"),
          fin=m("10:00"), responsable="X1", ambiente="A2", fija=False),
    ]
    return ds


# --------------------------------------------------------------------------- #
# 3. DEMO INFACTIBLE
# --------------------------------------------------------------------------- #
def demo_infactible() -> Dataset:
    ds = demo_pequeno()
    ds.nombre = "Demo infactible"
    ds.descripcion = ("Datos SIMULADOS: la teórica FIJA de Programación (A) se movió al lunes 08:30, encima de "
                      "la teórica FIJA de Base de Datos (A), que cursan los mismos estudiantes. Ningún horario "
                      "puede eliminar ese conflicto sin modificar actividades fijas.")
    for s in ds.sesiones:
        if s.id == "TEO-PRG-A":
            s.dia, s.inicio, s.fin, s.ambiente = LUN, m("08:30"), m("10:00"), "A3"
    return ds


# --------------------------------------------------------------------------- #
# 4. DEMO SEMESTRE (mediano, estudiantes individuales)
# --------------------------------------------------------------------------- #
def demo_semestre(semilla: int = 2026) -> Dataset:
    rng = random.Random(semilla)
    ds = Dataset(
        nombre="Demo semestre (mediano)", tipo_datos="simulado",
        descripcion=("Datos SIMULADOS: 9 asignaturas de 8.º y 9.º semestre, paralelos A/B, 86 estudiantes con "
                     "inscripciones individuales (regulares, que omiten alguna materia, e irregulares que mezclan "
                     "semestres y paralelos), docentes compartidos, auxiliares con disponibilidad limitada, "
                     "ambientes con capacidad y laboratorios concentrados deliberadamente en pocas franjas."),
        dias=[LUN, MAR, MIE, JUE, VIE, SAB], hora_inicio=m("07:00"), hora_fin=m("21:00"),
    )
    materias = {"8": [("M81", True), ("M82", True), ("M83", False), ("M84", True), ("M85", False)],
                "9": [("M91", True), ("M92", False), ("M93", True), ("M94", False)]}
    paralelos = {"8": ["A", "B"], "9": ["A"]}
    for sem, lista in materias.items():
        for clave, lab in lista:
            ds.asignaturas[clave] = Asignatura(clave, f"Materia {clave[1]}.{clave[2]} (sim.)", f"SIM-{clave}", sem,
                                               horas_teoria=3, horas_laboratorio=1.5 if lab else 0,
                                               horas_auxiliatura=1.5)
            ds.personas[f"D-{clave}"] = Persona(f"D-{clave}", f"Docente {clave} (sim.)", "docente")
    for i in range(1, 5):
        ds.personas[f"AX{i}"] = Persona(f"AX{i}", f"Auxiliar {i} (sim.)", "auxiliar")
        for d in range(5):
            ds.disponibilidad.append(Disponibilidad(f"AX{i}", d, m("14:00"), m("21:00")))
        ds.disponibilidad.append(Disponibilidad(f"AX{i}", (i + 1) % 5, m("08:00"), m("12:00")))
    for i in range(1, 5):
        ds.ambientes[f"A-10{i}"] = Ambiente(f"A-10{i}", f"Aula 10{i} (sim.)", "aula", 45)
    ds.ambientes["LAB-1"] = Ambiente("LAB-1", "Laboratorio 1 (sim.)", "laboratorio", 35)
    ds.ambientes["LAB-2"] = Ambiente("LAB-2", "Laboratorio 2 (sim.)", "laboratorio", 20)
    for d in range(5):   # el laboratorio 2 sólo está disponible de lunes a viernes hasta las 19:00
        ds.disponibilidad.append(Disponibilidad("LAB-2", d, m("07:00"), m("19:00")))

    # --- estudiantes regulares (omiten al azar 0 o 1 materia) ----------------
    n = 0
    for sem in ("8", "9"):
        for par in paralelos[sem]:
            for _ in range(24 if sem == "8" else 22):
                n += 1
                eid = f"S{n:03d}"
                ds.estudiantes[eid] = Estudiante(eid, f"Estudiante {n:03d} (sim.)", sem)
                omitir = rng.choice([None, None, rng.choice(materias[sem])[0]])
                for clave, _ in materias[sem]:
                    if clave != omitir:
                        ds.inscripciones.append(Inscripcion(eid, clave, par))

    # --- teóricas fijas, colocadas sin choques para los REGULARES ---------------
    pares_dias = [(LUN, MIE), (MAR, JUE), (MIE, VIE), (LUN, JUE), (MAR, VIE)]
    horas = [m(h) for h in ("07:00", "08:30", "10:00", "11:30", "14:30", "16:00")]
    aulas = [k for k, v in ds.ambientes.items() if v.tipo == "aula"]
    sesiones: list[Sesion] = []

    def libre(c: Sesion) -> bool:
        for o in sesiones:
            if o.dia == c.dia and se_superponen(o.inicio, o.fin, c.inicio, c.fin):
                if ds.inscritos(o) & ds.inscritos(c) or o.responsable == c.responsable or o.ambiente == c.ambiente:
                    return False
        return True

    for sem in ("8", "9"):
        for par in paralelos[sem]:
            for clave, _ in materias[sem]:
                ops = [(p, h, a) for p in pares_dias for h in horas for a in aulas]
                rng.shuffle(ops)
                ops.sort(key=lambda o: o[1] >= m("14:30"))
                for (d1, d2), h, a in ops:
                    c1 = Sesion(f"TEO-{clave}-{par}-1", clave, "teoria", par, d1, h, h + 90, f"D-{clave}", a,
                                origen="simulado")
                    c2 = Sesion(f"TEO-{clave}-{par}-2", clave, "teoria", par, d2, h, h + 90, f"D-{clave}", a,
                                origen="simulado")
                    if libre(c1) and libre(c2):
                        sesiones += [c1, c2]
                        break
                else:
                    raise RuntimeError(f"No se pudo colocar {clave}-{par}")
    ds.sesiones = sesiones

    # --- estudiantes irregulares: mezclan semestres/paralelos sin choques de teoría
    ofertas = [(c, p) for sem in ("8", "9") for p in paralelos[sem] for c, _ in materias[sem]]
    for k in range(16):
        n += 1
        eid = f"S{n:03d}"
        ds.estudiantes[eid] = Estudiante(eid, f"Estudiante {n:03d} (sim., irregular)", "8/9")
        rng.shuffle(ofertas)
        elegidas: list[tuple[str, str]] = []
        for clave, par in ofertas:
            if len(elegidas) >= 4 or any(c == clave for c, _ in elegidas):
                continue
            teo = [s for s in sesiones if s.asignatura == clave and s.paralelo == par]
            ya = [s for s in sesiones for c, p in elegidas if s.asignatura == c and s.paralelo == p]
            if all(not (a.dia == b.dia and se_superponen(a.inicio, a.fin, b.inicio, b.fin)) for a in teo for b in ya):
                elegidas.append((clave, par))
        for clave, par in elegidas:
            ds.inscripciones.append(Inscripcion(eid, clave, par))
        if k < 6:   # algunos trabajan: declaran disponibilidad sólo por la mañana (preferencia blanda)
            for d in range(6):
                ds.disponibilidad.append(Disponibilidad(eid, d, m("07:00"), m("14:00")))
    ds._cache_inscritos = {}

    # --- laboratorios y auxiliaturas reprogramables, concentrados ---------------
    franjas = [(MIE, m("16:30")), (MAR, m("16:30")), (LUN, m("14:30")), (VIE, m("14:30")), (MIE, m("10:30"))]
    claves = [c for lista in materias.values() for c, _ in lista]
    aux_de = {c: f"AX{i % 4 + 1}" for i, c in enumerate(claves)}
    for sem in ("8", "9"):
        for par in paralelos[sem]:
            for clave, lab in materias[sem]:
                if lab:
                    d, h = rng.choice(franjas)
                    ds.sesiones.append(Sesion(f"LAB-{clave}-{par}", clave, "laboratorio", par, d, h, h + 90,
                                              f"D-{clave}", rng.choice(["LAB-1", "LAB-2"]), fija=False,
                                              origen="simulado", tipo_ambiente="laboratorio"))
                d, h = rng.choice(franjas)
                ds.sesiones.append(Sesion(f"AUX-{clave}-{par}", clave, "auxiliatura", par, d, h, h + 90,
                                          aux_de[clave], rng.choice(aulas), fija=False, origen="simulado",
                                          tipo_ambiente="aula"))
    # sesión de repaso de asistencia NO obligatoria (paralelo R, inscripción voluntaria)
    for eid in list(ds.estudiantes)[:15]:
        ds.inscripciones.append(Inscripcion(eid, "M81", "R", ["auxiliatura"]))
    ds.sesiones.append(Sesion("REPASO-M81", "M81", "auxiliatura", "R", MIE, m("16:30"), m("18:00"), "AX1",
                              "A-104", fija=True, obligatoria=False, origen="simulado",
                              observacion="Repaso voluntario, asistencia NO obligatoria (sim.)"))
    ds._cache_inscritos = {}
    return ds


def main() -> None:
    for carpeta, ds in [("caso_real_2026_2", caso_real()), ("demo_pequeno", demo_pequeno()),
                        ("demo_infactible", demo_infactible()), ("demo_semestre", demo_semestre())]:
        guardar_carpeta(ds, RAIZ_DATOS / carpeta)
        print(f"{carpeta:18s} -> {len(ds.sesiones):3d} sesiones, {len(ds.estudiantes):3d} estudiantes, "
              f"{len(ds.inscripciones):3d} inscripciones ({ds.tipo_datos})")


if __name__ == "__main__":
    main()
