#!/usr/bin/env python3
"""
KAVACH dashboard mockup generator.
Builds a large, readable BI-style control-room board as one SVG from the real
engine data in dash.json, so the visual can be rendered (cairosvg) and judged
as an image, then iterated. Hand-built — every coordinate is intentional.
"""
import json, os, math, html

D = json.load(open(os.path.join(os.path.dirname(__file__) or ".", "dash.json")))

# ---- palette (dark-navy BI + cyan) -----------------------------------------
BG="#0f1830"; CARD="#1c2b4d"; CARD2="#17233f"; LINE="#2c3a63"; LINE2="#3a4a78"
INK="#eef2f8"; DIM="#9aa6c0"; FAINT="#6f7a99"
CYAN="#29b6f6"; CYAN2="#7fd3f7"; ORANGE="#f5921f"; PURPLE="#c264d6"; TEAL="#4dd0e1"
OK="#35c47a"; AMBER="#f2b134"; RED="#ef4b58"
MONO="'DejaVu Sans Mono','Consolas',monospace"
SANS="'Segoe UI','DejaVu Sans','Helvetica Neue',Arial,sans-serif"

W,H = 1680,1236
S=[]  # svg fragments
def add(x): S.append(x)
def esc(t): return html.escape(str(t))
def wrap(text,maxchars):
    words=text.split(); lines=[""]
    for w in words:
        if lines[-1] and len(lines[-1])+1+len(w)>maxchars: lines.append("")
        lines[-1]+=((" " if lines[-1] else "")+w)
    return lines
def fit(text,w,cpp=6.4):
    mc=int((w-40)/cpp)
    return text if len(text)<=mc else text[:mc-1]+"…"

def rect(x,y,w,h,fill,rx=0,stroke=None,sw=1,op=1,dash=None):
    s=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" opacity="{op}"'
    if stroke: s+=f' stroke="{stroke}" stroke-width="{sw}"'
    if dash: s+=f' stroke-dasharray="{dash}"'
    return s+'/>'
def txt(x,y,t,size=14,fill=INK,w=400,anchor="start",font=SANS,ls=0,op=1):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{w}" '
            f'text-anchor="{anchor}" font-family="{font}" letter-spacing="{ls}" opacity="{op}">{esc(t)}</text>')
def line(x1,y1,x2,y2,stroke=LINE,sw=1,dash=None,op=1,cap="butt"):
    s=f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}" stroke-linecap="{cap}"'
    if dash: s+=f' stroke-dasharray="{dash}"'
    return s+'/>'
def poly(points,stroke,sw=2,fill="none",op=1,dash=None):
    p=" ".join(f"{x:.1f},{y:.1f}" for x,y in points)
    s=f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}" stroke-linejoin="round" stroke-linecap="round"'
    if dash: s+=f' stroke-dasharray="{dash}"'
    return s+'/>'
def circle(cx,cy,r,fill,stroke=None,sw=1,op=1):
    s=f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{op}"'
    if stroke: s+=f' stroke="{stroke}" stroke-width="{sw}"'
    return s+'/>'

def info_glyph(x,y):
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="none" stroke="{FAINT}" stroke-width="1.3"/>'
            f'<text x="{x}" y="{y+4.5}" font-size="12" fill="{DIM}" text-anchor="middle" '
            f'font-family="{SANS}" font-style="italic" font-weight="700">i</text>')

def card(x,y,w,h,title,caption,info=True):
    add(rect(x,y,w,h,CARD,rx=6,stroke=LINE,sw=1))
    add(rect(x,y,w,3,CYAN,rx=0,op=0.0))  # (reserved accent)
    add(txt(x+18,y+30,title,18,"#d6dcea",500))
    if info: add(info_glyph(x+w-22,y+22))
    if caption: add(txt(x+18,y+50,fit(caption,w),12.5,DIM,400))
    return (x+18,y+ (66 if caption else 48))  # content origin

# ============================================================ background
add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
# faint grid
add('<defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">'
    f'<path d="M40 0 H0 V40" fill="none" stroke="rgba(140,160,200,0.05)" stroke-width="1"/></pattern>'
    f'<radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="{RED}" stop-opacity="0.5"/>'
    f'<stop offset="100%" stop-color="{RED}" stop-opacity="0"/></radialGradient></defs>')
add(f'<rect width="{W}" height="{H}" fill="url(#g)"/>')

