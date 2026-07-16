#!/usr/bin/env python3
"""Neofetch-style animated GitHub profile SVG (Andrew6rant aesthetic).

Sequence: ASCII crackers burst in the corners, then the ASCII portrait
(converted from avatar.png) types in line by line, then the info panel.
Pure SMIL — renders inside GitHub's README <img> sandbox.

Regenerate:  sips -z 120 240 avatar.png -s format bmp --out small.bmp
             python3 ascii_profile.py
"""
import json
import os
import struct
import urllib.request
from calendar import monthrange
from datetime import datetime, timezone
from html import escape

USER = "Hemraj8"

# ---------- 0. live GitHub stats (falls back to last-known values offline) ----------
def gh(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def fetch_stats():
    u = gh(f"https://api.github.com/users/{USER}")
    repos = gh(f"https://api.github.com/users/{USER}/repos?per_page=100")
    joined = datetime.fromisoformat(u["created_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    y, m, d = now.year - joined.year, now.month - joined.month, now.day - joined.day
    if d < 0:
        m -= 1
        py, pm = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
        d += monthrange(py, pm)[1]
    if m < 0:
        y, m = y - 1, m + 12
    uptime = f"{y} years, {m} months, {d} days" if m else f"{y} years, {d} days"
    return {
        "uptime": uptime,
        "repos": u["public_repos"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "followers": u["followers"],
        "joined": joined.strftime("%B %Y"),
    }

try:
    STATS = fetch_stats()
    print("stats:", STATS)
except Exception as e:
    print(f"stats fetch failed ({e}), using fallbacks")
    STATS = {"uptime": "3 years, 18 days", "repos": 14, "stars": 3,
             "followers": 1, "joined": "June 2023"}

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

# ---------- 2. pixels -> donut-math shaded ASCII ----------
# Shading a la a1k0n's donut: treat the portrait as a 3D surface (brightness
# = height), compute the surface normal from its gradient, dot it with a
# fixed light direction, and map the result onto the donut character ramp.
import math

RAMP = ".,-~:;=!*#$@"          # the donut's luminance ramp, dim -> bright
LIGHT = (-0.45, -0.55, 0.70)   # fixed light from upper-left, in front

def lum(px):
    return 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]

vals = sorted(lum(px) for row in rows for px in row)
LO, HI = vals[int(len(vals) * 0.05)], vals[int(len(vals) * 0.95)]

def value(px):
    v = (lum(px) - LO) / max(HI - LO, 1)
    return min(max(v, 0.0), 1.0) ** 0.65     # lifted shadows: sculpted look

vmap = [[value(px) for px in row] for row in rows]
MASK = [[vmap[y][x] > 0.05 for x in range(w)] for y in range(h)]   # background = space

# blur the height surface before taking normals — small features (lips,
# moustache) become smooth slopes instead of char noise
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

hmap = blur(blur(vmap))     # double blur: small features (moustache, lips)
                            # become one smooth form, no char noise

def vget(y, x):
    return hmap[min(max(y, 0), h - 1)][min(max(x, 0), w - 1)]

def shaded(y, x):
    """sculpted donut lighting that respects the photo's dark regions:
    the lighting term is scaled by local tone, so hair/eyes/moustache stay
    dark and recognizable while lit areas get the full sculpted treatment"""
    gx = (vget(y, x + 1) - vget(y, x - 1)) * 2.4
    gy = (vget(y + 1, x) - vget(y - 1, x)) * 2.4
    nz = 0.45
    inv = 1.0 / math.sqrt(gx * gx + gy * gy + nz * nz)
    d = max((-gx * LIGHT[0] - gy * LIGHT[1] + nz * LIGHT[2]) * inv, 0.0)
    v = vmap[y][x]
    return min(0.35 * v + 0.80 * d * min(v / 0.45, 1.0), 1.0)

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

# ---------- 3. layout ----------
W, H = 985, 460
ART_X, ART_Y0 = 15, 38                              # bigger portrait, top-aligned
ART_LH = 405 / max(h, 1)                            # line height fills the 405px column
ART_FS = ART_LH * 0.92
ART_W = 390                                         # pixel width of the portrait
COL_X, COL_Y0, LH = 425, 52, 20
PANEL_CHARS = 58                                    # chars per info line

REVEAL_T0 = 0.3    # sketch-draw of the portrait starts
REVEAL_DUR = 2.6   # ...and takes this long to sweep left-to-right
T_INFO = 2.4       # info panel starts

def dots(key, value, extra=0):
    n = PANEL_CHARS - len(key) - len(value) - 4 - extra
    return " " + "." * max(n, 2) + " "

def kv(key, value):
    return (f'<tspan class="cc">. </tspan><tspan class="key">{escape(key)}</tspan>:'
            f'<tspan class="cc">{dots(key, value)}</tspan><tspan class="value">{escape(value)}</tspan>')

def header(label):
    pad = "—" * (PANEL_CHARS - len(label) - 3)
    return f'<tspan class="hdr">{escape(label)}</tspan> <tspan class="cc">-{pad}-</tspan>'

PANEL = [
    header("hemraj@sodisetti"),
    kv("OS", "macOS, Linux"),
    kv("Uptime.GitHub", STATS["uptime"]),
    kv("Host", "Edge-to-Cloud Infrastructure"),
    kv("Kernel", "Systems + ML"),
    kv("IDE", "VS Code, Claude Code"),
    '<tspan class="cc">. </tspan>',
    kv("Languages.Programming", "Python, C++, Rust, Go, CUDA"),
    kv("Languages.Cloud", "AWS, GCP, Docker"),
    kv("Languages.ML", "PyTorch, TensorFlow"),
    '<tspan class="cc">. </tspan>',
    header("- Contact"),
    kv("Email.Personal", "hemrajsodisetti@gmail.com"),
    kv("LinkedIn", "hemraj-sodisetti"),
    kv("GitHub", "github.com/Hemraj8"),
    '<tspan class="cc">. </tspan>',
    header("- GitHub Stats"),
    kv("Repos", f"{STATS['repos']} | Stars: {STATS['stars']}"),
    kv("Followers", f"{STATS['followers']} | Joined: {STATS['joined']}"),
]

# ---------- 4. sketch-draw reveal with a colorful crackling edge ----------
# The portrait is revealed by a clip window that widens left-to-right, as if
# being sketched in. A column of colorful crackling sparks rides the pen edge.
EDGE_COLORS = ["#ffd166", "#ff7b72", "#79c0ff", "#d2a8ff", "#56d364", "#f0f3f6"]
EDGE_CHARS = ["*", "+", "'", "*", ".", "+"]

edge_bits = []
for i in range(16):
    y = 32 + i * 26
    c = EDGE_COLORS[i % len(EDGE_COLORS)]
    ch = EDGE_CHARS[i % len(EDGE_CHARS)]
    xoff = (-6, 2, -2, 6, 0)[i % 5]                  # ragged edge, not a straight line
    blink = 0.10 + (i % 4) * 0.04
    edge_bits.append(
        f'<text x="{xoff}" y="{y}" font-size="{11 + i % 6}" fill="{c}">{ch}'
        f'<animate attributeName="opacity" values="1;0.15;1" dur="{blink:.2f}s" repeatCount="indefinite"/></text>'
    )

SPARKLER = (
    f'<g opacity="0">'
    f'<animate attributeName="opacity" values="0;0;1;1;0" '
    f'keyTimes="0;{REVEAL_T0/(REVEAL_T0+REVEAL_DUR+0.3):.3f};{(REVEAL_T0+0.15)/(REVEAL_T0+REVEAL_DUR+0.3):.3f};0.92;1" '
    f'dur="{REVEAL_T0+REVEAL_DUR+0.3:.1f}s" fill="freeze"/>'
    f'<animateTransform attributeName="transform" type="translate" '
    f'from="{ART_X} 0" to="{ART_X + ART_W + 8} 0" begin="{REVEAL_T0}s" dur="{REVEAL_DUR}s" fill="freeze"/>'
    + "".join(edge_bits) + "</g>"
)

# no persistent sparkles — the card sits still once the sketch reveal is done

# ---------- 5. assemble ----------
# textLength pins each line to an exact pixel width so the layout is
# identical in every renderer regardless of which monospace font loads
import re as _re

CHAR_W = 9.3         # panel: px per character (60 chars ~ 558px)

def plain_len(svg_fragment):
    return len(_re.sub(r"<[^>]+>", "", svg_fragment)
               .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))

# portrait lines are fully drawn; the animated clip window reveals them
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

panel_svg = []
for i, content in enumerate(PANEL):
    t = T_INFO + i * 0.10
    tl = plain_len(content) * CHAR_W
    panel_svg.append(
        f'<text x="{COL_X}" y="{COL_Y0 + i * LH}" textLength="{tl:.0f}" '
        f'lengthAdjust="spacingAndGlyphs" opacity="0">{content}'
        f'<animate attributeName="opacity" begin="{t:.2f}s" dur="0.3s" from="0" to="1" fill="freeze"/></text>'
    )

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Consolas, 'Fira Code', Menlo, monospace" font-size="16">
<style>
  text, tspan {{ white-space: pre; }}
  .key {{ fill: #ffa657; }}
  .value {{ fill: #79c0ff; }}
  .cc {{ fill: #4d5566; }}
  .hdr {{ fill: #e6edf3; font-weight: bold; }}
  .r2 {{ fill: #ff5c50; }}
  .r1 {{ fill: #a83a34; }}
  .o2 {{ fill: #ffa657; }}
  .o1 {{ fill: #b07038; }}
  .e2 {{ fill: #56d364; }}
  .e1 {{ fill: #2f7a3d; }}
  .c2 {{ fill: #39c5cf; }}
  .c1 {{ fill: #1f7f88; }}
  .b2 {{ fill: #58a6ff; }}
  .b1 {{ fill: #3a6ea8; }}
  .p2 {{ fill: #bc8cff; }}
  .p1 {{ fill: #7c4dbb; }}
  .g2 {{ fill: #f0f3f6; }}
  .g1 {{ fill: #97a1ad; }}
</style>
<rect width="{W}" height="{H}" fill="#0d1117" rx="15"/>
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
{SPARKLER}
{"".join(panel_svg)}
</svg>
'''

with open("profile.svg", "w") as f:
    f.write(svg)
print(f"profile.svg written, {len(svg)/1024:.0f} KB, art {len(art_lines)} lines x {w} cols")
