# Day-by-day motion clip of the escalation, for the Telegram channel and the dashboard.
# Reads the built dashboard data (yemen-dashboard.html), writes escalation.mp4 (1080x1080, H.264).
# Usage: python3 video.py [out.mp4] [page.html]   (page defaults to yemen-dashboard.html; the public index.html works too)
# The ye-dashboard GitHub Action runs a copy (tools/video.py) on index.html before each Telegram post.
import json, re, sys, math, subprocess, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import numpy as np
import matplotlib.patheffects as pe

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "escalation.mp4")
s = open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "yemen-dashboard.html")).read()
D = json.loads(re.search(r"const D=(\{.*?\});\n", s).group(1))

INC = {"Artillery", "Rockets", "Air strike", "Drone", "Unspecified attack", "Ground operation", "PLC shelling", "PLC sniper fire"}
START = "2026-09-01"
from datetime import date, timedelta
d0 = date.fromisoformat(START)
last = max(r[1] for r in D["ev"])
DAYS = [(d0 + timedelta(i)).isoformat() for i in range((date.fromisoformat(last) - d0).days + 1)]
NDAY = len(DAYS); DI = {d: i for i, d in enumerate(DAYS)}

# ---------- data per day ----------
GEO = {}
for g, ds in D["geo"].items():
    for n, c, _ in ds: GEO[(g, n)] = c
GOVC = {g: (np.mean([c[0] for _, c, _ in ds]), np.mean([c[1] for _, c, _ in ds])) for g, ds in D["geo"].items() if ds}
def normd(d): return "Haydan" if d.startswith("Marran") else d
pts = {}  # key -> [lon, lat, daily counts]
daily = np.zeros(NDAY); killed = np.zeros(NDAY); injured = np.zeros(NDAY)
for r in D["ev"]:
    g, dt, cat, dists, k, i = r[0], r[1], r[3], r[4], r[6], r[7]
    if dt < START or dt not in DI: continue
    di = DI[dt]; killed[di] += k; injured[di] += i
    if cat not in INC: continue
    daily[di] += 1
    placed = False
    for dn in (dists or []):
        geo = (D["gname"].get(g) or {}).get(normd(dn))
        if geo and (g, geo) in GEO:
            key = (g, geo); c = GEO[key]
            pts.setdefault(key, [c[0], c[1], np.zeros(NDAY)])[2][di] += 1; placed = True
    if not placed and g in GOVC:
        key = (g, "*"); c = GOVC[g]
        pts.setdefault(key, [c[0], c[1], np.zeros(NDAY)])[2][di] += 1
KEYS = list(pts); PX = np.array([[pts[k][0], pts[k][1]] for k in KEYS])
CUM = np.cumsum(np.array([pts[k][2] for k in KEYS]), axis=1)  # keys x days
HIT = np.array([pts[k][2] for k in KEYS]) > 0
tally = np.array([D["tally"].get(d, 0) or 0 for d in DAYS])
ops = [o for o in D["ops"] if o[0] >= START and o[0] in DI]
ksa_daily = np.zeros(NDAY)
for o in ops:
    if o[1] == "KSA": ksa_daily[DI[o[0]]] += 1
BB = [41.3, 50.2, 12.45, 18.75]
opl = [o for o in ops if o[6] is not None and BB[0] <= o[6] <= BB[1] and BB[2] <= o[7] <= BB[3] and o[1] in ("KSA", "GROUND")]
OPX = np.array([[o[6], o[7]] for o in opl]) if opl else np.zeros((0, 2))
OPD = np.array([DI[o[0]] for o in opl]); OPK = [o[1] for o in opl]

# ---------- look ----------
BG = "#141517"; SEA = "#17202a"; LAND = "#24262a"; LANDYE = "#2c2b28"; BORDER = "#45474d"; INK = "#f1f1ee"; INK2 = "#c3c3bd"; MUTED = "#8d9098"
ACC = "#e0743f"; HOT = "#ff5a4e"; WARM = "#e0743f"; OLD = "#8c6a58"; KSA = "#a68cf0"; GND = "#4fb3a9"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
W = 1080
fig = plt.figure(figsize=(10.8, 10.8), dpi=100, facecolor=BG)
k = math.cos(math.radians((BB[2] + BB[3]) / 2))
ax = fig.add_axes([0.02, 0.365, 0.96, 0.545]); ax.set_facecolor(SEA)
ax.set_xlim(BB[0], BB[1]); ax.set_ylim(BB[2], BB[3]); ax.set_aspect(1 / k, adjustable="datalim")
ax.set_xticks([]); ax.set_yticks([])
for sp in ax.spines.values(): sp.set_visible(False)
def polys(pl, **kw):
    ps = [Polygon(np.array(p[0]), closed=True) for p in pl]
    ax.add_collection(PatchCollection(ps, **kw))