# ============================================================ header
add(rect(24,24,W-48,70,CARD,rx=6,stroke=LINE))
# shield mark
add(f'<g transform="translate(40,34)"><path d="M22 2 L38 8 V22 C38 33 31 40 22 44 C13 40 6 33 6 22 V8 Z" '
    f'fill="#0e1826" stroke="{CYAN}" stroke-width="2"/>'
    f'<path d="M13 23 h5 l3 7 l4 -13 l3 6 h5" fill="none" stroke="{CYAN2}" stroke-width="2.4" '
    f'stroke-linecap="round" stroke-linejoin="round"/></g>')
add(txt(96,52,"KAVACH",26,INK,800,ls=3))
add(txt(96,74,"Industrial Safety Intelligence · Compound-Risk Control Room",12.5,DIM,400,ls=0.4))
add(txt(560,50,"Gas Release Incident Replay — Coke Oven Battery 4",15,INK,600))
add(txt(560,72,"Synthetic composite · inspired by publicly reported coke-oven gas incidents",11.5,FAINT,400))
# right cluster
add(rect(W-350,45,158,30,"#3a1420",rx=15,stroke=RED,sw=1.2))
add(circle(W-332,60,5,RED)); add(txt(W-318,64,"RISK: CRITICAL",12.5,"#ff9aa0",700,ls=0.4))
add(txt(W-40,52,"06:30",30,INK,700,anchor="end",font=MONO))
add(txt(W-40,72,"SIM CLOCK · SHIFT A",10.5,FAINT,600,anchor="end",ls=1.2))

# ============================================================ instruction strip
iy=102
add(rect(24,iy,W-48,70,CARD2,rx=6,stroke=LINE))
add(txt(40,iy+27,"HOW TO READ THIS BOARD",11,CYAN2,700,ls=1.6))
guide=("A plant where every alarm worked — yet a compound hazard went unseen. "
       "Follow the story left→right: the RISK chart shows KAVACH flagging danger 3h before any single alarm; "
       "the SCHEMATIC shows where and why; the SAFETY LAYERS show which barriers were already breached.")
