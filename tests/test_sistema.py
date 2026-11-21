"""Pruebas automáticas del sistema (ejecutar con:  python -m pytest -v)."""
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.conflictos import detectar_conflictos, estado_restricciones  # noqa: E402
from core.datos import RAIZ_DATOS, cargar_carpeta, dataset_a_excel, excel_a_dataset  # noqa: E402
from core.evaluacion import comparar_configuraciones  # noqa: E402
from core.genetico import (ConfigAG, construir_problema, cruce, ejecutar_ag, evaluar,  # noqa: E402
                           mutacion, poblacion_inicial)
from core.modelo import (Ambiente, Asignatura, Dataset, Disponibilidad, Estudiante, Inscripcion,  # noqa: E402
                         Persona, Sesion, a_minutos as m, se_superponen)
from core import propuestas as P  # noqa: E402
from scripts.generar_datos import SOLUCION_CONOCIDA_DEMO  # noqa: E402

CFG = ConfigAG(poblacion=40, generaciones=150, tiempo_limite=30, paciencia=60, semilla=7)


@pytest.fixture
def demo():
    return cargar_carpeta(RAIZ_DATOS / "demo_pequeno")


@pytest.fixture
def infactible():
    return cargar_carpeta(RAIZ_DATOS / "demo_infactible")


@pytest.fixture
def real():
    return cargar_carpeta(RAIZ_DATOS / "caso_real_2026_2")


# --------------------------------------------------------------------------- #
# Mini conjunto de datos para pruebas unitarias
#   E1 cursa X(A) y Y(A); E2 cursa Z(B). Docente D, auxiliar AX, aula AU (cap. 2), lab LB.
# --------------------------------------------------------------------------- #
def _mini(sesiones, inscripciones=None):
    ds = Dataset("mini", "simulado", dias=[0, 1, 2], hora_inicio=m("07:00"), hora_fin=m("21:00"))
    ds.asignaturas = {k: Asignatura(k, k) for k in ("X", "Y", "Z")}
    ds.estudiantes = {e: Estudiante(e, e) for e in ("E1", "E2", "E3")}
    ds.inscripciones = inscripciones if inscripciones is not None else [
        Inscripcion("E1", "X", "A"), Inscripcion("E1", "Y", "A"), Inscripcion("E2", "Z", "B")]
    ds.personas = {"D": Persona("D", "D", "docente"), "D2": Persona("D2", "D2", "docente"),
                   "AX": Persona("AX", "AX", "auxiliar")}
    ds.ambientes = {"AU": Ambiente("AU", "AU", "aula", 2), "AU2": Ambiente("AU2", "AU2", "aula", 40),
                    "LB": Ambiente("LB", "LB", "laboratorio", 30)}
    ds.sesiones = sesiones
    return ds


def _s(id_, asig, par, ini, fin, dia=0, **kw):
    kw.setdefault("tipo", "teoria")
    return Sesion(id=id_, asignatura=asig, paralelo=par, dia=dia, inicio=m(ini), fin=m(fin), **kw)


def _cats(conf, sev="obligatorio"):
    return sorted(c.categoria for c in conf if c.severidad == sev)


# 1. Conflictos entre estudiantes inscritos en dos actividades ----------------
def test_conflicto_estudiante_inscrito():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30"), _s("y", "Y", "A", "09:00", "10:30")])
    conf = detectar_conflictos(ds)
    assert _cats(conf) == ["estudiante"]
    assert conf[0].afectados == 1 and (conf[0].inicio, conf[0].fin) == (m("09:00"), m("09:30"))


def test_inscripcion_por_tipo():
    # E3 sólo recursa el laboratorio de X: no choca con la teórica de Y
    ins = [Inscripcion("E3", "X", "A", ["laboratorio"]), Inscripcion("E3", "Y", "A")]
    ds = _mini([_s("xt", "X", "A", "08:00", "09:30"), _s("y", "Y", "A", "08:00", "09:30", dia=0),
                _s("xl", "X", "A", "10:00", "11:30", tipo="laboratorio")], ins)
    assert detectar_conflictos(ds) == []


# 2. Actividades simultáneas sin recursos compartidos ------------------------
def test_simultaneas_sin_recursos_compartidos():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", responsable="D", ambiente="AU2"),
                _s("z", "Z", "B", "08:00", "09:30", responsable="D2", ambiente="LB")])
    assert detectar_conflictos(ds) == []


def test_mismo_semestre_distinto_horario():
    # Dos estudiantes del mismo semestre con paralelos distintos no comparten horario
    ins = [Inscripcion("E1", "X", "A"), Inscripcion("E2", "X", "B")]
    ds = _mini([_s("xa", "X", "A", "08:00", "09:30"), _s("xb", "X", "B", "08:00", "09:30")], ins)
    assert detectar_conflictos(ds) == []