for n, pl in D["world"]:
    polys(pl, facecolor=LANDYE if n == "Yemen" else LAND, edgecolor=BORDER, linewidth=0.8, zorder=1)
for f, n, rings in D["ctrl"]:
    col = "#e0675c" if f == "AA" else "#36a865"
    ax.add_patch(Polygon(np.array(rings[0]), closed=True, facecolor=col, alpha=0.10, edgecolor="none", zorder=2))
for n, pl in D["adm1"]:
    polys(pl, facecolor="none", edgecolor="#55575d", linewidth=0.5, zorder=3)
for t, x, y in [("SAUDI ARABIA", 46.6, 18.45), ("RED SEA", 41.75, 15.3), ("GULF OF ADEN", 48.2, 12.75), ("ERITREA", 41.3, 13.9)]:
    ax.text(x, y, t, color="#5d6068", fontsize=10, ha="center", va="center", zorder=4, fontweight="bold")
for t, x, y in [("Sa'dah", 43.75, 16.95), ("Al-Jawf", 45.3, 16.35), ("Sana'a", 44.2, 15.25), ("Hodeidah", 42.95, 14.75), ("Marib", 45.6, 15.2), ("Taiz", 43.95, 13.35), ("Aden", 45.0, 12.62), ("Hajjah", 43.25, 16.05), ("Hadramawt", 49.5, 16.0), ("Shabwah", 47.0, 14.6)]:
    ax.text(x, y, t, color="#b9bcc2", fontsize=10, ha="center", va="center", zorder=9, path_effects=[pe.withStroke(linewidth=2.6, foreground="#1b1c1f")])
ring = ax.scatter([], [], s=[], facecolors="none", edgecolors=HOT, linewidths=1.6, zorder=6)
dots = ax.scatter(PX[:, 0], PX[:, 1], s=np.zeros(len(KEYS)), c=[OLD] * len(KEYS), edgecolors=BG, linewidths=0.6, zorder=7)
opsc = ax.scatter([], [], s=[], marker="^", zorder=8, edgecolors=BG, linewidths=0.6)

# header
fig.text(0.04, 0.965, "YEMEN ESCALATION", fontsize=26, fontweight="bold", color=INK, va="center")
fig.text(0.04, 0.933, "Incidents by district, day by day since 1 Sep 2026", fontsize=13.5, color=INK2, va="center")
dtxt = fig.text(0.96, 0.955, "", fontsize=32, fontweight="bold", color=ACC, ha="right", va="center")
# legend
lx = 0.04; ly = 0.338
for col, lab in [(HOT, "Hit today"), (WARM, "Last 7 days"), (OLD, "Earlier")]:
    fig.patches.append(plt.Circle((lx * W, ly * W), 7, transform=None, color=col, figure=fig)); fig.text(lx + 0.016, ly, lab, fontsize=11.5, color=INK2, va="center"); lx += 0.135
fig.text(lx + 0.0, ly, "▲", fontsize=13, color=KSA, va="center"); fig.text(lx + 0.022, ly, "AA strike on Saudi territory", fontsize=11.5, color=INK2, va="center")
fig.text(lx + 0.29, ly, "◆", fontsize=12, color=GND, va="center"); fig.text(lx + 0.31, ly, "AA ground operation", fontsize=11.5, color=INK2, va="center")
# counters
CNT = [("Incidents", INK), ("Civilians killed", "#ff7b72"), ("Civilians injured", "#6aa8f0"), ("Saudi strikes\nclaimed by AA", ACC), ("AA strikes on\nSaudi territory", KSA)]
ctx = []
for j, (lab, col) in enumerate(CNT):
    x = 0.04 + j * 0.19
    ctx.append(fig.text(x, 0.282, "0", fontsize=30, fontweight="bold", color=col, va="center"))
    fig.text(x, 0.238, lab, fontsize=11.5, color=MUTED, va="center", linespacing=1.2)