# wrap guide into 2 lines on word boundaries
gl=wrap(guide,150)
add(txt(40,iy+48,gl[0],13,INK,400))
if len(gl)>1: add(txt(40,iy+64,gl[1],13,INK,400))
# mini legend at right
lx=W-470
add(txt(lx,iy+27,"LEGEND",11,FAINT,700,ls=1.6))
leg=[("KAVACH compound risk",CYAN),("Single-sensor baseline",ORANGE),("Incident",RED),("Barrier breached",AMBER)]
for i,(lb,c) in enumerate(leg):
    yy=iy+44+ (i//2)*18; xx=lx+(i%2)*230
    add(rect(xx,yy-9,11,11,c,rx=2)); add(txt(xx+18,yy,lb,11.5,DIM,400))

# ============================================================ helpers for charts
def axis_box(x,y,w,h):
    add(rect(x,y,w,h,CARD2,rx=4,stroke=LINE,op=0.55))

# ============================================================ ROW 1 : RISK vs BASELINE (money chart)
rc_x,rc_y,rc_w,rc_h = 24,184,996,430
cx,cy = card(rc_x,rc_y,rc_w,rc_h,"Compound Risk  vs  Single-Sensor Baseline",
             "KAVACH crosses ALERT at 06:30 · a conventional alarm only trips at 09:39 — 3h 09m later.")
# plot area
px,py,pw,ph = rc_x+70, rc_y+92, rc_w-110, rc_h-170
axis_box(px,py,pw,ph)
dur=D["duration"]; T=D["T"]
def X(t): return px + (t/dur)*pw
def Yv(v,vmax=105): return py+ph - (v/vmax)*ph
# gridlines y (0,20,40,60,80,100)
for gv in (0,20,40,60,80,100):
    yy=Yv(gv); add(line(px,yy,px+pw,yy,LINE,1,op=0.5))
    add(txt(px-10,yy+4,f"{gv}",11,FAINT,400,anchor="end",font=MONO))
add(txt(px-46,py+ph/2,"RISK  (0–100)",11,FAINT,600,anchor="middle")+ "")
# threshold lines (labels on the left, clear of the right-side markers)
add(line(px,Yv(60),px+pw,Yv(60),CYAN,1.4,dash="6 4",op=0.7))
add(txt(px+10,Yv(60)-7,"KAVACH ALERT  ≥ 60",11,CYAN2,700,anchor="start"))
add(line(px,Yv(100),px+pw,Yv(100),ORANGE,1.4,dash="6 4",op=0.7))
add(txt(px+10,Yv(100)-7,"BASELINE ALARM  = 100%",11,"#f7b06a",700,anchor="start"))
# baseline single-sensor curve = max(value/alarm)*100
lim=D["limits"]; ser=D["series"]
def bl_pct(i):
    vals=[]
    for s in ("GD-CO4-203","GD-CO4-204","PT-GM-104","DP-CO4-801"):
        al=(lim.get(s) or {}).get("alarm")
        if al: vals.append(ser[s][i]/al*100)
    return min(140,max(vals))
bpts=[(X(T[i]),Yv(bl_pct(i))) for i in range(len(T))]
add(poly(bpts,ORANGE,2.4))
# kavach compound risk curve (cob4_basement)
kr=D["risk_ts"]["cob4_basement"]
kpts=[(X(T[i]),Yv(kr[i])) for i in range(len(T))]
# shaded area under the KAVACH risk curve
apts=" ".join(f"{x:.1f},{y:.1f}" for x,y in kpts)
add(f'<polygon points="{X(0):.1f},{py+ph:.1f} {apts} {X(dur):.1f},{py+ph:.1f}" fill="{CYAN}" opacity="0.10"/>')
add(poly(kpts,CYAN,3))
# event markers
def vmark(t,label,clock,color,side="l"):
    xx=X(t)
    add(line(xx,py,xx,py+ph,color,1.4,dash="2 3",op=0.8))
    add(circle(xx,py-2,4,color))
    anch = "start" if side=="l" else "end"
    ox = 7 if side=="l" else -7
    add(txt(xx+ox,py+16,label,11.5,color,700,anchor=anch))
    add(txt(xx+ox,py+31,clock,11,DIM,400,anchor=anch,font=MONO))
vmark(270,"KAVACH detects","06:30",CYAN2,"l")
vmark(459,"1st single alarm","09:39",ORANGE,"r")
vmark(510,"INCIDENT","10:30",RED,"l")
# lead-time span annotation
ax1,ax2=X(270),X(459); ay=py+ph+22
add(line(ax1,ay,ax2,ay,CYAN2,1.6))
add(line(ax1,ay-5,ax1,ay+5,CYAN2,1.6)); add(line(ax2,ay-5,ax2,ay+5,CYAN2,1.6))
add(txt((ax1+ax2)/2,ay+18,"◀  3h 09m of prediction lead time  ▶",13,CYAN2,700,anchor="middle"))
# x axis labels (clock ticks)
for t,lb in [(0,"02:00"),(120,"04:00"),(240,"06:00"),(360,"08:00"),(480,"10:00"),(600,"12:00")]:
    xx=X(t); add(line(xx,py+ph,xx,py+ph+4,FAINT,1))
    add(txt(xx,py+ph+ (55),lb,11,FAINT,400,anchor="middle",font=MONO))

# ============================================================ ROW 1 right : SCHEMATIC
sc_x,sc_y,sc_w,sc_h = 1032,184,624,430
cx,cy=card(sc_x,sc_y,sc_w,sc_h,"Plant Schematic — Live Compound Risk",
           "Zones shaded by KAVACH risk. The hazard is where a breach meets people.")
# ---- clean, purpose-drawn gas-network schematic (no spaghetti) ----
def srgb(s):
    stops=[(0,(34,52,74)),(30,(53,196,122)),(45,(242,177,52)),(62,(245,146,31)),(82,(239,75,88)),(100,(214,60,72))]
    s=max(0,min(100,s))
    for i in range(1,len(stops)):
        x1,c1=stops[i-1]; x2,c2=stops[i]
        if s<=x2:
            p=(s-x1)/((x2-x1) or 1)
            return tuple(round(c1[k]+(c2[k]-c1[k])*p) for k in range(3))
    return stops[-1][1]
def zbox(x,y,w,h,label,score,tag=None):
    c=srgb(score); fill=f"rgba({c[0]},{c[1]},{c[2]},{0.08+score/100*0.5:.2f})"
    strk=f"rgba({c[0]},{c[1]},{c[2]},{0.75 if score>6 else 0.32:.2f})"
    if score>=80:
        add(f'<rect x="{x-9}" y="{y-9}" width="{w+18}" height="{h+18}" rx="12" fill="url(#halo)"/>')
    add(rect(x,y,w,h,fill,rx=6,stroke=strk,sw=2 if score>6 else 1.4))
    add(txt(x+12,y+(22 if tag else h/2+5),label,13.5,INK,600))
    if tag: add(txt(x+12,y+39,tag,10.5,("#ffb3b7" if score>=80 else DIM),400))
    if score>=1:
        add(txt(x+w-10,y+h-9,str(round(score)),18,f"rgb{srgb(score)}".replace(" ",""),800,anchor="end",font=MONO))
def arrow(x,y,d="r",col="rgba(150,175,215,0.55)"):
    if d=="r": p=f"{x},{y-4} {x+7},{y} {x},{y+4}"
    elif d=="l": p=f"{x},{y-4} {x-7},{y} {x},{y+4}"
    else: p=f"{x-4},{y} {x},{y+7} {x+4},{y}"
    add(f'<polygon points="{p}" fill="{col}"/>')
# gas-main spine (vertical) with flow
spx,spw,spy0,spy1=1336,24,272,556
add(rect(spx,spy0,spw,spy1-spy0,CARD2,rx=8,stroke=LINE2,sw=1.5))
add(f'<text x="{spx+spw/2}" y="{(spy0+spy1)/2}" transform="rotate(-90 {spx+spw/2} {(spy0+spy1)/2})" '
    f'font-size="11.5" fill="{DIM}" text-anchor="middle" font-family="{SANS}" letter-spacing="3" font-weight="700">GAS MAIN</text>')
add(rect(spx,492,spw,48,"rgba(239,75,88,0.45)",rx=4))   # riser-tap hazard segment
# left process units
LX,LW=1064,152
zbox(LX,278,LW,44,"Battery 3",4)
zbox(LX,340,LW,44,"Battery 4",8)
zbox(LX,404,LW,30,"Platform P2",6)
zbox(1056,470,216,74,"Battery 4 Basement",100,tag="confined space · 5 crew inside")
# right units (gas routed out to)
RX,RW=1472,166
zbox(RX,278,RW,44,"By-Products Plant",0)
zbox(RX,340,RW,44,"Gas Holder",0)
zbox(RX,404,RW,40,"Blast Furnace",0)
zbox(RX,470,RW,40,"Control Room",0)
# pipes: units -> main (flow in)
for yy in (300,362,419):
    add(line(LX+LW,yy,spx,yy,"rgba(150,175,215,0.4)",3)); arrow(spx-8,yy,"r")
# pipes: main -> right units (flow out)
for yy in (300,362,424):
    add(line(spx+spw,yy,RX,yy,"rgba(150,175,215,0.4)",3)); arrow(RX-2,yy,"r")
# vertical structural link Battery4 -> Platform -> Basement
add(line(LX+34,384,LX+34,404,"rgba(150,175,215,0.35)",2))
add(line(LX+34,434,LX+34,470,"rgba(150,175,215,0.35)",2))
# HAZARD branch: riser tap -> basement (red flow)
add(line(spx,516,1272,516,RED,4,dash="7 4")); arrow(1276,516,"l",RED)
add(txt(1304,486,"riser PT-GM-104 ▲ drift 8.60 kPa",10.5,"#ffb3b7",600,anchor="start"))
# crew inside basement
for i in range(5):
    add(circle(1074+i*15,528,4.2,"#ffd0d3",stroke=RED,sw=1))
# hazard note
add(rect(sc_x+18,sc_y+sc_h-46,sc_w-36,32,"#2a1420",rx=5,stroke="rgba(239,75,88,0.5)"))
add(circle(sc_x+34,sc_y+sc_h-30,5.5,RED))
add(txt(sc_x+48,sc_y+sc_h-26,fit("CRITICAL: crew in a confined space fed by a drifting gas main; isolation not applied — no single sensor in alarm.",sc_w-40,5.9),11.5,"#ffb3b7",500))

# ============================================================ KPI ribbon
ky=626
kpis=[("PREDICTION LEAD TIME","3h 09m",CYAN2,"KAVACH vs first alarm"),
 ("KAVACH DETECTS","06:30",INK,"compound alert, critical"),
 ("BASELINE ALARM","09:39",ORANGE,"single sensor crosses limit"),
 ("FALSE NEGATIVES","0",OK,"hazard windows missed"),
 ("FALSE POSITIVES","0",OK,"vs 1 for baseline (normal day)")]
kw=(W-48-4*12)/5
for i,(lb,val,col,sub) in enumerate(kpis):
    x=24+i*(kw+12)
    add(rect(x,ky,kw,96,CARD,rx=6,stroke=LINE))
    add(txt(x+16,ky+26,lb,10.5,FAINT,700,ls=1))
    add(txt(x+16,ky+64,val,34,col,700,font=MONO))
    add(txt(x+16,ky+84,sub,11,DIM,400))

# ============================================================ ROW 2 : SAFETY LAYERS
ly=734; lh=420
lx0=24; lw=530
cx,cy=card(lx0,ly,lw,lh,"Safety Layers — barrier status @ 06:30",
           "Plants have many barriers. Accidents happen when they fail one by one.")
barriers=[("Gas detection (sensors live)","INTACT",OK,"readings still sub-threshold"),
 ("Permit-to-work issued","INTACT",OK,"CSE-2093 confined-space entry"),
 ("Shift handover","BREACHED",AMBER,"overnight pressure drift not passed on · 06:00"),
 ("Pre-entry gas test","BREACHED",AMBER,"single-point only — chamber rear untested · 06:15"),
 ("Gas-main isolation / interlock","BREACHED",RED,"NOT applied for 'inspection-only' step · 06:30"),
 ("Hot-work separation","PENDING",FAINT,"breaches at 08:30 (welding 20 m from vent)"),
 ("Valve interlock","PENDING",FAINT,"breaches at 09:30 (V-707 throttled)")]
by=cy+6; rowh=(lh-(cy-ly)-58)/len(barriers)
for i,(nm,st,col,note) in enumerate(barriers):
    yy=by+i*rowh
    add(rect(lx0+18,yy,lw-36,rowh-8,CARD2,rx=4,stroke=LINE,op=0.7))
    add(circle(lx0+36,yy+(rowh-8)/2,7,col))
    add(txt(lx0+54,yy+21,nm,13.5,INK,600))
    add(txt(lx0+54,yy+38,note,11,DIM,400))
    add(rect(lx0+lw-116,yy+(rowh-8)/2-11,86,22,("none"),rx=11,stroke=col,sw=1.3))
    add(txt(lx0+lw-73,yy+(rowh-8)/2+4,st,11,col,700,anchor="middle",ls=0.5))
add(txt(lx0+18,ly+lh-14,"► 3 barriers already breached; no single alarm connects them. KAVACH does.",12,CYAN2,600))

# ============================================================ ROW 2 : EVIDENCE
ex0=566; ew=530
cx,cy=card(ex0,ly,ew,lh,"Why — Alert Evidence @ 06:30",
           "Every KAVACH alert carries its full reasoning. Judges probe; it answers.")
# alert header
add(rect(ex0+18,cy,ew-36,40,"rgba(239,75,88,0.10)",rx=5,stroke="rgba(239,75,88,0.4)"))
add(rect(ex0+18,cy,4,40,RED,rx=0))
add(rect(ex0+30,cy+10,72,20,RED,rx=4)); add(txt(ex0+66,cy+24,"CRITICAL",11,"#fff",800,anchor="middle"))
add(txt(ex0+114,cy+18,"Battery 4 Basement / Inspection Chamber",13,INK,600))
add(txt(ex0+114,cy+34,"score 100/100 · confidence 91%",11,DIM,400,font=MONO))
add(txt(ex0+ew-30,cy+24,"06:30",13,DIM,600,anchor="end",font=MONO))
# rules
rules=[("R1","Gas trend inside an occupied confined space (rising CO + gas-main drift on connected riser)"),
 ("R3","Confined entry without gas-main isolation while the connected network is abnormal"),
 ("R5","Entry cleared on a single-point gas test; same-zone trend now rising"),
 ("R4","Shift-changeover blindspot — unacknowledged drift on PT-GM-104")]
ry=cy+58; add(txt(ex0+18,ry,"REASONING · 4 RULES FUSED",10.5,FAINT,700,ls=1)); ry+=8
for rid,det in rules:
    ry+=8
    add(rect(ex0+18,ry,30,20,"rgba(41,182,246,0.14)",rx=4,stroke="rgba(41,182,246,0.3)"))
    add(txt(ex0+33,ry+14,rid,12,CYAN2,700,anchor="middle",font=MONO))
    # wrap detail to ~62 chars
    words=det.split(); lines=[""]
    for wd in words:
        if len(lines[-1])+len(wd)+1>60: lines.append("")
        lines[-1]+=(" "+wd if lines[-1] else wd)
    for j,ln in enumerate(lines):
        add(txt(ex0+58,ry+13+j*16,ln,12,DIM,400))
    ry+=max(24,len(lines)*16+6)
# signals + permit
ry+=2; add(txt(ex0+18,ry,"SIGNALS",10.5,FAINT,700,ls=1)); ry+=18
for lb in ["PT-GM-104  8.60 kPa · sub-threshold drift","GD-CO4-203  16.4 ppm ↑","CSE-2093  isolation: NOT applied"]:
    col = AMBER if "drift" in lb or "NOT" in lb else INK
    add(rect(ex0+18,ry-13,ew-36,22,CARD2,rx=4,stroke=LINE))
    add(txt(ex0+28,ry+2,lb,12,col,500,font=MONO)); ry+=28

# ============================================================ ROW 2 : INSTRUMENTS
tx0=1108; tw=548
cx,cy=card(tx0,ly,tw,lh,"Key Instruments — the drift was there",
           "Both stayed below their alarm line while KAVACH already warned.")
def trend(x,y,w,h,sid,name,unit):
    add(rect(x,y,w,h,CARD2,rx=4,stroke=LINE,op=0.6))
    vals=ser[sid]; al=(lim.get(sid) or {}).get("alarm"); wn=(lim.get(sid) or {}).get("warn")
    refs=[v for v in (wn,al) if v]
    lo=min(vals+refs); hi=max(vals+refs); sp=hi-lo or 1; lo-=sp*0.12; hi+=sp*0.12
    def PX(i): return x+40+ (i/(len(vals)-1))*(w-56)
    def PY(v): return y+h-16 - ((v-lo)/(hi-lo))*(h-32)
    if wn: add(line(x+40,PY(wn),x+w-16,PY(wn),AMBER,1,dash="3 3",op=0.55)); add(txt(x+w-18,PY(wn)-3,"warn",9.5,AMBER,400,anchor="end"))
    if al: add(line(x+40,PY(al),x+w-16,PY(al),ORANGE,1,dash="3 3",op=0.55)); add(txt(x+w-18,PY(al)-3,"alarm",9.5,"#f7b06a",400,anchor="end"))
    # cursor at t=270
    ci=min(range(len(T)),key=lambda i:abs(T[i]-270))
    add(line(PX(ci),y+10,PX(ci),y+h-14,CYAN2,1,op=0.6,dash="2 2"))
    pts=[(PX(i),PY(vals[i])) for i in range(len(vals))]
    add(poly(pts[:ci+1],CYAN,2.4)); add(poly(pts[ci:],CYAN,2,op=0.4))
    add(circle(PX(ci),PY(vals[ci]),3.4,CYAN2,stroke=BG,sw=1.2))
    add(txt(x+12,y+20,name,12,DIM,600))
    add(txt(x+w-16,y+20,f"{vals[ci]} {unit}",13,INK,700,anchor="end",font=MONO))
    add(txt(PX(ci)+6,y+h-4,"06:30",9.5,CYAN2,600,font=MONO))
th=(lh-(cy-ly)-24)/2
trend(tx0+18,cy+4,tw-36,th-10,"PT-GM-104","PT-GM-104 · Battery-4 riser pressure","kPa")
trend(tx0+18,cy+4+th,tw-36,th-10,"GD-CO4-203","GD-CO4-203 · basement CO (chamber A)","ppm")

# ============================================================ footer
fy=H-46
add(rect(24,fy,W-48,32,CARD2,rx=5,stroke=LINE))
add(txt(40,fy+21,"KAVACH · The digital armour for zero-harm industrial operations",12,DIM,500))
add(txt(W-40,fy+21,"All data synthetic — a composite inspired by publicly reported incidents. No real plant data.",11,FAINT,400,anchor="end"))

svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'+ "".join(S)+'</svg>'
open("dashboard.svg","w").write(svg)
print("wrote dashboard.svg", len(svg), "bytes")
