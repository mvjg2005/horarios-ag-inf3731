"""
Evaluador rápido de la función fitness.

Calcula EXACTAMENTE los mismos valores (conflictos duros y penalización blanda) que
``genetico.evaluar`` —que usa el detector completo de ``conflictos.py``— pero sin
construir los textos de cada conflicto. Se usa dentro del bucle del algoritmo
genético, donde se evalúan decenas de miles de individuos; el resultado final se
vuelve a evaluar con el detector completo para el reporte.

Técnicas:
* Los estudiantes de cada sesión se guardan como una máscara de bits (int de Python):
  "¿comparten estudiantes?" es un AND de dos enteros.
* Las restricciones que no cambian al mover sesiones (duración y carga semanal) se
  cuentan una sola vez al inicio.
* La equivalencia con el detector completo se verifica en las pruebas automáticas.
"""
from __future__ import annotations

from .conflictos import detectar_conflictos


class EvaluadorRapido:
    def __init__(self, problema, cfg):
        from .genetico import decodificar  # evitar import circular
        self.p, self.cfg = problema, cfg
        ds = problema.ds
        orden = problema.fijas + problema.modificables
        self.n, self.nf = len(orden), len(problema.fijas)
        self.ids = [s.id for s in orden]
        irregulares = {e.id for e in ds.estudiantes.values() if e.tipo == "irregular"}
        bit = {e: i for i, e in enumerate(sorted({e for s in orden for e in ds.inscritos(s)}))}
        self.reg, self.irr, self.n_ins, self.ins_disp = [], [], [], []
        con_disp = ds.con_disponibilidad()
        for s in orden:
            ins = ds.inscritos(s)
            self.reg.append(sum(1 << bit[e] for e in ins if e not in irregulares))
            self.irr.append(sum(1 << bit[e] for e in ins if e in irregulares))
            self.n_ins.append(len(ins))
            self.ins_disp.append(sorted(ins & con_disp))
        self.resp = [s.responsable for s in orden]
        self.cat_resp = [("auxiliar" if (ds.personas.get(s.responsable) and ds.personas[s.responsable].rol == "auxiliar")
                          else "docente") if s.responsable else None for s in orden]
        self.oblig = [s.obligatoria for s in orden]
        self.dur = [s.duracion for s in orden]
        self.dias_perm = [set(s.dias_permitidos) if s.dias_permitidos else None for s in orden]
        self.asig = [(s.asignatura, s.paralelo, s.tipo, s.obligatoria) for s in orden]
        self.fijo = [(s.dia, s.inicio, s.ambiente) for s in problema.fijas]
        self.tipo_amb = {a.id: a.tipo for a in ds.ambientes.values()}
        self.cap_amb = {a.id: a.capacidad for a in ds.ambientes.values()}
        self.dias_ok = set(ds.dias)
        self.disp = ds._indice_disponibilidad()
        # Restricciones invariantes (duración de cada sesión y carga semanal): se cuentan una vez.
        self.constantes = [(c.categoria, c.severidad, c.afectados)
                           for c in detectar_conflictos(ds, decodificar(problema, problema.original), problema.escenario)
                           if c.categoria == "duracion"]

    def _disponible(self, ent, d, i, f):
        lista = self.disp.get(ent)
        return not lista or any(x.dia == d and x.inicio <= i and f <= x.fin for x in lista)

    def evaluar(self, crom):
        from .genetico import DETALLE, PESO_DURO, Evaluacion, _huecos_y_carga_arr, _mismo_dia
        cfg, p, ds = self.cfg, self.cfg.pesos, self.p.ds
        asign = self.fijo + list(crom)
        dia = [a[0] for a in asign]
        ini = [a[1] for a in asign]
        fin = [ini[i] + self.dur[i] for i in range(self.n)]
        amb = [a[2] for a in asign]
        duras = cfg.categorias_duras
        det = dict.fromkeys(DETALLE, 0.0)
        duros = 0
        en_conf = set()

        def sumar(cat, sev, af=0):
            nonlocal duros
            if sev in ("obligatorio", "preferencia"):
                if cat in duras:
                    duros += 1
                elif cat == "disp_estudiante":
                    det["disp_estudiante"] += p["disp_estudiante"] * max(1, af)
                elif cat == "estudiante_irregular":
                    det["irregulares"] += p["irregular"] * max(1, af)
                else:
                    det["relajadas"] += p["relajada"]
            elif sev == "no_obligatorio":
                det["no_obligatorio"] += p["no_obligatorio"]

        # ---- pares superpuestos (barrido por día) ------------------------------
        por_dia = {}
        for i in range(self.n):
            por_dia.setdefault(dia[i], []).append(i)
        reg, irr, resp, oblig = self.reg, self.irr, self.resp, self.oblig
        for lista in por_dia.values():
            lista.sort(key=lambda i: ini[i])
            for x, a in enumerate(lista):
                fa = fin[a]
                for b in lista[x + 1:]:
                    if ini[b] >= fa:
                        break
                    hubo = False
                    r = reg[a] & reg[b]
                    if r:
                        sumar("estudiante", "obligatorio" if oblig[a] and oblig[b] else "no_obligatorio")
                        hubo = True
                    else:
                        c = irr[a] & irr[b]
                        if c:
                            sumar("estudiante_irregular", "preferencia", c.bit_count())
                            hubo = True
                    if resp[a] and resp[a] == resp[b]:
                        sumar(self.cat_resp[a], "obligatorio")
                        hubo = True
                    if amb[a] and amb[a] == amb[b]:
                        sumar("laboratorio" if self.tipo_amb.get(amb[a]) == "laboratorio" else "aula", "obligatorio")
                        hubo = True
                    if hubo:
                        en_conf.add(a); en_conf.add(b)  # noqa: E702
        # ---- restricciones de una sola sesión ---------------------------------
        for i in range(self.n):
            d, a0, f0, am = dia[i], ini[i], fin[i], amb[i]
            cap = self.cap_amb.get(am, 0) if am else 0
            if cap and self.n_ins[i] > cap:
                sumar("capacidad", "obligatorio"); en_conf.add(i)  # noqa: E702
            if (d not in self.dias_ok or a0 < ds.hora_inicio or f0 > ds.hora_fin
                    or (self.dias_perm[i] is not None and d not in self.dias_perm[i])
                    or (resp[i] and not self._disponible(resp[i], d, a0, f0))
                    or (am and not self._disponible(am, d, a0, f0))):
                sumar("disponibilidad", "obligatorio"); en_conf.add(i)  # noqa: E702
            if self.ins_disp[i]:
                af = sum(1 for e in self.ins_disp[i] if not self._disponible(e, d, a0, f0))
                if af:
                    sumar("disp_estudiante", "preferencia", af); en_conf.add(i)  # noqa: E702
        for cat, sev, af in self.constantes:
            sumar(cat, sev, af)
        # ---- preferencias que no son conflictos --------------------------------
        for s, (d, i, a) in zip(self.p.modificables, crom):
            if d != s.dia:
                det["cambios"] += p["cambio_dia"]
            elif i != s.inicio:
                det["cambios"] += p["cambio_hora"]
            if a != s.ambiente:
                det["cambios"] += p["cambio_ambiente"]
            if i < cfg.franja_preferida[0] or i + s.duracion > cfg.franja_preferida[1]:
                det["franja"] += p["franja"]
            if d == 5:
                det["sabado"] += p["sabado"]
        huecos, exceso = _huecos_y_carga_arr(self.p.patrones, dia, ini, fin, cfg.max_min_dia)
        det["huecos"] = p["hueco"] * huecos / 30
        det["carga_diaria"] = p["carga_diaria"] * exceso / 30
        det["mismo_dia"] = p["mismo_dia"] * _mismo_dia([(dia[i], *self.asig[i][:3], self.asig[i][3]) for i in range(self.n)])
        blando = sum(det.values())
        return Evaluacion(duros, blando, 1.0 / (1.0 + PESO_DURO * duros + blando), [], det,
                          {self.ids[i] for i in en_conf})
