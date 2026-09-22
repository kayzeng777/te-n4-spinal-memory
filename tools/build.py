#!/usr/bin/env python3
"""Build index.html (repo, file fonts) and artifact.html (inline fonts) from parts."""
import base64, json, os, re

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

# The type scale. Each step carries the sizes AND the light, because the two were
# tuned together by eye and the light does not follow from the size on its own:
# soft and bloom are absolute px, glow is em. size is (poster, under the 760px
# breakpoint). Picking a different step for a role is one word.
STEPS = dict(
    mark=dict(size=(110, 66), soft=1.6,  glow=.095, bloom=9),
    xl  =dict(size=(40, 30),  soft=1.4,  glow=.3,   bloom=14),
    l   =dict(size=(24, 18),  soft=1.2,  glow=.805, bloom=20),
    m   =dict(size=(20, 16),  soft=1,    glow=.805, bloom=16),
    s   =dict(size=(16, 14),  soft=.94,  glow=1.06, bloom=17.3),
    xs  =dict(size=(14, 12),  soft=.86,  glow=1.15, bloom=16),
)

# Where everything sits, and the whole of what it takes to move it. `at` is one of
# the four corners; a corner stacks its roles in this order and aligns them to the
# edge it is pinned to, so the right-hand corners are right-aligned without being
# told. `gap` is the space above a role when it follows a sibling in the same
# corner. `step` names a row of STEPS, `set` a row of COLOUR_SETS. width caps the
# measure in ch so it survives a size change.
CORNERS = ('head', 'head-r', 'foot', 'foot-r')
ROLES = dict(
    logo=dict(at='head', step='mark', set='a'),
    title=dict(at='head-r', step='xl', set='a', weight=500, ls=-.055, lh=.8),
    tag=dict(at='head-r', step='s', set='a', gap=14, width=34,
             weight=500, ls=-.03, lh=.9),
    info=dict(at='foot-r', step='l', set='a', weight=500, ls=-.04, lh=.9),
    desc=dict(at='foot', step='s', set='a', width=19, weight=500, ls=-.03, lh=.9),
)


# Type that is not pinned to a corner: the lecture blocks along the spine. Same
# three-layer machinery, same steps and colour sets as the poster roles — the
# only difference is that nothing places them, the spine does.
TEXT = dict(
    lecn=dict(step='xs', set='a', weight=500, ls=-.03, lh=1),
    lect=dict(step='m',  set='a', weight=500, ls=-.04, lh=.9),
    lecb=dict(step='xs', set='a', weight=500, ls=-.03, lh=1.2, width=34),
)

# One row per segment of the spine, top to bottom: segment 0 is the top vertebra.
# `when` and `who` are one line each; `what` is the title; `about` is prose, and
# a blank line in it starts a paragraph, exactly as in COPY.
# TODO: placeholder copy — the dates are spaced across oct 10 ~ nov 7 but not
# confirmed, and every speaker, title and blurb is still to be filled in.
LECTURES = [
    dict(when='oct 10, 2026', who='speaker one',   what='lecture one',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 11, 2026', who='speaker two',   what='lecture two',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 17, 2026', who='speaker three', what='lecture three',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 18, 2026', who='speaker four',  what='lecture four',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 24, 2026', who='speaker five',  what='lecture five',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 25, 2026', who='speaker six',   what='lecture six',
         about='One or two sentences on what this lecture is about.'),
    dict(when='oct 31, 2026', who='speaker seven', what='lecture seven',
         about='One or two sentences on what this lecture is about.'),
    dict(when='nov 7, 2026',  who='speaker eight', what='lecture eight',
         about='One or two sentences on what this lecture is about.'),
]


