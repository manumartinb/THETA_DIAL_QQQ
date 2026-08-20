# -*- coding: ascii -*-
r"""Anade cuatro graficos al dashboard THETA_DIAL_QQQ.

La pagina tenia UN grafico (la serie) y cuatro TABLAS. Las tablas son exactas
pero no se leen de un vistazo, y este dashboard existe justo para eso: para que
alguien mire diez segundos y sepa si hoy conviene operar.

LOS CUATRO, Y POR QUE CADA UNO

  1. DECILES        barras de mediana + PF en log. Lo que la tabla dice en 10
                    filas -- que D1 y D2 pierden -- aqui se ve en un golpe.
  2. CORTES         el canje real de apretar el dial: PF sube, dias caen. Es el
                    unico grafico de la pagina con DOS ejes a proposito, porque
                    el coste de este indicador esta en el eje que nadie mira.
  3. COBERTURA      barras apiladas BAJO/MEDIO/ALTO por anio. Es la prueba
                    visual del aviso 2: 2022 casi todo BAJO, 2023 sin un solo
                    ALTO. Un reparto asi no es un dial "equilibrado".
  4. CONCENTRACION  NUEVO, sale de la @AuditoriaLogica del 2026-08-20. De que
                    anos esta hecha la cohorte de elite. El PF de 2.108 que el
                    aviso 3 menciona es 98% de 2020, y hasta ahora eso solo
                    estaba escrito en prosa. Ahora se ve.

Todo se pinta con los datos que YA viaja en theta_dial_data.json salvo el (4),
que necesita dos campos nuevos -- se anaden en update_dashboard.py.

Patron de parche de la casa: anclas literales, assert count==1, backup previo.
"""
import io
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent
IDX = DIR / "index.html"

raw = io.open(IDX, encoding="utf-8").read()
bak = DIR / "index.html.bak_pre_graficos_20260820"
if not bak.exists():
    io.open(bak, "w", encoding="utf-8").write(raw)
    print("backup -> %s" % bak.name)
assert "g-dec" not in raw, "los graficos YA estan puestos"


def rep(old, new, tag):
    global raw
    n = raw.count(old)
    assert n == 1, "[%s] esperaba 1 ocurrencia, hay %d" % (tag, n)
    raw = raw.replace(old, new, 1)
    print("  OK  %s" % tag)


# ---- 1. los contenedores, cada uno ENCIMA de su tabla ----
rep('  <div class="tw"><table id="t-dec"></table></div>',
    '  <div id="g-dec" style="margin-bottom:10px"></div>\n'
    '  <div class="tw"><table id="t-dec"></table></div>',
    "contenedor deciles")

rep('  <div class="tw"><table id="t-est"></table></div>\n'
    '  <div class="tw"><table id="t-cor"></table></div>',
    '  <div class="tw"><table id="t-est"></table></div>\n'
    '  <div id="g-cor" style="margin:14px 0 10px"></div>\n'
    '  <div class="tw"><table id="t-cor"></table></div>',
    "contenedor cortes")

rep('  <div class="tw"><table id="t-cob"></table></div>',
    '  <div id="g-cob" style="margin-bottom:10px"></div>\n'
    '  <div class="tw"><table id="t-cob"></table></div>\n'
    '  <div id="g-con" style="margin-top:26px"></div>\n'
    '  <p class="sub" id="con-sub" style="margin-top:6px"></p>',
    "contenedor cobertura + concentracion")

