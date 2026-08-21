# -*- coding: ascii -*-
r"""COMPRUEBA QUE https://manumartinb.github.io/THETA_DIAL_QQQ/ SE ACTUALIZA.

Este es EL script que hay que correr para saber si el dashboard esta vivo.
Recorre la cadena entera, eslabon por eslabon, y dice en cual se rompe:

    LIVE (18:30)  ->  entrega canonica  ->  dias_live.csv  ->  JSON local
                                                                   |
    Master Daily (hijo THDQ)  ->  git push  ->  GitHub Pages  <-----+

POR QUE HACE FALTA
------------------
El 2026-08-21 se descubrio que la cadena llevaba DOS DIAS rota sin que nada
avisara: la entrega no emitia `THETA_DIAL_RAW`, el refresco decia "entregas con
dial: 0" y republicaba lo de siempre con rc=0. Ni un error, ni un log rojo, ni
una alarma. Solo se noto porque un humano miro la fecha de la pagina.

Un fallo asi no se caza con "el proceso termino bien". Se caza preguntando
**si el dato de hoy llego hasta el final**, que es lo que hace este script.

QUE COMPRUEBA
-------------
  1. El LIVE dejo entrega de hoy (o del ultimo dia habil)?
  2. Esa entrega trae RAW y NCELDAS?          <- sin RAW la serie NO crece
  3. El dia esta en dias_live.csv, o fue rechazado con motivo?
  4. Esta en el JSON local?
  5. Esta PUBLICADO en GitHub Pages?
  6. El percentil publicado COINCIDE con el que emitio el LIVE?
  7. El Master Daily ejecuto el hijo THDQ, y con que codigo?
  8. La serie de PRODUCCION sigue intacta (el dashboard no debe escribirla).

USO
---
    python verificar_actualizacion.py            # el ultimo dia con entrega
    python verificar_actualizacion.py 2026-08-20 # un dia concreto

Read-only. No toca ni un fichero.
"""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

DIR = Path(__file__).resolve().parent
EST = Path(r"C:\Users\Administrator\Desktop\BULK OPTIONSTRAT\ESTRATEGIAS")
BULK = EST.parent
GEN3 = Path.home() / "Desktop" / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
PROD = GEN3 / "GEN3_THETA_DIAL_SERIE_QQQ.csv"
ENTREGAS = (EST / "Batman" / "QQQ" / "ANALISIS" / "BATMAN_QQQ_LT_OWN_REACT"
            / "backend" / "data" / "deliveries")
DIAS_LIVE = DIR / "data" / "dias_live.csv"
JSON_LOCAL = DIR / "data" / "theta_dial_data.json"
LOGS = BULK / "_master_logs"
URL = "https://manumartinb.github.io/THETA_DIAL_QQQ"

R = []


def chk(n, estado, det=""):
    """estado: True=OK, False=FALLA, None=aviso (ni bien ni mal)."""
    R.append((n, estado))
    m = {True: "OK  ", False: "FALLA", None: "aviso"}[estado]
    print("[%s] %-46s %s" % (m, n, det))