def at_corner(corner):
    """The roles pinned to one corner, in the order they are declared."""
    return [r for r in ROLES if ROLES[r]['at'] == corner]


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
    for role, r in {**ROLES, **TEXT}.items():
        c, st = COLOUR_SETS[r['set']], STEPS[r['step']]
        v = [f"--ink:{c['ink']}", f"--glow:{c['glow']}", f"--bloom:{c['bloom']}",
             f"--fs:{st['size'][0]}px", f"--soft:{st['soft']}px",
             f"--glowR:{st['glow']}em", f"--bloomR:{st['bloom']}px"]
        if 'weight' in r:
            v += [f"--w:{r['weight']}", f"--ls:{r['ls']}em", f"--lh:{r['lh']}"]
        if 'width' in r:
            v += [f"--maxw:{r['width']}ch"]
        if r.get('gap'):
            v += [f"--gap:{r['gap']}px"]
        out.append(f".t-{role}{{{';'.join(v)}}}")
    return '\n  '.join(out)


def type_css_small():
    """The breakpoint only moves font sizes. Every radius is absolute except the
    tight glow, which is in em and follows on its own."""
    return ''.join(f".t-{role}{{--fs:{STEPS[r['step']]['size'][1]}px}}"
                   for role, r in {**ROLES, **TEXT}.items()
                   if STEPS[r['step']]['size'][0] != STEPS[r['step']]['size'][1])


# The measure is capped against the viewport as well as in ch: the poster's
# blocks are max-content and pinned to a corner, so on a narrow screen a measure
# set in ch would simply run off the edge.
TYPE_CSS = '''.t{--fit:calc(100vw - 2 * var(--pad) - var(--tools,0px));
    position:relative;margin:0;color:var(--ink);font-size:var(--fs);
    max-width:min(var(--maxw,var(--fit)),var(--fit))}
  .t>*{margin:0;font-family:var(--font-sans);font-weight:var(--w);font-size:var(--fs);
    letter-spacing:var(--ls);line-height:var(--lh);
    max-width:min(var(--maxw,var(--fit)),var(--fit))}
  /* Only the first layer is in flow; the other two are laid over it, so the box
     is the size of the text and the light spills outside it. */
  .t>*+*{position:absolute;inset:0}
  .t .bloom{color:var(--bloom);filter:blur(var(--bloomR));opacity:1}
  .t .tight{color:transparent;
    text-shadow:0 0 calc(var(--glowR) * .35) var(--glow), 0 0 var(--glowR) var(--glow)}
  .t .ink{filter:blur(var(--soft))}
  /* text-shadow does nothing to an SVG, so the mark's tight glow is a pair of
     drop-shadows, and the layer needs a fill for them to have any alpha to cast. */
  .t-logo{line-height:0}
  .t-logo svg{height:var(--fs);width:auto;display:block;overflow:visible}
  .t-logo .bloom svg{fill:var(--bloom);filter:blur(var(--bloomR));opacity:1}
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
  .grain{position:fixed;inset:0 var(--tools,0) 0 0;z-index:4;pointer-events:none;
    mix-blend-mode:overlay;opacity:__GRAINA__;
    background-size:__GRAINSIZE__ __GRAINSIZE__;background-image:__GRAINURL__}
  .grid{position:absolute;inset:0;pointer-events:none;z-index:0;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><path d='M0 0H1M0 0V1' fill='none' stroke='%23cccccc' stroke-width='.05' stroke-dasharray='.14 .1'/></svg>");
    background-size:var(--cell) var(--cell);
    background-position:calc(50% + var(--cell) / 2) 8vh;}
  main{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;
    padding:8vh 0 12vh;margin-right:var(--tools,0)}
  .spine{width:calc(__COLS__ * var(--cell));height:auto;overflow:visible;display:block}
  .cells rect{stroke:#cccccc;stroke-width:.05;stroke-dasharray:.14 .1;shape-rendering:crispEdges}
  .glyphs{--gfs:1.57px;--gdy:0.41px}
  .glyphs text{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace;font-size:var(--gfs);text-anchor:middle;dominant-baseline:auto;transform:translateY(var(--gdy));pointer-events:none}
  .glyphs text.h{font-family:"Noto Sans Egyptian Hieroglyphs",sans-serif;font-size:1.5px;dominant-baseline:central;transform:none}
  .seg .pic{opacity:0;transition:opacity var(--lec-out,.26s) ease}
  /* `hot` is hover as the script sees it. Not the same as :hover — after a
     click glides the spine under a still cursor, nothing is hovered until
     the reader moves, and :hover cannot be told that. */
  .seg.hot .pic,.seg.active .pic{opacity:1}
  .seg{cursor:pointer}
  __TYPEBASE__
  __TOOLSCSS__
  __TYPECSS__
  __LECCSS__
  :root{--pad:24px}
  /* --tools is the width the side panel takes when it is open, so the stage
     gives way and the right-hand corners stay visible. */
  .poster{position:fixed;inset:0 var(--tools,0) 0 0;z-index:3;pointer-events:none;padding:var(--pad)}
  .poster>*{position:absolute;pointer-events:auto;width:max-content;margin:0}
  .poster h1,.poster p{margin:0}
  /* Four corners. Everything on the poster is pinned to one of them, so a new
     block is a class, not a new rule. The right-hand pair is set right-aligned:
     they grow inward, away from their edge. */
  .poster>*{display:flex;flex-direction:column}
  .head,.foot{left:var(--pad);align-items:flex-start;text-align:left}
  .head-r,.foot-r{right:var(--pad);align-items:flex-end;text-align:right}
  .head,.head-r{top:var(--pad)}
  .foot,.foot-r{bottom:var(--pad)}
  /* A role that follows a sibling in the same corner sets its own space above. */
  .poster>*>*+*{margin-top:var(--gap,0)}
  /* The breakpoint changes sizes and the padding, nothing else: a block stays in
     the corner it was placed in, so the arrangement reads the same on a phone as
     on a screen. The measures are in ch and capped against --fit, which is what
     keeps the two bottom corners from meeting. */
  @media (max-width:760px){
    :root{--pad:16px}
    __TYPECSS_SMALL__
  }
  .lens{position:fixed;left:0;top:0;width:var(--lens,100px);height:var(--lens,100px);border-radius:50%;background:#8A8A8A;filter:blur(var(--feather,8px));
    mix-blend-mode:difference;pointer-events:none;z-index:100;transform:translate(-1000px,-1000px);will-change:transform;display:none}
  @media (hover:hover) and (pointer:fine){.lens{display:block}}

</style>'''

