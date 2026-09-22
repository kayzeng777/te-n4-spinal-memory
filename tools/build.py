#!/usr/bin/env python3
"""Build index.html (repo, file fonts) and artifact.html (inline fonts) from parts."""
import base64, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
def load_spine(name):
    svg = open(os.path.join(HERE, name)).read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    cols, height = float(m.group(1)), float(m.group(2))
    return svg, cols, round(height / 1.6)


SPINE, SPINE_COLS, SPINE_ROWS = load_spine('spine.seg.part')
# ---------------------------------------------------------------------------
# Poster type. One SVG filter per role per breakpoint, built from a distance
# field: feMorphology erode stacked into equal-width shells around the contour.
# The field is what makes the effect even — a Gaussian blur of the alpha is a
# THICKNESS field (a stem's centre reads deeper than a hairline's), while equal
# width shells are the same on every stroke and in every direction.
#
# Three layers, merged in this order:
#   glow  dilate (equal width, so thin strokes glow as much as thick ones)
#         then a Gaussian, then gamma
#   base  the edge colour filling the whole glyph
#   core  the fill colour carried by the distance field, covering the middle
#
# Every length is derived from the role's font size, so a breakpoint that changes
# a size gets its own filter. Values were tuned in tools/_two.html.
TYPE = dict(
    fill='#F28331', edge='#FDF48E', glow='#FDF48E',
    ratio=.09,          # inward distance as a fraction of the STEM width
    min_core=1.0,       # below this much remaining core, fall back to solid fill
    steps=4,            # shells; each one is a feMorphology
    falloff=1.5,        # how the shell opacity steps down inward
    round=1.2,          # each shell is blurred by round x its own radius: the
                        # feMorphology kernel is a BOX, whose corner sticks out by
                        # 0.41 x radius, so the rounding must scale with radius
    peak=1.0,           # field value at the deepest shell
    comp=.75,           # small-size compensation, tapering to 1 at ref_size
    ref_size=32,
    g_fat=.06,          # glow: dilate before the blur, as a fraction of font size
    g_blur=.085,        # glow: Gaussian sigma, as a fraction of font size
    g_amp=1.0,
    g_gamma=.85,
)

# Stem width per font size. Measured off the rendered font (a canvas scanline
# across 'H', median run length) at 20/24/32/48/64px, then fitted: the per-size
# numbers are quantised by the pixel grid and come out non-monotonic (15px reads
# 3px while 16px reads 2px), so a single ratio is the honest summary.
PP_STEM = .167          # PP Neue Montreal 600
PP_WEIGHT, PP_LS, PP_LH = 600, -.06, .9
# The logo is a drawn mark, so its stroke was measured the same way but off a
# rasterised copy of the SVG: 0.100 of the mark's height, steady from 32 to 200px.
# It is noticeably lighter than PP's 0.167 per em, which is why the logo needs a
# much larger ratio to get a comparable edge.
LOGO_STEM = .100

# The logo is not type and does not want the same numbers: a much wider edge (it
# has plenty of core to spare at any size), a tighter, harder glow, and its
# compensation starting higher up. Anything not named here falls back to TYPE.
LOGO_FX = dict(ratio=.4, mult=.45, comp=.35, ref_size=56,
               steps=4, falloff=1.25, round=1.0, peak=1.0,
               g_fat=.08, g_blur=.045, g_amp=1.0, g_gamma=3.0)
TYPE_MULT = dict(info=1.4)

# role -> (size on the poster, size under the 760px breakpoint)
# Apoc is gone from the poster; `te` stays because it is an SVG logotype, not type.
TYPE_SIZES = dict(logo=(120, 72), info=(20, 15))


def _fx(role):
    """Per-role parameters: the type defaults, with the logo's overrides on top."""
    t = dict(TYPE)
    t['mult'] = TYPE_MULT.get(role, 1.0)
    if role == 'logo':
        t.update(LOGO_FX)
    return t


def _stem(role, fs):
    return (LOGO_STEM if role == 'logo' else PP_STEM) * fs


def _boost(t, fs):
    """Small sizes get a wider edge, tapering back to 1 at ref_size."""
    return 1 + t['comp'] * max(0.0, (t['ref_size'] - fs) / t['ref_size'])


