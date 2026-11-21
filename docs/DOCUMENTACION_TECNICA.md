# Documentación técnica (versión 3)

Base para el **Capítulo 3 (Desarrollo)** del informe. Todas las cifras de la sección 6 provienen de
`python scripts/experimentos.py` (ejecución del 20/11/2026, Python 3.13, semillas 1–5; archivos en
`resultados/`). Si cambian los datos, vuelva a ejecutar el script.

## 1. Cambios respecto a la versión 1

| Versión 1 | Versión 2 |
|---|---|
| Grupos idénticos (todos asisten a todo) | Estudiantes individuales con **inscripciones** a materia + paralelo (y opcionalmente solo a laboratorio o auxiliatura) |
| Conflicto “grupo” | Conflicto **estudiante**: solo si las dos actividades comparten estudiantes inscritos |
| Sin capacidad | **Capacidad** del ambiente frente al nº de inscritos (dura, también filtrada en el dominio) |
| Disponibilidad solo de personas | Disponibilidad de **docentes, auxiliares, ambientes (dura) y estudiantes (blanda)** |
| Aux. de IA fija | Reprogramable: el horario establecido no implica que una actividad sea fija |
| Aplicar el resultado directamente | **Propuestas** con revisión: pendiente → aprobada/rechazada → aplicada (con versionado) |
| Un solo usuario | **Roles simulados**: responsable académico, docente, auxiliar, estudiante |
| — | El AG puede optimizar **solo un subconjunto** de actividades (solicitud de un auxiliar) |
| — | **Inmigración aleatoria** cuando el AG se estanca sin solución válida |

## 2. Modelo de datos

```
Asignatura ──< Sesion (paralelo, tipo, día, inicio, fin, responsable, ambiente, fija, estado, reemplaza)
    │
    └──< Inscripcion >── Estudiante          Persona (docente | auxiliar)   Ambiente (aula | lab, capacidad)
                                             Disponibilidad (entidad_id = persona, ambiente o estudiante)
```

- **Inscritos de una sesión:** estudiantes con una inscripción de la misma materia, del mismo paralelo
  y (si se indica) del mismo tipo. *Ejemplo:* E8 está inscrito en BD-A solo para el laboratorio, así que
  no cuenta como asistente de la teórica de BD-A.
- **Versiones:** una reprogramación es otra sesión con `reemplaza = id_original`, y la original queda
  como `reemplazada`. El escenario *vigente* usa la versión más reciente y el *original* usa la
  primera, así que **nunca se cuentan las dos**.

## 3. Detección de conflictos

Los intervalos son semiabiertos `[inicio, fin)`: 08:00–09:30 y 09:30–11:00 **no** chocan. Se recorren
los pares de actividades superpuestas del mismo día. Un par genera un conflicto solo si las dos
actividades comparten algo:

| Comparten… | Categoría |
|---|---|
| estudiantes inscritos | estudiante (con nº de afectados) |
| responsable docente / auxiliar | docente / auxiliar |
| aula / laboratorio | aula / laboratorio |

Las categorías de una sola actividad son:

- **capacidad**;
- **disponibilidad**: del responsable o del ambiente, franja institucional y días permitidos;
- **duración/carga**;
- **disponibilidad de estudiantes**: preferencia.

*Ejemplo:* la teórica de X-A y la de X-B a la misma hora, con distinto docente y aula, **no** chocan,
porque ningún estudiante cursa ambos paralelos (prueba `test_mismo_semestre_distinto_horario`).

Un par se cuenta una sola vez por categoría. Si la otra actividad no es obligatoria, se registra como
*coincidencia no obligatoria*.

## 4. Algoritmo genético

| Elemento | Implementación |
|---|---|
| Cromosoma | Lista de genes; **un gen = una actividad reprogramable** = `(día, inicio, ambiente)`. Las fijas no están en el cromosoma. |
| Dominio del gen | Solo valores válidos: días habilitados, franja, **duración exacta**, disponibilidad del responsable y ambiente del tipo correcto con **capacidad suficiente**. |
| Población inicial | El horario actual más individuos aleatorios dentro del dominio. |
| Fitness | `1 / (1 + 1000·D + B)`. **D** = conflictos duros (inscritos, docente, auxiliar, aula, laboratorio, capacidad, disponibilidad, duración). **B** = penalizaciones blandas (cambios, horas libres por estudiante, franja no preferida, sábado, exceso diario, disponibilidad de estudiantes, coincidencias no obligatorias). |
| Selección | Torneo k = 3, comparando `(D, B)` en orden lexicográfico. |
| Cruce | Uniforme (también de 1 y 2 puntos). Intercambia genes completos. |
| Mutación | Cambia día, hora o ambiente de un gen dentro de su dominio. La *mutación dirigida* (opcional) multiplica por 4 la probabilidad de los genes en conflicto. |
| Elitismo | Los 2 mejores individuos distintos pasan sin cambios. |
| Parada | Generaciones máximas, tiempo límite, estancamiento o condición satisfactoria. Antes de detenerse por estancamiento **sin solución válida**, aplica hasta 3 inmigraciones aleatorias. |
| Semilla | `random.Random(semilla)` propio de cada ejecución: la misma semilla da el mismo resultado. |
| Historial | Por generación: mejor fitness, fitness promedio y peor, D y B del mejor, D promedio, diversidad e inmigraciones. |
| Infactibilidad | `diagnosticar()` detecta actividades sin franjas válidas, conflictos entre fijas y discrepancias de duración. El mensaje nunca presenta como válido un horario con D > 0. |

