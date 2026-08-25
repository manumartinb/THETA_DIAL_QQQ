# -*- coding: ascii -*-
r"""Bloque de PROCEDENCIA que viaja dentro de theta_dial_data.json.

PARA QUE SIRVE
--------------
La pagina publica cifras. Quien quiera comprobarlas necesita saber de que
fichero sale cada una, con que formula y con que constantes. Eso va aqui, con
RUTAS ABSOLUTAS, y viaja DENTRO del propio JSON publicado.

Objetivo concreto: que un agente con acceso al disco pueda ir a la madre,
rehacer el numero y peritar la pagina entera **sin entrar en este repo** y sin
preguntarle nada a nadie.

Se mantiene en un modulo aparte a proposito: es documentacion densa y no tiene
que ensuciar la logica de update_dashboard.py.
"""

BANDAS_DTE1 = [199, 250, 300, 350, 400, 450, 500]
BANDAS_DTE2 = [249, 350, 450, 600, 800, 1045]
MIN_HIST = 250
MIN_CELDAS = 4

_DESK = r"C:\Users\Administrator\Desktop"
_GEN3 = _DESK + r"\BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES"
_EST = _DESK + r"\BULK OPTIONSTRAT\ESTRATEGIAS"


def procedencia(frontera, n_backtest, n_vivo):
    return {
        "que_es": (
            "THETA_DIAL es un INDICADOR DE REGIMEN a nivel DIA para Batman QQQ "
            "LT. NO es una estrategia ni un modelo entrenado: no tiene un solo "
            "parametro ajustado contra el PnL. Es una formula determinista "
            "sobre theta_k2/spot."),

        "formula": {
            "1_por_candidato": "x = theta_k2 / spot   (theta de la pata LARGA back, k2)",
            "2_celda": "celda = (banda de DTE1, banda de DTE2)",
            "3_dentro": "media de x DENTRO de cada celda ocupada",
            "4_dial_raw": "RAW = media de esas medias  <- media de medias, NO media simple",
            "5_percentil": (
                "PCTL = percentil expanding SOLO-PASADO del RAW contra su propia "
                "historia (min_hist=%d dias), searchsorted side='right'." % MIN_HIST),
            "6_estado": "BAJO si PCTL < corte_bajo ; ALTO si >= corte_alto ; si no MEDIO",
            "por_que_media_de_medias": (
                "theta_k2/spot correlaciona +0,475 con DTE1 y +0,560 con DTE2, "
                "asi que una media simple dependeria de CUANTOS candidatos caen "
                "en cada banda de DTE. Ejemplo real (2026-08-21): 13 celdas con "
                "entre 8 y 1.580 candidatos -- ratio 200x -- y medias por celda "
                "de -1,516e-4 a -1,047e-4, un rango del 38%. Promediando por "
                "celda cada una pesa igual y el dial deja de depender del "
                "reparto. La ganancia esta medida: +0,027 de r_day con CI95 "
                "[+0,006, +0,047] por bootstrap de dia."),
            "cuantos_theta_k2": (
                "TODOS los del dia, no uno elegido. El 2026-08-21 habia 5.169 "
                "candidatos con solo 123 valores distintos de theta_k2, porque "
                "muchos candidatos comparten la misma pata k2 (misma expiracion "
                "y strike) y se diferencian en k1/k3."),
        },

        "constantes": {
            "bandas_dte1": BANDAS_DTE1,
            "bandas_dte2": BANDAS_DTE2,
            "min_hist_dias": MIN_HIST,
            "min_celdas_para_aceptar_un_dia": MIN_CELDAS,
            "cortes_estado": "en GEN3_THETA_DIAL_REF_QQQ.json -> cortes_estado",
        },

        "ficheros": {
            "madre": {
                "ruta": _GEN3 + r"\MADRE_GEN3_V42_QQQ_LT.csv",
                "que_es": ("203.716 filas / 1.799 dias. Brazo neutro = FWD_SLOT "
                           "que empieza por 'RAND_Q'."),
                "columnas_del_dial": ["dia", "hora", "DTE1", "DTE2", "SPX", "theta_k2"],
                "dos_trampas": (
                    "(1) la columna de spot se llama SPX pero contiene el precio "
                    "de QQQ -- herencia del clon multi-subyacente, rename "
                    "descartado el 2026-08-20 tras medir que tocaba 46 ficheros. "
                    "(2) 'hora' es hora de MADRID: 16:30 CEST = 10:30 ET."),
            },
            "serie_historica": {
                "ruta": _GEN3 + r"\GEN3_THETA_DIAL_SERIE_QQQ.csv",
                "que_es": "dia,raw -- la serie que el persistidor emite desde la madre.",
                "la_escribe": _EST + r"\Batman\_GEN3_MULTIASSET\persist_gen3_theta_dial_symbol.py",
                "nota": ("SOLO LECTURA para el dashboard. Es tambien la "
                         "referencia que el LIVE usa para rankear el dial del dia."),
            },
            "referencia_cortes": {
                "ruta": _GEN3 + r"\GEN3_THETA_DIAL_REF_QQQ.json",
                "que_es": "bandas de DTE y cortes de estado (P33/P67 de la distribucion del dial).",
            },
            "parquets_por_dia": {
                "ruta": _DESK + r"\BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES_ADHOC",
                "que_es": ("T0_DIAL_QQQ_<fecha>.parquet: los candidatos de ese dia "
                           "en T+0 con theta_k2 y los DTE. Es el fichero mas "
                           "comodo para reproducir un dia suelto."),
            },
            "cadenas_30min": {
                "ruta": _DESK + r"\FINAL DATA\HIST AND STREAMING DATA\QQQ UPDATED HISTORICAL DAYS PARQUET",
                "que_es": ("30MINDATA_QQQ_<fecha>.parquet, la materia prima. Las "
                           "descarga el MASTER DAILY, no el orquestador: por eso "
                           "un dia perdido del LIVE sigue siendo recalculable."),
            },
            "dias_reconstruidos": {
                "ruta": "data/dias_backtest.csv (en este repo)",
                "que_es": ("los 92 dias 2026-04-13..2026-08-21 que la madre no "
                           "cubre porque su gate forward exige PnL a W50. "
                           "Calculados con el backtester ADHOC: MISMO motor y "
                           "MISMA hora que la madre."),
            },
            "dias_en_vivo": {
                "ruta": "data/dias_live.csv (en este repo)",
                "que_es": "dias posteriores a la frontera, leidos de la entrega canonica del LIVE.",
            },
            "frontera": {
                "ruta": "data/frontera.json (en este repo)",
                "que_es": "la fecha que separa backtest de vivo. Tope duro: no se mueve.",
            },
            "estudio": {
                "ruta": _EST + r"\Batman\QQQ\ANALISIS\THETA_DIAL_QQQ_STUDY\tabla_completa_theta_dial.json",
                "que_es": ("de aqui salen TAL CUAL las tablas de deciles, estados, "
                           "cortes, cobertura y elite que muestra la pagina."),
            },
        },

        "scripts": {
            "generar_json": "update_dashboard.py",
            "refresco_diario": "daily_refresh.py  (lo llaman el LIVE de QQQ y el Master Daily)",
            "reconstruir_tramo": "reconstruir_homogeneo.py  (con el ADHOC, resumible)",
            "recuperar_un_dia": "recuperar_dias.py  (--control compara ADHOC vs LIVE)",
            "verificar_cadena": "verificar_actualizacion.py  (5 eslabones, de la entrega a la web)",
            "backtester_adhoc": (_EST + r"\Batman\QQQ\Backtester\Batman QQQ Gen 3 V42 "
                                 r"BACKTESTER FILE TO FILE (Fable 5) [ADHOC SINGLE DAY].py"),
        },

        "como_reproducir_un_dia": [
            "1. Abrir T0_DIAL_QQQ_<fecha>.parquet (o filtrar la madre por ese dia "
            "y por FWD_SLOT que empiece por RAND_Q).",
            "2. x = theta_k2 / SPX      (ojo: esa columna SPX es el precio de QQQ).",
            "3. b1 = pandas.cut(DTE1, bandas_dte1) ; b2 = pandas.cut(DTE2, bandas_dte2).",
            "4. Media de x por (b1,b2), y media de esas medias -> RAW del dia.",
            "5. PCTL: contra los RAW de TODOS los dias ANTERIORES, "
            "searchsorted(sorted(prev), raw, side='right') / len(prev) * 100.",
            "6. Comparar con el punto de 'series' que tenga esa fecha.",
        ],

        "limites_declarados": [
            ("Hasta %s el dial lo calcula el BACKTESTER (entrada 10:30 ET); a "
             "partir de ahi, el LIVE (12:30 ET). Medido sobre el 2026-08-20, que "
             "existe por las dos vias: 1,93%% de diferencia en el raw = 4,17 "
             "puntos de percentil, el 34%% del ancho de una banda de estado."
             % frontera),
            ("'IS/OOS' aqui NO significa lo habitual. La formula no tiene "
             "parametros ajustados, asi que el VALOR de un dia no es ni dentro "
             "ni fuera de muestra. Lo que si se eligio mirando 2019-2026 es la "
             "AFIRMACION de que el dial predice el PnL (r_day +0,406, LOYO 6/7), "
             "y esa solo podra juzgarse cuando los dias nuevos tengan su PnL a "
             "W50, unos 250 dias despues. La linea del grafico separa "
             "PROCEDENCIA del dato, no muestra estadistica."),
            ("Interpolar un dia perdido con la media de sus vecinos NO vale: "
             "probado sobre los 1.889 dias de la serie, el error mediano del raw "
             "es 1,39%% (p90 4,61%%) y el 7,1%% de los dias CAMBIARIA de estado. "
             "Recalcularlo con el ADHOC da el valor exacto en ~55 s."),
            ("El dial es un FRENO: sus dos deciles mas bajos pierden dinero "
             "(PF 0,77 y 1,16, acierto 52%). Su valor esta en senalar los dias "
             "de NO operar."),
            ("Las cifras de elite estan dominadas por 2020: la interseccion de "
             "elite alta con dial alto es 83,2% de 2020 y 15,5% de 2021, con "
             "cero operaciones en 2022 y 2023."),
            ("r(dial, VIX) = -0,27 supera el umbral 0,20 del protocolo interno. "
             "Eliminatorio como SORT; se admite como GATE declarado, que es su "
             "uso. Su partial controlando VIX (+0,385) es MAYOR que su r crudo, "
             "asi que hay senal propia."),
        ],

        "recuento_actual": {
            "dias_backtest": n_backtest,
            "dias_en_vivo": n_vivo,
            "frontera": frontera,
        },
    }
