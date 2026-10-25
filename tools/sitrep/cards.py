# Weekly SITREP (user request, 25 Oct 2026; v2 the same day): 7 designed cards, 2 short animated clips and a
# Telegram brief. Compares the two Sunday-to-Saturday weeks that ended before the run day (Sana'a time, UTC+3)
# and adds the running record since 1 Sep. Built from the dashboard data in index.html.
# Run by .github/workflows/sitrep.yml every Sunday 08:00 Sana'a.
# Usage: python3 cards.py INDEX_HTML OUTDIR [YYYY-MM-DD run day] [--no-video]
# Writes 0_open.mp4, 1_card.png ... 7_card.png, 8_record.mp4, sitrep.txt (Telegram HTML), status.json.
# Reading rules: deaths lead (never hidden inside a combined toll), red is used only for harm to civilians,
# counts with unstated numbers carry "≥" (at least), tally gaps are always stated, disputed incidents are flagged.
import json, os, re, sys, html, math, subprocess, datetime as dt
from collections import Counter, defaultdict

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
SRC, OUT = ARGS[0], ARGS[1]
VIDEO = '--no-video' not in sys.argv
os.makedirs(OUT, exist_ok=True)
d = json.loads(re.search(r'const D=(\{.*?\});\n', open(SRC).read()).group(1))
G = d['gov']
INC = {"Artillery", "Rockets", "Air strike", "Drone", "Unspecified attack", "Ground operation", "PLC shelling", "PLC sniper fire"}
SAUDI = {"Artillery", "Rockets", "Air strike", "Drone", "Unspecified attack"}
PLC = {"PLC shelling", "PLC sniper fire"}
TODAY = dt.date.fromisoformat(ARGS[2]) if len(ARGS) > 2 else (dt.datetime.utcnow() + dt.timedelta(hours=3)).date()
B2 = TODAY - dt.timedelta(days=(TODAY.weekday() - 5) % 7 or 7)   # last Saturday
A2 = B2 - dt.timedelta(days=6); A1 = A2 - dt.timedelta(days=7)
DAYS = [(A1 + dt.timedelta(days=i)).isoformat() for i in range(14)]
W1, W2 = set(DAYS[:7]), set(DAYS[7:])
START = "2026-09-01"
_cut = dt.datetime.strptime(d['cut'], "%d %b %Y, %H:%M")
FRESH = _cut >= dt.datetime.combine(B2, dt.time(21, 0))   # data read to at least Saturday 21:00 Sana'a
e = lambda x: html.escape(str(x))
C = dict(ksa="#3d8fef", plc="#c99a62", aa="#9d8cf2", k="#ff6b5e", i="#ffab9f", fg="#f4f4f0", mute="#9a9ca3", acc="#e8793f", neu="#c8c8c2")


def side(cat):
    return "KSA" if cat in SAUDI else "PLC" if cat in PLC else "AA"


def lab(x):
    x = dt.date.fromisoformat(x) if isinstance(x, str) else x
    return f"{x.day} {x.strftime('%b')}"


def dn_(x):
    return re.sub(r'\s*\(.*?\)', '', x)


ALL = [r for r in d['ev'] if r[1] >= START]
EV = [r for r in ALL if r[1] in W1 | W2]
INCR = [r for r in EV if r[3] in INC]
OPS_ALL = [o for o in d['ops'] if o[0] >= START]
OPS = [o for o in OPS_ALL if o[0] in W1 | W2]
CL = [c for c in d['claims'] if c['date'] in W1 | W2]
TL = {k: v for k, v in d['tally'].items() if k in W1 | W2}

# disputed: the other side gives a different account (summary says so, or a PLC/KSA claim matched to it blames AA)
DISP = set()
for r in ALL:
    if re.search(r"government side blames|IRG/PLC blames|government blames|PLC says .*(Houthi|AA)|blame[sd]? AA", r[8], re.I):
        DISP.add(r[10])
for c in d['claims']:
    if c['src'] in ('PLC', 'KSA') and re.search(r'Houthi', c['s']):
        for m in c.get('match') or []:
            DISP.add(m)


