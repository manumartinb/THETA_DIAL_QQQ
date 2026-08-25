# -*- coding: cp1252 -*-
r"""
Cierra el hueco de THETA_DIAL con UN SOLO metodo, para que la serie sea homogenea.

LA DECISION (usuario, 2026-08-25)
---------------------------------
"Dejalo todo IS pero homogeneo, dejate de dias recuperables y tal."

Y es la decision correcta. Lo que habia era una serie con TRES construcciones
distintas conviviendo:

    1.549 dias del persistidor  (backtester, 10:30 ET)
      131 dias de hueco         (nada)
        3 dias del LIVE         (12:30 ET, otra poblacion de candidatos)
        1 dia recuperado        (backtester, 10:30 ET)

Tres metodos en un mismo grafico, separados 4,17 puntos de percentil entre si
(medido). Un percentil expanding calculado sobre esa mezcla no significa nada
limpio: cada dia se rankea contra un pasado que no se construyo como el.

LO QUE HACE ESTE SCRIPT
-----------------------
Calcula con el backtester ADHOC **todos** los dias desde la frontera del
persistidor (2026-04-10) hasta donde llegan las cadenas. Resultado: una serie
continua 2019-01-02 -> hoy-ish, **toda con el mismo motor y la misma hora**.

Y ojo al detalle que lo hace barato: los 1.549 dias historicos YA son de ese
mismo motor a esa misma hora (la madre entra a las 16:30 CEST = 10:30 ET). No
hay que rehacerlos. Solo hay que continuar la serie.

A partir de ahi, OOS empieza de cero con el LIVE, y esta vez la frontera es
NITIDA: todo lo de antes es backtest, todo lo de despues es vivo.

RESUMIBLE. Cada dia deja su `T0_DIAL_QQQ_<fecha>.parquet`; si ya existe, no se
recalcula. Se puede parar con Ctrl+C y relanzar sin perder nada.

NO TOCA NADA DE PRODUCCION: ni la serie del persistidor (solo lectura) ni el
ADHOC original (copia temporal). Escribe solo `data/dias_backtest.csv`.

USO
---
    python reconstruir_homogeneo.py --dry-run
    python reconstruir_homogeneo.py
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
from recuperar_dias import (correr_adhoc, dial_desde_parquet, CADENAS,   # noqa: E402
                            SERIE_PROD, MIN_CELDAS)

DIAS_BT = DIR / "data" / "dias_backtest.csv"


def log(m):
    print("[HOMOG %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def guardar(filas):
    d = pd.DataFrame(filas)
    if DIAS_BT.exists():
        prev = pd.read_csv(DIAS_BT, encoding="utf-8-sig")
        prev["dia"] = prev["dia"].astype(str).str[:10]
        d = pd.concat([prev, d], ignore_index=True)
    d = d.drop_duplicates(subset=["dia"], keep="last").sort_values("dia")
    DIAS_BT.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIAS_BT.with_suffix(".csv.tmp")     # temporal + rename, nunca en sitio
    d.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(DIAS_BT)
    return len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--desde", default=None, help="YYYY-MM-DD (por defecto, la frontera)")
    a = ap.parse_args()

    s = pd.read_csv(SERIE_PROD, encoding="utf-8-sig")
    frontera = max(s["dia"].astype(str).str[:10])
    desde = a.desde or frontera
    log("=" * 66)
    log("frontera del persistidor: %s  (%d dias historicos)" % (frontera, len(s)))

    cad = sorted(re.findall(r"(\d{4}-\d{2}-\d{2})",
                            " ".join(p.name for p in
                                     CADENAS.glob("30MINDATA_QQQ_*.parquet"))))
    # La frontera declarada es un tope DURO: por encima de ella los dias son
    # OOS y no se tocan. Sin esto, cada dia que llegara una cadena nueva el
    # reconstructor se comeria un dia de OOS y el tramo fuera de muestra se
    # vaciaria solo -- la forma mas silenciosa de enganarse.
    _fr = json.loads((DIR / "data" / "frontera.json").read_text(encoding="utf-8"))
    TOPE = _fr["frontera_is_oos"]
    objetivo = [d for d in cad if desde < d <= TOPE]
    log("frontera declarada IS/OOS: %s (tope duro)" % TOPE)
    ya = set()
    if DIAS_BT.exists():
        ya = set(pd.read_csv(DIAS_BT, encoding="utf-8-sig")["dia"].astype(str).str[:10])
    pend = [d for d in objetivo if d not in ya]

    log("cadenas disponibles hasta %s" % (cad[-1] if cad else "-"))
    log("dias objetivo: %d | ya calculados: %d | PENDIENTES: %d"
        % (len(objetivo), len(objetivo) - len(pend), len(pend)))
    if pend:
        log("   de %s a %s  (~%.0f min a 55 s/dia)"
            % (pend[0], pend[-1], len(pend) * 55 / 60))
    if a.dry_run or not pend:
        log("(nada que hacer)" if not pend else "(--dry-run)")
        return 0

    ok, fallos, t0 = 0, [], datetime.now()
    for i, dia in enumerate(pend, 1):
        el = (datetime.now() - t0).total_seconds()
        eta = (el / max(1, i - 1)) * (len(pend) - i + 1) / 60 if i > 1 else len(pend) * 55 / 60
        log("[%d/%d] %s   (ETA ~%.0f min)" % (i, len(pend), dia, eta))
        p = correr_adhoc(dia)
        if p is None:
            fallos.append((dia, "el ADHOC no dejo parquet")); continue
        raw, nc, err = dial_desde_parquet(p)
        if raw is None:
            fallos.append((dia, err)); continue
        if nc < MIN_CELDAS:
            fallos.append((dia, "solo %d celdas" % nc)); continue
        n = guardar([{"dia": dia, "raw": raw, "n_celdas": nc, "origen": "BACKTEST"}])
        log("       raw=%.6e  (%d celdas)  -> dias_backtest.csv: %d" % (raw, nc, n))
        ok += 1

    log("=" * 66)
    log("calculados %d de %d en %.0f min" % (ok, len(pend),
                                             (datetime.now() - t0).total_seconds() / 60))
    for d, m in fallos:
        log("   FALLO %s: %s" % (d, m))
    if ok:
        log("Siguiente: update_dashboard.py mapea BACKTEST -> IS, y OOS")
        log("empieza limpio con el proximo dia del LIVE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