# daily bars
bx = fig.add_axes([0.04, 0.062, 0.92, 0.1]); bx.set_facecolor(BG)
for sp in bx.spines.values(): sp.set_visible(False)
bars = bx.bar(range(NDAY), np.zeros(NDAY), width=0.72, color=WARM)
bx.bar(range(NDAY), daily, width=0.72, color="#2a2c30", zorder=0)
bx.set_xlim(-0.8, NDAY - 0.2); bx.set_ylim(0, max(daily.max(), 1) * 1.08)
bx.set_yticks([]); ticks = [i for i, d in enumerate(DAYS) if d.endswith("-01") or d.endswith("-15")]
bx.set_xticks(ticks); bx.set_xticklabels([date.fromisoformat(DAYS[i]).strftime("%-d %b") for i in ticks], color=MUTED, fontsize=10.5)
bx.tick_params(length=0, pad=4)
fig.text(0.04, 0.183, "Incidents per day", fontsize=11.5, color=MUTED, va="center")
fig.text(0.96, 0.022, "YE Paradise  ·  drelmalihi02-ai.github.io/ye-dashboard", fontsize=11, color=MUTED, ha="right", va="center")

RMAX = 34.0; VMAX = max(CUM[:, -1].max(), 1)
def size(v): return (np.sqrt(np.maximum(v, 0) / VMAX) * RMAX) ** 2 * (v > 0)
def ease(t): return 1 - (1 - t) ** 3
FPD = 14; FPS = 30
cum_daily = np.cumsum(daily); cum_k = np.cumsum(killed); cum_i = np.cumsum(injured); cum_t = np.cumsum(tally); cum_ksa = np.cumsum(ksa_daily)

def frame(di, t):
    prev = CUM[:, di - 1] if di > 0 else np.zeros(len(KEYS))
    v = prev + (CUM[:, di] - prev) * ease(t)
    dots.set_sizes(size(v))
    lasthit = np.full(len(KEYS), -999)
    for j in range(len(KEYS)):
        h = np.nonzero(HIT[j, :di + 1])[0]
        if len(h): lasthit[j] = h[-1]
    age = di - lasthit
    dots.set_facecolors([HOT if a == 0 else WARM if a <= 6 else OLD for a in age])
    today = HIT[:, di]
    if today.any() and t < 1:
        ring.set_offsets(PX[today]); ring.set_sizes(size(CUM[today, di]) * (1 + 3.2 * t) + 60 * t)
        ring.set_alpha(max(0, 1 - t))
    else:
        ring.set_offsets(np.zeros((0, 2)))
    if len(OPX):
        m = OPD <= di
        grow = np.where(OPD[m] == di, ease(min(1, t * 1.6)), 1.0)
        opsc.set_offsets(OPX[m]); opsc.set_sizes(150 * grow)
        opsc.set_facecolors([KSA if OPK[i] == "KSA" else GND for i in np.nonzero(m)[0]])
        opsc.set_paths([matplotlib.markers.MarkerStyle("^" if OPK[i] == "KSA" else "D").get_path().transformed(matplotlib.markers.MarkerStyle("^" if OPK[i] == "KSA" else "D").get_transform()) for i in np.nonzero(m)[0]])
    dtxt.set_text(date.fromisoformat(DAYS[di]).strftime("%-d %b %Y"))
    def lerp(arr): p = arr[di - 1] if di > 0 else 0; return int(round(p + (arr[di] - p) * ease(t)))
    for c, arr in zip(ctx, [cum_daily, cum_k, cum_i, cum_t, cum_ksa]): c.set_text(f"{lerp(arr):,}")
    for j, b in enumerate(bars):
        b.set_height(daily[j] if j < di else daily[j] * ease(t) if j == di else 0)
        b.set_color(HOT if j == di else WARM)

proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{W}", "-r", str(FPS), "-i", "-",
                         "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
def emit(n=1):
    fig.canvas.draw(); buf = fig.canvas.buffer_rgba()
    for _ in range(n): proc.stdin.write(bytes(buf))
frame(0, 0.0); emit(FPS)  # 1 s intro hold
for di in range(NDAY):
    for f in range(FPD): frame(di, (f + 1) / FPD); emit()
for j, b in enumerate(bars): b.set_color(WARM)
emit(FPS * 3)  # 3 s end hold
proc.stdin.close(); proc.wait()
print("video", OUT, f"{os.path.getsize(OUT)/1e6:.1f} MB", f"{(FPS*4+NDAY*FPD)/FPS:.1f} s", len(KEYS), "places", len(opl), "ops")
