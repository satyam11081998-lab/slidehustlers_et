import json, os, math, html
D = json.load(open(os.path.join(os.path.dirname(__file__) or ".", "dash.json")))
BG="#0f1830"; CARD="#1c2b4d"; CARD2="#17233f"; LINE="#2c3a63"; LINE2="#3a4a78"
INK="#eef2f8"; DIM="#9aa6c0"; FAINT="#6f7a99"
CYAN="#29b6f6"; CYAN2="#7fd3f7"; ORANGE="#f5921f"; PURPLE="#c264d6"; TEAL="#4dd0e1"
OK="#3fb6a6"; AMBER="#f2b134"; RED="#ef4b58"
MONO="'DejaVu Sans Mono','Consolas',monospace"
SANS="'Segoe UI','DejaVu Sans','Helvetica Neue',Arial,sans-serif"
W,H = 1680,1236
S=[]
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
    add(txt(x+18,y+30,title,18,"#d6dcea",500))
    if info: add(info_glyph(x+w-22,y+22))
    if caption: add(txt(x+18,y+50,fit(caption,w),12.5,DIM,400))
    return (x+18,y+ (66 if caption else 48))
add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
add('<defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">'
    f'<path d="M40 0 H0 V40" fill="none" stroke="rgba(140,160,200,0.05)" stroke-width="1"/></pattern>'
    f'<radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="{RED}" stop-opacity="0.5"/>'
    f'<stop offset="100%" stop-color="{RED}" stop-opacity="0"/></radialGradient></defs>')
add(f'<rect width="{W}" height="{H}" fill="url(#g)"/>')
add(rect(24,24,W-48,70,CARD,rx=6,stroke=LINE))
add(f'<g transform="translate(40,34)"><path d="M22 2 L38 8 V22 C38 33 31 40 22 44 C13 40 6 33 6 22 V8 Z" '
    f'fill="#0e1826" stroke="{CYAN}" stroke-width="2"/>'
    f'<path d="M13 23 h5 l3 7 l4 -13 l3 6 h5" fill="none" stroke="{CYAN2}" stroke-width="2.4" '
    f'stroke-linecap="round" stroke-linejoin="round"/></g>')
add(txt(96,52,"KAVACH",26,INK,800,ls=3))
add(txt(96,74,"Industrial Safety Intelligence · Compound-Risk Control Room",12.5,DIM,400,ls=0.4))
add(txt(560,50,"Gas Release Incident Replay — Coke Oven Battery 4",15,INK,600))
add(txt(560,72,"Synthetic composite · inspired by publicly reported coke-oven gas incidents",11.5,FAINT,400))
add(rect(W-350,45,158,30,"#3a1420",rx=15,stroke=RED,sw=1.2))
add(circle(W-332,60,5,RED)); add(txt(W-318,64,"RISK: CRITICAL",12.5,"#ff9aa0",700,ls=0.4))
add(txt(W-40,52,"06:30",30,INK,700,anchor="end",font=MONO))
add(txt(W-40,72,"SIM CLOCK · SHIFT A",10.5,FAINT,600,anchor="end",ls=1.2))
iy=102
add(rect(24,iy,W-48,70,CARD2,rx=6,stroke=LINE))
add(txt(40,iy+27,"HOW TO READ THIS BOARD",11,CYAN2,700,ls=1.6))
guide=("REPLAY of a past coke-oven gas incident — you are viewing 06:30, the moment KAVACH first alerted (first conventional alarm: 09:39). "
       "COMPOUND RISK = KAVACH fuses many sensors + permits + shift + plant layout into one 0-100 score; a single alarm only ever watches one sensor alone.")