**Rendimiento.** Los estudiantes que asisten exactamente a las mismas actividades se agrupan en
*patrones*. *Ejemplo:* 20 estudiantes regulares de 8A tienen las mismas horas libres, así que se calculan
una sola vez con peso 20. El resultado es idéntico y el cálculo es varias veces más rápido.

## 5. Propuestas y revisión

```
pendiente ──aprobar (solo si D = 0 al reevaluar)──► aprobada ──aplicar (con confirmación)──► aplicada
    └───────────────rechazar (con motivo)────────────► rechazada
```

Las propuestas pueden venir del AG (responsable o auxiliar) o ser manuales (docente). Todas se evalúan
con la misma función de conflictos.

- **Aprobar** reevalúa con los datos actuales y rechaza las alternativas inviables.
- **Aplicar** crea versiones `<id>-R<n>` y conserva las originales.

## 6. Resultados

### E1. Caso real 2026/2: parcial, sin las clases teóricas oficiales

| Escenario | Conflictos oblig. antes | Después | Actividades movidas | Generaciones | Tiempo |
|---|---|---|---|---|---|
| Original (Lab. IA miércoles 16:30) | 6 | 0 | 3 | 195 | 0,29 s |
| Vigente (Lab. IA lunes 10:00) | 3 | 0 | 2 | 175 | 0,30 s |

Con la semilla 42, la alternativa del escenario vigente mueve:

- la Aux. de Gestión de Proyectos al miércoles 13:30–15:00;
- el Lab. de Auditoría al miércoles 15:00–16:30.

Queda *pendiente de confirmación* la duración de 30 min del Lab. de IA.

> **No** se afirma que se eliminaron los conflictos institucionales. Faltan las clases teóricas, así
> que esas franjas no se han verificado contra el horario oficial.

### E2. Verificación con datos simulados

| Conjunto | Conflictos oblig. iniciales | Válidos (5 semillas) | Observación |
|---|---|---|---|
| Demo pequeño | 12 | 5/5 | 0 conflictos en todas las semillas |
| Demo infactible | 17 | 0/5 | Quedan 4, todos entre actividades fijas. Se diagnostican como no resolubles y la propuesta no puede aprobarse. |

### E3. Demo semestre (simulado): 66 conflictos obligatorios iniciales

De ellos, 44 son de estudiantes y suman **485 choques estudiante-actividad**; además hay 15
preferencias incumplidas.

| Configuración | Válidos | Penalización blanda media (desv.) | Gen. 1ª solución válida (media) | Tiempo medio |
|---|---|---|---|---|
| C1 base (N=80, pc=0,85, pm=0,08, uniforme) | 5/5 | 75,74 (3,16) | 1,0 | 5,79 s |
| C2 con mutación dirigida | 5/5 | 111,04 (2,31) | 1,0 | 2,58 s |
| C3 población 30 | 5/5 | 82,02 (4,02) | 1,2 | 2,03 s |
| C4 cruce un punto, pm = 0,20 | 5/5 | 102,75 (6,69) | 1,0 | 5,06 s |

Con el 10 % de población heurística la primera solución válida aparece en la generación 1–2.

**Interpretación:**

- Todas las configuraciones alcanzaron horarios sin conflictos obligatorios en las 5 semillas.
- La **mutación dirigida empeoró** la calidad, por eso quedó
  desactivada por defecto. Una explicación plausible: mover con más fuerza las actividades en conflicto
  rompe las buenas asignaciones que ya tenían.
- La población de 30 es unas 3 veces más rápida, con una pérdida pequeña de calidad.
- Con 5 semillas, estas diferencias son indicativas, no concluyentes.

## 7. Pruebas (40, todas aprobadas el 20/11/2026)

