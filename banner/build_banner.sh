#!/bin/sh
# Rebuilds profile-video-banner.gif: the top half of the profile card with a
# video looping in the left panel.
#
# Why a GIF: GitHub READMEs won't autoplay or loop an .mp4, but they do loop GIFs.
# Why the whole card is baked into every frame: the README shows this one image
# where profile_top.svg used to be, so the right-hand text has to be inside it.
# That also means the stats in it freeze — rerun this after ascii_profile.py
# changes anything.
#
# Usage (from the repo root):  sh banner/build_banner.sh path/to/video.mp4
# Needs: Google Chrome (draws the SVG) and ffmpeg (everything else).
set -e

VIDEO="$1"
OUT="profile-video-banner.gif"
FPS=12   # the intro moves fast; at the old 6 fps the spinning ball stutters
WORK="$(mktemp -d)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 1. Turn profile_top.svg into a 1960x1076 PNG (2x, so text stays sharp on
#    retina screens). It's loaded through an <img> tag, the same way GitHub
#    shows it, so fonts fall back exactly as they do on the profile page.
#    The black page background also paints the card's rounded corners black.
cp profile_top.svg "$WORK/"
printf '<html><body style="margin:0;background:#000"><img src="profile_top.svg" width="980" height="538"></body></html>' > "$WORK/wrap.html"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=980,538 --screenshot="$WORK/card.png" "file://$WORK/wrap.html" 2>/dev/null

# 2. Put the video on the card and write the GIF, in one ffmpeg pass.
#    All numbers are 2x pixels. Left panel: x 28..972, y 96..1016 — it stops
#    8px short of the divider at x=980 so the divider stays visible.
#    - geq: the video's background isn't pure black — it's ~8/255 with a faint
#      dark-red dot grid (up to ~63/255). Cropped into the panel, both show up
#      as a visible box. So any pixel whose brightest channel is <=72 becomes
#      black, 72..112 fades in, and anything brighter (the logo) is untouched.
#      All three channels are scaled by the same factor so colours keep their
#      hue (TEDH red stays TEDH red). It runs before scaling, so the scale step
#      re-smooths the logo's edges afterwards.
#    - scale+crop: video is shrunk to 1152x648, then 104px trimmed off each
#      side (empty background) so it fills the 944px-wide panel.
#    - drawbox: wipes the old ASCII portrait so only the video shows there.
#    - palettegen/paletteuse: a GIF can hold only 256 colours; this picks the
#      best 256 from all frames instead of a generic set.
#      reserve_transparent=0 + -gifflags -transdiff keep every pixel opaque —
#      GitHub showed transparent pixels as white specks on the previous banner.
# keep = 0 at brightness <=72, 1 at >=112, a straight ramp in between
KEEP="clip((max(max(r(X,Y),g(X,Y)),b(X,Y))-72)/40,0,1)"
ffmpeg -v error -y \
  -framerate "$FPS" -loop 1 -i "$WORK/card.png" \
  -i "$VIDEO" \
  -filter_complex "
    [1:v] fps=$FPS, format=gbrp,
          geq=r='r(X,Y)*$KEEP':g='g(X,Y)*$KEEP':b='b(X,Y)*$KEEP',
          scale=1152:648, crop=944:648:104:0 [vid];
    [0:v] drawbox=x=28:y=96:w=944:h=920:color=black:t=fill [card];
    [card][vid] overlay=28:232:shortest=1, split [a][b];
    [a] palettegen=stats_mode=full:reserve_transparent=0 [pal];
    [b][pal] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle
  " \
  -gifflags -transdiff -loop 0 "$OUT"

rm -rf "$WORK"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1 | tr -d ' '))"
