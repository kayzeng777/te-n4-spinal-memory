#!/usr/bin/env python3
"""Turn an ASCII-shade drawing into spine.svg.part.

One cell per non-space character: a
white cell with the character drawn on it in the colour for its shade level.
Blank cells enclosed by the drawing take part too, in green.
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
HOLE = '#86C689'   # blank cells enclosed by the drawing get a ▓ in this green

lines = open(SRC).read().split('\n')
cells = {(x, y): ch for y, line in enumerate(lines)
         for x, ch in enumerate(line) if not ch.isspace()}
if not cells:
    sys.exit('no content')

xs = [x for x, _ in cells]; ys = [y for _, y in cells]
x0, y0 = min(xs), min(ys)
COLS = max(xs) - x0 + 1 + 2 * PAD
ROWS = max(ys) - y0 + 1 + 2 * PAD

# blanks the outside can reach are background; the rest are holes inside the spine
def interior_blanks():
    seen, stack = set(), []
    lo_c, hi_c, lo_r, hi_r = -PAD, COLS - PAD, -PAD, ROWS - PAD
    for c in range(lo_c, hi_c + 1):
        stack += [(c, lo_r), (c, hi_r)]
    for r in range(lo_r, hi_r + 1):
        stack += [(lo_c, r), (hi_c, r)]
    while stack:
        c, r = stack.pop()
        if (c, r) in seen or not (lo_c <= c <= hi_c and lo_r <= r <= hi_r): continue
        if (c + x0, r + y0) in cells: continue
        seen.add((c, r))
        stack += [(c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)]
    return {(c, r) for c in range(0, COLS - 2 * PAD) for r in range(0, ROWS - 2 * PAD)
            if (c + x0, r + y0) not in cells and (c, r) not in seen}


HOLES = interior_blanks()

# every cell, drawn or enclosed blank, is white with a ▓ in its own colour
PAINT = {(x, y): TONE.get(ch, FALLBACK) for (x, y), ch in cells.items()}
PAINT.update({(c + x0, r + y0): HOLE for c, r in HOLES})

rects, glyphs = [], []


for (x, y), tone in sorted(PAINT.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    cx = x - x0 + PAD
    cy = (y - y0 + PAD) * ASPECT
    r = y - y0 + PAD
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
print(f'grid {COLS} x {ROWS} cells (pad {PAD}, aspect {ASPECT}), '
      f'{len(cells)} drawn + {len(HOLES)} enclosed blanks, all as {GLYPH}')
for ch, n in sorted(tally.items(), key=lambda kv: list(TONE).index(kv[0])):
    print(f'  {ch} -> {GLYPH}  {n:5d}  ink {TONE[ch]}')
print(f'  hole -> {GLYPH}  {len(HOLES):5d}  ink {HOLE}')
