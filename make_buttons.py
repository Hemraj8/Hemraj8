#!/usr/bin/env python3
"""Generate the contact buttons as standalone bordered-button SVGs.
Each is wrapped in a link in README.md, so they match the mockup exactly
AND stay clickable. Email is the orange "active" button; the rest are gray.
"""
import json

ICONS = json.load(open("btn_icons.json"))
H = 40

def button(name, label, icon_svg, color, text_color, fname):
    w = 44 + int(len(label) * 8.4) + 20
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{H}" viewBox="0 0 {w} {H}" font-family="Consolas, 'Fira Code', Menlo, monospace">
<rect x="1" y="1" width="{w - 2}" height="{H - 2}" rx="7" fill="#0a0d12" stroke="{color}" stroke-width="1.2"/>
<g transform="translate(15,{H/2 - 8}) scale(0.667)">{icon_svg}</g>
<text x="42" y="{H/2 + 4:.0f}" font-size="12" letter-spacing="1.5" fill="{text_color}" font-weight="bold">{label}</text>
</svg>'''
    open(fname, "w").write(svg)
    print(f"{fname}  ({w}x{H})")

# envelope drawn with primitives (outline), tinted to the button color
def envelope(color):
    return (f'<rect x="1.5" y="4" width="21" height="16" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
            f'<path d="M2 6 L12 13 L22 6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')

ORANGE = "#f97316"
GRAY = "#8b949e"
ICON_GRAY = "#c9d1d9"

button("email", "EMAIL", envelope(ORANGE), ORANGE, ORANGE, "btn_email.svg")
button("linkedin", "LINKEDIN", f'<path d="{ICONS["linkedin"]}" fill="{ICON_GRAY}"/>', "#30363d", GRAY, "btn_linkedin.svg")
button("github", "GITHUB", f'<path d="{ICONS["github"]}" fill="{ICON_GRAY}"/>', "#30363d", GRAY, "btn_github.svg")
