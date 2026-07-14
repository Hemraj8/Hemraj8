#!/usr/bin/env python3
"""Generate an animated GitHub profile SVG:
fireworks (crackers) play first, then the photo + info panel appear.
Everything is self-contained (SMIL animations + base64 photo) so it
renders inside GitHub's README <img> sandbox.
"""
import base64
import math
import random

random.seed(41)

W, H = 900, 440
CYCLE = 7.0          # seconds per firework loop
PHOTO_AT = 2.3       # photo appears after the first big bursts
PHOTO_CX, PHOTO_CY, PHOTO_R = 200, 220, 115

with open("avatar.png", "rb") as f:
    AVATAR_B64 = base64.b64encode(f.read()).decode()

PALETTES = [
    ["#ffd166", "#ff9f1c", "#fff3b0"],          # gold
    ["#ef476f", "#ff70a6", "#ffd6e0"],          # pink/red
    ["#06d6a0", "#80ffdb", "#c7f9cc"],          # green
    ["#4cc9f0", "#90e0ef", "#caf0f8"],          # cyan
    ["#c77dff", "#e0aaff", "#f3d9fa"],          # violet
]


def rocket(x, burst_y, t_launch, t_burst, color):
    """A streak rising from the bottom to the burst point."""
    k0 = t_launch / CYCLE
    k1 = t_burst / CYCLE
    return f'''
  <circle cx="{x}" cy="{H}" r="2.2" fill="{color}" opacity="0">
    <animate attributeName="cy" values="{H};{H};{burst_y};{burst_y}" keyTimes="0;{k0:.3f};{k1:.3f};1" dur="{CYCLE}s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;0;1;0.9;0;0" keyTimes="0;{k0:.3f};{(k0+k1)/2:.3f};{k1-0.005:.3f};{k1:.3f};1" dur="{CYCLE}s" repeatCount="indefinite"/>
  </circle>'''


def burst(cx, cy, t_burst, palette, n=14, radius=62, dur=1.5):
    """Radial particle burst at (cx, cy) starting t_burst into each cycle."""
    k0 = t_burst / CYCLE
    k1 = min((t_burst + dur) / CYCLE, 0.999)
    parts = []
    for i in range(n):
        a = 2 * math.pi * i / n + random.uniform(-0.1, 0.1)
        r = radius * random.uniform(0.75, 1.15)
        ex, ey = cx + r * math.cos(a), cy + r * math.sin(a) + 8  # slight gravity droop
        c = random.choice(palette)
        pr = random.uniform(1.6, 2.8)
        parts.append(f'''
  <circle cx="{cx}" cy="{cy}" r="{pr:.1f}" fill="{c}" opacity="0">
    <animate attributeName="cx" values="{cx};{cx};{ex:.0f};{ex:.0f}" keyTimes="0;{k0:.3f};{k1:.3f};1" dur="{CYCLE}s" repeatCount="indefinite" calcMode="spline" keySplines="0 0 1 1;0.1 0.8 0.3 1;0 0 1 1"/>
    <animate attributeName="cy" values="{cy};{cy};{ey:.0f};{ey:.0f}" keyTimes="0;{k0:.3f};{k1:.3f};1" dur="{CYCLE}s" repeatCount="indefinite" calcMode="spline" keySplines="0 0 1 1;0.1 0.8 0.3 1;0 0 1 1"/>
    <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;{k0:.3f};{(k0 + (k1-k0)*0.25):.3f};{k1:.3f};1" dur="{CYCLE}s" repeatCount="indefinite"/>
  </circle>''')
    # bright flash at burst center
    parts.append(f'''
  <circle cx="{cx}" cy="{cy}" r="5" fill="#ffffff" opacity="0">
    <animate attributeName="opacity" values="0;0;0.95;0;0" keyTimes="0;{k0:.3f};{k0+0.015:.3f};{k0+0.06:.3f};1" dur="{CYCLE}s" repeatCount="indefinite"/>
    <animate attributeName="r" values="2;2;16;20;2" keyTimes="0;{k0:.3f};{k0+0.03:.3f};{k0+0.06:.3f};1" dur="{CYCLE}s" repeatCount="indefinite"/>
  </circle>''')
    return "".join(parts)


def stars(n=40):
    out = []
    for _ in range(n):
        x, y = random.uniform(0, W), random.uniform(0, H * 0.75)
        d = random.uniform(1.8, 4.5)
        b = random.uniform(0, 3)
        out.append(f'''
  <circle cx="{x:.0f}" cy="{y:.0f}" r="{random.uniform(0.5, 1.3):.1f}" fill="#8b96a8">
    <animate attributeName="opacity" values="0.15;0.9;0.15" dur="{d:.1f}s" begin="{b:.1f}s" repeatCount="indefinite"/>
  </circle>''')
    return "".join(out)


