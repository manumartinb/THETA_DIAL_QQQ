# -*- coding: ascii -*-
r"""Pinta la particion IS / OOS en el dashboard THETA_DIAL_QQQ.

POR QUE
-------
La serie tiene una frontera natural y limpia. A la izquierda del 2026-04-10 esta
el backtest, que es donde se calibro TODO lo que la pagina afirma. A la derecha,
los dias que va emitiendo el LIVE, que nadie ha visto antes. Y en medio, un
hueco de 131 dias sin dato: ni backtest (el gate forward no llega) ni entrega
(el LIVE no existia).

Ese hueco parecia un defecto y es lo contrario: separa **sin solape ni zona
gris**. Es la mejor frontera IS/OOS que se puede pedir, y hasta ahora la pagina
la dibujaba como una linea continua, que es justo lo que no es.

LO QUE ESTE GRAFICO **NO** HACE, Y HAY QUE DECIRLO
--------------------------------------------------
El contador de dias OOS **no es una barra de progreso hacia un veredicto**. Los
dias OOS acumulan LECTURAS del dial, no aciertos: para saber si un dia acerto
hace falta su PnL a W50, y ese no existe hasta ~250 dias despues. Por eso se
publica la FECHA del primer veredicto posible, en vez de un porcentaje que
insinuaria que el tramo ya dice algo. Insinuarlo seria exactamente el tipo de
cosa que las auditorias de esta semana llevan cazando.

NOTA DE OFICIO (rota dos veces ya, 2026-08-19 y 2026-08-21)
-----------------------------------------------------------
`open(path, "w")` TRUNCA el fichero antes de codificar. Si la codificacion
falla, te quedas con 0 bytes. Este mismo script se perdio asi. Se escribe a
temporal y se renombra, o se usa una herramienta que no trunque.

Patron de parche de la casa: anclas literales, assert count==1, backup previo.
"""
import io
import os
from pathlib import Path

DIR = Path(__file__).resolve().parent
IDX = DIR / "index.html"

I_, PM = "\u00ed", "\u00b7"          # i acentuada y punto medio, como escapes

raw = io.open(IDX, encoding="utf-8").read()
bak = DIR / "index.html.bak_pre_isoos_20260821"
if not bak.exists():
    io.open(bak, "w", encoding="utf-8").write(raw)
    print("backup -> %s" % bak.name)
assert 'id="particion"' not in raw, "la particion YA esta puesta"


def rep(old, new, tag):
    global raw
    n = raw.count(old)
    assert n == 1, "[%s] esperaba 1 ocurrencia, hay %d" % (tag, n)
    raw = raw.replace(old, new, 1)
    print("  OK  %s" % tag)


# ---- 1) el contenedor del chip, encima del grafico ----
rep('  <div class="pills" id="pills"></div>\n  <div id="chart"></div>',
    '  <div class="pills" id="pills"></div>\n'
    '  <div id="particion" style="margin:2px 0 12px"></div>\n'
    '  <div id="chart"></div>',
    "contenedor del chip")

# ---- 2) el grafico, partido en dos trazas ----
rep("""  const trazas=[
    {x, y:dat.map(r=>r.p), type:"scatter", mode:"lines", name:"THETA_DIAL (percentil)",
     line:{color:"#c4b5fd",width:1.8}, hovertemplate:"%{x}<br>dial %{y:.1f}<extra></extra>"},
  ];""",
"""  // La serie va PARTIDA en dos trazas a proposito. Pintarla continua daba a
  // entender que el tramo del LIVE es mas de lo mismo, y no lo es: a la
  // izquierda esta el backtest donde se calibro todo, a la derecha lo que
  // todavia no ha demostrado nada. Se separan con null en la frontera para que
  // Plotly no una los extremos con una recta que cruzaria el hueco entero.
  const esOOS = r => r.o === "OOS";
  const yIS  = dat.map(r => esOOS(r) ? null : r.p);
  const yOOS = dat.map(r => esOOS(r) ? r.p  : null);
  const hayOOS = dat.some(esOOS);
  const trazas=[
    {x, y:yIS, type:"scatter", mode:"lines", name:"IS \\u00b7 backtest",
     line:{color:"#c4b5fd",width:1.8}, connectgaps:false,
     hovertemplate:"%{x}<br>dial %{y:.1f}<br><i>dentro de muestra</i><extra></extra>"},
  ];
  if(hayOOS){
    trazas.push({x, y:yOOS, type:"scatter", mode:"lines+markers", name:"OOS \\u00b7 LIVE",
      line:{color:"#2bd48a",width:2.4}, marker:{size:6,color:"#2bd48a"}, connectgaps:false,
      hovertemplate:"%{x}<br>dial %{y:.1f}<br><i>fuera de muestra</i><extra></extra>"});
  }""",
    "grafico partido IS/OOS")