LEC_CSS = '''/* The lecture blocks. One per segment of the spine, parked at the middle of
     its own segment and laid alongside it. Nothing about them is in the spine:
     the block is placed by a fraction of the spine\'s height, so it follows the
     spine through every size it takes.

     WHEN THEY ARE SEEN IS ALL IN ONE PLACE — the `.lec.on` rule. A block is
     `on` while its segment is hovered or open, and nothing else turns it on:
     a state the reader cannot see the cause of is a state they cannot dismiss. */
  .stage{position:relative;width:calc(__COLS__ * var(--cell))}
  :root{--lec-in:.42s; --lec-out:.26s}
  .lecs{position:absolute;inset:0;pointer-events:none;
    /* room the spine leaves on one side, which is what a block has to live in */
    --side:calc((100vw - var(--tools,0px) - __COLS__ * var(--cell)) / 2);
    --lec-gap:2.2vw;      /* between the spine and the block */
    --lec-rise:10px;      /* how far a block travels as it arrives */
    --lec-lead:7px}
  .lec{position:absolute;left:100%;margin-left:var(--lec-gap);
    top:calc(var(--y) * 100%);
    width:max(18ch, min(34ch, calc(var(--side) - var(--lec-gap) - var(--pad))));
    opacity:0;transform:translateY(calc(-50% + var(--lec-rise)));
    transition:opacity var(--lec-out) ease, transform var(--lec-out) ease}
  .lec>*+*{margin-top:var(--lec-lead)}
  .lec .t{max-width:100%}
  .lec .t>*{max-width:100%}
  .lec.on{opacity:1;transform:translateY(-50%);
    transition-duration:var(--lec-in),var(--lec-in)}
  /* Not enough room beside the spine any more: the block lies over it, from the
     left edge of the spine, where the segment\'s photo is its ground. */
  @media (max-width:1100px){
    .lecs{--lec-gap:0px}
    .lec{left:0;margin-left:0;width:min(34ch,100%)}
  }'''


