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
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'spine.svg.part')
PAD = 2            # blank cells kept around the drawing
ASPECT = 1.6       # cell height / cell width, i.e. a monospace character box
# one solid colour per shade level, lightest to darkest. #FDF48E / #F38530 / #822D00
# are the palette; #F8BC5F is their cream-orange midpoint, filling the fourth step.
# Every cell draws the same character; the four source levels are told apart by
# colour alone. Cells are white and the colour is on the character.
# tints of the accent #F28532, mixed with white at 75 / 55 / 30 / 0 percent.
# Only the shade levels the drawing actually uses are spread across this ramp,
# so a three-level drawing still reaches the accent at its darkest.
# the shade levels a drawing uses are spread evenly along this ramp,
# lightest character to darkest
RAMP_FROM = '#D6D782'   # lightest
RAMP_TO = '#F28532'     # darkest
DENSITY = '░▒▓█'


def lerp(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02X%02X%02X' % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))
GLYPH = '▓'
FALLBACK = RAMP_TO
CELL = '#ffffff'
HOLE = '#86C689'   # blank cells enclosed by the drawing get a ▓ in this green

lines = open(SRC).read().split('\n')
cells = {(x, y): ch for y, line in enumerate(lines)
         for x, ch in enumerate(line) if not ch.isspace()}
if not cells:
    sys.exit('no content')

# Each row's centre drifts off the overall axis, so the spine leans and the left
# and right margins read as uneven. Nudge whole rows back onto the axis, using a
# moving average so the correction eases in over many rows instead of stepping.
STRAIGHTEN = True
SMOOTH = 15          # rows averaged either side when working out a row's drift
MAX_SHIFT = 4        # cells a row may be moved


def straighten(cells):
    weight = {ch: i + 1 for i, ch in enumerate(DENSITY)}
    rows = collections.defaultdict(list)
    for (x, y), ch in cells.items():
        rows[y].append((x, weight.get(ch, 2)))
    ys = sorted(rows)
    centre = {y: sum(x * w for x, w in rows[y]) / sum(w for _, w in rows[y]) for y in ys}
    axis = sum(centre.values()) / len(centre)
    half = SMOOTH // 2
    shift = {}
    for i, y in enumerate(ys):
        near = [centre[ys[j]] for j in range(max(0, i - half), min(len(ys), i + half + 1))]
        drift = sum(near) / len(near) - axis
        shift[y] = max(-MAX_SHIFT, min(MAX_SHIFT, round(-drift)))
    moved = {(x + shift[y], y): ch for (x, y), ch in cells.items()}
    worst = max(abs(v) for v in shift.values())
    print(f'  straightened: {sum(1 for v in shift.values() if v)} of {len(ys)} rows moved, '
          f'up to {worst} cells')
    return moved


if STRAIGHTEN:
    cells = straighten(cells)

xs = [x for x, _ in cells]; ys = [y for _, y in cells]
x0, y0 = min(xs), min(ys)
W = max(xs) - x0 + 1
ROWS = max(ys) - y0 + 1 + 2 * PAD

# Centre on the silhouette, not on the centre of mass. The widest part of the
# drawing sets how the left and right margins read, and straighten() has already
# put the rows on a common axis, so equal padding is what looks balanced.
PAD_L = PAD
COLS = W + 2 * PAD

# blanks the outside can reach are background; the rest are holes inside the spine
def interior_blanks():
    """Flood the blank space from outside the drawing; whatever it cannot reach is a hole."""
    H = max(ys) - y0 + 1
    lo_c, hi_c, lo_r, hi_r = -1, W, -1, H          # one ring of margin around the bbox
    seen, stack = set(), [(c, lo_r) for c in range(lo_c, hi_c + 1)]
    stack += [(c, hi_r) for c in range(lo_c, hi_c + 1)]
    stack += [(lo_c, r) for r in range(lo_r, hi_r + 1)]
    stack += [(hi_c, r) for r in range(lo_r, hi_r + 1)]
    while stack:
        c, r = stack.pop()
        if (c, r) in seen or not (lo_c <= c <= hi_c and lo_r <= r <= hi_r): continue
        if (c + x0, r + y0) in cells: continue
        seen.add((c, r))
        stack += [(c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)]
    return {(c, r) for c in range(W) for r in range(H)
            if (c + x0, r + y0) not in cells and (c, r) not in seen}


HOLES = interior_blanks()

levels = sorted({ch for ch in cells.values() if ch in DENSITY}, key=DENSITY.index)
TONE = {ch: lerp(RAMP_FROM, RAMP_TO, i / max(1, len(levels) - 1))
        for i, ch in enumerate(levels)}
for ch in set(cells.values()) - set(TONE):
    TONE[ch] = FALLBACK

# every cell, drawn or enclosed blank, is white with a ▓ in its own colour
PAINT = {(x, y): TONE[ch] for (x, y), ch in cells.items()}
PAINT.update({(c + x0, r + y0): HOLE for c, r in HOLES})

rects, glyphs = [], []


for (x, y), tone in sorted(PAINT.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    cx = x - x0 + PAD_L
    cy = (y - y0 + PAD) * ASPECT
    r = y - y0 + PAD
    glyph = GLYPH
    rects.append(f'<rect x="{cx}" y="{cy:g}" width="1" height="{ASPECT:g}" '
                 f'data-c="{cx}" data-r="{r}" fill="{CELL}"/>')
    glyphs.append(f'<text x="{cx + 0.5:g}" y="{cy + ASPECT / 2:g}" data-c="{cx}" data-r="{r}" '
                  f'textLength="1" lengthAdjust="spacingAndGlyphs" fill="{tone}">{glyph}</text>')

out = (f'<svg class="spine" viewBox="0 0 {COLS:.3f} {ROWS * ASPECT:g}" '
       f'xmlns="http://www.w3.org/2000/svg" aria-label="spine">\n'
       f'<g class="cells">{"".join(rects)}</g>\n<g class="glyphs">{"".join(glyphs)}</g>\n</svg>')
open(OUT, 'w').write(out)

tally = collections.Counter(cells.values())
print(f'grid {COLS:.2f} x {ROWS} cells (pad L{PAD_L}, aspect {ASPECT}), '
      f'{len(cells)} drawn + {len(HOLES)} enclosed blanks, all as {GLYPH}')
for ch, n in sorted(tally.items(), key=lambda kv: DENSITY.index(kv[0]) if kv[0] in DENSITY else 9):
    print(f'  {ch} -> {GLYPH}  {n:5d}  ink {TONE[ch]}')
print(f'  hole -> {GLYPH}  {len(HOLES):5d}  ink {HOLE}')
