"""
Modelo de datos del sistema de horarios.

Entidades:
    Asignatura, Estudiante, Inscripcion (estudiante -> asignatura + paralelo),
    Persona (docente / auxiliar), Ambiente (aula / laboratorio, con capacidad),
    Disponibilidad (de una persona, estudiante o ambiente) y Sesion (una clase
    teórica, laboratorio o auxiliatura de un paralelo).

Los estudiantes NO se asumen iguales por semestre: cada uno asiste sólo a las
sesiones de las asignaturas y paralelos en los que está inscrito.

El conjunto completo de datos se agrupa en un objeto ``Dataset``.
Las horas se manejan internamente en MINUTOS desde las 00:00 para que la
comparación de intervalos sea exacta (ej. 16:30 -> 990).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
TIPOS_SESION = ["teoria", "laboratorio", "auxiliatura"]
NOMBRE_TIPO = {"teoria": "Clase teórica", "laboratorio": "Laboratorio", "auxiliatura": "Auxiliatura"}
ESTADOS = ["vigente", "reemplazada", "pendiente_confirmacion"]
TIPOS_AMBIENTE = ["aula", "laboratorio"]
LUN, MAR, MIE, JUE, VIE, SAB = range(6)


# --------------------------------------------------------------------------- #
# Utilidades de tiempo
# --------------------------------------------------------------------------- #
def a_minutos(hhmm: str) -> int:
    """'16:30' -> 990. Acepta también '7:00' y objetos time de Excel."""
    if hasattr(hhmm, "hour"):
        return hhmm.hour * 60 + hhmm.minute
    texto = str(hhmm).strip()
    if texto.count(":") == 2:          # '16:30:00'
        texto = texto.rsplit(":", 1)[0]
    h, m = texto.split(":")
    return int(h) * 60 + int(m)


def a_hhmm(minutos: int) -> str:
    """990 -> '16:30'."""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def indice_dia(nombre: str) -> int:
    """Normaliza el nombre del día (con o sin tilde) y devuelve su índice 0..5."""
    limpio = str(nombre).strip().lower()
    limpio = (limpio.replace("á", "a").replace("é", "e").replace("í", "i")
              .replace("ó", "o").replace("ú", "u"))
    base = [d.lower().replace("é", "e").replace("á", "a") for d in DIAS]
    if limpio not in base:
        raise ValueError(f"Día no reconocido: {nombre!r}")
    return base.index(limpio)


def se_superponen(ini_a: int, fin_a: int, ini_b: int, fin_b: int) -> bool:
    """Superposición REAL de intervalos semiabiertos [ini, fin).

    Dos actividades consecutivas (una termina 10:00 y la otra empieza 10:00)
    NO se superponen.
    """
    return ini_a < fin_b and ini_b < fin_a


# --------------------------------------------------------------------------- #
# Entidades
# --------------------------------------------------------------------------- #
@dataclass
class Asignatura:
    clave: str                 # identificador interno (ej. "IA")
    nombre: str
    codigo: str = "PENDIENTE"  # código oficial (ej. "INF3731"); PENDIENTE si no se conoce
    semestre: str = ""
    horas_teoria: float = 0.0  # carga semanal requerida en horas (0 = no especificada)
    horas_laboratorio: float = 0.0
    horas_auxiliatura: float = 0.0

    def carga_requerida_min(self, tipo: str) -> int:
        horas = {"teoria": self.horas_teoria, "laboratorio": self.horas_laboratorio,
                 "auxiliatura": self.horas_auxiliatura}[tipo]
        return int(round(horas * 60))


@dataclass
class Estudiante:
    """Un estudiante real o una COHORTE CURRICULAR (estudiante tipo de una mención y
    semestre). ``tipo``: regular (sus choques son restricciones duras) o irregular
    (estudiante referencial que adelanta/arrastra materias: sus choques son blandos)."""
    id: str
    nombre: str
    semestre: str = ""
    tipo: str = "regular"


@dataclass
class Inscripcion:
    """El estudiante cursa ``asignatura`` en ``paralelo``.

    ``tipos`` limita a qué sesiones asiste (ej. sólo laboratorio); None = todas.
    Paralelo vacío ("") significa paralelo no especificado/pendiente.
    """
    estudiante_id: str
    asignatura: str
    paralelo: str = ""
    tipos: Optional[list[str]] = None

    def cubre(self, s: "Sesion") -> bool:
        return (self.asignatura == s.asignatura and self.paralelo == s.paralelo
                and (not self.tipos or s.tipo in self.tipos))


@dataclass
class Persona:
    id: str
    nombre: str
    rol: str  # "docente" | "auxiliar"


@dataclass
class Ambiente:
    id: str
    nombre: str
    tipo: str  # "aula" | "laboratorio"
    capacidad: int = 0


@dataclass
class Disponibilidad:
    """Intervalo en el que una entidad (docente, auxiliar, estudiante o ambiente)
    está disponible. Si una entidad no tiene filas, se asume disponible siempre."""
    entidad_id: str
    dia: int
    inicio: int
    fin: int


@dataclass
class Sesion:
    id: str
    asignatura: str            # clave de Asignatura
    tipo: str                  # teoria | laboratorio | auxiliatura
    paralelo: str              # paralelo de la asignatura ("" = no especificado)
    dia: int                   # 0..5
    inicio: int                # minutos
    fin: int                   # minutos
    responsable: Optional[str] = None   # id de Persona (docente o auxiliar)
    ambiente: Optional[str] = None      # id de Ambiente
    duracion_requerida: Optional[int] = None  # minutos; None = la duración actual
    fija: bool = True
    obligatoria: bool = True
    estado: str = "vigente"
    reemplaza: Optional[str] = None     # id de la sesión original que reprograma
    origen: str = "oficial"             # oficial | adicional | reprogramacion | simulado
    dias_permitidos: Optional[list[int]] = None  # None = todos los días configurados
    tipo_ambiente: Optional[str] = None  # aula | laboratorio | None (= el del ambiente actual)
    observacion: str = ""

    @property
    def duracion(self) -> int:
        return self.fin - self.inicio

    def mover(self, dia: int, inicio: int, ambiente: Optional[str]) -> "Sesion":
        """Devuelve una COPIA de la sesión en otro día/hora/ambiente conservando duración."""
        return replace(self, dia=dia, inicio=inicio, fin=inicio + self.duracion, ambiente=ambiente)


@dataclass
class Dataset:
    nombre: str
    tipo_datos: str            # "real" | "simulado"
    descripcion: str = ""
    dias: list[int] = field(default_factory=lambda: list(range(6)))  # Lunes..Sábado
    hora_inicio: int = 7 * 60
    hora_fin: int = 21 * 60
    resolucion: int = 30       # minutos entre posibles horas de inicio
    asignaturas: dict[str, Asignatura] = field(default_factory=dict)
    estudiantes: dict[str, Estudiante] = field(default_factory=dict)
    inscripciones: list[Inscripcion] = field(default_factory=list)
    personas: dict[str, Persona] = field(default_factory=dict)
    ambientes: dict[str, Ambiente] = field(default_factory=dict)
    disponibilidad: list[Disponibilidad] = field(default_factory=list)
    sesiones: list[Sesion] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)   # datos faltantes / supuestos
    modo: str = "reprogramacion"   # reprogramacion | planificacion (horario completo sin asignar)
    _cache_inscritos: dict = field(default_factory=dict, repr=False, compare=False)

    # ---- inscripciones -------------------------------------------------------
    def inscritos(self, s: Sesion) -> frozenset[str]:
        """Estudiantes que realmente asisten a la sesión (según sus inscripciones)."""
        clave = (s.asignatura, s.paralelo, s.tipo)
        if clave not in self._cache_inscritos:
            self._cache_inscritos[clave] = frozenset(
                i.estudiante_id for i in self.inscripciones if i.cubre(s))
        return self._cache_inscritos[clave]

    def sesiones_de_estudiante(self, est_id: str, escenario: str = "reprogramado") -> list[Sesion]:
        return [s for s in self.sesiones_activas(escenario) if est_id in self.inscritos(s)]

    # ---- escenarios original / reprogramado ---------------------------------
    def tiene_reprogramaciones(self) -> bool:
        return any(s.reemplaza for s in self.sesiones)

    def sesiones_activas(self, escenario: str = "reprogramado") -> list[Sesion]:
        """Sesiones vigentes en un escenario.

        * ``reprogramado``: se usan las reprogramaciones y se excluyen las sesiones
          marcadas como ``reemplazada``.
        * ``original``: se usa la sesión original y se excluyen las reprogramaciones.

        Así nunca se cuentan simultáneamente el horario original y el reprogramado
        de una misma sesión.
        """
        if escenario == "original":
            reemplazadas_por = {s.reemplaza for s in self.sesiones if s.reemplaza}
            return [s for s in self.sesiones
                    if not s.reemplaza and (s.estado != "reemplazada" or s.id in reemplazadas_por)]
        return [s for s in self.sesiones if s.estado != "reemplazada"]

    def _indice_disponibilidad(self) -> dict[str, list[Disponibilidad]]:
        # índice reconstruido si la lista cambió de tamaño (edición en la interfaz)
        cache = self._cache_inscritos.get("__disp__")
        if cache is None or cache[0] != len(self.disponibilidad):
            idx: dict[str, list[Disponibilidad]] = {}
            for d in self.disponibilidad:
                idx.setdefault(d.entidad_id, []).append(d)
            cache = (len(self.disponibilidad), idx)
            self._cache_inscritos["__disp__"] = cache
        return cache[1]

    def disponibilidad_de(self, entidad_id: str) -> list[Disponibilidad]:
        return self._indice_disponibilidad().get(entidad_id, [])

    def con_disponibilidad(self) -> set[str]:
        """Entidades que declararon disponibilidad (el resto se asume siempre disponible)."""
        return set(self._indice_disponibilidad())

    def disponible(self, entidad_id: str, dia: int, inicio: int, fin: int) -> bool:
        disp = self.disponibilidad_de(entidad_id)
        return not disp or any(d.dia == dia and d.inicio <= inicio and fin <= d.fin for d in disp)

    def nombre_sesion(self, s: Sesion) -> str:
        asig = self.asignaturas.get(s.asignatura)
        nombre = asig.nombre if asig else s.asignatura
        par = f" ({s.paralelo})" if s.paralelo else ""
        return f"{NOMBRE_TIPO.get(s.tipo, s.tipo)} – {nombre}{par}"

    def copia(self) -> "Dataset":
        import copy
        nuevo = copy.deepcopy(self)
        nuevo._cache_inscritos = {}
        return nuevo
