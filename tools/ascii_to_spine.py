#!/usr/bin/env python3
"""Turn an ASCII-shade drawing into spine.svg.part (flat cells + overflowing glyphs)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'ascii-art.txt')
PAD = 2
GLYPH = '▓▓▓▓'
FONT_SIZE = '0.8'
# shade character -> cell colour, lightest to darkest
COLOR = {'░': '#FDF48E', '▒': '#F38530', '▓': '#822D00'}

lines = open(SRC).read().split('\n')
cells = {(x, y): ch for y, line in enumerate(lines)
         for x, ch in enumerate(line) if not ch.isspace()}
if not cells:
    sys.exit('no content')

xs = [x for x, _ in cells]; ys = [y for _, y in cells]
x0, y0 = min(xs), min(ys)
W = max(xs) - x0 + 1 + 2 * PAD
H = max(ys) - y0 + 1 + 2 * PAD

rects, glyphs = [], []
for (x, y), ch in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    cx, cy = x - x0 + PAD, y - y0 + PAD
    rects.append(f'<rect x="{cx}" y="{cy}" width="1" height="1"/>')
    clip = ('c' if (x - 1, y) in cells else 'o') + ('c' if (x + 1, y) in cells else 'o')
    fill = COLOR.get(ch, '#F38530')
    glyphs.append(f'<g clip-path="url(#k{clip})" transform="translate({cx},{cy})">'
                  f'<text x=".5" y=".5" font-size="{FONT_SIZE}" fill="{fill}">{GLYPH}</text></g>')

defs = '<defs>' + ''.join(
    f'<clipPath id="k{a}{b}"><rect x="{0 if a == "c" else -1}" y="0" '
    f'width="{(1 if a == "c" else 2) + (0 if b == "c" else 1)}" height="1"/></clipPath>'
    for a in 'co' for b in 'co') + '</defs>'

out = (f'<svg class="spine" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" aria-label="spine">\n'
       f'{defs}\n<g class="cells">{"".join(rects)}</g>\n<g class="glyphs">{"".join(glyphs)}</g>\n</svg>')
open(os.path.join(HERE, 'spine.svg.part'), 'w').write(out)

import collections
tally = collections.Counter(cells.values())
print(f'grid {W} x {H} (pad {PAD}), {len(cells)} cells')
for ch, n in tally.most_common():
    print(f'  {ch} {n:5d}  {COLOR.get(ch)}')