gl=wrap(guide,150)
add(txt(40,iy+48,gl[0],13,INK,400))
if len(gl)>1: add(txt(40,iy+64,gl[1],13,INK,400))
lx=W-470
add(txt(lx,iy+27,"LEGEND",11,FAINT,700,ls=1.6))
leg=[("KAVACH compound risk",CYAN),("Single-sensor baseline",ORANGE),("Incident / hazard",RED)]
for i,(lb,c) in enumerate(leg):
    yy=iy+44+ (i//2)*18; xx=lx+(i%2)*230
    add(rect(xx,yy-9,11,11,c,rx=2)); add(txt(xx+18,yy,lb,11.5,DIM,400))
def axis_box(x,y,w,h): add(rect(x,y,w,h,CARD2,rx=4,stroke=LINE,op=0.55))
rc_x,rc_y,rc_w,rc_h = 24,184,996,430
cx,cy = card(rc_x,rc_y,rc_w,rc_h,"Compound Risk  vs  Single-Sensor Baseline",
             "KAVACH crosses ALERT at 06:30 · a conventional alarm only trips at 09:39 — 3h 09m later.")
px,py,pw,ph = rc_x+70, rc_y+92, rc_w-110, rc_h-170
axis_box(px,py,pw,ph)
dur=D["duration"]; T=D["T"]
def X(t): return px + (t/dur)*pw
def Yv(v,vmax=105): return py+ph - (v/vmax)*ph
for gv in (0,20,40,60,80,100):
    yy=Yv(gv); add(line(px,yy,px+pw,yy,LINE,1,op=0.5))
    add(txt(px-10,yy+4,f"{gv}",11,FAINT,400,anchor="end",font=MONO))
add(txt(px-46,py+ph/2,"RISK  (0-100)",11,FAINT,600,anchor="middle"))
add(line(px,Yv(60),px+pw,Yv(60),CYAN,1.4,dash="6 4",op=0.7))
add(txt(px+10,Yv(60)-7,"KAVACH ALERT  >= 60",11,CYAN2,700,anchor="start"))
add(line(px,Yv(100),px+pw,Yv(100),ORANGE,1.4,dash="6 4",op=0.7))
add(txt(px+10,Yv(100)-7,"BASELINE ALARM  = 100%",11,"#f7b06a",700,anchor="start"))
lim=D["limits"]; ser=D["series"]
def bl_pct(i):
    vals=[]
    for s in ("GD-CO4-203","GD-CO4-204","PT-GM-104","DP-CO4-801"):
        al=(lim.get(s) or {}).get("alarm")
        if al: vals.append(ser[s][i]/al*100)
    return min(100,max(vals))
bpts=[(X(T[i]),Yv(bl_pct(i))) for i in range(len(T))]
add(poly(bpts,ORANGE,2.4))
kr=D["risk_ts"]["cob4_basement"]
pre=[(X(T[i]),Yv(kr[i])) for i in range(len(T)) if T[i]<=270]
post=[(X(T[i]),Yv(kr[i])) for i in range(len(T)) if 270<=T[i]<=520]
apts=" ".join(f"{x:.1f},{y:.1f}" for x,y in post)
add(f'<polygon points="{X(270):.1f},{py+ph:.1f} {apts} {X(520):.1f},{py+ph:.1f}" fill="{CYAN}" opacity="0.12"/>')
add(poly(pre,CYAN,1.6,op=0.45,dash="4 3"))
add(poly(post,CYAN,3))
add(txt(X(140),Yv(18)+15,"watching (below alert)",10,CYAN2,400,anchor="middle",op=0.75))
def vmark(t,label,clock,color,side="l"):
    xx=X(t)
    add(line(xx,py,xx,py+ph,color,1.4,dash="2 3",op=0.85)); add(circle(xx,py,3.5,color))
    anch="start" if side=="l" else "end"; ox=6 if side=="l" else -6
    add(txt(xx+ox,py-9,f"{label} · {clock}",11,color,700,anchor=anch))
vmark(270,"KAVACH","06:30",CYAN2,"l")
vmark(459,"1st alarm","09:39",ORANGE,"r")
vmark(510,"INCIDENT","10:30",RED,"l")
ax1,ax2=X(270),X(459); ay=py+ph+22
add(line(ax1,ay,ax2,ay,CYAN2,1.6)); add(line(ax1,ay-5,ax1,ay+5,CYAN2,1.6)); add(line(ax2,ay-5,ax2,ay+5,CYAN2,1.6))
add(txt((ax1+ax2)/2,ay+18,"<-  3h 09m of prediction lead time  ->",13,CYAN2,700,anchor="middle"))
for t,lb in [(0,"02:00"),(120,"04:00"),(240,"06:00"),(360,"08:00"),(480,"10:00"),(600,"12:00")]:
    xx=X(t); add(line(xx,py+ph,xx,py+ph+4,FAINT,1)); add(txt(xx,py+ph+55,lb,11,FAINT,400,anchor="middle",font=MONO))
sc_x,sc_y,sc_w,sc_h = 1032,184,624,430
cx,cy=card(sc_x,sc_y,sc_w,sc_h,"Plant Schematic — Live Compound Risk",
           "Zones shaded by KAVACH risk. The hazard is where a breach meets people.")
def srgb(s):
    stops=[(0,(34,52,74)),(30,(53,196,122)),(45,(242,177,52)),(62,(245,146,31)),(82,(239,75,88)),(100,(214,60,72))]
    s=max(0,min(100,s))
    for i in range(1,len(stops)):
        x1,c1=stops[i-1]; x2,c2=stops[i]
        if s<=x2:
            p=(s-x1)/((x2-x1) or 1); return tuple(round(c1[k]+(c2[k]-c1[k])*p) for k in range(3))
    return stops[-1][1]
def zbox(x,y,w,h,label,score,tag=None):
    c=srgb(score); fill=f"rgba({c[0]},{c[1]},{c[2]},{0.08+score/100*0.5:.2f})"
    strk=f"rgba({c[0]},{c[1]},{c[2]},{0.75 if score>6 else 0.32:.2f})"
    if score>=80: add(f'<rect x="{x-9}" y="{y-9}" width="{w+18}" height="{h+18}" rx="12" fill="url(#halo)"/>')
    add(rect(x,y,w,h,fill,rx=6,stroke=strk,sw=2 if score>6 else 1.4))
    add(txt(x+12,y+(22 if tag else h/2+5),label,13.5,INK,600))
    if tag: add(txt(x+12,y+39,tag,10.5,("#ffb3b7" if score>=80 else DIM),400))
    if score>=1: add(txt(x+w-10,y+h-9,str(round(score)),18,f"rgb{srgb(score)}".replace(" ",""),800,anchor="end",font=MONO))
def arrow(x,y,d="r",col="rgba(150,175,215,0.55)"):
    if d=="r": p=f"{x},{y-4} {x+7},{y} {x},{y+4}"
    elif d=="l": p=f"{x},{y-4} {x-7},{y} {x},{y+4}"
    else: p=f"{x-4},{y} {x},{y+7} {x+4},{y}"
    add(f'<polygon points="{p}" fill="{col}"/>')
spx,spw,spy0,spy1=1336,24,272,556
add(rect(spx,spy0,spw,spy1-spy0,CARD2,rx=8,stroke=LINE2,sw=1.5))
add(f'<text x="{spx+spw/2}" y="{(spy0+spy1)/2}" transform="rotate(-90 {spx+spw/2} {(spy0+spy1)/2})" '
    f'font-size="11.5" fill="{DIM}" text-anchor="middle" font-family="{SANS}" letter-spacing="3" font-weight="700">GAS MAIN</text>')
add(rect(spx,492,spw,48,"rgba(239,75,88,0.45)",rx=4))
LX,LW=1064,152
zbox(LX,278,LW,44,"Battery 3",4); zbox(LX,340,LW,44,"Battery 4",8); zbox(LX,404,LW,30,"Platform P2",6)
zbox(1056,470,216,74,"Battery 4 Basement",100,tag="confined space · 5 crew inside")
RX,RW=1472,166
zbox(RX,278,RW,44,"By-Products Plant",0); zbox(RX,340,RW,44,"Gas Holder",0)
zbox(RX,404,RW,40,"Blast Furnace",0); zbox(RX,470,RW,40,"Control Room",0)
for yy in (300,362,419):
    add(line(LX+LW,yy,spx,yy,"rgba(150,175,215,0.4)",3)); arrow(spx-8,yy,"r")
for yy in (300,362,424):
    add(line(spx+spw,yy,RX,yy,"rgba(150,175,215,0.4)",3)); arrow(RX-2,yy,"r")
add(line(LX+34,384,LX+34,404,"rgba(150,175,215,0.35)",2)); add(line(LX+34,434,LX+34,470,"rgba(150,175,215,0.35)",2))
add(line(spx,516,1272,516,RED,4.5,dash="7 4")); arrow(1266,516,"l",RED)
vx=1302
add(f'<path d="M{vx-9},508 L{vx},516 L{vx-9},524 Z M{vx+9},508 L{vx},516 L{vx+9},524 Z" fill="none" stroke="{RED}" stroke-width="1.8"/>')
add(txt(vx,538,"V-707 OPEN",9,"#ffb3b7",700,anchor="middle"))
add(txt(1164,462,"coke-oven gas leaking into chamber",10.5,"#ffb3b7",600,anchor="middle"))
for i in range(5): add(circle(1074+i*15,528,4.2,"#ffd0d3",stroke=RED,sw=1))
add(rect(sc_x+18,sc_y+sc_h-54,sc_w-36,42,"#2a1420",rx=5,stroke="rgba(239,75,88,0.5)"))
add(circle(sc_x+34,sc_y+sc_h-36,5.5,RED))
add(txt(sc_x+48,sc_y+sc_h-38,"CRITICAL: isolation valve V-707 left open, so coke-oven gas leaks into the occupied",11,"#ffb3b7",600))
add(txt(sc_x+48,sc_y+sc_h-22,"chamber; the slowly-rising main pressure drives the leak. No single sensor in alarm.",10.5,"#ffb3b7",400))
ky=626
kpis=[("PREDICTION LEAD TIME","3h 09m",CYAN2,"KAVACH 06:30 vs alarm 09:39"),
 ("KAVACH ALERTED","06:30",INK,"compound critical alert"),
 ("1ST SINGLE ALARM","09:39",ORANGE,"conventional system · 3h later"),
 ("HAZARDS MISSED","0",OK,"caught the real hazard (replay)"),
 ("FALSE ALARMS","0",OK,"vs 1 for baseline · this replay")]
kw=(W-48-4*12)/5
for i,(lb,val,col,sub) in enumerate(kpis):
    x=24+i*(kw+12); add(rect(x,ky,kw,96,CARD,rx=6,stroke=LINE))
    add(txt(x+16,ky+26,lb,10.5,FAINT,700,ls=1)); add(txt(x+16,ky+64,val,34,col,700,font=MONO)); add(txt(x+16,ky+84,sub,11,DIM,400))
ly=734; lh=420; lx0=24; lw=530
cx,cy=card(lx0,ly,lw,lh,"Safety Layers — barrier status @ 06:30",
           "Plants have many barriers. Accidents happen when they fail one by one.")
barriers=[("Gas-main isolation (V-707)","OMITTED",RED,"never applied — treated as 'inspection-only' · 06:30"),
 ("Pre-entry gas test","DEGRADED",AMBER,"single-point only; chamber rear untested · 06:15"),
 ("Permit-to-work control","DEGRADED",AMBER,"authorised entry with no isolation · 06:30"),
 ("Shift handover","FAILED",AMBER,"overnight pressure drift not communicated · 06:00"),
 ("Fixed gas detection","EFFECTIVE",OK,"live, but readings still sub-threshold"),
 ("Hot-work separation","HOLDS",FAINT,"compromised later — welding near vent · 08:30"),
 ("Riser back-pressure","HOLDS",FAINT,"compromised later — V-707 throttled · 09:30")]
by=cy+6; rowh=(lh-(cy-ly)-58)/len(barriers)
for i,(nm,st,col,note) in enumerate(barriers):
    yy=by+i*rowh
    add(rect(lx0+18,yy,lw-36,rowh-8,CARD2,rx=4,stroke=LINE,op=0.7))
    add(circle(lx0+36,yy+(rowh-8)/2,7,col)); add(txt(lx0+54,yy+21,nm,13.5,INK,600)); add(txt(lx0+54,yy+38,note,11,DIM,400))
    add(rect(lx0+lw-116,yy+(rowh-8)/2-11,86,22,"none",rx=11,stroke=col,sw=1.3))
    add(txt(lx0+lw-73,yy+(rowh-8)/2+4,st,11,col,700,anchor="middle",ls=0.5))
add(txt(lx0+18,ly+lh-14,"1 omitted + 3 degraded/failed — no single alarm connects them.",12,CYAN2,600))
ex0=566; ew=530
cx,cy=card(ex0,ly,ew,lh,"Why — Alert Evidence @ 06:30",
           "Every KAVACH alert carries its full reasoning. Judges probe; it answers.")
add(rect(ex0+18,cy,ew-36,40,"rgba(239,75,88,0.10)",rx=5,stroke="rgba(239,75,88,0.4)"))
add(rect(ex0+18,cy,4,40,RED,rx=0))
add(rect(ex0+30,cy+10,72,20,RED,rx=4)); add(txt(ex0+66,cy+24,"CRITICAL",11,"#fff",800,anchor="middle"))
add(txt(ex0+114,cy+18,"Battery 4 Basement / Inspection Chamber",13,INK,600))
add(txt(ex0+114,cy+34,"score 100/100 · confidence 91%",11,DIM,400,font=MONO))
add(txt(ex0+ew-30,cy+24,"06:30",13,DIM,600,anchor="end",font=MONO))
rules=[("R1","Rising CO inside an occupied confined space, fed by an un-isolated gas main leaking on the connected riser"),
 ("R3","Confined entry with gas-main isolation (V-707) left open while the connected main is abnormal"),
 ("R5","Entry cleared on a single-point gas test; same-zone trend now rising"),
 ("R4","Shift-changeover blindspot — unacknowledged drift on PT-GM-104")]
ry=cy+58; add(txt(ex0+18,ry,"REASONING · 4 RULES FUSED",10.5,FAINT,700,ls=1)); ry+=8
for rid,det in rules:
    ry+=8
    add(rect(ex0+18,ry,30,20,"rgba(41,182,246,0.14)",rx=4,stroke="rgba(41,182,246,0.3)"))
    add(txt(ex0+33,ry+14,rid,12,CYAN2,700,anchor="middle",font=MONO))
    words=det.split(); lines=[""]
    for wd in words:
        if len(lines[-1])+len(wd)+1>60: lines.append("")
        lines[-1]+=(" "+wd if lines[-1] else wd)
    for j,ln in enumerate(lines): add(txt(ex0+58,ry+13+j*16,ln,12,DIM,400))
    ry+=max(24,len(lines)*16+6)
ry+=2; add(txt(ex0+18,ry,"SIGNALS",10.5,FAINT,700,ls=1)); ry+=18
for lb in ["PT-GM-104  8.60 kPa · sub-threshold drift","GD-CO4-203  16.4 ppm rising","CSE-2093  isolation: NOT applied"]:
    col = AMBER if "drift" in lb or "NOT" in lb else INK
    add(rect(ex0+18,ry-13,ew-36,22,CARD2,rx=4,stroke=LINE)); add(txt(ex0+28,ry+2,lb,12,col,500,font=MONO)); ry+=28
tx0=1108; tw=548
cx,cy=card(tx0,ly,tw,lh,"Key Instruments — the drift was there",
           "Both stayed below their alarm line while KAVACH already warned.")
def trend(x,y,w,h,sid,name,unit):
    add(rect(x,y,w,h,CARD2,rx=4,stroke=LINE,op=0.6))
    vals=ser[sid]; al=(lim.get(sid) or {}).get("alarm"); wn=(lim.get(sid) or {}).get("warn")
    refs=[v for v in (wn,al) if v]; lo=min(vals+refs); hi=max(vals+refs); sp=hi-lo or 1; lo-=sp*0.12; hi+=sp*0.12
    def PX(i): return x+40+ (i/(len(vals)-1))*(w-56)
    def PY(v): return y+h-16 - ((v-lo)/(hi-lo))*(h-32)
    if wn: add(line(x+40,PY(wn),x+w-16,PY(wn),AMBER,1,dash="3 3",op=0.55)); add(txt(x+w-18,PY(wn)-3,"warn",9.5,AMBER,400,anchor="end"))
    if al: add(line(x+40,PY(al),x+w-16,PY(al),ORANGE,1,dash="3 3",op=0.55)); add(txt(x+w-18,PY(al)-3,"alarm",9.5,"#f7b06a",400,anchor="end"))
    ci=min(range(len(T)),key=lambda i:abs(T[i]-270))
    add(line(PX(ci),y+10,PX(ci),y+h-14,CYAN2,1,op=0.6,dash="2 2"))
    pts=[(PX(i),PY(vals[i])) for i in range(len(vals))]
    add(poly(pts[:ci+1],CYAN,2.4)); add(poly(pts[ci:],CYAN,2,op=0.4))
    add(circle(PX(ci),PY(vals[ci]),3.4,CYAN2,stroke=BG,sw=1.2))
    add(txt(x+12,y+20,name,12,DIM,600)); add(txt(x+w-16,y+20,f"{vals[ci]} {unit}",13,INK,700,anchor="end",font=MONO))
    add(txt(PX(ci)+6,y+h-4,"06:30",9.5,CYAN2,600,font=MONO))
th=(lh-(cy-ly)-24)/2
trend(tx0+18,cy+4,tw-36,th-10,"PT-GM-104","PT-GM-104 · Battery-4 riser pressure","kPa")
trend(tx0+18,cy+4+th,tw-36,th-10,"GD-CO4-203","GD-CO4-203 · basement CO (chamber A)","ppm")
fy=H-46
add(rect(24,fy,W-48,32,CARD2,rx=5,stroke=LINE))
add(txt(40,fy+21,"KAVACH · The digital armour for zero-harm industrial operations",12,DIM,500))
add(txt(W-40,fy+21,"All data synthetic — a composite inspired by publicly reported incidents. No real plant data.",11,FAINT,400,anchor="end"))
svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'+ "".join(S)+'</svg>'
open(os.path.join(os.path.dirname(__file__) or ".","dashboard.svg"),"w").write(svg)
print("wrote dashboard.svg", len(svg))