def _inward(role, fs):
    """Inward distance in px, or 0 when too little core would be left."""
    t = _fx(role)
    stem = _stem(role, fs)
    d = stem * min(.48, t['ratio'] * _boost(t, fs)) * t['mult']
    return 0.0 if stem - 2 * d < t['min_core'] else d


def _shells(op, total, n, peak, falloff, round_by):
    """Equal-width shells as an alpha staircase.

    feMerge composites alpha-over, so stacking the target values directly would
    saturate; each shell's opacity is solved back from the staircase it should
    add up to:  w_k = 1 - (1 - T_k) / (1 - T_k+1)
    """
    target = lambda k: peak * (1 - (k - 1) / n) ** falloff
    parts, nodes = [], []
    for k in range(n, 0, -1):                 # outermost first, inner ones on top
        r = total * (n - k + 1) / n if op == 'erode' else total * k / n
        w = target(n) if k == n else 1 - (1 - target(k)) / (1 - target(k + 1))
        w = max(0.0, min(1.0, w))
        rd = r * round_by
        parts.append(
            f'<feMorphology in="SourceAlpha" operator="{op}" radius="{r:.2f}" result="d{k}"/>'
            + (f'<feGaussianBlur in="d{k}" stdDeviation="{rd:.2f}" result="r{k}"/>'
               if rd > .05 else f'<feOffset in="d{k}" dx="0" dy="0" result="r{k}"/>')
            + f'<feFlood flood-color="#fff" flood-opacity="{w:.4f}" result="f{k}"/>'
            + f'<feComposite in="f{k}" in2="r{k}" operator="in" result="s{k}"/>')
        nodes.append(f'<feMergeNode in="s{k}"/>')
    return ''.join(parts) + f'<feMerge result="field">{"".join(nodes)}</feMerge>'


def type_filter(role, fs, fid):
    t = _fx(role)
    b = _boost(t, fs)
    glow = (f'<feMorphology in="SourceAlpha" operator="dilate" radius="{fs*t["g_fat"]*b:.2f}" result="gfat"/>'
            f'<feGaussianBlur in="gfat" stdDeviation="{fs*t["g_blur"]*b:.2f}" result="gb"/>'
            f'<feComponentTransfer in="gb" result="gsh"><feFuncA type="gamma" '
            f'amplitude="{t["g_amp"]}" exponent="{t["g_gamma"]}" offset="0"/></feComponentTransfer>'
            f'<feFlood flood-color="{t["glow"]}" result="gc"/>'
            f'<feComposite in="gc" in2="gsh" operator="in" result="glow"/>')
    head = (f'<filter id="{fid}" x="-160%" y="-160%" width="420%" height="420%" '
            f'color-interpolation-filters="sRGB">')
    d = _inward(role, fs)
    if d <= 0:                                  # too thin for two colours
        return (head + glow + f'<feFlood flood-color="{t["fill"]}" result="c"/>'
                + '<feComposite in="c" in2="SourceAlpha" operator="in" result="letter"/>'
                + '<feMerge><feMergeNode in="glow"/><feMergeNode in="letter"/></feMerge></filter>')
    return (head + glow
            + _shells('erode', d, t['steps'], t['peak'], t['falloff'], t['round'])
            + f'<feFlood flood-color="{t["edge"]}" result="ec"/>'
            + '<feComposite in="ec" in2="SourceAlpha" operator="in" result="base"/>'
            + f'<feFlood flood-color="{t["fill"]}" result="fc"/>'
            + '<feComposite in="fc" in2="field" operator="in" result="core"/>'
            + '<feMerge><feMergeNode in="glow"/><feMergeNode in="base"/>'
              '<feMergeNode in="core"/></feMerge></filter>')


def type_defs():
    out = []
    for role, (big, small) in TYPE_SIZES.items():
        out.append(type_filter(role, big, f'tw-{role}'))
        if small != big:
            out.append(type_filter(role, small, f'tw-{role}-s'))
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
            '<defs>' + ''.join(out) + '</defs></svg>')


