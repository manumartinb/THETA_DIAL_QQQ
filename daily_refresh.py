# -*- coding: cp1252 -*-
r"""
THETA_DIAL_QQQ dashboard -- refresco DIARIO. Lo llama el Master Daily.

QUE HACE
--------
1. Lee la serie historica del persistidor (SOLO LECTURA).
2. Busca en las entregas del LIVE los dias que esa serie todavia no tiene.
3. Descarta los que vengan con POCAS CELDAS (ver mas abajo).
4. Guarda los aceptados en SU PROPIO fichero, `data/dias_live.csv`.
5. Publica la union de las dos series: historico del persistidor + dias del LIVE.
6. git add + commit + push a GitHub Pages.

DOS COSAS QUE ESTE FICHERO HACIA MAL Y SE ARREGLARON EL 2026-08-21
------------------------------------------------------------------

(1) ESCRIBIA EN UN FICHERO DE PRODUCCION. Appendeaba los dias nuevos DENTRO de
    `GEN3_THETA_DIAL_SERIE_QQQ.csv`, que es la referencia que el LIVE lee cada
    dia para rankear el dial. Tres problemas en uno:
      - un script de una pagina web tenia permiso de escritura sobre una
        referencia de la que depende el regimen que se opera;
      - `persist_gen3_theta_dial_symbol.py` reescribe ese fichero ENTERO con
        `to_csv`, sin leer lo que hay (verificado en su linea 208-210), asi que
        re-persistir -- cosa normal al ampliar la madre -- BORRABA en silencio
        todos los dias que este script habia anadido;
      - y ampliar la referencia del LIVE debe ser una decision del persistidor,
        no un efecto colateral de refrescar una web.
    AHORA: la produccion se abre en modo lectura y nunca se toca. Los dias del
    LIVE viven en `data/dias_live.csv`, que es de este dashboard. Si manana el
    persistidor extiende el historico, su valor MANDA sobre el del LIVE para
    ese dia (es el backtesteado, con su filtro forward aplicado).

(2) ACEPTABA CUALQUIER VALOR. El dial es "media de las medias por celda
    (DTE1 x DTE2)". Estratificar lo hace invariante a CUANTOS candidatos caen
    en cada celda -- que era el objetivo -- pero NO a QUE celdas estan
    presentes. El backtest cubre 8 celdas de mediana; si un dia el LIVE
    entregase pocas, su raw no seria comparable con el historico. Medido sobre
    los 1.799 dias:

        celdas | error tipico del raw | en puntos de percentil
             1 |                 9,0% |                   16,5
             2 |                 5,5% |                    9,5
             4 |                 3,0% |                    5,4
             8 |                 1,6% |                    3,0

    La banda BAJO entera mide 12,3 puntos, asi que con 1 celda el dia puede
    cambiar de estado. Y no se queda en pintarlo mal: entra en la serie y
    contamina los percentiles de todos los dias siguientes.
    AHORA: se exige `THETA_DIAL_NCELDAS >= MIN_CELDAS` (4). Por debajo, el dia
    se descarta y se dice en el log.

POR QUE LEE LA ENTREGA Y NO RECALCULA
-------------------------------------
Se probo recalcular el dial del dia desde los parquets (2026-08-19): 1,55% de
error, ~5 puntos de percentil, y el 7,7% de los dias cambiaba de estado. La
causa es estructural: el dial historico se calcula sobre los candidatos que
sobrevivieron al filtro FORWARD, y para hoy ese filtro no puede aplicarse. El
unico numero que coincide con el que ve el usuario en la app es el del LIVE.

NUNCA FALLA POR NO HABER ENTREGA NUEVA: republica lo que ya tenia y lo deja
dicho en `meta.sin_datos_nuevos`. Un dashboard congelado que avisa es correcto;
uno que revienta el pipeline, no.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import update_dashboard as full                                   # noqa: E402

GEN3 = Path.home() / "Desktop" / "BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
SERIE_PROD = GEN3 / "GEN3_THETA_DIAL_SERIE_QQQ.csv"     # <-- SOLO LECTURA
DIAS_LIVE = DIR / "data" / "dias_live.csv"              # <-- lo nuestro
ENTREGAS = (Path.home() / "Desktop" / "BULK OPTIONSTRAT" / "ESTRATEGIAS" / "Batman"
            / "QQQ" / "ANALISIS" / "BATMAN_QQQ_LT_OWN_REACT" / "backend" / "data"
            / "deliveries")
DATA = DIR / "data" / "theta_dial_data.json"

MIN_CELDAS = 4      # ver el bloque (2) de la cabecera


def log(m):
    print("[THDQ %s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def leer_entregas():
    """{dia: (raw, n_celdas)} de las entregas que traigan THETA_DIAL_RAW."""
    out = {}
    if not ENTREGAS.exists():
        return out
    usa = ("dia", "THETA_DIAL_RAW", "THETA_DIAL_PCTL", "THETA_DIAL_NCELDAS")
    for f in sorted(ENTREGAS.glob("Batman_QQQ_Delivery_*.csv")):
        try:
            d = pd.read_csv(f, encoding="utf-8-sig",
                            usecols=lambda c: c in usa)
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
        # NCELDAS es de alta 2026-08-21: las entregas viejas no lo traen. Se
        # marca None y se decide abajo (se aceptan por compatibilidad, con aviso).
        nc = None
        if "THETA_DIAL_NCELDAS" in d.columns:
            c = pd.to_numeric(d["THETA_DIAL_NCELDAS"], errors="coerce").dropna()
            if not c.empty:
                nc = int(c.iloc[0])
        out[dia] = (float(v.iloc[0]), nc)
    return out


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(DIR),
                          capture_output=True, text=True, timeout=180)


def main():
    log("=" * 62)
    log("THETA_DIAL_QQQ -- refresco diario")

    # ---- 1) el historico del persistidor, SOLO LECTURA ----
    prod = pd.read_csv(SERIE_PROD, encoding="utf-8-sig")
    prod["dia"] = prod["dia"].astype(str).str[:10]
    prod = prod[["dia", "raw"]]
    log("historico del persistidor (solo lectura): %d dias, hasta %s"
        % (len(prod), prod["dia"].max()))

    # ---- 2) los dias que ya teniamos del LIVE ----
    if DIAS_LIVE.exists():
        live = pd.read_csv(DIAS_LIVE, encoding="utf-8-sig")
        live["dia"] = live["dia"].astype(str).str[:10]
    else:
        live = pd.DataFrame(columns=["dia", "raw", "n_celdas"])
    log("dias propios del LIVE acumulados: %d" % len(live))

    # ---- 3) los nuevos, con el filtro de celdas ----
    conocidos = set(prod["dia"]) | set(live["dia"])
    ent = leer_entregas()
    nuevos, rechazados = [], []
    for dia, (raw, nc) in sorted(ent.items()):
        if dia in conocidos:
            continue
        if nc is not None and nc < MIN_CELDAS:
            rechazados.append((dia, nc))
            continue
        if nc is None:
            log("  nota: %s no trae THETA_DIAL_NCELDAS (entrega anterior al "
                "2026-08-21); se acepta sin comprobar cobertura" % dia)
        nuevos.append({"dia": dia, "raw": raw, "n_celdas": (nc if nc is not None else -1)})

    log("entregas con dial: %d | dias NUEVOS aceptados: %d | rechazados: %d"
        % (len(ent), len(nuevos), len(rechazados)))
    for dia, nc in rechazados:
        log("  RECHAZADO %s: solo %d celda(s), por debajo del minimo de %d. "
            "Un dial con tan poca cobertura se desvia mas que el ancho de una "
            "banda de estado, y ademas contaminaria los percentiles futuros."
            % (dia, nc, MIN_CELDAS))
    for r in nuevos:
        log("  + %s  raw=%.6e  (%s celdas)"
            % (r["dia"], r["raw"], r["n_celdas"] if r["n_celdas"] > 0 else "?"))

    if nuevos:
        live = pd.concat([live, pd.DataFrame(nuevos)], ignore_index=True)
        live = live.drop_duplicates(subset=["dia"], keep="last").sort_values("dia")
        DIAS_LIVE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DIAS_LIVE.with_suffix(".csv.tmp")
        live.to_csv(tmp, index=False, encoding="utf-8-sig")
        tmp.replace(DIAS_LIVE)          # escritura atomica, y en NUESTRO fichero
        log("dias_live.csv ampliado a %d dias" % len(live))
    else:
        log("sin dias nuevos: se republica lo que ya habia")

    # ---- 4) publicar. La serie efectiva la compone update_dashboard ----
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

    # ---- 5) git ----
    if not (DIR / ".git").exists():
        log("AVISO: no hay repo git aqui todavia -> no se publica (solo local)")
        return 0
    # `-u` versiona lo YA RASTREADO que haya cambiado, y solo eso: nunca
    # arrastra ficheros nuevos ni basura suelta.
    git("add", "-u")
    git("add", "data/theta_dial_data.json", "data/dias_live.csv")
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
