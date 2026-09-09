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
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from procedencia import procedencia, BANDAS_DTE1, BANDAS_DTE2   # trazabilidad + constantes de formula

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_GEN3_MULTIASSET"))
import theta_dial_vara as tdv  # noqa: E402 -- unico percentilador de runtime (R.3)

DIR = Path(__file__).resolve().parent
GEN3 = Path.home() / "Desktop" / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
SERIE = GEN3 / "GEN3_THETA_DIAL_SERIE_QQQ.csv"          # historico crudo del persistidor (RAW), solo lectura
SELLADA = tdv.SERIE_SELLADA_CSV                          # dia,raw,pctl,estado ya sellados (<=frontera)
MANIFEST = tdv.MANIFEST_JSON                             # cortes + hash de vara vigentes
ESTUDIO = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
           / "QQQ" / "ANALISIS" / "THETA_DIAL_QQQ_STUDY"
           / "tabla_completa_theta_dial.json")
OHLC = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
        / "_GEN3_MULTIASSET" / "QQQ_VIX_DAILY_OHLC.parquet")
DIAS_LIVE = DIR / "data" / "dias_live.csv"      # dias del LIVE, posteriores a la vara sellada -> OOS
OUT = DIR / "data" / "theta_dial_data.json"

MIN_HIST = 250          # el mismo que el persistidor

# --- tildes como escapes: el .py se queda ASCII, la pagina sale bien ---
A, E, I_, O, U = "\u00e1", "\u00e9", "\u00ed", "\u00f3", "\u00fa"
N_ = "\u00f1"
POR, MENOS, RAYA = "\u00d7", "\u2212", "\u2014"