| Requisito | Pruebas |
|---|---|
| Estudiantes inscritos en dos actividades | `test_conflicto_estudiante_inscrito`, `test_inscripcion_por_tipo`, `test_no_cuenta_dos_veces_y_cuenta_afectados`, `test_distingue_actividad_no_obligatoria` |
| Simultáneas sin recursos compartidos | `test_simultaneas_sin_recursos_compartidos`, `test_mismo_semestre_distinto_horario`, `test_consecutivas_no_se_superponen` |
| Docentes y auxiliares | `test_conflicto_docente_y_auxiliar`, `test_disponibilidad_responsable` |
| Aulas | `test_conflicto_aula_y_laboratorio` |
| Fijas y reprogramables | `test_actividades_fijas_no_cambian`, `test_horario_actual_no_implica_fijo`, `test_optimizar_solo_un_subconjunto` |
| Duraciones y capacidades | `test_capacidad_insuficiente`, `test_dominio_excluye_ambientes_pequenos`, `test_operadores_conservan_sesiones_y_duraciones`, `test_resultado_mantiene_sesiones_y_duraciones`, `test_duracion_por_confirmar` |
| Sin solución factible | `test_informa_infactibilidad`, `test_sesion_sin_franjas_validas`, `test_no_se_aprueba_propuesta_inviable` |
| Reprogramación de labs y auxiliaturas | `test_escenarios_original_y_reprogramado`, `test_aplicar_propuesta_crea_version_sin_doble_conteo`, `test_propuesta_manual_se_evalua` |
| Varias ejecuciones | `test_comparacion_varias_ejecuciones`, `test_misma_semilla_mismo_resultado`, `test_ag_resuelve_demo_varias_semillas` |
| Versión 3 (carrera) | `test_evaluador_rapido_equivale_al_completo` (5 conjuntos), `test_carrera_cohortes_y_oferta`, `test_heuristica_respeta_dominio_y_reduce_choques`, `test_irregulares_son_blandos`, `test_mismo_dia_penaliza_teorias` |
| Otros | `test_solucion_conocida_es_factible`, `test_disponibilidad_estudiante_es_blanda`, `test_ida_y_vuelta_excel`, `test_propuestas_persisten` |

Además se recorrieron con `streamlit.testing.AppTest` todas las páginas de los 4 roles en los 5 conjuntos
de datos, sin excepciones. También el flujo completo: generar → registrar → aprobar → aplicar, la
propuesta del docente, la solicitud del auxiliar y el bloqueo de la propuesta inviable. **No** se probó
en Windows: la ejecución se hizo en Linux.

## 8. Versión 3: planificación de la carrera completa

**Fuentes reales.** `scripts/extraer_planes.py` lee los 5 PDF de `fuentes/` y produce
`data/catalogo/plan_estudios.csv` (305 filas: mención, semestre, sigla, horas T/P/L, prerrequisito).
El plantel de https://www.sisinf.fni.uto.edu.bo/docentes/ (20/11/2026) está en
`data/catalogo/plantel_docente.csv` (docente, materia, sigla, paralelo; **sin correos**).

**Conjunto `carrera_2026_2`** (`modo = planificacion`): 68 asignaturas SIS/INF, 113 paralelos,
369 sesiones (218 T, 104 P, 47 L), 42 docentes.
- Horas del plan → sesiones de 90 min (+ resto de 45); hora académica de 45 min (supuesto).
- T → docente del paralelo; P y L sin responsable (auxiliares no publicados). CH = sede Challapata.
- Correcciones pendientes de confirmar: SIS 1210 CH → INF 1210, SIS 3430 CH → SIS 2430.

**Cohortes** (curriculum-based timetabling, Bonutti et al., 2012):
- 161 regulares (mención × semestre × paralelo; si falta el paralelo, A). Choque = **duro**.
- 45 irregulares (semestres consecutivos). Choque = **preferencia** (peso 0,5).
- `mismo_dia` (peso 4): dos teorías de la misma materia y paralelo el mismo día.

**Cambios en el AG:** `individuo_heuristico` (cada sesión a la franja con menos choques),
`frac_heuristica` (0,1; 0,3 en planificación), `EvaluadorRapido` (máscaras de bits, equivalente
al detector completo según las pruebas) y `config_planificacion()` (pm = 0,005, 500 generaciones,
paciencia 150, 180 s).

### E4. Carrera 2026/2 (369 sesiones, semillas 1–5)

| Estrategia | Sin conflictos oblig. | Penalización blanda media (desv.) | Tiempo medio |
|---|---|---|---|
| A · AG con población aleatoria | 5/5 | 60,92 (5,83) | 47,0 s |
| B · solo heurística | 5/5 | 45,14 (2,91) | — |
| C · heurística + AG | 5/5 | 18,41 (2,51) | 48,7 s |

> El horario generado **no** es oficial: faltan ambientes, auxiliares, disponibilidad docente e
> inscripciones reales. Es un punto de partida para que la carrera lo revise.
