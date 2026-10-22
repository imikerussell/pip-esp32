import math, os, subprocess
OUT=os.path.dirname(os.path.abspath(__file__))  # writes next to this script; needs rsvg-convert; os.makedirs(OUT,exist_ok=True)
STATES=["idle","happy","surprised","dizzy","sad","love"]
LABEL={"idle":"idle / neutral","happy":"happy","surprised":"surprised (poked)","dizzy":"dizzy (shaken)","sad":"sad / worried","love":"excited / love"}
YEL="#FFD23F"; PINK="#FF4F8B"; TEAR="#6CC7FF"; WHITE="#FFFFFF"

def heart(cx,cy,s,fill,extra=""):
    return (f'<path d="M{cx:.1f},{cy+0.42*s:.1f} C{cx-0.62*s:.1f},{cy+0.02*s:.1f} {cx-0.55*s:.1f},{cy-0.52*s:.1f} {cx:.1f},{cy-0.22*s:.1f} '
            f'C{cx+0.55*s:.1f},{cy-0.52*s:.1f} {cx+0.62*s:.1f},{cy+0.02*s:.1f} {cx:.1f},{cy+0.42*s:.1f} Z" fill="{fill}" {extra}/>')
def sparkle(cx,cy,r,fill):
    return (f'<path d="M{cx},{cy-r} Q{cx},{cy} {cx+r},{cy} Q{cx},{cy} {cx},{cy+r} Q{cx},{cy} {cx-r},{cy} Q{cx},{cy} {cx},{cy-r} Z" fill="{fill}"/>')
