# -*- coding: cp1252 -*-
r"""
THETA_DIAL_QQQ dashboard -- generador FULL.

Corre 1 vez y despues solo cuando cambie la madre o las tablas del estudio.
El refresco de cada dia lo hace `daily_refresh.py`, que solo anade el punto
nuevo y hace push.

QUE GENERA
----------
data/theta_dial_data.json con:
    meta        - procedencia, fechas, cortes
    latest      - el dia mas reciente con dial (valor, percentil, estado, edad)
    series      - la serie diaria completa (fecha, raw, percentil, estado, QQQ)
    deciles     - monotonia: mediana/WR/PF/CVaR por decil del dial
    estados     - BAJO / MEDIO / ALTO
    cortes      - RAW, >=P33 .. >=P90
    cobertura   - por anio: dias con dial y reparto de estados
    anio_estado - por anio x estado
    elite       - aporte sobre la cohorte que ya pasa el sort
    avisos      - los cuatro caveats que NO pueden faltar en la pagina

DE DONDE SALE CADA COSA
-----------------------
  serie      -> GEN3_THETA_DIAL_SERIE_QQQ.csv      (exacta, la del persistidor)
  percentil  -> recalculado expanding SOLO-PASADO  (identico al persistidor)
  tablas     -> tabla_completa_theta_dial.json     (estudio del 2026-08-19)
  precio QQQ -> QQQ_VIX_DAILY_OHLC.parquet         (contexto del grafico)

NO inventa ni recalcula el dial: lo lee. El unico numero que deriva es el
percentil, con la misma formula que el persistidor.

DOS NOTAS DE OFICIO, las dos aprendidas rompiendo esto mismo el 2026-08-19:

  ENCODING. El fichero es ASCII puro (regla del proyecto para .py). Los textos
  EDITORIALES que acaban VISIBLES en la pagina llevan sus tildes como escapes
  \uXXXX; json.dumps(ensure_ascii=False) las vuelca bien en UTF-8. Escribirlas
  como caracteres reales aqui rompe el parseo.

  ESCRITURA. El JSON se escribe a temporal y se renombra. Path.write_text()
  TRUNCA el fichero antes de codificar: si la codificacion falla, te quedas con
  0 bytes. Asi se perdio este mismo script una vez.
"""
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(__file__).resolve().parent
GEN3 = Path.home() / "Desktop" / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
SERIE = GEN3 / "GEN3_THETA_DIAL_SERIE_QQQ.csv"
REF = GEN3 / "GEN3_THETA_DIAL_REF_QQQ.json"
ESTUDIO = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
           / "QQQ" / "ANALISIS" / "THETA_DIAL_QQQ_STUDY"
           / "tabla_completa_theta_dial.json")
OHLC = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
        / "_GEN3_MULTIASSET" / "QQQ_VIX_DAILY_OHLC.parquet")
OUT = DIR / "data" / "theta_dial_data.json"

MIN_HIST = 250          # el mismo que el persistidor

# --- tildes como escapes: el .py se queda ASCII, la pagina sale bien ---
A, E, I_, O, U = "\u00e1", "\u00e9", "\u00ed", "\u00f3", "\u00fa"
N_ = "\u00f1"
POR, MENOS, RAYA = "\u00d7", "\u2212", "\u2014"


