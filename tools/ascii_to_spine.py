#!/usr/bin/env python3
"""Turn an ASCII-shade drawing into spine.svg.part.

One cell per non-space character, filled with a solid colour for that character's
shade level, so the tonal range survives at small cell sizes. The character itself
is kept in the markup (invisible) so the hieroglyph cycling has somewhere to land.
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
TONE = {'░': '#FDF48E', '▒': '#F8BC5F', '▓': '#F38530', '█': '#822D00'}
FALLBACK = '#F38530'

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
    rects.append(f'<rect x="{cx}" y="{cy:g}" width="1" height="{ASPECT:g}" '
                 f'data-c="{cx}" data-r="{r}" fill="{tone}"/>')
    glyphs.append(f'<text x="{cx + 0.5:g}" y="{cy + ASPECT / 2:g}" data-c="{cx}" data-r="{r}" '
                  f'fill="{tone}">{ch}</text>')

out = (f'<svg class="spine" viewBox="0 0 {COLS} {ROWS * ASPECT:g}" '
       f'xmlns="http://www.w3.org/2000/svg" aria-label="spine">\n'
       f'<g class="cells">{"".join(rects)}</g>\n<g class="glyphs">{"".join(glyphs)}</g>\n</svg>')
open(os.path.join(HERE, 'spine.svg.part'), 'w').write(out)

tally = collections.Counter(cells.values())
print(f'grid {COLS} x {ROWS} cells (pad {PAD}, aspect {ASPECT}), {len(cells)} filled')
for ch, n in sorted(tally.items(), key=lambda kv: list(TONE).index(kv[0])):
    print(f'  {ch}  {n:5d}  {TONE[ch]}')