BODY = '''
<div class="bg"></div>
<div class="grid"></div>
<div class="lens" id="lens"></div>
<div class="poster">
__CORNERS__
</div>
<div class="grain"></div>
<main id="content">
<div class="stage">
__SPINE__
<div class="lecs">
__LECS__
</div>
</div>
<script>
  // A segment has two states and its lecture block reads both: hovered, and
  // open (clicked, and it stays open until something else is). The script only
  // ever sets the classes; when a class is worth seeing is CSS.
  (function(){
    const segs=[...document.querySelectorAll('.seg')];
    const lecs=segs.map((g,i)=>document.querySelector('.lec[data-lec="'+i+'"]'));
    let hot=-1, open=-1;
    function sync(){segs.forEach((g,i)=>{
      g.classList.toggle('active',i===open);
      g.classList.toggle('hot',i===hot);
      const l=lecs[i];if(!l)return;
      l.classList.toggle('on',i===hot||i===open);});}
    // Opening a segment brings it to the middle of the screen. Only a click does
    // this — a hover that moved the page would move itself out from under the
    // cursor. The scroll is its own tween because scrollIntoView's smooth scroll
    // has neither a duration nor a curve to set, and the point here is slowness.
    const GLIDE=900, DEAD=24;   // ms end to end; px already near enough to leave alone
    // Starts slow, arrives slow. For a pure ease-in, swap in t=>t*t*t.
    const EASE=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
    const still=matchMedia('(prefers-reduced-motion: reduce)');
    let tween=null;
    function glide(g){
      const b=g.getBoundingClientRect();
      const to=Math.max(0,Math.min(scrollY+(b.top+b.bottom)/2-innerHeight/2,
                                   document.documentElement.scrollHeight-innerHeight));
      const from=scrollY,d=to-from;
      if(Math.abs(d)<DEAD)return false;   // nothing moved, so nothing to hold
      if(still.matches){scrollTo(0,to);return true;}
      const t0=performance.now(),id={};tween=id;
      (function step(now){
        if(tween!==id)return;               // the reader took the scroll back
        const k=Math.min(1,(now-t0)/GLIDE);
        scrollTo(0,from+d*EASE(k));
        k<1?requestAnimationFrame(step):tween=null;})(t0);
      return true;
    }
    // Hover is read from where the pointer actually is — not from enter/leave on
    // the segments. While the page glides, the spine slides under a cursor that
    // is standing still; the browser queues the boundary events that causes and
    // delivers them on the next real move, interleaved with it, so a late enter
    // could light a segment the cursor had already left and no leave ever came
    // to undo it. One hit test at the last real pointer position cannot go stale.
    //
    // And from the click until the reader moves for real the choice is HELD: the
    // page went there, the reader did not, so nothing under the cursor counts.
    let held=false,px=-1,py=-1,queued=false;
    const at=(x,y)=>{const e=document.elementFromPoint(x,y),g=e&&e.closest&&e.closest('.seg');
      return g?segs.indexOf(g):-1;};
    // a hit test per pointermove is a hit test per mouse report; once a frame is
    // as often as it can be seen.
    function look(){queued=false;const i=at(px,py);if(i!==hot){hot=i;sync();}}
    addEventListener('pointermove',e=>{
      if(held&&Math.hypot(e.clientX-px,e.clientY-py)<=3)return;   // the glide's own
      held=false;px=e.clientX;py=e.clientY;
      if(!queued){queued=true;requestAnimationFrame(look);}},{passive:true});
    addEventListener('pointerleave',()=>{held=false;px=py=-1;
      if(hot!==-1){hot=-1;sync();}});
    ['wheel','touchstart','keydown'].forEach(e=>
      addEventListener(e,()=>{tween=null;held=false;},{passive:true}));
    segs.forEach((g,i)=>{
      g.addEventListener('click',e=>{open=(open===i?-1:i);hot=i;sync();
        if(open===i){px=e.clientX;py=e.clientY;held=glide(g);}
        e.stopPropagation();});
    });
    // A click outside closes everything, and it says where the pointer is:
    // a click does not have to be preceded by a move, so its own coordinates
    // are the only ones that are certainly current.
    document.addEventListener('click',e=>{open=-1;held=false;
      px=e.clientX;py=e.clientY;look();sync();});
    sync();
  })();
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

# The copy, as plain text. A blank line starts a paragraph, a single newline is a
# line break — one rule, so the tools panel can hand the same text back and the
# export pastes straight in here.
COPY = dict(
    title='Spinal\nMemory',
    tag='research and practice\non non-human animals',
    info='online lectures\n5 weeks\noct 10 ~ nov 7, 2026\n9am edt / 9PM cst',
    desc='Spinal Memory, the fourth issue of te magazine, grew out of a reflection on '
         'the imagining of non-human animals. As an extension of this issue\u2019s theme, te '
         'editions is launching its first online lecture series, inviting nine speakers '
         '(including several contributors to this issue) to give eight online lectures.'
         '\n\n'
         'Each speaker approaches this theme in a completely different way: years of '
         'companionship and careful field observation, or history, design, writing, '
         'moving image, archives, and data.',
)


# tag -> the element each role's copy is wrapped in. The logo is a drawing, the
# description is two paragraphs, so neither is a single text element.
ROLE_TAG = dict(logo='div', title='h1', tag='p', info='p', desc='div',
                lecn='p', lect='p', lecb='div')


def copy_html(role, text):
    """Plain text in, markup out. Only the roles wrapped in a div can hold
    paragraphs; the rest are a single text element, so every newline is a break."""
    paras = [p for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    br = lambda p: '<br>'.join(line for line in p.split('\n'))
    if ROLE_TAG[role] == 'div':
        return ''.join(f'<p>{br(p)}</p>' for p in paras)
    return '<br>'.join(br(p) for p in paras)


def corners():
    """One div per corner that has anything in it, holding its roles in order."""
    out = []
    for corner in CORNERS:
        roles = at_corner(corner)
        if not roles:
            continue
        inner = ''.join(
            layers(ROLE_TAG[r], r, LOGO, **{'aria-label': 'te'}) if r == 'logo'
            else layers(ROLE_TAG[r], r, copy_html(r, COPY[r])) for r in roles)
        out.append(f'  <div class="{corner}">{inner}</div>')
    return '\n'.join(out)


def lectures_html():
    """One block per segment, parked at the middle of its own segment's band.

    spine.py records each segment's extent in viewBox units, so the block is
    placed as a fraction of the spine's height and follows it through every
    size the spine takes. Nothing here says when a block is seen — that is the
    .lec rules and the script, so the copy and the choreography stay apart."""
    height = float(re.search(r'viewBox="0 0 [\d.]+ ([\d.]+)"', SPINE).group(1))
    bands = [(float(a), float(b)) for a, b in
             re.findall(r'<g class="seg"[^>]*data-y0="(-?[\d.]+)" data-y1="(-?[\d.]+)"', SPINE)]
    out = []
    for i, lec in enumerate(LECTURES[:len(bands)]):
        y0, y1 = bands[i]
        mid = (y0 + y1) / 2 / height
        head = f"{i + 1:02d} \u00b7 {lec['when']}\n{lec['who']}"
        out.append(
            f'<div class="lec" data-lec="{i}" style="--y:{mid:.4f}">'
            + layers('p', 'lecn', copy_html('lecn', head))
            + layers('p', 'lect', copy_html('lect', lec['what']))
            + layers('div', 'lecb', copy_html('lecb', lec['about']))
            + '</div>')
    return '\n'.join(out)


TOOLS_CSS = '.tools{position:fixed;right:0;top:0;bottom:0;z-index:200;width:272px;overflow:auto;\n    background:#141614;color:#ECEEE9;font:11px/1.4 var(--font-sans);letter-spacing:.04em;\n    padding-bottom:18px;display:none}\n  .tools.on{display:block}\n  html.has-tools{--tools:272px}\n  .tools h3{margin:0;padding:8px 12px;font-size:10px;font-weight:600;letter-spacing:.14em;\n    text-transform:uppercase;background:#1D201D;color:#9BA39A;position:sticky;top:0}\n  .tools section{padding:7px 12px;border-bottom:1px solid #2A2E2A;display:grid;gap:5px}\n  .tools .f{display:grid;grid-template-columns:1fr 4.4em;gap:7px;align-items:center}\n  .tools label{color:#C8D4C2}\n  .tools input,.tools select{background:#0D0F0D;border:1px solid #2A2E2A;color:#ECEEE9;\n    font:inherit;padding:3px 4px;border-radius:3px;width:100%}\n  .tools input[type=number]{text-align:right}\n  .tools input[type=range]{grid-column:1/-1;accent-color:#C8D4C2;padding:0;border:0}\n  .tools textarea{width:100%;height:220px;background:#0D0F0D;color:#C8D4C2;\n    border:1px solid #2A2E2A;border-radius:3px;font:10px/1.45 ui-monospace,Menlo,monospace;\n    padding:6px;resize:vertical}\n  .tools .hint{color:#6E766C;font-size:9.5px;line-height:1.35}'


PANEL_JS = '(function(){\n  if(!/[?&]tools/.test(location.search)) return;\n  const D = __DATA__;\n  D.order = Object.keys(D.roles);\n  const panel = document.getElementById(\'tools\');\n  panel.classList.add(\'on\');\n  document.documentElement.classList.add(\'has-tools\');\n\n  const $ = (t, a = {}, kids = []) => {\n    const el = document.createElement(t);\n    for (const k in a) k === \'text\' ? el.textContent = a[k] : el.setAttribute(k, a[k]);\n    kids.forEach(c => el.appendChild(c));\n    return el;\n  };\n  const field = (box, label, input) => {\n    box.appendChild($(\'div\', {class: \'f\'}, [$(\'label\', {text: label}), input]));\n    return input;\n  };\n  const num = (v, min, max, step) => $(\'input\', {type: \'number\', value: v, min, max, step});\n  const slider = (box, v, min, max, step) => {\n    const r = $(\'input\', {type: \'range\', min, max, step, value: v});\n    box.appendChild(r); return r;\n  };\n  const pick = (v, opts) => {\n    const sel = $(\'select\');\n    opts.forEach(o => {\n      const opt = $(\'option\', {value: o});\n      opt.textContent = o;\n      if (o === v) opt.selected = true;\n      sel.appendChild(opt);\n    });\n    return sel;\n  };\n\n  // The same rule as copy_html in build.py: a blank line starts a paragraph, a\n  // single newline is a break, and only the div-wrapped roles take paragraphs.\n  function copyHtml(role, text) {\n    const esc = t => t.replace(/&/g, \'&amp;\').replace(/</g, \'&lt;\').replace(/>/g, \'&gt;\');\n    const paras = text.trim().split(/\\n\\s*\\n/).filter(p => p.trim());\n    const br = p => p.split(\'\\n\').map(esc).join(\'<br>\');\n    return D.tag[role] === \'div\'\n      ? paras.map(p => \'<p>\' + br(p) + \'</p>\').join(\'\')\n      : paras.map(br).join(\'<br>\');\n  }\n  function setCopy(role) {\n    const el = document.querySelector(\'.t-\' + role);\n    if (!el) return;\n    const html = copyHtml(role, D.copy[role]);\n    [...el.children].forEach(layer => layer.innerHTML = html);\n  }\n\n  // The one place a role\'s numbers reach the page. Corners are re-filled in the\n  // declared order so moving one role never reshuffles the others.\n  function apply() {\n    D.order.forEach(role => {\n      const r = D.roles[role], st = D.steps[r.step], c = D.sets[r.set];\n      const el = document.querySelector(\'.t-\' + role);\n      if (!el) return;\n      const s = el.style;\n      s.setProperty(\'--fs\', st.size[0] + \'px\');\n      s.setProperty(\'--soft\', st.soft + \'px\');\n      s.setProperty(\'--glowR\', st.glow + \'em\');\n      s.setProperty(\'--bloomR\', st.bloom + \'px\');\n      s.setProperty(\'--ink\', c.ink);\n      s.setProperty(\'--glow\', c.glow);\n      s.setProperty(\'--bloom\', c.bloom);\n      s.setProperty(\'--gap\', (r.gap || 0) + \'px\');\n      s.setProperty(\'--maxw\', r.width ? r.width + \'ch\' : \'var(--fit)\');\n    });\n    D.corners.forEach(corner => {\n      const box = document.querySelector(\'.\' + corner);\n      if (!box) return;\n      D.order.filter(role => D.roles[role].at === corner)\n             .forEach(role => box.appendChild(document.querySelector(\'.t-\' + role)));\n    });\n  }\n\n  Object.entries(D.roles).forEach(([role, r]) => {\n    panel.appendChild($(\'h3\', {text: role}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n\n    field(box, \'字号档\', pick(r.step, Object.keys(D.steps)))\n      .onchange = e => { r.step = e.target.value; apply(); dump(); };\n    field(box, \'位置\', pick(r.at, D.corners))\n      .onchange = e => { r.at = e.target.value; apply(); dump(); };\n    field(box, \'配色\', pick(r.set, Object.keys(D.sets)))\n      .onchange = e => { r.set = e.target.value; apply(); dump(); };\n\n    const g = field(box, \'上方间距 px\', num(r.gap || 0, 0, 160, 2));\n    const gr = slider(box, r.gap || 0, 0, 160, 2);\n    const setGap = v => { r.gap = +v; g.value = v; gr.value = v; apply(); dump(); };\n    g.oninput = e => setGap(e.target.value);\n    gr.oninput = e => setGap(e.target.value);\n\n    if (role in D.copy) {\n      box.appendChild($(\'div\', {class: \'hint\', text: \'文案：空行分段，单个换行是换行\'}));\n      const ta = document.createElement(\'textarea\');\n      ta.value = D.copy[role];\n      ta.rows = role === \'desc\' ? 8 : 4;\n      ta.spellcheck = false;\n      ta.style.cssText = \'height:auto;font:10px/1.5 var(--font-sans)\';\n      box.appendChild(ta);\n      ta.oninput = () => { D.copy[role] = ta.value; setCopy(role); dump(); };\n    }\n\n    const w = field(box, \'宽度 ch · 0=不限\', num(r.width || 0, 0, 90, 1));\n    const wr = slider(box, r.width || 0, 0, 90, 1);\n    const setW = v => { r.width = +v; w.value = v; wr.value = v; apply(); dump(); };\n    w.oninput = e => setW(e.target.value);\n    wr.oninput = e => setW(e.target.value);\n  });\n\n  panel.appendChild($(\'h3\', {text: \'页边距\'}));\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue(\'--pad\'));\n    const p = field(box, \'--pad px\', num(cur, 8, 96, 2));\n    const pr = slider(box, cur, 8, 96, 2);\n    const setPad = v => {\n      document.documentElement.style.setProperty(\'--pad\', v + \'px\');\n      p.value = v; pr.value = v; dump();\n    };\n    p.oninput = e => setPad(e.target.value);\n    pr.oninput = e => setPad(e.target.value);\n  }\n\n  panel.appendChild($(\'h3\', {text: \'导出 · 贴回 build.py\'}));\n  const out = $(\'textarea\', {readonly: \'\', spellcheck: \'false\'});\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    box.appendChild(out);\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'面板只改这一页，刷新就回到 build.py 里的值。\' +\n      \'把上面这段贴回 ROLES 才算定下来。\'}));\n  }\n\n  function dump() {\n    const q = s => "\'" + s + "\'";\n    const lines = D.order.map(role => {\n      const r = D.roles[role];\n      const bits = [\'at=\' + q(r.at), \'step=\' + q(r.step), \'set=\' + q(r.set)];\n      if (r.gap) bits.push(\'gap=\' + r.gap);\n      if (r.width) bits.push(\'width=\' + r.width);\n      [\'weight\', \'ls\', \'lh\'].forEach(k => { if (k in r) bits.push(k + \'=\' + r[k]); });\n      return \'    \' + role + \'=dict(\' + bits.join(\', \') + \'),\';\n    });\n    const py = s => "\'" + s.replace(/\\\\/g, \'\\\\\\\\\').replace(/\'/g, "\\\\\'")\n      .replace(/\\n/g, \'\\\\n\') + "\'";\n    const copy = Object.keys(D.copy).map(k => \'    \' + k + \'=\' + py(D.copy[k]) + \',\');\n    out.value = \'ROLES = dict(\\n\' + lines.join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'COPY = dict(\\n\' + copy.join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'--pad: \' + getComputedStyle(document.documentElement).getPropertyValue(\'--pad\').trim();\n  }\n\n  apply(); dump();\n})();\n'


def tools_panel():
    """A side panel for placing and sizing the roles. It appears on ?tools only —
    the poster itself should not ship a dev panel. It edits the same three tables
    the build reads, and prints ROLES back as Python to paste into this file."""
    data = json.dumps(dict(steps=STEPS, roles=ROLES, sets=COLOUR_SETS,
                           corners=list(CORNERS), copy=COPY, tag=ROLE_TAG),
                      ensure_ascii=False)
    return ('<aside class="tools" id="tools"></aside>\n<script>'
            + PANEL_JS.replace('__DATA__', data) + '</script>')


def page(inline, spine=None, cols=None, rows=None, tools=False):
    spine = SPINE if spine is None else spine
    cols = SPINE_COLS if cols is None else cols
    rows = SPINE_ROWS if rows is None else rows
    grain = grain_url()
    return (HEAD.replace('__FONTS__', font_faces(inline))
                .replace('__TYPEBASE__', TYPE_CSS)
                .replace('__TOOLSCSS__', TOOLS_CSS if tools else '').replace('__TYPECSS__', type_css())
                .replace('__TYPECSS_SMALL__', type_css_small())
                .replace('__LECCSS__', LEC_CSS)
                .replace('__GRAINURL__', grain).replace('__GRAINA__', str(GRAIN['opacity']))
                .replace('__GRAINSIZE__', f"{GRAIN['cell'] * 40:g}px")
                .replace('__COLS__', f'{cols:g}').replace('__ROWS__', str(rows))
            + BODY.replace('__SPINE__', spine).replace('__LECS__', lectures_html()).replace('__CORNERS__', corners())
            + (tools_panel() if tools else ''))


repo_doc = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + page(False, tools=True).replace('</style>', '</style>\n</head>\n<body>', 1) + '</body>\n</html>\n')
open(os.path.join(REPO, 'index.html'), 'w').write(repo_doc)
# the artifact is the poster itself, fonts inlined
art = page(True)
open(os.path.join(REPO, 'artifact.html'), 'w').write(art)
print(f'index.html {len(repo_doc)//1024} KB ({SPINE_COLS:g}x{SPINE_ROWS}) · '
      f'artifact.html {len(art)//1024} KB')
