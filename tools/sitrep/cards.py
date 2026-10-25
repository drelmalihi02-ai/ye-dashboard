# Weekly SITREP (user request, 25 Oct 2026): 6 designed cards and a Telegram brief comparing the two
# Sunday-to-Saturday weeks that ended before the run day (Sana'a time, UTC+3). Built from the dashboard data
# in index.html. Run by .github/workflows/sitrep.yml every Sunday 08:00 Sana'a.
# Usage: python3 cards.py INDEX_HTML OUTDIR [YYYY-MM-DD run day]
# Writes 1_card.png ... 6_card.png, sitrep.txt (Telegram HTML) and status.json ({"ok": bool, "reason": ...}).
import json, os, re, sys, html, math, datetime as dt
from collections import Counter, defaultdict

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
d = json.loads(re.search(r'const D=(\{.*?\});\n', open(SRC).read()).group(1))
G = d['gov']
INC = {"Artillery", "Rockets", "Air strike", "Drone", "Unspecified attack", "Ground operation", "PLC shelling", "PLC sniper fire"}
SAUDI = {"Artillery", "Rockets", "Air strike", "Drone", "Unspecified attack"}
PLC = {"PLC shelling", "PLC sniper fire"}
TODAY = dt.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else (dt.datetime.utcnow() + dt.timedelta(hours=3)).date()
B2 = TODAY - dt.timedelta(days=(TODAY.weekday() - 5) % 7 or 7)   # last Saturday
A2 = B2 - dt.timedelta(days=6); A1 = A2 - dt.timedelta(days=7); B1 = A2 - dt.timedelta(days=1)
DAYS = [(A1 + dt.timedelta(days=i)).isoformat() for i in range(14)]
W1, W2 = set(DAYS[:7]), set(DAYS[7:])
# freshness: the data cut-off must reach late Saturday (week 2 read)
_cut = dt.datetime.strptime(d['cut'], "%d %b %Y, %H:%M")
FRESH = _cut >= dt.datetime.combine(B2, dt.time(21, 0))   # read to at least Saturday 21:00 Sana'a
e = lambda x: html.escape(str(x))
C = dict(ksa="#3987e5", plc="#c08a55", aa="#9085e9", k="#ff6b5e", i="#ff9f95", mute="#8d9098", fg="#f1f1ee", grid="#2a2c31", panel="#1b1c1f", acc="#e0743f", ok="#36c27a")


def side(cat):
    return "KSA" if cat in SAUDI else "PLC" if cat in PLC else "AA"


EV = [r for r in d['ev'] if r[1] in W1 | W2]
INCR = [r for r in EV if r[3] in INC]
OPS = [o for o in d['ops'] if o[0] in W1 | W2]
CL = [c for c in d['claims'] if c['date'] in W1 | W2]
TL = {k: v for k, v in d['tally'].items() if k in W1 | W2}


def wk(rows, W, f=lambda r: 1):
    return sum(f(r) for r in rows if r[1] in W)


def st(W):
    inc = [r for r in INCR if r[1] in W]
    ev = [r for r in EV if r[1] in W]
    air = [r for r in inc if r[3] == 'Air strike']
    ops = [o for o in OPS if o[0] in W]
    tl = [v for k, v in TL.items() if k in W]
    cl = [c for c in CL if c['date'] in W]
    dists = set()
    for r in inc:
        for x in r[4]:
            dists.add((r[0], x))
    tm = [r for r in inc if r[2]]
    night = sum(1 for r in tm if int(r[2][:2]) >= 18 or int(r[2][:2]) < 6)
    return dict(
        inc=len(inc), k=sum(r[6] for r in ev), i=sum(r[7] for r in ev),
        air=sum(r[9] or 1 for r in air), air_r=len(air),
        ksa_inc=sum(1 for r in inc if side(r[3]) == 'KSA'), plc=sum(1 for r in inc if side(r[3]) == 'PLC'), gnd=sum(1 for r in inc if side(r[3]) == 'AA'),
        tally=sum(tl), tally_n=len(tl), tally_avg=round(sum(tl) / len(tl)) if tl else 0,
        hits=sum(1 for o in ops if o[1] == 'KSA'), aaops=sum(1 for o in ops if o[1] in ('GROUND', 'SEA', 'AD')),
        intc=sum((c['n'] or 1) for c in cl if c['src'] == 'KSA' and c['cat'] == 'Interception'),
        plc_cl=sum(1 for c in cl if c['src'] == 'PLC'),
        govs=len({r[0] for r in inc}), dists=len(dists), night=night, timed=len(tm),
    )


S1, S2 = st(W1), st(W2)
json.dump({'w1': S1, 'w2': S2}, open(os.path.join(OUT, 'stats2w.json'), 'w'), indent=1)


def pct(a, b):
    return None if not b else round((a - b) * 100 / b)


def chip(a, b, good_down=True):
    p = pct(b, a)
    if p is None:
        return '<span class="ch fl">new</span>'
    if p == 0:
        return '<span class="ch fl">= 0%</span>'
    up = p > 0
    cls = ("bad" if up else "good") if good_down else ("flat2")
    return f'<span class="ch {cls}">{"▲" if up else "▼"} {abs(p)}%</span>'