def spiral(cx,cy,R,col,w,turns=2.3,flip=1):
    pts=[]; n=60
    for i in range(n+1):
        t=i/n; a=flip*t*turns*2*math.pi; r=R*t
        pts.append(f"{cx+r*math.cos(a):.1f},{cy+r*math.sin(a):.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'
def arc_stroke(d,col,w): return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'
def teardrop(cx,cy,s,fill):
    return f'<path d="M{cx},{cy-s} Q{cx+0.75*s},{cy+0.1*s} {cx+0.55*s},{cy+0.45*s} A{0.6*s},{0.6*s} 0 0 1 {cx-0.55*s},{cy+0.45*s} Q{cx-0.75*s},{cy+0.1*s} {cx},{cy-s} Z" fill="{fill}"/>'

# ---------- generic eyes / mouths ----------
def eyes(state,E,r,ink,style="dot",hl=WHITE):
    o=[]
    for i,(x,y) in enumerate(E):
        side=-1 if i==0 else 1   # -1 left eye, +1 right eye
        if state=="idle":
            if style=="lid":   # sleepy content closed eyes
                o.append(arc_stroke(f"M{x-r*1.15},{y-r*0.2} Q{x},{y+r*1.2} {x+r*1.15},{y-r*0.2}",ink,r*0.5))
            elif style=="pill":
                o.append(f'<rect x="{x-r*0.62}" y="{y-r*1.15}" width="{r*1.24}" height="{r*2.3}" rx="{r*0.62}" fill="{ink}"/>')
            else:
                o.append(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r*1.18}" fill="{ink}"/>')
                o.append(f'<circle cx="{x-r*0.32}" cy="{y-r*0.42}" r="{r*0.36}" fill="{hl}"/>')
        elif state=="happy":
            o.append(arc_stroke(f"M{x-r*1.1},{y+r*0.45} Q{x},{y-r*1.45} {x+r*1.1},{y+r*0.45}",ink,r*0.58))
        elif state=="surprised":
            R=r*1.45
            if style=="pill":
                o.append(f'<circle cx="{x}" cy="{y}" r="{R}" fill="none" stroke="{ink}" stroke-width="{r*0.42}"/>')
                o.append(f'<circle cx="{x}" cy="{y}" r="{r*0.42}" fill="{ink}"/>')
            else:
                o.append(f'<circle cx="{x}" cy="{y}" r="{R}" fill="{ink}"/>')
                o.append(f'<circle cx="{x-R*0.3}" cy="{y-R*0.32}" r="{R*0.34}" fill="{hl}"/>')
                o.append(f'<circle cx="{x+R*0.35}" cy="{y+R*0.35}" r="{R*0.14}" fill="{hl}"/>')
        elif state=="dizzy":
            o.append(spiral(x,y,r*1.35,ink,r*0.36,flip=side))
        elif state=="sad":
            if style=="pill":
                o.append(f'<path d="M{x-r*0.75},{y-r*0.2+side*r*0.0} L{x+r*0.75},{y-r*0.2} L{x+r*0.75},{y+r*0.9} A{r*0.75},{r*0.75} 0 0 1 {x-r*0.75},{y+r*0.9} Z" fill="{ink}" transform="rotate({-side*14} {x} {y})"/>')
            else:
                o.append(f'<ellipse cx="{x}" cy="{y+r*0.15}" rx="{r*0.95}" ry="{r*1.05}" fill="{ink}"/>')
                o.append(f'<circle cx="{x-r*0.3}" cy="{y-r*0.2}" r="{r*0.4}" fill="{hl}"/>')
                o.append(f'<circle cx="{x+r*0.35}" cy="{y+r*0.45}" r="{r*0.18}" fill="{hl}"/>')
            # worried brows: inner end raised
            ix=x-side*r*0.0
            o.append(arc_stroke(f"M{x+side*r*1.15},{y-r*1.55} L{x-side*r*0.9},{y-r*2.3}",ink,r*0.32))
        elif state=="love":
            o.append(heart(x,y,r*2.9,PINK))
            o.append(f'<circle cx="{x-r*0.62}" cy="{y-r*0.45}" r="{r*0.28}" fill="{WHITE}"/>')
    return "".join(o)

def mouth(state,mx,my,m,ink,inner="#FF5C8A",style="smile"):
    if state=="idle":
        if style=="cat":
            return arc_stroke(f"M{mx-m*1.4},{my} Q{mx-m*0.7},{my+m*1.0} {mx},{my} Q{mx+m*0.7},{my+m*1.0} {mx+m*1.4},{my}",ink,m*0.38)
        if style=="flat":
            return arc_stroke(f"M{mx-m},{my} L{mx+m},{my}",ink,m*0.42)
        return arc_stroke(f"M{mx-m},{my} Q{mx},{my+m*0.9} {mx+m},{my}",ink,m*0.4)
    if state=="happy" or state=="love":
        k=1.0 if state=="happy" else 0.85
        w=1.6*m*k; d=2.4*m*k
        return (f'<path d="M{mx-w},{my} Q{mx},{my+d} {mx+w},{my} Z" fill="{ink}" stroke="{ink}" stroke-width="{m*0.3}" stroke-linejoin="round"/>'
                f'<ellipse cx="{mx}" cy="{my+d*0.36}" rx="{w*0.45}" ry="{d*0.13}" fill="{inner}"/>')
    if state=="surprised":
        return f'<ellipse cx="{mx}" cy="{my+m*0.4}" rx="{m*0.62}" ry="{m*0.85}" fill="{ink}"/>'
    if state=="dizzy":
        s=m*0.75
        return arc_stroke(f"M{mx-2*s},{my} q{s*0.5},{-s*0.7} {s},0 t{s},0 t{s},0 t{s},0",ink,m*0.36)
    if state=="sad":
        return arc_stroke(f"M{mx-m},{my+m*0.55} Q{mx},{my-m*0.45} {mx+m},{my+m*0.55}",ink,m*0.4)

def cheeks(state,E,dy,rx,col):
    if state=="sad": return ""
    k=1.25 if state=="love" else 1.0
    op=1.0 if state in("love","happy") else 0.75
    return "".join(f'<ellipse cx="{x+(-1 if i==0 else 1)*rx*0.55}" cy="{y+dy}" rx="{rx*k}" ry="{rx*0.55*k}" fill="{col}" opacity="{op}"/>' for i,(x,y) in enumerate(E))

def extras(state, top_y, accent=YEL, love=((98,None,44),(386,None,56),(410,None,30)), mid_star=True):
    o=[]
    if state=="surprised":   # burst lines, spaced so they never read as a glyph
        for sx in (-1,1):
            bx=240+sx*128; by=top_y+34
            for a in (-34,0,34):
                ang=math.radians(-90+sx*42+a); L1=34; L2=66
                o.append(arc_stroke(f"M{bx+L1*math.cos(ang):.1f},{by+L1*math.sin(ang):.1f} L{bx+L2*math.cos(ang):.1f},{by+L2*math.sin(ang):.1f}",accent,10))
    if state=="dizzy":
        o.append(f'<ellipse cx="240" cy="{top_y-8}" rx="120" ry="26" fill="none" stroke="{accent}" stroke-width="4" stroke-dasharray="6 12" opacity="0.55"/>')
        for (x,y,r) in ((130,top_y-8,20),(240,top_y+18,15),(350,top_y-16,22)):
            if x==240 and not mid_star: continue
            o.append(sparkle(x,y,r,accent))
    if state=="happy":
        for (x,y,r) in ((92,top_y+10,16),(392,top_y+30,12),(380,top_y-12,8)):
            o.append(sparkle(x,y,r,accent))
    if state=="love":
        dflt=(top_y+15,top_y-5,top_y+60)
        for (x,y,s),dy in zip(love,dflt):
            o.append(heart(x,y if y is not None else dy,s,PINK))
    return "".join(o)

def pose(state):
    # whole-character transform per state (the 'drama' in body language)
    return {"idle":"",
            "happy":"translate(0,-10)",
            "surprised":"translate(240,250) scale(0.96,1.06) translate(-240,-250) translate(0,-14)",
            "dizzy":"rotate(-9 240 260)",
            "sad":"translate(240,410) scale(1.04,0.95) translate(-240,-410) translate(0,8)",
            "love":"translate(0,-6)"}[state]

# ---------- concepts ----------
def mochi(state):
    body="#FFEEF3"; shade="#F6CFDC"; ink="#3B2235"; blush="#FF8FB0"
    E=[(178,262),(302,262)]
    g=[f'<ellipse cx="240" cy="420" rx="150" ry="16" fill="#2A1A22"/>',
       f'<path d="M66,338 C66,170 150,108 240,108 C330,108 414,170 414,338 C414,402 360,414 240,414 C120,414 66,402 66,338 Z" fill="{body}"/>',
       f'<path d="M86,350 C110,392 170,398 240,398 C310,398 370,392 394,350 C380,404 330,414 240,414 C150,414 100,404 86,350 Z" fill="{shade}"/>',
       f'<ellipse cx="160" cy="160" rx="34" ry="18" fill="#FFFFFF" transform="rotate(-25 160 160)"/>',
       cheeks(state,E,46,34,blush), eyes(state,E,21,ink), mouth(state,240,304,20,ink)]
    if state=="sad": g.append(teardrop(308,322,18,TEAR))
    return f'<g transform="{pose(state)}">{"".join(g)}</g>'+extras(state,96)

def bolt(state):
    head="#DCE3EE"; edge="#9AA7BC"; visor="#0E1424"; glow="#3DF5FF"; bolt_c="#FF6B6B"
    bulb={"love":PINK,"sad":TEAR,"dizzy":"#B07CFF","surprised":"#FFFFFF"}.get(state,YEL)
    E=[(192,252),(288,252)]
    ant_tilt={"dizzy":24,"surprised":0,"sad":-18}.get(state,0)
    g=[f'<g transform="rotate({ant_tilt} 240 116)"><line x1="240" y1="116" x2="240" y2="80" stroke="{edge}" stroke-width="10" stroke-linecap="round"/>'
       f'<circle cx="240" cy="68" r="19" fill="{bulb}"/>'
       + (f'<circle cx="240" cy="68" r="30" fill="{bulb}" opacity="0.25"/>' if state in("love","happy") else "") + '</g>',
       f'<rect x="62" y="218" width="30" height="76" rx="12" fill="{bolt_c}"/><rect x="388" y="218" width="30" height="76" rx="12" fill="{bolt_c}"/>',
       f'<rect x="80" y="112" width="320" height="300" rx="86" fill="{head}"/>',
       f'<clipPath id="hc"><rect x="80" y="112" width="320" height="300" rx="86"/></clipPath><rect x="80" y="352" width="320" height="60" fill="{edge}" opacity="0.35" clip-path="url(#hc)"/>',
       f'<rect x="112" y="164" width="256" height="184" rx="64" fill="{visor}"/>',
       f'<rect x="132" y="178" width="70" height="14" rx="7" fill="#FFFFFF" opacity="0.18"/>']
    inner="#0E1424"
    if state in("idle","happy","love"):
        g.append(cheeks(state,E,52,22,"#FF6FAE"))
    g.append(eyes(state,E,24,glow,"pill"))
    g.append(mouth(state,240,302,17,glow,inner=visor,style="flat" if state=="idle" else "smile"))
    if state=="sad": g.append(teardrop(300,316,13,TEAR))
    return f'<g transform="{pose(state)}">{"".join(g)}</g>'+extras(state,70 if state!="dizzy" else 52, mid_star=False)

def boo(state):
    body="#EEE8FF"; shade="#CFC4F5"; ink="#231A3D"; blush="#FF9EC4"
    E=[(196,226),(284,226)]
    def ghost(fill):
        return (f'<path d="M108,250 C108,146 168,86 240,86 C312,86 372,146 372,250 L372,384 '
                f'Q339,438 306,384 Q273,342 240,384 Q207,438 174,384 Q141,342 108,384 Z" fill="{fill}"/>')
    g=[f'<ellipse cx="240" cy="438" rx="112" ry="13" fill="#1C1830"/>',
       ghost(body),
       f'<path d="M340,150 C368,190 372,230 372,250 L372,384 Q339,438 306,384 Q330,330 340,150 Z" fill="{shade}"/>',
       f'<ellipse cx="172" cy="150" rx="26" ry="14" fill="#FFFFFF" transform="rotate(-35 172 150)"/>',
       cheeks(state,E,52,26,blush),
       eyes(state,E,20,ink), mouth(state,240,276,17,ink)]
    if state=="sad": g.append(teardrop(290,288,16,TEAR))
    return f'<g transform="{pose(state)}">{"".join(g)}</g>'+extras(state,74)

def mimi(state):
    fur="#FFB347"; inner_ear="#FF7E6B"; muzzle="#FFE3B8"; ink="#3A2318"; nose="#FF6F91"; stripe="#E8862A"; whisk="#FFE3B8"
    E=[(180,262),(300,262)]
    ear_rot={"sad":(-28,28),"surprised":(8,-8),"dizzy":(-6,22)}.get(state,(0,0))
    def ear(x,rot,mirror):
        s=-1 if mirror else 1
        p=f"M{x-60*s},{200} L{x-22*s},{88} L{x+50*s},{168} Z"
        pi=f"M{x-38*s},{184} L{x-20*s},{122} L{x+22*s},{170} Z"
        return (f'<g transform="rotate({rot} {x} 190)"><path d="{p}" fill="{fur}" stroke="{fur}" stroke-width="26" stroke-linejoin="round"/>'
                f'<path d="{pi}" fill="{inner_ear}" stroke="{inner_ear}" stroke-width="10" stroke-linejoin="round"/></g>')
    g=[ear(140,ear_rot[0],False), ear(340,ear_rot[1],True),
       f'<ellipse cx="240" cy="272" rx="172" ry="138" fill="{fur}"/>',
       arc_stroke("M222,150 L226,180",stripe,12)+arc_stroke("M240,146 L240,184",stripe,12)+arc_stroke("M258,150 L254,180",stripe,12),
       f'<ellipse cx="240" cy="324" rx="70" ry="48" fill="{muzzle}"/>']
    for sy,dy in ((312,-10),(334,6)):
        g.append(arc_stroke(f"M{120},{sy} L{40},{sy+dy}",whisk,6)+arc_stroke(f"M{360},{sy} L{440},{sy+dy}",whisk,6))
    g.append(cheeks(state,E,48,26,"#FF7E8E"))
    g.append(eyes(state,E,22,ink,"lid" if state=="idle" else "dot"))
    g.append(f'<path d="M228,300 L252,300 L240,314 Z" fill="{nose}" stroke="{nose}" stroke-width="8" stroke-linejoin="round"/>')
    st="cat" if state in("idle",) else "smile"
    g.append(mouth(state,240,328 if state!="idle" else 324,15,ink,style=st))
    if state=="sad": g.append(teardrop(306,300,16,TEAR))
    if state=="idle":   # sleepy 'z' bubbles as circles (no text)
        g.append(f'<circle cx="388" cy="132" r="10" fill="#9ED8FF" opacity="0.8"/><circle cx="410" cy="100" r="15" fill="#9ED8FF" opacity="0.6"/>')
    return f'<g transform="{pose(state)}">{"".join(g)}</g>'+extras(state,84,love=((62,150,44),(426,196,44),(408,120,30)))

# pixel pet: 18x18 grid of 22px, origin (42,42)
PX=22; OX=42; OY=42
BODY=[
"..oo..........oo..",
".o##o........o##o.",
".o###oooooooo###o.",
".o##############o.",
"o###hh###########o",
"o##hh############o",
"o##h#############o",
"o################o",
"o################o",
"o################o",
"o################o",
"o################o",
"o################o",
"o################o",
".o##############o.",
".o##############o.",
"..oo#oo####oo#oo..",
"....o..oooo..o....",
]
EYE={
 "idle":["kk","kk","kk"],
 "happy":[".kk.","k..k"],
 "surprised":["kkk","kwk","kkk"],
 "dizzy":["k.k",".k.","k.k"],
 "sad":["..kk","kk..","....",".kk.",".kk."],
 "love":[".r.r.","rrrrr",".rrr.","..r.."],
}
MOUTH={
 "idle":["k...k",".kkk."],
 "happy":["kkkkk","kpppk",".kpk."],
 "surprised":[".k.","k.k",".k."],
 "dizzy":["kk..kk","..kk.."],
 "sad":[".kk.","k..k"],
 "love":["k...k",".kkk."],
}
def pip(state):
    C={"#":"#7CF06B","o":"#2E9E4F","h":"#D4FFC4","k":"#10241A","w":"#FFFFFF","r":PINK,"p":"#FF7FA8","b":"#FF8FB0","t":TEAR,"y":YEL}
    cells={}
    for r,row in enumerate(BODY):
        for c,ch in enumerate(row):
            if ch!=".": cells[(c,r)]=ch
    def stamp(sp,c0,r0,mirror=False):
        for r,row in enumerate(sp):
            if mirror: row=row[::-1]
            for c,ch in enumerate(row):
                if ch!=".": cells[(c0+c,r0+r)]=ch
    e=EYE[state]; w=len(e[0])
    er=6 if state=="sad" else 7
    if state=="love": er=6
    lc=3 if state=="love" else 6-w//2; rc=18-lc-w
    stamp(e,lc,er); stamp(e,rc,er,mirror=True)
    m=MOUTH[state]; mw=len(m[0]); stamp(m,9-mw//2,12 if state=="sad" else 11)
    if state not in("sad",): 
        for c in (3,4,14,15):
            if state!="dizzy": cells[(c,10)]="b"
    if state=="sad": cells[(12,11)]="t"; cells[(12,12)]="t"; cells[(12,13)]="t"
    dy={"happy":-1,"surprised":-1,"sad":1}.get(state,0)
    o=[]
    for (c,r),ch in cells.items():
        o.append(f'<rect x="{OX+c*PX}" y="{OY+(r+dy)*PX}" width="{PX}" height="{PX}" fill="{C[ch]}"/>')
    # pixel extras
    def px(c,r,col): o.append(f'<rect x="{OX+c*PX}" y="{OY+r*PX}" width="{PX}" height="{PX}" fill="{col}"/>')
    if state=="happy":
        for (c,r) in ((0,4),(17,6)): px(c,r-1,YEL);px(c,r+1,YEL);px(c-1 if c else c+1,r,YEL)
    if state=="surprised":
        for (c,r) in ((6,0),(8,-0.5),(11,0)): px(c+0.5,r+0.6,YEL)
    if state=="dizzy":
        for (c,r) in ((6,0.3),(8.5,-0.2),(11,0.3)): px(c,r,YEL)
    if state=="love":
        pass
    g="".join(o)
    tr="translate(-22,0)" if state=="dizzy" else ""
    return f'<g transform="{tr}" shape-rendering="crispEdges">{g}</g>'

CONCEPTS=[("01","mochi","Mochi",mochi),("02","bolt","Bolt",bolt),("03","pip","Pip",pip),("04","boo","Boo",boo),("05","mimi","Mimi",mimi)]

def cell_svg(fn,state):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480"><rect width="480" height="480" fill="#000"/>{fn(state)}</svg>'

def sheet_svg(nn,title,fn):
    G=28; LB=58; TB=84; W=3*480+4*G; H=TB+2*(480+LB)+2*G
    o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       f'<rect width="{W}" height="{H}" fill="#141414"/>',
       f'<text x="{G}" y="56" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="38" font-weight="700" fill="#F2F2F2">{nn}  {title}</text>',
       f'<text x="{W-G}" y="56" text-anchor="end" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="22" fill="#8A8A8A">480 x 480 cells, 18 px safe margin dashed</text>']
    for i,s in enumerate(STATES):
        cx=G+(i%3)*(480+G); cy=TB+(i//3)*(480+LB+G)
        o.append(f'<svg x="{cx}" y="{cy}" width="480" height="480" viewBox="0 0 480 480"><rect width="480" height="480" rx="44" fill="#000"/>'
                 f'<rect x="18" y="18" width="444" height="444" rx="30" fill="none" stroke="#333" stroke-width="2" stroke-dasharray="8 8"/>{fn(s)}</svg>')
        o.append(f'<text x="{cx+240}" y="{cy+480+40}" text-anchor="middle" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="28" fill="#DADADA">{i+1}. {LABEL[s]}</text>')
    o.append("</svg>"); return "".join(o)

if __name__=="__main__":
    for nn,slug,title,fn in CONCEPTS:
        base=f"{OUT}/{nn}_{slug}"
        open(base+".svg","w").write(sheet_svg(nn,title,fn))
        subprocess.run(["rsvg-convert",base+".svg","-o",base+".png"],check=True)
        for s in STATES:
            p=f"{OUT}/.cells/{nn}_{slug}_{s}.svg"; os.makedirs(os.path.dirname(p),exist_ok=True)
            open(p,"w").write(cell_svg(fn,s))
            subprocess.run(["rsvg-convert","-w","480","-h","480",p,"-o",f"{base}_{s}.png"],check=True)
    print("ok")
