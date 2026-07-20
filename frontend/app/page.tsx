"use client";

/**
 * KAVACH — Compound-Risk Control Room (route "/")
 * ===============================================
 * The live product board. The whole dashboard is drawn as one responsive SVG
 * (same design that was rendered, critiqued and hardened offline), fed by live
 * data over the WebSocket so it updates as you play/scrub the incident replay.
 * HTML transport controls and clickable info (ⓘ) are overlaid on top.
 *
 * Sections: header · how-to-read strip · risk-vs-baseline chart · plant
 * schematic · KPI ribbon · safety-layers barriers · alert evidence · key
 * instruments · transport (play / speed / scrub / Baseline⇄KAVACH / scenario).
 */

import { useCallback, useEffect, useRef, useState } from "react";

const IS_PROD = typeof window !== "undefined" && window.location.hostname !== "localhost";
const RAW_API = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "");
const API = RAW_API || (IS_PROD ? null : "http://localhost:8000");
const WS = API ? API.replace(/^http/, "ws") : null;

// ---------- palette ----------
const BG="#0f1830",CARD="#1c2b4d",CARD2="#17233f",LINE="#2c3a63",LINE2="#3a4a78";
const INK="#eef2f8",DIM="#9aa6c0",FAINT="#6f7a99";
const CYAN="#29b6f6",CYAN2="#7fd3f7",ORANGE="#f5921f",OK="#3fb6a6",AMBER="#f2b134",RED="#ef4b58";
const MONO="ui-monospace,'DejaVu Sans Mono',Consolas,monospace";
const SANS="'Segoe UI',system-ui,-apple-system,Roboto,sans-serif";