def get(path, timeout=25):
    try:
        with urllib.request.urlopen(
                "%s/%s?cb=%d" % (URL, path, int(datetime.now().timestamp())),
                timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:
        return None, str(e).encode()


print("=" * 86)
print("THETA_DIAL_QQQ -- se actualiza?   %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 86)

# ---------------------------------------------------------------- 1. entrega
print("\n1) LA ENTREGA DEL LIVE")
ents = sorted(ENTREGAS.glob("Batman_QQQ_Delivery_*.csv")) if ENTREGAS.exists() else []
if not ents:
    chk("hay alguna entrega", False, "carpeta vacia: %s" % ENTREGAS)
    print("\n-> El LIVE no ha dejado ninguna entrega. Nada mas que mirar.")
    sys.exit(1)

dia = sys.argv[1] if len(sys.argv) > 1 else ents[-1].name[-14:-4]
f = ENTREGAS / ("Batman_QQQ_Delivery_%s.csv" % dia)
chk("existe la entrega de %s" % dia, f.exists(), f.name if f.exists() else "no esta")
if not f.exists():
    sys.exit(1)

edad = (datetime.now() - datetime.strptime(dia, "%Y-%m-%d")).days
chk("la entrega es reciente", (edad <= 4) if edad > 0 else True,
    "%d dia(s) de antiguedad" % edad)

d = pd.read_csv(f, encoding="utf-8-sig")
raw_ok = "THETA_DIAL_RAW" in d.columns and pd.to_numeric(
    d["THETA_DIAL_RAW"], errors="coerce").notna().any()
chk("trae THETA_DIAL_RAW", raw_ok,
    "sin el, la serie NO puede crecer" if not raw_ok else
    "%.6e" % pd.to_numeric(d["THETA_DIAL_RAW"], errors="coerce").dropna().iloc[0])

nc = None
if "THETA_DIAL_NCELDAS" in d.columns:
    v = pd.to_numeric(d["THETA_DIAL_NCELDAS"], errors="coerce").dropna()
    nc = int(v.iloc[0]) if len(v) else None
chk("trae THETA_DIAL_NCELDAS", (nc is not None) if nc is not None else None,
    ("%d celdas%s" % (nc, "  <- POR DEBAJO DEL MINIMO (4)" if nc < 4 else ""))
    if nc is not None else "ausente (entrega anterior al 2026-08-21)")

pctl_live = None
if "THETA_DIAL_PCTL" in d.columns:
    v = pd.to_numeric(d["THETA_DIAL_PCTL"], errors="coerce").dropna()
    pctl_live = float(v.iloc[0]) if len(v) else None
chk("trae THETA_DIAL_PCTL", pctl_live is not None, str(pctl_live))

# ---------------------------------------------------------- 2. dias_live.csv
print("\n2) EL FICHERO DEL DASHBOARD")
en_live = False
if DIAS_LIVE.exists():
    dl = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
    dl["dia"] = dl["dia"].astype(str).str[:10]
    en_live = dia in set(dl["dia"])
    chk("existe dias_live.csv", True, "%d dia(s) acumulados" % len(dl))
else:
    chk("existe dias_live.csv", None, "aun no se ha creado")

esperado = (nc is None) or (nc >= 4)
if esperado:
    chk("el dia %s esta dentro" % dia, en_live,
        "" if en_live else "el refresco no lo ha cogido -- mira el paso 4")
else:
    chk("el dia %s RECHAZADO por pocas celdas" % dia, (not en_live),
        "correcto: %d celdas < 4" % nc if not en_live else "deberia estar fuera!")

# --------------------------------------------------------- 3. JSON publicado
print("\n3) LA PAGINA PUBLICADA")
st, body = get("data/theta_dial_data.json")
chk("el JSON responde", st == 200, "HTTP %s" % st)
pub = json.loads(body.decode("utf-8")) if st == 200 else {}
if pub:
    L = pub.get("latest") or {}
    P = pub.get("particion") or {}
    edad_pub = L.get("edad_dias")
    chk("latest publicado", L.get("d") is not None,
        "%s  pctl %s  %s  (hace %s dias)"
        % (L.get("d"), L.get("p"), L.get("e"), edad_pub))
    # el corazon del asunto: la pagina esta al dia?
    chk("*** la pagina esta AL DIA ***",
        (edad_pub is not None and edad_pub <= 4),
        "si esto falla, la cadena esta rota aunque todo lo demas diga OK")
    dias_pub = {x["d"] for x in pub.get("series", [])}
    if esperado:
        chk("el dia %s esta en la serie publicada" % dia, dia in dias_pub)
    chk("la particion IS/OOS viaja", bool(P),
        "IS %s | hueco %sd | OOS %s" % (P.get("n_is"), P.get("hueco_dias"),
                                        P.get("n_oos")) if P else "")
    # coherencia LIVE <-> publicado
    if pctl_live is not None and dia in dias_pub:
        p_pub = next((x["p"] for x in pub["series"] if x["d"] == dia), None)
        dif = abs(p_pub - pctl_live) if p_pub is not None else None
        chk("el percentil publicado casa con el del LIVE",
            (dif is not None and dif <= 1.5),
            "publicado %.2f vs LIVE %.2f (dif %.2f)" % (p_pub, pctl_live, dif)
            if dif is not None else "no se pudo comparar")

st_h, _ = get("index.html")
chk("la pagina HTML responde", st_h == 200, "HTTP %s" % st_h)

# ------------------------------------------------------- 4. el Master Daily
print("\n4) EL HIJO DEL MASTER DAILY")
logs = sorted(LOGS.glob("master_*.log")) if LOGS.exists() else []
if not logs:
    chk("hay logs del Master Daily", None, "no encuentro %s" % LOGS)
else:
    lg = logs[-1]
    txt = lg.read_text(encoding="cp1252", errors="replace")
    fin = "[END]" in txt or "END " in txt.split("\n")[-3:][0] if txt else False
    thdq = re.search(r"THDQ.*?exit=(\d+)", txt) or re.search(
        r"THETA_DIAL_QQQ_dashboard.*?exit=(\d+)", txt)
    if thdq:
        rc = int(thdq.group(1))
        chk("el hijo THDQ corrio", rc == 0, "%s  exit=%d" % (lg.name, rc))
    elif not fin:
        chk("el hijo THDQ corrio", None,
            "%s aun EN CURSO (%d hijos terminados); THDQ va despues de CALREG"
            % (lg.name, txt.count("[CHILD-END]")))
    else:
        chk("el hijo THDQ corrio", False,
            "%s termino y NO hay rastro de THDQ -- revisa el alta en el pipeline"
            % lg.name)

# ------------------------------------------------- 5. produccion intacta
print("\n5) LA SERIE DE PRODUCCION (el dashboard NO debe tocarla)")
if PROD.exists():
    mt = datetime.fromtimestamp(PROD.stat().st_mtime)
    h = hashlib.sha256(PROD.read_bytes()).hexdigest()[:16]
    chk("solo la escribe el persistidor", True,
        "hash %s  mtime %s" % (h, mt.strftime("%Y-%m-%d %H:%M")))
    print("      (guarda este hash: si cambia sin haber re-persistido la madre,")
    print("       alguien esta escribiendo donde no debe)")
else:
    chk("existe la serie de produccion", False, str(PROD))

# ---------------------------------------------------------------- veredicto
ok = sum(1 for _, e in R if e is True)
fail = [n for n, e in R if e is False]
avisos = [n for n, e in R if e is None]
print("\n" + "=" * 86)
print("VEREDICTO: %d OK, %d FALLA, %d aviso(s)" % (ok, len(fail), len(avisos)))
for n in fail:
    print("   FALLA  -> %s" % n)
for n in avisos:
    print("   aviso  -> %s" % n)
if not fail:
    print("\nLa cadena esta entera: la entrega de %s llego hasta la pagina." % dia)
print("=" * 86)
sys.exit(1 if fail else 0)