def type_css():
    t = TYPE
    logo, info = TYPE_SIZES['logo'][0], TYPE_SIZES['info'][0]
    return '\n  '.join([
        f".t{{color:{t['fill']};margin:0}}",
        f".t-logo{{line-height:0;filter:url(#tw-logo)}}",
        f".t-logo svg{{height:{logo}px;width:auto;display:block;overflow:visible;fill:currentColor}}",
        f".t-info{{font-family:var(--font-sans);font-weight:{PP_WEIGHT};font-size:{info}px;"
        f"line-height:{PP_LH};letter-spacing:{PP_LS}em;filter:url(#tw-info)}}",
    ])


def type_css_small():
    logo, info = TYPE_SIZES['logo'][1], TYPE_SIZES['info'][1]
    return (f".t-logo{{filter:url(#tw-logo-s)}}.t-logo svg{{height:{logo}px}}"
            f".t-info{{font-size:{info}px;filter:url(#tw-info-s)}}")


LOGO_RAW = '<svg class="logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 405.76 481.63">\n  <path d="M114.11,0c-.01.91-.03,1.82-.03,2.72,0,37.34,0,74.67,0,112.01v2.97c6.41.12,12.68.04,18.94.05,6.29.01,12.59,0,18.88,0h75.65c.48,1.69.54,16.63.07,18.88h-113.43c-.04.91-.1,1.59-.1,2.28,0,87.89.04,175.78-.04,263.67-.02,23.15,16.08,42.26,37.46,46.96,25.8,5.67,51.84-11.48,56.6-37.5.54-2.94.81-5.97.82-8.95.06-27.41.04-54.82.04-82.23,0-.83,0-1.67,0-2.46,1.58-.49,16.06-.6,18.88-.14,0,.77,0,1.58,0,2.4,0,23.35,0,46.71,0,70.06,0,3.36.05,6.71.03,10.07-.17,35.88-24.74,68.57-60.98,78.13-4.46,1.18-9,1.99-13.61,2.34-.62.05-1.22.24-1.83.36h-10.91c-.61-.13-1.21-.28-1.82-.37-3.31-.5-6.69-.73-9.93-1.51-29.56-7.15-49.69-25.01-60.17-53.56-3.07-8.37-4.45-17.12-4.44-26.08.02-81.92.01-163.84.01-245.76,0-5.1,0-10.21,0-15.31,0-.74,0-1.48,0-2.39-1.13,0-1.96,0-2.79,0-19.5,0-39,0-58.5-.01-.97,0-1.93-.18-2.9-.28,0-6.15,0-12.31,0-18.46,1.11-.04,2.23-.12,3.34-.12,19.43,0,38.86,0,58.3,0,.81,0,1.62-.05,2.55-.08V0h49.92Z"/>\n  <path d="M386.94,318.11h18.7c.02.82.07,1.63.07,2.44,0,22.79,0,45.59,0,68.38,0,3.71,0,7.41.03,11.12.14,15.77-4.25,30.26-12.81,43.39-12.91,19.8-31.09,32.16-54.36,36.34-44.59,8.01-85.72-21.09-94.67-63.86-1.16-5.53-1.79-11.13-1.79-16.83.06-72.99.06-145.99,0-218.98,0-7.54,1.11-14.89,3.14-22.1,8.34-29.59,32.37-52.06,62.5-58.02,46.12-9.13,87.41,21,96.33,63.01,1.09,5.14,1.69,10.31,1.68,15.59-.05,33.21-.03,66.42-.03,99.63,0,.83,0,1.66,0,2.76h-113.7v2.52c0,39.64-.02,79.29,0,118.93.01,23.78,17.12,43.73,40.68,47.16,25.4,3.7,48.35-13.27,53.23-37.36.66-3.26.95-6.65.95-9.99.07-27.13.04-54.26.04-81.38,0-.89,0-1.78,0-2.76ZM356.01,262.05c.04-.8.1-1.48.1-2.16.05-36.97.12-73.95.13-110.92,0-18.86-16.55-33.63-35.34-31.6-16.52,1.78-28.88,15.32-28.9,31.85-.05,36.98-.02,73.95,0,110.93,0,.61.08,1.22.13,1.9h63.89Z"/>\n</svg>'
LOGO = LOGO_RAW.replace('<path ', '<path vector-effect="non-scaling-stroke" ')
PP = [('Thin',100,'normal'),('ThinItalic',100,'italic'),('Light',300,'normal'),('LightItalic',300,'italic'),
      ('Book',350,'normal'),('BookItalic',350,'italic'),('Regular',400,'normal'),('Italic',400,'italic'),
      ('Medium',500,'normal'),('MediumItalic',500,'italic'),('SemiBold',600,'normal'),('SemiBolditalic',600,'italic'),
      ('Bold',700,'normal'),('BoldItalic',700,'italic')]