# fireworks show: (x, burst_y, launch_t, burst_t, palette)
SHOTS = [
    (620, 110, 0.10, 0.65, PALETTES[0]),
    (760, 160, 0.45, 1.05, PALETTES[1]),
    (500, 190, 0.80, 1.45, PALETTES[3]),
    (690, 80,  1.20, 1.85, PALETTES[2]),
    (200, 100, 1.55, 2.15, PALETTES[4]),   # burst right above where the photo appears
    (830, 90,  3.20, 3.85, PALETTES[0]),
    (560, 130, 4.30, 4.95, PALETTES[4]),
    (740, 200, 5.30, 5.95, PALETTES[2]),
]

fireworks = "".join(rocket(x, y, tl, tb, p[0]) + burst(x, y, tb, p) for x, y, tl, tb, p in SHOTS)

# info panel lines: (key, value), revealed one by one after the photo
LINES = [
    ("Name", "HemRaj Sodisetti"),
    ("Handle", "@Hemraj8"),
    ("Focus", "Edge-to-Cloud, Infra, ML"),
    ("Languages", "Python, C++, Rust, Go, CUDA"),
    ("Email", "hemrajsodisetti@gmail.com"),
    ("LinkedIn", "in/hemraj-sodisetti"),
]
text_rows = []
ty = 200
for i, (k, v) in enumerate(LINES):
    t = PHOTO_AT + 1.0 + i * 0.25
    text_rows.append(f'''
  <text x="420" y="{ty}" opacity="0" font-size="17">
    <tspan class="key">{k}</tspan><tspan class="dot">{" ." * max(1, (16 - len(k)))} </tspan><tspan class="val">{v}</tspan>
    <animate attributeName="opacity" begin="{t:.2f}s" dur="0.5s" from="0" to="1" fill="freeze"/>
  </text>''')
    ty += 34

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Consolas, 'Fira Code', Menlo, monospace">
<style>
  .key {{ fill: #ffd166; font-weight: bold; }}
  .dot {{ fill: #3d4654; }}
  .val {{ fill: #c9d5e3; }}
  .title {{ fill: #ffffff; font-weight: bold; }}
</style>
<defs>
  <clipPath id="photoClip"><circle cx="{PHOTO_CX}" cy="{PHOTO_CY}" r="{PHOTO_R}"/></clipPath>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0b1020"/>
    <stop offset="1" stop-color="#141c30"/>
  </linearGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ffd166"/>
    <stop offset="0.5" stop-color="#ef476f"/>
    <stop offset="1" stop-color="#4cc9f0"/>
  </linearGradient>
</defs>

<rect width="{W}" height="{H}" fill="url(#sky)" rx="16"/>
{stars()}
{fireworks}

<!-- photo: hidden at first, pops in after the opening bursts -->
<g opacity="0" transform-origin="{PHOTO_CX} {PHOTO_CY}">
  <animate attributeName="opacity" begin="{PHOTO_AT}s" dur="0.7s" from="0" to="1" fill="freeze"/>
  <animateTransform attributeName="transform" type="scale" begin="{PHOTO_AT}s" dur="0.7s" values="0.4;1.08;1" keyTimes="0;0.7;1" calcMode="spline" keySplines="0.2 0.8 0.3 1.2;0.4 0 0.6 1" fill="freeze"/>
  <circle cx="{PHOTO_CX}" cy="{PHOTO_CY}" r="{PHOTO_R + 6}" fill="none" stroke="url(#ring)" stroke-width="4">
    <animateTransform attributeName="transform" type="rotate" from="0 {PHOTO_CX} {PHOTO_CY}" to="360 {PHOTO_CX} {PHOTO_CY}" dur="14s" repeatCount="indefinite"/>
  </circle>
  <image href="data:image/jpeg;base64,{AVATAR_B64}" x="{PHOTO_CX - PHOTO_R}" y="{PHOTO_CY - PHOTO_R}" width="{PHOTO_R * 2}" height="{PHOTO_R * 2}" clip-path="url(#photoClip)"/>
</g>

<!-- header + info panel -->
<text x="420" y="120" class="title" font-size="26" opacity="0">HemRaj Sodisetti
  <animate attributeName="opacity" begin="{PHOTO_AT + 0.5}s" dur="0.6s" from="0" to="1" fill="freeze"/>
</text>
<text x="420" y="150" class="dot" font-size="15" opacity="0">———————————————————————————————
  <animate attributeName="opacity" begin="{PHOTO_AT + 0.7}s" dur="0.6s" from="0" to="1" fill="freeze"/>
</text>
{"".join(text_rows)}
</svg>
'''

with open("profile.svg", "w") as f:
    f.write(svg)
print(f"profile.svg written, {len(svg)/1024:.0f} KB")
