#!/usr/bin/env python3
"""ASCII portrait card for the GitHub profile README.

The photo (avatar.png, background removed via cutout.swift) becomes a
donut-ramp ASCII portrait that sketches itself in left-to-right.
Pure SMIL — renders inside GitHub's README <img> sandbox.

Regenerate:  sips -z 120 260 avatar.png -s format bmp --out small.bmp
             python3 ascii_profile.py
"""
import struct
from html import escape

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
# window chrome (traffic-light dots + titlebar), portrait + name on the left,
# a real shell session ($ cmd -> output) on the right, one orange accent.
W, H = 880, 560
TB = 46                                             # titlebar height
ART_X, ART_Y0 = 16, TB + 24
ART_LH = 380 / max(h, 1)                            # portrait height
ART_FS = ART_LH * 0.92
ART_W = 410                                         # ~7% under true aspect: monospace runs read wide,
                                                    # so a slight slim makes the face look correct
RX = 470                                            # right column (shell session) x
NOTE_END = W - 28                                   # right rail for bar annotations

REVEAL_T0 = 0.3    # sketch-draw of the portrait starts
REVEAL_DUR = 2.2   # ...and takes this long to sweep left-to-right
T_NAME = REVEAL_T0 + REVEAL_DUR
BAR_CW = 7.2       # char width at font-size 12

def fade(t):
    return f'<animate attributeName="opacity" begin="{t:.2f}s" dur="0.4s" from="0" to="1" fill="freeze"/>'

def cmd(command, y, t):
    """a typed shell command: orange $ prompt, bright command text"""
    return (f'<text x="{RX}" y="{y}" font-size="12.5" opacity="0">'
            f'<tspan fill="#f97316">$</tspan><tspan fill="#e6edf3"> {escape(command)}</tspan>{fade(t)}</text>')

def out_dotted(items, y, t):
    """command output: values separated by dim middots"""
    spans = '<tspan fill="#484f58"> · </tspan>'.join(
        f'<tspan fill="#8b949e">{escape(it)}</tspan>' for it in items
    )
    return f'<text x="{RX}" y="{y}" font-size="12.5" opacity="0">{spans}{fade(t)}</text>'

# ---- window chrome: traffic lights + titlebar ----
TITLEBAR = (
    f'<path d="M0 15 A15 15 0 0 1 15 0 H{W - 15} A15 15 0 0 1 {W} 15 V{TB} H0 Z" fill="#0d1117"/>'
    f'<line x1="0" y1="{TB}" x2="{W}" y2="{TB}" stroke="#21262d" stroke-width="1"/>'
    f'<circle cx="26" cy="23" r="6" fill="#ff5f56"/>'
    f'<circle cx="46" cy="23" r="6" fill="#febc2e"/>'
    f'<circle cx="66" cy="23" r="6" fill="#28c840"/>'
    f'<text x="{W/2:.0f}" y="27" text-anchor="middle" font-size="12" fill="#6e7681">hemraj@sodisetti — -zsh — 92×30</text>'
)

# ---- left: name block under the portrait ----
SUBTITLE = '<tspan fill="#f97316"> · </tspan>'.join(
    f'<tspan fill="#8b949e">{s}</tspan>' for s in ("systems engineer", "builder")
)
NAME_SVG = (
    f'<g opacity="0">{fade(T_NAME)}'
    f'<text x="18" y="500" font-size="17" fill="#f97316">&gt;</text>'
    f'<text x="42" y="500" font-size="17" letter-spacing="5" fill="#f0f3f6">HEMRAJ SODISETTI</text>'
    f'<text x="42" y="524" font-size="12" letter-spacing="1">{SUBTITLE}</text>'
    f'</g>'
)

# ---- right: a live shell session ----
BARS = [
    ("building", 9, "systems that don't fall over"),
    ("learning", 7, "whatever the problem demands"),
    ("sleeping", 2, "overrated anyway"),
]
session = [
    f'<rect x="446" y="{TB + 18}" width="1" height="{H - TB - 56}" fill="#21262d"/>',   # pane divider
    cmd("./status --now", 104, T_NAME + 0.2),
]
for i, (label, fill, note) in enumerate(BARS):
    y = 134 + i * 25
    t0 = T_NAME + 0.4 + i * 0.22
    fill_w = fill * BAR_CW
    session.append(
        f'<g opacity="0">'
        f'<animate attributeName="opacity" begin="{t0:.2f}s" dur="0.35s" from="0" to="1" fill="freeze"/>'
        f'<text x="{RX + 12}" y="{y}" font-size="12" fill="#8b949e" textLength="{len(label) * BAR_CW:.0f}" lengthAdjust="spacingAndGlyphs">{label}</text>'
        f'<text x="{RX + 100}" y="{y}" font-size="12" fill="#2d333b" textLength="{10 * BAR_CW:.0f}" lengthAdjust="spacingAndGlyphs">{"░" * 10}</text>'
        f'<clipPath id="barfill{i}"><rect x="{RX + 100}" y="{y - 12}" width="0" height="16">'
        f'<animate attributeName="width" from="0" to="{fill_w + 1:.0f}" begin="{t0 + 0.15:.2f}s" dur="0.7s" '
        f'calcMode="spline" keySplines="0.2 0.7 0.3 1" fill="freeze"/></rect></clipPath>'
        f'<text x="{RX + 100}" y="{y}" font-size="12" fill="#f97316" clip-path="url(#barfill{i})" '
        f'textLength="{fill_w:.0f}" lengthAdjust="spacingAndGlyphs">{"▓" * fill}</text>'
        f'<text x="{NOTE_END}" y="{y}" font-size="12" fill="#6e7681" text-anchor="end" '
        f'textLength="{len(note) * BAR_CW:.0f}" lengthAdjust="spacingAndGlyphs">{escape(note)}</text>'
        f'</g>'
    )
session += [
    cmd("cat ~/stack", 262, T_NAME + 1.15),
    out_dotted(["rust", "go", "python", "c++", "cuda"], 290, T_NAME + 1.3),
    out_dotted(["aws", "gcp", "k8s", "docker", "pytorch"], 314, T_NAME + 1.45),
    cmd("tail -1 ~/.plan", 386, T_NAME + 1.65),
    f'<text x="{RX}" y="414" font-size="12.5" fill="#8b949e" opacity="0">tools change. shipping doesn\'t.{fade(T_NAME + 1.8)}</text>',
    # live prompt with a blinking cursor
    f'<g opacity="0">{fade(T_NAME + 2.0)}'
    f'<text x="{RX}" y="474" font-size="12.5"><tspan fill="#f97316">$</tspan><tspan fill="#e6edf3"> </tspan>'
    f'<tspan fill="#e6edf3">▊<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></tspan></text>'
    f'</g>',
]
BARS_SVG = TITLEBAR + NAME_SVG + "".join(session)

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
<rect width="{W}" height="{H}" fill="#010409" rx="15"/>
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
