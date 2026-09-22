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
# Poster type. Three layers per element, all of it plain CSS:
#
#   bloom  the whole block copied and blurred far past legibility, so the light
#          follows the SILHOUETTE OF THE BLOCK rather than each glyph — this is
#          the layer that makes it read as one lit object instead of lit letters
#   tight  a glow hugging each glyph, two stops of text-shadow
#   ink    the letterform itself, barely softened
#
# Tuned in tools/_page.html. Two things worth knowing before changing a number:
#
# The glows are NOT proportional to the type size. Measured across the sizes that
# were tuned by eye (110 / 40 / 24 / 20 / 16 / 14px), both radii come out near
# constant in px — the light belongs to the page, not to the glyph. So the bloom
# radius and the ink softness are absolute, and only the tight glow is in em,
# where it tracks the size loosely. A breakpoint therefore only changes font
# sizes; the light stays put.
#
# The colours live in sets, not in the roles. Mixing on this page is done by
# colour rather than by a second typeface, so a role points at a set and the set
# holds the three colours. Switching a role from 'a' to 'b' is one word.
COLOUR_SETS = dict(
    a=dict(ink='#f38432', glow='#fdf48e', bloom='#fdf48e'),
    b=dict(ink='#277c3c', glow='#fdf48e', bloom='#fdf48e'),
)

# The poster's roles, and the whole of what it takes to add one. size is (poster,
# under the 760px breakpoint). width caps the measure in ch, so it holds when the
# size changes. The logo is the odd one out: it is a drawn mark, so its size is
# the drawing's height and it has no text properties.
ROLES = dict(
    logo=dict(set='a', size=(110, 66), soft=1.6, glow=.095, bloom=9,  bloomA=1),
    title=dict(set='a', size=(40, 30), soft=1.4, glow=.3,   bloom=14, bloomA=1,
               weight=500, ls=-.055, lh=.8),
    tag=dict(set='a', size=(20, 16),   soft=1,   glow=.805, bloom=16, bloomA=1,
             weight=500, ls=-.03, lh=.9, width=34),
    info=dict(set='a', size=(24, 18),  soft=1.2, glow=.805, bloom=20, bloomA=1,
              weight=500, ls=-.04, lh=.9),
    desc=dict(set='a', size=(20, 16),  soft=1,   glow=.805, bloom=16, bloomA=1,
              weight=500, ls=-.03, lh=.9, width=42),
)

LAYERS = ('bloom', 'tight', 'ink')

# Grain over the whole page. feTurbulence's fractalNoise comes out with a mean of
# 0.732, not 0.5, and `overlay` is only the identity at 0.5 — left alone a grain
# this strong lifts the background by about +14 per channel and shifts its hue.
# The transfer below recentres it, so the grain is texture and nothing else and
# the gradient renders the colours it is given.
GRAIN = dict(cell=1.9, opacity=.82, mean=.732)


def grain_url():
    g = GRAIN
    shift = f'{0.5 - g["mean"]:.3f}'
    transfer = ('<feComponentTransfer>'
                + ''.join(f"<feFunc{c} type='linear' slope='1' intercept='{shift}'/>"
                          for c in 'RGB')
                + '</feComponentTransfer>')
    return ("url(\"data:image/svg+xml;utf8,"
            "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'>"
            f"<feTurbulence type='fractalNoise' baseFrequency='{1/g['cell']:.4f}' "
            "numOctaves='2' stitchTiles='stitch'/>"
            "<feColorMatrix type='saturate' values='0'/>"
            f"{transfer}</filter>"
            "<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")")


def type_css():
    """One block per role: its own colours and radii as custom properties, which
    the three shared layer rules read."""
    out = []
    for role, r in ROLES.items():
        c = COLOUR_SETS[r['set']]
        v = [f"--ink:{c['ink']}", f"--glow:{c['glow']}", f"--bloom:{c['bloom']}",
             f"--fs:{r['size'][0]}px", f"--soft:{r['soft']}px",
             f"--glowR:{r['glow']}em", f"--bloomR:{r['bloom']}px", f"--bloomA:{r['bloomA']}"]
        if 'weight' in r:
            v += [f"--w:{r['weight']}", f"--ls:{r['ls']}em", f"--lh:{r['lh']}"]
        if 'width' in r:
            v += [f"--maxw:{r['width']}ch"]
        out.append(f".t-{role}{{{';'.join(v)}}}")
    return '\n  '.join(out)