def test_consecutivas_no_se_superponen():
    assert not se_superponen(m("08:00"), m("09:30"), m("09:30"), m("11:00"))
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", responsable="D", ambiente="AU2"),
                _s("y", "Y", "A", "09:30", "11:00", responsable="D", ambiente="AU2")])
    assert detectar_conflictos(ds) == []


def test_no_cuenta_dos_veces_y_cuenta_afectados():
    ins = [Inscripcion(e, "X", "A") for e in ("E1", "E2", "E3")] + [Inscripcion(e, "Y", "A") for e in ("E1", "E2", "E3")]
    ds = _mini([_s("x", "X", "A", "08:00", "09:30"), _s("y", "Y", "A", "08:00", "09:30")], ins)
    est = [c for c in detectar_conflictos(ds) if c.categoria == "estudiante"]
    assert len(est) == 1 and est[0].afectados == 3


def test_distingue_actividad_no_obligatoria():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30"), _s("y", "Y", "A", "08:00", "09:30", obligatoria=False)])
    conf = detectar_conflictos(ds)
    assert _cats(conf) == [] and _cats(conf, "no_obligatorio") == ["estudiante"]


# 3. Conflictos de docentes y auxiliares ------------------------------------
def test_conflicto_docente_y_auxiliar():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", responsable="D"),
                _s("z", "Z", "B", "08:30", "10:00", responsable="D"),
                _s("xa", "X", "A", "14:00", "15:30", tipo="auxiliatura", responsable="AX"),
                _s("za", "Z", "B", "15:00", "16:30", tipo="auxiliatura", responsable="AX")])
    assert _cats(detectar_conflictos(ds)) == ["auxiliar", "docente"]


def test_disponibilidad_responsable():
    ds = _mini([_s("x", "X", "A", "16:00", "17:30", responsable="D")])
    ds.disponibilidad = [Disponibilidad("D", 0, m("07:00"), m("12:00"))]
    assert _cats(detectar_conflictos(ds)) == ["disponibilidad"]


# 4. Conflictos de aulas -----------------------------------------------------
def test_conflicto_aula_y_laboratorio():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", ambiente="AU2"),
                _s("z", "Z", "B", "09:00", "10:30", ambiente="AU2"),
                _s("xl", "X", "A", "11:00", "12:30", tipo="laboratorio", ambiente="LB"),
                _s("zl", "Z", "B", "11:00", "12:30", tipo="laboratorio", ambiente="LB")])
    assert _cats(detectar_conflictos(ds)) == ["aula", "laboratorio"]


# 5. Actividades fijas y reprogramables -------------------------------------
def test_actividades_fijas_no_cambian(demo):
    r = ejecutar_ag(demo, CFG)
    originales = {s.id: (s.dia, s.inicio, s.fin, s.ambiente) for s in demo.sesiones if s.fija}
    for s in r.sesiones_propuestas:
        if s.fija:
            assert (s.dia, s.inicio, s.fin, s.ambiente) == originales[s.id]


def test_horario_actual_no_implica_fijo(real):
    # Las auxiliaturas y laboratorios del caso real son reprogramables aunque tengan horario establecido
    assert all(not s.fija for s in real.sesiones if s.tipo in ("laboratorio", "auxiliatura"))


def test_optimizar_solo_un_subconjunto(demo):
    cfg = replace(CFG, solo_sesiones=("AUX-PRG-A", "AUX-RED-B"))
    r = ejecutar_ag(demo, cfg)
    movidas = {c["Sesión"] for c in r.cambios}
    assert movidas <= {"AUX-PRG-A", "AUX-RED-B"}


# 6. Duraciones y capacidades ----------------------------------------------
def test_capacidad_insuficiente():
    ins = [Inscripcion(e, "X", "A") for e in ("E1", "E2", "E3")]
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", ambiente="AU")], ins)   # AU admite 2
    assert _cats(detectar_conflictos(ds)) == ["capacidad"]


def test_dominio_excluye_ambientes_pequenos():
    ins = [Inscripcion(e, "X", "A") for e in ("E1", "E2", "E3")]
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", ambiente="AU2", fija=False)], ins)
    dom = construir_problema(ds).dominios[0]
    assert "AU" not in dom.ambientes and "AU2" in dom.ambientes


def test_operadores_conservan_sesiones_y_duraciones(demo):
    rng = random.Random(0)
    prob = construir_problema(demo)
    pob = poblacion_inicial(prob, 20, rng)
    for _ in range(50):
        a, b = rng.sample(pob, 2)
        for tipo in ("uniforme", "un_punto", "dos_puntos"):
            for h in cruce(a, b, tipo, rng):
                h = mutacion(h, prob, 0.5, rng)
                assert len(h) == len(prob.modificables)
                for (d, i, amb), dom in zip(h, prob.dominios):
                    assert (d, i) in dom.franjas and amb in dom.ambientes