CSS = """*{box-sizing:border-box}body{margin:0;width:1080px;background:#101114;font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;color:#f1f1ee}
.c{padding:52px 54px 44px;background:radial-gradient(110% 60% at 0% 0%,#3a2518 0%,transparent 55%),linear-gradient(160deg,#17181c,#101114);min-height:1350px;display:flex;flex-direction:column}
.ey{font:600 19px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:#e0743f;display:flex;justify-content:space-between}
.ey b{color:#8d9098;font-weight:500;letter-spacing:.06em}
h1{font:700 60px/1.04 "IBM Plex Sans Condensed","Arial Narrow",sans-serif;margin:14px 0 8px;letter-spacing:-.01em}
h1 em{font-style:normal;color:#ff7b72}
.sub{font-size:22px;color:#a9aab0;margin:0 0 26px;line-height:1.35}
.p{background:#1b1c1f;border:1px solid #2e3035;border-radius:18px;padding:22px 24px;margin-bottom:16px}
.p h2{margin:0 0 4px;font:600 25px "IBM Plex Sans Condensed",sans-serif}.p .s{margin:0 0 12px;font-size:16px;color:#8d9098}
svg text{font-family:"IBM Plex Mono",monospace}
.lg{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:17px;color:#c3c3bd;margin:4px 0 6px}.lg i{display:inline-block;width:14px;height:14px;border-radius:4px;margin-right:8px;vertical-align:-1px}
.ch{font:600 18px "IBM Plex Mono",monospace;border-radius:999px;padding:4px 11px;white-space:nowrap}
.ch.bad{background:#3a1d1b;color:#ff7b72}.ch.good{background:#15301f;color:#36c27a}.ch.fl,.ch.flat2{background:#26282c;color:#c3c3bd}
.f{margin-top:auto;display:flex;justify-content:space-between;align-items:center;padding-top:18px;font-size:16px;color:#6d7077;border-top:1px solid #26282c}
.f b{color:#c3c3bd;font-weight:600}
.k2{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.kb{background:#16171a;border:1px solid #2a2c31;border-radius:14px;padding:14px 16px}
.kb .l{font-size:16px;color:#a9aab0}.kb .v{font:700 40px/1.1 "IBM Plex Mono",monospace;letter-spacing:-.03em;margin-top:6px}.kb .v small{font-size:20px;color:#8d9098;font-weight:500}
.kb .d{margin-top:6px}
.read{font-size:21px;line-height:1.45;color:#d8d8d2}.read b{color:#fff}
"""