def font_src(name, inline):
    path = os.path.join(REPO, 'fonts', name + '.woff2')
    if inline:
        b = base64.b64encode(open(path, 'rb').read()).decode()
        return f"url(data:font/woff2;base64,{b}) format('woff2')"
    return f"url(fonts/{name}.woff2) format('woff2')"

def font_faces(inline):
    """PP only. Nothing is set in Apoc any more, so that face is not served;
    fonts/Apoc-Variable.woff2 is kept on disk but unused."""
    out = []
    for n, w, s in PP:
        out.append(f"@font-face{{font-family:'PP Neue Montreal';src:{font_src('PPNeueMontreal-'+n, inline)};font-weight:{w};font-style:{s};font-display:swap}}")
    return '\n  '.join(out)

HEAD = '''<title>te online lecture</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Egyptian+Hieroglyphs&display=swap">
<style>
  __FONTS__

  :root{
    --font-sans:"PP Neue Montreal",-apple-system,"Helvetica Neue",Arial,sans-serif;
    --ink:#101410; --ink-brown:#822D00; --ink-soft:rgba(16,20,16,.7);
    --cell:min(8px, calc(66vw / __COLS__));
  }
  *{box-sizing:border-box}
  html,body{margin:0;min-height:100%}
  body{min-height:100vh;background:#92CA87;color:var(--ink);position:relative;font-family:var(--font-sans);}
  .bg {
    position: fixed; inset: 0; z-index: -1;
    background: linear-gradient(180deg, #66BF8C 0%, #92CA87 31%, #BED881 63%, #A8D184 74%, #92CA87 87%, #68C08D 100%);
  }
  .bg::after {
    content: ""; position: absolute; inset: 0;
    opacity: 0.03; mix-blend-mode: multiply;
    background-size: 200px 200px;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='2.00' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.09  0 0 0 0 0.10  0 0 0 0 0.09  0 0 0 1 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
  }
  .grid{position:absolute;inset:0;pointer-events:none;z-index:0;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><path d='M0 0H1M0 0V1' fill='none' stroke='%23cccccc' stroke-width='.05' stroke-dasharray='.14 .1'/></svg>");
    background-size:var(--cell) var(--cell);
    background-position:calc(50% + var(--cell) / 2) 8vh;}
  main{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;padding:8vh 0 12vh}
  .spine{width:calc(__COLS__ * var(--cell));height:auto;overflow:visible;display:block}
  .cells rect{stroke:#cccccc;stroke-width:.05;stroke-dasharray:.14 .1;shape-rendering:crispEdges}
  .glyphs{--gfs:1.57px;--gdy:0.41px}
  .glyphs text{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace;font-size:var(--gfs);text-anchor:middle;dominant-baseline:auto;transform:translateY(var(--gdy));pointer-events:none}
  .glyphs text.h{font-family:"Noto Sans Egyptian Hieroglyphs",sans-serif;font-size:1.5px;dominant-baseline:central;transform:none}
  .seg .pic{opacity:0;transition:opacity .25s ease}
  .seg:hover .pic,.seg.active .pic{opacity:1}
  .seg{cursor:pointer}
  __TYPECSS__
  :root{--pad:24px}
  .poster{position:fixed;inset:0;z-index:3;pointer-events:none;padding:var(--pad)}
  .poster>*{position:absolute;pointer-events:auto;width:max-content;margin:0}
  .poster h1,.poster p{margin:0}
  .head{left:var(--pad);top:var(--pad)}
  .foot{left:var(--pad);bottom:var(--pad)}
  @media (max-width:760px){:root{--pad:16px}__TYPECSS_SMALL__}
  .lens{position:fixed;left:0;top:0;width:var(--lens,100px);height:var(--lens,100px);border-radius:50%;background:#8A8A8A;filter:blur(var(--feather,8px));
    mix-blend-mode:difference;pointer-events:none;z-index:100;transform:translate(-1000px,-1000px);will-change:transform;display:none}
  @media (hover:hover) and (pointer:fine){.lens{display:block}}

</style>'''

