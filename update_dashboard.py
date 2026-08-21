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
DIAS_LIVE = DIR / "data" / "dias_live.csv"   # los dias que aporta el LIVE
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


# Reparto por anio de la cohorte de elite y de su interseccion con el dial alto.
# Medido sobre MADRE_GEN3_V42_QQQ_LT.csv el 2026-08-20 (brazo RAND_Q*, cortes
# V7>=P80 y TX_UP_V7_AREA>=P80). Constantes a proposito: no cambian salvo que
# cambie la madre, y recalcularlas exigiria leer 1,1 GB en cada refresco diario.
CONCENTRACION = {
    "por_anio": [
        {"anio": "2019", "cuota_elite": 0.9, "cuota_dial": 0.0},
        {"anio": "2020", "cuota_elite": 46.3, "cuota_dial": 83.2},
        {"anio": "2021", "cuota_elite": 14.7, "cuota_dial": 15.5},
        {"anio": "2022", "cuota_elite": 13.0, "cuota_dial": 0.0},
        {"anio": "2023", "cuota_elite": 14.4, "cuota_dial": 0.0},
        {"anio": "2024", "cuota_elite": 0.4, "cuota_dial": 0.3},
        {"anio": "2025", "cuota_elite": 8.0, "cuota_dial": 0.8},
        {"anio": "2026", "cuota_elite": 2.3, "cuota_dial": 0.2},
    ],
    "nota": ("De qu%s a%sos est%s hecha la cohorte que produce esos profit "
             "factors. La %slite ya carga hacia 2020 (46,3%%), pero al cruzarla "
             "con el dial alto la concentraci%sn se dispara: <b>83,2%% es 2020 "
             "y 15,5%% es 2021</b> &mdash; entre los dos, el 98,7%%. En "
             "<b>2022 y 2023 no hay ni una sola operaci%sn</b>. Y la %slite, "
             "por su cuenta, <b>pierde dinero</b> en 2021 (mediana %s1,48) y "
             "2022 (%s1,15). Por eso el aviso de arriba dice que ese PF "
             "describe un episodio y no una regla anual."
             % (E, N_, A, E, O, O, E, MENOS, MENOS)),
}