def page(eyebrow, n, title, sub, body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="c">
<div class="ey"><span>🇾🇪 {eyebrow}</span><b>{n}/6</b></div><h1>{title}</h1><p class="sub">{sub}</p>{body}
<div class="f"><span>Week 1 <b>{lab(DAYS[0])} to {lab(DAYS[6])}</b> · Week 2 <b>{lab(DAYS[7])} to {lab(DAYS[13])}</b> · Sana'a time</span><span><b>YE Paradise</b></span></div></div></body></html>'''


def lab(x):
    x = dt.date.fromisoformat(x)
    return f"{x.day} {x.strftime('%b')}"


# ---------------- Card 1: two weeks at a glance (versus rows)
def card1():
    rows = [
        ("Security incidents", S1['inc'], S2['inc'], True, ""),
        ("Civilians killed", S1['k'], S2['k'], True, ""),
        ("Civilians injured", S1['i'], S2['i'], True, ""),
        ("KSA air strikes counted", S1['air'], S2['air'], True, "≥"),
        ("AA/Houthi tally of KSA strikes, per reported day", S1['tally_avg'], S2['tally_avg'], True, ""),
        ("AA/Houthi strikes on Saudi territory", S1['hits'], S2['hits'], True, ""),
        ("KSA-reported interceptions", S1['intc'], S2['intc'], False, ""),
        ("AA/Houthi ground operations", S1['gnd'], S2['gnd'], True, ""),
        ("IRG/PLC attacks (shelling, snipers)", S1['plc'], S2['plc'], True, ""),
        ("Districts hit", S1['dists'], S2['dists'], True, ""),
    ]
    W = 972
    out = []
    y = 0
    for lbl, a, b, gd, pre in rows:
        m = max(a, b, 1)
        bw = 330
        out.append(f'<div class="vr"><div class="vl">{e(lbl)}</div><div class="vbs">'
                   f'<div class="vb"><span class="b1" style="width:{a/m*100:.0f}%"></span><em>{pre}{a:,}</em></div>'
                   f'<div class="vb"><span class="b2" style="width:{b/m*100:.0f}%"></span><em>{pre}{b:,}</em></div></div>'
                   f'<div class="vc">{chip(a, b, gd)}</div></div>')
    css = """<style>.vr{display:grid;grid-template-columns:290px 1fr 120px;column-gap:18px;align-items:center;padding:10px 0;border-bottom:1px solid #26282c}
.vr:last-child{border-bottom:0}.vl{font-size:19px;color:#d8d8d2;line-height:1.25}.vc{text-align:right}.vbs{display:flex;flex-direction:column;gap:4px;padding-right:70px}
.vb{display:flex;align-items:center;gap:10px;height:22px}.vb em{min-width:60px}.vb span{display:block;height:16px;border-radius:8px}.b1{background:#4a4d55}.b2{background:linear-gradient(90deg,#b5451b,#e0743f)}
.vb em{font:600 19px "IBM Plex Mono",monospace;font-style:normal}.vb:first-child em{color:#8d9098}</style>"""
    title = HEAD
    sub = (f"Incidents {S1['inc']} to {S2['inc']}. KSA air strikes counted {S1['air']} to {S2['air']}. "
           f"AA/Houthi target hits in Saudi Arabia {S1['hits']} to {S2['hits']}. IRG/PLC attacks {S1['plc']} to {S2['plc']}.")
    leg = f'<div class="lg"><span><i style="background:#4a4d55"></i>Week 1, {lab(DAYS[0])} to {lab(DAYS[6])}</span><span><i style="background:#e0743f"></i>Week 2, {lab(DAYS[7])} to {lab(DAYS[13])}</span><span style="color:#8d9098">Chip = change in week 2</span></div>'
    R = READ
    body = css + f'<div class="p">{leg}{"".join(out)}</div><div class="p"><h2>What changed</h2><div class="read">' + "".join(f"<p style='margin:10px 0'>{x}</p>" for x in R) + '</div></div>'
    return page("Yemen SITREP · two weeks at a glance", 1, title, sub, body)


# ---------------- Card 2: daily pulse
def card2():
    W, H = 922, 780
    PL, PR = 46, 6
    cw = (W - PL - PR) / 14
    by = {x: Counter() for x in DAYS}
    for r in INCR:
        by[r[1]][side(r[3])] += 1
    cas = {x: [0, 0] for x in DAYS}
    for r in EV:
        cas[r[1]][0] += r[6]; cas[r[1]][1] += r[7]
    air = Counter()
    for r in INCR:
        if r[3] == 'Air strike':
            air[r[1]] += r[9] or 1
    hits = Counter(o[0] for o in OPS if o[1] == 'KSA')
    mi = max(sum(v.values()) for v in by.values())
    mc = max(a + b for a, b in cas.values()) or 1
    ma = max(list(air.values()) + [1])
    top, h1 = 44, 340           # incidents block
    base = top + h1
    cb = base + 34              # casualties below (mirrored)
    h2 = 230
    sb = cb + h2 + 40           # strikes row
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%">']
    # week shading
    s.append(f'<rect x="{PL+7*cw}" y="0" width="{7*cw}" height="{H-20}" fill="#e0743f" opacity=".05" rx="8"/>')
    s.append(f'<text x="{PL+3.5*cw}" y="18" text-anchor="middle" fill="#8d9098" font-size="16">WEEK 1 · {S1["inc"]} incidents</text>')
    s.append(f'<text x="{PL+10.5*cw}" y="18" text-anchor="middle" fill="#e0743f" font-size="16">WEEK 2 · {S2["inc"]} incidents</text>')
    for v in range(0, mi + 1, 5):
        y = base - v / mi * h1
        s.append(f'<line x1="{PL}" x2="{W-PR}" y1="{y:.1f}" y2="{y:.1f}" stroke="#2a2c31" stroke-dasharray="3 5"/>')
        s.append(f'<text x="{PL-8}" y="{y+5:.1f}" text-anchor="end" fill="#6d7077" font-size="14">{v}</text>')
    for j, x in enumerate(DAYS):
        X = PL + j * cw + 6
        bw = cw - 12
        y = base
        for sd, col in (("KSA", C['ksa']), ("PLC", C['plc']), ("AA", C['aa'])):
            n = by[x][sd]
            if n:
                hh = n / mi * h1
                y -= hh
                s.append(f'<rect x="{X:.1f}" y="{y+1:.1f}" width="{bw:.1f}" height="{hh-2:.1f}" rx="4" fill="{col}"/>')
        tot = sum(by[x].values())
        s.append(f'<text x="{X+bw/2:.1f}" y="{y-8:.1f}" text-anchor="middle" fill="#f1f1ee" font-size="16" font-weight="600">{tot}</text>')
        # day label
        dd = dt.date.fromisoformat(x)
        s.append(f'<text x="{X+bw/2:.1f}" y="{base+23}" text-anchor="middle" fill="#a9aab0" font-size="15">{dd.day}</text>')
        # casualties mirrored
        k, i = cas[x]
        yk = k / mc * h2; yi = i / mc * h2
        if k:
            s.append(f'<rect x="{X:.1f}" y="{cb}" width="{bw:.1f}" height="{yk:.1f}" rx="3" fill="{C["k"]}"/>')
        if i:
            s.append(f'<rect x="{X:.1f}" y="{cb+yk:.1f}" width="{bw:.1f}" height="{yi:.1f}" rx="3" fill="{C["i"]}" opacity=".55"/>')
        if k or i:
            s.append(f'<text x="{X+bw/2:.1f}" y="{cb+yk+yi+18:.1f}" text-anchor="middle" fill="#ff9f95" font-size="14">{k}/{i}</text>')
        # strikes row: dot size = itemised air strikes, diamond = AA hits on KSA
        a = air[x]
        if a:
            r = 5 + 17 * math.sqrt(a / ma)
            s.append(f'<circle cx="{X+bw/2:.1f}" cy="{sb}" r="{r:.1f}" fill="{C["ksa"]}" opacity=".85"/>')
            s.append(f'<text x="{X+bw/2:.1f}" y="{sb+5}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{a}</text>')
        h = hits[x]
        if h:
            s.append(f'<rect x="{X+bw/2-12:.1f}" y="{sb+34}" width="24" height="24" rx="4" transform="rotate(45 {X+bw/2:.1f} {sb+46})" fill="{C["aa"]}"/>')
            s.append(f'<text x="{X+bw/2:.1f}" y="{sb+51}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{h}</text>')
    s.append(f'<text x="{PL-8}" y="{cb+12}" text-anchor="end" fill="#ff9f95" font-size="13">civ</text>')
    s.append(f'<text x="{PL-8}" y="{sb+5}" text-anchor="end" fill="#6fa8ef" font-size="13">air</text>')
    s.append(f'<text x="{PL-8}" y="{sb+51}" text-anchor="end" fill="#b0a8f0" font-size="13">KSA</text>')
    s.append(f'<text x="{PL}" y="{base+23}" text-anchor="end" fill="#6d7077" font-size="13">Oct</text>')
    s.append('</svg>')
    peak = max(DAYS, key=lambda x: sum(by[x].values()))
    pk = max(DAYS, key=lambda x: cas[x][0])
    leg = (f'<div class="lg"><span><i style="background:{C["ksa"]}"></i>KSA</span><span><i style="background:{C["plc"]}"></i>IRG/PLC</span>'
           f'<span><i style="background:{C["aa"]}"></i>AA/Houthis</span><span><i style="background:{C["k"]}"></i>Civilians killed</span>'
           f'<span><i style="background:{C["i"]};opacity:.6"></i>injured</span></div>'
           f'<div class="lg" style="color:#8d9098;font-size:15px"><span>● blue = KSA air strikes counted that day</span><span>◆ purple = AA/Houthi target hits in Saudi Arabia</span></div>')
    title = "Daily pulse: 14 days in one view"
    sub = f"Busiest day {lab(peak)} ({sum(by[peak].values())} incidents). Deadliest day {lab(pk)} ({cas[pk][0]} civilians killed). Bars above the line are incidents by attacker, bars below are civilian casualties."
    return page("Yemen SITREP · daily pulse", 2, title, sub, f'<div class="p">{leg}{"".join(s)}</div>')


# ---------------- Card 3: map of change
NAME = {'Amanat al-Asimah': 'sanaa', "Sana'a": 'sanaa', 'Lahij': 'lahj', 'Aden': 'aden', 'Al Hudaydah': 'hodeidah', "Ta'izz": 'taiz', 'Shabwah': 'shabwah',
        'Hadhramaut': 'hadramawt', 'Abyan': 'abyan', 'Al Jawf': 'jawf', 'Ibb': 'ibb', "Al Bayda'": 'bayda', "Ad Dali'": 'dhale', 'Al Mahwit': 'mahwit',
        "Sa'dah": 'saada', 'Hajjah': 'hajjah', 'Dhamar': 'dhamar', 'Amran': 'amran', 'Al Mahrah': 'mahrah', "Ma'rib": 'marib', 'Raymah': 'raymah', 'Socotra': 'socotra'}


def card3():
    g1, g2 = Counter(), Counter()
    k2 = Counter()
    for r in INCR:
        (g1 if r[1] in W1 else g2)[r[0]] += 1
    for r in EV:
        if r[1] in W2:
            k2[r[0]] += r[6]
    MW, MH = 920, 640
    x0, x1, y0, y1 = 42.4, 50.4, 12.4, 18.6   # west and central Yemen, where the incidents are
    kx = MW / (x1 - x0); ky = MH / (y1 - y0)
    k = min(kx, ky * 1.0)
    P = lambda lon, lat: ((lon - x0) * k, (y1 - lat) * k * 1.03)
    mx = max(list(g2.values()) + [1])
    s = [f'<svg viewBox="0 0 {MW} {MH}" width="100%"><rect width="{MW}" height="{MH}" rx="14" fill="#14202a"/>']
    cents = defaultdict(list)
    for nm, mp in d['adm1']:
        key = NAME.get(nm)
        n = g2.get(key, 0)
        f = "#22252a" if not n else f"rgba(224,116,63,{0.18+0.82*(n/mx)**0.6:.2f})"
        path = ""
        for poly in mp:
            for ring in poly:
                path += "M" + "L".join(f"{P(*p)[0]:.1f} {P(*p)[1]:.1f}" for p in ring) + "Z"
                if len(ring) > 20:
                    cents[key].append((sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring), len(ring)))
        s.append(f'<path d="{path}" fill="{f}" stroke="#101114" stroke-width="1.6"/>')
    # Saudi border hint
    s.append(f'<text x="{P(45.2,18.2)[0]:.0f}" y="{P(45.2,18.2)[1]:.0f}" fill="#4a4d55" font-size="15" letter-spacing="3">SAUDI ARABIA</text>')
    s.append(f'<text x="{P(42.55,14.0)[0]:.0f}" y="{P(42.55,14.0)[1]:.0f}" fill="#2f4656" font-size="14" letter-spacing="2" transform="rotate(-62 {P(42.55,14.0)[0]:.0f} {P(42.55,14.0)[1]:.0f})">RED SEA</text>')
    for key in set(g1) | set(g2):
        if key not in cents:
            continue
        c = max(cents[key], key=lambda t: t[2])
        if key == 'sanaa':
            c = (44.3, 15.45, 0)
        X, Y = P(c[0], c[1])
        a, b = g1.get(key, 0), g2.get(key, 0)
        if b < 2 and a < 2:
            continue
        dlt = b - a
        col = "#ff7b72" if dlt > 0 else "#36c27a" if dlt < 0 else "#c3c3bd"
        ar = "▲" if dlt > 0 else "▼" if dlt < 0 else "="
        s.append(f'<text x="{X:.0f}" y="{Y:.0f}" text-anchor="middle" fill="#fff" font-size="22" font-weight="700" paint-order="stroke" stroke="#101114" stroke-width="4">{b}</text>')
        s.append(f'<text x="{X:.0f}" y="{Y+20:.0f}" text-anchor="middle" fill="{col}" font-size="14" font-weight="600" paint-order="stroke" stroke="#101114" stroke-width="4">{ar}{abs(dlt) if dlt else ""}</text>')
    s.append('</svg>')
    # slope list
    keys = sorted(set(g1) | set(g2), key=lambda k_: -(g2.get(k_, 0) + g1.get(k_, 0) * .5))[:9]
    m = max([g1.get(x, 0) for x in keys] + [g2.get(x, 0) for x in keys] + [1])
    L = []
    for key in keys:
        a, b = g1.get(key, 0), g2.get(key, 0)
        L.append(f'<div class="sl"><span class="sn">{e(G.get(key,key))}</span><span class="sv">{a}</span>'
                 f'<span class="sb"><i class="o" style="left:{a/m*100:.0f}%"></i><i class="n" style="left:{b/m*100:.0f}%"></i><b style="left:{min(a,b)/m*100:.0f}%;width:{abs(b-a)/m*100:.0f}%;background:{"#ff7b72" if b>a else "#36c27a"}"></b></span>'
                 f'<span class="sv n2">{b}</span>{f"<span class=kk>{k2[key]} killed</span>" if k2.get(key) else "<span class=kk></span>"}</div>')
    css = """<style>.mg{display:block}.mg2{display:grid;grid-template-columns:1fr 1fr;column-gap:36px}
.sl{display:grid;grid-template-columns:110px 30px 1fr 34px;grid-template-rows:auto auto;column-gap:8px;align-items:center;margin:2px 0 12px}
.sn{font-size:17px;color:#d8d8d2}.sv{font:600 16px "IBM Plex Mono",monospace;color:#8d9098;text-align:right}.sv.n2{color:#fff;text-align:left}
.sb{position:relative;height:16px}.sb b{position:absolute;top:6px;height:4px;border-radius:2px}.sb i{position:absolute;top:2px;width:12px;height:12px;border-radius:50%;margin-left:-6px;z-index:2}
.sb i.o{background:#4a4d55}.sb i.n{background:#e0743f}.kk{grid-column:3/5;font:500 13px "IBM Plex Mono",monospace;color:#ff7b72;margin-top:2px}</style>"""
    rise = max(keys, key=lambda x: g2.get(x, 0) - g1.get(x, 0))
    fall = min(keys, key=lambda x: g2.get(x, 0) - g1.get(x, 0))
    title = "Where the violence moved"
    sub = ((f"{G[rise]} rose most (+{g2[rise]-g1.get(rise,0)}). " if g2.get(rise,0) > g1.get(rise,0) else "") + (f"{G[fall]} fell most ({g2.get(fall,0)-g1.get(fall,0)}). " if g2.get(fall,0) < g1.get(fall,0) else "") + 
           f"Sa'dah and Taiz carry {round((g2['saada']+g2['taiz'])*100/max(1,S2['inc']))}% of week 2 incidents.")
    body = css + f'''<div class="p"><div class="mg"><div>{"".join(s)}<div class="lg" style="font-size:15px;margin-top:10px"><span>Shade and number = week 2 incidents</span><span><b style="color:#ff7b72">▲</b>/<b style="color:#36c27a">▼</b> change on week 1</span></div></div>
</div></div><div class="p"><h2>Week 1 → week 2, by governorate</h2><p class="s"><span style="color:#8d9098">●</span> week 1 &nbsp; <span style="color:#e0743f">●</span> week 2 &nbsp; red line = rise, green = fall. Civilians killed in week 2 in red.</p><div class="mg2">{"".join(L)}</div></div>'''
    return page("Yemen SITREP · geography", 3, title, sub, body)


