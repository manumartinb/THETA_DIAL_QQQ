# -*- coding: cp1252 -*-
r"""
THETA_DIAL_QQQ dashboard -- refresco DIARIO. Lo llama el Master Daily.

QUE HACE
--------
1. Busca la entrega canonica de QQQ mas reciente.
2. Si trae un dia que la serie no tiene, lo anade.
3. Recalcula el percentil expanding SOLO-PASADO de toda la serie.
4. Reescribe data/theta_dial_data.json (conservando las tablas del estudio).
5. git add + commit + push a GitHub Pages.

POR QUE LEE LA ENTREGA Y NO RECALCULA
-------------------------------------
Se probo recalcular el dial desde los parquets del dia (2026-08-19). Sale con un
1,55% de error, que en percentil son ~5 puntos y hace que el 7,7% de los dias
cambien de estado. La causa es estructural, no de precision: el dial historico
se calcula sobre los candidatos que sobrevivieron al filtro FORWARD, y para el
dia de hoy ese filtro no puede aplicarse porque el futuro no ha pasado.

El unico numero que coincide con el que ve el usuario en la app es el que emite
el LIVE. Por eso se lee de su entrega. Coste: un dia de retraso en el punto mas
nuevo, porque el Master Daily corre antes que el LIVE de las 18:30. Es lo mismo
que hacen los demas dashboards de la casa ("publica historico al dia aunque hoy
no haya LIVE").

NUNCA FALLA POR NO HABER ENTREGA NUEVA: si no la hay, republica lo que ya tenia
y lo deja dicho en `meta.sin_datos_nuevos`. Un dashboard congelado que avisa de
que esta congelado es correcto; uno que revienta el pipeline, no.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import update_dashboard as full                                   # noqa: E402

GEN3 = Path.home() / "Desktop" / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
SERIE = GEN3 / "GEN3_THETA_DIAL_SERIE_QQQ.csv"
ENTREGAS = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
            / "QQQ" / "ANALISIS" / "BATMAN_QQQ_LT_OWN_REACT" / "backend" / "data"
            / "deliveries")
DATA = DIR / "data" / "theta_dial_data.json"


def log(m):
    print("[THDQ %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def leer_entregas():
    """{dia: raw} de todas las entregas que traigan THETA_DIAL_RAW o _PCTL."""
    out = {}
    if not ENTREGAS.exists():
        return out
    for f in sorted(ENTREGAS.glob("Batman_QQQ_Delivery_*.csv")):
        try:
            d = pd.read_csv(f, encoding="utf-8-sig",
                            usecols=lambda c: c in ("dia", "THETA_DIAL_RAW",
                                                    "THETA_DIAL_PCTL"))
        except Exception as e:
            log("  AVISO: no se pudo leer %s (%s)" % (f.name, e))
            continue
        if "dia" not in d.columns or "THETA_DIAL_RAW" not in d.columns:
            continue
        v = pd.to_numeric(d["THETA_DIAL_RAW"], errors="coerce").dropna()
        if v.empty:
            continue
        # el dial es UNO por dia: si hay varios valores, algo va mal aguas arriba
        if v.nunique() > 1:
            log("  AVISO: %s trae %d valores distintos de THETA_DIAL_RAW; "
                "se usa el primero" % (f.name, v.nunique()))
        dia = str(d["dia"].dropna().astype(str).str[:10].mode().iloc[0])
        out[dia] = float(v.iloc[0])
    return out


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(DIR),
                          capture_output=True, text=True, timeout=180)


def main():
    log("=" * 62)
    log("THETA_DIAL_QQQ -- refresco diario")

    s = pd.read_csv(SERIE, encoding="utf-8-sig")
    s["dia"] = s["dia"].astype(str).str[:10]
    conocidos = set(s["dia"])
    ult_serie = max(conocidos)
    log("serie actual: %d dias, hasta %s" % (len(s), ult_serie))

    ent = leer_entregas()
    nuevos = {d: v for d, v in ent.items() if d not in conocidos}
    log("entregas con dial: %d | dias NUEVOS: %d" % (len(ent), len(nuevos)))

    if nuevos:
        add = pd.DataFrame({"dia": sorted(nuevos), "raw": [nuevos[d] for d in sorted(nuevos)]})
        s = pd.concat([s[["dia", "raw"]], add], ignore_index=True)
        s = s.drop_duplicates(subset=["dia"], keep="first").sort_values("dia")
        # escritura atomica: tmp + replace, nunca en sitio
        tmp = SERIE.with_suffix(".csv.tmp")
        s.to_csv(tmp, index=False, encoding="utf-8-sig")
        tmp.replace(SERIE)
        log("serie ampliada a %d dias (hasta %s)" % (len(s), s["dia"].iloc[-1]))
        for d in sorted(nuevos):
            log("   + %s  raw=%.6e" % (d, nuevos[d]))
    else:
        log("sin dias nuevos: se republica lo que ya habia")

    data = full.build()
    if not nuevos:
        data["meta"]["sin_datos_nuevos"] = True
        data["meta"]["nota"] = ("No habia entrega con dia nuevo en este refresco. "
                                "El grafico muestra el historico hasta la fecha de "
                                "`latest`; el chip de antiguedad lo indica.")
        DATA.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    L = data.get("latest") or {}
    log("latest: %s  percentil %.1f  %s  (hace %s dias)"
        % (L.get("d"), L.get("p", float("nan")), L.get("e"), L.get("edad_dias")))

    # ---- publicar ----
    if not (DIR / ".git").exists():
        log("AVISO: no hay repo git aqui todavia -> no se publica (solo local)")
        return 0
    # `-u` (--update) versiona TODO fichero YA RASTREADO que haya cambiado, y
    # solo esos: nunca arrastra ficheros nuevos ni basura suelta. Antes esto era
    # una lista fija de dos rutas, y una edicion al propio update_dashboard.py
    # se quedaba fuera del repo en silencio -- la publicacion dejaba de ser
    # reproducible: el JSON de GitHub ya no salia del codigo de GitHub.
    # Lo cazo la verificacion end-to-end del 2026-08-20.
    git("add", "-u")
    git("add", "data/theta_dial_data.json")   # por si aun no estuviera rastreado
    st = git("status", "--porcelain")
    if not st.stdout.strip():
        log("nada que commitear")
        return 0
    msg = "daily refresh %s (latest %s, %s)" % (
        datetime.now().strftime("%Y-%m-%d"), L.get("d"), L.get("e"))
    c = git("commit", "-m", msg)
    if c.returncode != 0:
        log("AVISO: commit fallo -> %s" % (c.stderr or c.stdout)[:200])
        return 0
    p = git("push")
    if p.returncode != 0:
        log("AVISO: push fallo -> %s" % (p.stderr or p.stdout)[:200])
        return 0
    log("publicado OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
