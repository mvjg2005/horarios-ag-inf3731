# Prototipo de apoyo a la planificación de horarios académicos mediante algoritmos genéticos

**INF3731 – Inteligencia Artificial** · Carrera de Ingeniería de Sistemas e Informática · FNI – Universidad Técnica de Oruro

El prototipo genera, compara y evalúa alternativas de asignación de clases teóricas, laboratorios y
auxiliaturas. Considera las inscripciones individuales de los estudiantes y la disponibilidad de
docentes, auxiliares, ambientes y estudiantes. Usa un **algoritmo genético implementado desde cero en
Python**. **No sustituye las decisiones de las autoridades universitarias.**

---

## 1. Instalación y ejecución en Windows

1. Instale **Python 3.10 o superior** desde python.org y marque *Add Python to PATH*.
2. Descomprima el ZIP, abra `cmd` en la carpeta `horarios_ag` y ejecute:

```
python -m pip install -r requirements.txt
```

3. Inicie la aplicación con doble clic en **`iniciar.bat`** o con:

```
python -m streamlit run app.py
```

Se abre el navegador en `http://localhost:8501`.

| Acción | Comando |
|---|---|
| Pruebas automáticas | `python -m pytest -v` (o doble clic en `ejecutar_pruebas.bat`) |
| Regenerar los datos de ejemplo | `python scripts/generar_datos.py` |
| Repetir los experimentos E1–E3 | `python scripts/experimentos.py` (~3 min) |
| Repetir el experimento E4 (carrera completa) | `python scripts/experimento_carrera.py` (~8 min) |
| Reextraer el plan de estudios de los PDF | `python scripts/extraer_planes.py` |
| Regenerar el conjunto de la carrera | `python scripts/generar_carrera.py` |

> Si `python` no se reconoce, pruebe con `py` en lugar de `python`.

## 2. Roles (simulados)

El selector de rol de la barra lateral es una **simulación para la demostración académica**. No es un
sistema de autenticación ni de control de acceso.

| Rol | Puede |
|---|---|
| Responsable académico | Gestionar materias, paralelos, estudiantes, inscripciones, docentes, auxiliares y ambientes; importar horarios; configurar restricciones; ejecutar el AG; revisar, aprobar, rechazar y aplicar propuestas. |
| Docente | Consultar sus actividades, registrar su disponibilidad, proponer cambios y consultar las alternativas que lo involucran. |
| Auxiliar | Consultar sus auxiliaturas, registrar su disponibilidad, revisar conflictos con estudiantes inscritos y solicitar alternativas al AG. |
| Estudiante | Consultar su horario según sus inscripciones y registrar su disponibilidad. No modifica horarios. |

## 3. Estructura

```
app.py                Interfaz Streamlit por roles
core/modelo.py        Entidades: Asignatura, Estudiante, Inscripcion, Persona, Ambiente,
                      Disponibilidad, Sesion, Dataset (escenarios original/reprogramado)
core/datos.py         CSV/Excel: carga, guardado, importación, exportación y validación
core/conflictos.py    Detección de conflictos (10 categorías) y estado de restricciones
core/genetico.py      Algoritmo genético (cromosoma, población, fitness, torneo, cruce,
                      mutación, elitismo, parada, semilla, historial, diagnóstico)
core/propuestas.py    Propuestas: pendiente → aprobada/rechazada → aplicada (versionado)
core/evaluador_rapido.py  Evaluación con máscaras de bits (mismos resultados que el detector)
core/evaluacion.py    Indicadores y comparación de varias ejecuciones
ui/                   Estilos institucionales, calendario semanal y cuadrícula de disponibilidad
data/                 Un directorio por conjunto de datos (reales y simulados separados)
scripts/              Generación de datos y experimentos
tests/                40 pruebas automáticas (pytest)
fuentes/              5 PDF de planes de estudio y el plantel docente (sin correos)
resultados/           Salidas reales de scripts/experimentos.py
docs/                 Documentación técnica y explicación para la defensa
plantillas/           Plantillas CSV para transcribir el horario oficial e inscripciones
```

## 4. Datos

| Carpeta | Tipo | Contenido |
|---|---|---|
| `caso_real_2026_2` | **REAL** | Auxiliaturas y laboratorios informados, y la reprogramación del Lab. de IA. **Las clases teóricas del horario oficial siguen pendientes:** no se recibió la captura. |
| `demo_pequeno` | SIMULADO | 7 actividades y 8 estudiantes (uno irregular y uno que solo recursa un laboratorio). Tiene una solución factible conocida. |
| `demo_infactible` | SIMULADO | Dos teóricas fijas comparten estudiantes a la misma hora. Sirve para comprobar que el sistema informa que no hay solución. |
| `demo_semestre` | SIMULADO | 51 actividades, 86 estudiantes, 380 inscripciones individuales, capacidades y disponibilidades. |
| `carrera_2026_2` | **REAL con supuestos** · modo planificación | 68 asignaturas SIS/INF de los 5 planes de estudio, 113 paralelos (incluye CH = sede Challapata), 369 sesiones, 42 docentes del plantel publicado, 161 cohortes regulares y 45 irregulares. Sin ambientes, auxiliares ni disponibilidades (no publicados). |

**Cargar el horario oficial (cuando esté disponible):** en *Gestión académica*:

1. Registre la materia (pestaña *Materias*).
2. Registre cada clase teórica en *Actividades* (`tipo = teoria`, `fija = si`, `origen = oficial`, con el
   paralelo si es legible).
3. Agregue la inscripción de la estudiante (pestaña *Inscripciones*).
4. Pulse **Validar y aplicar** y, si desea conservarlo, **Guardar conjunto** (requiere confirmación).

También puede usar las plantillas de `plantillas/`. Los datos ilegibles se dejan vacíos y se anotan en
*Configuración → Datos pendientes*.

## 5. Supuestos y limitaciones

- Faltan las clases teóricas, los paralelos, los docentes, los auxiliares, los ambientes y las
  disponibilidades del caso real. No se inventan.
- La franja 07:00–21:00 de lunes a sábado es un supuesto configurable.
- El horario actual de auxiliaturas y laboratorios **no** las vuelve fijas: se consideran
  reprogramables.
- La duración de 30 min del Lab. de IA reprogramado figura como *pendiente de confirmación*.
- El caso real corresponde a una sola estudiante y **no** se generaliza a la carrera.
- En `carrera_2026_2`: hora académica de 45 min (supuesto); un semestre sin paralelo propio cursa el paralelo A; las materias de otros departamentos (FIS, MAT, QMC…) no se programan; SIS 1210 CH → INF 1210 y SIS 3430 CH → SIS 2430 son correcciones pendientes de confirmar.
- Fuentes: planes de estudio oficiales (PDF en `fuentes/`) y https://www.sisinf.fni.uto.edu.bo/docentes/ (consultado el 20/11/2026).
- Las propuestas se guardan en `data/<conjunto>/propuestas.json`. El horario solo se guarda en disco si
  el responsable lo confirma.