def test_resultado_mantiene_sesiones_y_duraciones(demo):
    r = ejecutar_ag(demo, CFG)
    assert {s.id: s.duracion for s in demo.sesiones_activas()} == {s.id: s.duracion for s in r.sesiones_propuestas}


def test_duracion_por_confirmar(real):
    dur = [c for c in detectar_conflictos(real) if c.categoria == "duracion"]
    assert len(dur) == 1 and dur[0].severidad == "por_confirmar"


# 7. Escenarios sin solución factible ---------------------------------------
def test_informa_infactibilidad(infactible):
    r = ejecutar_ag(infactible, CFG)
    assert not r.factible
    assert "NO se encontró un horario válido" in r.mensaje()
    assert any("sólo actividades fijas" in d for d in r.diagnostico)


def test_sesion_sin_franjas_validas():
    ds = _mini([_s("x", "X", "A", "08:00", "09:30", fija=False, responsable="AX", tipo="auxiliatura")])
    ds.disponibilidad = [Disponibilidad("AX", 0, m("08:00"), m("09:00"))]   # 60 min < 90 min
    r = ejecutar_ag(ds, CFG)
    assert not r.factible and any("ninguna franja" in d for d in r.diagnostico)


def test_no_se_aprueba_propuesta_inviable(infactible):
    r = ejecutar_ag(infactible, CFG)
    prop = P.desde_resultado(r, "Responsable", "prueba", [])
    ok, msg = P.aprobar(infactible, prop, "Responsable")
    assert not ok and "inviable" in msg and prop.estado == "pendiente"


# 8. Reprogramación de laboratorios y auxiliaturas ---------------------------
def test_escenarios_original_y_reprogramado(real):
    rep = [c for c in detectar_conflictos(real, escenario="reprogramado") if c.categoria == "estudiante"]
    ori = [c for c in detectar_conflictos(real, escenario="original") if c.categoria == "estudiante"]
    assert len(rep) == 3 and all("LAB-IA-ORIG" not in c.sesiones for c in rep)
    assert len(ori) == 6 and all("LAB-IA-REPRO" not in c.sesiones for c in ori)


def test_aplicar_propuesta_crea_version_sin_doble_conteo(demo):
    r = ejecutar_ag(demo, CFG)
    assert r.factible
    prop = P.desde_resultado(r, "Responsable", "prueba", [])
    ok, _ = P.aprobar(demo, prop, "Responsable")
    assert ok
    nuevo = P.aplicar(demo, prop)
    activas = nuevo.sesiones_activas()
    movidas = prop.sesiones_involucradas()
    assert all(s.id not in movidas for s in activas)                         # originales no vigentes
    assert {s.reemplaza for s in activas if s.reemplaza} == movidas         # versiones nuevas vigentes
    assert len(activas) == len(demo.sesiones_activas())                     # nada se cuenta dos veces
    assert all(s.estado == "reemplazada" for s in nuevo.sesiones if s.id in movidas)   # el original se guarda
    assert [c for c in detectar_conflictos(nuevo) if c.severidad == "obligatorio"] == []   # sólo quedan preferencias
    assert prop.estado == "aplicada"


def test_propuesta_manual_se_evalua(demo):
    # Mover LAB-BD-A al lunes 10:00 resuelve sus choques pero LAB-RED-B sigue chocando
    prop = P.propuesta_manual(demo, "LAB-BD-A", 0, m("10:00"), "LAB1", "Docente 1", "prueba", "reprogramado", [])
    assert prop.duros_despues < prop.duros_antes and prop.duros_despues > 0
    assert not P.aprobar(demo, prop, "Responsable")[0]


# 9. Comparación de resultados de varias ejecuciones -------------------------
def test_comparacion_varias_ejecuciones(demo):
    cfgs = {"base": CFG, "sin_dirigida": replace(CFG, mutacion_dirigida=False)}
    det, res, resultados = comparar_configuraciones(demo, cfgs, [1, 2, 3])
    assert len(det) == 6 and list(res["Configuración"]) == ["base", "sin_dirigida"]
    assert all(r.factible for rs in resultados.values() for r in rs)
    assert set(res["Horarios válidos"]) == {"3/3"}


def test_misma_semilla_mismo_resultado(demo):
    r1, r2 = ejecutar_ag(demo, CFG), ejecutar_ag(demo, CFG)
    assert r1.mejor == r2.mejor
    assert [h["mejor_fitness"] for h in r1.historial] == [h["mejor_fitness"] for h in r2.historial]


# Conjunto pequeño con solución factible conocida ---------------------------
def test_solucion_conocida_es_factible(demo):
    prob = construir_problema(demo)
    crom = [SOLUCION_CONOCIDA_DEMO[s.id] for s in prob.modificables]
    assert evaluar(prob, crom, CFG).duros == 0
    assert evaluar(prob, prob.original, CFG).duros > 0