// ---------- svg string helpers (mirror the offline generator) ----------
const esc=(t:any)=>String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
function wrap(t:string,mc:number){const w=t.split(" ");const l=[""];for(const x of w){if(l[l.length-1]&&l[l.length-1].length+1+x.length>mc)l.push("");l[l.length-1]+=(l[l.length-1]?" ":"")+x;}return l;}
const fit=(t:string,w:number,cpp=6.4)=>{const m=Math.floor((w-40)/cpp);return t.length<=m?t:t.slice(0,m-1)+"…";};
const R=(x:number,y:number,w:number,h:number,f:string,rx=0,s?:string,sw=1,op=1,dash?:string)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${f}" opacity="${op}"${s?` stroke="${s}" stroke-width="${sw}"`:""}${dash?` stroke-dasharray="${dash}"`:""}/>`;
const T=(x:number,y:number,t:any,size=14,f=INK,w=400,anchor="start",font=SANS,ls=0,op=1)=>`<text x="${x}" y="${y}" font-size="${size}" fill="${f}" font-weight="${w}" text-anchor="${anchor}" font-family="${font}" letter-spacing="${ls}" opacity="${op}">${esc(t)}</text>`;
const L=(x1:number,y1:number,x2:number,y2:number,s=LINE,sw=1,dash?:string,op=1)=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${s}" stroke-width="${sw}" opacity="${op}" stroke-linecap="round"${dash?` stroke-dasharray="${dash}"`:""}/>`;
const P=(pts:[number,number][],s:string,sw=2,f="none",op=1,dash?:string)=>`<polyline points="${pts.map(p=>`${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")}" fill="${f}" stroke="${s}" stroke-width="${sw}" opacity="${op}" stroke-linejoin="round" stroke-linecap="round"${dash?` stroke-dasharray="${dash}"`:""}/>`;
const CI=(cx:number,cy:number,r:number,f:string,s?:string,sw=1,op=1)=>`<circle cx="${cx}" cy="${cy}" r="${r}" fill="${f}" opacity="${op}"${s?` stroke="${s}" stroke-width="${sw}"`:""}/>`;
const infoGlyph=(x:number,y:number)=>`<circle cx="${x}" cy="${y}" r="9" fill="none" stroke="${FAINT}" stroke-width="1.3"/><text x="${x}" y="${y+4.5}" font-size="12" fill="${DIM}" text-anchor="middle" font-family="${SANS}" font-style="italic" font-weight="700">i</text>`;
function scoreRGB(s:number):[number,number,number]{const st:[number,[number,number,number]][]=[[0,[34,52,74]],[30,[53,196,122]],[45,[242,177,52]],[62,[245,146,31]],[82,[239,75,88]],[100,[214,60,72]]];s=Math.max(0,Math.min(100,s));for(let i=1;i<st.length;i++){const[a,c1]=st[i-1],[b,c2]=st[i];if(s<=b){const p=(s-a)/((b-a)||1);return[0,1,2].map(k=>Math.round(c1[k]+(c2[k]-c1[k])*p)) as[number,number,number];}}return st[st.length-1][1];}
const rgba=(c:[number,number,number],a:number)=>`rgba(${c[0]},${c[1]},${c[2]},${a})`;
const fmtDur=(m:number|null)=>m==null?"—":(m>=60?`${Math.floor(m/60)}h ${String(m%60).padStart(2,"0")}m`:`${m}m`);

// ---------- info hotspots (as % of the 1680x1236 viewBox) ----------
const HOTSPOTS=[
 {x:59.4,y:16.7,t:"Compound Risk vs Single-Sensor Baseline",b:"Blue = KAVACH's fused 0–100 risk score for the basement. Orange = the single worst sensor as a % of its own alarm limit. KAVACH crosses ALERT (60) at 06:30; the sensor only hits 100% (a real alarm) at 09:39. The shaded gap is the lead time. The vertical marker is the live 'now' cursor."},
 {x:97.3,y:16.7,t:"Plant Schematic — Live Compound Risk",b:"A map of the coke-oven gas network, each zone shaded by its live KAVACH risk (the number is the 0–100 score). The red path shows coke-oven gas leaking from the main into the occupied Battery-4 basement because isolation valve V-707 was left open."},
 {x:31.7,y:61.2,t:"Safety Layers — barrier status",b:"Plants rely on layered barriers (isolation, gas test, permit, handover, detection). Accidents happen when they fail one-by-one and nothing connects them. This shows each barrier's state at the current time — KAVACH is what connects them."},
 {x:63.9,y:61.2,t:"Why — Alert Evidence",b:"The full reasoning behind the current alert: the rules that fired, the exact signal values, and the permits in play — so a supervisor or auditor can always ask 'why?' and get an answer."},
 {x:97.3,y:61.2,t:"Key Instruments — the drift was there",b:"The sensors that mattered, over the whole shift, with their warn/alarm limits (dashed). Both stayed below their alarm line the entire time KAVACH was already warning."},
];
const SPARKS:Record<string,string[]>={vizag_replay:["PT-GM-104","GD-CO4-203"],normal_day:["PT-GM-103","GD-CO3-208"]};
// open each scenario on its most instructive moment (KAVACH's alert / the calibration), not the empty start
const OPEN_T:Record<string,number>={vizag_replay:270,normal_day:240};
const JUMPS:Record<string,{label:string;t:number;hot?:boolean}[]>={
 vizag_replay:[{label:"02:30 drift",t:30},{label:"06:00 handover",t:240},{label:"06:30 entry",t:270,hot:true},{label:"08:30 hot work",t:390,hot:true},{label:"09:40 1st alarm",t:460},{label:"10:29 T−1",t:509}],
 normal_day:[{label:"06:00 start",t:0},{label:"08:00 entry",t:120},{label:"09:55 calibration",t:235},{label:"13:00 close",t:420}],
};
// vizag barrier timeline (state as a function of t)
const BARRIERS:Record<string,{n:string;note:string;breach:number;st:[string,string]}[]>={
 vizag_replay:[
  {n:"Gas-main isolation (V-707)",note:"never applied — 'inspection-only' entry",breach:270,st:["ARMED?","OMITTED"]},
  {n:"Pre-entry gas test",note:"single-point only; chamber rear untested",breach:255,st:["—","DEGRADED"]},
  {n:"Permit-to-work control",note:"authorised entry with no isolation",breach:270,st:["—","DEGRADED"]},
  {n:"Shift handover",note:"overnight pressure drift not communicated",breach:240,st:["OK","FAILED"]},
  {n:"Fixed gas detection",note:"live, but readings still sub-threshold",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
  {n:"Hot-work separation",note:"welding 20 m from basement vent",breach:390,st:["HOLDS","BREACHED"]},
  {n:"Riser back-pressure",note:"V-707 throttled, driving the leak",breach:450,st:["HOLDS","BREACHED"]},
 ],
 normal_day:[
  {n:"Gas-main isolation",note:"adjacent leg isolated and purged",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
  {n:"Pre-entry gas test",note:"multi-point; continuous monitor issued",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
  {n:"Permit-to-work control",note:"CSE-2094 issued correctly",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
  {n:"Calibration context",note:"PT-GM-103 test pressure — KAVACH suppressed",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
  {n:"Fixed gas detection",note:"all readings within limits",breach:-1,st:["EFFECTIVE","EFFECTIVE"]},
 ],
};
const stColor=(s:string)=>s==="OMITTED"||s==="BREACHED"?RED:(s==="DEGRADED"||s==="FAILED")?AMBER:s==="EFFECTIVE"?OK:FAINT;

// ============================================================ BOARD BUILDER
function buildBoard(D:any):string{
 const s:string[]=[];const add=(x:string)=>s.push(x);
 const W=1680,H=1236;
 const {state,risk,rs,metrics:m,series,mode,scenarioTitle,alerts}=D;
 const t=state.t,dur=state.duration;
 // defs + bg
 add(`<defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0 H0 V40" fill="none" stroke="rgba(140,160,200,0.05)" stroke-width="1"/></pattern><radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="${RED}" stop-opacity="0.5"/><stop offset="100%" stop-color="${RED}" stop-opacity="0"/></radialGradient></defs>`);
 add(R(0,0,W,H,BG));add(R(0,0,W,H,"url(#g)"));
 const card=(x:number,y:number,w:number,h:number,title:string,cap:string)=>{add(R(x,y,w,h,CARD,6,LINE,1));add(T(x+18,y+30,title,18,"#d6dcea",500));add(infoGlyph(x+w-22,y+22));if(cap)add(T(x+18,y+50,fit(cap,w),12.5,DIM,400));return [x+18,y+(cap?66:48)];};
 // ---- header ----
 add(R(24,24,W-48,70,CARD,6,LINE));
 add(`<g transform="translate(40,34)"><path d="M22 2 L38 8 V22 C38 33 31 40 22 44 C13 40 6 33 6 22 V8 Z" fill="#0e1826" stroke="${CYAN}" stroke-width="2"/><path d="M13 23 h5 l3 7 l4 -13 l3 6 h5" fill="none" stroke="${CYAN2}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></g>`);
 add(T(96,52,"KAVACH",26,INK,800,"start",SANS,3));
 add(T(96,74,"Industrial Safety Intelligence · Compound-Risk Control Room",12.5,DIM,400,"start",SANS,0.4));
 add(T(560,50,scenarioTitle,15,INK,600));
 add(T(560,72,"Synthetic composite · inspired by publicly reported coke-oven gas incidents",11.5,FAINT,400));
 const topBand=risk?.top_band_name?String(risk.top_band_name).toUpperCase():"—";
 const bandCol=risk?.top_band>=3?RED:risk?.top_band>=2?ORANGE:risk?.top_band>=1?AMBER:OK;
 add(R(W-360,45,168,30,mode==="baseline"?"#22314f":"#3a1420",15,bandCol,1.2));
 add(CI(W-342,60,5,bandCol));add(T(W-328,64,`RISK: ${topBand}`,12.5,mode==="baseline"?"#cdd5e6":"#ff9aa0",700,"start",SANS,0.4));
 add(T(W-40,52,state.clock,30,INK,700,"end",MONO));
 add(T(W-40,72,`SIM CLOCK${state.shift?` · SHIFT ${state.shift.name}`:""}`,10.5,FAINT,600,"end",SANS,1.2));
 // ---- instruction strip ----
 const iy=102;add(R(24,iy,W-48,70,CARD2,6,LINE));
 add(T(40,iy+27,"HOW TO READ THIS BOARD",11,CYAN2,700,"start",SANS,1.6));
 const guide="REPLAY of a coke-oven gas incident — scrub the timeline; you start at 06:30, when KAVACH first alerted (first conventional alarm: 09:39). COMPOUND RISK = KAVACH fuses many sensors + permits + shift + plant layout into one 0-100 score; a single alarm only ever watches one sensor alone.";
 const gl=wrap(guide,150);add(T(40,iy+48,gl[0],13,INK,400));if(gl[1])add(T(40,iy+64,gl[1],13,INK,400));
 const lx=W-470;add(T(lx,iy+27,"LEGEND",11,FAINT,700,"start",SANS,1.6));
 [["KAVACH compound risk",CYAN],["Single-sensor baseline",ORANGE],["Incident / hazard",RED]].forEach((it,i)=>{const yy=iy+44+Math.floor(i/2)*18,xx=lx+(i%2)*230;add(R(xx,yy-9,11,11,it[1] as string,2));add(T(xx+18,yy,it[0],11.5,DIM,400));});
 // ---- risk chart ----
 const rx=24,ry=184,rw=996,rh=430;card(rx,ry,rw,rh,"Compound Risk  vs  Single-Sensor Baseline","KAVACH crosses ALERT at 06:30 · a conventional alarm only trips at 09:39 — 3h 09m later.");
 const px=rx+70,py=ry+92,pw=rw-110,ph=rh-170;add(R(px,py,pw,ph,CARD2,4,LINE,1,0.55));
 const X=(tt:number)=>px+(tt/dur)*pw,Yv=(v:number)=>py+ph-(v/105)*ph;
 [0,20,40,60,80,100].forEach(gv=>{add(L(px,Yv(gv),px+pw,Yv(gv),LINE,1,undefined,0.5));add(T(px-10,Yv(gv)+4,gv,11,FAINT,400,"end",MONO));});
 add(T(px-46,py+ph/2,"RISK (0-100)",11,FAINT,600,"middle"));
 add(L(px,Yv(60),px+pw,Yv(60),CYAN,1.4,"6 4",0.7));add(T(px+10,Yv(60)-7,"KAVACH ALERT  >= 60",11,CYAN2,700));
 add(L(px,Yv(100),px+pw,Yv(100),ORANGE,1.4,"6 4",0.7));add(T(px+10,Yv(100)-7,"BASELINE ALARM  = 100%",11,"#f7b06a",700));
 const rt=rs.t as number[];const hero=rs.hero as string;const kr=rs.zones[hero] as number[];const bl=rs.baseline as number[];
 // baseline curve (clamped in-plot)
 add(P(rt.map((tt,i)=>[X(tt),Yv(Math.min(100,bl[i]))] as [number,number]),ORANGE,2.4));
 // kavach curve pre/post detection
 const det=m?.kavach?.detection_t ?? null;const incid=m?.incident_at ?? null;const cut=incid!=null?Math.min(dur,incid+10):dur;
 const splitT=det!=null?det:0;
 const pre=rt.map((tt,i)=>[tt,i] as [number,number]).filter(([tt])=>tt<=splitT).map(([tt,i])=>[X(tt),Yv(kr[i])] as [number,number]);
 const post=rt.map((tt,i)=>[tt,i] as [number,number]).filter(([tt])=>tt>=splitT&&tt<=cut).map(([tt,i])=>[X(tt),Yv(kr[i])] as [number,number]);
 if(post.length){const apts=post.map(p=>`${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");add(`<polygon points="${X(splitT).toFixed(1)},${(py+ph).toFixed(1)} ${apts} ${X(cut).toFixed(1)},${(py+ph).toFixed(1)}" fill="${CYAN}" opacity="0.12"/>`);}
 if(pre.length>1){add(P(pre,CYAN,1.6,"none",0.45,"4 3"));add(T(X(splitT/2),Yv(18)+15,"watching (below alert)",10,CYAN2,400,"middle",SANS,0,0.75));}
 if(post.length)add(P(post,CYAN,3));
 // markers
 const vmark=(tt:number,label:string,clk:string,col:string,side="l")=>{if(tt==null)return;const xx=X(tt);add(L(xx,py,xx,py+ph,col,1.4,"2 3",0.85));add(CI(xx,py,3.5,col));const anch=side==="l"?"start":"end",ox=side==="l"?6:-6;add(T(xx+ox,py-9,`${label} · ${clk}`,11,col,700,anch));};
 vmark(det,"KAVACH",m?.kavach?.detection_clock||"",CYAN2,"l");
 vmark(m?.baseline?.first_uncleared_t,"1st alarm",m?.baseline?.first_uncleared_clock||"",ORANGE,"r");
 vmark(incid,"INCIDENT",m?.incident_clock||"",RED,"l");
 // lead-time span
 if(det!=null&&m?.baseline?.first_uncleared_t!=null){const a1=X(det),a2=X(m.baseline.first_uncleared_t),ayy=py+ph+22;add(L(a1,ayy,a2,ayy,CYAN2,1.6));add(L(a1,ayy-5,a1,ayy+5,CYAN2,1.6));add(L(a2,ayy-5,a2,ayy+5,CYAN2,1.6));add(T((a1+a2)/2,ayy+18,`<-  ${fmtDur(m.lead_time_min)} of prediction lead time  ->`,13,CYAN2,700,"middle"));}
 // live NOW cursor
 add(L(X(t),py,X(t),py+ph,INK,1.5,undefined,0.9));add(CI(X(t),py+ph,4,INK));add(T(X(t),py+ph+38,`NOW ${state.clock}`,10.5,INK,700,"middle",MONO));
 // x ticks
 const startClock=scenarioTitle.includes("Normal")?6*60:2*60;
 [0,120,240,360,480,600].filter(tt=>tt<=dur).forEach(tt=>{const hh=Math.floor((startClock+tt)/60)%24;add(L(X(tt),py+ph,X(tt),py+ph+4,FAINT,1));add(T(X(tt),py+ph+55,`${String(hh).padStart(2,"0")}:00`,11,FAINT,400,"middle",MONO));});
 // ---- schematic ----
 const scx=1032,scy=184,scw=624,sch=430;card(scx,scy,scw,sch,"Plant Schematic — Live Compound Risk","Zones shaded by KAVACH risk. The hazard is where a breach meets people.");
 const zScore=(z:string)=>mode==="baseline"?baselineZone(z,state):(risk?.zones?.[z]?.score??0);
 const zbox=(x:number,y:number,w:number,h:number,label:string,zid:string,tag?:string)=>{const sc=zScore(zid);const c=scoreRGB(sc);add(sc>=80?`<rect x="${x-9}" y="${y-9}" width="${w+18}" height="${h+18}" rx="12" fill="url(#halo)"/>`:"");add(R(x,y,w,h,rgba(c,0.08+sc/100*0.5),6,rgba(c,sc>6?0.75:0.32),sc>6?2:1.4));add(T(x+12,y+(tag?22:h/2+5),label,13.5,INK,600));if(tag)add(T(x+12,y+39,tag,10.5,sc>=80?"#ffb3b7":DIM,400));if(sc>=1)add(T(x+w-10,y+h-9,Math.round(sc),18,`rgb(${scoreRGB(sc).join(",")})`,800,"end",MONO));};
 const arrow=(x:number,y:number,d="r",col="rgba(150,175,215,0.55)")=>{const p=d==="r"?`${x},${y-4} ${x+7},${y} ${x},${y+4}`:`${x},${y-4} ${x-7},${y} ${x},${y+4}`;add(`<polygon points="${p}" fill="${col}"/>`);};
 const spx=1336,spw=24;add(R(spx,272,spw,284,CARD2,8,LINE2,1.5));
 add(`<text x="${spx+spw/2}" y="414" transform="rotate(-90 ${spx+spw/2} 414)" font-size="11.5" fill="${DIM}" text-anchor="middle" font-family="${SANS}" letter-spacing="3" font-weight="700">GAS MAIN</text>`);
 const showLeak=zScore("cob4_basement")>=80;
 if(showLeak)add(R(spx,492,spw,48,"rgba(239,75,88,0.45)",4));
 zbox(1064,278,152,44,"Battery 3","cob3");zbox(1064,340,152,44,"Battery 4","cob4");zbox(1064,404,152,30,"Platform P2","platform_p2");
 zbox(1056,470,216,74,"Battery 4 Basement","cob4_basement",showLeak?"confined space · 5 crew inside":"confined space");
 zbox(1472,278,166,44,"By-Products Plant","bpp");zbox(1472,340,166,44,"Gas Holder","gas_holder");zbox(1472,404,166,40,"Blast Furnace","bf_approach");zbox(1472,470,166,40,"Control Room","control_room");
 [300,362,419].forEach(yy=>{add(L(1216,yy,spx,yy,"rgba(150,175,215,0.4)",3));arrow(spx-8,yy,"r");});
 [300,362,424].forEach(yy=>{add(L(spx+spw,yy,1472,yy,"rgba(150,175,215,0.4)",3));arrow(1470,yy,"r");});
 add(L(1098,384,1098,404,"rgba(150,175,215,0.35)",2));add(L(1098,434,1098,470,"rgba(150,175,215,0.35)",2));
 if(showLeak){add(L(spx,516,1272,516,RED,4.5,"7 4"));arrow(1266,516,"l",RED);const vx=1302;add(`<path d="M${vx-9},508 L${vx},516 L${vx-9},524 Z M${vx+9},508 L${vx},516 L${vx+9},524 Z" fill="none" stroke="${RED}" stroke-width="1.8"/>`);add(T(vx,538,"V-707 OPEN",9,"#ffb3b7",700,"middle"));add(T(1164,462,"coke-oven gas leaking into chamber",10.5,"#ffb3b7",600,"middle"));for(let i=0;i<5;i++)add(CI(1074+i*15,528,4.2,"#ffd0d3",RED,1));}
 add(R(scx+18,scy+sch-54,scw-36,42,showLeak?"#2a1420":CARD2,5,showLeak?"rgba(239,75,88,0.5)":LINE));
 add(CI(scx+34,scy+sch-36,5.5,showLeak?RED:OK));
 if(showLeak){add(T(scx+48,scy+sch-38,"CRITICAL: isolation valve V-707 left open, so coke-oven gas leaks into the occupied",11,"#ffb3b7",600));add(T(scx+48,scy+sch-22,"chamber; the slowly-rising main pressure drives the leak. No single sensor in alarm.",10.5,"#ffb3b7",400));}
 else{add(T(scx+48,scy+sch-30,fit("No compound hazard: barriers effective and gas readings within limits.",scw-40),11.5,DIM,500));}
 // ---- KPI ribbon ----
 const ky=626;const lead=m?.lead_time_min;
 const kpis=lead!=null?[["PREDICTION LEAD TIME",fmtDur(lead),CYAN2,`KAVACH ${m.kavach.detection_clock} vs alarm ${m.baseline.first_uncleared_clock}`],["KAVACH ALERTED",m.kavach.detection_clock,INK,"compound critical alert"],["1ST SINGLE ALARM",m.baseline.first_uncleared_clock,ORANGE,"conventional system · 3h later"],["HAZARDS MISSED",String(m.kavach.false_negatives),OK,"caught the real hazard (replay)"],["FALSE ALARMS",String(m.kavach.false_positives),OK,"vs 1 for baseline · this replay"]]
  :[["FALSE ALERTS (KAVACH)",String(m?.kavach?.false_positives??0),OK,"a benign shift"],["FALSE ALERTS (BASELINE)",String(m?.baseline?.false_positives??0),ORANGE,"single-sensor system"],["SUPPRESSIONS",String(m?.suppression_count??0),CYAN2,"calibration explained away"],["HAZARDS",String(0),OK,"none present"],["VERDICT","RESTRAINT",OK,"KAVACH holds fire"]];
 const kw=(W-48-4*12)/5;
 kpis.forEach((k:any,i:number)=>{const x=24+i*(kw+12);add(R(x,ky,kw,96,CARD,6,LINE));add(T(x+16,ky+26,k[0],10.5,FAINT,700,"start",SANS,1));add(T(x+16,ky+64,k[1],k[1].length>6?26:34,k[2],700,"start",MONO));add(T(x+16,ky+84,k[3],11,DIM,400));});
 // ---- safety layers ----
 const ly=734,lh=420,lw=530;const[,cyS]=card(24,ly,lw,lh,"Safety Layers — barrier status","Plants have many barriers. Accidents happen when they fail one by one.");
 const bars=(BARRIERS[D.scenario]||BARRIERS.vizag_replay);
 const by=cyS+6,rowh=(lh-(cyS-ly)-58)/bars.length;let breached=0;
 bars.forEach((b,i)=>{const st=(b.breach>=0&&t>=b.breach)?b.st[1]:b.st[0];const col=stColor(st);if(st==="OMITTED"||st==="DEGRADED"||st==="FAILED"||st==="BREACHED")breached++;const yy=by+i*rowh;add(R(24+18,yy,lw-36,rowh-8,CARD2,4,LINE,1,0.7));add(CI(24+36,yy+(rowh-8)/2,7,col));add(T(24+54,yy+21,b.n,13.5,INK,600));add(T(24+54,yy+38,fit(b.note,lw-190),11,DIM,400));add(R(24+lw-116,yy+(rowh-8)/2-11,86,22,"none",11,col,1.3));add(T(24+lw-73,yy+(rowh-8)/2+4,st,st.length>8?9.5:11,col,700,"middle",SANS,0.4));});
 add(T(24+18,ly+lh-14,breached>0?`${breached} barrier(s) compromised — no single alarm connects them. KAVACH does.`:"All barriers effective — KAVACH confirms, and stays quiet.",12,CYAN2,600));
 // ---- evidence ----
 const ex=566,ew=530;const[,cyE]=card(ex,ly,ew,lh,"Why — Alert Evidence","Every KAVACH alert carries its full reasoning. Judges probe; it answers.");
 const al=risk?.active_alerts?.[0];
 if(al){add(R(ex+18,cyE,ew-36,40,"rgba(239,75,88,0.10)",5,"rgba(239,75,88,0.4)"));add(R(ex+18,cyE,4,40,RED));add(R(ex+30,cyE+10,72,20,al.band>=3?RED:al.band>=2?ORANGE:AMBER,4));add(T(ex+66,cyE+24,al.band_name.toUpperCase(),11,"#fff",800,"middle"));add(T(ex+114,cyE+18,fit(al.zone_name,ew-160),13,INK,600));add(T(ex+114,cyE+34,`score ${Math.round(al.score)}/100 · confidence ${Math.round(al.confidence*100)}%`,11,DIM,400,"start",MONO));add(T(ex+ew-30,cyE+24,al.clock,13,DIM,600,"end",MONO));
  let yy=cyE+58;add(T(ex+18,yy,`REASONING · ${al.rules.length} RULES FUSED`,10.5,FAINT,700,"start",SANS,1));yy+=8;
  al.rules.slice(0,4).forEach((r:any)=>{yy+=8;add(R(ex+18,yy,30,20,"rgba(41,182,246,0.14)",4,"rgba(41,182,246,0.3)"));add(T(ex+33,yy+14,r.id,12,CYAN2,700,"middle",MONO));const wl=wrap(r.detail,58);wl.slice(0,2).forEach((ln,j)=>add(T(ex+58,yy+13+j*16,ln,12,DIM,400)));yy+=Math.max(24,Math.min(2,wl.length)*16+6);});
  yy+=2;add(T(ex+18,yy,"SIGNALS",10.5,FAINT,700,"start",SANS,1));yy+=18;
  const sig:string[]=[];Object.entries(al.signals.gas_main_pressure||{}).forEach(([k,v]:any)=>sig.push(`${k}  ${v.value} kPa${v.drifting?" · drift":""}`));Object.entries(al.signals.rising_gas||{}).forEach(([k,v]:any)=>sig.push(`${k}  ${v.value} rising`));(al.permits||[]).slice(0,1).forEach((p:any)=>sig.push(`${p.id}  isolation: NOT applied`));
  sig.slice(0,3).forEach(lb=>{const col=lb.includes("drift")||lb.includes("NOT")?AMBER:INK;add(R(ex+18,yy-13,ew-36,22,CARD2,4,LINE));add(T(ex+28,yy+2,lb,12,col,500,"start",MONO));yy+=28;});
 }else{add(T(ex+18,cyE+30,"No compound alert right now.",13,OK,600));add(T(ex+18,cyE+52,"KAVACH is watching developing trends below the alert",12,DIM,400));add(T(ex+18,cyE+70,"band — it does not fire until context makes a hazard real.",12,DIM,400));}
 // ---- instruments ----
 const tx=1108,tw=548;const[,cyT]=card(tx,ly,tw,lh,"Key Instruments — the drift was there","Both stayed below their alarm line while KAVACH already warned.");
 const th=(lh-(cyT-ly)-24)/2;const sids=SPARKS[D.scenario]||SPARKS.vizag_replay;
 const trend=(x:number,y:number,w:number,h:number,sid:string,name:string,unit:string)=>{const S=series[sid];if(!S)return;add(R(x,y,w,h,CARD2,4,LINE,1,0.6));const vals=S.values as number[];const lim=S.limits||{};const refs=[lim.warn,lim.alarm].filter((v:any)=>v!=null);let lo=Math.min(...vals,...refs),hi=Math.max(...vals,...refs);const sp=(hi-lo)||1;lo-=sp*0.12;hi+=sp*0.12;const st=S.step||2;const PXi=(i:number)=>x+40+(i/(vals.length-1))*(w-56);const PYv=(v:number)=>y+h-16-((v-lo)/(hi-lo))*(h-32);if(lim.warn){add(L(x+40,PYv(lim.warn),x+w-16,PYv(lim.warn),AMBER,1,"3 3",0.55));add(T(x+w-18,PYv(lim.warn)-3,"warn",9.5,AMBER,400,"end"));}if(lim.alarm){add(L(x+40,PYv(lim.alarm),x+w-16,PYv(lim.alarm),ORANGE,1,"3 3",0.55));add(T(x+w-18,PYv(lim.alarm)-3,"alarm",9.5,"#f7b06a",400,"end"));}const ci=Math.min(vals.length-1,Math.round(t/st));add(L(PXi(ci),y+10,PXi(ci),y+h-14,INK,1,undefined,0.7));const pts=vals.map((v,i)=>[PXi(i),PYv(v)] as [number,number]);add(P(pts.slice(0,ci+1),CYAN,2.4));add(P(pts.slice(ci),CYAN,2,"none",0.4));add(CI(PXi(ci),PYv(vals[ci]),3.4,CYAN2,BG,1.2));add(T(x+12,y+20,name,12,DIM,600));add(T(x+w-16,y+20,`${vals[ci]} ${unit}`,13,INK,700,"end",MONO));add(T(PXi(ci)+6,y+h-4,state.clock,9.5,INK,600,"start",MONO));};
 const inst:Record<string,[string,string]>={"PT-GM-104":["PT-GM-104 · Battery-4 riser pressure","kPa"],"GD-CO4-203":["GD-CO4-203 · basement CO (chamber A)","ppm"],"PT-GM-103":["PT-GM-103 · calibration under test","kPa"],"GD-CO3-208":["GD-CO3-208 · Battery-3 basement CO","ppm"]};
 if(sids[0]&&inst[sids[0]])trend(tx+18,cyT+4,tw-36,th-10,sids[0],inst[sids[0]][0],inst[sids[0]][1]);
 if(sids[1]&&inst[sids[1]])trend(tx+18,cyT+4+th,tw-36,th-10,sids[1],inst[sids[1]][0],inst[sids[1]][1]);
 // ---- footer ----
 const fy=H-46;add(R(24,fy,W-48,32,CARD2,5,LINE));add(T(40,fy+21,"KAVACH · The digital armour for zero-harm industrial operations",12,DIM,500));add(T(W-40,fy+21,"All data synthetic — a composite inspired by publicly reported incidents. No real plant data.",11,FAINT,400,"end"));
 return s.join("");
}
function baselineZone(zid:string,state:any):number{
 // baseline "risk" = worst sensor status in the zone mapped to a pseudo-score
 let worst=0;for(const sd of Object.values(state.sensors) as any[]){if(sd.zone!==zid)continue;const m={ok:0,warn:35,alarm:70,high:100}[sd.status as string]??0;worst=Math.max(worst,m);}return worst;
}

// ============================================================ PAGE
export default function ControlRoom(){
 const [scenario,setScenario]=useState("vizag_replay");
 const [mode,setMode]=useState<"kavach"|"baseline">("kavach");
 const [snap,setSnap]=useState<any>(null);
 const [rs,setRs]=useState<any>(null);
 const [metrics,setMetrics]=useState<any>(null);
 const [alerts,setAlerts]=useState<any[]>([]);
 const [series,setSeries]=useState<Record<string,any>>({});
 const [scenarios,setScenarios]=useState<{id:string;title:string}[]>([]);
 const [tip,setTip]=useState<{t:string;b:string;x:number;y:number}|null>(null);
 const [wsOn,setWsOn]=useState(false);
 const wsRef=useRef<WebSocket|null>(null);const retry=useRef<any>(null);
 const STEP=2;

 // ---- offline fallback -------------------------------------------------
 // Live WebSocket is the primary path and gives the real streaming system.
 // If no backend is reachable (a hosted judge link, a cold-started free dyno,
 // or simply no API configured) we fall back to precomputed frames shipped in
 // /public/demo — identical numbers, played back locally. The demo therefore
 // cannot go blank in front of a jury.
 const offline=useRef<any>(null);const tick=useRef<any>(null);
 const local=useRef({t:0,playing:false,speed:2});
 const paint=useCallback(()=>{const d=offline.current;if(!d)return;
  const t=Math.max(0,Math.min(d.duration,Math.round(local.current.t)));const f=d.frames[t];if(!f)return;
  setSnap({state:f.state,risk:f.risk,session:{scenario:d.scenario,cursor:t,playing:local.current.playing,speed:local.current.speed}});},[]);
 const goOffline=useCallback((sc:string)=>{
  fetch(`/demo/${sc}.json`).then(r=>r.ok?r.json():Promise.reject()).then(d=>{
   offline.current=d;setWsOn(false);
   setRs(d.risk_series);setMetrics(d.metrics);setAlerts(d.alerts||[]);
   setSeries(Object.fromEntries(Object.entries(d.series||{}).map(([k,v]:any)=>[k,{values:v.values,limits:v.limits,step:v.step??STEP}])));
   setScenarios(prev=>prev.length?prev:[{id:d.scenario,title:d.title}]);
   local.current={t:OPEN_T[sc]??0,playing:false,speed:2};paint();
   if(tick.current)clearInterval(tick.current);
   tick.current=setInterval(()=>{const L=local.current;if(!L.playing)return;
    L.t=Math.min(offline.current.duration,L.t+L.speed*0.25);
    if(L.t>=offline.current.duration)L.playing=false;paint();},250);
  }).catch(()=>{});
 },[paint]);

 useEffect(()=>{fetch(`${API}/api/scenarios`).then(r=>r.json()).then(setScenarios)
   .catch(()=>fetch(`/demo/index.json`).then(r=>r.json()).then(setScenarios).catch(()=>{}));},[]);
 useEffect(()=>{let closed=false;setSnap(null);setSeries({});offline.current=null;
  if(tick.current){clearInterval(tick.current);tick.current=null;}
  if(API){
   fetch(`${API}/api/risk/series?scenario=${scenario}&step=${STEP}`).then(r=>r.json()).then(setRs).catch(()=>{});
   fetch(`${API}/api/metrics?scenario=${scenario}`).then(r=>r.json()).then(setMetrics).catch(()=>{});
   fetch(`${API}/api/risk/alerts?scenario=${scenario}`).then(r=>r.json()).then(d=>setAlerts((d.alerts||[]).filter((a:any)=>a.kind==="new"))).catch(()=>{});
   (SPARKS[scenario]||[]).forEach(sid=>fetch(`${API}/api/series?scenario=${scenario}&sensor=${sid}&step=${STEP}`).then(r=>r.json()).then(d=>setSeries(p=>({...p,[sid]:{values:d.values,limits:d.limits,step:STEP}}))).catch(()=>{}));
  }
  let opened=false,attempts=0;
  const connect=()=>{
   let ws:WebSocket;
   if(!WS){goOffline(scenario);return;}
   try{ws=new WebSocket(`${WS}/ws/stream?session_id=board-${scenario}&scenario=${scenario}`);}catch{goOffline(scenario);return;}
   wsRef.current=ws;
   ws.onopen=()=>{setWsOn(true);offline.current=null;if(tick.current){clearInterval(tick.current);tick.current=null;}
    if(!opened){opened=true;ws.send(JSON.stringify({action:"seek",value:OPEN_T[scenario]??0}));}};
   ws.onmessage=e=>setSnap(JSON.parse(e.data));
   ws.onclose=()=>{setWsOn(false);if(closed)return;
    attempts++;
    if(attempts>=2&&!offline.current)goOffline(scenario);      // backend unreachable
    retry.current=setTimeout(connect,attempts>=2?8000:1500);}; // keep trying quietly
   ws.onerror=()=>ws.close();};
  connect();
  const guard=setTimeout(()=>{if(!wsRef.current||wsRef.current.readyState!==WebSocket.OPEN)goOffline(scenario);},2500);
  return()=>{closed=true;clearTimeout(guard);if(retry.current)clearTimeout(retry.current);
   if(tick.current){clearInterval(tick.current);tick.current=null;}wsRef.current?.close();};
 },[scenario,goOffline]);
 const send=useCallback((action:string,value?:number)=>{
  if(wsRef.current?.readyState===WebSocket.OPEN){wsRef.current.send(JSON.stringify({action,value}));return;}
  const L=local.current;                                        // offline transport
  if(action==="play")L.playing=true;else if(action==="pause")L.playing=false;
  else if(action==="seek"&&value!=null)L.t=value;
  else if(action==="speed"&&value!=null)L.speed=value;
  paint();},[paint]);

 if(!snap||!rs||!metrics){return <div className="kv2-loading">INITIALISING CONTROL ROOM…</div>;}
 const state=snap.state,session=snap.session,risk=snap.risk;
 const scenarioTitle=scenarios.find(s=>s.id===scenario)?.title||scenario;
 const svg=buildBoard({state,risk,rs,metrics,series,mode,scenario,scenarioTitle,alerts});
 const dur=state.duration;const jumps=JUMPS[scenario]||[];

 const openTip=(i:number,el:HTMLElement)=>{const h=HOTSPOTS[i];const r=el.getBoundingClientRect();let x=r.left+18,y=r.top+8;const pw=360;if(x+pw>window.innerWidth-12)x=window.innerWidth-pw-12;if(y>window.innerHeight-220)y=window.innerHeight-220;setTip({t:h.t,b:h.b,x,y});};

 return (
  <div className="kv2-app">
   <div className="kv2-board">
    <svg viewBox="0 0 1680 1236" role="img" aria-label="KAVACH compound-risk board" dangerouslySetInnerHTML={{__html:svg}} />
    <div className="kv2-ov">
     {HOTSPOTS.map((h,i)=>(<button key={i} className="kv2-ihot" style={{left:`${h.x}%`,top:`${h.y}%`}} aria-label={h.t} onClick={e=>openTip(i,e.currentTarget)} />))}
    </div>
   </div>

   {tip&&(<div className="kv2-tip" style={{display:"block",left:tip.x,top:tip.y}}><button className="x" onClick={()=>setTip(null)}>✕</button><h4>{tip.t}</h4><p>{tip.b}</p></div>)}

   {/* transport */}
   <div className="cr-transport">
    <button className="cr-play" onClick={()=>send(session.playing?"pause":"play")} title={session.playing?"Pause":"Play"}>
     {session.playing?<svg width="14" height="14" viewBox="0 0 14 14"><rect x="2.5" y="2" width="3" height="10" rx="1" fill="currentColor"/><rect x="8.5" y="2" width="3" height="10" rx="1" fill="currentColor"/></svg>:<svg width="14" height="14" viewBox="0 0 14 14"><path d="M3.5 2.4 L11.5 7 L3.5 11.6 Z" fill="currentColor"/></svg>}
    </button>
    <div className="cr-seg" role="tablist">
     <button className={`cr-seg-btn baseline ${mode==="baseline"?"on":""}`} onClick={()=>setMode("baseline")}><span className="cr-seg-dot"/>Baseline</button>
     <button className={`cr-seg-btn kavach ${mode==="kavach"?"on":""}`} onClick={()=>setMode("kavach")}><span className="cr-seg-dot"/>KAVACH</button>
    </div>
    <div className="cr-speed"><span className="cr-label">Speed</span>
     <select className="cr-select" value={session.speed} onChange={e=>send("speed",Number(e.target.value))}>{[1,2,5,10,30,60].map(v=><option key={v} value={v}>{v}×</option>)}</select>
    </div>
    <div className="cr-scrubwrap">
     <div className="cr-track"/><div className="cr-fill" style={{width:`${(state.t/dur)*100}%`}}/>
     {alerts.map((a,i)=>(<span key={`a${i}`} className="cr-atick" title={`KAVACH ${a.clock}`} style={{left:`${(a.t/dur)*100}%`}}/>))}
     {metrics?.baseline?.first_uncleared_t!=null&&(<span className="cr-btick" title={`Baseline alarm ${metrics.baseline.first_uncleared_clock}`} style={{left:`${(metrics.baseline.first_uncleared_t/dur)*100}%`}}/>)}
     <input className="cr-range" type="range" min={0} max={dur} value={state.t} onChange={e=>send("seek",Number(e.target.value))}/>
    </div>
    <span className="cr-treadout cr-mono">{state.clock} · t={state.t}</span>
    <div className="cr-speed"><span className="cr-label">Scenario</span>
     <select className="cr-select" value={scenario} onChange={e=>setScenario(e.target.value)}>{scenarios.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select>
    </div>
    <span className={`conn ${wsOn?"on":""}`} title={wsOn?"live":"reconnecting"}/>
    <div className="cr-jumps">{jumps.map(j=>(<button key={j.t} className={`cr-jump ${j.hot?"hot":""}`} onClick={()=>send("seek",j.t)}>{j.label}</button>))}</div>
   </div>
  </div>
 );
}