# ---- 3) la banda gris del hueco ----
rep("""    shapes:[
      {type:"rect",xref:"paper",x0:0,x1:1,yref:"y",y0:0,y1:B,fillcolor:"rgba(255,115,105,.09)",line:{width:0},layer:"below"},""",
"""    shapes:[
      // el hueco sin dato: sombreado y etiquetado, porque es la FRONTERA y no un fallo
      ...((D.particion && D.particion.hueco) ? [{
        type:"rect", xref:"x", yref:"paper",
        x0:D.particion.hueco[0], x1:D.particion.hueco[1], y0:0, y1:1,
        fillcolor:"rgba(95,104,119,.30)", line:{width:0}, layer:"below"
      }] : []),
      {type:"rect",xref:"paper",x0:0,x1:1,yref:"y",y0:0,y1:B,fillcolor:"rgba(255,115,105,.09)",line:{width:0},layer:"below"},""",
    "banda del hueco")

# ---- 4) la anotacion (ancla unica: el rect de la zona ALTA) ----
rep("""      {type:"rect",xref:"paper",x0:0,x1:1,yref:"y",y0:A,y1:100,fillcolor:"rgba(43,212,138,.08)",line:{width:0},layer:"below"}
    ]
  }, {displayModeBar:false,responsive:true});
}""",
"""      {type:"rect",xref:"paper",x0:0,x1:1,yref:"y",y0:A,y1:100,fillcolor:"rgba(43,212,138,.08)",line:{width:0},layer:"below"}
    ],
    annotations: ((D.particion && D.particion.hueco && VENTANA==="all") ? [{
      xref:"x", yref:"paper", x:D.particion.hueco[0], y:1.02,
      xanchor:"left", showarrow:false,
      text:"sin dato ("+D.particion.hueco_dias+"d)",
      font:{size:10, color:"#9aa3b2"}
    }] : [])
  }, {displayModeBar:false,responsive:true});
}""",
    "anotacion del hueco")

# ---- 5) la funcion del chip ----
CHIP = ("""// El chip de la particion. Deliberadamente SIN barra de progreso: los dias OOS
// acumulan LECTURAS del dial, no veredictos, y una barra insinuaria que el tramo
// ya dice algo. Para saber si un dia acerto hace falta su PnL a W50, que tarda
// ~250 dias en existir; por eso se publica la fecha del primer veredicto
// posible en vez de un porcentaje.
function pintarParticion(){
  const P=D.particion, el=document.getElementById("particion");
  if(!P || !el) return;
  const caja=(t,v,c)=>'<span style="display:inline-block;padding:3px 9px;margin-right:7px;'+
    'border:1px solid #232a36;border-radius:4px;background:#11151c;font-size:11.5px">'+
    '<span style="color:#5f6877">'+t+'</span> <b style="color:'+c+'">'+v+'</b></span>';
  let h = caja("IS (backtest)", P.n_is+" d@Ias @PM hasta "+P.frontera, "#c4b5fd");
  if(P.hueco) h += caja("sin dato", P.hueco_dias+" d@Ias", "#5f6877");
  h += caja("OOS (LIVE)", P.n_oos+" d@Ia"+(P.n_oos===1?"":"s"),
            P.n_oos>0 ? "#2bd48a" : "#5f6877");
  if(P.evaluable){
    h += '<div style="margin-top:7px;color:#5f6877;font-size:11px;line-height:1.55">'+
         P.nota+' Primer veredicto posible: <b style="color:#9aa3b2">'+P.evaluable+
         '</b>.</div>';
  }
  el.innerHTML = h;
}

""").replace("@I", I_).replace("@PM", PM)

rep("""// ---------------------------------------------------------------- graficos
// Anadidos el 2026-08-20.""",
    CHIP + """// ---------------------------------------------------------------- graficos
// Anadidos el 2026-08-20.""",
    "funcion pintarParticion")

# ---- 6) llamarla ----
rep("pintarTablas(); pintarDeciles();",
    "pintarTablas(); pintarParticion(); pintarDeciles();",
    "llamada a pintarParticion")

# escritura SEGURA: temporal + rename. Ver la nota de oficio de la cabecera.
tmp = IDX.with_suffix(".html.tmp%d" % os.getpid())
io.open(tmp, "w", encoding="utf-8").write(raw)
os.replace(tmp, IDX)
print("\nescrito index.html (%.1f KB)" % (IDX.stat().st_size / 1024))
for t in ('id="particion"', "pintarParticion", "yOOS", "D.particion"):
    print("   %-20s %d" % (t, raw.count(t)))
