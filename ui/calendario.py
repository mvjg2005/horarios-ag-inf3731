"""Cuadrícula semanal en HTML/CSS (lunes a sábado) con detección visual de superposiciones."""
from __future__ import annotations

import html

from core.modelo import DIAS, NOMBRE_TIPO, Dataset, Sesion, a_hhmm
from .estilos import AZUL, COLOR_TIPO, DORADO, GRIS, LINEA, ROJO, SANS, SERIF, VERDE

PX_MIN = 1.05   # píxeles por minuto


def _carriles(sesiones: list[Sesion]) -> dict[str, tuple[int, int]]:
    """Asigna carriles a sesiones superpuestas del mismo día para dibujarlas lado a lado.
    Devuelve {id: (carril, total_carriles_del_bloque)}."""
    res: dict[str, tuple[int, int]] = {}
    orden = sorted(sesiones, key=lambda s: (s.inicio, -s.fin, s.id))
    bloque: list[Sesion] = []
    fin_bloque = -1

    def cerrar(b):
        fines: list[int] = []
        asignado = {}
        for s in b:
            for k, f in enumerate(fines):
                if f <= s.inicio:
                    fines[k] = s.fin
                    asignado[s.id] = k
                    break
            else:
                fines.append(s.fin)
                asignado[s.id] = len(fines) - 1
        for sid, k in asignado.items():
            res[sid] = (k, len(fines))

    for s in orden:
        if bloque and s.inicio >= fin_bloque:
            cerrar(bloque)
            bloque, fin_bloque = [], -1
        bloque.append(s)
        fin_bloque = max(fin_bloque, s.fin)
    if bloque:
        cerrar(bloque)
    return res


FUENTE = f"font-family:{SANS};"
MARCO = f"overflow-x:auto;border:1px solid {LINEA};border-radius:4px;background:#fff;{FUENTE}"


def _cabecera(dias, titulo=""):
    p = [f'<div style="{MARCO}">']
    if titulo:
        p.append(f'<div style="padding:10px 14px;font-family:{SERIF};font-size:15px;font-weight:600;color:{AZUL};'
                 f'border-bottom:1px solid {LINEA};">{html.escape(titulo)}</div>')
    p.append(f'<div style="display:grid;grid-template-columns:52px repeat({len(dias)},minmax(118px,1fr));'
             f'min-width:{52 + 118 * len(dias)}px;">')
    p.append(f'<div style="border-bottom:1px solid {LINEA};"></div>')
    for d in dias:
        p.append(f'<div style="text-align:center;padding:10px 4px 8px;font-size:11px;font-weight:600;letter-spacing:.14em;'
                 f'text-transform:uppercase;color:{AZUL};border-left:1px solid {LINEA};border-bottom:2px solid {AZUL};">'
                 f'{DIAS[d]}</div>')
    return p


def _columna_horas(p, ini, fin, alto):
    p.append(f'<div style="position:relative;height:{alto}px;">')
    for h in range(ini, fin, 60):
        p.append(f'<div style="position:absolute;top:{(h - ini) * PX_MIN - 6}px;right:8px;font-size:10.5px;'
                 f'color:{GRIS};font-variant-numeric:tabular-nums;">{a_hhmm(h)}</div>')
    p.append('</div>')


def _lineas(p, ini, fin):
    for h in range(ini, fin, 30):
        estilo = f"1px solid {LINEA}" if h % 60 == 0 else "1px dotted #EEEAE2"
        p.append(f'<div style="position:absolute;top:{(h - ini) * PX_MIN}px;left:0;right:0;border-top:{estilo};"></div>')


