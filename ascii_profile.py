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
    # monochrome: three gray bands by brightness
    cls = "g3" if v > 0.7 else ("g2" if v > 0.4 else "g1")
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
COL_X, COL_Y0, LH = 400, 30, 20
PANEL_CHARS = 60                                    # chars per info line

T_ART = 2.0        # portrait starts typing after the corner crackers
T_INFO = 2.6       # info panel starts

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

# ---------- 4. ASCII crackers (corner fireworks) ----------
# frames of a burst, drawn with text; each frame shows briefly in sequence
FRAMES = [
    ["", "  |", ""],
    ["", "  *", ""],
    [r" \|/", " -o-", r" /|\\"],
    [r"\ ' /", "- * -", r"/ . \\"],
    ["'   `", "  .  ", ",   ."],
]
FRAMES = [[l.replace("\\\\", "\\") for l in f] for f in FRAMES]

def cracker(x, y, t0, color, fs=15, loop=True):
    """Burst at (x,y). loop=True replays every 8s cycle; loop=False plays once."""
    dt = 0.22
    repeat = 'repeatCount="indefinite"' if loop else 'repeatCount="1" fill="freeze"'
    out = []
    for i, frame in enumerate(FRAMES):
        t1, t2 = t0 + i * dt, t0 + (i + 1) * dt
        lines = "".join(
            f'<tspan x="{x}" y="{y + j * fs}">{escape(l)}</tspan>' for j, l in enumerate(frame) if l.strip()
        )
        out.append(
            f'<text font-size="{fs}" fill="{color}" opacity="0">{lines}'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" '
            f'keyTimes="0;{t1/8:.4f};{(t1+0.01)/8:.4f};{(t2-0.01)/8:.4f};{t2/8:.4f};1" '
            f'dur="8s" {repeat}/></text>'
        )
    return "".join(out)

# bursts keep firing on the four corners of the portrait, every 8s;
# the center burst plays once, right before the portrait reveals
CRACKERS = (
    cracker(24, 52, 0.15, "#ffd166")
    + cracker(330, 52, 0.55, "#ff7b72")
    + cracker(24, 360, 0.95, "#79c0ff")
    + cracker(330, 360, 1.35, "#d2a8ff")
    + cracker(160, 200, 1.70, "#ffd166", fs=17, loop=False)
)

# sparkles twinkling over the whole portrait after the intro
SPARK_POS = [
    (8, 34, "*", "#ffd166"), (388, 34, "*", "#ff7b72"), (8, 396, "*", "#79c0ff"),
    (388, 396, "*", "#d2a8ff"), (195, 22, "*", "#ffd166"), (195, 404, "*", "#79c0ff"),
    (60, 120, "+", "#f0f3f6"), (300, 90, "*", "#ffd166"), (140, 70, "+", "#79c0ff"),
    (250, 160, "*", "#d2a8ff"), (90, 250, "+", "#ff7b72"), (330, 230, "*", "#f0f3f6"),
    (180, 310, "+", "#ffd166"), (280, 350, "*", "#79c0ff"), (45, 330, "+", "#d2a8ff"),
    (350, 140, "+", "#ff7b72"),
]
SPARKS = "".join(
    f'<text x="{x}" y="{y}" font-size="{12 + (i % 3)}" fill="{c}" opacity="0">{ch}'
    f'<animate attributeName="opacity" values="0;0.9;0" dur="{1.3 + (i % 5) * 0.45:.2f}s" '
    f'begin="{2.8 + i * 0.33:.2f}s" repeatCount="indefinite"/></text>'
    for i, (x, y, ch, c) in enumerate(SPARK_POS)
)

# ---------- 5. assemble ----------
# textLength pins each line to an exact pixel width so the layout is
# identical in every renderer regardless of which monospace font loads
import re as _re

ART_W = 368          # pixel width of the 60-char portrait lines
CHAR_W = 9.3         # panel: px per character (60 chars ~ 558px)

def plain_len(svg_fragment):
    return len(_re.sub(r"<[^>]+>", "", svg_fragment)
               .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))

art_svg = []
for i, runs in enumerate(art_lines):
    spans = "".join(
        f'<tspan class="{cls}">{escape(txt)}</tspan>' if cls else f"<tspan>{escape(txt)}</tspan>"
        for cls, txt in runs
    )
    t = T_ART + i * 0.045
    art_svg.append(
        f'<text x="{ART_X}" y="{ART_Y0 + i * ART_LH}" font-size="{ART_FS}" '
        f'textLength="{ART_W}" lengthAdjust="spacingAndGlyphs" opacity="0">{spans}'
        f'<animate attributeName="opacity" begin="{t:.2f}s" dur="0.25s" from="0" to="1" fill="freeze"/></text>'
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
  .g3 {{ fill: #f0f3f6; }}
  .g2 {{ fill: #aab4bf; }}
  .g1 {{ fill: #5c6570; }}
</style>
<rect width="{W}" height="{H}" fill="#0d1117" rx="15"/>
{CRACKERS}
{SPARKS}
<!-- portrait shivers briefly every few seconds -->
<g>
<animateTransform attributeName="transform" type="translate" begin="{T_ART + 1.5:.1f}s"
  values="0 0;2 -1.5;-2 1.5;1.5 2;-1.5 -2;1 1;0 0;0 0"
  keyTimes="0;0.02;0.04;0.06;0.08;0.1;0.12;1" dur="4s" repeatCount="indefinite"/>
{"".join(art_svg)}
</g>
{"".join(panel_svg)}
</svg>
'''

with open("profile.svg", "w") as f:
    f.write(svg)
print(f"profile.svg written, {len(svg)/1024:.0f} KB, art {len(art_lines)} lines x {w} cols")