def type_css_small():
    """The breakpoint only moves font sizes. Every radius is absolute except the
    tight glow, which is in em and follows on its own."""
    return ''.join(f".t-{role}{{--fs:{r['size'][1]}px}}"
                   for role, r in ROLES.items() if r['size'][0] != r['size'][1])


# The measure is capped against the viewport as well as in ch: the poster's
# blocks are max-content and pinned to a corner, so on a narrow screen a measure
# set in ch would simply run off the edge.
TYPE_CSS = '''.t{--fit:calc(100vw - 2 * var(--pad));
    position:relative;margin:0;color:var(--ink);font-size:var(--fs);
    max-width:min(var(--maxw,var(--fit)),var(--fit))}
  .t>*{margin:0;font-family:var(--font-sans);font-weight:var(--w);font-size:var(--fs);
    letter-spacing:var(--ls);line-height:var(--lh);
    max-width:min(var(--maxw,var(--fit)),var(--fit))}
  /* Only the first layer is in flow; the other two are laid over it, so the box
     is the size of the text and the light spills outside it. */
  .t>*+*{position:absolute;inset:0}
  .t .bloom{color:var(--bloom);filter:blur(var(--bloomR));opacity:var(--bloomA)}
  .t .tight{color:transparent;
    text-shadow:0 0 calc(var(--glowR) * .35) var(--glow), 0 0 var(--glowR) var(--glow)}
  .t .ink{filter:blur(var(--soft))}
  /* text-shadow does nothing to an SVG, so the mark's tight glow is a pair of
     drop-shadows, and the layer needs a fill for them to have any alpha to cast. */
  .t-logo{line-height:0}
  .t-logo svg{height:var(--fs);width:auto;display:block;overflow:visible}
  .t-logo .bloom svg{fill:var(--bloom);filter:blur(var(--bloomR));opacity:var(--bloomA)}
  .t-logo .tight svg{fill:var(--glow);
    filter:drop-shadow(0 0 calc(var(--glowR) * .35) var(--glow)) drop-shadow(0 0 var(--glowR) var(--glow))}
  .t-logo .ink svg{fill:var(--ink);filter:blur(var(--soft))}'''