# ---- 2. el JS ----
JS = r"""
// ---------------------------------------------------------------- graficos
// Anadidos el 2026-08-20. La pagina tenia solo la serie; las tablas eran
// exactas pero no se leen de un vistazo, y este dashboard existe para eso.
const LAY = {                      // el layout comun, para no repetirlo 4 veces
  paper_bgcolor:"#11151c", plot_bgcolor:"#11151c",
  font:{color:"#9aa3b2",family:"Cascadia Code,Consolas,monospace",size:11},
  margin:{l:52,r:52,t:26,b:42}, showlegend:false,
  xaxis:{gridcolor:"#232a36",zeroline:false},
  yaxis:{gridcolor:"#232a36",zeroline:false}
};
const CFG = {displayModeBar:false,responsive:true};
const OK="#2bd48a", MAL="#ff7369", AVI="#eda100", LILA="#c4b5fd", GRIS="#5f6877";
function L(extra){ return Object.assign(JSON.parse(JSON.stringify(LAY)), extra||{}); }

function pintarDeciles(){
  const d=D.deciles||[]; if(!d.length) return;
  const x=d.map((_,i)=>"D"+(i+1));
  // el color ES la lectura: rojo el decil que pierde, no por estetica
  Plotly.newPlot("g-dec",[
    {x, y:d.map(r=>r.mediana), type:"bar", name:"mediana",
     marker:{color:d.map(r=>r.mediana<=1?MAL:OK)},
     hovertemplate:"%{x}<br>mediana %{y:.2f} pts<extra></extra>"},
    {x, y:d.map(r=>r.PF), type:"scatter", mode:"lines+markers", name:"PF", yaxis:"y2",
     line:{color:LILA,width:1.6}, marker:{size:5},
     hovertemplate:"%{x}<br>PF %{y:.2f}<extra></extra>"}
  ], L({
    showlegend:true, legend:{orientation:"h",y:1.16,x:0,font:{size:10.5}},
    yaxis:{title:"mediana (pts)",gridcolor:"#232a36",zeroline:true,zerolinecolor:"#3a4453"},
    yaxis2:{title:"PF (log)",overlaying:"y",side:"right",type:"log",showgrid:false},
    shapes:[{type:"line",xref:"paper",x0:0,x1:1,yref:"y2",y0:1,y1:1,
             line:{color:MAL,width:1,dash:"dot"}}]
  }), CFG);
}

function pintarCortes(){
  const c=(D.cortes||[]).slice(); if(!c.length) return;
  const x=c.map(r=>r.corte.replace(/\s+\(pctl.*\)/,"").trim());
  // dos ejes A PROPOSITO: el coste de este indicador esta en los dias, que es
  // justo el eje que nadie mira cuando ve un PF de tres cifras.
  Plotly.newPlot("g-cor",[
    {x, y:c.map(r=>r.Ndias), type:"bar", name:"dias que quedan",
     marker:{color:GRIS}, hovertemplate:"%{x}<br>%{y} dias<extra></extra>"},
    {x, y:c.map(r=>r.PF), type:"scatter", mode:"lines+markers", name:"PF", yaxis:"y2",
     line:{color:OK,width:1.8}, marker:{size:6},
     hovertemplate:"%{x}<br>PF %{y:.1f}<extra></extra>"}
  ], L({
    showlegend:true, legend:{orientation:"h",y:1.16,x:0,font:{size:10.5}},
    yaxis:{title:"dias",gridcolor:"#232a36"},
    yaxis2:{title:"PF (log)",overlaying:"y",side:"right",type:"log",showgrid:false}
  }), CFG);
}

function pintarCobertura(){
  const c=(D.cobertura||[]).filter(r=>r["BAJO_%"]!==null); if(!c.length) return;
  const x=c.map(r=>r.anio);
  Plotly.newPlot("g-cob",[
    {x, y:c.map(r=>r["BAJO_%"]),  type:"bar", name:"BAJO",  marker:{color:MAL}},
    {x, y:c.map(r=>r["MEDIO_%"]), type:"bar", name:"MEDIO", marker:{color:AVI}},
    {x, y:c.map(r=>r["ALTO_%"]),  type:"bar", name:"ALTO",  marker:{color:OK}}
  ], L({
    barmode:"stack", showlegend:true,
    legend:{orientation:"h",y:1.16,x:0,font:{size:10.5}},
    yaxis:{title:"% de los dias del anio",range:[0,100],gridcolor:"#232a36"}
  }), CFG);
}

function pintarConcentracion(){
  const c=D.concentracion;
  const g=document.getElementById("g-con"), s=document.getElementById("con-sub");
  if(!c || !c.por_anio || !c.por_anio.length){ if(g) g.style.display="none"; return; }
  const x=c.por_anio.map(r=>r.anio);
  Plotly.newPlot("g-con",[
    {x, y:c.por_anio.map(r=>r.cuota_elite), type:"bar", name:"elite",
     marker:{color:GRIS}, hovertemplate:"%{x}<br>%{y:.1f}% de la elite<extra></extra>"},
    {x, y:c.por_anio.map(r=>r.cuota_dial), type:"bar", name:"elite + dial alto",
     marker:{color:LILA}, hovertemplate:"%{x}<br>%{y:.1f}% de la cohorte<extra></extra>"}
  ], L({
    barmode:"group", showlegend:true,
    legend:{orientation:"h",y:1.16,x:0,font:{size:10.5}},
    yaxis:{title:"% de la cohorte",gridcolor:"#232a36"}
  }), CFG);
  if(s) s.innerHTML = c.nota || "";
}
"""

rep("function pintarTablas(){", JS.strip() + "\n\nfunction pintarTablas(){",
    "funciones de los graficos")

# ---- 3. llamarlas donde ya se llama a pintarTablas ----
n = raw.count("pintarTablas();")
assert n >= 1, "no encuentro la llamada a pintarTablas()"
raw = raw.replace("pintarTablas();",
                  "pintarTablas(); pintarDeciles(); pintarCortes(); "
                  "pintarCobertura(); pintarConcentracion();", 1)
print("  OK  llamadas (%d ocurrencia(s) de pintarTablas, parcheada la 1a)" % n)

# ---- 4. titulos de seccion que ahora llevan grafico ----
rep("<h2><span>##</span> Cobertura por a\u00f1o</h2>",
    "<h2><span>##</span> Cobertura y concentraci\u00f3n</h2>",
    "titulo de la seccion")

io.open(IDX, "w", encoding="utf-8").write(raw)
print("\nescrito index.html (%.1f KB)" % (IDX.stat().st_size / 1024))
for tag in ("g-dec", "g-cor", "g-cob", "g-con", "pintarDeciles", "pintarCortes",
            "pintarCobertura", "pintarConcentracion"):
    print("   %-20s %d" % (tag, raw.count(tag)))
