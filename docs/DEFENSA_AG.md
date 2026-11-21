# Explicación del algoritmo genético para la defensa (10 minutos)

## Idea en una frase

En lugar de probar todos los horarios posibles, que son demasiados, el algoritmo **evoluciona** una
población de horarios: los mejores “se reproducen”, se combinan y mutan, y tras varias generaciones
aparecen horarios con menos conflictos.

¿Por qué no probar todo? En el demo semestre hay 22 actividades reprogramables y cada una tiene entre
156 y 264 combinaciones válidas de día, hora y ambiente. En total son unos **10⁵¹ horarios posibles**
(cálculo hecho con el propio sistema). Es imposible revisarlos uno por uno.

---

## Minuto 0–1 · El problema

> “El horario oficial no incluye auxiliaturas ni laboratorios. Por eso un estudiante puede tener dos
> actividades a la misma hora. En el caso real, el miércoles 16:30 coinciden la Aux. de Gestión de
> Proyectos, la Aux. de IO IV y el Lab. de Auditoría.”

*Mostrar:* Calendario semanal → miércoles en rojo.

## Minuto 1–3 · ¿Qué es un individuo?

**Un individuo = un horario completo.** Cada gen es una actividad que se puede mover:

```
Gen 1: Aux. IO IV     → (Miércoles, 16:30, Aula ?)
Gen 2: Lab. Auditoría → (Miércoles, 16:30, Lab ?)
...
```

- Las actividades **fijas** (por ejemplo, las teóricas oficiales) **no son genes**. Por eso es imposible
  que el AG las mueva.
- El gen solo puede tomar valores **válidos**: la duración se mantiene, el docente está disponible y el
  aula tiene capacidad.

  *Ejemplo:* si un auxiliar solo puede por las tardes, sus genes nunca reciben una hora de la mañana.

## Minuto 3–5 · ¿Cómo se mide si un horario es bueno? (fitness)

**Duras (obligatorias):** un mismo estudiante en dos actividades, un docente o aula duplicados, aula
llena, responsable no disponible.
**Blandas (preferencias):** mover pocas actividades, pocas horas libres, evitar el sábado y respetar la
disponibilidad que declararon los estudiantes.

```
fitness = 1 / (1 + 1000 × conflictos_duros + penalización_blanda)
```

*Ejemplo sencillo:*

| Horario | Duros | Blanda | ¿Cuál gana? |
|---|---|---|---|
| A | 1 | 2 | |
| B | 0 | 30 | **B**: sin conflictos obligatorios siempre gana, aunque tenga más preferencias incumplidas |

**Detalle clave:** un conflicto de estudiante solo existe si **comparten estudiantes inscritos**. Dos
paralelos distintos pueden tener clase a la misma hora sin problema.

## Minuto 5–7 · Operadores

1. **Selección por torneo (k = 3):** se eligen 3 horarios al azar y gana el mejor. Como un sorteo entre
   3 candidatos.
   - *¿Por qué no ruleta?* El factor 1000 haría que un solo horario acapare casi toda la probabilidad.
     El torneo solo compara cuál es mejor.
2. **Cruce uniforme:** el hijo toma cada actividad del padre 1 o del padre 2, como una moneda al aire
   por cada gen. Nunca se pierde una actividad ni cambia su duración.
3. **Mutación:** con probabilidad 0,08 por gen, cambia el día, la hora o el aula de una actividad,
   siempre dentro de valores válidos.
4. **Elitismo:** los 2 mejores pasan intactos. El mejor horario nunca empeora.
5. **Parada:** máximo de generaciones, tiempo, estancamiento o condición satisfactoria. Si se estanca
   **sin** solución válida, reemplaza la mitad peor por horarios nuevos (inmigración) hasta 3 veces.
6. **Semilla:** la misma semilla da el mismo resultado, así que el experimento es reproducible.

## Minuto 7–9 · Demostración en vivo

1. Rol *Responsable académico* → *Generación de alternativas* → semilla 42 → **Generar**.
2. Mostrar antes/después, el gráfico de fitness y la tabla de restricciones cumplidas e incumplidas.
3. **Registrar propuesta** → *Revisión de propuestas* → **Aprobar**.
4. Cambiar al conjunto *Demo infactible* → generar → registrar → intentar aprobar. El sistema **se
   niega**: “una alternativa inviable no se presenta como válida”, y explica que el choque está entre
   teóricas fijas.

## Minuto 9–10 · Resultados y límites honestos

- **Demo semestre** (simulado, 86 estudiantes): de 66 conflictos obligatorios a 0 en 5/5 semillas.
- **Comparación de configuraciones:** la *mutación dirigida*, que se esperaba que ayudara, **empeoró**
  los resultados. Por eso quedó desactivada; es un resultado experimental real.
- **Caso real:** de 3 a 0 conflictos entre las actividades registradas. **Faltan las clases teóricas
  oficiales**, así que no se afirma que se eliminaron los conflictos institucionales, y el caso
  corresponde a una sola estudiante.

---

## Preguntas probables del docente

**¿Por qué un algoritmo genético y no reglas fijas?**
Porque el espacio de búsqueda es enorme y las restricciones interactúan entre sí: mover una actividad
puede crear otro conflicto. El AG explora muchas combinaciones a la vez y equilibra las restricciones
duras con las preferencias.

**¿Garantiza la solución óptima?**
No. Es una metaheurística: encuentra buenas soluciones, no necesariamente la óptima. Por eso se ejecuta
con varias semillas y se comparan los resultados.

**¿Qué pasa si no hay solución?**
`diagnosticar()` detecta antes de optimizar las restricciones imposibles, como dos fijas que chocan. El
resultado muestra “NO se encontró un horario válido” y la propuesta no puede aprobarse.

**¿Cómo evitan que se cuente dos veces la versión original y la reprogramada?**
Cada reprogramación apunta a su original (`reemplaza`) y la original queda como `reemplazada`. Solo una
de las dos está vigente en cada escenario.

**¿El selector de rol es seguro?**
No. Es una simulación para la demostración académica, y así se indica en la interfaz.

## Extra · Planificar toda la carrera (versión 3)

- Con los 5 planes de estudio y el plantel docente se armó el horario de las 68 materias SIS/INF:
  369 sesiones, 42 docentes, 206 cohortes.
- Una **cohorte** es el grupo que cursa la misma mención, semestre y paralelo: sus materias no pueden chocar.
- Parte de la población inicial se arma con una **heurística** y el AG mejora desde ahí.
- 5 semillas: las tres estrategias logran 0 conflictos obligatorios; la penalización por preferencias
  baja de 45,14 (solo heurística) y 60,92 (AG aleatorio) a **18,41** (heurística + AG).
- *¿Por qué no basta la heurística?* Es voraz: decide clase por clase y no corrige decisiones previas.