def layers(tag, role, html, **attrs):
    """The three copies. Only the ink layer is real text; the other two are
    decoration and are hidden from the accessibility tree and from find-in-page."""
    extra = ''.join(f' {k}="{v}"' for k, v in attrs.items())
    return (f'<div class="t t-{role}"{extra}>'
            + ''.join(f'<{tag} class="{name}"'
                      + ('' if name == 'ink' else ' aria-hidden="true"')
                      + f'>{html}</{tag}>' for name in LAYERS)
            + '</div>')


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
  .bg{position:fixed;inset:0;z-index:-1;
    background:linear-gradient(180deg,#66BF8C 0%,#92CA87 70%,#68C08D 100%)}
  /* Over everything, including the spine and the type — it is the medium, not a
     property of any one layer. Constant cell size, so it never tracks a font. */
  .grain{position:fixed;inset:0;z-index:4;pointer-events:none;
    mix-blend-mode:overlay;opacity:__GRAINA__;
    background-size:__GRAINSIZE__ __GRAINSIZE__;background-image:__GRAINURL__}
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
  __TYPEBASE__
  __TYPECSS__
  :root{--pad:24px;--tag-gap:14px}
  .poster{position:fixed;inset:0;z-index:3;pointer-events:none;padding:var(--pad)}
  .poster>*{position:absolute;pointer-events:auto;width:max-content;margin:0}
  .poster h1,.poster p{margin:0}
  /* Four corners. Everything on the poster is pinned to one of them, so a new
     block is a class, not a new rule. The right-hand pair is set right-aligned:
     they grow inward, away from their edge. */
  .head{left:var(--pad);top:var(--pad)}
  .head-r{right:var(--pad);top:var(--pad);text-align:right;
    display:flex;flex-direction:column;align-items:flex-end;gap:var(--tag-gap)}
  .foot{left:var(--pad);bottom:var(--pad)}
  .foot-r{right:var(--pad);bottom:var(--pad)}
  @media (max-width:760px){
    :root{--pad:16px}
    /* Too narrow to keep the two bottom corners apart: the right-hand one
       stacks above the left, on the left edge. */
    .foot-r{right:auto;left:var(--pad);bottom:calc(var(--pad) + 6.2em)}
    __TYPECSS_SMALL__
  }
  .lens{position:fixed;left:0;top:0;width:var(--lens,100px);height:var(--lens,100px);border-radius:50%;background:#8A8A8A;filter:blur(var(--feather,8px));
    mix-blend-mode:difference;pointer-events:none;z-index:100;transform:translate(-1000px,-1000px);will-change:transform;display:none}
  @media (hover:hover) and (pointer:fine){.lens{display:block}}

</style>'''

BODY = '''
<div class="bg"></div>
<div class="grid"></div>
<div class="lens" id="lens"></div>
<div class="poster">
  <div class="head">__T_LOGO__</div>
  <div class="head-r">__T_TITLE____T_TAG__</div>
  <div class="foot">__T_INFO__</div>
  <div class="foot-r">__T_DESC__</div>
</div>
<div class="grain"></div>
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

# The copy, kept next to the markup that places it.
COPY = dict(
    title='Spinal<br>Memory',
    tag='Research and Practice on<br>Non-Human Animals',
    info='Online Lectures<br>5 weeks<br>Oct 10 ~ Nov 7, 2026<br>9am EDT / 9PM CST',
    desc='<p>Spinal Memory, the fourth issue of te magazine, grew out of a reflection '
         'on the imagining of non-human animals. As an extension of this issue\u2019s theme, '
         'te editions is launching its first online lecture series, inviting nine speakers '
         '(including several contributors to this issue) to give eight online lectures.</p>'
         '<p>Each speaker approaches this theme in a completely different way: years of '
         'companionship and careful field observation, or history, design, writing, moving '
         'image, archives, and data.</p>',
)


def page(inline, spine=None, cols=None, rows=None):
    spine = SPINE if spine is None else spine
    cols = SPINE_COLS if cols is None else cols
    rows = SPINE_ROWS if rows is None else rows
    grain = grain_url()
    return (HEAD.replace('__FONTS__', font_faces(inline))
                .replace('__TYPEBASE__', TYPE_CSS).replace('__TYPECSS__', type_css())
                .replace('__TYPECSS_SMALL__', type_css_small())
                .replace('__GRAINURL__', grain).replace('__GRAINA__', str(GRAIN['opacity']))
                .replace('__GRAINSIZE__', f"{GRAIN['cell'] * 40:g}px")
                .replace('__COLS__', f'{cols:g}').replace('__ROWS__', str(rows))
            + BODY.replace('__SPINE__', spine)
                  .replace('__T_LOGO__', layers('div', 'logo', LOGO, **{'aria-label': 'te'}))
                  .replace('__T_TITLE__', layers('h1', 'title', COPY['title']))
                  .replace('__T_TAG__', layers('p', 'tag', COPY['tag']))
                  .replace('__T_INFO__', layers('p', 'info', COPY['info']))
                  .replace('__T_DESC__', layers('div', 'desc', COPY['desc'])))


repo_doc = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + page(False).replace('</style>', '</style>\n</head>\n<body>', 1) + '</body>\n</html>\n')
open(os.path.join(REPO, 'index.html'), 'w').write(repo_doc)
# the artifact is the poster itself, fonts inlined
art = page(True)
open(os.path.join(REPO, 'artifact.html'), 'w').write(art)
print(f'index.html {len(repo_doc)//1024} KB ({SPINE_COLS:g}x{SPINE_ROWS}) · '
      f'artifact.html {len(art)//1024} KB')
