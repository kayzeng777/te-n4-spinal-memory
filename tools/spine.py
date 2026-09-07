#!/usr/bin/env python3
"""Split the flat spine SVG (spine.svg.part) into hoverable segments -> spine.seg.part."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'spine.svg.part')).read()

# first row of each segment after the first; chosen at narrow points between vertebrae
CUTS = [15, 32, 48, 65, 78, 97, 113, 129]
IMAGES = ['images/web/01-05-7.jpg', 'images/web/02-09-5.jpg', 'images/web/03-fig-5.jpg', 'images/web/04-fig1.jpg', 'images/web/05-fig3.jpg', 'images/web/06-fig7.jpg', 'images/web/07-front-portrait.jpg', 'images/web/08-zir8.jpg', 'images/web/09-3.jpg']
PLACEHOLDER_FILL = ['#822D00', '#F38530', '#FDF48E', '#D4F724', '#822D00', '#F38530', '#FDF48E', '#D4F724', '#822D00']

import random
SYMBOLS = [c for c in '𓃠 𓃰 𓃱 𓃯 𓃸 𓃵 𓃗 𓃙 𓃟 𓄀 𓄁 𓄂 𓄃 𓃚 𓃛 𓃜 𓃞 𓃓 𓃔 𓃕 𓃖 𓃦 𓃬 𓃷 𓃹 𓃻 𓃾 𓄅 𓄇 𓆈 𓆉 𓆌 𓆏 𓆗 𓆙 𓆐 𓆓 𓆊 𓆣 𓆤 𓆦 𓆧 𓆨 𓆝 𓆡 𓅂 𓅐 𓅓 𓅟 𓅮 𓅰 𓆀' if not c.isspace()]
SYMBOL_SHARE = 0.0  # static share; live cycling is done in JS (see build.py)
rng = random.Random(4)

def pick_symbol_cells(positions):
    """~60% of cells, preferring cells whose 4-neighbours are not already picked."""
    pos = set(positions); order = list(positions); rng.shuffle(order)
    target = round(len(order) * SYMBOL_SHARE); chosen = set()
    for x, y in order:  # pass 1: no adjacent picks
        if len(chosen) >= target: break
        if not any(n in chosen for n in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))): chosen.add((x, y))
    for x, y in order:  # pass 2: top up randomly
        if len(chosen) >= target: break
        chosen.add((x, y))
    return chosen

head = re.match(r'<svg[^>]*>', src).group(0)
cells_src = re.search(r'<g class="cells">(.*?)</g>', src, re.S).group(1)
rects = re.findall(r'<rect x="(\d+)" y="(\d+)" width="1" height="1"/>', cells_src)
defs = re.search(r'<defs>.*?</defs>', src, re.S).group(0)
glyphs = re.findall(r'<g clip-path="url\(#k..\)" transform="translate\((\d+),(\d+)\)">.*?</g>', src, re.S)
glyph_els = re.findall(r'(<g clip-path="url\(#k..\)" transform="translate\((\d+),(\d+)\)">.*?</g>)', src, re.S)
symbol_cells = pick_symbol_cells([(int(x), int(y)) for _, x, y in glyph_els])
def symbolize(el, x, y):
    if (x, y) not in symbol_cells: return el
    return re.sub(r'<text ([^>]*)>[^<]*</text>', lambda m: f'<text class="h" {m.group(1)}>{rng.choice(SYMBOLS)}</text>', el)
glyph_els = [(symbolize(el, int(x), int(y)), y) for el, x, y in glyph_els]
print(f'symbol cells: {len(symbol_cells)} of {len(glyph_els)}')

def seg_of(y):
    y = int(y)
    return sum(1 for c in CUTS if y >= c)

segs = [{'rects': [], 'glyphs': []} for _ in range(9)]
for x, y in rects:
    segs[seg_of(y)]['rects'].append((int(x), int(y)))
for el, y in glyph_els:
    segs[seg_of(y)]['glyphs'].append(el)

GLOW = ('<filter id="glow" x="-30%" y="-30%" width="160%" height="160%" filterUnits="objectBoundingBox">'
        '<feGaussianBlur stdDeviation="0.22" result="b"/>'
        '<feComponentTransfer in="b" result="g"><feFuncA type="linear" slope="1.4"/></feComponentTransfer>'
        '<feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
out = [head, defs.replace('</defs>', GLOW + '</defs>')]
for i, s in enumerate(segs):
    xs = [x for x, _ in s['rects']]; ys = [y for _, y in s['rects']]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
    rect_str = ''.join(f'<rect x="{x}" y="{y}" width="1" height="1"/>' for x, y in s['rects'])
    out.append(
        f'<g class="seg" data-seg="{i}">'
        f'<clipPath id="segclip-{i}">{rect_str}</clipPath>'
        f'<g class="cells">{rect_str}</g>'
        f'<g class="glyphs">{"".join(s["glyphs"])}</g>'
        f'<g class="pic" clip-path="url(#segclip-{i})">'
        f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="{PLACEHOLDER_FILL[i]}"/>'
        f'<image href="{IMAGES[i]}" x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" preserveAspectRatio="xMidYMid slice"/>'
        f'</g></g>')
    print(f'seg {i}: rows {y0}-{y1-1}, {len(s["rects"])} cells, {len(s["glyphs"])} glyphs')
out.append('</svg>')
open(os.path.join(HERE, 'spine.seg.part'), 'w').write('\n'.join(out))
