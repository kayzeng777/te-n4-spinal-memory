#!/usr/bin/env python3
"""Split the flat spine SVG (spine.svg.part) into 9 hoverable segments -> spine.seg.part.

Cuts land on the narrowest rows near evenly spaced targets, so segments break
between vertebrae rather than through them.
"""
import collections, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'spine.svg.part')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'spine.seg.part')
src = open(SRC).read()

N_SEGS = 9
IMAGES = ['images/web/01-05-7.jpg', 'images/web/02-09-5.jpg', 'images/web/03-fig-5.jpg',
          'images/web/04-fig1.jpg', 'images/web/05-fig3.jpg', 'images/web/06-fig7.jpg',
          'images/web/07-front-portrait.jpg', 'images/web/08-zir8.jpg', 'images/web/09-3.jpg']
PLACEHOLDER_FILL = ['#822D00', '#F38530', '#FDF48E', '#D4F724', '#822D00',
                    '#F38530', '#FDF48E', '#D4F724', '#822D00']

head = re.match(r'<svg[^>]*>', src).group(0)
defs = ''
cells_src = re.search(r'<g class="cells">(.*?)</g>', src, re.S).group(1)
RECT = r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)"[^>]*/>'
# group by the grid row (data-r), not the drawn y, which cells may overshoot
rects = [(m.group(0), int(re.search(r'data-r="(\d+)"', m.group(0)).group(1)))
         for m in re.finditer(RECT, cells_src)]
glyph_els = [(m.group(0), int(re.search(r'data-r="(\d+)"', m.group(0)).group(1)))
             for m in re.finditer(r'<text [^>]*>.*?</text>', src)]

width = collections.Counter(y for _, y in rects)
rows = sorted(width)
y0, y1 = rows[0], rows[-1]


def find_cuts():
    """Narrowest row within a window around each evenly spaced target."""
    span = (y1 - y0 + 1) / N_SEGS
    cuts, prev = [], y0
    for i in range(1, N_SEGS):
        target = y0 + span * i
        lo, hi = int(target - span * 0.3), int(target + span * 0.3)
        window = [y for y in rows if lo <= y <= hi and y > prev]
        cut = min(window, key=lambda y: (width[y], abs(y - target))) if window else int(target)
        cuts.append(cut); prev = cut
    return cuts


CUTS = find_cuts()
seg_of = lambda y: sum(1 for c in CUTS if y >= c)

segs = [{'rects': [], 'glyphs': []} for _ in range(N_SEGS)]
for el, y in rects:
    segs[seg_of(y)]['rects'].append((el, y))
for el, y in glyph_els:
    segs[seg_of(y)]['glyphs'].append(el)

CLIP_EPS = 0.03   # overlap between clip rects, to close anti-aliasing seams


def clip_path(els):
    """Merge each row of cells into runs so the clip has as few seams as possible."""
    rows = collections.defaultdict(list)
    for el, _ in els:
        x, y, w, h = map(float, re.search(RECT, el).groups())
        rows[(y, h)].append((x, w))
    out = []
    for (y, h), spans in sorted(rows.items()):
        spans.sort()
        cx, cw = spans[0]
        for x, w in spans[1:]:
            if abs(x - (cx + cw)) < 1e-6:
                cw += w
            else:
                out.append((cx, y, cw, h)); cx, cw = x, w
        out.append((cx, y, cw, h))
    return ''.join(
        f'<rect x="{x-CLIP_EPS:g}" y="{y-CLIP_EPS:g}" '
        f'width="{w+2*CLIP_EPS:g}" height="{h+2*CLIP_EPS:g}"/>' for x, y, w, h in out)


def bbox(els):
    xs, ys = [], []
    for el, _ in els:
        m = re.search(RECT, el)
        x, y, w, h = map(float, m.groups())
        xs += [x, x + w]; ys += [y, y + h]
    return min(xs), min(ys), max(xs), max(ys)

out = [head]
for i, s in enumerate(segs):
    sx0, sy0, sx1, sy1 = bbox(s['rects'])
    rect_str = ''.join(el for el, _ in s['rects'])
    out.append(
        f'<g class="seg" data-seg="{i}">'
        f'<clipPath id="segclip-{i}">{clip_path(s["rects"])}</clipPath>'
        f'<g class="cells">{rect_str}</g>'
        f'<g class="glyphs">{"".join(s["glyphs"])}</g>'
        f'<g class="pic" clip-path="url(#segclip-{i})">'
        f'<rect x="{sx0:g}" y="{sy0:g}" width="{sx1-sx0:g}" height="{sy1-sy0:g}" fill="{PLACEHOLDER_FILL[i]}"/>'
        f'<image href="{IMAGES[i]}" x="{sx0:g}" y="{sy0:g}" width="{sx1-sx0:g}" height="{sy1-sy0:g}" '
        f'preserveAspectRatio="xMidYMid slice"/>'
        f'</g></g>')
    print(f'seg {i}: y {sy0:g}-{sy1:g}, {len(s["rects"])} cells, {len(s["glyphs"])} glyphs')
out.append('</svg>')
open(OUT, 'w').write('\n'.join(out))
print('cuts at rows', CUTS)