def test_ag_resuelve_demo_varias_semillas(demo):
    for sem in (1, 2, 3, 4, 5):
        assert ejecutar_ag(demo, replace(CFG, semilla=sem)).factible


def test_disponibilidad_estudiante_es_blanda(demo):
    r = ejecutar_ag(demo, CFG)
    tabla = estado_restricciones(r.eval_mejor.conflictos)
    fila = tabla[tabla["Restricción"] == "Disponibilidad de estudiantes"].iloc[0]
    assert fila["Tipo"] == "Blanda"
    assert r.factible   # una preferencia incumplida no invalida el horario


def test_ida_y_vuelta_excel(demo):
    ds2 = excel_a_dataset(dataset_a_excel(demo))
    assert [(s.id, s.dia, s.inicio, s.fin, s.fija, s.paralelo) for s in ds2.sesiones] == \
           [(s.id, s.dia, s.inicio, s.fin, s.fija, s.paralelo) for s in demo.sesiones]
    assert len(ds2.inscripciones) == len(demo.inscripciones) and ds2.tipo_datos == "simulado"


def test_propuestas_persisten(tmp_path, demo):
    r = ejecutar_ag(demo, CFG)
    prop = P.desde_resultado(r, "Responsable", "prueba", [])
    P.guardar_propuestas([prop], tmp_path)
    assert P.cargar_propuestas(tmp_path)[0].cambios == prop.cambios


# Evaluador rápido: debe coincidir EXACTAMENTE con el detector completo -------
@pytest.mark.parametrize("carpeta", ["demo_pequeno", "demo_infactible", "demo_semestre", "caso_real_2026_2", "carrera_2026_2"])
def test_evaluador_rapido_equivale_al_completo(carpeta):
    from core.evaluador_rapido import EvaluadorRapido
    ds = cargar_carpeta(RAIZ_DATOS / carpeta)
    for duras in (CFG.categorias_duras, ("estudiante", "docente")):
        cfg = replace(CFG, categorias_duras=duras)
        prob = construir_problema(ds)
        rap = EvaluadorRapido(prob, cfg)
        rng = random.Random(3)
        for crom in poblacion_inicial(prob, 25, rng):
            a, b = evaluar(prob, crom, cfg), rap.evaluar(crom)
            assert a.duros == b.duros
            assert abs(a.blando - b.blando) < 1e-6
            assert a.en_conflicto == b.en_conflicto


# Planificación de la carrera (datos reales: planes de estudio + plantel docente) --
def test_carrera_cohortes_y_oferta():
    ds = cargar_carpeta(RAIZ_DATOS / "carrera_2026_2")
    assert ds.modo == "planificacion" and ds.tipo_datos == "real"
    # cada paralelo ofertado tiene su teoría con el docente publicado
    teoria = [s for s in ds.sesiones if s.tipo == "teoria"]
    assert teoria and all(s.responsable for s in teoria)
    # las cohortes regulares del mismo semestre agrupan varias materias
    reg = [e for e in ds.estudiantes.values() if e.tipo == "regular"]
    assert reg and all(sum(i.estudiante_id == e.id for i in ds.inscripciones) >= 2 for e in reg)
    # la carga horaria de cada materia respeta el plan (T,P,L x 45 min)
    assert not [c for c in detectar_conflictos(ds) if c.categoria == "duracion" and c.severidad == "obligatorio"]


def test_heuristica_respeta_dominio_y_reduce_choques():
    from core.genetico import individuo_heuristico
    ds = cargar_carpeta(RAIZ_DATOS / "carrera_2026_2")
    prob = construir_problema(ds)
    rng = random.Random(1)
    h = individuo_heuristico(prob, rng)
    for (d, i, a), dom in zip(h, prob.dominios):
        assert (d, i) in dom.franjas and a in dom.ambientes
    azar = poblacion_inicial(prob, 5, rng, incluir_original=False)
    assert evaluar(prob, h, CFG).duros < min(evaluar(prob, c, CFG).duros for c in azar)


def test_irregulares_son_blandos():
    ins = [Inscripcion("E1", "X", "A"), Inscripcion("E1", "Y", "A")]
    ds = _mini([_s("x", "X", "A", "08:00", "09:30"), _s("y", "Y", "A", "08:00", "09:30")], ins)
    ds.estudiantes["E1"].tipo = "irregular"
    conf = detectar_conflictos(ds)
    assert _cats(conf) == [] and _cats(conf, "preferencia") == ["estudiante_irregular"]


def test_mismo_dia_penaliza_teorias():
    from core.genetico import _mismo_dia
    assert _mismo_dia([(0, "X", "A", "teoria", True), (0, "X", "A", "teoria", True), (2, "X", "A", "teoria", True)]) == 1
