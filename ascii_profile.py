#!/usr/bin/env python3
"""ASCII portrait card for the GitHub profile README.

The photo (avatar.png, background removed via cutout.swift) becomes a
donut-ramp ASCII portrait that sketches itself in left-to-right.
Pure SMIL — renders inside GitHub's README <img> sandbox.

Regenerate:  sips -z 120 260 avatar.png -s format bmp --out small.bmp
             python3 ascii_profile.py
"""
import json
import os
import struct
import urllib.request
from datetime import datetime
from html import escape

# ---------- 0. live GitHub stats (static fallback offline) ----------
USER = "Hemraj8"

def _gh(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

try:
    u = _gh(f"https://api.github.com/users/{USER}")
    reps = _gh(f"https://api.github.com/users/{USER}/repos?per_page=100")
    joined = datetime.fromisoformat(u["created_at"].replace("Z", "+00:00"))
    STATS = {"repos": u["public_repos"], "stars": sum(r["stargazers_count"] for r in reps),
             "followers": u["followers"], "joined": joined.strftime("%B %Y")}
    print("stats:", STATS)
except Exception as e:
    print("stats fallback:", e)
    STATS = {"repos": 14, "stars": 3, "followers": 1, "joined": "June 2023"}

# ---------- 1. read the BMP produced by sips (2x the char grid) ----------
data = open("small.bmp", "rb").read()
off = struct.unpack("<I", data[10:14])[0]
w, h = struct.unpack("<ii", data[18:26])
bpp = struct.unpack("<H", data[28:30])[0] // 8      # bytes per pixel: 3 or 4 (BGRA)
top_down = h < 0
h = abs(h)
stride = (w * bpp + 3) & ~3
rows = []
for r in range(h):
    y = r if top_down else h - 1 - r
    base = off + y * stride
    row = []
    for x in range(w):
        b, g, rr = data[base + x * bpp: base + x * bpp + 3]
        row.append((rr, g, b))
    rows.append(row)

# 2x2 box-average down to the final character grid (kills pixel speckle)
DS = 2
grid = []
for gy in range(h // DS):
    grow = []
    for gx in range(w // DS):
        ps = [rows[gy * DS + dy][gx * DS + dx] for dy in range(DS) for dx in range(DS)]
        grow.append(tuple(sum(p[i] for p in ps) // len(ps) for i in range(3)))
    grid.append(grow)
rows, h, w = grid, h // DS, w // DS

# ---------- 2. pixels -> maximal-clarity donut-ramp ASCII ----------
# The photo already carries real 3D lighting (it was shot in sunlight), so
# the pipeline focuses on tonal clarity instead of synthetic shading:
#   1. histogram-equalize the subject's tones -> every ramp character gets
#      used, so no detail is crushed into one brightness level
#   2. unsharp mask -> local contrast pop on features (jaw, collar, hairline)
import bisect

RAMP = ".,-~:;=!*#$@"          # the donut's luminance ramp, dim -> bright

def lum(px):
    return (0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]) / 255

raw = [[lum(px) for px in row] for row in rows]
MASK = [[raw[y][x] > 0.03 for x in range(w)] for y in range(h)]    # background = space

subj = sorted(raw[y][x] for y in range(h) for x in range(w) if MASK[y][x])
S_LO = subj[int(len(subj) * 0.02)]
S_HI = subj[int(len(subj) * 0.98)]

def tone(v):
    """blend of histogram equalization (detail everywhere) and a plain
    contrast stretch (keeps large areas smooth)"""
    eq = bisect.bisect_right(subj, v) / len(subj)
    st = min(max((v - S_LO) / max(S_HI - S_LO, 1e-6), 0.0), 1.0)
    return 0.6 * eq + 0.4 * st

vmap = [[tone(raw[y][x]) if MASK[y][x] else 0.0 for x in range(w)] for y in range(h)]

def blur(m):
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            acc = tot = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    wt = (2 if dy == 0 else 1) * (2 if dx == 0 else 1)
                    ny, nx = min(max(y + dy, 0), h - 1), min(max(x + dx, 0), w - 1)
                    acc += m[ny][nx] * wt
                    tot += wt
            row.append(acc / tot)
        out.append(row)
    return out

base = blur(vmap)

def shaded(y, x):
    """unsharp mask: v + k*(v - blurred v) — the classic clarity operator"""
    v = vmap[y][x]
    return min(max(v + 0.55 * (v - base[y][x]), 0.0), 1.0)

def classify(y, x):
    if not MASK[y][x]:
        return " ", None, None
    s = shaded(y, x)
    ch = RAMP[min(int(s * len(RAMP)), len(RAMP) - 1)]
    # monochrome, like the terminal donut: density does the shading
    return ch, "g", "2" if s > 0.6 else "1"

# classify every cell, then smooth color families with a neighbor vote —
# a cell surrounded by mostly one family joins it (kills rainbow confetti)
cells = [[classify(y, x) for x in range(w)] for y in range(h)]

def voted(cy, cx):
    ch, fam, band = cells[cy][cx]
    if fam is None:
        return None
    votes = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == dx == 0:
                continue
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and cells[ny][nx][1]:
                nf = cells[ny][nx][1]
                votes[nf] = votes.get(nf, 0) + 1
    if votes:
        top, n = max(votes.items(), key=lambda kv: kv[1])
        if top != fam and n >= 4 and votes.get(fam, 0) <= 2:
            return top
    return fam

smoothed = [[voted(cy, cx) for cx in range(w)] for cy in range(h)]

art_lines = []                 # each line: list of (class, run_of_chars)
for cy in range(h):
    runs, cur_cls, cur = [], None, ""
    for cx in range(w):
        ch, _, band = cells[cy][cx]
        fam = smoothed[cy][cx]
        key = fam + band if (ch != " " and fam) else None
        if key != cur_cls and cur:
            runs.append((cur_cls, cur)); cur = ""
        cur_cls = key
        cur += ch
    if cur:
        runs.append((cur_cls, cur))
    art_lines.append(runs)

# ---------- 3. layout: a terminal window ----------
# mac chrome; left = portrait + caption + "right now" bars;
# right = big name, toolchain rack, github stats, live plan. one orange accent.
ICONS = json.load(open("tool_icons.json"))

W, H = 980, 624
TB = 46                                             # titlebar height
ART_X, ART_Y0 = 18, TB + 18
ART_W = 468                                         # bigger portrait
ART_LH = 436 / max(h, 1)                            # taller: fixes the squeeze (true aspect ~430)
ART_FS = ART_LH * 0.92
RX = 512                                            # right column x (portrait grew)
NOTE_END = W - 26

REVEAL_T0 = 0.3    # sketch-draw of the portrait starts
REVEAL_DUR = 2.2   # ...and takes this long to sweep left-to-right
T_NAME = REVEAL_T0 + REVEAL_DUR
BAR_CW = 7.2       # char width at font-size 12

def fade(t):
    return f'<animate attributeName="opacity" begin="{t:.2f}s" dur="0.4s" from="0" to="1" fill="freeze"/>'

def blink(color):
    return (f'<tspan fill="{color}">▊<animate attributeName="fill-opacity" '
            f'values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></tspan>')

# ---- window chrome ----
TITLEBAR = (
    f'<path d="M0 15 A15 15 0 0 1 15 0 H{W - 15} A15 15 0 0 1 {W} 15 V{TB} H0 Z" fill="#0a0a0a"/>'
    f'<line x1="0" y1="{TB}" x2="{W}" y2="{TB}" stroke="#2a2a2a" stroke-width="1"/>'
    f'<circle cx="26" cy="23" r="6" fill="#ff5f56"/>'
    f'<circle cx="46" cy="23" r="6" fill="#febc2e"/>'
    f'<circle cx="66" cy="23" r="6" fill="#28c840"/>'
    f'<text x="{W/2:.0f}" y="27" text-anchor="middle" font-size="12" fill="#6e7681">hemraj@sodisetti — -zsh — 96×30</text>'
)

# ---- left: caption + "right now" bars under the portrait ----
CAP = "not a stock avatar — me, rendered as 130×60 chars of .,-~:;=!*#$@"
BARS = [("building", 90), ("learning", 65), ("sleeping", 15)]
BAR_N = 42
left = [
    f'<text x="20" y="528" font-size="10" fill="#aeb6c0" opacity="0">{escape(CAP)}{fade(T_NAME)}</text>',
    f'<text x="20" y="554" font-size="11" fill="#6e7681" opacity="0">// right now{fade(T_NAME + 0.15)}</text>',
]
for i, (label, pct) in enumerate(BARS):
    y = 576 + i * 21
    t0 = T_NAME + 0.3 + i * 0.2
    filled = round(pct * BAR_N / 100)
    fw = filled * BAR_CW
    left.append(
        f'<g opacity="0"><animate attributeName="opacity" begin="{t0:.2f}s" dur="0.35s" from="0" to="1" fill="freeze"/>'
        f'<text x="22" y="{y}" font-size="12" fill="#8b949e" textLength="72" lengthAdjust="spacingAndGlyphs">{label}</text>'
        f'<text x="112" y="{y}" font-size="12" fill="#242a33" textLength="{BAR_N * BAR_CW:.0f}" lengthAdjust="spacingAndGlyphs">{"▏" * BAR_N}</text>'
        f'<clipPath id="bf{i}"><rect x="112" y="{y - 12}" width="0" height="16">'
        f'<animate attributeName="width" from="0" to="{fw + 1:.0f}" begin="{t0 + 0.15:.2f}s" dur="0.7s" '
        f'calcMode="spline" keySplines="0.2 0.7 0.3 1" fill="freeze"/></rect></clipPath>'
        f'<text x="112" y="{y}" font-size="12" fill="#f97316" clip-path="url(#bf{i})" '
        f'textLength="{fw:.0f}" lengthAdjust="spacingAndGlyphs">{"▎" * filled}</text>'
        f'<text x="{ART_X + ART_W}" y="{y}" font-size="12" fill="#c9d1d9" text-anchor="end" '
        f'font-variant-numeric="tabular-nums">{pct}%</text></g>'
    )

# ---- right: name, subtitle, toolchain, plan ----
divider = f'<rect x="{RX - 22}" y="{TB + 18}" width="1" height="{H - TB - 54}" fill="#2a2a2a"/>'

name = (
    f'<g opacity="0">{fade(T_NAME)}'
    f'<text x="{RX}" y="118" font-size="30" font-weight="bold" letter-spacing="2">'
    f'<tspan fill="#f0f3f6">HEMRAJ SODISETTI</tspan>{blink("#f97316")}</text>'
    f'<text x="{RX + 2}" y="148" font-size="13" letter-spacing="2">'
    + '<tspan fill="#f97316"> · </tspan>'.join(
        f'<tspan fill="#8b949e">{s}</tspan>' for s in ("SYSTEM ENGINEER", "BUILDER", "PROBLEM SOLVER")
    )
    + '</text></g>'
)

# toolchain: bordered box with a notched label, brand icons + captions
BX, BY, BW, BH = RX, 174, W - RX - 16, 94
def icon(d, cx, cy, size=21, fill="#c9d1d9"):
    s = size / 24
    return (f'<g transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) scale({s:.4f})">'
            f'<path d="{d}" fill="{fill}"/></g>')

tool = [
    f'<g opacity="0">{fade(T_NAME + 0.4)}'
    f'<rect x="{BX}" y="{BY}" width="{BW}" height="{BH}" rx="8" fill="none" stroke="#2a2a2a"/>'
    f'<rect x="{BX + 16}" y="{BY - 7}" width="86" height="14" fill="#000000"/>'
    f'<text x="{BX + 22}" y="{BY + 3}" font-size="10" letter-spacing="1.5" fill="#6e7681">// TOOLCHAIN</text>'
]
for i, ic in enumerate(ICONS):
    cx = BX + 20 + (BW - 40) / len(ICONS) * (i + 0.5)
    tool.append(icon(ic["d"], cx, BY + 40))
    tool.append(
        f'<text x="{cx:.0f}" y="{BY + 72}" text-anchor="middle" font-size="7.5" '
        f'letter-spacing="0.5" fill="#6e7681">{escape(ic["label"])}</text>'
    )
tool.append('</g>')

# ---- github stats: header with divider + 2x2 dotted grid ----
def stat(key, val, x, y, chars=27):
    n = max(chars - len(key) - len(str(val)) - 2, 2)
    return (f'<text x="{x}" y="{y}" font-size="13">'
            f'<tspan fill="#f97316">{escape(key)}</tspan>'
            f'<tspan fill="#2d333b"> {"." * n} </tspan>'
            f'<tspan fill="#e6edf3">{escape(str(val))}</tspan></text>')

GC = RX + 232   # right stat column
stats = (
    f'<g opacity="0">{fade(T_NAME + 0.9)}'
    f'<text x="{RX}" y="322" font-size="13" letter-spacing="1">'
    f'<tspan fill="#f97316">&gt;</tspan><tspan fill="#e6edf3"> GITHUB STATS</tspan></text>'
    f'<line x1="{RX + 128}" y1="318" x2="{W - 16}" y2="318" stroke="#2a2a2a"/>'
    f'{stat("Repos", STATS["repos"], RX, 356, chars=24)}{stat("Joined", STATS["joined"], GC, 356, chars=24)}'
    f'</g>'
)

plan = (
    f'<text x="{RX}" y="444" font-size="13" opacity="0">'
    f'<tspan fill="#f97316">$</tspan><tspan fill="#e6edf3"> tail -1 ~/.plan</tspan>{fade(T_NAME + 1.4)}</text>'
    f'<text x="{RX}" y="474" font-size="13" fill="#8b949e" opacity="0">tools change. shipping doesn\'t.{fade(T_NAME + 1.55)}</text>'
    f'<text x="{RX}" y="514" font-size="13" opacity="0">'
    f'<tspan fill="#f97316">$</tspan><tspan fill="#e6edf3"> open a PR</tspan> {blink("#e6edf3")}{fade(T_NAME + 1.8)}</text>'
)

# ---- contact buttons: inside the terminal, under the plan (mirrors make_buttons.py) ----
BTN_ICONS = json.load(open("btn_icons.json"))
BTN_H = 40
BTN_Y = 552

def envelope(color):
    return (f'<rect x="1.5" y="4" width="21" height="16" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<path d="M2 6 L12 13 L22 6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')

def btn(x, label, icon_svg, color, text_color):
    bw = 44 + int(len(label) * 8.4) + 20
    g = (f'<g transform="translate({x:.0f},{BTN_Y})">'
         f'<rect x="1" y="1" width="{bw - 2}" height="{BTN_H - 2}" rx="7" fill="#0a0a0a" stroke="{color}" stroke-width="1.2"/>'
         f'<g transform="translate(15,{BTN_H / 2 - 8}) scale(0.667)">{icon_svg}</g>'
         f'<text x="42" y="{BTN_H / 2 + 4:.0f}" font-size="12" letter-spacing="1.5" fill="{text_color}" font-weight="bold">{label}</text>'
         f'</g>')
    return g, bw

ORANGE = "#f97316"
email_btn, ew = btn(RX, "EMAIL", envelope(ORANGE), ORANGE, ORANGE)
li_btn, _ = btn(RX + ew + 14, "LINKEDIN",
                f'<path d="{BTN_ICONS["linkedin"]}" fill="#c9d1d9"/>', "#30363d", "#8b949e")
buttons = f'<g opacity="0">{fade(T_NAME + 2.0)}{email_btn}{li_btn}</g>'

BARS_SVG = TITLEBAR + divider + "".join(left) + name + "".join(tool) + stats + plan + buttons

# ---------- 4. assemble ----------
# textLength pins each line to an exact pixel width so the layout is
# identical in every renderer regardless of which monospace font loads.
# The portrait is fully drawn; an animated clip window reveals it.
art_svg = []
for i, runs in enumerate(art_lines):
    spans = "".join(
        f'<tspan class="{cls}">{escape(txt)}</tspan>' if cls else f"<tspan>{escape(txt)}</tspan>"
        for cls, txt in runs
    )
    art_svg.append(
        f'<text x="{ART_X}" y="{ART_Y0 + i * ART_LH}" font-size="{ART_FS}" '
        f'textLength="{ART_W}" lengthAdjust="spacingAndGlyphs">{spans}</text>'
    )

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Consolas, 'Fira Code', Menlo, monospace">
<style>
  text, tspan {{ white-space: pre; }}
  .g2 {{ fill: #f0f3f6; }}
  .g1 {{ fill: #97a1ad; }}
</style>
<rect width="{W}" height="{H}" fill="#000000" rx="15"/>
<defs>
  <clipPath id="reveal">
    <rect x="{ART_X - 4}" y="{ART_Y0 - 16}" width="0" height="{h * ART_LH + 24:.0f}">
      <animate attributeName="width" from="0" to="{ART_W + 12}"
        begin="{REVEAL_T0}s" dur="{REVEAL_DUR}s" fill="freeze"/>
    </rect>
  </clipPath>
</defs>
<g clip-path="url(#reveal)">
{"".join(art_svg)}
</g>
{BARS_SVG}
</svg>
'''

with open("profile.svg", "w") as f:
    f.write(svg)
print(f"profile.svg written, {len(svg)/1024:.0f} KB, art {len(art_lines)} lines x {w} cols")