# ---------------- Card 4: civilian toll
def card4():
    ev = [r for r in EV if r[6] + r[7] > 0]
    kg = defaultdict(lambda: [0, 0, 0, 0])
    for r in ev:
        w = 0 if r[1] in W1 else 2
        kg[r[0]][w] += r[6]; kg[r[0]][w + 1] += r[7]
    keys = sorted(kg, key=lambda x: -(kg[x][0] + kg[x][2]) * 3 - (kg[x][1] + kg[x][3]))[:7]
    m = max(max(v[0] + v[1], v[2] + v[3]) for v in kg.values())
    rows = []
    for key in keys:
        v = kg[key]
        def bar(k, i, op):
            return (f'<span class="cb" style="opacity:{op}"><i style="width:{k/m*100:.1f}%;background:{C["k"]}"></i>'
                    f'<i style="width:{i/m*100:.1f}%;background:{C["i"]};opacity:.6"></i></span>')
        rows.append(f'<div class="cr"><span class="cn">{e(G[key])}</span><div>{bar(v[0], v[1], .45)}{bar(v[2], v[3], 1)}</div>'
                    f'<span class="cv"><span class="o">{v[0]}/{v[1]}</span><br>{v[2]}/{v[3]}</span></div>')
    dead = sorted(ev, key=lambda r: (-r[6], -r[7]))[:6]
    D = []
    for r in dead:
        place = dn_(", ".join(r[4][:2])) or (r[5] or "")
        who = {"KSA": "KSA", "PLC": "IRG/PLC", "AA": "AA/Houthis"}.get(side(r[3]), "") if r[3] in INC else ""
        loc = r[5] if r[5] and len(r[5]) < 48 else ""
        D.append(f'<div class="dr"><span class="dd">{lab(r[1])}</span><span class="dk">{r[6]}<small>/{r[7]}</small></span>'
                 f'<span class="dp"><b>{e(place)}</b>, {e(G[r[0]])}<br><small>{e(loc)}{" · " if loc and who else ""}{who} {e(r[3].lower()) if who else ""}</small></span></div>')
    css = """<style>.cr{display:grid;grid-template-columns:120px 1fr 90px;gap:12px;align-items:center;margin:10px 0}.cn{font-size:18px}
.cb{display:flex;height:14px;margin:3px 0;background:#26282c;border-radius:7px;overflow:hidden}.cb i{display:block;height:100%}
.cv{font:600 15px/1.25 "IBM Plex Mono",monospace;text-align:right;color:#ff9f95}.cv .o{color:#8d9098;font-weight:500}
.dr{display:grid;grid-template-columns:80px 90px 1fr;gap:12px;align-items:center;padding:11px 0;border-top:1px solid #26282c}.dr:first-of-type{border-top:0}
.dd{font:500 16px "IBM Plex Mono",monospace;color:#a9aab0}.dk{font:700 30px "IBM Plex Mono",monospace;color:#ff7b72}.dk small{font-size:17px;color:#ff9f95;font-weight:500}
.dp{font-size:18px;line-height:1.3}.dp small{font-size:14px;color:#8d9098}</style>"""
    tk = S1['k'] + S2['k']; ti = S1['i'] + S2['i']
    kpis = f'''<div class="k2" style="margin-bottom:16px"><div class="kb"><div class="l">Killed, 14 days</div><div class="v" style="color:#ff7b72">{tk}</div><div class="d">{chip(S1["k"],S2["k"])} <small style="color:#8d9098">{S1["k"]} → {S2["k"]}</small></div></div>
<div class="kb"><div class="l">Injured, 14 days</div><div class="v" style="color:#ff9f95">{ti}</div><div class="d">{chip(S1["i"],S2["i"])} <small style="color:#8d9098">{S1["i"]} → {S2["i"]}</small></div></div>
<div class="kb"><div class="l">Incidents with civilian casualties</div><div class="v">{len(ev)}</div><div class="d"><small style="color:#8d9098">of {S1["inc"]+S2["inc"]} incidents ({round(len(ev)*100/(S1["inc"]+S2["inc"]))}%)</small></div></div></div>'''
    title = f"Civilian toll: {tk} killed, {ti} injured"
    sub = f"Civilians only. Combatant tolls from either side are never counted. Killed {S1['k']} to {S2['k']}, injured {S1['i']} to {S2['i']}."
    body = css + kpis + f'''<div class="p"><h2>By governorate</h2><p class="s">Killed / injured. Faded bar week 1, bright bar week 2.</p>{"".join(rows)}</div>
<div class="p"><h2>Deadliest incidents in the 14 days</h2><p class="s">Killed / injured, as reported.</p>{"".join(D)}</div>'''
    return page("Yemen SITREP · civilians", 4, title, sub, body)


