#!/usr/bin/env python3
"""Split the flat spine SVG (spine.svg.part) into 8 hoverable segments -> spine.seg.part.

Cuts land on the narrowest rows near evenly spaced targets, so segments break
between vertebrae rather than through them.
"""
import collections, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'spine.svg.part')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'spine.seg.part')
src = open(SRC).read()

N_SEGS = 8
IMAGES = [f'images/web/0{i}.jpg' for i in range(1, N_SEGS + 1)]
PLACEHOLDER_FILL = ['#822D00', '#F38530', '#FDF48E', '#D4F724',
                    '#822D00', '#F38530', '#FDF48E', '#D4F724']

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

# per-row extent of the drawing, for the box a segment's photo has to fill
xlo, xhi, ylo, yhi = {}, {}, {}, {}
for el, r in rects:
    x, y, w, h = map(float, re.search(RECT, el).groups())
    xlo[r] = min(xlo.get(r, x), x);      xhi[r] = max(xhi.get(r, x + w), x + w)
    ylo[r] = min(ylo.get(r, y), y);      yhi[r] = max(yhi.get(r, y + h), y + h)


# what a narrow cut row is worth, as a fraction of one segment's box. The cut
# scores the imbalance it causes plus this times how wide the row is, so a cut
# buys its way onto a narrow row only when the row is narrow enough to pay.
CUT_WIDTH_COST = 0.0
# relative size of each segment, top to bottom. Equal boxes still do not read as
# equal -- a dark or empty photo shrinks, a busy one swells -- so this is the
# knob for the eye, applied on top of the split. 1 is the mean; raise a number
# to give that segment more of the spine.
SEG_SIZE = [1.04, 0.96, 0.96, 1, 1.06, 1.06, 1, 1.16]


def box_areas():
    """box[a][b] = area of the box the rows rows[a:b] have to fill."""
    R = len(rows)
    box = [[0.0] * (R + 1) for _ in range(R + 1)]
    for a in range(R):
        x0 = y0_ = float('inf'); x1 = y1_ = float('-inf')
        for b in range(a, R):
            r = rows[b]
            x0 = min(x0, xlo[r]); x1 = max(x1, xhi[r])
            y0_ = min(y0_, ylo[r]); y1_ = max(y1_, yhi[r])
            box[a][b + 1] = (x1 - x0) * (y1_ - y0_)
    return box


def split(box, target):
    """Cheapest set of cuts, by dynamic programming over the cut rows.

    Segments are scored on how far their box falls from the target, so the cost
    of a segment depends on its own two cuts and nothing else, which is what
    lets the search be a walk over prefixes.
    """
    want = [target * w * N_SEGS / sum(SEG_SIZE) for w in SEG_SIZE]
    R, INF = len(rows), float('inf')
    widest = max(width.values())
    dp = [[INF] * (N_SEGS + 1) for _ in range(R + 1)]
    back = [[None] * (N_SEGS + 1) for _ in range(R + 1)]
    dp[0][0] = 0.0
    for k in range(1, N_SEGS + 1):
        for b in range(k, R + 1 - (N_SEGS - k)):
            cut = CUT_WIDTH_COST * width[rows[b]] / widest if k < N_SEGS else 0.0
            for a in range(k - 1, b):
                if dp[a][k - 1] == INF: continue
                c = dp[a][k - 1] + ((box[a][b] - want[k - 1]) / want[k - 1]) ** 2 + cut
                if c < dp[b][k]: dp[b][k], back[b][k] = c, a
    edges, b = [R], R
    for k in range(N_SEGS, 0, -1):
        b = back[b][k]; edges.append(b)
    edges.reverse()
    return edges


def find_cuts():
    """Split the rows so every segment's photo box comes out the same size.

    Equal cell counts still read as unequal: where the spine is widest it is
    also shortest, so an equal share of the cells there is a 2.7:1 strip that
    letterboxes its photo, while a share up at the shoulders is nearly square.
    What the eye measures is the box, so that is what gets split -- and box
    area does not add up down the rows the way a cell count does, so the split
    is searched for rather than walked to. target is a fixed point: the mean
    box of a split depends on the split, so solve, re-average, repeat.
    """
    box = box_areas()
    target, best = box[0][len(rows)] / N_SEGS, None
    for _ in range(30):
        edges = split(box, target)
        areas = [box[a][b] for a, b in zip(edges, edges[1:])]
        spread = max(areas) / min(areas)
        if best is None or spread < best[0]: best = (spread, edges)
        nxt = sum(areas) / N_SEGS
        if abs(nxt - target) < 1e-6: break
        target = nxt
    return [rows[i] for i in best[1][1:-1]]


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
        f'<g class="seg" data-seg="{i}" data-y0="{sy0:g}" data-y1="{sy1:g}">'
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