BODY = '''
<div class="bg"></div>
<div class="grid"></div>
<div class="lens" id="lens"></div>
__TYPEDEFS__
<div class="poster">
  <div class="head">
    <div class="t t-logo" aria-label="te">__LOGO__</div>
  </div>
  <div class="foot">
    <p class="t t-info">Online Lecture<br>5 weeks<br>Oct 10 ~ Nov 7, 2026<br>9am EDT / 9pm CST</p>
  </div>
</div>
<main id="content">
__SPINE__
<script>
  document.querySelectorAll('.seg').forEach(g=>g.addEventListener('click',e=>{
    const on=g.classList.contains('active');document.querySelectorAll('.seg.active').forEach(x=>x.classList.remove('active'));
    if(!on)g.classList.add('active');e.stopPropagation();}));
  document.addEventListener('click',()=>document.querySelectorAll('.seg.active').forEach(x=>x.classList.remove('active')));
  const lens=document.getElementById('lens'), q=new URLSearchParams(location.search);
  if(q.get('lens'))lens.style.setProperty('--lens',q.get('lens')+'px');
  if(q.get('feather'))lens.style.setProperty('--feather',q.get('feather')+'px');
  if(q.get('lenscolor'))lens.style.background='#'+q.get('lenscolor').replace('#','');
  if(q.get('cell'))document.documentElement.style.setProperty('--cell',q.get('cell')+'px');
  // a high-polling-rate mouse fires far more than once a frame, and the lens blends
  // against the whole page, so each write is expensive: coalesce onto one frame.
  let lx=0,ly=0,lqueued=false;
  addEventListener('pointermove',e=>{lx=e.clientX;ly=e.clientY;
    if(lqueued)return;lqueued=true;
    requestAnimationFrame(()=>{lqueued=false;
      lens.style.transform=`translate(${lx}px,${ly}px) translate(-50%,-50%)`;});},{passive:true});
  addEventListener('pointerleave',()=>{lens.style.transform='translate(-1000px,-1000px)';});
  // size ▓ so its ink exactly fills a cell, whichever monospace font actually resolved
  (function(){
    const t=document.querySelector('.glyphs text');if(!t)return;
    const c=document.createElement('canvas').getContext('2d');
    c.font='100px '+getComputedStyle(t).fontFamily;
    const m=c.measureText('▓'), a=m.actualBoundingBoxAscent/100, d=m.actualBoundingBoxDescent/100;
    if(!(a+d))return;
    const CELL=1.6, fs=CELL/(a+d);
    document.querySelectorAll('.glyphs').forEach(g=>{
      g.style.setProperty('--gfs',fs.toFixed(4)+'px');
      g.style.setProperty('--gdy',(CELL*a/(a+d)-CELL/2).toFixed(4)+'px');});
  })();
  // cells: ~5% show a hieroglyph animal at a time, 7s each, then another cell takes over.
  // while active the cell takes that glyph's colour as its background, and the animal is
  // drawn black on the light tones, white on the dark ones.
  (function(){
    const SYMS=Array.from('𓃠𓃰𓃱𓃯𓃸𓃵𓃗𓃙𓃟𓄀𓄁𓄂𓄃𓃚𓃛𓃜𓃞𓃓𓃔𓃕𓃖𓃦𓃬𓃷𓃹𓃻𓃾𓄅𓄇𓆈𓆉𓆌𓆏𓆗𓆙𓆐𓆓𓆊𓆣𓆤𓆦𓆧𓆨𓆝𓆡𓅂𓅐𓅓𓅟𓅮𓅰𓆀');
    const SHARE=0.05, HOLD=7000;
    const ts=[...document.querySelectorAll('.glyphs text')];if(!ts.length)return;
    // perceived brightness; the cut sits just above the accent orange (156) and below
    // the cream-orange midpoint (196) and the green of the holes (172), so only the
    // darkest tone of the ramp takes white ink.
    const light=c=>{const n=parseInt(c.slice(1),16);return !isNaN(n)&&((n>>16&255)*299+(n>>8&255)*587+(n&255)*114)/1000>165;};
    const key=t=>t.dataset.c+','+t.dataset.r;
    const rects=new Map([...document.querySelectorAll('.seg .cells rect')].map(r=>[r.dataset.c+','+r.dataset.r,r]));
    const idx=new Map(ts.map((t,i)=>[key(t),i])), active=new Set(), TARGET=Math.round(ts.length*SHARE);
    const rnd=n=>Math.floor(Math.random()*n);
    const free=i=>{const c=+ts[i].dataset.c,r=+ts[i].dataset.r;return !active.has(i)&&
      ![[1,0],[-1,0],[0,1],[0,-1]].some(([dc,dr])=>{const j=idx.get((c+dc)+','+(r+dr));return j!==undefined&&active.has(j);});};
    // every swap costs a layout+paint of the whole spine, and the lens blends against
    // that, so all the swaps that fall due in one TICK are done in a single batch:
    // ~4 paints a second instead of ~70, for the same glyphs at the same hold.
    const TICK=250, due=new Map();
    function on(i,first){const t=ts[i],rect=rects.get(key(t)),col=(t.getAttribute('fill')||'').toUpperCase();
      t.dataset.orig=t.textContent;t.textContent=SYMS[rnd(SYMS.length)];t.classList.add('h');
      t.removeAttribute('textLength');t.removeAttribute('lengthAdjust');
      t.parentNode.appendChild(t);   // paint above the neighbouring cells it overhangs
      t.style.fill=light(col)?'#000':'#fff';if(rect)rect.style.fill=col;active.add(i);
      due.set(i,performance.now()+(first?Math.random()*HOLD:HOLD));}
    function off(i){const t=ts[i],rect=rects.get(key(t));t.textContent=t.dataset.orig;t.classList.remove('h');
      t.setAttribute('textLength','1');t.setAttribute('lengthAdjust','spacingAndGlyphs');
      t.parentNode.insertBefore(t,t.parentNode.firstChild);   // drop back below the active animals
      t.style.fill='';if(rect)rect.style.fill='';active.delete(i);due.delete(i);}
    function spawn(first){for(let k=0;k<80;k++){const i=rnd(ts.length);if(free(i)){on(i,first);return true;}}return false;}
    for(let n=0;n<TARGET*3&&active.size<TARGET;n++)spawn(true);
    setInterval(()=>{
      if(document.hidden)return;              // nothing to paint, so don't
      const now=performance.now(),expired=[];
      due.forEach((at,i)=>{if(at<=now)expired.push(i);});
      expired.forEach(off);
      for(let n=0;n<expired.length&&active.size<TARGET;n++)spawn(false);
    },TICK);
  })();
</script>
</main>
'''

def page(inline, spine=None, cols=None, rows=None):
    spine = SPINE if spine is None else spine
    cols = SPINE_COLS if cols is None else cols
    rows = SPINE_ROWS if rows is None else rows
    return (HEAD.replace('__FONTS__', font_faces(inline)).replace('__TYPECSS__', type_css())
                .replace('__TYPECSS_SMALL__', type_css_small()).replace('__COLS__', f'{cols:g}')
                .replace('__ROWS__', str(rows))
            + BODY.replace('__SPINE__', spine)
                  .replace('__LOGO__', LOGO).replace('__TYPEDEFS__', type_defs()))


repo_doc = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + page(False).replace('</style>', '</style>\n</head>\n<body>', 1) + '</body>\n</html>\n')
open(os.path.join(REPO, 'index.html'), 'w').write(repo_doc)
# the artifact is the poster itself, fonts inlined
art = page(True)
open(os.path.join(REPO, 'artifact.html'), 'w').write(art)
print(f'index.html {len(repo_doc)//1024} KB ({SPINE_COLS:g}x{SPINE_ROWS}) · '
      f'artifact.html {len(art)//1024} KB')
