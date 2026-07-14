#!/usr/bin/env python3
"""Neofetch-style animated GitHub profile SVG (Andrew6rant aesthetic).

Sequence: ASCII crackers burst in the corners, then the ASCII portrait
(converted from avatar.png) types in line by line, then the info panel.
Pure SMIL — renders inside GitHub's README <img> sandbox.

Regenerate:  sips -z 30 60 avatar.png -s format bmp --out small.bmp
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

# ---------- 1. read the 60x30 BMP produced by sips ----------
data = open("small.bmp", "rb").read()
off = struct.unpack("<I", data[10:14])[0]
w, h = struct.unpack("<ii", data[18:26])
top_down = h < 0
h = abs(h)
stride = (w * 3 + 3) & ~3
rows = []
for r in range(h):
    y = r if top_down else h - 1 - r
    base = off + y * stride
    row = []
    for x in range(w):
        b, g, rr = data[base + x * 3: base + x * 3 + 3]
        row.append((rr, g, b))
    rows.append(row)

# ---------- 2. pixels -> colored ASCII ----------
RAMP = " .':;=+*#%@"          # sparse -> dense by brightness

# brightness = max channel (red reads as bright, matching how the eye sees the photo),
# contrast-stretched between the image's 5th and 98th percentile
vals = sorted(max(px) for row in rows for px in row)
LO, HI = vals[int(len(vals) * 0.05)], vals[int(len(vals) * 0.98)]

def classify(px):
    r, g, b = px
    v = (max(px) - LO) / max(HI - LO, 1)
    v = min(max(v, 0.0), 1.0)
    ch = RAMP[min(int(v * len(RAMP)), len(RAMP) - 1)]
    if ch == " ":
        return " ", None
    if r > 80 and r > 1.5 * g:                       # red-dominant pixel
        cls = "r2" if v > 0.55 else "r1"
    else:
        cls = "g2" if v > 0.55 else "g1"
    return ch, cls

art_lines = []                 # each line: list of (class, run_of_chars)
for row in rows:
    runs, cur_cls, cur = [], None, ""
    for px in row:
        ch, cls = classify(px)
        key = cls if ch != " " else None
        if key != cur_cls and cur:
            runs.append((cur_cls, cur)); cur = ""
        cur_cls = key
        cur += ch
    if cur:
        runs.append((cur_cls, cur))
    art_lines.append(runs)

# ---------- 3. layout ----------
W, H = 985, 415
ART_X, ART_Y0, ART_LH, ART_FS = 18, 40, 12, 10.5   # top-aligned with the info panel
ART_W = 368                                         # pixel width of the portrait
COL_X, COL_Y0, LH = 400, 30, 20
PANEL_CHARS = 60                                    # chars per info line

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
for i in range(14):
    y = 34 + i * 27
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
  .g2 {{ fill: #c9d1d9; }}
  .g1 {{ fill: #7d8590; }}
</style>
<rect width="{W}" height="{H}" fill="#0d1117" rx="15"/>
<defs>
  <clipPath id="reveal">
    <rect x="{ART_X - 4}" y="{ART_Y0 - 16}" width="0" height="{30 * ART_LH + 24}">
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