# ---------------- Card 5: air war vs retaliation
def card5():
    W, H = 922, 470
    PL = 40
    cw = (W - PL - 10) / 14
    air = Counter(); hits = Counter()
    for r in INCR:
        if r[3] == 'Air strike':
            air[r[1]] += r[9] or 1
    for o in OPS:
        if o[1] == 'KSA':
            hits[o[0]] += 1
    ma = max(list(air.values()) + list(TL.values()) + [1])
    mh = max(list(hits.values()) + [1])
    mid = 150
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%">']
    s.append(f'<text x="{PL}" y="16" fill="#b0a8f0" font-size="15">▲ AA/Houthi target hits in Saudi Arabia</text>')
    s.append(f'<text x="{PL}" y="{H-6}" fill="#6fa8ef" font-size="15">▼ KSA air strikes in Yemen: bar = counted in reports, outline = AA/Houthi daily tally</text>')
    for j, x in enumerate(DAYS):
        X = PL + j * cw + 7; bw = cw - 14
        h = hits[x]
        if h:
            hh = h / mh * 110
            s.append(f'<rect x="{X:.1f}" y="{mid-hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="4" fill="{C["aa"]}"/>')
            s.append(f'<text x="{X+bw/2:.1f}" y="{mid-hh-6:.1f}" text-anchor="middle" fill="#d8d2ff" font-size="15" font-weight="700">{h}</text>')
        t = TL.get(x)
        if t:
            th = t / ma * 220
            s.append(f'<rect x="{X-3:.1f}" y="{mid+10}" width="{bw+6:.1f}" height="{th:.1f}" rx="5" fill="none" stroke="#6fa8ef" stroke-width="2" stroke-dasharray="4 3"/>')
            s.append(f'<text x="{X+bw/2:.1f}" y="{mid+10+th+16:.1f}" text-anchor="middle" fill="#6fa8ef" font-size="13">{t}</text>')
        a = air[x]
        if a:
            ah = a / ma * 220
            s.append(f'<rect x="{X:.1f}" y="{mid+10}" width="{bw:.1f}" height="{ah:.1f}" rx="4" fill="{C["ksa"]}"/>')
            s.append(f'<text x="{X+bw/2:.1f}" y="{mid+10+ah/2+5:.1f}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{a}</text>' if ah > 18 else "")
        s.append(f'<text x="{X+bw/2:.1f}" y="{H-34}" text-anchor="middle" fill="#a9aab0" font-size="14">{int(x[8:])}</text>')
    s.append(f'<line x1="{PL}" x2="{W-10}" y1="{mid+5}" y2="{mid+5}" stroke="#4a4d55"/>')
    s.append(f'<line x1="{PL+7*cw}" x2="{PL+7*cw}" y1="20" y2="{H-26}" stroke="#4a4d55" stroke-dasharray="4 4"/>')
    s.append('</svg>')
    # Saudi target map
    MW, MH = 470, 420
    x0, x1, y0, y1 = 34.5, 56.0, 16.0, 32.5
    k = min(MW / (x1 - x0), MH / (y1 - y0))
    P = lambda lon, lat: ((lon - x0) * k, (y1 - lat) * k)
    m = [f'<svg viewBox="0 0 {MW} {MH}" width="100%"><rect width="{MW}" height="{MH}" rx="14" fill="#14202a"/>']
    for nm, mp in d['ksa']:
        p = ""
        for poly in mp:
            for ring in poly:
                p += "M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z"
        m.append(f'<path d="{p}" fill="#22252a" stroke="#33363c" stroke-width="1"/>')
    for nm, mp in d['adm1']:
        p = ""
        for poly in mp:
            for ring in poly:
                p += "M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z"
        m.append(f'<path d="{p}" fill="#3a2518" stroke="#3a2518" stroke-width=".6"/>')
    sites = defaultdict(lambda: [0, 0, ""])
    for o in OPS:
        if o[1] == 'KSA' and o[6] is not None:
            key = (round(o[6], 1), round(o[7], 1))
            sites[key][0 if o[0] in W1 else 1] += 1
            sites[key][2] = o[2].split(' (')[0]
    for (lon, lat), (a, b, nm) in sorted(sites.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        X, Y = P(lon, lat)
        r = 6 + 5 * math.sqrt(a + b)
        col = C['aa'] if b else "#5d578f"
        m.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{r:.1f}" fill="{col}" fill-opacity=".8" stroke="#101114" stroke-width="1.5"/>')
        m.append(f'<text x="{X:.1f}" y="{Y+4:.1f}" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">{a+b}</text>')
    labels = {"Riyadh": (46.7, 24.7), "Dammam": (50.1, 26.4), "Yanbu": (38.06, 24.09), "Jeddah": (39.2, 21.5), "Najran": (44.2, 17.5), "Khamis": (42.8, 18.3), "Rabigh": (39.0, 22.8)}
    for t, (lon, lat) in labels.items():
        X, Y = P(lon, lat)
        m.append(f'<text x="{X+14:.0f}" y="{Y-10:.0f}" fill="#a9aab0" font-size="13">{t}</text>')
    m.append('</svg>')
    gap1 = round(S1['air'] * 100 / S1['tally']) if S1['tally'] else 0
    gap2 = round(S2['air'] * 100 / S2['tally']) if S2['tally'] else 0
    css = "<style>.ag{display:grid;grid-template-columns:470px 1fr;gap:20px}.ag .kb{margin-bottom:12px}</style>"
    kb = lambda l, a, b, extra="", g=True: f'<div class="kb"><div class="l">{l}</div><div class="v">{b} <small>vs {a}</small></div><div class="d">{chip(a,b,g)} {extra}</div></div>'
    side_ = (kb("AA/Houthi target hits in Saudi Arabia", S1['hits'], S2['hits']) +
             kb("KSA-reported interceptions", S1['intc'], S2['intc'], '<small style="color:#8d9098">missiles and drones</small>', False) +
             f'<div class="kb"><div class="l">Coverage gap: strikes counted in reports as a share of the AA/Houthi tally</div><div class="v">{gap2}% <small>vs {gap1}%</small></div><div class="d"><small style="color:#8d9098">Week 2 tally covers {S2["tally_n"]} of 7 days</small></div></div>')
    title = "Air war and retaliation"
    sub = f"KSA air strikes counted in reports: {S1['air']} to {S2['air']}. AA/Houthi target hits in Saudi Arabia: {S1['hits']} to {S2['hits']}."
    body = css + f'''<div class="p">{"".join(s)}</div><div class="p"><div class="ag"><div>{"".join(m)}<div class="lg" style="font-size:14px;margin-top:8px"><span><i style="background:{C["aa"]}"></i>hit in week 2</span><span><i style="background:#5d578f"></i>week 1 only</span><span>number = target hits, 14 days</span></div></div><div>{side_}</div></div></div>'''
    return page("Yemen SITREP · air war", 5, title, sub, body)


# ---------------- Card 6: when and where (clock grid + hotspots)
def card6():
    grid = defaultdict(int)
    for r in INCR:
        if r[2]:
            grid[(r[1], int(r[2][:2]))] += 1
    mg = max(list(grid.values()) + [1])
    W = 922; PL = 70; cw = (W - PL - 6) / 24; rh = 26
    s = [f'<svg viewBox="0 0 {W} {14*rh+50}" width="100%">']
    for h in range(24):
        X = PL + h * cw
        night = h >= 18 or h < 6
        if h % 3 == 0:
            s.append(f'<text x="{X+cw/2:.1f}" y="16" text-anchor="middle" fill="#8d9098" font-size="13">{h:02d}</text>')
    for j, x in enumerate(DAYS):
        Y = 26 + j * rh + (10 if j >= 7 else 0)
        s.append(f'<text x="{PL-10}" y="{Y+17}" text-anchor="end" fill="{"#e0743f" if j>=7 else "#a9aab0"}" font-size="14">{lab(x)}</text>')
        for h in range(24):
            n = grid[(x, h)]
            night = h >= 18 or h < 6
            col = "#1f2125" if not n else f"rgba(255,123,114,{0.25+0.75*n/mg:.2f})"
            s.append(f'<rect x="{PL+h*cw+1.5:.1f}" y="{Y+1.5}" width="{cw-3:.1f}" height="{rh-3}" rx="4" fill="{col}"{" stroke=\"#2c2f45\"" if night and not n else ""}/>')
            if n > 1:
                s.append(f'<text x="{PL+h*cw+cw/2:.1f}" y="{Y+17}" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">{n}</text>')
    s.append('</svg>')
    n1 = round(S1['night'] * 100 / max(1, S1['timed'])); n2 = round(S2['night'] * 100 / max(1, S2['timed']))
    # hotspots
    c1, c2 = Counter(), Counter()
    for r in INCR:
        for x in set(r[4]):
            (c1 if r[1] in W1 else c2)[(r[0], x)] += 1
    top = sorted(set(c1) | set(c2), key=lambda k_: -(c1[k_] + c2[k_]))[:10]
    m = max(max(c1[k_], c2[k_]) for k_ in top)
    H = []
    for key in top:
        a, b = c1[key], c2[key]
        H.append(f'<div class="hr"><span class="hn">{e(dn_(key[1]))} <small>{e(G[key[0]])}</small></span>'
                 f'<span class="hb"><i style="width:{a/m*100:.0f}%;background:#4a4d55"></i></span><span class="hv o">{a}</span>'
                 f'<span class="hb"><i style="width:{b/m*100:.0f}%;background:#e0743f"></i></span><span class="hv">{b}</span></div>')
    css = """<style>.hr{display:grid;grid-template-columns:300px 1fr 36px 1fr 36px;gap:10px;align-items:center;margin:9px 0}.hn{font-size:18px}.hn small{color:#8d9098;font-size:14px}
.hb{height:14px;background:#26282c;border-radius:7px;overflow:hidden}.hb i{display:block;height:100%;border-radius:7px}.hv{font:600 16px "IBM Plex Mono",monospace}.hv.o{color:#8d9098}</style>"""
    peakh = max(range(24), key=lambda h: sum(grid[(x, h)] for x in DAYS))
    title = "When and where it hits"
    sub = f"After-dark share of timed incidents (18:00 to 06:00): {n1}% in week 1, {n2}% in week 2. The busiest hour over the 14 days is {peakh:02d}:00 Sana'a time."
    body = css + f'''<div class="p"><h2>Strike clock, hour by day</h2><p class="s">Incidents by hour (Sana'a time). Outlined cells are night hours. Week 2 in orange.</p>{"".join(s)}</div>
<div class="p"><h2>Hotspot districts</h2><p class="s">Incidents per district: grey week 1, orange week 2.</p>{"".join(H)}</div>'''
    return page("Yemen SITREP · timing and hotspots", 6, title, sub, body)



# ---------------- narrative (shared by card 1 and the brief), computed from the data
def fp(a, b):
    p = pct(b, a)
    return "new" if p is None else "no change" if p == 0 else f"{p:+d}%"


def tw(a, b, up="rose", down="fell", same="held level"):
    return up if b > a else down if b < a else same


_byday = Counter(r[1] for r in INCR)
_cas = Counter(); _kil = Counter()
for r in EV:
    _cas[r[1]] += r[6] + r[7]; _kil[r[1]] += r[6]
_air = Counter()
for r in INCR:
    if r[3] == 'Air strike':
        _air[r[1]] += r[9] or 1
_hit = Counter(o[0] for o in OPS if o[1] == 'KSA')
_dead = sorted([r for r in EV if r[6] + r[7] > 0], key=lambda r: (-r[6], -r[7]))
_g1, _g2 = Counter(), Counter()
for r in INCR:
    (_g1 if r[1] in W1 else _g2)[r[0]] += 1
_d1, _d2 = Counter(), Counter()
for r in INCR:
    for x in set(r[4]):
        (_d1 if r[1] in W1 else _d2)[(r[0], x)] += 1


def dn_(x):
    return re.sub(r'\s*\(.*?\)', '', x)


def where(r):
    p = dn_(", ".join(r[4][:1])) or ""
    return f"{p}, {G[r[0]]}" if p else G[r[0]]


HEAD = f"KSA air strikes <em>{fp(S1['air'], S2['air'])}</em>, civilian toll {fp(S1['k']+S1['i'], S2['k']+S2['i'])}"
_hd = max(DAYS[7:], key=lambda x: _hit[x]) if S2['hits'] else None
READ = [
    f"<b>Civilian casualties {tw(S1['k']+S1['i'], S2['k']+S2['i'])}.</b> {S1['k']} killed and {S1['i']} injured in week 1, {S2['k']} and {S2['i']} in week 2."
    + (f" Deadliest incident of week 2: {e(where(next(r for r in _dead if r[1] in W2)))}, {next(r for r in _dead if r[1] in W2)[6]} killed." if any(r[1] in W2 for r in _dead) else ""),
    f"<b>Strikes on Saudi territory {tw(S1['hits'], S2['hits'])}.</b> {S1['hits']} to {S2['hits']} AA/Houthi target hits"
    + (f", {_hit[_hd]} on {lab(_hd)}" if _hd else "") + f". KSA reported {S2['intc']} interceptions (week 1: {S1['intc']}).",
    f"<b>Ground fronts.</b> IRG/PLC attacks {S1['plc']} to {S2['plc']}, AA/Houthi ground operations {S1['gnd']} to {S2['gnd']}. Districts hit {S1['dists']} to {S2['dists']}.",
]


def brief():
    pk = max(DAYS, key=lambda x: _byday[x]); dk = max(DAYS, key=lambda x: _kil[x])
    top = sorted(_g2, key=lambda k: -_g2[k])[:2]
    share = round(sum(_g2[k] for k in top) * 100 / max(1, S2['inc']))
    ks = set(_g1) | set(_g2)
    rise = max(ks, key=lambda k: _g2[k] - _g1[k]) if ks else None
    fall = min(ks, key=lambda k: _g2[k] - _g1[k]) if ks else None
    hd = _hd
    tg = []
    if hd:
        for o in OPS:
            if o[0] == hd and o[1] == 'KSA':
                n = o[2].split(' (')[0]
                if n not in tg:
                    tg.append(n)
    dr = sorted(set(_d1) | set(_d2), key=lambda k: -(_d2[k] - _d1[k]))
    up3 = [k for k in dr if _d2[k] > _d1[k]][:3]
    dn = [k for k in dr[::-1] if _d2[k] < _d1[k]][:1]
    n1 = round(S1['night'] * 100 / max(1, S1['timed'])); n2 = round(S2['night'] * 100 / max(1, S2['timed']))
    cov1 = round(S1['air'] * 100 / S1['tally']) if S1['tally'] else None
    cov2 = round(S2['air'] * 100 / S2['tally']) if S2['tally'] else None
    L = [f"🇾🇪 <b>YEMEN SITREP | {lab(DAYS[0])} to {lab(DAYS[13])}</b>",
         f"<i>Week 1: {lab(DAYS[0])} to {lab(DAYS[6])} · Week 2: {lab(DAYS[7])} to {lab(DAYS[13])} (Sana'a time)</i>", "",
         "<b>📌 Bottom line</b>",
         f"KSA air strikes counted {fp(S1['air'], S2['air'])} (≥{S1['air']} to ≥{S2['air']}), civilian casualties {fp(S1['k']+S1['i'], S2['k']+S2['i'])}. "
         f"Incidents {tw(S1['inc'], S2['inc'])} ({S1['inc']} to {S2['inc']}). AA/Houthi target hits in Saudi Arabia: {S1['hits']} to {S2['hits']}.", "",
         "<b>1️⃣ At a glance</b>",
         f"🩸 Civilians: {S1['k']} killed / {S1['i']} injured ➜ {S2['k']} / {S2['i']}",
         f"✈️ AA/Houthi tally of KSA strikes: {S1['tally_avg']} ➜ {S2['tally_avg']} per reported day",
         f"🛡️ KSA-reported interceptions: {S1['intc']} ➜ {S2['intc']}",
         f"⚔️ IRG/PLC attacks: {S1['plc']} ➜ {S2['plc']} · AA/Houthi ground operations: {S1['gnd']} ➜ {S2['gnd']}", "",
         "<b>2️⃣ Daily pulse</b>",
         f"📈 Busiest day {lab(pk)} ({_byday[pk]} incidents, {_air[pk]} KSA air strikes). Deadliest day {lab(dk)} ({_kil[dk]} civilians killed).", "",
         "<b>3️⃣ Geography</b>",
         "📍 " + " and ".join(f"{G[k]} {_g1[k]} ➜ {_g2[k]}" for k in top) + f" carry {share}% of week 2 incidents."
         + (f" Biggest rise: {G[rise]} ({_g1[rise]} ➜ {_g2[rise]})." if rise and _g2[rise] > _g1[rise] else "")
         + (f" Biggest fall: {G[fall]} ({_g1[fall]} ➜ {_g2[fall]})." if fall and _g2[fall] < _g1[fall] else ""), "",
         "<b>4️⃣ Civilians</b>",
         f"🔻 {S1['k']+S2['k']} killed and {S1['i']+S2['i']} injured in 14 days. Deadliest: "
         + ", ".join(f"{where(r)} ({r[6]} killed, {lab(r[1])})" for r in _dead[:4] if r[6]) + ".", "",
         "<b>5️⃣ Air war and retaliation</b>",
         f"🚀 {S2['hits']} AA/Houthi target hits in Saudi Arabia" + (f", incl. {_hit[hd]} on {lab(hd)}: " + ", ".join(tg[:7]) if hd else "") + "."
         + (f" Reports itemise {cov2}% of the AA/Houthi strike tally in week 2 (week 1: {cov1}%)." if cov1 is not None and cov2 is not None else ""), "",
         "<b>6️⃣ Timing and hotspots</b>",
         f"🌙 After-dark share of incidents {n1}% ➜ {n2}%."
         + (" Rising: " + ", ".join(f"{dn_(k[1])} ({_d1[k]} ➜ {_d2[k]})" for k in up3) + "." if up3 else "")
         + (f" Easing: {dn_(dn[0][1])} ({_d1[dn[0]]} ➜ {_d2[dn[0]]})." if dn else ""), "",
         '<a href="https://drelmalihi02-ai.github.io/ye-dashboard/">Open the dashboard</a>']
    t = "\n".join(L)
    for bad in ('masirah', 'rnintel', 'spectator', 't.me/', '—', '@', 'claim'):
        assert bad not in t.lower(), 'brief contains forbidden text: ' + bad
    assert len(re.sub(r'<[^>]+>', '', t)) <= 3800, 'brief too long'
    return t


cards = [card1, card2, card3, card4, card5, card6]
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch()
    for n, fn in enumerate(cards, 1):
        h = fn()
        for bad in ('masirah', 'rnintel', 'spectator', 't.me/', '—'):
            assert bad not in h.lower(), (n, bad)
        open(os.path.join(OUT, f'card{n}.html'), 'w').write(h)
        pg = br.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=2)
        pg.set_content(h, wait_until='load')
        pg.screenshot(path=os.path.join(OUT, f'{n}_card.png'), full_page=True)
        hh = pg.evaluate("document.body.scrollHeight")
        print(n, hh)
        pg.close()
    br.close()
open(os.path.join(OUT, 'sitrep.txt'), 'w').write(brief() + "\n")
ok = FRESH and S2['inc'] > 0
json.dump({'ok': ok, 'reason': '' if ok else ('data cut-off ' + d['cut'] + ' does not cover week 2' if not FRESH else 'no incidents in week 2'),
           'w1': [DAYS[0], DAYS[6]], 'w2': [DAYS[7], DAYS[13]], 'cut': d['cut']}, open(os.path.join(OUT, 'status.json'), 'w'))
print(open(os.path.join(OUT, 'sitrep.txt')).read())
print(open(os.path.join(OUT, 'status.json')).read())
