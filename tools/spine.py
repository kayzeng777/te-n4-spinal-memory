#!/usr/bin/env python3
"""Split the flat spine SVG (spine.svg.part) into 9 hoverable segments -> spine.seg.part.

Cuts land on the narrowest rows near evenly spaced targets, so segments break
between vertebrae rather than through them.
"""
import collections, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'spine.svg.part')).read()

N_SEGS = 9
IMAGES = ['images/web/01-05-7.jpg', 'images/web/02-09-5.jpg', 'images/web/03-fig-5.jpg',
          'images/web/04-fig1.jpg', 'images/web/05-fig3.jpg', 'images/web/06-fig7.jpg',
          'images/web/07-front-portrait.jpg', 'images/web/08-zir8.jpg', 'images/web/09-3.jpg']
PLACEHOLDER_FILL = ['#822D00', '#F38530', '#FDF48E', '#D4F724', '#822D00',
                    '#F38530', '#FDF48E', '#D4F724', '#822D00']

head = re.match(r'<svg[^>]*>', src).group(0)
defs = re.search(r'<defs>.*?</defs>', src, re.S).group(0)
cells_src = re.search(r'<g class="cells">(.*?)</g>', src, re.S).group(1)
rects = [(int(x), int(y)) for x, y in
         re.findall(r'<rect x="(\d+)" y="(\d+)" width="1" height="1"/>', cells_src)]
glyph_els = [(el, int(y)) for el, y in
             re.findall(r'(<g clip-path="url\(#k..\)" transform="translate\(\d+,(\d+)\)">.*?</g>)', src, re.S)]

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
for x, y in rects:
    segs[seg_of(y)]['rects'].append((x, y))
for el, y in glyph_els:
    segs[seg_of(y)]['glyphs'].append(el)

out = [head, defs]
for i, s in enumerate(segs):
    xs = [x for x, _ in s['rects']]; ys = [y for _, y in s['rects']]
    sx0, sy0, sx1, sy1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
    rect_str = ''.join(f'<rect x="{x}" y="{y}" width="1" height="1"/>' for x, y in s['rects'])
    out.append(
        f'<g class="seg" data-seg="{i}">'
        f'<clipPath id="segclip-{i}">{rect_str}</clipPath>'
        f'<g class="cells">{rect_str}</g>'
        f'<g class="glyphs">{"".join(s["glyphs"])}</g>'
        f'<g class="pic" clip-path="url(#segclip-{i})">'
        f'<rect x="{sx0}" y="{sy0}" width="{sx1-sx0}" height="{sy1-sy0}" fill="{PLACEHOLDER_FILL[i]}"/>'
        f'<image href="{IMAGES[i]}" x="{sx0}" y="{sy0}" width="{sx1-sx0}" height="{sy1-sy0}" '
        f'preserveAspectRatio="xMidYMid slice"/>'
        f'</g></g>')
    print(f'seg {i}: rows {sy0}-{sy1-1}, {len(s["rects"])} cells')
out.append('</svg>')
open(os.path.join(HERE, 'spine.seg.part'), 'w').write('\n'.join(out))
print('cuts at rows', CUTS)