def st(W):
    inc = [r for r in INCR if r[1] in W]
    ev = [r for r in EV if r[1] in W]
    air = [r for r in inc if r[3] == 'Air strike']
    ops = [o for o in OPS if o[0] in W]
    tl = [v for k, v in TL.items() if k in W]
    cl = [c for c in CL if c['date'] in W]
    dists = {(r[0], x) for r in inc for x in r[4]}
    tm = [r for r in inc if r[2]]
    parts = Counter(int(r[2][:2]) // 6 for r in tm)
    tdays = [k for k in TL if k in W]
    air_td = sum(r[9] or 1 for r in air if r[1] in tdays)
    return dict(
        inc=len(inc), k=sum(r[6] for r in ev), i=sum(r[7] for r in ev),
        air=sum(r[9] or 1 for r in air), air_r=len(air), air_unc=sum(1 for r in air if not r[9]),
        plc=sum(1 for r in inc if side(r[3]) == 'PLC'), gnd=sum(1 for r in inc if side(r[3]) == 'AA'),
        tally=sum(tl), tally_n=len(tl), tally_avg=round(sum(tl) / len(tl)) if tl else 0, air_td=air_td,
        hits=sum(1 for o in ops if o[1] == 'KSA'),
        intc=sum((c['n'] or 1) for c in cl if c['src'] == 'KSA' and c['cat'] == 'Interception'),
        dists=len(dists), parts=[parts[j] for j in range(4)], timed=len(tm),
    )


S1, S2 = st(W1), st(W2)


def pct(a, b):
    return None if not b else round((a - b) * 100 / b)


def fp(a, b):
    p = pct(b, a)
    return "new" if p is None else "no change" if p == 0 else f"{p:+d}%"


def tw(a, b, up="rose", down="fell", same="held level"):
    return up if b > a else down if b < a else same


def chip(a, b, harm=False):
    """harm=True: red when up, green when down (civilian harm only). Otherwise neutral."""
    p = pct(b, a)
    if p is None:
        return '<span class="ch n">new</span>'
    if p == 0:
        return '<span class="ch n">= 0%</span>'
    cls = ("bad" if p > 0 else "good") if harm else "n"
    return f'<span class="ch {cls}">{"▲" if p > 0 else "▼"} {abs(p)}%</span>'


# ---------------- weekly history since 1 Sep (Sunday-to-Saturday weeks, the first one partial)
WEEKS = []
ws = dt.date(2026, 8, 30)
while ws <= B2:
    we = ws + dt.timedelta(days=6)
    S = {(ws + dt.timedelta(days=i)).isoformat() for i in range(7)}
    S = {x for x in S if x >= START}
    inc = [r for r in ALL if r[1] in S and r[3] in INC]
    WEEKS.append(dict(a=max(ws.isoformat(), START), b=we.isoformat(), inc=len(inc), k=sum(r[6] for r in ALL if r[1] in S),
                      i=sum(r[7] for r in ALL if r[1] in S), air=sum(r[9] or 1 for r in inc if r[3] == 'Air strike'),
                      hits=sum(1 for o in OPS_ALL if o[0] in S and o[1] == 'KSA'), partial=ws.isoformat() < START,
                      gov=Counter(r[0] for r in inc)))
    ws += dt.timedelta(days=7)
FULL = [w for w in WEEKS if not w['partial']]


def rank(key):
    v = FULL[-1][key]
    return 1 + sum(1 for w in FULL if w[key] > v), len(FULL)


TOT_INC = [r for r in ALL if r[3] in INC]
TOT = dict(inc=len(TOT_INC), k=sum(r[6] for r in ALL), i=sum(r[7] for r in ALL),
           air=sum(r[9] or 1 for r in TOT_INC if r[3] == 'Air strike'), hits=sum(1 for o in OPS_ALL if o[1] == 'KSA'),
           tally=d.get('claimed'), tally_to=d.get('claimedTo'))

CSS = """*{box-sizing:border-box}body{margin:0;width:1080px;background:#0f1013;font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;color:#f4f4f0}
.c{padding:56px 56px 40px;background:radial-gradient(110% 55% at 0% 0%,#3d2617 0%,transparent 55%),linear-gradient(160deg,#17181c,#0f1013);min-height:1350px;display:flex;flex-direction:column}
.ey{font:600 22px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:#e8793f;display:flex;justify-content:space-between}
.ey b{color:#9a9ca3;font-weight:500;letter-spacing:.04em}
h1{font:700 62px/1.04 "IBM Plex Sans Condensed","Arial Narrow",sans-serif;margin:16px 0 10px;letter-spacing:-.01em}
h1 em{font-style:normal;color:#ff7b6e}h1 i{font-style:normal;color:#e8793f}
.sub{font-size:26px;color:#b4b5ba;margin:0 0 26px;line-height:1.35}
.p{background:#1a1b1f;border:1px solid #2e3036;border-radius:20px;padding:24px 26px;margin-bottom:18px}
.p h2{margin:0 0 6px;font:600 30px "IBM Plex Sans Condensed",sans-serif}.p .s{margin:0 0 14px;font-size:21px;color:#9a9ca3}
svg text{font-family:"IBM Plex Mono",monospace}
.lg{display:flex;flex-wrap:wrap;gap:8px 26px;font-size:22px;color:#c8c8c2;margin:2px 0 10px}.lg i{display:inline-block;width:18px;height:18px;border-radius:5px;margin-right:9px;vertical-align:-2px}
.ch{font:600 23px "IBM Plex Mono",monospace;border-radius:999px;padding:5px 13px;white-space:nowrap}
.ch.bad{background:#40201d;color:#ff7b6e}.ch.good{background:#163221;color:#3ccd80}.ch.n{background:#2a2c31;color:#d8d8d2}
.f{margin-top:auto;display:flex;justify-content:space-between;align-items:center;padding-top:18px;font-size:19px;color:#7d8087;border-top:1px solid #26282d}
.f b{color:#c8c8c2;font-weight:600}
.k3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.kb{background:#141518;border:1px solid #2a2c31;border-radius:16px;padding:18px 20px}
.kb .l{font-size:21px;color:#b4b5ba;line-height:1.25}.kb .v{font:700 52px/1.05 "IBM Plex Mono",monospace;letter-spacing:-.03em;margin-top:8px}.kb .v small{font-size:24px;color:#9a9ca3;font-weight:500}
.kb .d{margin-top:10px;font-size:19px;color:#9a9ca3}
.note{font-size:19px;color:#9a9ca3;line-height:1.4;margin-top:4px}
.tag{display:inline-block;font:600 17px "IBM Plex Mono",monospace;border-radius:8px;padding:2px 8px;margin-left:8px;vertical-align:3px}
.tag.w1{background:#2a2c31;color:#c8c8c2}.tag.w2{background:#3d2617;color:#e8793f}.tag.dp{background:#3a3214;color:#f2c94c}
.tag.up{background:#3d2617;color:#e8793f}.tag.dn{background:#1d2a3a;color:#7fb2f0}
"""
N_CARDS = 7


def page(eyebrow, n, title, sub, body, foot=None):
    f = foot or f"Week 1 <b>{lab(DAYS[0])} to {lab(DAYS[6])}</b> · Week 2 <b>{lab(DAYS[7])} to {lab(DAYS[13])}</b> · Sana'a time"
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="c">
<div class="ey"><span>🇾🇪 {eyebrow}</span><b>{n}/{N_CARDS}</b></div><h1>{title}</h1><p class="sub">{sub}</p>{body}
<div class="f"><span>{f}</span><span><b>YE Paradise</b></span></div></div></body></html>'''


# ---------------- shared readings
_byday = Counter(r[1] for r in INCR)
_kil = Counter(); _inj = Counter()
for r in EV:
    _kil[r[1]] += r[6]; _inj[r[1]] += r[7]
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
        (_d1 if r[1] in W1 else _d2)[(r[0], dn_(x))] += 1
PEAK = max(DAYS, key=lambda x: (_byday[x], _air[x]))
DEADLY = max(DAYS, key=lambda x: (_kil[x], _inj[x]))
HD = max(DAYS[7:], key=lambda x: _hit[x]) if S2['hits'] else None
RK = rank('k'); RI = rank('inc'); RA = rank('air')


def where(r):
    p = dn_(", ".join(r[4][:1]))
    return f"{p}, {G[r[0]]}" if p else G[r[0]]


def ordinal(n):
    return {1: "deadliest", 2: "2nd deadliest", 3: "3rd deadliest"}.get(n, f"{n}th deadliest")


def head():
    k = fp(S1['k'], S2['k'])
    if S2['k'] > S1['k']:
        return f"Civilian deaths <em>up {pct(S2['k'], S1['k'])}%</em> as KSA air strikes {tw(S1['air'], S2['air'])}"
    if S2['k'] < S1['k']:
        return f"Civilian deaths <i>down {abs(pct(S2['k'], S1['k']))}%</i>, KSA air strikes {fp(S1['air'], S2['air'])}"
    return f"Civilian deaths held at {S2['k']}, KSA air strikes {fp(S1['air'], S2['air'])}"


HEAD = head()


# ---------------- Card 1: at a glance
def card1():
    rows = [
        ("Civilians killed", S1['k'], S2['k'], True, "", ""),
        ("Civilians injured", S1['i'], S2['i'], True, "", ""),
        ("Security incidents", S1['inc'], S2['inc'], False, "", ""),
        ("KSA air strikes counted", S1['air'], S2['air'], False, "≥", ""),
        ("AA/Houthi tally of KSA strikes", S1['tally_avg'], S2['tally_avg'], False, "", f"per day, tally on {S1['tally_n']} and {S2['tally_n']} of 7 days"),
        ("AA/Houthi target hits in Saudi Arabia", S1['hits'], S2['hits'], False, "", ""),
        ("IRG/PLC attacks", S1['plc'], S2['plc'], False, "", "shelling and sniper fire"),
        ("AA/Houthi ground operations", S1['gnd'], S2['gnd'], False, "", ""),
    ]
    out = []
    for lbl, a, b, harm, pre, note in rows:
        m = max(a, b, 1)
        out.append(f'<div class="vr"><div class="vl">{e(lbl)}{f"<small>{e(note)}</small>" if note else ""}</div><div class="vbs">'
                   f'<div class="vb"><span class="b1" style="width:{a/m*100:.0f}%"></span><em>{pre}{a:,}</em></div>'
                   f'<div class="vb"><span class="b2{" h" if harm else ""}" style="width:{b/m*100:.0f}%"></span><em>{pre}{b:,}</em></div></div>'
                   f'<div class="vc">{chip(a, b, harm)}</div></div>')
    css = """<style>.vr{display:grid;grid-template-columns:330px 1fr 130px;column-gap:18px;align-items:center;padding:11px 0;border-bottom:1px solid #26282d}
.vr:last-child{border-bottom:0}.vl{font-size:24px;color:#e4e4de;line-height:1.2}.vl small{display:block;font-size:17px;color:#9a9ca3;margin-top:3px}.vc{text-align:right}
.vbs{display:flex;flex-direction:column;gap:6px;padding-right:86px}.vb{display:flex;align-items:center;gap:12px;height:26px}
.vb span{display:block;height:18px;border-radius:9px;min-width:6px}.b1{background:#4a4d55}.b2{background:linear-gradient(90deg,#b8501f,#e8793f)}.b2.h{background:linear-gradient(90deg,#c4382d,#ff6b5e)}
.vb em{font:600 24px "IBM Plex Mono",monospace;font-style:normal;min-width:70px}.vb:first-child em{color:#9a9ca3}</style>"""
    leg = (f'<div class="lg"><span><i style="background:#4a4d55"></i>Week 1</span><span><i style="background:#e8793f"></i>Week 2</span>'
           f'<span style="color:#9a9ca3">Red tags only for harm to civilians</span></div>')
    two = (f'<div class="p two"><h2>Two accounts of the air war</h2><div class="tw"><div><b>{S2["hits"]}</b><span>targets hit in Saudi Arabia, '
           f'say AA/Houthis</span></div><div><b>{S2["intc"]}</b><span>missiles and drones intercepted, says KSA</span></div></div>'
           f'<p class="note">Week 2. "≥" means at least: {S2["air_unc"]} strike reports gave no number and count as 1.</p></div>')
    css += """<style>.tw{display:grid;grid-template-columns:1fr 1fr;gap:18px}.tw div{background:#141518;border:1px solid #2a2c31;border-radius:16px;padding:16px 20px}
.tw b{display:block;font:700 54px/1 "IBM Plex Mono",monospace;color:#9d8cf2}.tw div:last-child b{color:#3d8fef}.tw span{font-size:21px;color:#c8c8c2;line-height:1.3}</style>"""
    sub = f"Week 2 was the {ordinal(RK[0])} of {RK[1]} full weeks since 1 Sep for civilian deaths."
    return page("Yemen weekly SITREP · at a glance", 1, HEAD, sub, css + f'<div class="p">{leg}{"".join(out)}</div>' + two)


# ---------------- Card 2: daily pulse
def card2():
    W = 922; PL = 40; cw = (W - PL - 4) / 14
    by = {x: Counter() for x in DAYS}
    for r in INCR:
        by[r[1]][side(r[3])] += 1
    mi = max(sum(v.values()) for v in by.values()) or 1
    mc = max(_kil[x] + _inj[x] for x in DAYS) or 1
    ma = max(list(_air.values()) + [1])
    T0, H1 = 56, 300
    BASE = T0 + H1
    CB = BASE + 46; H2 = 200
    SB = CB + H2 + 70
    H = SB + 110
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%">']
    s.append(f'<rect x="{PL+7*cw}" y="0" width="{7*cw}" height="{H}" fill="#e8793f" opacity=".06" rx="10"/>')
    s.append(f'<text x="{PL+3.5*cw}" y="24" text-anchor="middle" fill="#9a9ca3" font-size="21">WEEK 1 · {S1["inc"]}</text>')
    s.append(f'<text x="{PL+10.5*cw}" y="24" text-anchor="middle" fill="#e8793f" font-size="21">WEEK 2 · {S2["inc"]}</text>')
    for j, x in enumerate(DAYS):
        X = PL + j * cw + 5; bw = cw - 10; cx = X + bw / 2
        y = BASE
        for sd, col in (("KSA", C['ksa']), ("PLC", C['plc']), ("AA", C['aa'])):
            n = by[x][sd]
            if n:
                hh = n / mi * H1; y -= hh
                s.append(f'<rect x="{X:.1f}" y="{y+1:.1f}" width="{bw:.1f}" height="{max(hh-2,2):.1f}" rx="5" fill="{col}"/>')
        tot = sum(by[x].values())
        s.append(f'<text x="{cx:.1f}" y="{y-10:.1f}" text-anchor="middle" fill="#f4f4f0" font-size="22" font-weight="700">{tot}</text>')
        dc, dw = ("#e8793f", 700) if x == PEAK else ("#ff6b5e", 700) if x == DEADLY else ("#c8c8c2", 400)
        if x in (PEAK, DEADLY):
            s.append(f'<rect x="{cx-20:.1f}" y="{BASE+9}" width="40" height="30" rx="8" fill="none" stroke="{dc}" stroke-width="2"/>')
        s.append(f'<text x="{cx:.1f}" y="{BASE+31}" text-anchor="middle" fill="{dc}" font-size="20" font-weight="{dw}">{int(x[8:])}</text>')
        k, i = _kil[x], _inj[x]
        yk = k / mc * H2; yi = i / mc * H2
        if k:
            s.append(f'<rect x="{X:.1f}" y="{CB}" width="{bw:.1f}" height="{yk:.1f}" rx="4" fill="{C["k"]}"/>')
        if i:
            s.append(f'<rect x="{X:.1f}" y="{CB+yk:.1f}" width="{bw:.1f}" height="{yi:.1f}" rx="4" fill="{C["i"]}" opacity=".5"/>')
        if k:
            s.append(f'<text x="{cx:.1f}" y="{CB+yk+yi+24:.1f}" text-anchor="middle" fill="#ff8a7e" font-size="20" font-weight="700">{k}</text>')
        a = _air[x]
        if a:
            r = 9 + 20 * math.sqrt(a / ma)
            s.append(f'<circle cx="{cx:.1f}" cy="{SB}" r="{r:.1f}" fill="{C["ksa"]}"/>')
            s.append(f'<text x="{cx:.1f}" y="{SB+7}" text-anchor="middle" fill="#fff" font-size="{18 if a<100 else 15}" font-weight="700">{a}</text>')
        h = _hit[x]
        if h:
            s.append(f'<rect x="{cx-14:.1f}" y="{SB+50}" width="28" height="28" rx="5" transform="rotate(45 {cx:.1f} {SB+64})" fill="{C["aa"]}"/>')
            s.append(f'<text x="{cx:.1f}" y="{SB+71}" text-anchor="middle" fill="#fff" font-size="18" font-weight="700">{h}</text>')
    s.append(f'<line x1="{PL}" x2="{W}" y1="{BASE+4}" y2="{BASE+4}" stroke="#3a3c42"/>')
    s.append('</svg>')
    leg = (f'<div class="lg"><span><i style="background:{C["ksa"]}"></i>KSA</span><span><i style="background:{C["plc"]}"></i>IRG/PLC</span>'
           f'<span><i style="background:{C["aa"]}"></i>AA/Houthis</span></div>')
    key = (f'<div class="rows"><div><i style="background:{C["k"]}"></i>Below the line: civilians killed (number) and injured (light)</div>'
           f'<div><i class="dot" style="background:{C["ksa"]}"></i>Blue circle: KSA air strikes counted that day</div>'
           f'<div><i class="dia" style="background:{C["aa"]}"></i>Purple diamond: AA/Houthi target hits in Saudi Arabia</div>'
           f'<div><i style="background:none;border:2px solid #e8793f"></i>Busiest day <span style="margin:0 8px;color:#6d7077">·</span><i style="background:none;border:2px solid #ff6b5e"></i>Deadliest day</div></div>')
    css = """<style>.rows{display:grid;gap:8px;font-size:20px;color:#c8c8c2;margin-top:6px}.rows i{display:inline-block;width:18px;height:18px;border-radius:4px;margin-right:10px;vertical-align:-2px}
.rows i.dot{border-radius:50%}.rows i.dia{transform:rotate(45deg) scale(.85)}</style>"""
    sub = (f"Busiest day {lab(PEAK)}: {_byday[PEAK]} incidents and {_air[PEAK]} KSA air strikes. "
           f"Deadliest day {lab(DEADLY)}: {_kil[DEADLY]} civilians killed.")
    return page("Yemen weekly SITREP · daily pulse", 2, "Fourteen days, day by day", sub, css + f'<div class="p">{leg}{"".join(s)}{key}</div>')


# ---------------- Card 3: geography, two week maps
NAME = {'Amanat al-Asimah': 'sanaa', "Sana'a": 'sanaa', 'Lahij': 'lahj', 'Aden': 'aden', 'Al Hudaydah': 'hodeidah', "Ta'izz": 'taiz', 'Shabwah': 'shabwah',
        'Hadhramaut': 'hadramawt', 'Abyan': 'abyan', 'Al Jawf': 'jawf', 'Ibb': 'ibb', "Al Bayda'": 'bayda', "Ad Dali'": 'dhale', 'Al Mahwit': 'mahwit',
        "Sa'dah": 'saada', 'Hajjah': 'hajjah', 'Dhamar': 'dhamar', 'Amran': 'amran', 'Al Mahrah': 'mahrah', "Ma'rib": 'marib', 'Raymah': 'raymah', 'Socotra': 'socotra'}


def ring_centroid(ring):
    a = cx = cy = 0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if not a:
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring), 0
    return cx / (3 * a), cy / (3 * a), abs(a) / 2


CENT = {}
for nm, mp in d['adm1']:
    key = NAME.get(nm)
    for poly in mp:
        c = ring_centroid(poly[0])
        if key not in CENT or c[2] > CENT[key][2]:
            CENT[key] = c
CENT['sanaa'] = (44.42, 15.42, 1)
CENT['hodeidah'] = (43.15, 14.75, 1)
CENT['raymah'] = (43.62, 14.62, 1)
CENT['mahwit'] = (43.55, 15.42, 1)
CENT['hajjah'] = (43.35, 16.05, 1)


def gmap(cnt, mx, W, H, title, col):
    x0, x1, y0, y1 = 42.55, 46.2, 12.55, 17.65
    k = min(W / (x1 - x0), H / (y1 - y0))
    P = lambda lon, lat: ((lon - x0) * k, (y1 - lat) * k)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%"><rect width="{W}" height="{H}" rx="16" fill="#131d26"/>']
    for nm, mp in d['adm1']:
        key = NAME.get(nm); n = cnt.get(key, 0)
        f = "#202227" if not n else f"rgba({col},{0.22+0.78*(n/mx)**0.6:.2f})"
        p = "".join("M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z" for poly in mp for ring in poly)
        s.append(f'<path d="{p}" fill="{f}" stroke="#0f1013" stroke-width="2"/>')
    for key, (lon, lat, _) in CENT.items():
        n = cnt.get(key, 0)
        if n < 1 or not (x0 < lon < x1 and y0 < lat < y1):
            continue
        X, Y = P(lon, lat)
        s.append(f'<text x="{X:.0f}" y="{Y+10:.0f}" text-anchor="middle" fill="#fff" font-size="{34 if n>=10 else 28}" font-weight="700" paint-order="stroke" stroke="#0f1013" stroke-width="5">{n}</text>')
    s.append('</svg>')
    return "".join(s)


def card3():
    mx = max(list(_g1.values()) + list(_g2.values()) + [1])
    m1 = gmap(_g1, mx, 430, 560, f"Week 1 · {S1['inc']}", "150,152,160")
    m2 = gmap(_g2, mx, 430, 560, f"Week 2 · {S2['inc']}", "232,121,63")
    keys = sorted(set(_g1) | set(_g2), key=lambda k_: -(_g2[k_] * 2 + _g1[k_]))[:8]
    m = max([_g1[x] for x in keys] + [_g2[x] for x in keys] + [1])
    L = []
    k2 = Counter()
    for r in EV:
        if r[1] in W2:
            k2[r[0]] += r[6]
    for key in keys:
        a, b = _g1[key], _g2[key]
        tg = f'<span class="tag up">▲ {b-a}</span>' if b > a else f'<span class="tag dn">▼ {a-b}</span>' if b < a else ''
        L.append(f'<div class="sl"><span class="sn">{e(G[key])}{tg}</span><span class="sv">{a}</span><span class="ar">→</span><span class="sv n2">{b}</span>'
                 f'<span class="kk">{f"{k2[key]} killed" if k2[key] else ""}</span></div>')
    css = """<style>.mm{display:grid;grid-template-columns:1fr 1fr;gap:16px}.mt{font:600 24px 'IBM Plex Mono',monospace;color:#c8c8c2;margin:0 0 10px}.mt.w2{color:#e8793f}.mg2{display:grid;grid-template-columns:1fr 1fr;column-gap:40px}
.sl{display:grid;grid-template-columns:1fr 44px 26px 44px 110px;align-items:center;gap:6px;padding:9px 0;border-bottom:1px solid #26282d;font-size:23px}
.sv{font:600 23px "IBM Plex Mono",monospace;color:#9a9ca3;text-align:right}.sv.n2{color:#fff}.ar{color:#6d7077;text-align:center}.kk{font:500 18px "IBM Plex Mono",monospace;color:#ff8a7e;text-align:right}</style>"""
    top = sorted(_g2, key=lambda k_: -_g2[k_])[:2]
    share = round(sum(_g2[k_] for k_ in top) * 100 / max(1, S2['inc']))
    ks = set(_g1) | set(_g2)
    rise = max(ks, key=lambda k_: _g2[k_] - _g1[k_]); fall = min(ks, key=lambda k_: _g2[k_] - _g1[k_])
    sub = (f"{' and '.join(G[k_] for k_ in top)} carry {share}% of week 2 incidents. "
           + (f"Biggest rise {G[rise]} (+{_g2[rise]-_g1[rise]}). " if _g2[rise] > _g1[rise] else "")
           + (f"Biggest fall {G[fall]} ({_g2[fall]-_g1[fall]})." if _g2[fall] < _g1[fall] else ""))
    body = css + f'''<div class="p"><div class="mm"><div><div class="mt">Week 1 · {S1['inc']} incidents</div>{m1}</div><div><div class="mt w2">Week 2 · {S2['inc']} incidents</div>{m2}</div></div><p class="note">Number = incidents in the governorate. West and central Yemen shown; Sana'a includes the capital.</p></div>
<div class="p"><h2>Week 1 → week 2</h2><div class="mg2"><div>{"".join(L[:4])}</div><div>{"".join(L[4:])}</div></div><p class="note">Red = civilians killed in week 2.</p></div>'''
    return page("Yemen weekly SITREP · geography", 3, "Where the incidents were", sub, body)


# ---------------- Card 4: civilians
def card4():
    kg = defaultdict(lambda: [0, 0, 0, 0])
    for r in EV:
        if r[6] + r[7]:
            w = 0 if r[1] in W1 else 2
            kg[r[0]][w] += r[6]; kg[r[0]][w + 1] += r[7]
    keys = sorted(kg, key=lambda x: -(kg[x][2] * 3 + kg[x][3] + kg[x][0] * 2))[:6]
    m = max(max(v[0], v[2]) for v in kg.values()) or 1
    rows = []
    for key in keys:
        v = kg[key]
        rows.append(f'<div class="cr"><span class="cn">{e(G[key])}</span>'
                    f'<span class="cb"><i style="width:{v[0]/m*100:.1f}%;background:#6b4a47"></i></span><span class="cv o">{v[0]}<small>/{v[1]}</small></span>'
                    f'<span class="cb"><i style="width:{v[2]/m*100:.1f}%;background:{C["k"]}"></i></span><span class="cv">{v[2]}<small>/{v[3]}</small></span></div>')
    D = []
    for r in _dead[:5]:
        place = dn_(", ".join(r[4][:2])) or (r[5] or "")
        who = {"KSA": "KSA", "PLC": "IRG/PLC", "AA": "AA/Houthis"}.get(side(r[3])) if r[3] in INC else ""
        wk = '<span class="tag w2">W2</span>' if r[1] in W2 else '<span class="tag w1">W1</span>'
        dp = '<span class="tag dp">DISPUTED</span>' if r[10] in DISP else ''
        what = f"{who} {r[3].lower()}" if who else r[3]
        if r[10] in DISP:
            what += ", the other side blames AA/Houthis"
        D.append(f'<div class="dr"><span class="dd">{lab(r[1])}</span><span class="dk">{r[6]}<small> killed</small></span>'
                 f'<span class="dp"><b>{e(place)}</b>, {e(G[r[0]])}{wk}{dp}<br><small>{e(what)}{", " + str(r[7]) + " injured" if r[7] else ""}</small></span></div>')
    css = """<style>.cr{display:grid;grid-template-columns:150px 1fr 92px 1fr 92px;gap:12px;align-items:center;margin:12px 0}.cn{font-size:23px}
.cb{display:block;height:18px;background:#26282d;border-radius:9px;overflow:hidden}.cb i{display:block;height:100%;border-radius:9px}
.cv{font:700 24px "IBM Plex Mono",monospace;color:#ff8a7e}.cv small{font-size:17px;color:#ffab9f;font-weight:500}.cv.o{color:#a3807c}.cv.o small{color:#8d7774}
.hd{display:grid;grid-template-columns:150px 1fr 92px 1fr 92px;gap:12px;font-size:18px;color:#9a9ca3}
.dr{display:grid;grid-template-columns:92px 150px 1fr;gap:14px;align-items:center;padding:12px 0;border-top:1px solid #26282d}.dr:first-of-type{border-top:0}
.dd{font:500 20px "IBM Plex Mono",monospace;color:#b4b5ba}.dk{font:700 40px "IBM Plex Mono",monospace;color:#ff6b5e}.dk small{font-size:18px;color:#ffab9f;font-weight:500}
.dp{font-size:23px;line-height:1.3}.dp small{font-size:18px;color:#9a9ca3}</style>"""
    kp = f'''<div class="k3" style="margin-bottom:18px"><div class="kb"><div class="l">Civilians killed</div><div class="v" style="color:#ff6b5e">{S2["k"]} <small>vs {S1["k"]}</small></div><div class="d">{chip(S1["k"],S2["k"],True)}</div></div>
<div class="kb"><div class="l">Civilians injured</div><div class="v" style="color:#ffab9f">{S2["i"]} <small>vs {S1["i"]}</small></div><div class="d">{chip(S1["i"],S2["i"],True)}</div></div>
<div class="kb"><div class="l">Deadliest week rank</div><div class="v">{RK[0]}<small> of {RK[1]}</small></div><div class="d">full weeks since 1 Sep</div></div></div>'''
    body = css + kp + f'''<div class="p"><h2>By governorate</h2><div class="hd"><span></span><span>Week 1</span><span></span><span>Week 2</span><span></span></div>{"".join(rows)}<p class="note">Killed / injured.</p></div>
<div class="p"><h2>Deadliest incidents, 14 days</h2>{"".join(D)}</div>'''
    return page("Yemen weekly SITREP · civilians", 4, f"{S2['k']} civilians killed in week 2",
                "Civilians only. Combatant tolls from either side are never counted.", body)


# ---------------- Card 5: air war and retaliation
def card5():
    W, H = 922, 520; PL = 40; cw = (W - PL - 4) / 14
    mt = max(list(TL.values()) + list(_air.values()) + [1]); mh = max(list(_hit.values()) + [1])
    MID = 150
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%">']
    s.append(f'<rect x="{PL+7*cw}" y="0" width="{7*cw}" height="{H}" fill="#e8793f" opacity=".06" rx="10"/>')
    for j, x in enumerate(DAYS):
        X = PL + j * cw + 6; bw = (cw - 12) / 2; cx = X + bw
        h = _hit[x]
        if h:
            hh = h / mh * 110
            s.append(f'<rect x="{X+bw/2:.1f}" y="{MID-hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="5" fill="{C["aa"]}"/>')
            s.append(f'<text x="{cx:.1f}" y="{MID-hh-9:.1f}" text-anchor="middle" fill="#d9d1ff" font-size="21" font-weight="700">{h}</text>')
        t = TL.get(x)
        if t:
            th = t / mt * 270
            s.append(f'<rect x="{X:.1f}" y="{MID+12}" width="{bw-2:.1f}" height="{th:.1f}" rx="4" fill="#2f5d94"/>')
            s.append(f'<text x="{X+bw/2-1:.1f}" y="{MID+12+th+20:.1f}" text-anchor="middle" fill="#7fb2f0" font-size="15">{t}</text>')
        if not t:
            s.append(f'<text x="{X+bw/2-1:.1f}" y="{MID+36}" text-anchor="middle" fill="#6d7077" font-size="15">n/r</text>')
        a = _air[x]
        if a:
            ah = a / mt * 270
            s.append(f'<rect x="{X+bw+1:.1f}" y="{MID+12}" width="{bw-2:.1f}" height="{ah:.1f}" rx="4" fill="{C["ksa"]}"/>')
            s.append(f'<text x="{X+bw*1.5:.1f}" y="{MID+12+ah+20:.1f}" text-anchor="middle" fill="#fff" font-size="15" font-weight="700">{a}</text>')
        s.append(f'<text x="{cx:.1f}" y="{H-12}" text-anchor="middle" fill="#c8c8c2" font-size="20">{int(x[8:])}</text>')
    s.append(f'<line x1="{PL}" x2="{W}" y1="{MID+6}" y2="{MID+6}" stroke="#3a3c42"/>')
    s.append(f'<text x="{PL}" y="24" fill="#c2b7ff" font-size="19">▲ AA/Houthi target hits in Saudi Arabia</text>')
    s.append(f'<text x="{PL}" y="{MID+40}" fill="#7fb2f0" font-size="19" opacity="0">.</text></svg>')
    leg = (f'<div class="lg"><span><i style="background:#2f5d94"></i>AA/Houthi daily tally of KSA strikes (n/r = no tally)</span>'
           f'<span><i style="background:{C["ksa"]}"></i>KSA air strikes counted in reports</span></div>')
    # Saudi map with named, de-overlapped sites
    MW, MH = 470, 470
    x0, x1, y0, y1 = 34.5, 56.0, 16.2, 32.2
    k = min(MW / (x1 - x0), MH / (y1 - y0))
    P = lambda lon, lat: ((lon - x0) * k, (y1 - lat) * k)
    m = [f'<svg viewBox="0 0 {MW} {MH}" width="100%"><rect width="{MW}" height="{MH}" rx="16" fill="#131d26"/>']
    for nm, mp in d['ksa']:
        p = "".join("M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z" for poly in mp for ring in poly)
        m.append(f'<path d="{p}" fill="#222429" stroke="#34373d" stroke-width="1"/>')
    for nm, mp in d['adm1']:
        p = "".join("M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z" for poly in mp for ring in poly)
        m.append(f'<path d="{p}" fill="#3d2617" stroke="#3d2617" stroke-width=".6"/>')
    CITY = [("pipeline", "East-West pipeline"), ("Riyadh", "Riyadh"), ("Dammam", "Dammam"), ("Dhahran", "Dhahran"), ("Yanbu", "Yanbu"), ("Rabigh", "Rabigh"),
            ("Jeddah", "Jeddah"), ("Taif", "Taif"), ("Shaybah", "Shaybah"), ("Najran", "Najran"), ("Khamis", "Khamis Mushait"), ("Abha", "Abha"),
            ("Jizan", "Jizan"), ("Jazan", "Jizan"), ("Bir Askar", "Najran"), ("Sharurah", "Sharurah"), ("Eastern", "Eastern Province"), ("naval", "Naval camp, Red Sea")]
    def city(t):
        for kw, nm in CITY:
            if kw.lower() in t.lower():
                return nm
        return t.split(' (')[0][:18]
    sites = defaultdict(lambda: [0, 0, [], []])
    for o in OPS:
        if o[1] == 'KSA' and o[6] is not None:
            c_ = city(o[2] + " " + (o[9] or ""))
            sites[c_][0 if o[0] in W1 else 1] += 1
            sites[c_][2].append(o[6]); sites[c_][3].append(o[7])
    order = sorted(sites.items(), key=lambda kv: -(kv[1][1] * 10 + kv[1][0]))[:9]
    pos = []
    for nm, (a, b, lo, la) in order:
        X, Y = P(sum(lo) / len(lo), sum(la) / len(la)); pos.append([X, Y, 11 + 6 * math.sqrt(a + b)])
    for _ in range(60):                      # push overlapping circles apart
        for p_ in pos:
            for q_ in pos:
                if p_ is q_:
                    continue
                dx, dy = p_[0] - q_[0], p_[1] - q_[1]; dd = math.hypot(dx, dy) or 0.01; need = p_[2] + q_[2] + 3
                if dd < need:
                    p_[0] += dx / dd * (need - dd) / 2; p_[1] += dy / dd * (need - dd) / 2
    for j_, (nm, (a, b, lo, la)) in enumerate(order):
        X, Y, r = pos[j_]
        m.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{r:.1f}" fill="{C["aa"] if b else "#5f598f"}" fill-opacity=".9" stroke="#0f1013" stroke-width="2"/>')
        m.append(f'<text x="{X:.1f}" y="{Y+6:.1f}" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">{j_+1}</text>')
    SL = "".join(f'<div class="si"><b>{j_+1}</b><span>{e(nm)}</span><em class="o">{a}</em><em>{b}</em></div>' for j_, (nm, (a, b, lo, la)) in enumerate(order[:9]))
    m.append('</svg>')
    cov = (round(S2['air_td'] * 100 / S2['tally']) if S2['tally'] else None)
    cov1 = (round(S1['air_td'] * 100 / S1['tally']) if S1['tally'] else None)
    side_ = (f'<div class="sh"><span></span><span>Site</span><em>W1</em><em>W2</em></div>{SL}')
    kbs = (f'<div class="k3" style="margin-top:16px"><div class="kb"><div class="l">AA/Houthis say targets hit</div><div class="v" style="color:#9d8cf2">{S2["hits"]} <small>vs {S1["hits"]}</small></div></div>'
           f'<div class="kb"><div class="l">KSA says intercepted</div><div class="v" style="color:#3d8fef">{S2["intc"]} <small>vs {S1["intc"]}</small></div></div>'
           f'<div class="kb"><div class="l">Share of the AA/Houthi tally that reports itemise</div><div class="v">{cov if cov is not None else "n/a"}%<small> vs {cov1 if cov1 is not None else "n/a"}%</small></div></div></div>'
           f'<p class="note">Tally given on {S1["tally_n"]} of 7 days in week 1 and {S2["tally_n"]} of 7 in week 2. Share compares only days with a tally.</p>')
    css = """<style>.ag{display:grid;grid-template-columns:450px 1fr;gap:22px;align-items:start}
.si,.sh{display:grid;grid-template-columns:36px 1fr 44px 44px;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid #26282d;font-size:22px}
.sh{font-size:17px;color:#9a9ca3;border-bottom:0}.si b{display:inline-flex;width:30px;height:30px;border-radius:50%;background:#9d8cf2;color:#fff;font:700 16px "IBM Plex Mono",monospace;align-items:center;justify-content:center}
.si em,.sh em{font:700 22px "IBM Plex Mono",monospace;font-style:normal;text-align:right}.sh em{font-size:17px;font-weight:500}.si em.o{color:#9a9ca3}.k3 .kb .v{font-size:44px}.k3 .kb .l{font-size:19px}</style>"""
    sub = f"KSA air strikes counted ≥{S1['air']} to ≥{S2['air']}. AA/Houthi target hits in Saudi Arabia {S1['hits']} to {S2['hits']}."
    body = css + f'<div class="p">{leg}{"".join(s)}</div><div class="p"><h2>Sites hit in Saudi Arabia, 14 days</h2><div class="ag"><div>{"".join(m)}<p class="note">Bright = hit in week 2. Number = site in the list.</p></div><div>{side_}</div></div>{kbs}</div>'
    return page("Yemen weekly SITREP · air war", 5, "Air war and retaliation", sub, body)


# ---------------- Card 6: timing and hotspots
PARTS = ["Night 00–06", "Morning 06–12", "Afternoon 12–18", "Evening 18–24"]


def card6():
    P1 = S1['parts']; P2 = S2['parts']
    t1 = max(1, sum(P1)); t2 = max(1, sum(P2))
    cols = ["#3b3f74", "#d9a441", "#e8793f", "#7b5ad6"]

    def bar(P, t, lbl):
        segs = "".join(f'<i style="flex:{n};background:{c}">{round(n*100/t)}%</i>' for n, c in zip(P, cols) if n)
        return f'<div class="pb"><span>{lbl}</span><div>{segs}</div></div>'
    chg = []
    for j, nm in enumerate(PARTS):
        a, b = round(P1[j] * 100 / t1), round(P2[j] * 100 / t2)
        chg.append(f'<div class="pc"><i style="background:{cols[j]}"></i><b>{nm}</b><span>{a}% → {b}%</span></div>')
    keys = sorted(set(_d1) | set(_d2), key=lambda k_: -(_d2[k_] * 2 + _d1[k_]))[:5]
    m = max([_d1[x] for x in keys] + [_d2[x] for x in keys] + [1])
    H = []
    for key in keys:
        a, b = _d1[key], _d2[key]
        tg = '<span class="tag up">RISING</span>' if b > a else '<span class="tag dn">EASING</span>' if b < a else '<span class="tag w1">STEADY</span>'
        H.append(f'<div class="hr"><span class="hn">{e(key[1])}<small>{e(G[key[0]])}</small>{tg}</span>'
                 f'<span class="hb"><i style="width:{a/m*100:.0f}%;background:#4a4d55"></i></span><span class="hv o">{a}</span>'
                 f'<span class="hb"><i style="width:{b/m*100:.0f}%;background:#e8793f"></i></span><span class="hv">{b}</span></div>')
    css = """<style>.pb{display:grid;grid-template-columns:110px 1fr;gap:14px;align-items:center;margin:12px 0}.pb span{font-size:22px;color:#c8c8c2}
.pb div{display:flex;height:52px;border-radius:12px;overflow:hidden;gap:3px}.pb i{display:flex;align-items:center;justify-content:center;font:700 20px "IBM Plex Mono",monospace;font-style:normal;color:#fff;min-width:44px}
.pcs{display:grid;grid-template-columns:1fr 1fr;gap:10px 30px;margin-top:14px}.pc{font-size:21px;display:flex;align-items:center;gap:10px}.pc i{width:18px;height:18px;border-radius:5px}.pc b{font-weight:500;color:#e4e4de}.pc span{margin-left:auto;font:600 21px "IBM Plex Mono",monospace;color:#c8c8c2}
.hr{display:grid;grid-template-columns:1fr 160px 44px 160px 44px;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #26282d}.hr:last-child{border-bottom:0}
.hn{font-size:24px}.hn small{display:block;font-size:17px;color:#9a9ca3}.hb{height:18px;background:#26282d;border-radius:9px;overflow:hidden}.hb i{display:block;height:100%;border-radius:9px}
.hv{font:700 24px "IBM Plex Mono",monospace}.hv.o{color:#9a9ca3}.hh{display:grid;grid-template-columns:1fr 160px 44px 160px 44px;gap:12px;font-size:18px;color:#9a9ca3}</style>"""
    n1 = round((P1[0] + P1[3]) * 100 / t1); n2 = round((P2[0] + P2[3]) * 100 / t2)
    sub = f"After dark (18:00 to 06:00) {n1}% of timed incidents in week 1, {n2}% in week 2."
    body = css + f'''<div class="p"><h2>Time of day</h2><p class="s">Share of incidents with a reported time, Sana'a time.</p>{bar(P1, t1, "Week 1")}{bar(P2, t2, "Week 2")}<div class="pcs">{"".join(chg)}</div></div>
<div class="p"><h2>Top 5 hotspot districts</h2><div class="hh"><span></span><span>Week 1</span><span></span><span>Week 2</span><span></span></div>{"".join(H)}</div>'''
    return page("Yemen weekly SITREP · timing and hotspots", 6, "When and where it hits", sub, body)


# ---------------- Card 7: the running record since 1 Sep
def cumul(f):
    days = []
    x = dt.date.fromisoformat(START)
    end = _cut.date()
    while x <= end:
        days.append(x.isoformat()); x += dt.timedelta(days=1)
    c = 0; out = []
    for x in days:
        c += f(x); out.append(c)
    return days, out


_ci = Counter(r[1] for r in TOT_INC); _ck = Counter();
for r in ALL:
    _ck[r[1]] += r[6]
_ca = Counter()
for r in TOT_INC:
    if r[3] == 'Air strike':
        _ca[r[1]] += r[9] or 1
_ch = Counter(o[0] for o in OPS_ALL if o[1] == 'KSA')
KEYEV = [dict(d=k['d'], t=re.sub(r'\s*\(claim\)', '', k['t'])) for k in d.get('keyev', [])]


def spark(series, days, col, W=420, H=150, marks=True):
    mx = max(series) or 1
    pts = [(i / (len(series) - 1) * W, H - 8 - v / mx * (H - 22)) for i, v in enumerate(series)]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%"><path d="{path} L{W} {H} L0 {H}Z" fill="{col}" opacity=".18"/><path d="{path}" fill="none" stroke="{col}" stroke-width="4" stroke-linejoin="round"/>']
    if marks:
        for k in KEYEV:
            if k['d'] in days:
                i = days.index(k['d']); x = i / (len(series) - 1) * W
                s.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{H}" stroke="#55585f" stroke-dasharray="3 4"/>')
    s.append('</svg>')
    return "".join(s)


def card7():
    days, ci = cumul(lambda x: _ci[x]); _, ck = cumul(lambda x: _ck[x]); _, ca = cumul(lambda x: _ca[x]); _, ch = cumul(lambda x: _ch[x])
    tiles = [("Security incidents", f"{TOT['inc']:,}", ci, C['acc']), ("Civilians killed", f"{TOT['k']:,}", ck, C['k']),
             ("KSA air strikes counted", f"≥{TOT['air']:,}", ca, C['ksa']), ("AA/Houthi hits in Saudi Arabia", f"{TOT['hits']:,}", ch, C['aa'])]
    T = "".join(f'<div class="rt"><div class="l">{e(t)}</div><div class="v" style="color:{c}">{e(v)}</div>{spark(sr, days, c)}</div>' for t, v, sr, c in tiles)
    W, H = 922, 420; PL = 10
    n = len(WEEKS); bw = (W - PL) / n
    mi = max(w['inc'] for w in WEEKS) or 1; mk = max(w['k'] for w in WEEKS) or 1
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%">']
    BASE = 210
    for j, w in enumerate(WEEKS):
        X = PL + j * bw + 7; ww = bw - 14; cx = X + ww / 2
        last = j == n - 1; op = 0.55 if w["partial"] else 1
        hh = w['inc'] / mi * 160
        s.append(f'<rect x="{X:.1f}" y="{BASE-hh:.1f}" width="{ww:.1f}" height="{hh:.1f}" rx="6" fill="{"#e8793f" if last else "#5a5d66"}" opacity="{op}"/>')
        s.append(f'<text x="{cx:.1f}" y="{BASE-hh-10:.1f}" text-anchor="middle" fill="#f4f4f0" font-size="21" font-weight="700">{w["inc"]}</text>')
        s.append(f'<text x="{cx:.1f}" y="{BASE+27}" text-anchor="middle" fill="#c8c8c2" font-size="17">{lab(w["a"])}</text>')
        kh = w['k'] / mk * 130
        s.append(f'<rect x="{X:.1f}" y="{BASE+40}" width="{ww:.1f}" height="{max(kh,3):.1f}" rx="6" fill="{C["k"] if last else "#8a4a45"}" opacity="{op}"/>')
        s.append(f'<text x="{cx:.1f}" y="{BASE+40+kh+24:.1f}" text-anchor="middle" fill="#ff8a7e" font-size="20" font-weight="700">{w["k"]}</text>')
    s.append('</svg>')
    KE = "".join(f'<span><b>{lab(k["d"])}</b> {e(k["t"])}</span>' for k in KEYEV)
    gv = Counter(r[0] for r in TOT_INC); gk = Counter()
    for r in ALL:
        gk[r[0]] += r[6]
    top = gv.most_common(6); mg = top[0][1] if top else 1
    GV = "".join(f'<div class="gr"><span>{e(G[k_])}</span><span class="gb"><i style="width:{v/mg*100:.0f}%"></i></span><b>{v}</b><em>{gk[k_]} killed</em></div>' for k_, v in top)
    css = """<style>.rg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}.rt{background:#1a1b1f;border:1px solid #2e3036;border-radius:18px;padding:16px 18px 6px}
.rt .l{font-size:21px;color:#b4b5ba}.ke{font-size:19px;color:#c8c8c2;line-height:1.6}.ke .kg{display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;margin-top:6px}.ke span{display:block}.ke span b{color:#e8793f;font-weight:600}.rt .v{font:700 50px/1.1 "IBM Plex Mono",monospace;letter-spacing:-.03em}
.gr{display:grid;grid-template-columns:140px 1fr 60px 120px;gap:12px;align-items:center;margin:9px 0;font-size:22px}.gb{height:16px;background:#26282d;border-radius:8px;overflow:hidden}.gb i{display:block;height:100%;background:linear-gradient(90deg,#b8501f,#e8793f)}
.gr b{font:700 22px "IBM Plex Mono",monospace;text-align:right}.gr em{font:500 18px "IBM Plex Mono",monospace;font-style:normal;color:#ff8a7e}</style>"""
    ri = rank('inc'); rk = rank('k')
    sub = (f"Since 1 Sep, to {d['cut']} Sana'a: {TOT['k']} civilians killed and {TOT['i']} injured. "
           f"Last week ranks {ri[0]} of {ri[1]} for incidents and {rk[0]} of {rk[1]} for civilian deaths.")
    body = css + f'''<div class="rg">{T}</div>
<div class="p ke"><b>Key events</b> (dashed lines above)<div class="kg">{KE}</div></div>
<div class="p"><h2>Week by week</h2><p class="s">Incidents above the line, civilians killed below. Last week highlighted. The first week starts on 1 Sep (partial).</p>{"".join(s)}</div>
<div class="p"><h2>Most hit governorates since 1 Sep</h2>{GV}</div>'''
    return page("Yemen weekly SITREP · the running record", 7, "Since 1 September", sub, body,
                foot=f"1 Sep to {d['cut']} Sana'a · AA/Houthi tally of KSA strikes: {TOT['tally']:,} since 13 Jul, to {TOT['tally_to']}")


# ---------------- Clips (rendered frame by frame, then encoded with ffmpeg)
ANIM_JS = """
<script>
const ease=t=>t<0?0:t>1?1:1-Math.pow(1-t,3);
function setT(t){
 document.querySelectorAll('[data-in]').forEach(el=>{const a=+el.dataset.in,p=ease((t-a)/0.6);el.style.opacity=p;el.style.transform=`translateY(${(1-p)*24}px)`});
 document.querySelectorAll('[data-n]').forEach(el=>{const a=+el.dataset.a,dur=+(el.dataset.d||1.6),p=ease((t-a)/dur),v=+el.dataset.n;el.textContent=(el.dataset.pre||'')+Math.round(v*p).toLocaleString('en-US')+(el.dataset.suf||'')});
 document.querySelectorAll('[data-w]').forEach(el=>{const a=+el.dataset.a,p=ease((t-a)/1.2);el.style.width=(+el.dataset.w*p)+'%'});
 if(window.REC)REC(t);
}
</script>"""


def clip_open():
    rows = [("Civilians killed", S1['k'], S2['k'], True), ("Civilians injured", S1['i'], S2['i'], True), ("Security incidents", S1['inc'], S2['inc'], False),
            ("KSA air strikes counted", S1['air'], S2['air'], False), ("AA/Houthi hits in Saudi Arabia", S1['hits'], S2['hits'], False), ("IRG/PLC attacks", S1['plc'], S2['plc'], False)]
    R = []
    for j, (l, a, b, h) in enumerate(rows):
        m = max(a, b, 1); t0 = 2.6 + j * 0.35
        R.append(f'<div class="vr" data-in="{t0-0.3:.2f}"><div class="vl">{e(l)}</div><div class="vbs">'
                 f'<div class="vb"><span class="b1" data-a="{t0:.2f}" data-w="{a/m*100:.0f}"></span><em data-a="{t0:.2f}" data-n="{a}" data-d="1.2">0</em></div>'
                 f'<div class="vb"><span class="b2{" h" if h else ""}" data-a="{t0+0.2:.2f}" data-w="{b/m*100:.0f}"></span><em data-a="{t0+0.2:.2f}" data-n="{b}" data-d="1.2">0</em></div></div>'
                 f'<div class="vc" data-in="{t0+1.2:.2f}">{chip(a, b, h)}</div></div>')
    big = (f'<div class="bg3"><div data-in="0.9"><b data-a="1.0" data-n="{S2["k"]}" style="color:#ff6b5e">0</b><span>civilians killed</span></div>'
           f'<div data-in="1.1"><b data-a="1.2" data-n="{S2["air"]}" data-pre="≥" style="color:#3d8fef">0</b><span>KSA air strikes counted</span></div>'
           f'<div data-in="1.3"><b data-a="1.4" data-n="{S2["hits"]}" style="color:#9d8cf2">0</b><span>AA/Houthi hits in Saudi Arabia</span></div></div>')
    tot = (f'<div class="p tot" data-in="5.6"><span>Since 1 Sep</span><div><b data-a="5.7" data-n="{TOT["inc"]}">0</b> incidents</div>'
           f'<div><b data-a="5.8" data-n="{TOT["k"]}" style="color:#ff6b5e">0</b> killed</div><div><b data-a="5.9" data-n="{TOT["i"]}" style="color:#ffab9f">0</b> injured</div></div>')
    css = """<style>.vr{display:grid;grid-template-columns:330px 1fr 130px;column-gap:18px;align-items:center;padding:10px 0;border-bottom:1px solid #26282d}
.vl{font-size:24px;color:#e4e4de}.vc{text-align:right}.vbs{display:flex;flex-direction:column;gap:6px;padding-right:86px}.vb{display:flex;align-items:center;gap:12px;height:26px}
.vb span{display:block;height:18px;border-radius:9px;width:0}.b1{background:#4a4d55}.b2{background:linear-gradient(90deg,#b8501f,#e8793f)}.b2.h{background:linear-gradient(90deg,#c4382d,#ff6b5e)}
.vb em{font:600 24px "IBM Plex Mono",monospace;font-style:normal}.vb:first-child em{color:#9a9ca3}
.bg3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}.bg3 div{background:#1a1b1f;border:1px solid #2e3036;border-radius:18px;padding:18px 20px}
.bg3 b{display:block;font:700 66px/1 "IBM Plex Mono",monospace;letter-spacing:-.03em}.bg3 span{font-size:21px;color:#c8c8c2}
.tot{display:flex;align-items:center;gap:26px;font-size:24px;color:#c8c8c2}.tot span{font:600 20px "IBM Plex Mono",monospace;color:#e8793f;text-transform:uppercase;letter-spacing:.08em}.tot b{font:700 36px "IBM Plex Mono",monospace;color:#fff}
[data-in]{opacity:0}</style>"""
    body = css + big + f'<div class="p">{"".join(R)}</div>' + tot
    h = page("Yemen weekly SITREP", 0, HEAD, f"Week 2 ({lab(DAYS[7])} to {lab(DAYS[13])}) against week 1 ({lab(DAYS[0])} to {lab(DAYS[6])}).", body)
    h = h.replace('<b>0/7</b>', '<b>▶</b>').replace('<h1>', '<h1 data-in="0.1">').replace('<p class="sub">', '<p class="sub" data-in="0.4">')
    return h.replace('</body>', ANIM_JS + '</body>'), 8.0


def clip_record():
    # weekly cumulative per governorate + running totals + weekly incidents line drawn week by week
    n = len(WEEKS)
    cum = []; c = Counter(); tk = ti = tinc = 0
    for w in WEEKS:
        c = c + w['gov']; tk += w['k']; ti += w['i']; tinc += w['inc']
        cum.append(dict(end=w['b'], g=dict(c), k=tk, i=ti, inc=tinc, lab=f"{lab(w['a'])} to {lab(min(w['b'], _cut.date().isoformat()))}", wi=w['inc'], wk=w['k']))
    if _cut.date() > B2:
        cum.append(dict(end=_cut.date().isoformat(), g=dict(Counter(r[0] for r in TOT_INC)), k=TOT['k'], i=TOT['i'], inc=TOT['inc'],
                        lab=f"to {lab(_cut.date())}, {d['cut'][-5:]}", wi=cum[-1]['wi'], wk=cum[-1]['wk']))
    MW, MH = 560, 650
    x0, x1, y0, y1 = 42.55, 46.2, 12.55, 17.65
    k = min(MW / (x1 - x0), MH / (y1 - y0))
    P = lambda lon, lat: ((lon - x0) * k, (y1 - lat) * k)
    paths = []
    for nm, mp in d['adm1']:
        key = NAME.get(nm)
        p = "".join("M" + "L".join(f"{P(*q)[0]:.1f} {P(*q)[1]:.1f}" for q in ring) + "Z" for poly in mp for ring in poly)
        paths.append(f'<path d="{p}" data-g="{key}" fill="#202227" stroke="#0f1013" stroke-width="2"/>')
    labels = []
    for key, (lon, lat, _) in CENT.items():
        if x0 < lon < x1 and y0 < lat < y1:
            X, Y = P(lon, lat)
            labels.append(f'<text data-l="{key}" x="{X:.0f}" y="{Y+10:.0f}" text-anchor="middle" fill="#fff" font-size="28" font-weight="700" paint-order="stroke" stroke="#0f1013" stroke-width="5"></text>')
    mx = max(cum[-1]['g'].values())
    js = f"""<script>const CUM={json.dumps(cum)},MX={mx},T0=0.8,T1=8.6;
function REC(t){{const f=Math.max(0,Math.min(1,(t-T0)/(T1-T0)))*(CUM.length-1),i=Math.floor(f),fr=f-i,a=CUM[i],b=CUM[Math.min(i+1,CUM.length-1)];
const lerp=(x,y)=>x+(y-x)*fr;
document.querySelectorAll('[data-g]').forEach(el=>{{const g=el.dataset.g,v=lerp(a.g[g]||0,b.g[g]||0);el.setAttribute('fill',v>0?`rgba(232,121,63,${{(0.22+0.78*Math.pow(v/MX,0.6)).toFixed(2)}})`:'#202227')}});
document.querySelectorAll('[data-l]').forEach(el=>{{const g=el.dataset.l,v=Math.round(lerp(a.g[g]||0,b.g[g]||0));el.textContent=v>0?v:''}});
document.getElementById('r-inc').textContent=Math.round(lerp(a.inc,b.inc)).toLocaleString('en-US');
document.getElementById('r-k').textContent=Math.round(lerp(a.k,b.k));document.getElementById('r-i').textContent=Math.round(lerp(a.i,b.i));
document.getElementById('r-wk').textContent=(fr<0.5?a:b).lab;
const W=330,H=200,n=CUM.length,mi=Math.max(...CUM.map(c=>c.wi)),pts=CUM.map((c,j)=>[j/(n-1)*W,H-10-c.wi/mi*(H-30)]);
let d='M'+pts[0][0]+' '+pts[0][1];for(let j=1;j<=i;j++)d+=' L'+pts[j][0].toFixed(1)+' '+pts[j][1].toFixed(1);
if(i<n-1){{const p=pts[i],q=pts[i+1];d+=' L'+(p[0]+(q[0]-p[0])*fr).toFixed(1)+' '+(p[1]+(q[1]-p[1])*fr).toFixed(1)}}
document.getElementById('r-line').setAttribute('d',d);const ce=(fr<0.5?a:b).end;document.querySelectorAll('.ev .e').forEach(el=>{{el.style.opacity=el.dataset.d<=ce?1:.15}});}}</script>"""
    css = """<style>.rr{display:grid;grid-template-columns:560px 1fr;gap:20px;align-items:start}.rs{display:flex;flex-direction:column;gap:14px}
.rs .kb .v{font-size:58px}.ev b{display:block;font-size:22px;margin-bottom:6px}.ev .e{font-size:21px;color:#c8c8c2;opacity:.15;padding:3px 0}.ev .e span{display:inline-block;width:90px;font:600 20px 'IBM Plex Mono',monospace;color:#e8793f}#r-wk{font:600 24px "IBM Plex Mono",monospace;color:#e8793f}[data-in]{opacity:0}</style>"""
    body = css + f'''<div class="p" data-in="0.2"><div class="rr"><svg viewBox="0 0 {MW} {MH}" width="100%"><rect width="{MW}" height="{MH}" rx="16" fill="#131d26"/>{"".join(paths)}{"".join(labels)}</svg>
<div class="rs"><div class="kb"><div class="l">Week</div><div id="r-wk"></div></div>
<div class="kb"><div class="l">Security incidents</div><div class="v" id="r-inc">0</div></div>
<div class="kb"><div class="l">Civilians killed</div><div class="v" id="r-k" style="color:#ff6b5e">0</div></div>
<div class="kb"><div class="l">Civilians injured</div><div class="v" id="r-i" style="color:#ffab9f">0</div></div>
<div class="kb"><div class="l">Incidents per week</div><svg viewBox="0 0 330 200" width="100%"><path id="r-line" d="" fill="none" stroke="#e8793f" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/></svg></div></div></div>
<p class="note">Number on the map = incidents in the governorate since 1 Sep.</p></div>
<div class="p ev"><b>Key events</b>{"".join(f'<div class="e" data-d="{k["d"]}"><span>{lab(k["d"])}</span>{e(k["t"])}</div>' for k in KEYEV)}</div>'''
    h = page("Yemen weekly SITREP · the running record", "▶", "Since 1 September, week by week", f"Running totals to {d['cut']} Sana'a.", body,
             foot=f"1 Sep to {d['cut']} Sana'a")
    h = h.replace('<b>▶/7</b>', '<b>▶</b>')
    return h.replace('</body>', ANIM_JS + js + '</body>'), 10.0


def render_clip(pw, html_, dur, path, fps=25):
    pg = pw.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
    pg.set_content(html_, wait_until='load')
    hh = pg.evaluate("document.body.scrollHeight")
    hh += hh % 2
    pg.set_viewport_size({'width': 1080, 'height': hh})
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-i', '-',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '22', '-preset', 'medium', '-movflags', '+faststart', path], stdin=subprocess.PIPE)
    N = int(dur * fps)
    for f in range(N + fps):            # 1 s hold at the end
        pg.evaluate(f"setT({min(f, N) / fps})")
        ff.stdin.write(pg.screenshot(type='jpeg', quality=92, clip={'x': 0, 'y': 0, 'width': 1080, 'height': hh}))
    ff.stdin.close(); ff.wait()
    pg.close()
    assert ff.returncode == 0, 'ffmpeg failed'


# ---------------- brief
def brief():
    top = sorted(_g2, key=lambda k_: -_g2[k_])[:2]
    share = round(sum(_g2[k_] for k_ in top) * 100 / max(1, S2['inc']))
    dw2 = [r for r in _dead if r[1] in W2 and r[6]]
    cov = round(S2['air_td'] * 100 / S2['tally']) if S2['tally'] else None
    tg = []
    if HD:
        for o in OPS:
            if o[0] == HD and o[1] == 'KSA':
                nm = o[2].split(' (')[0]
                if nm not in tg:
                    tg.append(nm)
    up = [k_ for k_ in sorted(set(_d1) | set(_d2), key=lambda k_: -(_d2[k_] - _d1[k_])) if _d2[k_] > _d1[k_]][:2]
    P1, P2 = S1['parts'], S2['parts']
    n1 = round((P1[0] + P1[3]) * 100 / max(1, sum(P1))); n2 = round((P2[0] + P2[3]) * 100 / max(1, sum(P2)))
    hl = re.sub(r'<[^>]+>', '', HEAD)
    L = [f"🇾🇪 <b>YEMEN WEEKLY SITREP | {lab(DAYS[7])} to {lab(DAYS[13])}</b>",
         f"<i>Compared with {lab(DAYS[0])} to {lab(DAYS[6])} · Sana'a time</i>", "",
         f"📌 <b>{hl}.</b>",
         f"🩸 {S2['k']} civilians killed, {S2['i']} injured (week before: {S1['k']} and {S1['i']}). The {ordinal(RK[0])} of {RK[1]} full weeks since 1 Sep.",
         f"✈️ KSA air strikes counted ≥{S2['air']} (≥{S1['air']}). AA/Houthis say {S2['hits']} targets hit in Saudi Arabia, KSA says {S2['intc']} missiles and drones intercepted.", "",
         f"2️⃣ Over the 14 days: busiest day {lab(PEAK)} ({_byday[PEAK]} incidents), deadliest {lab(DEADLY)} ({_kil[DEADLY]} killed).",
         f"3️⃣ {' and '.join(f'{G[k_]} ({_g2[k_]})' for k_ in top)} carry {share}% of incidents.",
         "4️⃣ Deadliest: " + "; ".join(f"{where(r)}, {r[6]} killed ({lab(r[1])}){' (disputed)' if r[10] in DISP else ''}" for r in dw2[:3]) + "." if dw2 else "4️⃣ No civilian deaths reported.",
         f"5️⃣ " + (f"{_hit[HD]} AA/Houthi target hits on {lab(HD)}: {', '.join(tg[:5])}. " if HD else "")
         + (f"Reports itemise {cov}% of the strikes AA/Houthis count (tally on {S2['tally_n']} of 7 days)." if cov is not None else ""),
         f"6️⃣ After dark: {n1}% ➜ {n2}% of incidents." + (" Rising: " + ", ".join(f"{k_[1]} ({_d1[k_]} ➜ {_d2[k_]})" for k_ in up) + "." if up else ""), "",
         f"🗂️ <b>Since 1 Sep:</b> {TOT['inc']:,} incidents, {TOT['k']} civilians killed, {TOT['i']} injured, ≥{TOT['air']:,} KSA air strikes counted, {TOT['hits']} AA/Houthi hits in Saudi Arabia.", "",
         "🎬 Below: 7 cards and 2 short clips.",
         '<a href="https://drelmalihi02-ai.github.io/ye-dashboard/">Open the dashboard</a>']
    t = "\n".join(L)
    for bad in ('masirah', 'rnintel', 'spectator', 't.me/', '—', '@', 'claim'):
        assert bad not in t.lower(), 'brief contains forbidden text: ' + bad
    assert len(re.sub(r'<[^>]+>', '', t)) <= 3800, 'brief too long'
    return t


if __name__ == '__main__':
    cards = [card1, card2, card3, card4, card5, card6, card7]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        for n, fn in enumerate(cards, 1):
            h = fn()
            for bad in ('masirah', 'rnintel', 'spectator', 't.me/', '—'):
                assert bad not in h.lower(), (n, bad)
            pg = br.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=2)
            pg.set_content(h, wait_until='load')
            pg.screenshot(path=os.path.join(OUT, f'{n}_card.png'), full_page=True)
            print(n, pg.evaluate("document.body.scrollHeight"))
            pg.close()
        if VIDEO:
            for name, (h, dur) in (('0_open.mp4', clip_open()), ('8_record.mp4', clip_record())):
                for bad in ('masirah', 'rnintel', 'spectator', 't.me/', '—'):
                    assert bad not in h.lower(), (name, bad)
                render_clip(br, h, dur, os.path.join(OUT, name))
                print(name, os.path.getsize(os.path.join(OUT, name)))
        br.close()
    open(os.path.join(OUT, 'sitrep.txt'), 'w').write(brief() + "\n")
    ok = FRESH and S2['inc'] > 0
    json.dump({'ok': ok, 'reason': '' if ok else ('data cut-off ' + d['cut'] + ' does not cover week 2' if not FRESH else 'no incidents in week 2'),
               'w1': [DAYS[0], DAYS[6]], 'w2': [DAYS[7], DAYS[13]], 'cut': d['cut']}, open(os.path.join(OUT, 'status.json'), 'w'))
    print(open(os.path.join(OUT, 'sitrep.txt')).read())
    print(open(os.path.join(OUT, 'status.json')).read())
