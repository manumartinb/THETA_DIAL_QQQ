# THETA_DIAL — QQQ Batman LT

Reloj de **régimen diario** para Batman QQQ Long Term.

## Qué mide

Media de medias por celda (DTE1 × DTE2) de `theta_k2 / spot`, expresada como
**percentil expandido solo-pasado** contra su propia historia.

Describe el **día**, no el candidato: todos los trades de una jornada comparten
valor. Cortes de estado: `BAJO < 12,3 ≤ MEDIO < 38,8 ≤ ALTO`.

**Nativo de QQQ.** Se calcula con datos del propio subyacente; ningún feed de
SPX interviene.

## Por qué estratificado por celda

`theta_k2/spot` correlaciona +0,475 con DTE1 y +0,560 con DTE2. Una media simple
dependería de la mezcla de vencimientos de la población, y el LIVE no emite la
misma mezcla que el backtester — el percentil habría salido sesgado de forma
sistemática. Promediando por celda, cada celda pesa igual y el estadístico deja
de depender de cuántos candidatos caen en cada una.

## Cómo leerlo

Es sobre todo un **freno**, no un acelerador. Los dos deciles más bajos pierden
dinero (PF 0,77 y 1,16, acierto 52%). Lo más fiable que hace es señalar los días
en los que no operar.

Ver la página para los cuatro avisos completos, incluido el más importante: las
cifras de la cohorte élite están dominadas por 2020.

## Estructura

| fichero | qué hace |
|---|---|
| `index.html` | el panel (autocontenido salvo Plotly desde CDN) |
| `data/theta_dial_data.json` | serie + tablas del estudio |
| `update_dashboard.py` | regenera el JSON entero. Manual, tras cambios en la madre |
| `daily_refresh.py` | añade el día nuevo desde la entrega del LIVE + push. Lo llama el Master Daily |

## Frescura

El punto más nuevo lleva **un día de retraso**: el Master Daily corre antes que
el LIVE de las 18:30, así que publica el dial del día anterior. El chip de
antigüedad de la cabecera lo dice siempre.

Se probó recalcular el dial del día desde los parquets para evitar ese retraso.
Sale con 1,55% de error, que en percentil son ~5 puntos y hace que el 7,7% de
los días cambien de estado. La causa es estructural: el dial histórico se
calcula sobre los candidatos que sobrevivieron al filtro forward, y para hoy ese
filtro no puede aplicarse. Por eso se lee de la entrega, que es el único sitio
donde está el mismo número que ve el usuario en la app.

## Trazabilidad

- Estudio: `Batman/QQQ/ANALISIS/THETA_DIAL_QQQ_STUDY/`
- @APR: `memory/analisis_predictabilidad_robustez_theta_dial_qqq_20260819.md`
- Serie: `BATMAN_QQQ_GEN3_V42_BACKTEST_OUTPUT_FILES/GEN3_THETA_DIAL_SERIE_QQQ.csv`
