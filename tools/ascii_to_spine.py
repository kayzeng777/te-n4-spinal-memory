#!/usr/bin/env python3
"""Turn an ASCII-shade drawing into spine.svg.part.

One cell per non-space character: a
white cell with the character drawn on it in the colour for its shade level.
The character is stretched to the full cell width but is shorter than the cell,
so every row keeps a white band above and below the colour.
Cells are 1 unit wide and ASPECT tall, matching a monospace character box, so the
drawing keeps the proportions it had in a terminal.
"""
import collections, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'ascii-art.txt')
PAD = 2            # blank cells kept around the drawing
ASPECT = 1.6       # cell height / cell width, i.e. a monospace character box
# one solid colour per shade level, lightest to darkest. #FDF48E / #F38530 / #822D00
# are the palette; #F8BC5F is their cream-orange midpoint, filling the fourth step.
# Every cell draws the same character; the four source levels are told apart by
# colour alone. Cells are white and the colour is on the character.
TONE = {'░': '#FDF48E', '▒': '#F8BC5F', '▓': '#F38530', '█': '#822D00'}
GLYPH = '▓'
FALLBACK = '#F38530'
CELL = '#ffffff'

lines = open(SRC).read().split('\n')
cells = {(x, y): ch for y, line in enumerate(lines)
         for x, ch in enumerate(line) if not ch.isspace()}
if not cells:
    sys.exit('no content')

xs = [x for x, _ in cells]; ys = [y for _, y in cells]
x0, y0 = min(xs), min(ys)
COLS = max(xs) - x0 + 1 + 2 * PAD
ROWS = max(ys) - y0 + 1 + 2 * PAD

rects, glyphs = [], []

for (x, y), ch in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    cx = x - x0 + PAD
    cy = (y - y0 + PAD) * ASPECT
    r = y - y0 + PAD
    tone = TONE.get(ch, FALLBACK)
    glyph = GLYPH
    rects.append(f'<rect x="{cx}" y="{cy:g}" width="1" height="{ASPECT:g}" '
                 f'data-c="{cx}" data-r="{r}" fill="{CELL}"/>')
    glyphs.append(f'<text x="{cx + 0.5:g}" y="{cy + ASPECT / 2:g}" data-c="{cx}" data-r="{r}" '
                  f'textLength="1" lengthAdjust="spacingAndGlyphs" fill="{tone}">{glyph}</text>')

out = (f'<svg class="spine" viewBox="0 0 {COLS} {ROWS * ASPECT:g}" '
       f'xmlns="http://www.w3.org/2000/svg" aria-label="spine">\n'
       f'<g class="cells">{"".join(rects)}</g>\n<g class="glyphs">{"".join(glyphs)}</g>\n</svg>')
open(os.path.join(HERE, 'spine.svg.part'), 'w').write(out)

tally = collections.Counter(cells.values())
print(f'grid {COLS} x {ROWS} cells (pad {PAD}, aspect {ASPECT}), {len(cells)} drawn')
for ch, n in sorted(tally.items(), key=lambda kv: list(TONE).index(kv[0])):
    print(f'  {ch} -> {GLYPH}  {n:5d}  ink {TONE[ch]}')
