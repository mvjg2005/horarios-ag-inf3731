"""
Persistencia e intercambio de datos: CSV (una carpeta por conjunto de datos) y Excel
(un libro con una hoja por tabla). Conversión Dataset <-> DataFrames de pandas.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from .modelo import (DIAS, Ambiente, Asignatura, Dataset, Disponibilidad, Estudiante,
                     Inscripcion, Persona, Sesion, a_hhmm, a_minutos, indice_dia)

RAIZ_DATOS = Path(__file__).resolve().parent.parent / "data"

COLUMNAS = {
    "asignaturas": ["clave", "codigo", "nombre", "semestre", "horas_teoria",
                    "horas_laboratorio", "horas_auxiliatura"],
    "estudiantes": ["id", "nombre", "semestre", "tipo"],
    "inscripciones": ["estudiante_id", "asignatura", "paralelo", "tipos"],
    "personas": ["id", "nombre", "rol"],
    "ambientes": ["id", "nombre", "tipo", "capacidad"],
    "disponibilidad": ["entidad_id", "dia", "inicio", "fin"],
    "sesiones": ["id", "asignatura", "tipo", "paralelo", "dia", "inicio", "fin",
                 "responsable", "ambiente", "duracion_requerida_min", "fija", "obligatoria",
                 "estado", "reemplaza", "origen", "dias_permitidos", "tipo_ambiente",
                 "observacion"],
}
TABLAS = list(COLUMNAS)


# --------------------------------------------------------------------------- #
# Helpers de limpieza
# --------------------------------------------------------------------------- #
def _txt(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def _opt(v):
    s = _txt(v)
    return s or None


def _bool(v, defecto=True) -> bool:
    s = _txt(v).lower()
    if not s:
        return defecto
    return s in {"si", "sí", "s", "true", "1", "yes", "x", "verdadero"}


def _num(v, defecto=0.0) -> float:
    s = _txt(v)
    try:
        return float(s.replace(",", ".")) if s else defecto
    except ValueError:
        return defecto


# --------------------------------------------------------------------------- #
# Dataset -> DataFrames
# --------------------------------------------------------------------------- #
def dataset_a_tablas(ds: Dataset) -> dict[str, pd.DataFrame]:
    t = {
        "asignaturas": pd.DataFrame([{
            "clave": a.clave, "codigo": a.codigo, "nombre": a.nombre, "semestre": a.semestre,
            "horas_teoria": a.horas_teoria, "horas_laboratorio": a.horas_laboratorio,
            "horas_auxiliatura": a.horas_auxiliatura} for a in ds.asignaturas.values()],
            columns=COLUMNAS["asignaturas"]),
        "estudiantes": pd.DataFrame([vars(e) for e in ds.estudiantes.values()], columns=COLUMNAS["estudiantes"]),
        "inscripciones": pd.DataFrame([{
            "estudiante_id": i.estudiante_id, "asignatura": i.asignatura, "paralelo": i.paralelo,
            "tipos": ";".join(i.tipos) if i.tipos else ""} for i in ds.inscripciones],
            columns=COLUMNAS["inscripciones"]),
        "personas": pd.DataFrame([vars(p) for p in ds.personas.values()], columns=COLUMNAS["personas"]),
        "ambientes": pd.DataFrame([vars(a) for a in ds.ambientes.values()], columns=COLUMNAS["ambientes"]),
        "disponibilidad": pd.DataFrame([{
            "entidad_id": d.entidad_id, "dia": DIAS[d.dia], "inicio": a_hhmm(d.inicio),
            "fin": a_hhmm(d.fin)} for d in ds.disponibilidad], columns=COLUMNAS["disponibilidad"]),
        "sesiones": sesiones_a_df(ds.sesiones),
    }
    return t


def sesiones_a_df(sesiones: list[Sesion]) -> pd.DataFrame:
    filas = []
    for s in sesiones:
        filas.append({
            "id": s.id, "asignatura": s.asignatura, "tipo": s.tipo,
            "paralelo": s.paralelo, "dia": DIAS[s.dia],
            "inicio": a_hhmm(s.inicio), "fin": a_hhmm(s.fin),
            "responsable": s.responsable or "", "ambiente": s.ambiente or "",
            "duracion_requerida_min": str(s.duracion_requerida) if s.duracion_requerida else "",
            "fija": "si" if s.fija else "no", "obligatoria": "si" if s.obligatoria else "no",
            "estado": s.estado, "reemplaza": s.reemplaza or "", "origen": s.origen,
            "dias_permitidos": ";".join(DIAS[d] for d in s.dias_permitidos) if s.dias_permitidos else "",
            "tipo_ambiente": s.tipo_ambiente or "", "observacion": s.observacion,
        })
    return pd.DataFrame(filas, columns=COLUMNAS["sesiones"])


# --------------------------------------------------------------------------- #
# DataFrames -> Dataset
# --------------------------------------------------------------------------- #
class ErrorDatos(ValueError):
    """Error de validación de datos de entrada."""


def tablas_a_dataset(t: dict[str, pd.DataFrame], meta: dict) -> Dataset:
    errores: list[str] = []
    ds = Dataset(
        nombre=meta.get("nombre", "Sin nombre"),
        tipo_datos=meta.get("tipo_datos", "simulado"),
        descripcion=meta.get("descripcion", ""),
        dias=[indice_dia(d) for d in meta.get("dias", DIAS)],
        hora_inicio=a_minutos(meta.get("hora_inicio", "07:00")),
        hora_fin=a_minutos(meta.get("hora_fin", "21:00")),
        resolucion=int(meta.get("resolucion", 30)),
        pendientes=list(meta.get("pendientes", [])),
        modo=meta.get("modo", "reprogramacion"),
    )
    vacio = lambda n: pd.DataFrame(columns=COLUMNAS[n])  # noqa: E731

    for _, r in t.get("asignaturas", vacio("asignaturas")).iterrows():
        clave = _txt(r.get("clave"))
        if not clave:
            continue
        ds.asignaturas[clave] = Asignatura(
            clave=clave, nombre=_txt(r.get("nombre")) or clave, codigo=_txt(r.get("codigo")) or "PENDIENTE",
            semestre=_txt(r.get("semestre")), horas_teoria=_num(r.get("horas_teoria")),
            horas_laboratorio=_num(r.get("horas_laboratorio")),
            horas_auxiliatura=_num(r.get("horas_auxiliatura")))

    for _, r in t.get("estudiantes", vacio("estudiantes")).iterrows():
        eid = _txt(r.get("id"))
        if eid:
            tipo = _txt(r.get("tipo")).lower() or "regular"
            if tipo not in ("regular", "irregular"):
                errores.append(f"Estudiante {eid}: tipo '{tipo}' inválido (use regular/irregular).")
            ds.estudiantes[eid] = Estudiante(eid, _txt(r.get("nombre")) or eid, _txt(r.get("semestre")), tipo)

    for _, r in t.get("personas", vacio("personas")).iterrows():
        pid = _txt(r.get("id"))
        if not pid:
            continue
        rol = _txt(r.get("rol")).lower() or "docente"
        if rol not in ("docente", "auxiliar"):
            errores.append(f"Persona {pid}: rol '{rol}' inválido (use docente/auxiliar).")
        ds.personas[pid] = Persona(pid, _txt(r.get("nombre")) or pid, rol)

    for _, r in t.get("ambientes", vacio("ambientes")).iterrows():
        aid = _txt(r.get("id"))
        if not aid:
            continue
        tipo = _txt(r.get("tipo")).lower() or "aula"
        if tipo not in ("aula", "laboratorio"):
            errores.append(f"Ambiente {aid}: tipo '{tipo}' inválido (use aula/laboratorio).")
        ds.ambientes[aid] = Ambiente(aid, _txt(r.get("nombre")) or aid, tipo, int(_num(r.get("capacidad"))))

    for i, r in t.get("inscripciones", vacio("inscripciones")).iterrows():
        eid = _txt(r.get("estudiante_id"))
        if not eid:
            continue
        if eid not in ds.estudiantes:
            errores.append(f"Inscripción fila {i + 2}: estudiante '{eid}' no registrado.")
            continue
        asig = _txt(r.get("asignatura"))
        if asig not in ds.asignaturas:
            errores.append(f"Inscripción fila {i + 2}: asignatura '{asig}' no registrada.")
            continue
        tipos = [x.strip() for x in _txt(r.get("tipos")).split(";") if x.strip()] or None
        ds.inscripciones.append(Inscripcion(eid, asig, _txt(r.get("paralelo")), tipos))

    ids_entidades = set(ds.personas) | set(ds.estudiantes) | set(ds.ambientes)
    for i, r in t.get("disponibilidad", vacio("disponibilidad")).iterrows():
        eid = _txt(r.get("entidad_id")) or _txt(r.get("persona_id"))   # compatibilidad v1
        if not eid:
            continue
        try:
            if eid not in ids_entidades:
                raise ErrorDatos(f"entidad '{eid}' no registrada")
            d = Disponibilidad(eid, indice_dia(r.get("dia")), a_minutos(r.get("inicio")), a_minutos(r.get("fin")))
            if d.fin <= d.inicio:
                raise ErrorDatos("fin debe ser mayor que inicio")
            ds.disponibilidad.append(d)
        except Exception as e:  # noqa: BLE001
            errores.append(f"Disponibilidad fila {i + 2}: {e}")

    ids_vistos: set[str] = set()
    for i, r in t.get("sesiones", vacio("sesiones")).iterrows():
        sid = _txt(r.get("id"))
        if not sid:
            continue
        try:
            if sid in ids_vistos:
                raise ErrorDatos(f"id duplicado '{sid}'")
            ids_vistos.add(sid)
            ini, fin = a_minutos(r.get("inicio")), a_minutos(r.get("fin"))
            if fin <= ini:
                raise ErrorDatos("la hora de fin debe ser mayor que la de inicio")
            tipo = _txt(r.get("tipo")).lower()
            if tipo not in ("teoria", "laboratorio", "auxiliatura"):
                raise ErrorDatos(f"tipo '{tipo}' inválido")
            dias_p = _txt(r.get("dias_permitidos"))
            dur_req = _txt(r.get("duracion_requerida_min"))
            ses = Sesion(
                id=sid, asignatura=_txt(r.get("asignatura")), tipo=tipo, paralelo=_txt(r.get("paralelo")),
                dia=indice_dia(r.get("dia")), inicio=ini, fin=fin,
                responsable=_opt(r.get("responsable")), ambiente=_opt(r.get("ambiente")),
                duracion_requerida=int(float(dur_req)) if dur_req else None,
                fija=_bool(r.get("fija"), True), obligatoria=_bool(r.get("obligatoria"), True),
                estado=_txt(r.get("estado")) or "vigente", reemplaza=_opt(r.get("reemplaza")),
                origen=_txt(r.get("origen")) or "oficial",
                dias_permitidos=[indice_dia(d) for d in dias_p.split(";") if d.strip()] or None,
                tipo_ambiente=_opt(r.get("tipo_ambiente")), observacion=_txt(r.get("observacion")),
            )
            if ses.estado not in ("vigente", "reemplazada", "pendiente_confirmacion"):
                raise ErrorDatos(f"estado '{ses.estado}' inválido")
            if ses.asignatura and ses.asignatura not in ds.asignaturas:
                raise ErrorDatos(f"asignatura '{ses.asignatura}' no registrada")
            if ses.responsable and ses.responsable not in ds.personas:
                raise ErrorDatos(f"responsable '{ses.responsable}' no registrado")
            if ses.ambiente and ses.ambiente not in ds.ambientes:
                raise ErrorDatos(f"ambiente '{ses.ambiente}' no registrado")
            ds.sesiones.append(ses)
        except Exception as e:  # noqa: BLE001
            errores.append(f"Sesión fila {i + 2} ({sid}): {e}")

    ids = {s.id for s in ds.sesiones}
    for s in ds.sesiones:
        if s.reemplaza and s.reemplaza not in ids:
            errores.append(f"Sesión {s.id}: reemplaza a '{s.reemplaza}', que no existe.")
    if errores:
        raise ErrorDatos("\n".join(errores))
    return ds


def meta_de(ds: Dataset) -> dict:
    return {"nombre": ds.nombre, "tipo_datos": ds.tipo_datos, "descripcion": ds.descripcion,
            "dias": [DIAS[d] for d in ds.dias], "hora_inicio": a_hhmm(ds.hora_inicio),
            "hora_fin": a_hhmm(ds.hora_fin), "resolucion": ds.resolucion,
            "pendientes": ds.pendientes, "modo": ds.modo}


# --------------------------------------------------------------------------- #
# CSV en carpeta
# --------------------------------------------------------------------------- #
def cargar_carpeta(carpeta: str | Path) -> Dataset:
    carpeta = Path(carpeta)
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    tablas = {}
    for n in TABLAS:
        f = carpeta / f"{n}.csv"
        tablas[n] = pd.read_csv(f, dtype=str, keep_default_na=False) if f.exists() else pd.DataFrame(columns=COLUMNAS[n])
    return tablas_a_dataset(tablas, meta)


def guardar_carpeta(ds: Dataset, carpeta: str | Path) -> None:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "meta.json").write_text(json.dumps(meta_de(ds), ensure_ascii=False, indent=2), encoding="utf-8")
    for n, df in dataset_a_tablas(ds).items():
        df.to_csv(carpeta / f"{n}.csv", index=False, encoding="utf-8")


def conjuntos_disponibles() -> dict[str, Path]:
    """{nombre visible: carpeta} de todos los conjuntos de datos en data/."""
    res = {}
    for c in sorted(RAIZ_DATOS.iterdir()):
        if (c / "meta.json").exists():
            meta = json.loads((c / "meta.json").read_text(encoding="utf-8"))
            etiqueta = "REAL" if meta.get("tipo_datos") == "real" else "SIMULADO"
            res[f"[{etiqueta}] {meta.get('nombre', c.name)}"] = c
    return res


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #
def exportar_excel(hojas: dict[str, pd.DataFrame]) -> bytes:
    """Exporta varias tablas a un libro Excel con formato básico."""
    from openpyxl.styles import Font, PatternFill

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for nombre, df in hojas.items():
            df.to_excel(xw, sheet_name=nombre[:31], index=False)
            ws = xw.sheets[nombre[:31]]
            for celda in ws[1]:
                celda.font = Font(bold=True, color="FFFFFF")
                celda.fill = PatternFill("solid", fgColor="0B1F3A")
            for col in ws.columns:
                ancho = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, ancho + 2), 60)
    return buf.getvalue()


def dataset_a_excel(ds: Dataset) -> bytes:
    hojas = dataset_a_tablas(ds)
    m = meta_de(ds)
    hojas = {"meta": pd.DataFrame([{"clave": k, "valor": json.dumps(v, ensure_ascii=False)
                                    if isinstance(v, list) else v} for k, v in m.items()]), **hojas}
    return exportar_excel(hojas)


def excel_a_dataset(contenido: bytes, meta_defecto: dict | None = None) -> Dataset:
    """Importa un libro con hojas asignaturas, estudiantes, inscripciones, personas,
    ambientes, disponibilidad y sesiones (y opcionalmente meta)."""
    libro = pd.read_excel(io.BytesIO(contenido), sheet_name=None, dtype=str)
    libro = {k.strip().lower(): v.fillna("") for k, v in libro.items()}
    meta = dict(meta_defecto or {})
    if "meta" in libro:
        for _, r in libro["meta"].iterrows():
            k, v = _txt(r.get("clave")), _txt(r.get("valor"))
            if k in ("dias", "pendientes"):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    v = [x.strip() for x in v.split(";") if x.strip()]
            meta[k] = v
    faltan = [n for n in ("sesiones",) if n not in libro]
    if faltan:
        raise ErrorDatos(f"El libro no contiene la hoja obligatoria: {', '.join(faltan)}")
    return tablas_a_dataset({n: libro.get(n, pd.DataFrame(columns=COLUMNAS[n])) for n in TABLAS}, meta)