def calendario_html(ds: Dataset, sesiones: list[Sesion], en_conflicto: set[str] | None = None,
                    movidas: set[str] | None = None, extra: list[Sesion] | None = None,
                    titulo: str = "") -> str:
    """Genera la cuadrícula. ``extra`` son sesiones a mostrar atenuadas (p. ej. reemplazadas)."""
    en_conflicto = en_conflicto or set()
    movidas = movidas or set()
    extra = extra or []
    todas = sesiones + extra
    ini = min([ds.hora_inicio] + [s.inicio for s in todas])
    fin = max([ds.hora_fin] + [s.fin for s in todas])
    ini, fin = (ini // 60) * 60, -(-fin // 60) * 60
    alto = int((fin - ini) * PX_MIN)
    usados = set(ds.dias) | {s.dia for s in todas}
    dias = [d for d in range(6) if d in usados] or list(range(6))
    p = _cabecera(dias, titulo)
    _columna_horas(p, ini, fin, alto)
    for d in dias:
        del_dia = [s for s in sesiones if s.dia == d]
        atenuadas = [s for s in extra if s.dia == d]
        carriles = _carriles(del_dia + atenuadas)
        p.append(f'<div style="position:relative;height:{alto}px;border-left:1px solid {LINEA};">')
        _lineas(p, ini, fin)
        for s in atenuadas:
            k, n = carriles[s.id]
            p.append(_bloque(ds, s, k, n, ini, atenuada=True))
        for s in sorted(del_dia, key=lambda s: s.inicio):
            k, n = carriles[s.id]
            p.append(_bloque(ds, s, k, n, ini, conflicto=s.id in en_conflicto, movida=s.id in movidas))
        p.append('</div>')
    p.append('</div></div>')
    return "".join(p)


ETIQ_TIPO = {"teoria": "Teoría", "laboratorio": "Lab.", "auxiliatura": "Aux."}


def _bloque(ds, s: Sesion, carril, total, ini, conflicto=False, movida=False, atenuada=False) -> str:
    color = COLOR_TIPO.get(s.tipo, "#555")
    top = (s.inicio - ini) * PX_MIN
    alto = max(s.duracion * PX_MIN - 2, 16)
    ancho = 100 / total
    izq = carril * ancho
    asig = ds.asignaturas.get(s.asignatura)
    nombre = asig.nombre if asig else s.asignatura
    resp = ds.personas[s.responsable].nombre if s.responsable in ds.personas else "Responsable: sin dato"
    amb = ds.ambientes[s.ambiente].nombre if s.ambiente in ds.ambientes else "Ambiente: sin dato"
    n_ins = len(ds.inscritos(s))
    paralelo = (f"Paralelo {s.paralelo}" if s.paralelo else "Paralelo: sin dato") + f" · {n_ins} inscrito(s)"
    estado = {"vigente": "", "reemplazada": "Reemplazada", "pendiente_confirmacion": "Pendiente de confirmación"}[s.estado]
    tip = "\n".join(x for x in [
        f"{NOMBRE_TIPO.get(s.tipo, s.tipo)}: {nombre}",
        f"{DIAS[s.dia]} {a_hhmm(s.inicio)}–{a_hhmm(s.fin)} ({s.duracion} min)", paralelo, resp, amb,
        ("Horario fijo" if s.fija else "Reprogramable") + " · " + ("Obligatoria" if s.obligatoria else "No obligatoria"),
        estado, s.observacion, "Conflicto obligatorio" if conflicto else "", "Movida por el algoritmo" if movida else ""] if x)
    estilo = [f"position:absolute;top:{top + 1}px;height:{alto}px;left:calc({izq}% + 2px);width:calc({ancho}% - 4px);",
              f"border-radius:3px;padding:4px 6px;font-size:10.5px;line-height:1.25;overflow:hidden;",
              "overflow-wrap:break-word;cursor:default;"]
    if atenuada:
        estilo.append(f"background:repeating-linear-gradient(135deg,#F1EEE8,#F1EEE8 5px,#E6E1D7 5px,#E6E1D7 10px);"
                      f"color:{GRIS};border:1px solid #D8D2C6;text-decoration:line-through;")
    else:
        estilo.append(f"background:{color};color:#fff;border-left:3px solid #00000033;")
        sombras = []
        if conflicto:
            sombras.append(f"0 0 0 2px {ROJO}")
        if movida:
            sombras.append(f"inset 0 0 0 2px {DORADO}")
        if sombras:
            estilo.append(f"box-shadow:{','.join(sombras)};")
        if s.estado == "pendiente_confirmacion":
            estilo.append("outline:1.5px dashed #FFFFFFB3;outline-offset:-4px;")
    # marcas tipográficas discretas en la esquina (sin íconos)
    marcas = ""
    if conflicto and not atenuada:
        marcas += (f'<span style="position:absolute;top:0;right:0;width:0;height:0;border-top:11px solid {ROJO};'
                   f'border-left:11px solid transparent;"></span>')
    if movida and not atenuada:
        marcas += (f'<span style="position:absolute;bottom:3px;right:4px;width:6px;height:6px;border-radius:50%;'
                   f'background:{DORADO};"></span>')
    etiqueta = ETIQ_TIPO.get(s.tipo, s.tipo)
    if total >= 2:
        contenido = f'<span style="opacity:.8">{etiqueta}</span><br><b>{html.escape(s.asignatura)}</b>'
    else:
        contenido = (f'<span style="opacity:.8;text-transform:uppercase;letter-spacing:.06em;font-size:9.5px">'
                     f'{etiqueta}{" · " + html.escape(s.paralelo) if s.paralelo else ""}</span><br>'
                     f'<b style="font-weight:600">{html.escape(nombre)}</b><br>'
                     f'<span style="opacity:.85;font-variant-numeric:tabular-nums">{a_hhmm(s.inicio)}–{a_hhmm(s.fin)}</span>'
                     f'{"<br><span style=opacity:.75>" + html.escape(s.ambiente) + "</span>" if s.ambiente and alto > 60 else ""}')
    return f'<div title="{html.escape(tip)}" style="{"".join(estilo)}">{marcas}{contenido}</div>'


def leyenda_html() -> str:
    def m(muestra, texto):
        return f'<span><i style="{muestra}"></i>{texto}</span>'
    partes = [m(f"background:{COLOR_TIPO['teoria']}", "Clase teórica"),
              m(f"background:{COLOR_TIPO['laboratorio']}", "Laboratorio"),
              m(f"background:{COLOR_TIPO['auxiliatura']}", "Auxiliatura"),
              m(f"background:#fff;box-shadow:0 0 0 2px {ROJO}", "Conflicto obligatorio"),
              m(f"background:#fff;box-shadow:inset 0 0 0 2px {DORADO}", "Movida por el algoritmo"),
              m("background:#fff;outline:1.5px dashed #8C6D2A;outline-offset:-3px", "Pendiente de confirmación"),
              m("background:repeating-linear-gradient(135deg,#F1EEE8,#F1EEE8 3px,#E0DACF 3px,#E0DACF 6px)",
                "Versión reemplazada")]
    return '<div class="leyenda">' + "".join(partes) + "</div>"


def disponibilidad_html(ds: Dataset, entidad_id: str, sesiones: list[Sesion] | None = None) -> str:
    """Cuadrícula con los intervalos de disponibilidad de una entidad y, encima, sus
    sesiones vigentes. Sin filas de disponibilidad = disponible en toda la franja."""
    disp = ds.disponibilidad_de(entidad_id)
    ini, fin = (ds.hora_inicio // 60) * 60, -(-ds.hora_fin // 60) * 60
    alto = int((fin - ini) * PX_MIN)
    sesiones = sesiones or []
    dias = list(range(6))
    p = _cabecera(dias)
    _columna_horas(p, ini, fin, alto)
    for d in dias:
        fondo = "#fff" if d in ds.dias else "#F4F1EB"
        p.append(f'<div style="position:relative;height:{alto}px;border-left:1px solid {LINEA};background:{fondo};">')
        _lineas(p, ini, fin)
        intervalos = [(x.inicio, x.fin) for x in disp if x.dia == d] if disp else (
            [(ds.hora_inicio, ds.hora_fin)] if d in ds.dias else [])
        for a, b in intervalos:
            p.append(f'<div style="position:absolute;top:{(a - ini) * PX_MIN}px;height:{(b - a) * PX_MIN}px;left:0;right:0;'
                     f'background:{VERDE}14;border-left:3px solid {VERDE};"></div>')
        for s in [x for x in sesiones if x.dia == d]:
            ok = ds.disponible(entidad_id, s.dia, s.inicio, s.fin)
            borde = "" if ok else f"box-shadow:0 0 0 2px {ROJO};"
            p.append(f'<div title="{html.escape(ds.nombre_sesion(s))}" style="position:absolute;'
                     f'top:{(s.inicio - ini) * PX_MIN + 1}px;height:{s.duracion * PX_MIN - 2}px;left:16%;right:4px;'
                     f'background:{COLOR_TIPO.get(s.tipo, "#555")};{borde}border-radius:3px;color:#fff;font-size:10.5px;'
                     f'padding:3px 5px;overflow:hidden;"><b>{html.escape(s.asignatura)}</b> '
                     f'{a_hhmm(s.inicio)}{"" if ok else "<br>Fuera de disponibilidad"}</div>')
        p.append('</div>')
    p.append('</div></div>')
    return "".join(p)