def log(m):
    print("[THDQ-FULL %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def pct_expanding(v):
    """Percentil expanding SOLO-PASADO. Copia exacta de persist_gen3_theta_dial."""
    out = np.full(v.size, np.nan)
    for i in range(MIN_HIST, v.size):
        prev = v[:i]
        prev = prev[np.isfinite(prev)]
        if prev.size:
            out[i] = 100.0 * (prev < v[i]).mean()
    return out


AVISOS = [
    {"t": "Es sobre todo un FRENO, no un acelerador",
     "d": ("Los dos deciles m%ss bajos del dial PIERDEN dinero: PF 0,77 y 1,16 "
           "con un acierto del 52%%. Lo m%ss fiable que hace este indicador es "
           "se%salar los d%sas en los que NO operar." % (A, A, N_, I_))},
    {"t": "La cobertura es muy epis%sdica" % O,
     "d": ("No reparte tres estados cada a%so: a%sos enteros viven en uno solo. "
           "2023 no tuvo ni un d%sa ALTO; 2022 fue 91%% BAJO; 2025 fue 0,3%% BAJO. "
           "Estrechar el dial concentra la cohorte en periodos concretos."
           % (N_, N_, I_))},
    {"t": "Las cifras de la %slite est%sn dominadas por 2020" % (E, A),
     "d": ("La intersecci%sn de %slite alta con dial alto (PF 2.108, acierto "
           "99,8%%) son 1.654 operaciones de las que el 98%% son de 2020, la "
           "recuperaci%sn del COVID. Cero en 2022, 2023, 2024, 2025 y 2026. "
           "Ese PF describe 44 d%sas, no una regla operable." % (O, E, O, I_))},
    {"t": "Roza el confound del VIX",
     "d": ("r(dial, VIX) = %s0,27, por encima del umbral 0,20 del protocolo. Es "
           "eliminatorio para un SORT; se admite como GATE declarado, que es su "
           "uso. Apretarlo se parece EN PARTE a elegir d%sas de VIX bajo %s su "
           "partial controlando VIX es +0,385, mayor que su r crudo, as%s que "
           "hay se%sal propia, pero conviene saberlo."
           % (MENOS, I_, RAYA, I_, N_))},
]


def build():
    meta_ref = json.loads(REF.read_text(encoding="utf-8"))
    cortes = meta_ref["cortes_estado"]
    bajo, alto = float(cortes["BAJO_hasta"]), float(cortes["ALTO_desde"])
    log("cortes de estado: BAJO < %.2f <= MEDIO < %.2f <= ALTO" % (bajo, alto))

    s = pd.read_csv(SERIE, encoding="utf-8-sig")
    s["dia"] = s["dia"].astype(str).str[:10]
    s = s.sort_values("dia").reset_index(drop=True)
    raw = pd.to_numeric(s["raw"], errors="coerce").to_numpy(np.float64)
    pctl = pct_expanding(raw)
    est = np.where(np.isnan(pctl), None,
                   np.where(pctl < bajo, "BAJO",
                            np.where(pctl < alto, "MEDIO", "ALTO")))
    log("serie: %d dias (%s -> %s), dial valido en %d"
        % (len(s), s["dia"].iloc[0], s["dia"].iloc[-1], int(np.isfinite(pctl).sum())))

    qqq = {}
    if OHLC.exists():
        o = pd.read_parquet(OHLC)
        col_d = "date" if "date" in o.columns else o.columns[0]
        col_c = next((c for c in o.columns if c.lower().endswith("close")
                      and "vix" not in c.lower()), None)
        if col_c:
            o[col_d] = pd.to_datetime(o[col_d]).dt.strftime("%Y-%m-%d")
            qqq = dict(zip(o[col_d], pd.to_numeric(o[col_c], errors="coerce")))
            log("OHLC de QQQ: %d dias para el contexto" % len(qqq))

    series = []
    for i in range(len(s)):
        d = s["dia"].iloc[i]
        q = qqq.get(d)
        series.append({
            "d": d,
            "raw": (round(float(raw[i]), 12) if np.isfinite(raw[i]) else None),
            "p": (round(float(pctl[i]), 2) if np.isfinite(pctl[i]) else None),
            "e": (est[i] if est[i] is not None else None),
            "q": (round(float(q), 2) if q is not None and np.isfinite(q) else None),
        })

    ult = next((x for x in reversed(series) if x["p"] is not None), None)
    hoy = datetime.now().strftime("%Y-%m-%d")
    edad = (pd.Timestamp(hoy) - pd.Timestamp(ult["d"])).days if ult else None
    log("ultimo dia con dial: %s (percentil %.1f, %s) -- %d dias de antiguedad"
        % (ult["d"], ult["p"], ult["e"], edad))

    est_full = json.loads(ESTUDIO.read_text(encoding="utf-8")) if ESTUDIO.exists() else {}

    data = {
        "meta": {
            "titulo": "THETA_DIAL - QQQ Batman LT",
            "generado": datetime.now().isoformat(timespec="seconds"),
            "formula": ("media de medias por celda (DTE1 %s DTE2) de "
                        "theta_k2/spot, expresada como percentil expandido "
                        "SOLO-PASADO" % POR),
            "bandas_dte1": meta_ref["estratificacion"]["bandas_dte1"],
            "bandas_dte2": meta_ref["estratificacion"]["bandas_dte2"],
            "min_hist_dias": MIN_HIST,
            "corte_bajo": round(bajo, 2), "corte_alto": round(alto, 2),
            "universo": est_full.get("raw", {}),
            "n_dias_serie": len(series),
            "n_dias_con_dial": int(np.isfinite(pctl).sum()),
            "rango": [series[0]["d"], series[-1]["d"]],
            "fuente": "MADRE_GEN3_V42_QQQ_LT (brazo RAND_Q*) + LIVE Batman QQQ V40",
            "nativo": ("Se calcula con theta_k2/spot del propio QQQ. "
                       "Ning%sn dato de SPX interviene." % U),
        },
        # `latest` lleva DOS juegos de claves a proposito:
        #   d/p/e/q/raw  -> las que consume esta pagina
        #   date/pct/zone-> el CONTRATO de zoneFeed del portal MANUMB_HOME
        #                   (static/index.html, loadZoneBadges: lee latest.zone,
        #                   latest.date y latest.pct, y si `zone` no esta en su
        #                   ZONE_COLORS no pinta nada, en silencio).
        # Duplicar tres escalares es mas barato que mantener dos formatos.
        "latest": (dict(ult, edad_dias=edad,
                        date=ult["d"], pct=ult["p"], zone=ult["e"]) if ult else None),
        "series": series,
        "deciles": est_full.get("deciles", []),
        "estados": est_full.get("estados", []),
        "cortes": est_full.get("cortes", []),
        "cobertura": est_full.get("cobertura_anual", []),
        "anio_estado": est_full.get("anio_x_estado", []),
        "elite": est_full.get("elite", []),
        "monotonia": est_full.get("monotonia", {}),
        "contexto": est_full.get("contexto", {}),
        "avisos": AVISOS,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp%d" % os.getpid())
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    os.replace(tmp, OUT)
    log("escrito %s (%.1f KB)" % (OUT.name, OUT.stat().st_size / 1024))
    return data


if __name__ == "__main__":
    d = build()
    print("\nOK. latest = %s" % json.dumps(d["latest"], ensure_ascii=False))