def log(m):
    print("[THDQ-FULL %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def cargar_vara_o_abortar():
    info = tdv.cargar_vara_sellada(estricto=False)
    if info is None:
        raise SystemExit(
            "[THDQ-FULL] *** No existe la vara sellada (%s / %s). Correr primero "
            "01_sellar_vara_theta_dial_qqq.py --apply en "
            "Batman/QQQ/ANALISIS/SECUENCIA_THETA_DIAL_QQQ/. ***"
            % (tdv.VARA_NPY.name, tdv.MANIFEST_JSON.name))
    if not info["hash_ok"]:
        log("*** AVISO (R.3): sha256 de %s no coincide con el declarado en %s. "
            "El dashboard publica de todas formas (no es el trader), pero esto "
            "es una FALLA -- alguien reescribio la vara sin re-sellar. ***"
            % (tdv.VARA_NPY.name, tdv.MANIFEST_JSON.name))
    return info


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
    # UNA vara, sellada, consumida por LIVE y dashboard por igual (2026-09-09,
    # plan de subsanacion THETA_DIAL_QQQ). Antes cada uno recalculaba su propio
    # percentil expanding sobre una poblacion distinta -- persistidor (1799
    # dias), LIVE (serie congelada de abril), dashboard (compuesta hasta 1900) --
    # y publicaban ESTADO distinto para el mismo dia (medido: 5 de 101 dias
    # OOS). Ahora los dos leen el MISMO artefacto.
    vara_info = cargar_vara_o_abortar()
    bajo, alto = vara_info["bajo"], vara_info["alto"]
    log("cortes de estado (manifiesto sellado): BAJO < %.4f <= MEDIO < %.4f <= ALTO"
        % (bajo, alto))

    # 1) El tramo SELLADO (persistidor + backtester ADHOC <= frontera, mismo
    #    motor): se LEE tal cual, no se recalcula. Es exactamente lo que
    #    01_sellar_vara_theta_dial_qqq.py escribio -- misma fuente que la vara
    #    congelada, para que dashboard y LIVE jamas puedan discrepar en este
    #    tramo. SOLO LECTURA.
    sellada = pd.read_csv(SELLADA, encoding="utf-8-sig")
    sellada["dia"] = sellada["dia"].astype(str).str[:10]
    n_sellados = len(sellada)

    # 2) El tramo OOS (dias_live.csv, posteriores a la vara): se MIDE contra la
    #    vara CONGELADA con el mismo codigo que usa el LIVE -- no se matriculan
    #    en la vara (eso es cadencia, no cada refresco diario).
    dias_oos, dias_recup = set(), set()
    filas_post = []
    if DIAS_LIVE.exists():
        lv = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        lv["dia"] = lv["dia"].astype(str).str[:10]
        origen = lv["origen"].fillna("LIVE") if "origen" in lv.columns else pd.Series("LIVE", index=lv.index)
        # Un dia ya sellado NO se sobreescribe con el del LIVE: la vara manda.
        lv = lv[~lv["dia"].isin(set(sellada["dia"]))]
        origen = origen.loc[lv.index]
        for (_, r), o in zip(lv.iterrows(), origen):
            raw_v = pd.to_numeric(r.get("raw"), errors="coerce")
            raw_v = float(raw_v) if pd.notna(raw_v) else float("nan")
            pctl_v = tdv.pctl_contra_vara(raw_v, vara_info["vara"])
            filas_post.append({
                "dia": r["dia"], "raw": raw_v, "pctl": pctl_v,
                "estado": tdv.estado_desde_pctl(pctl_v, bajo, alto),
            })
            # Se separan a proposito: un dia RECUPERADO se recalcula con el
            # backtester ADHOC (10:30 ET); el LIVE entra a las 12:30 ET con
            # otra poblacion de candidatos. Medido: 4,17 puntos de percentil de
            # diferencia entre las dos vias para el mismo dia. Pintarlo como si
            # fuera del LIVE seria vender por equivalente algo que no lo es.
            (dias_recup if o == "RECUPERADO" else dias_oos).add(r["dia"])
        log("serie: %d dias sellados + %d del LIVE (medidos contra la vara congelada)"
            % (n_sellados, len(filas_post)))
    else:
        log("serie: %d dias sellados (aun no hay dias del LIVE)" % n_sellados)

    post = (pd.DataFrame(filas_post, columns=["dia", "raw", "pctl", "estado"])
            if filas_post else pd.DataFrame(columns=["dia", "raw", "pctl", "estado"]))
    s = pd.concat([sellada[["dia", "raw", "pctl", "estado"]], post], ignore_index=True)
    s = s.drop_duplicates(subset=["dia"], keep="first").sort_values("dia").reset_index(drop=True)

    raw = pd.to_numeric(s["raw"], errors="coerce").to_numpy(np.float64)
    pctl = pd.to_numeric(s["pctl"], errors="coerce").to_numpy(np.float64)
    est = np.where(s["estado"].isna() | (s["estado"] == ""), None, s["estado"].to_numpy(dtype=object))
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
            "o": ("RECUP" if d in dias_recup else
                  ("OOS" if d in dias_oos else "IS")),
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
    n_bt = sum(1 for x in series
               if x["o"] == "IS" and x["p"] is not None)
    # OOS = los que vienen del LIVE + los recuperados: los dos son fuera de
    # muestra (ninguno vio el futuro). Se cuentan juntos para la frontera y
    # aparte para pintarlos distinto.
    n_oos = sum(1 for x in series if x["o"] in ("OOS", "RECUP") and x["p"] is not None)
    hueco_dias = 0
    evaluable = None
    _post = dias_oos | dias_recup
    if _post and frontera:
        hueco_dias = (pd.Timestamp(min(_post)) - pd.Timestamp(frontera)).days
        # ~250 dias de calendario para que cierre el W50 del DTE1 mas largo del
        # universo (500). Es una cota, no una promesa: los DTE cortos cierran antes.
        evaluable = (pd.Timestamp(min(_post)) +
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
            "bandas_dte1": BANDAS_DTE1,
            "bandas_dte2": BANDAS_DTE2,
            "min_hist_dias": MIN_HIST,
            "corte_bajo": round(bajo, 2), "corte_alto": round(alto, 2),
            "vara_sha256": vara_info["manifest"]["vara"]["sha256"],
            "vara_n_dias": vara_info["manifest"]["vara"]["n"],
            "cortes_historial": vara_info["manifest"].get("cortes_historial", []),
            "universo": est_full.get("raw", {}),
            "n_dias_serie": len(series),
            "n_dias_con_dial": int(np.isfinite(pctl).sum()),
            "rango": [series[0]["d"], series[-1]["d"]],
            "fuente": "MADRE_GEN3_V42_QQQ_LT (brazo ALL, sin filtrar FWD_SLOT) + LIVE Batman QQQ V40",
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
        # De donde sale cada cifra de esta pagina, con rutas absolutas,
        # para que se pueda peritar sin entrar en el repo. Ver procedencia.py.
        "procedencia": procedencia(frontera, n_bt, n_oos),
        "particion": {
            "frontera": frontera,
            "n_is": int(sum(1 for x in series if x["o"] == "IS" and x["p"] is not None)),
            "n_oos": int(n_oos),
            "n_recup": int(sum(1 for x in series
                               if x["o"] == "RECUP" and x["p"] is not None)),
            "primer_oos": (min(_post) if _post else None),
            # Un fin de semana NO es un hueco. Solo se declara (y se pinta la
            # banda gris) si hay mas de 5 dias naturales sin dato, que es lo
            # unico que no explica el calendario. Antes eran 131 dias y tenia
            # todo el sentido; desde la reconstruccion homogenea del 2026-08-25
            # lo normal es que no haya ninguno.
            "hueco": ([frontera, min(_post)] if (_post and hueco_dias > 5) else None),
            "hueco_dias": (int(hueco_dias) if (_post and hueco_dias > 5) else 0),
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
