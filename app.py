"""
Prototipo de apoyo a la planificación de horarios académicos mediante algoritmos
genéticos – INF3731 Inteligencia Artificial (UTO – FNI – Ing. de Sistemas e Informática).

Ejecutar:   streamlit run app.py

El sistema NO sustituye las decisiones de las autoridades universitarias: genera,
compara y evalúa propuestas. El selector de rol es una SIMULACIÓN para la
demostración académica y no es un mecanismo de autenticación.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import replace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import propuestas as P
from core.conflictos import (CATEGORIAS, DURAS_DEFECTO, NOMBRE_CATEGORIA, conflictos_a_df, detectar_conflictos,
                             estado_restricciones, resumen_por_categoria, sesiones_en_conflicto)
from core.datos import (COLUMNAS, TABLAS, ErrorDatos, cargar_carpeta, conjuntos_disponibles, dataset_a_excel,
                        dataset_a_tablas, excel_a_dataset, exportar_excel, guardar_carpeta, meta_de,
                        sesiones_a_df, tablas_a_dataset)
from core.evaluacion import CONFIGS_REFERENCIA, comparar_configuraciones, indicadores, tabla_antes_despues
from core.genetico import PESOS_DEFECTO, ConfigAG, config_planificacion, construir_dominio, ejecutar_ag
from core.datos import RAIZ_DATOS
from core.modelo import DIAS, NOMBRE_TIPO, Disponibilidad, a_hhmm, a_minutos
from ui.calendario import calendario_html, disponibilidad_html, leyenda_html
from ui.estilos import (AZUL, AZUL_3, CSS, DORADO, ROJO, VERDE, aviso_html, colorear_estados, encabezado, kpi,
                        plotly_layout)

st.set_page_config(page_title="Horarios AG · INF3731", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

ROLES = ["Responsable académico", "Docente", "Auxiliar", "Estudiante"]
PAGINAS_ROL = {
    "Responsable académico": ["Resumen", "Calendario semanal", "Plan de estudios", "Gestión académica", "Disponibilidad",
                              "Detección de conflictos", "Generación de alternativas (AG)",
                              "Revisión de propuestas", "Evaluación y comparación", "Exportación"],
    "Docente": ["Mis actividades", "Mi disponibilidad", "Proponer cambio", "Alternativas generadas"],
    "Auxiliar": ["Mis auxiliaturas", "Mi disponibilidad", "Conflictos con estudiantes", "Solicitar alternativas",
                 "Alternativas generadas"],
    "Estudiante": ["Mi horario", "Mi disponibilidad"],
}
ESTADO_TXT = {"pendiente": "Pendiente", "aprobada": "Aprobada", "rechazada": "Rechazada", "aplicada": "Aplicada"}
CLAVE_ROL = {"Responsable académico": "resp", "Docente": "doc", "Auxiliar": "aux", "Estudiante": "est"}


# Avisos sobrios (reemplazan los cuadros de color por defecto de Streamlit)
def ok(texto, titulo=None):
    st.markdown(aviso_html(texto, "ok", titulo), unsafe_allow_html=True)


def err(texto, titulo=None):
    st.markdown(aviso_html(texto, "err", titulo), unsafe_allow_html=True)


def warn(texto, titulo=None):
    st.markdown(aviso_html(texto, "warn", titulo), unsafe_allow_html=True)


def note(texto, titulo=None):
    st.markdown(aviso_html(texto, "note", titulo), unsafe_allow_html=True)


# =========================================================================== #
# Estado de la sesión
# =========================================================================== #
def cargar_conjunto(etiqueta: str) -> None:
    carpeta = conjuntos_disponibles()[etiqueta]
    ds = cargar_carpeta(carpeta)
    st.session_state.update(conjunto=etiqueta, carpeta=carpeta, ds=ds, ds_original=ds.copia(),
                            resultados=[], resultado=None, comparacion=None,
                            propuestas=P.cargar_propuestas(carpeta),
                            version=st.session_state.get("version", 0) + 1)


def estado():
    if "ds" not in st.session_state:
        opciones = list(conjuntos_disponibles())
        cargar_conjunto(next((o for o in opciones if o.startswith("[REAL]")), opciones[0]))
    return st.session_state.ds


def escenario_actual() -> str:
    return st.session_state.get("escenario", "reprogramado")


def guardar_props():
    if st.session_state.get("carpeta"):
        P.guardar_propuestas(st.session_state.propuestas, st.session_state.carpeta)


def autor() -> str:
    ident = st.session_state.get("identidad")
    ds = estado()
    nombre = (ds.personas.get(ident) or ds.estudiantes.get(ident)) if ident else None
    return f"{st.session_state.rol}" + (f": {nombre.nombre}" if nombre else "")


def insignia(ds) -> str:
    if ds.tipo_datos == "real":
        return '<span class="insignia real">DATOS REALES</span>'
    return '<span class="insignia sim">DATOS SIMULADOS · DEMOSTRACIÓN</span>'


def faltan_teoricas(ds) -> bool:
    return ds.tipo_datos == "real" and not any(s.tipo == "teoria" for s in ds.sesiones)


def aviso_datos_incompletos(ds):
    if faltan_teoricas(ds):
        warn("**Datos institucionales incompletos.** Faltan las clases teóricas del horario oficial; los "
                   "conflictos y alternativas sólo consideran las auxiliaturas y laboratorios registrados. "
                   "No se puede afirmar que se eliminaron los conflictos institucionales.")


# =========================================================================== #
# Barra lateral
# =========================================================================== #
def barra_lateral():
    ds = estado()
    with st.sidebar:
        st.markdown("<div class='marca'>Horarios AG</div>"
                    "<div class='marca-sub'>Prototipo de apoyo · INF3731</div>"
                    "<div class='marca-inst'>Ingeniería de Sistemas e Informática<br>FNI · Universidad Técnica de Oruro</div>",
                    unsafe_allow_html=True)
        st.divider()
        opciones = list(conjuntos_disponibles())
        actual = st.session_state.get("conjunto", opciones[0])
        elegido = st.selectbox("Conjunto de datos", opciones, index=opciones.index(actual) if actual in opciones else 0)
        if elegido != actual:
            cargar_conjunto(elegido)
            st.rerun()
        if ds.tiene_reprogramaciones():
            st.session_state.escenario = st.radio(
                "Escenario", ["reprogramado", "original"], horizontal=True,
                format_func=lambda e: "Vigente (reprogramado)" if e == "reprogramado" else "Original",
                index=0 if escenario_actual() == "reprogramado" else 1,
                help="Nunca se cuentan a la vez la versión original y la reprogramada de una misma sesión.")
        else:
            st.session_state.escenario = "reprogramado"
        st.divider()
        rol = st.selectbox("Rol (simulado)", ROLES, key="rol")
        identidad = None
        if rol in ("Docente", "Auxiliar"):
            ids = [p.id for p in ds.personas.values() if p.rol == rol.lower()]
            if ids:
                identidad = st.selectbox(f"{rol}", ids, format_func=lambda i: ds.personas[i].nombre, key=f"id_{rol}")
            else:
                st.caption(f"No hay {rol.lower()}s registrados en este conjunto (no se inventan).")
        elif rol == "Estudiante":
            ids = list(ds.estudiantes)
            if ids:
                identidad = st.selectbox("Estudiante", ids, format_func=lambda i: ds.estudiantes[i].nombre, key="id_est")
        st.session_state.identidad = identidad
        st.caption("Selector de rol simulado para la demostración académica; no es un sistema de "
                   "autenticación ni de control de acceso.")
        st.divider()
        paginas = PAGINAS_ROL[rol]
        pagina = st.radio("Módulos", paginas, key=f"nav_{CLAVE_ROL[rol]}")
        st.divider()
        st.caption("Herramienta de apoyo: no sustituye las decisiones de las autoridades universitarias.")
    return pagina


# =========================================================================== #
# Utilidades de presentación
# =========================================================================== #
def fila_kpis(items):
    cols = st.columns(len(items))
    for c, (v, l, e) in zip(cols, items):
        c.markdown(kpi(v, l, e), unsafe_allow_html=True)


def grafico_categorias(df: pd.DataFrame, titulo: str):
    fig = go.Figure()
    corto = [c.split(" (")[0] for c in df["Categoría"]]
    for col, color in (("Obligatorios", ROJO), ("No obligatorios", DORADO), ("Por confirmar", AZUL_3),
                       ("Preferencias", "#B9C3D1")):
        fig.add_bar(y=corto, x=df[col], name=col, orientation="h", marker_color=color)
    fig.update_traces(marker_line_width=0, width=0.6)
    fig.update_layout(barmode="stack", title=titulo, yaxis=dict(autorange="reversed"), bargap=0.35)
    return plotly_layout(fig, 360)


def grafico_fitness(historial: list[dict], titulo="Evolución del fitness por generación"):
    h = pd.DataFrame(historial)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Fitness = 1 / (1 + 1000·duros + blando)",
                                        "Conflictos obligatorios (restricciones duras)"))
    fig.add_scatter(x=h.generacion, y=h.mejor_fitness, name="Mejor fitness", line=dict(color=AZUL, width=3), row=1, col=1)
    fig.add_scatter(x=h.generacion, y=h.fitness_promedio, name="Fitness promedio", line=dict(color=DORADO, width=2),
                    row=1, col=1)
    fig.add_scatter(x=h.generacion, y=h.mejor_duros, name="Duros del mejor", line=dict(color=ROJO, width=3), row=2, col=1)
    fig.add_scatter(x=h.generacion, y=h.duros_promedio, name="Duros promedio", line=dict(color="#E8A0A0", dash="dot"),
                    row=2, col=1)
    fig.update_xaxes(title_text="Generación", row=2, col=1)
    fig.update_layout(title=titulo)
    return plotly_layout(fig, 520)


def solo_duros(conflictos):
    """Para marcar en rojo sólo conflictos obligatorios (no preferencias ni coincidencias)."""
    return [c for c in conflictos or [] if c.severidad == "obligatorio"]


def mostrar_calendario(ds, sesiones, conflictos=None, movidas=None, extra=None, titulo=""):
    ids = sesiones_en_conflicto(solo_duros(conflictos))
    st.markdown(calendario_html(ds, sesiones, ids, movidas, extra, titulo), unsafe_allow_html=True)


def tabla_sesiones(ds, sesiones, conflictos=None):
    df = sesiones_a_df(sesiones)
    if df.empty:
        note("No hay actividades para mostrar.")
        return
    en_c = sesiones_en_conflicto(solo_duros(conflictos))
    df.insert(0, "Conflicto", ["Sí" if i in en_c else "" for i in df["id"]])
    df.insert(4, "inscritos", [len(ds.inscritos(s)) for s in sesiones])
    df["asignatura"] = [ds.asignaturas[a].nombre if a in ds.asignaturas else a for a in df["asignatura"]]
    st.dataframe(df.drop(columns=["dias_permitidos", "tipo_ambiente", "duracion_requerida_min"]),
                 hide_index=True, width="stretch")


def editor_disponibilidad(ds, entidad_id: str, clave: str, nota: str):
    st.caption(nota)
    filas = pd.DataFrame([{"dia": DIAS[d.dia], "inicio": a_hhmm(d.inicio), "fin": a_hhmm(d.fin)}
                          for d in ds.disponibilidad_de(entidad_id)], columns=["dia", "inicio", "fin"])
    ed = st.data_editor(filas, num_rows="dynamic", hide_index=True, width="stretch",
                        key=f"disp_{clave}_{entidad_id}_{st.session_state.version}",
                        column_config={"dia": st.column_config.SelectboxColumn("Día", options=DIAS, required=True),
                                       "inicio": st.column_config.TextColumn("Desde (HH:MM)", required=True),
                                       "fin": st.column_config.TextColumn("Hasta (HH:MM)", required=True)})
    if st.button("Guardar disponibilidad", type="primary", key=f"g_{clave}"):
        try:
            nuevas = []
            for _, r in ed.dropna(how="all").iterrows():
                d = Disponibilidad(entidad_id, DIAS.index(r["dia"]), a_minutos(r["inicio"]), a_minutos(r["fin"]))
                if d.fin <= d.inicio:
                    raise ValueError(f"{r['dia']}: la hora final debe ser mayor que la inicial")
                nuevas.append(d)
            nuevo = ds.copia()
            nuevo.disponibilidad = [d for d in nuevo.disponibilidad if d.entidad_id != entidad_id] + nuevas
            st.session_state.update(ds=nuevo, version=st.session_state.version + 1)
            ok("Disponibilidad registrada en la copia de trabajo.")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            err(f"No se guardó: {e}")


# =========================================================================== #
# RESPONSABLE ACADÉMICO
# =========================================================================== #
def pagina_resumen():
    ds = estado()
    esc = escenario_actual()
    st.markdown(encabezado("Prototipo de apoyo a la planificación de horarios académicos",
                           "Generación de alternativas mediante algoritmos genéticos · Carrera de Ingeniería de "
                           "Sistemas e Informática – UTO", "Panel de resumen"), unsafe_allow_html=True)
    st.markdown(f"{insignia(ds)} <b style='color:{AZUL}'>{ds.nombre}</b>", unsafe_allow_html=True)
    st.write(ds.descripcion)
    aviso_datos_incompletos(ds)
    activas = ds.sesiones_activas(esc)
    conf = detectar_conflictos(ds, escenario=esc)
    oblig = sum(c.severidad == "obligatorio" for c in conf)
    props = st.session_state.propuestas
    fila_kpis([
        (len(activas), "Actividades vigentes", ""),
        (f"{sum(s.fija for s in activas)} / {sum(not s.fija for s in activas)}", "Fijas / movibles", ""),
        (f"{len(ds.estudiantes)} / {len(ds.inscripciones)}", "Estudiantes / inscripciones", ""),
        (oblig, "Conflictos obligatorios", "mal" if oblig else "bien"),
        (sum(c.severidad == "por_confirmar" for c in conf), "Datos por confirmar", ""),
        (sum(p.estado == "pendiente" for p in props), "Propuestas pendientes", ""),
    ])
    st.write("")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.plotly_chart(grafico_categorias(resumen_por_categoria(conf), "Conflictos por categoría"), width="stretch")
    with c2:
        st.markdown("#### Composición")
        comp = pd.DataFrame([{"Tipo": NOMBRE_TIPO[t], "Actividades": sum(s.tipo == t for s in activas),
                              "Horas semanales": round(sum(s.duracion for s in activas if s.tipo == t) / 60, 1)}
                             for t in NOMBRE_TIPO])
        st.dataframe(comp, hide_index=True, width="stretch")
        st.markdown(f"**Franja:** {a_hhmm(ds.hora_inicio)}–{a_hhmm(ds.hora_fin)} · "
                    f"**Días:** {', '.join(DIAS[d] for d in ds.dias)}")
        st.markdown(f"**Docentes / auxiliares:** {sum(p.rol == 'docente' for p in ds.personas.values())} / "
                    f"{sum(p.rol == 'auxiliar' for p in ds.personas.values())} · **Ambientes:** {len(ds.ambientes)}")
    if ds.pendientes:
        st.markdown("#### Datos pendientes y supuestos")
        st.markdown('<div class="aviso warn"><ul class="lista-supuestos">' + "".join(
            f"<li>{p}</li>" for p in ds.pendientes) + "</ul></div>", unsafe_allow_html=True)
    if ds.tipo_datos == "real":
        st.caption("Alcance: el caso real corresponde al horario de una estudiante y no se generaliza a toda la carrera.")


def pagina_calendario():
    ds = estado()
    esc = escenario_actual()
    st.markdown(encabezado("Calendario académico semanal", "Lunes a sábado · pase el cursor sobre una actividad "
                           "para ver el detalle", "Visualización"), unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1.4, 1.5, 1])
    vista = c1.selectbox("Ver por", ["Estudiante", "Paralelo", "Responsable", "Ambiente", "Todo"],
                         format_func=lambda v: "Estudiante / cohorte" if v == "Estudiante" else v)
    activas = ds.sesiones_activas(esc)
    filtro = lambda s: True  # noqa: E731
    if vista == "Estudiante" and ds.estudiantes:
        e = c2.selectbox("Estudiante / cohorte", list(ds.estudiantes), format_func=lambda i: ds.estudiantes[i].nombre)
        filtro = lambda s: e in ds.inscritos(s)  # noqa: E731
    elif vista == "Paralelo":
        pares = sorted({(s.asignatura, s.paralelo) for s in activas})
        ps = sorted({p for _, p in pares})
        par = c2.selectbox("Paralelo", ps, format_func=lambda p: p or "(sin especificar)")
        filtro = lambda s: s.paralelo == par  # noqa: E731
    elif vista == "Responsable" and ds.personas:
        r = c2.selectbox("Responsable", list(ds.personas), format_func=lambda i: ds.personas[i].nombre)
        filtro = lambda s: s.responsable == r  # noqa: E731
    elif vista == "Ambiente" and ds.ambientes:
        a = c2.selectbox("Ambiente", list(ds.ambientes), format_func=lambda i: ds.ambientes[i].nombre)
        filtro = lambda s: s.ambiente == a  # noqa: E731
    tipos = c3.multiselect("Tipos", list(NOMBRE_TIPO), default=list(NOMBRE_TIPO), format_func=lambda t: NOMBRE_TIPO[t])
    ver_reemp = c4.toggle("Ver reemplazadas", value=esc == "reprogramado" and ds.tiene_reprogramaciones())
    ses = [s for s in activas if filtro(s) and s.tipo in tipos]
    extra = ([s for s in ds.sesiones if s.estado == "reemplazada" and filtro(s) and s.tipo in tipos]
             if ver_reemp and esc == "reprogramado" else [])
    conf = detectar_conflictos(ds, escenario=esc)
    st.markdown(leyenda_html(), unsafe_allow_html=True)
    st.write("")
    mostrar_calendario(ds, ses, conf, extra=extra)
    st.markdown("#### Actividades registradas")
    tabla_sesiones(ds, ses, conf)


SI_NO = ["si", "no"]


def _config_columnas(ds, tabla):
    cc = st.column_config
    hora = dict(validate=r"^\d{1,2}:\d{2}$", help="Formato HH:MM")
    if tabla == "sesiones":
        return {
            "tipo": cc.SelectboxColumn("tipo", options=list(NOMBRE_TIPO), required=True),
            "dia": cc.SelectboxColumn("dia", options=DIAS, required=True),
            "inicio": cc.TextColumn("inicio", required=True, **hora), "fin": cc.TextColumn("fin", required=True, **hora),
            "asignatura": cc.SelectboxColumn("asignatura", options=list(ds.asignaturas)),
            "responsable": cc.SelectboxColumn("responsable", options=[""] + list(ds.personas)),
            "ambiente": cc.SelectboxColumn("ambiente", options=[""] + list(ds.ambientes)),
            "fija": cc.SelectboxColumn("fija", options=SI_NO, help="si = el AG no la mueve; no = reprogramable"),
            "obligatoria": cc.SelectboxColumn("obligatoria", options=SI_NO),
            "estado": cc.SelectboxColumn("estado", options=["vigente", "reemplazada", "pendiente_confirmacion"]),
            "origen": cc.SelectboxColumn("origen", options=["oficial", "adicional", "reprogramacion", "simulado"]),
            "tipo_ambiente": cc.SelectboxColumn("tipo_ambiente", options=["", "aula", "laboratorio"]),
            "paralelo": cc.TextColumn("paralelo", help="Paralelo de la asignatura (vacío = sin especificar)"),
            "dias_permitidos": cc.TextColumn("dias_permitidos", help="vacío = todos; ej. Lunes;Martes"),
            "duracion_requerida_min": cc.TextColumn("duracion_requerida_min", help="vacío = la duración actual"),
        }
    if tabla == "inscripciones":
        return {"estudiante_id": cc.SelectboxColumn("estudiante_id", options=list(ds.estudiantes), required=True),
                "asignatura": cc.SelectboxColumn("asignatura", options=list(ds.asignaturas), required=True),
                "tipos": cc.TextColumn("tipos", help="vacío = todas; ej. laboratorio;auxiliatura")}
    if tabla == "personas":
        return {"rol": cc.SelectboxColumn("rol", options=["docente", "auxiliar"], required=True)}
    if tabla == "ambientes":
        return {"tipo": cc.SelectboxColumn("tipo", options=["aula", "laboratorio"], required=True),
                "capacidad": cc.NumberColumn("capacidad", min_value=0, help="0 = sin dato (no se verifica)")}
    if tabla == "disponibilidad":
        ids = list(ds.personas) + list(ds.ambientes) + list(ds.estudiantes)
        return {"entidad_id": cc.SelectboxColumn("entidad_id", options=ids, required=True),
                "dia": cc.SelectboxColumn("dia", options=DIAS, required=True),
                "inicio": cc.TextColumn("inicio", **hora), "fin": cc.TextColumn("fin", **hora)}
    return {}


def pagina_gestion():
    ds = estado()
    st.markdown(encabezado("Gestión académica", "Materias, paralelos, inscripciones, docentes, auxiliares, "
                           "ambientes, disponibilidad y actividades", "Datos"), unsafe_allow_html=True)
    st.markdown(insignia(ds), unsafe_allow_html=True)
    st.caption("Use la última fila de cada tabla para agregar registros; seleccione filas para eliminarlas. "
               "Los cambios se aplican a la copia de trabajo con **Validar y aplicar**.")
    tablas = dataset_a_tablas(ds)
    nombres = {"sesiones": "Actividades", "asignaturas": "Materias", "estudiantes": "Estudiantes",
               "inscripciones": "Inscripciones", "personas": "Docentes y auxiliares",
               "ambientes": "Aulas y laboratorios", "disponibilidad": "Disponibilidad"}
    orden = ["sesiones", "asignaturas", "estudiantes", "inscripciones", "personas", "ambientes", "disponibilidad"]
    v = st.session_state.version
    editados = {}
    tabs = st.tabs([nombres[t] for t in orden] + ["Configuración"])
    notas = {
        "sesiones": "Cada actividad pertenece a una materia y un paralelo. `fija = si` sólo si NO puede moverse "
                    "(el horario actual no implica que sea fija). Una reprogramación es una nueva fila con "
                    "`reemplaza = id original`; la original queda con estado `reemplazada`.",
        "inscripciones": "Un estudiante asiste a las actividades de la materia y paralelo en que está inscrito. "
                         "`tipos` permite inscribirse sólo a laboratorio o auxiliatura (ej. recursantes).",
        "disponibilidad": "Para docentes, auxiliares y ambientes es una restricción dura; para estudiantes, "
                          "una preferencia. Sin filas = disponible en toda la franja.",
        "ambientes": "La capacidad se compara con el número de inscritos (restricción dura).",
    }
    for tab, t in zip(tabs, orden):
        with tab:
            if t in notas:
                st.caption(notas[t])
            df = tablas[t] if t == "ambientes" else tablas[t].astype(str)
            editados[t] = st.data_editor(df, num_rows="dynamic", width="stretch", key=f"ed_{t}_{v}",
                                         column_config=_config_columnas(ds, t), hide_index=True)
    with tabs[-1]:
        c1, c2, c3 = st.columns(3)
        h_ini = c1.text_input("Inicio de la franja", a_hhmm(ds.hora_inicio), key=f"hi_{v}")
        h_fin = c2.text_input("Fin de la franja", a_hhmm(ds.hora_fin), key=f"hf_{v}")
        resol = c3.selectbox("Resolución (min)", [15, 30, 60], index=[15, 30, 60].index(ds.resolucion)
                             if ds.resolucion in (15, 30, 60) else 1, key=f"rs_{v}")
        dias = st.multiselect("Días habilitados", DIAS, default=[DIAS[d] for d in ds.dias], key=f"dh_{v}")
        pend = st.text_area("Datos pendientes / supuestos (uno por línea)", "\n".join(ds.pendientes), key=f"pd_{v}")
    c1, c2 = st.columns([1, 3])
    if c1.button("Validar y aplicar", type="primary"):
        meta = meta_de(ds)
        meta.update(hora_inicio=h_ini, hora_fin=h_fin, resolucion=resol, dias=dias,
                    pendientes=[x for x in pend.splitlines() if x.strip()])
        try:
            nuevo = tablas_a_dataset({t: df.fillna("") for t, df in editados.items()}, meta)
            st.session_state.update(ds=nuevo, resultados=[], resultado=None, version=st.session_state.version + 1)
            st.rerun()
        except (ErrorDatos, ValueError) as e:
            err(f"No se aplicaron los cambios:\n{e}")

    st.divider()
    st.markdown("#### Importar horarios académicos")
    c1, c2 = st.columns(2)
    with c1:
        f = st.file_uploader("Libro Excel (.xlsx) con hojas: " + ", ".join(TABLAS), type=["xlsx"])
        tipo_imp = st.radio("Los datos importados son", ["simulado", "real"], horizontal=True,
                            format_func=lambda x: "Simulados / demostración" if x == "simulado" else "Reales (verificados)")
        if f and st.button("Importar Excel"):
            try:
                nuevo = excel_a_dataset(f.getvalue(), {**meta_de(ds), "nombre": f.name, "tipo_datos": tipo_imp})
                nuevo.tipo_datos = tipo_imp
                st.session_state.update(ds=nuevo, ds_original=nuevo.copia(), resultados=[], resultado=None,
                                        carpeta=None, propuestas=[], version=st.session_state.version + 1)
                ok(f"Importadas {len(nuevo.sesiones)} actividades.")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                err(f"Error al importar: {e}")
    with c2:
        fc = st.file_uploader("Tabla CSV (reemplaza una tabla completa)", type=["csv"])
        destino = st.selectbox("Tabla destino", TABLAS)
        if fc and st.button("Importar CSV"):
            try:
                t = dataset_a_tablas(ds)
                t[destino] = pd.read_csv(fc, dtype=str, keep_default_na=False)
                st.session_state.update(ds=tablas_a_dataset(t, meta_de(ds)), resultados=[], resultado=None,
                                        version=st.session_state.version + 1)
                st.rerun()
            except Exception as e:  # noqa: BLE001
                err(f"Error al importar: {e}")
        st.download_button("Plantilla Excel vacía", exportar_excel({t: pd.DataFrame(columns=COLUMNAS[t]) for t in TABLAS}),
                           "plantilla_horarios.xlsx")
    st.markdown("#### Guardar en disco")
    conf = st.checkbox("Confirmo que deseo sobrescribir los archivos CSV de este conjunto de datos")
    if st.button("Guardar conjunto en data/", disabled=not conf or not st.session_state.get("carpeta")):
        guardar_carpeta(st.session_state.ds, st.session_state.carpeta)
        st.session_state.ds_original = st.session_state.ds.copia()
        guardar_props()
        ok(f"Guardado en {st.session_state.carpeta.name}/")


def pagina_disponibilidad():
    ds = estado()
    st.markdown(encabezado("Disponibilidad de responsables y ambientes", "Verde = disponible · bloques = "
                           "actividades vigentes · contorno rojo = actividad fuera de la disponibilidad", "Restricciones"),
                unsafe_allow_html=True)
    opciones = {**{p.id: f"{p.nombre} ({p.rol})" for p in ds.personas.values()},
                **{a.id: f"{a.nombre} ({a.tipo})" for a in ds.ambientes.values()},
                **{e.id: f"{e.nombre} (estudiante)" for e in ds.estudiantes.values()}}
    if not opciones:
        note("No hay docentes, auxiliares, ambientes ni estudiantes registrados.")
        return
    ent = st.selectbox("Entidad", list(opciones), format_func=lambda i: opciones[i])
    activas = ds.sesiones_activas(escenario_actual())
    ses = [s for s in activas if s.responsable == ent or s.ambiente == ent or ent in ds.inscritos(s)]
    if not ds.disponibilidad_de(ent):
        st.caption("Sin disponibilidad registrada: se asume disponible en toda la franja (no se inventan datos).")
    st.markdown(disponibilidad_html(ds, ent, ses), unsafe_allow_html=True)
    with st.expander("Registrar / editar disponibilidad de esta entidad"):
        editor_disponibilidad(ds, ent, "resp", "Edición realizada por el responsable académico.")
    resumen = pd.DataFrame([{"Entidad": opciones.get(d.entidad_id, d.entidad_id), "Día": DIAS[d.dia],
                             "Desde": a_hhmm(d.inicio), "Hasta": a_hhmm(d.fin)} for d in ds.disponibilidad])
    st.markdown("#### Toda la disponibilidad registrada")
    st.dataframe(resumen, hide_index=True, width="stretch")


def pagina_conflictos():
    ds = estado()
    esc = escenario_actual()
    st.markdown(encabezado("Detección de conflictos", "Dos actividades simultáneas sólo chocan si comparten "
                           "estudiantes inscritos, responsable o ambiente", "Análisis"), unsafe_allow_html=True)
    aviso_datos_incompletos(ds)
    conf = detectar_conflictos(ds, escenario=esc)
    oblig = [c for c in conf if c.severidad == "obligatorio"]
    fila_kpis([(len(oblig), "Conflictos obligatorios", "mal" if oblig else "bien"),
               (sum(c.afectados for c in oblig if c.categoria == "estudiante"), "Choques estudiante-actividad", ""),
               (sum(c.severidad == "no_obligatorio" for c in conf), "Coincidencias no obligatorias", ""),
               (sum(c.severidad == "preferencia" for c in conf), "Preferencias incumplidas", ""),
               (sum(c.severidad == "por_confirmar" for c in conf), "Pendientes de confirmación", "")])
    st.write("")
    c1, c2 = st.columns([1, 1.2])
    c1.markdown("##### Restricciones cumplidas e incumplidas")
    c1.dataframe(colorear_estados(estado_restricciones(conf)), hide_index=True, width="stretch")
    c2.plotly_chart(grafico_categorias(resumen_por_categoria(conf), "Conflictos por categoría"), width="stretch")
    st.markdown("#### Reporte detallado")
    df = conflictos_a_df(ds, conf)
    f1, f2 = st.columns(2)
    cats = f1.multiselect("Categoría", sorted(df["Categoría"].unique()), placeholder="Todas")
    sevs = f2.multiselect("Severidad", sorted(df["Severidad"].unique()), placeholder="Todas")
    vista = df
    if cats:
        vista = vista[vista["Categoría"].isin(cats)]
    if sevs:
        vista = vista[vista["Severidad"].isin(sevs)]
    st.dataframe(vista, hide_index=True, width="stretch")
    st.download_button("Reporte (CSV)", vista.to_csv(index=False).encode("utf-8-sig"), "reporte_conflictos.csv")
    st.caption("Cada par de actividades se cuenta una sola vez por categoría; la columna de estudiantes afectados "
               "indica cuántos inscritos comparten el choque.")
    st.markdown("#### Conflictos en el calendario")
    st.markdown(leyenda_html(), unsafe_allow_html=True)
    mostrar_calendario(ds, ds.sesiones_activas(esc), conf)


def es_planificacion(ds=None) -> bool:
    return (ds or estado()).modo == "planificacion"


def formulario_config(prefijo="ag") -> tuple[ConfigAG, int, bool]:
    plan = es_planificacion()
    base = st.session_state.get(f"cfg_{estado().modo}") or (config_planificacion() if plan else ConfigAG())
    if plan:
        note("Modo planificación: no hay un horario previo que conservar. El 30 % de la población inicial se construye "
             "con una heurística voraz (las sesiones con más cohortes y docente compartido se colocan primero) y el "
             "algoritmo genético optimiza a partir de ahí. Mutación baja por gen porque el cromosoma tiene cientos de genes.",
             "Generar el horario completo de la carrera")
    with st.form(f"cfg_{prefijo}"):
        st.markdown("##### Parámetros del algoritmo genético")
        c1, c2, c3, c4 = st.columns(4)
        pob = c1.number_input("Individuos", 10, 500, base.poblacion, 10)
        gens = c2.number_input("Generaciones máximas", 10, 3000, base.generaciones, 10)
        pc = c3.slider("Prob. de cruzamiento", 0.0, 1.0, base.prob_cruce, 0.05)
        pm = c4.number_input("Prob. de mutación (por gen)", 0.0, 1.0, float(base.prob_mutacion), 0.001, format="%.3f")
        c1, c2, c3, c4 = st.columns(4)
        elit = c1.number_input("Elitismo", 0, 20, base.elitismo)
        k = c2.number_input("Tamaño del torneo k", 2, 10, base.torneo_k)
        cruce = c3.selectbox("Cruce", ["uniforme", "un_punto", "dos_puntos"],
                             index=["uniforme", "un_punto", "dos_puntos"].index(base.tipo_cruce))
        semilla = c4.number_input("Semilla", 0, 10**9, base.semilla or 0)
        c1, c2, c3, c4 = st.columns(4)
        tlim = c1.number_input("Límite de tiempo (s)", 1, 3600, int(base.tiempo_limite))
        pac = c2.number_input("Paciencia (gen. sin mejora)", 5, 3000, base.paciencia)
        dirigida = c3.toggle("Mutación dirigida a conflictos", base.mutacion_dirigida)
        n_alt = c4.number_input("Alternativas (semillas)", 1, 5, 1, help="Ejecuta el AG con semillas consecutivas")
        heur = st.slider("Población inicial heurística (%)", 0, 100, int(round(base.frac_heuristica * 100)), 5,
                         help="Porcentaje de individuos iniciales construidos con la heurística voraz; el resto es aleatorio.")
        st.markdown("##### Restricciones duras")
        duras = st.multiselect("Categorías obligatorias", CATEGORIAS, default=list(base.categorias_duras),
                               format_func=lambda c: NOMBRE_CATEGORIA[c],
                               help="Las no marcadas se tratan como preferencias penalizadas.")
        with st.expander("Restricciones blandas (pesos de preferencia)"):
            etiquetas = {"cambio_dia": "Mover a otro día", "cambio_hora": "Mover de hora", "cambio_ambiente": "Cambiar ambiente",
                         "hueco": "Horas libres (por 30 min/estudiante)", "franja": "Fuera de la franja preferida",
                         "sabado": "Actividad en sábado", "carga_diaria": "Exceso de carga diaria",
                         "disp_estudiante": "Disponibilidad de estudiantes (por estudiante)",
                         "no_obligatorio": "Coincidencia no obligatoria", "relajada": "Categoría relajada",
                         "irregular": "Choque de irregulares (por cohorte)", "mismo_dia": "Dos teorías el mismo día"}
            cols = st.columns(3)
            pesos = {kk: cols[i % 3].number_input(et, 0.0, 1000.0, float(base.pesos.get(kk, PESOS_DEFECTO[kk])), 0.1,
                                                  key=f"p_{prefijo}_{kk}") for i, (kk, et) in enumerate(etiquetas.items())}
            c1, c2, c3 = st.columns(3)
            fp_i = c1.text_input("Franja preferida desde", a_hhmm(base.franja_preferida[0]))
            fp_f = c2.text_input("Franja preferida hasta", a_hhmm(base.franja_preferida[1]))
            maxh = c3.number_input("Carga diaria máxima (h)", 1.0, 14.0, base.max_min_dia / 60, 0.5)
        enviar = st.form_submit_button("Generar alternativas", type="primary")
    cfg = ConfigAG(poblacion=int(pob), generaciones=int(gens), prob_cruce=pc, prob_mutacion=pm, elitismo=int(elit),
                   torneo_k=int(k), tipo_cruce=cruce, semilla=int(semilla), tiempo_limite=float(tlim),
                   paciencia=int(pac), mutacion_dirigida=dirigida, categorias_duras=tuple(duras), pesos=pesos,
                   frac_heuristica=heur / 100, incluir_original=base.incluir_original,
                   franja_preferida=(a_minutos(fp_i), a_minutos(fp_f)), max_min_dia=int(maxh * 60),
                   escenario=escenario_actual())
    return cfg, int(n_alt), enviar


def ejecutar_con_progreso(ds, cfg, etiqueta=""):
    barra = st.progress(0.0, text=f"{etiqueta}Inicializando población…")

    def progreso(g, reg):
        if g % 5 == 0:
            barra.progress(min(1.0, g / cfg.generaciones),
                           text=f"{etiqueta}Generación {g} · duros {reg['mejor_duros']} · blando {reg['mejor_blando']:.2f}")
    r = ejecutar_ag(ds, cfg, progreso)
    barra.empty()
    return r


def pagina_generacion():
    ds = estado()
    st.markdown(encabezado("Generación de alternativas con algoritmo genético",
                           "Cada individuo es un horario completo; cada gen asigna día, hora y ambiente a una "
                           "actividad reprogramable", "Algoritmo genético"), unsafe_allow_html=True)
    st.markdown(insignia(ds), unsafe_allow_html=True)
    aviso_datos_incompletos(ds)
    cfg, n_alt, enviar = formulario_config()
    if enviar:
        st.session_state[f"cfg_{ds.modo}"] = cfg
        st.session_state.resultados = [ejecutar_con_progreso(ds, replace(cfg, semilla=cfg.semilla + i),
                                                             f"Alternativa {i + 1}/{n_alt} · ") for i in range(n_alt)]
        st.session_state.resultado = st.session_state.resultados[0]
    rs = st.session_state.get("resultados") or []
    if not rs:
        note("Configure los parámetros y genere alternativas.")
        return
    if len(rs) > 1:
        st.markdown("#### Alternativas generadas")
        tabla = pd.DataFrame([{"Alternativa": i + 1, "Semilla": r.config.semilla, "Válida": "Sí" if r.factible else "No",
                               "Conflictos oblig.": r.eval_mejor.duros, "Penalización blanda": round(r.eval_mejor.blando, 2),
                               "Actividades movidas": len(r.cambios), "Fitness": round(r.eval_mejor.fitness, 5)}
                              for i, r in enumerate(rs)])
        st.dataframe(colorear_estados(tabla), hide_index=True, width="stretch")
        i = st.selectbox("Ver alternativa", range(len(rs)), format_func=lambda i: f"Alternativa {i + 1}")
        st.session_state.resultado = rs[i]
    mostrar_resultado(ds, st.session_state.resultado)


def mostrar_resultado(ds, r, registrar=True):
    (ok if r.factible else err)(r.mensaje())
    if r.factible and faltan_teoricas(ds):
        warn("Válido sólo respecto a los datos registrados: faltan las clases teóricas oficiales.")
    if r.factible and es_planificacion(ds):
        warn("Válido respecto a los datos publicados (planes de estudio y plantel docente). Faltan aulas, auxiliares, "
             "disponibilidad docente e inscripciones reales: es una propuesta de partida, no un horario definitivo.")
    ind = indicadores(r)
    red = ind["Reducción (%)"]
    if es_planificacion(ds):
        fila_kpis([(len(r.sesiones_propuestas), "Sesiones programadas", ""),
                   (ind["Conflictos obligatorios después"], "Conflictos obligatorios", "mal" if not r.factible else "bien"),
                   (round(r.eval_mejor.blando, 1), "Penalización por preferencias", ""),
                   (f"{r.eval_mejor.fitness:.4f}", "Mejor fitness", ""), (r.generaciones, "Generaciones", ""),
                   (f"{r.tiempo:.1f} s", "Tiempo", "")])
        st.caption(f"Motivo de parada: {r.motivo_parada} · Semilla: {r.config.semilla}")
    else:
        fila_kpis([(ind["Conflictos obligatorios antes"], "Conflictos antes", "mal" if ind["Conflictos obligatorios antes"] else "bien"),
                   (ind["Conflictos obligatorios después"], "Conflictos después", "mal" if not r.factible else "bien"),
                   (f"{red:.1f} %" if red is not None else "—", "Reducción", ""),
                   (f"{r.eval_mejor.fitness:.4f}", "Mejor fitness", ""), (r.generaciones, "Generaciones", ""),
                   (f"{r.tiempo:.2f} s", "Tiempo", "")])
        st.caption(f"Motivo de parada: {r.motivo_parada} · Semilla: {r.config.semilla} · Actividades movidas: {len(r.cambios)}")
    nombres = ["Horario generado", "Tabla del horario"] if es_planificacion(ds) else ["Antes / después", "Cambios"]
    t1, t2, t3, t4, t5 = st.tabs(nombres + ["Evolución del fitness", "Restricciones cumplidas e incumplidas", "Penalizaciones"])
    with t1:
        st.markdown(leyenda_html(), unsafe_allow_html=True)
        if es_planificacion(ds):
            ses = r.sesiones_propuestas
            c1, c2 = st.columns([1, 2])
            vista = c1.selectbox("Ver por", ["Cohorte", "Docente", "Paralelo de materia"], key=f"vp_{id(r)}")
            if vista == "Cohorte":
                regs = [e for e in ds.estudiantes.values() if e.tipo == "regular"]
                e = c2.selectbox("Cohorte (mención · semestre · paralelo)", [x.id for x in regs],
                                 format_func=lambda i: ds.estudiantes[i].nombre, key=f"vc_{id(r)}")
                sel = [s for s in ses if e in ds.inscritos(s)]
            elif vista == "Docente":
                d = c2.selectbox("Docente", sorted(ds.personas, key=lambda i: ds.personas[i].nombre),
                                 format_func=lambda i: ds.personas[i].nombre, key=f"vd_{id(r)}")
                sel = [s for s in ses if s.responsable == d]
            else:
                ops = sorted({(s.asignatura, s.paralelo) for s in ses})
                a = c2.selectbox("Materia y paralelo", ops, format_func=lambda x: f"{x[0]} {x[1]} · "
                                 f"{ds.asignaturas[x[0]].nombre if x[0] in ds.asignaturas else ''}", key=f"vm_{id(r)}")
                sel = [s for s in ses if (s.asignatura, s.paralelo) == a]
            mostrar_calendario(ds, sel, r.eval_mejor.conflictos, titulo="Horario generado")
        else:
            mostrar_calendario(ds, ds.sesiones_activas(r.config.escenario), r.eval_original.conflictos, titulo="Horario actual")
            st.write("")
            mostrar_calendario(ds, r.sesiones_propuestas, r.eval_mejor.conflictos,
                               movidas={c["Sesión"] for c in r.cambios}, titulo="Alternativa generada")
            st.dataframe(tabla_antes_despues(r), hide_index=True, width="stretch")
    with t2:
        if es_planificacion(ds):
            st.dataframe(tabla_horario(ds, r.sesiones_propuestas), hide_index=True, width="stretch")
        elif r.cambios:
            st.dataframe(pd.DataFrame(r.cambios), hide_index=True, width="stretch")
        else:
            note("Sin cambios.")
    with t3:
        if r.historial:
            st.plotly_chart(grafico_fitness(r.historial), width="stretch")
            with st.expander("Historial de generaciones (tabla)"):
                st.dataframe(pd.DataFrame(r.historial), hide_index=True, width="stretch")
    with t4:
        st.dataframe(colorear_estados(estado_restricciones(r.eval_mejor.conflictos, r.config.categorias_duras)), hide_index=True,
                     width="stretch")
        for p in r.restricciones_pendientes():
            st.markdown(f"- {p}")
        if r.diagnostico:
            st.markdown("**Diagnóstico previo (restricciones que el AG no puede satisfacer):**")
            for d in r.diagnostico:
                st.markdown(f"- {d}")
    with t5:
        st.dataframe(pd.DataFrame([{"Componente": k, "Penalización": round(v, 2)}
                                   for k, v in r.eval_mejor.detalle_blando.items()]), hide_index=True, width="stretch")
    if registrar:
        st.divider()
        st.markdown("#### Registrar como propuesta")
        st.caption("La alternativa queda **pendiente de revisión**; no modifica el horario vigente.")
        desc = st.text_input("Descripción", f"Alternativa AG (semilla {r.config.semilla})", key=f"desc_{id(r)}")
        if st.button("Registrar propuesta", key=f"reg_{id(r)}"):
            p = P.desde_resultado(r, autor(), desc, st.session_state.propuestas)
            st.session_state.propuestas.append(p)
            guardar_props()
            ok(f"Propuesta {p.id} registrada como pendiente. "
                       + ("" if p.factible else "Atención: es inviable y no podrá aprobarse."))


def tabla_horario(ds, sesiones) -> pd.DataFrame:
    filas = []
    for s in sorted(sesiones, key=lambda x: (x.asignatura, x.paralelo, x.tipo, x.dia, x.inicio)):
        a = ds.asignaturas.get(s.asignatura)
        filas.append({"Sigla": a.codigo if a else s.asignatura, "Materia": a.nombre if a else s.asignatura,
                      "Paralelo": s.paralelo, "Tipo": NOMBRE_TIPO.get(s.tipo, s.tipo), "Día": DIAS[s.dia],
                      "Inicio": a_hhmm(s.inicio), "Fin": a_hhmm(s.fin),
                      "Docente": ds.personas[s.responsable].nombre if s.responsable in ds.personas else "",
                      "Sesión": s.id})
    return pd.DataFrame(filas)


def horario_por_cohorte(ds, sesiones) -> pd.DataFrame:
    """Una fila por (cohorte, sesión): horario listo para publicar por mención y semestre."""
    filas = []
    for e in ds.estudiantes.values():
        for s in sorted((x for x in sesiones if e.id in ds.inscritos(x)), key=lambda x: (x.dia, x.inicio)):
            a = ds.asignaturas.get(s.asignatura)
            filas.append({"Cohorte / estudiante": e.nombre, "Tipo de cohorte": e.tipo, "Día": DIAS[s.dia],
                          "Inicio": a_hhmm(s.inicio), "Fin": a_hhmm(s.fin), "Sigla": a.codigo if a else s.asignatura,
                          "Materia": a.nombre if a else s.asignatura, "Paralelo": s.paralelo,
                          "Tipo": NOMBRE_TIPO.get(s.tipo, s.tipo),
                          "Docente": ds.personas[s.responsable].nombre if s.responsable in ds.personas else ""})
    return pd.DataFrame(filas)


def pagina_plan_estudios():
    ds = estado()
    st.markdown(encabezado("Plan de estudios y oferta", "Planes oficiales de las cinco menciones, materias que no "
                           "pueden coincidir y validación de los datos publicados", "Catálogo"), unsafe_allow_html=True)
    ruta = RAIZ_DATOS / "catalogo" / "plan_estudios.csv"
    if not ruta.exists():
        note("No se encontró data/catalogo/plan_estudios.csv. Ejecute scripts/extraer_planes.py.")
        return
    plan = pd.read_csv(ruta)
    t1, t2, t3 = st.tabs(["Planes de estudio", "Materias que no pueden coincidir", "Validación de datos"])
    with t1:
        c1, c2, c3 = st.columns([2, 1, 1])
        mencion = c1.selectbox("Mención", sorted(plan.mencion.unique()))
        sem = c2.selectbox("Semestre", ["Todos"] + [str(i) for i in range(1, 11)] + ["Electivas"])
        solo = c3.toggle("Sólo SIS / INF", value=True)
        v = plan[plan.mencion == mencion]
        if sem == "Electivas":
            v = v[v.tipo == "electiva"]
        elif sem != "Todos":
            v = v[v.semestre == int(sem)]
        if solo:
            v = v[v.sigla.str.match(r"^(SIS|INF) ")]
        ofertadas = {(s.asignatura) for s in ds.sesiones}
        v = v.assign(**{"Ofertada en la gestión": ["Sí" if x in ofertadas else "No" for x in v.sigla]})
        st.dataframe(colorear_estados(v.drop(columns=["mencion_id", "programa", "mencion"])
                                      .rename(columns={"horas_t": "T", "horas_p": "P", "horas_l": "L"}),
                                      ("Ofertada en la gestión",)), hide_index=True, width="stretch")
        st.caption("Fuente: planes de estudio oficiales (PDF) de la carrera. T = teoría, P = práctica, L = laboratorio "
                   "(horas académicas por semana).")
    with t2:
        regs = [e for e in ds.estudiantes.values() if e.tipo == "regular"]
        if not regs:
            note("Este conjunto no tiene cohortes ni estudiantes.")
        else:
            pares: dict[tuple, set] = {}
            por_est: dict[str, list] = {}
            for i in ds.inscripciones:
                if i.estudiante_id in {e.id for e in regs}:
                    por_est.setdefault(i.estudiante_id, []).append(f"{i.asignatura} {i.paralelo}".strip())
            for e, mats in por_est.items():
                mats = sorted(set(mats))
                for x in range(len(mats)):
                    for y in range(x + 1, len(mats)):
                        pares.setdefault((mats[x], mats[y]), set()).add(ds.estudiantes[e].nombre)
            df = pd.DataFrame([{"Materia 1": a, "Materia 2": b, "Cohortes que las cursan juntas": len(c),
                                "Ejemplo": sorted(c)[0]} for (a, b), c in pares.items()])
            df = df.sort_values("Cohortes que las cursan juntas", ascending=False)
            fila_kpis([(len(regs), "Cohortes / estudiantes regulares", ""),
                       (len(df), "Pares que no pueden coincidir", "")])
            st.write("")
            q = st.text_input("Buscar sigla", placeholder="ej. SIS 2610")
            if q.strip():
                df = df[df["Materia 1"].str.contains(q.strip(), case=False) | df["Materia 2"].str.contains(q.strip(), case=False)]
            st.dataframe(df, hide_index=True, width="stretch")
            st.caption("Cada par comparte al menos una cohorte regular (mención · semestre · paralelo): programarlas a la "
                       "misma hora genera un conflicto obligatorio.")
    with t3:
        if ds.pendientes:
            st.markdown('<div class="aviso warn"><ul class="lista-supuestos">' + "".join(
                f"<li>{p}</li>" for p in ds.pendientes) + "</ul></div>", unsafe_allow_html=True)
        else:
            note("Sin observaciones registradas para este conjunto.")


def pagina_revision():
    ds = estado()
    st.markdown(encabezado("Revisión de propuestas", "Aprobar, rechazar y aplicar alternativas dentro del prototipo",
                           "Decisión de apoyo"), unsafe_allow_html=True)
    st.caption("La aprobación es interna al prototipo y no reemplaza la decisión de las autoridades universitarias. "
               "Sólo pueden aprobarse propuestas sin conflictos obligatorios (se reevalúan con los datos actuales).")
    props = st.session_state.propuestas
    if not props:
        note("Aún no hay propuestas. Genere alternativas o espere solicitudes de docentes y auxiliares.")
        return
    tabla = pd.DataFrame([{"Id": p.id, "Estado": ESTADO_TXT[p.estado], "Origen": p.origen, "Autor": p.autor,
                           "Descripción": p.descripcion, "Oblig. antes": p.duros_antes, "Oblig. después": p.duros_despues,
                           "Válida": "Sí" if p.factible else "No", "Penalización blanda": p.blando,
                           "Cambios": len(p.cambios), "Creada": p.creada, "Revisor": p.revisada_por,
                           "Comentario": p.comentario} for p in props])
    st.dataframe(colorear_estados(tabla), hide_index=True, width="stretch")
    st.markdown("#### Comparar propuestas")
    sel = st.multiselect("Propuestas", [p.id for p in props], default=[p.id for p in props][:3])
    if sel:
        filas = []
        for p in props:
            if p.id in sel:
                antes, despues, conf = P.evaluar_cambios(ds, p.cambios, p.escenario) if not P.validar_vigencia(ds, p) else (p.duros_antes, None, [])
                filas.append({"Propuesta": p.id, "Estado": ESTADO_TXT[p.estado], "Oblig. (datos actuales)": despues,
                              "Preferencias incumplidas": sum(c.severidad == "preferencia" for c in conf),
                              "Penalización blanda (AG)": p.blando, "Cambios": len(p.cambios)})
        comp = pd.DataFrame(filas)
        c1, c2 = st.columns([1.3, 1])
        c1.dataframe(colorear_estados(comp), hide_index=True, width="stretch")
        fig = go.Figure(go.Bar(x=comp["Propuesta"], y=comp["Cambios"], name="Cambios", marker_color=AZUL))
        fig.add_bar(x=comp["Propuesta"], y=comp["Oblig. (datos actuales)"].fillna(0), name="Conflictos oblig.",
                    marker_color=ROJO)
        fig.update_layout(barmode="group", title="Cambios y conflictos por propuesta")
        c2.plotly_chart(plotly_layout(fig, 300), width="stretch")

    st.markdown("#### Detalle y decisión")
    pid = st.selectbox("Propuesta", [p.id for p in props], format_func=lambda i: f"{i} · {next(p for p in props if p.id == i).descripcion}")
    p = next(x for x in props if x.id == pid)
    st.markdown(f"**Estado:** {ESTADO_TXT[p.estado]} · **Autor:** {p.autor} · **Origen:** {p.origen} · "
                f"**Escenario:** {p.escenario}")
    st.dataframe(pd.DataFrame(p.texto_cambios(ds)), hide_index=True, width="stretch")
    error = P.validar_vigencia(ds, p)
    if error and p.estado in ("pendiente", "aprobada"):
        warn(error)
    elif not error:
        antes, despues, conf = P.evaluar_cambios(ds, p.cambios, p.escenario)
        c1, c2 = st.columns([1, 1.2])
        c1.markdown(f"**Reevaluación con datos actuales:** {antes} → {despues} conflictos obligatorios")
        c1.dataframe(colorear_estados(estado_restricciones(conf)), hide_index=True, width="stretch")
        with c2:
            mostrar_calendario(ds, P.aplicar_cambios(ds, p.cambios, p.escenario), conf,
                               movidas=p.sesiones_involucradas(), titulo=f"Horario con la propuesta {p.id}")
    comentario = st.text_input("Comentario de revisión", key=f"com_{p.id}")
    c1, c2, c3 = st.columns(3)
    if c1.button("Aprobar", disabled=p.estado != "pendiente", type="primary"):
        exito, msg = P.aprobar(ds, p, autor(), comentario)
        guardar_props()
        (ok if exito else err)(msg)
    if c2.button("Rechazar", disabled=p.estado not in ("pendiente", "aprobada")):
        if not comentario.strip():
            err("Indique el motivo del rechazo en el comentario.")
        else:
            exito, msg = P.rechazar(p, autor(), comentario)
            guardar_props()
            ok(msg)
            st.rerun()
    with c3:
        conf_ap = st.checkbox("Confirmo aplicar como nueva versión vigente", disabled=p.estado != "aprobada")
        if st.button("Aplicar propuesta", disabled=p.estado != "aprobada" or not conf_ap):
            try:
                st.session_state.ds = P.aplicar(ds, p)
                st.session_state.version += 1
                guardar_props()
                ok("Aplicada: se creó la versión reprogramada; las originales se conservan como 'reemplazada'. "
                           "Para conservarla en disco use *Guardar conjunto* en Gestión académica.")
                st.rerun()
            except ValueError as e:
                err(str(e))
    if st.button("Restaurar el horario cargado inicialmente"):
        st.session_state.update(ds=st.session_state.ds_original.copia(), version=st.session_state.version + 1)
        st.rerun()


def pagina_evaluacion():
    ds = estado()
    st.markdown(encabezado("Evaluación y comparación", "Indicadores calculados a partir de ejecuciones reales",
                           "Evaluación"), unsafe_allow_html=True)
    r = st.session_state.get("resultado")
    if r:
        st.markdown("#### Alternativa seleccionada")
        c1, c2 = st.columns([1, 1.4])
        c1.dataframe(pd.DataFrame([{"Indicador": k, "Valor": str(v if v is not None else "No corresponde")}
                                   for k, v in indicadores(r).items()]), hide_index=True, width="stretch")
        ad = tabla_antes_despues(r)
        fig = go.Figure([go.Bar(x=[c.split(" (")[0] for c in ad["Categoría"]], y=ad["Antes"], name="Antes", marker_color=ROJO),
                         go.Bar(x=[c.split(" (")[0] for c in ad["Categoría"]], y=ad["Después"], name="Después", marker_color=VERDE)])
        fig.update_layout(title="Conflictos por categoría: antes vs. después", barmode="group")
        c2.plotly_chart(plotly_layout(fig), width="stretch")
        if r.historial:
            st.plotly_chart(grafico_fitness(r.historial), width="stretch")
    else:
        note("Genere alternativas para ver los indicadores de una ejecución.")
    st.divider()
    st.markdown("#### Comparación de configuraciones (varias ejecuciones)")
    filas = [{"Nombre": n, "Población": c.poblacion, "Generaciones": c.generaciones, "Pc": c.prob_cruce,
              "Pm": c.prob_mutacion, "Elitismo": c.elitismo, "Torneo k": c.torneo_k, "Cruce": c.tipo_cruce,
              "Mutación dirigida": c.mutacion_dirigida} for n, c in CONFIGS_REFERENCIA.items()]
    editor = st.data_editor(pd.DataFrame(filas), num_rows="dynamic", hide_index=True, width="stretch",
                            column_config={"Cruce": st.column_config.SelectboxColumn(options=["uniforme", "un_punto", "dos_puntos"])},
                            key="ed_cfgs")
    c1, c2 = st.columns(2)
    n_sem = c1.number_input("Semillas por configuración", 1, 20, 3)
    sem0 = c2.number_input("Semilla inicial", 0, 10**6, 1)
    if st.button("Ejecutar comparación", type="primary"):
        configs = {str(f["Nombre"]): ConfigAG(
            poblacion=int(f["Población"]), generaciones=int(f["Generaciones"]), prob_cruce=float(f["Pc"]),
            prob_mutacion=float(f["Pm"]), elitismo=int(f["Elitismo"]), torneo_k=int(f["Torneo k"]),
            tipo_cruce=str(f["Cruce"]), mutacion_dirigida=bool(f["Mutación dirigida"]), escenario=escenario_actual())
            for _, f in editor.dropna(subset=["Nombre"]).iterrows()}
        semillas = list(range(int(sem0), int(sem0) + int(n_sem)))
        barra, cont = st.progress(0.0), {"n": 0}

        def prog(nombre, s):
            cont["n"] += 1
            barra.progress(cont["n"] / (len(configs) * len(semillas)), text=f"{nombre} · semilla {s}")
        st.session_state.comparacion = comparar_configuraciones(ds, configs, semillas, prog)
        barra.empty()
    comp = st.session_state.get("comparacion")
    if comp:
        det, res, resultados = comp
        st.dataframe(res, hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        fig = go.Figure(go.Bar(x=res["Configuración"], y=res["Penalización blanda (media)"], marker_color=AZUL,
                               error_y=dict(type="data", array=res["Penalización blanda (desv.)"], color=DORADO)))
        fig.update_layout(title="Penalización blanda media (menor es mejor)")
        c1.plotly_chart(plotly_layout(fig), width="stretch")
        fig2 = go.Figure()
        for i, (n, rs) in enumerate(resultados.items()):
            if rs and rs[0].historial:
                h = pd.DataFrame(rs[0].historial)
                fig2.add_scatter(x=h.generacion, y=h.mejor_duros + h.mejor_blando / 1000, name=n,
                                 line=dict(color=[AZUL, DORADO, VERDE, ROJO, AZUL_3][i % 5]))
        fig2.update_layout(title="Costo del mejor (1ª semilla): duros + blando/1000", xaxis_title="Generación",
                           yaxis_type="log")
        c2.plotly_chart(plotly_layout(fig2), width="stretch")
        with st.expander("Detalle por ejecución"):
            st.dataframe(det, hide_index=True, width="stretch")


def pagina_exportacion():
    ds = estado()
    st.markdown(encabezado("Exportación", "Excel (OpenPyXL) y CSV", "Salidas"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Datos")
        st.download_button("Copia de trabajo (Excel)", dataset_a_excel(ds), "horario_trabajo.xlsx", width="stretch")
        st.download_button("Horario cargado inicialmente (Excel)", dataset_a_excel(st.session_state.ds_original),
                           "horario_original.xlsx", width="stretch")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, df in dataset_a_tablas(ds).items():
                z.writestr(f"{n}.csv", df.to_csv(index=False))
            z.writestr("meta.json", json.dumps(meta_de(ds), ensure_ascii=False, indent=2))
        st.download_button("Copia de trabajo (CSV, zip)", buf.getvalue(), "horario_csv.zip", width="stretch")
        conf = conflictos_a_df(ds, detectar_conflictos(ds, escenario=escenario_actual()))
        st.download_button("Reporte de conflictos (Excel)", exportar_excel({"conflictos": conf}), "conflictos.xlsx",
                           width="stretch")
    with c2:
        st.markdown("##### Algoritmo genético y propuestas")
        r = st.session_state.get("resultado")
        if r:
            hojas = {
                "indicadores": pd.DataFrame([{"Indicador": k, "Valor": v} for k, v in indicadores(r).items()]),
                "configuracion": pd.DataFrame([{"Parámetro": k, "Valor": str(v)} for k, v in vars(r.config).items()]),
                "horario_propuesto": sesiones_a_df(r.sesiones_propuestas), "cambios": pd.DataFrame(r.cambios),
                "conflictos_antes": conflictos_a_df(ds, r.eval_original.conflictos),
                "conflictos_despues": conflictos_a_df(ds, r.eval_mejor.conflictos),
                "restricciones": estado_restricciones(r.eval_mejor.conflictos, r.config.categorias_duras),
                "historial_generaciones": pd.DataFrame(r.historial),
                "pendientes": pd.DataFrame({"Restricción": r.restricciones_pendientes() + r.diagnostico}),
            }
            st.download_button("Alternativa seleccionada (Excel)", exportar_excel(hojas), "alternativa_ag.xlsx",
                               width="stretch", type="primary")
        ses_exp = r.sesiones_propuestas if r else ds.sesiones_activas(escenario_actual())
        if ds.estudiantes:
            st.download_button("Horario por cohorte / estudiante (Excel)", exportar_excel({
                "por_cohorte": horario_por_cohorte(ds, ses_exp), "por_materia": tabla_horario(ds, ses_exp)}),
                "horario_por_cohorte.xlsx", width="stretch")
        props = st.session_state.propuestas
        if props:
            st.download_button("Propuestas y estado de revisión (Excel)", exportar_excel({
                "propuestas": pd.DataFrame([{k: v for k, v in vars(p).items() if k not in ("cambios", "configuracion")}
                                            for p in props]),
                "cambios": pd.DataFrame([{"Propuesta": p.id, **c} for p in props for c in p.texto_cambios(ds)])}),
                "propuestas.xlsx", width="stretch")
        comp = st.session_state.get("comparacion")
        if comp:
            st.download_button("Comparación de configuraciones (Excel)",
                               exportar_excel({"resumen": comp[1], "detalle": comp[0]}), "comparacion_ag.xlsx",
                               width="stretch")


# =========================================================================== #
# DOCENTE Y AUXILIAR
# =========================================================================== #
def sin_identidad() -> bool:
    if not st.session_state.get("identidad"):
        note("Seleccione una persona en la barra lateral. Si no hay ninguna, este conjunto de datos no tiene "
                "responsables registrados (en el caso real no se inventan); use un conjunto simulado.")
        return True
    return False


def mis_sesiones(ds):
    return [s for s in ds.sesiones_activas(escenario_actual()) if s.responsable == st.session_state.identidad]


def pagina_mis_actividades(titulo="Mis actividades"):
    ds = estado()
    st.markdown(encabezado(titulo, "Consulta de actividades asignadas", st.session_state.rol), unsafe_allow_html=True)
    if sin_identidad():
        return
    ses = mis_sesiones(ds)
    conf = detectar_conflictos(ds, escenario=escenario_actual())
    mias = [c for c in conf if set(c.sesiones) & {s.id for s in ses}]
    fila_kpis([(len(ses), "Actividades", ""), (round(sum(s.duracion for s in ses) / 60, 1), "Horas semanales", ""),
               (sum(c.severidad == "obligatorio" for c in mias), "Conflictos que me involucran",
                "mal" if any(c.severidad == "obligatorio" for c in mias) else "bien")])
    st.write("")
    st.markdown(leyenda_html(), unsafe_allow_html=True)
    mostrar_calendario(ds, ses, conf)
    tabla_sesiones(ds, ses, conf)
    if mias:
        st.markdown("#### Conflictos que involucran mis actividades")
        st.dataframe(conflictos_a_df(ds, mias), hide_index=True, width="stretch")


def pagina_mi_disponibilidad():
    ds = estado()
    st.markdown(encabezado("Mi disponibilidad", "Registre los intervalos en los que puede realizar actividades",
                           st.session_state.rol), unsafe_allow_html=True)
    if sin_identidad():
        return
    ent = st.session_state.identidad
    es_est = st.session_state.rol == "Estudiante"
    ses = ds.sesiones_de_estudiante(ent, escenario_actual()) if es_est else mis_sesiones(ds)
    st.markdown(disponibilidad_html(ds, ent, ses), unsafe_allow_html=True)
    editor_disponibilidad(ds, ent, "propia",
                          "Para estudiantes es una PREFERENCIA (restricción blanda): el AG intenta respetarla. "
                          if es_est else "Para docentes y auxiliares es una restricción DURA: el AG no asigna "
                          "actividades fuera de estos intervalos.")


def selector_franja(ds, s, clave):
    dom = construir_dominio(ds, s)
    if not dom.franjas:
        err("Esta actividad no tiene franjas válidas según su disponibilidad y la franja institucional.")
        return None
    dias = sorted({d for d, _ in dom.franjas})
    c1, c2, c3 = st.columns(3)
    dia = c1.selectbox("Nuevo día", dias, format_func=lambda d: DIAS[d], key=f"d_{clave}",
                       index=dias.index(s.dia) if s.dia in dias else 0)
    horas = [i for d, i in dom.franjas if d == dia]
    ini = c2.selectbox("Nueva hora de inicio", horas, format_func=lambda i: f"{a_hhmm(i)}–{a_hhmm(i + s.duracion)}",
                       key=f"h_{clave}", index=horas.index(s.inicio) if s.inicio in horas else 0)
    amb = c3.selectbox("Ambiente", dom.ambientes, format_func=lambda a: a or "(sin dato)", key=f"a_{clave}",
                       index=dom.ambientes.index(s.ambiente) if s.ambiente in dom.ambientes else 0)
    return dia, ini, amb


def pagina_proponer_cambio():
    ds = estado()
    st.markdown(encabezado("Proponer cambio de horario", "La propuesta se evalúa con las mismas restricciones que "
                           "el AG y queda pendiente de revisión", st.session_state.rol), unsafe_allow_html=True)
    if sin_identidad():
        return
    ses = [s for s in mis_sesiones(ds) if not s.fija]
    if not ses:
        note("No tiene actividades reprogramables (las fijas sólo puede liberarlas el responsable académico).")
        return
    s = next(x for x in ses if x.id == st.selectbox("Actividad", [x.id for x in ses],
                                                     format_func=lambda i: ds.nombre_sesion(next(x for x in ses if x.id == i))))
    st.caption(f"Horario actual: {DIAS[s.dia]} {a_hhmm(s.inicio)}–{a_hhmm(s.fin)} · {len(ds.inscritos(s))} inscritos")
    sel = selector_franja(ds, s, "doc")
    if not sel:
        return
    cambios = [{"sesion": s.id, "dia": sel[0], "inicio": sel[1], "fin": sel[1] + s.duracion, "ambiente": sel[2]}]
    antes, despues, conf = P.evaluar_cambios(ds, cambios, escenario_actual())
    (ok if despues == 0 else warn)(f"Conflictos obligatorios: {antes} antes → {despues} con este cambio.")
    mios = [c for c in conf if s.id in c.sesiones]
    if mios:
        st.dataframe(conflictos_a_df(ds, mios), hide_index=True, width="stretch")
    motivo = st.text_input("Motivo de la propuesta")
    if st.button("Enviar propuesta", type="primary", disabled=not motivo.strip()):
        p = P.propuesta_manual(ds, s.id, sel[0], sel[1], sel[2], autor(), motivo, escenario_actual(),
                               st.session_state.propuestas)
        st.session_state.propuestas.append(p)
        guardar_props()
        ok(f"Propuesta {p.id} enviada (pendiente de revisión).")


def pagina_alternativas_generadas():
    ds = estado()
    st.markdown(encabezado("Alternativas generadas", "Propuestas que involucran mis actividades",
                           st.session_state.rol), unsafe_allow_html=True)
    if sin_identidad():
        return
    mias = {s.id for s in mis_sesiones(ds)} | {s.id for s in ds.sesiones if s.responsable == st.session_state.identidad}
    props = [p for p in st.session_state.propuestas if p.sesiones_involucradas() & mias]
    if not props:
        note("No hay propuestas que involucren sus actividades.")
        return
    for p in props:
        with st.expander(f"{p.id} · {ESTADO_TXT[p.estado]} · {p.descripcion}"):
            st.markdown(f"Autor: {p.autor} · Conflictos obligatorios: {p.duros_antes} → {p.duros_despues}"
                        + (f" · Comentario: {p.comentario}" if p.comentario else ""))
            st.dataframe(pd.DataFrame([f for f in p.texto_cambios(ds) if f["Sesión"] in mias]), hide_index=True,
                         width="stretch")


def pagina_conflictos_estudiantes():
    ds = estado()
    st.markdown(encabezado("Conflictos con estudiantes inscritos", "Estudiantes de mis auxiliaturas que tienen otra "
                           "actividad a la misma hora", "Auxiliar"), unsafe_allow_html=True)
    if sin_identidad():
        return
    ids = {s.id for s in mis_sesiones(ds)}
    conf = [c for c in detectar_conflictos(ds, escenario=escenario_actual())
            if c.categoria in ("estudiante", "disp_estudiante") and set(c.sesiones) & ids]
    fila_kpis([(sum(c.categoria == "estudiante" for c in conf), "Choques con otras actividades", "mal" if conf else "bien"),
               (sum(c.afectados for c in conf if c.categoria == "estudiante"), "Estudiantes afectados (suma)", ""),
               (sum(c.categoria == "disp_estudiante" for c in conf), "Fuera de disponibilidad declarada", "")])
    st.write("")
    if conf:
        st.dataframe(conflictos_a_df(ds, conf), hide_index=True, width="stretch")
    else:
        ok("Ningún estudiante inscrito tiene conflictos con sus auxiliaturas.")


def pagina_solicitar_alternativas():
    ds = estado()
    st.markdown(encabezado("Solicitar alternativas", "El AG busca nuevos horarios sólo para las auxiliaturas "
                           "seleccionadas; el resto del horario se mantiene", "Auxiliar"), unsafe_allow_html=True)
    if sin_identidad():
        return
    ses = [s for s in mis_sesiones(ds) if not s.fija]
    if not ses:
        note("No tiene actividades reprogramables.")
        return
    elegidas = st.multiselect("Actividades a reprogramar", [s.id for s in ses], default=[s.id for s in ses],
                              format_func=lambda i: ds.nombre_sesion(next(s for s in ses if s.id == i)))
    c1, c2 = st.columns(2)
    sem = c1.number_input("Semilla", 0, 10**6, 42)
    gens = c2.number_input("Generaciones", 10, 1000, 150, 10)
    if st.button("Buscar alternativas", type="primary", disabled=not elegidas):
        cfg = ConfigAG(semilla=int(sem), generaciones=int(gens), solo_sesiones=tuple(elegidas), escenario=escenario_actual())
        st.session_state.res_aux = ejecutar_con_progreso(ds, cfg)
    r = st.session_state.get("res_aux")
    if r and set(r.config.solo_sesiones or ()) <= {s.id for s in ses}:
        mostrar_resultado(ds, r, registrar=False)
        if st.button("Enviar como propuesta", disabled=not r.cambios):
            p = P.desde_resultado(r, autor(), "Solicitud de alternativas del auxiliar", st.session_state.propuestas)
            st.session_state.propuestas.append(p)
            guardar_props()
            ok(f"Propuesta {p.id} enviada (pendiente de revisión)."
                       + ("" if p.factible else " Es inviable: el responsable no podrá aprobarla."))


# =========================================================================== #
# ESTUDIANTE
# =========================================================================== #
def pagina_mi_horario():
    ds = estado()
    st.markdown(encabezado("Mi horario", "Consulta de actividades según mis inscripciones (sólo lectura)",
                           "Estudiante"), unsafe_allow_html=True)
    if sin_identidad():
        return
    e = st.session_state.identidad
    aviso_datos_incompletos(ds)
    ses = ds.sesiones_de_estudiante(e, escenario_actual())
    # todas estas sesiones incluyen al estudiante: cualquier choque de inscritos lo involucra
    conf = [c for c in detectar_conflictos(ds, ses, escenario_actual()) if c.categoria == "estudiante"]
    ins = [i for i in ds.inscripciones if i.estudiante_id == e]
    fila_kpis([(len(ins), "Materias inscritas", ""), (len(ses), "Actividades", ""),
               (len(conf), "Choques en mi horario", "mal" if conf else "bien")])
    st.write("")
    st.markdown(leyenda_html(), unsafe_allow_html=True)
    mostrar_calendario(ds, ses, conf)
    st.markdown("#### Mis inscripciones")
    st.dataframe(pd.DataFrame([{"Materia": ds.asignaturas[i.asignatura].nombre if i.asignatura in ds.asignaturas else i.asignatura,
                                "Paralelo": i.paralelo or "(sin especificar)",
                                "Tipos": ", ".join(i.tipos) if i.tipos else "Todas"} for i in ins]),
                 hide_index=True, width="stretch")
    if conf:
        st.markdown("#### Choques detectados")
        st.dataframe(conflictos_a_df(ds, conf), hide_index=True, width="stretch")
    st.caption("El estudiante no puede modificar horarios académicos; puede registrar su disponibilidad.")


# =========================================================================== #
PAGINA_FN = {
    "Resumen": pagina_resumen, "Calendario semanal": pagina_calendario, "Gestión académica": pagina_gestion,
    "Plan de estudios": pagina_plan_estudios,
    "Disponibilidad": pagina_disponibilidad, "Detección de conflictos": pagina_conflictos,
    "Generación de alternativas (AG)": pagina_generacion, "Revisión de propuestas": pagina_revision,
    "Evaluación y comparación": pagina_evaluacion, "Exportación": pagina_exportacion,
    "Mis actividades": pagina_mis_actividades, "Mi disponibilidad": pagina_mi_disponibilidad,
    "Proponer cambio": pagina_proponer_cambio, "Alternativas generadas": pagina_alternativas_generadas,
    "Mis auxiliaturas": lambda: pagina_mis_actividades("Mis auxiliaturas"),
    "Conflictos con estudiantes": pagina_conflictos_estudiantes,
    "Solicitar alternativas": pagina_solicitar_alternativas, "Mi horario": pagina_mi_horario,
}

PAGINA_FN[barra_lateral()]()
