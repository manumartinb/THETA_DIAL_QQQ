# -*- coding: cp1252 -*-
r"""
Recupera los dias de THETA_DIAL que el LIVE no llego a calcular.

EL PROBLEMA QUE RESUELVE
------------------------
El dial del dia lo calcula el LIVE de QQQ a las 18:30, y lo lanza el
orquestador. Si el orquestador se cae -- como el viernes 2026-08-21 -- ese dia
se pierde y la serie queda con un agujero para siempre.

Pero **los datos no se pierden**. Las cadenas 30MIN las descarga el MASTER
DAILY, que es un proceso distinto y sigue corriendo. La del 21-ago estaba en
disco al dia siguiente. Lo unico que falto fue el CALCULO, y el calculo se puede
rehacer.

COMO
----
El backtester ADHOC de un solo dia vuelca `T0_DIAL_QQQ_<fecha>.parquet` con
`dia, hora, DTE1, DTE2, SPX, theta_k2, ...` -- justo lo que necesita el dial. Y
lo vuelca ANTES del bloque forward, a proposito, para que se pueda usar el mismo
dia sin esperar a que madure el PnL (ver su comentario en la linea ~3365).

Con eso, la receta es: correr el ADHOC para el dia que falta, leer ese parquet y
aplicarle la misma formula de siempre (media de las medias por celda DTE1xDTE2
de theta_k2/spot).

DOS AVISOS QUE VAN EN LOS DATOS, NO EN UN COMENTARIO
----------------------------------------------------
1. **El dia recuperado NO es identico al que habria emitido el LIVE.** El ADHOC
   entra a las **10:30 ET** (= 16:30 CEST, la hora de la madre) y el LIVE a las
   **12:30 ET**. Dos horas de diferencia sobre una cadena que se mueve. Ademas
   el ADHOC usa la poblacion de candidatos del BACKTESTER, no la del LIVE.
   Por eso el dia se marca `RECUPERADO` en `dias_live.csv` y el dashboard lo
   pinta aparte: mezclarlo en silencio con los dias del LIVE seria vender como
   equivalente algo que no lo es.

2. **Curiosamente, el recuperado es MAS consistente con el historico** que el
   propio LIVE: los 1.549 dias de la serie IS son todos de las 16:30 CEST. Pero
   "mas consistente con A" no es "igual que B", y el tramo OOS esta hecho de B.

EL FICHERO ADHOC ES GENERADO AUTOMATICAMENTE ("NO EDITAR A MANO"), asi que este
script NUNCA lo toca: hace una COPIA temporal con la fecha sustituida, la corre
y la borra.

USO
---
    python recuperar_dias.py                 # detecta y recupera lo que falte
    python recuperar_dias.py --dry-run       # solo dice que haria
    python recuperar_dias.py 2026-08-21      # un dia concreto
    python recuperar_dias.py --control 2026-08-20
                                             # recalcula un dia que YA tenemos
                                             # por el LIVE y compara -> mide la
                                             # separacion real entre las dos vias
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(__file__).resolve().parent
EST = Path(r"C:\Users\Administrator\Desktop\BULK OPTIONSTRAT\ESTRATEGIAS")
DESK = Path.home() / "Desktop"

ADHOC = (EST / "Batman" / "QQQ" / "Backtester"
         / "Batman QQQ Gen 3 V42 BACKTESTER FILE TO FILE (Fable 5) [ADHOC SINGLE DAY].py")
ADHOC_OUT = DESK / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES_ADHOC"
CADENAS = (DESK / "FINAL DATA" / "HIST AND STREAMING DATA"
           / "QQQ UPDATED HISTORICAL DAYS PARQUET")
SERIE_PROD = (DESK / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
              / "GEN3_THETA_DIAL_SERIE_QQQ.csv")
DIAS_LIVE = DIR / "data" / "dias_live.csv"

# Las MISMAS bandas del persistidor y del LIVE. Si cambian ahi, cambian aqui.
B1 = [199, 250, 300, 350, 400, 450, 500]
B2 = [249, 350, 450, 600, 800, 1045]
MIN_CELDAS = 4          # el mismo umbral que daily_refresh
TIMEOUT_ADHOC = 3600    # 1 h por dia; si tarda mas, algo va mal


def log(m):
    print("[RECUP %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def dial_desde_parquet(p: Path):
    """La formula canonica: media de las MEDIAS POR CELDA (DTE1 x DTE2) de
    theta_k2/spot. Identica a persist_gen3_theta_dial_symbol y al LIVE."""
    d = pd.read_parquet(p)
    spot = next((c for c in ("QQQ", "SPY", "SPX", "SPOT") if c in d.columns), None)
    if spot is None:
        return None, 0, "sin columna de spot"
    for c in ("theta_k2", spot, "DTE1", "DTE2"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["x"] = d["theta_k2"] / d[spot]
    d["b1"] = pd.cut(d["DTE1"], B1, labels=False)
    d["b2"] = pd.cut(d["DTE2"], B2, labels=False)
    d = d.dropna(subset=["x", "b1", "b2"])
    if d.empty:
        return None, 0, "ningun candidato cae en las celdas"
    por_celda = d.groupby(["b1", "b2"], observed=True)["x"].mean()
    return float(por_celda.mean()), int(len(por_celda)), None


def correr_adhoc(dia: str) -> Path | None:
    """Copia temporal del ADHOC con la fecha sustituida. NUNCA toca el original:
    lleva cabecera 'GENERADO AUTOMATICAMENTE -- NO EDITAR A MANO'."""
    destino = ADHOC_OUT / ("T0_DIAL_QQQ_%s.parquet" % dia)
    if destino.exists():
        log("   ya existe %s, no se recalcula" % destino.name)
        return destino

    src = ADHOC.read_text(encoding="utf-8-sig", errors="replace")
    nuevo, n = re.subn(r'ADHOC_ONLY_DATES\s*=\s*\[[^\]]*\]',
                       'ADHOC_ONLY_DATES = ["%s"]' % dia, src, count=1)
    if n != 1:
        log("   ERROR: no encuentro ADHOC_ONLY_DATES en el ADHOC")
        return None

    tmpdir = Path(tempfile.mkdtemp(prefix="adhoc_recup_"))
    tmp = tmpdir / ADHOC.name
    try:
        tmp.write_text(nuevo, encoding="utf-8-sig")
        log("   corriendo el ADHOC para %s (puede tardar)..." % dia)
        t0 = datetime.now()
        r = subprocess.run([sys.executable, str(tmp)], cwd=str(ADHOC.parent),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT_ADHOC)
        dt = (datetime.now() - t0).total_seconds()
        for ln in (r.stdout or "").split("\n"):
            if "[DIAL]" in ln or "candidatos" in ln.lower():
                log("      " + ln.strip()[:110])
        log("   ADHOC rc=%d en %.0f s" % (r.returncode, dt))
        if not destino.exists():
            log("   AVISO: el ADHOC no dejo %s" % destino.name)
            if r.stderr:
                log("      stderr: " + r.stderr.strip()[-300:])
            return None
        return destino
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def dias_conocidos():
    """Los que ya tienen dial: historico del persistidor + los propios."""
    ks = set()
    if SERIE_PROD.exists():
        s = pd.read_csv(SERIE_PROD, encoding="utf-8-sig")
        ks |= set(s["dia"].astype(str).str[:10])
    if DIAS_LIVE.exists():
        s = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        ks |= set(s["dia"].astype(str).str[:10])
    return ks


def guardar(dia, raw, n_celdas, origen):
    if DIAS_LIVE.exists():
        d = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        d["dia"] = d["dia"].astype(str).str[:10]
    else:
        d = pd.DataFrame(columns=["dia", "raw", "n_celdas"])
    if "origen" not in d.columns:
        # los que ya estaban vinieron del LIVE; se etiquetan como tal
        d["origen"] = "LIVE"
    d = pd.concat([d, pd.DataFrame([{"dia": dia, "raw": raw,
                                     "n_celdas": n_celdas, "origen": origen}])],
                  ignore_index=True)
    d = d.drop_duplicates(subset=["dia"], keep="last").sort_values("dia")
    DIAS_LIVE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DIAS_LIVE.with_suffix(".csv.tmp")       # temporal + rename, nunca en sitio
    d.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(DIAS_LIVE)
    return len(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dias", nargs="*", help="dias concretos YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--control", metavar="YYYY-MM-DD",
                    help="recalcula un dia que YA tenemos del LIVE y compara")
    a = ap.parse_args()

    log("=" * 66)

    # ---------- modo CONTROL: medir la separacion entre las dos vias ----------
    if a.control:
        dia = a.control
        log("CONTROL sobre %s -- ADHOC (10:30 ET) vs LIVE (12:30 ET)" % dia)
        if not DIAS_LIVE.exists():
            log("no hay dias_live.csv con que comparar"); return 1
        dl = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        dl["dia"] = dl["dia"].astype(str).str[:10]
        fila = dl[dl["dia"] == dia]
        if fila.empty:
            log("%s no esta en dias_live.csv" % dia); return 1
        raw_live = float(fila["raw"].iloc[0])
        p = correr_adhoc(dia)
        if p is None:
            return 1
        raw_ad, nc, err = dial_desde_parquet(p)
        if raw_ad is None:
            log("no se pudo calcular: %s" % err); return 1
        log("")
        log("   LIVE   (12:30 ET) raw = %.9e" % raw_live)
        log("   ADHOC  (10:30 ET) raw = %.9e   (%d celdas)" % (raw_ad, nc))
        log("   diferencia relativa   = %+.2f%%" % (100 * (raw_ad / raw_live - 1)))
        log("")
        log("   Interpretalo asi: por debajo de ~2%% las dos vias son")
        log("   intercambiables para el percentil; por encima, un dia recuperado")
        log("   NO se puede pintar como si fuera del LIVE.")
        return 0

    # ---------- que dias faltan ----------
    conocidos = dias_conocidos()
    if a.dias:
        faltan = [d for d in a.dias]
    else:
        disponibles = sorted(re.findall(r"(\d{4}-\d{2}-\d{2})",
                                        " ".join(p.name for p in
                                                 CADENAS.glob("30MINDATA_QQQ_*.parquet"))))
        # solo desde el primer dia que ya tenemos del LIVE: hacia atras esta el
        # hueco de 131 dias, que es una decision aparte y NO se toca aqui
        if DIAS_LIVE.exists():
            dl = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
            desde = min(dl["dia"].astype(str).str[:10])
        else:
            desde = max(conocidos) if conocidos else "9999-12-31"
        faltan = [d for d in disponibles if d >= desde and d not in conocidos]

    log("dias con dial: %d | cadenas disponibles: %d"
        % (len(conocidos), len(list(CADENAS.glob("30MINDATA_QQQ_*.parquet")))))
    if not faltan:
        log("no falta ningun dia. Nada que hacer.")
        return 0
    log("FALTAN %d dia(s): %s" % (len(faltan), ", ".join(faltan)))
    if a.dry_run:
        log("(--dry-run: no se recupera nada)")
        return 0

    ok = 0
    for dia in faltan:
        log("-" * 66)
        log("recuperando %s" % dia)
        cad = CADENAS / ("30MINDATA_QQQ_%s.parquet" % dia)
        if not cad.exists():
            log("   sin cadena en disco -> imposible. Se salta.")
            continue
        p = correr_adhoc(dia)
        if p is None:
            continue
        raw, nc, err = dial_desde_parquet(p)
        if raw is None:
            log("   no se pudo calcular el dial: %s" % err)
            continue
        if nc < MIN_CELDAS:
            log("   RECHAZADO: solo %d celda(s) < %d. Un dial con tan poca "
                "cobertura contaminaria los percentiles futuros." % (nc, MIN_CELDAS))
            continue
        n = guardar(dia, raw, nc, "RECUPERADO")
        log("   OK  raw=%.6e  (%d celdas)  -> dias_live.csv tiene %d" % (raw, nc, n))
        ok += 1

    log("=" * 66)
    log("recuperados %d de %d" % (ok, len(faltan)))
    if ok:
        log("Ahora corre daily_refresh.py para republicar el dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