def build():
    meta_ref = json.loads(REF.read_text(encoding="utf-8"))
    cortes = meta_ref["cortes_estado"]
    bajo, alto = float(cortes["BAJO_hasta"]), float(cortes["ALTO_desde"])
    log("cortes de estado: BAJO < %.2f <= MEDIO < %.2f <= ALTO" % (bajo, alto))

    # La serie efectiva son DOS fuentes, y el orden de precedencia importa:
    #   1. GEN3_THETA_DIAL_SERIE_QQQ.csv -- el historico del persistidor. Se
    #      abre SOLO LECTURA: es la referencia que el LIVE usa para rankear, y
    #      un dashboard no tiene por que escribir ahi (arreglado 2026-08-21).
    #   2. data/dias_live.csv -- los dias que daily_refresh ha ido sacando de
    #      las entregas, que es lo unico que puede rellenar el tramo posterior
    #      al corte del gate forward.
    # Si un dia esta en las dos, MANDA el persistidor: su valor esta calculado
    # sobre los candidatos que sobrevivieron al filtro forward, y el del LIVE es
    # una aproximacion del dia en curso. Asi, cuando se amplia la madre, los
    # dias aproximados se sustituyen solos por los buenos.
    s = pd.read_csv(SERIE, encoding="utf-8-sig")[["dia", "raw"]]
    s["dia"] = s["dia"].astype(str).str[:10]
    n_prod = len(s)
    dias_oos = set()
    if DIAS_LIVE.exists():
        lv = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        lv["dia"] = lv["dia"].astype(str).str[:10]
        lv = lv[~lv["dia"].isin(set(s["dia"]))][["dia", "raw"]]
        if len(lv):
            s = pd.concat([s, lv], ignore_index=True)
            dias_oos = set(lv["dia"])
        log("serie: %d dias del persistidor + %d del LIVE" % (n_prod, len(lv)))
    else:
        log("serie: %d dias del persistidor (aun no hay dias del LIVE)" % n_prod)
    s = s.drop_duplicates(subset=["dia"], keep="first")
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
            # "o" = origen. IS = backtest con gate forward (donde se calibro
            # TODO lo que dice esta pagina). OOS = leido de la entrega del LIVE,
            # dia a dia, sin que nadie lo hubiera visto antes.
            "o": ("OOS" if d in dias_oos else "IS"),
        })

    ult = next((x for x in reversed(series) if x["p"] is not None), None)
    hoy = datetime.now().strftime("%Y-%m-%d")
    edad = (pd.Timestamp(hoy) - pd.Timestamp(ult["d"])).days if ult else None
    log("ultimo dia con dial: %s (percentil %.1f, %s) -- %d dias de antiguedad"
        % (ult["d"], ult["p"], ult["e"], edad))

    est_full = json.loads(ESTUDIO.read_text(encoding="utf-8")) if ESTUDIO.exists() else {}

    # --- la particion IS / OOS ---
    frontera = max((x["d"] for x in series if x["o"] == "IS" and x["p"] is not None),
                   default=None)
    n_oos = sum(1 for x in series if x["o"] == "OOS" and x["p"] is not None)
    hueco_dias = 0
    evaluable = None
    if dias_oos and frontera:
        hueco_dias = (pd.Timestamp(min(dias_oos)) - pd.Timestamp(frontera)).days
        # ~250 dias de calendario para que cierre el W50 del DTE1 mas largo del
        # universo (500). Es una cota, no una promesa: los DTE cortos cierran antes.
        evaluable = (pd.Timestamp(min(dias_oos)) +
                     pd.Timedelta(days=250)).strftime("%Y-%m-%d")
    log("particion: IS %d dias (hasta %s) | hueco %d dias | OOS %d dias"
        % (sum(1 for x in series if x["o"] == "IS" and x["p"] is not None),
           frontera, hueco_dias, n_oos))

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
        # La particion IS / OOS. El hueco entre las dos (el tramo que no tiene ni
        # backtest ni entrega) no es un defecto que tapar: es la frontera mas
        # limpia que se puede pedir, sin solape ni zona gris.
        #
        # OJO CON LO QUE SIGNIFICA EL CONTADOR: los dias OOS acumulan LECTURAS
        # del dial, no VEREDICTOS. Para saber si el dial acerto en un dia hace
        # falta su PnL a W50, y ese no existe hasta ~250 dias despues. Por eso
        # se publica la fecha a partir de la cual el tramo empieza a ser
        # evaluable, en vez de una barra de progreso que insinuaria que ya dice
        # algo.
        "particion": {
            "frontera": frontera,
            "n_is": int(sum(1 for x in series if x["o"] == "IS" and x["p"] is not None)),
            "n_oos": int(n_oos),
            "primer_oos": (min(dias_oos) if dias_oos else None),
            "hueco": ([frontera, min(dias_oos)] if dias_oos else None),
            "hueco_dias": (int(hueco_dias) if dias_oos else 0),
            "evaluable_desde": evaluable,
            "nota": ("El tramo OOS acumula LECTURAS del dial, no todav%sa "
                     "veredictos: para saber si un d%sa acert%s hace falta su PnL "
                     "a W50, que no existe hasta ~250 d%sas despu%ss. Lo que se "
                     "ve aqu%s es el registro en vivo; la evaluaci%sn llega "
                     "sola." % (I_, I_, O, I_, E, I_, O)),
        },
        "latest": (dict(ult, edad_dias=edad,
                        date=ult["d"], pct=ult["p"], zone=ult["e"]) if ult else None),
        "series": series,
        "deciles": est_full.get("deciles", []),
        "estados": est_full.get("estados", []),
        "cortes": est_full.get("cortes", []),
        "cobertura": est_full.get("cobertura_anual", []),
        "anio_estado": est_full.get("anio_x_estado", []),
        "elite": est_full.get("elite", []),
        # De que anos esta hecha la cohorte de elite. Sale de la
        # @AuditoriaLogica del 2026-08-20: el aviso 3 decia en prosa que el PF
        # de 2.108 es 98% de 2020, pero no habia forma de VERLO. Las cifras se
        # midieron sobre la madre en
        # Batman/QQQ/ANALISIS/RESEARCH_FIGS/_datos_figs.json y se copian aqui
        # como constantes: recalcularlas en cada refresco obligaria a leer una
        # madre de 1,1 GB todos los dias para un grafico que no cambia.
        "concentracion": CONCENTRACION,
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
