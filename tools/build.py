#!/usr/bin/env python3
"""Build index.html (repo, file fonts) and artifact.html (inline fonts) from parts."""
import base64, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SPINE = open(os.path.join(HERE, 'spine.seg.part')).read()
import json, re
PRESETS_PATH = os.path.join(HERE, 'presets.json')
PRESETS = json.load(open(PRESETS_PATH)) if os.path.exists(PRESETS_PATH) else None
FONT_FAMILY = {'apoc': 'var(--font-display)', 'pp': 'var(--font-sans)', 'cn': 'var(--font-cn)'}
FONT_ITALIC = {'apoc': 'axis', 'pp': 'style', 'cn': None}

def noise_url(n):
    r, g, b = [int(n['color'][i:i+2], 16) / 255 for i in (1, 3, 5)]
    freq = f"{0.8 / max(0.05, n['size']):.2f}"
    d = n['density'] / 100; slope = f"{1.2 + d * 1.2:.2f}"; off = f"{-(1 - d) * 0.55:.2f}"
    return (f"url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'>"
            f"<feTurbulence type='fractalNoise' baseFrequency='{freq}' numOctaves='1' stitchTiles='stitch'/>"
            f"<feColorMatrix values='0 0 0 0 {r:.2f}  0 0 0 0 {g:.2f}  0 0 0 0 {b:.2f}  0 0 0 {slope} {off}'/></filter>"
            f"<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")")

def preset_css():
    if not PRESETS: return ''
    n = PRESETS['noise']
    css = [f".fx .n{{background-image:{noise_url(n)};background-size:80px 80px;opacity:{n['opacity']/100}}}"]
    for key in PRESETS.get('order', PRESETS['presets'].keys()):
        p = PRESETS['presets'][key]; f = p['font']
        slug = re.sub(r'[^a-z0-9]+', '-', p['name'].lower()).strip('-')
        sel = f".fx-{f}-{slug}"
        ital = (f'font-variation-settings:"ital" {p.get("ital",0)};' if FONT_ITALIC[f] == 'axis'
                else ('font-style:italic;' if FONT_ITALIC[f] == 'style' and p.get('italicOn') else ''))
        css.append(f"{sel}{{font-family:{FONT_FAMILY[f]};font-size:{p['size']}px;font-weight:{p['weight']};line-height:{p['lh']};letter-spacing:{p['ls']}em;{ital}}}")
        for i, l in enumerate(p['layers'], 1):
            if not l['on']: css.append(f"{sel} .l{i}{{display:none}}"); continue
            blur = f"filter:blur({l['blur']/2:.2f}px);" if l['blur'] else ''
            stroke = f"-webkit-text-stroke:{l['stroke']*2}px {l['strokeColor']};" if l['stroke'] else '-webkit-text-stroke:0;'
            css.append(f"{sel} .l{i}{{z-index:{7-i};opacity:{l['opacity']/100};{blur}}}")
            css.append(f"{sel} .l{i} .t{{color:{l['fill'] or 'transparent'};{stroke}}}")
            css.append(f"{sel} .l{i} .n{{display:{'block' if l['noise'] else 'none'}}}")
    return '\n  '.join(css)

FX_BASE_CSS = '''.fx{position:relative;display:inline-block;white-space:nowrap}
  .fx .l{position:absolute;inset:0}
  .fx .l:first-child{position:relative}
  .fx .l>span{display:block}
  .fx .n{position:absolute;inset:0;color:transparent;-webkit-background-clip:text;background-clip:text}
  .fx .t{paint-order:stroke fill}'''
FX_JS = '''<script>
  document.querySelectorAll('[data-fx]').forEach(el=>{const html=el.innerHTML;el.innerHTML='';
    for(let i=1;i<=6;i++){const l=document.createElement('span');l.className='l l'+i;
      l.innerHTML='<span class="t">'+html+'</span><span class="n">'+html+'</span>';el.appendChild(l);}});
</script>'''

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
    out = [f"@font-face{{font-family:'Apoc';src:{font_src('Apoc-Variable', inline)};font-weight:80 145;font-display:swap}}"]
    for n, w, s in PP:
        out.append(f"@font-face{{font-family:'PP Neue Montreal';src:{font_src('PPNeueMontreal-'+n, inline)};font-weight:{w};font-style:{s};font-display:swap}}")
    return '\n  '.join(out)

HEAD = '''<title>te online lecture</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@200;300;400;500;600;700;900&display=swap">
<style>
  __FONTS__

  :root{
    --font-cn:"Noto Serif SC","Source Han Serif CN","Source Han Serif SC","Songti SC",serif;
    --font-display:"Apoc",Georgia,serif;
    --font-sans:"PP Neue Montreal",-apple-system,"Helvetica Neue",Arial,sans-serif;
    --ink:#101410; --ink-brown:#822D00; --ink-soft:rgba(16,20,16,.7);
    --cell:12px;
  }
  @media (max-width:760px){:root{--cell:7px}}
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
  .spine{width:calc(32 * var(--cell));height:auto;overflow:visible;display:block}
  .cells rect{fill:#fff;stroke:#cccccc;stroke-width:.05;stroke-dasharray:.14 .1;shape-rendering:crispEdges}
  .glyphs text{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace;text-anchor:middle;dominant-baseline:central;pointer-events:none}
  .seg .pic{opacity:0;transition:opacity .25s ease}
  .seg:hover .pic,.seg.active .pic{opacity:1}
  .seg{cursor:pointer}
  __FXBASE__
  __FXPRESETS__
  .lens{position:fixed;left:0;top:0;width:var(--lens,100px);height:var(--lens,100px);border-radius:50%;background:#D9D9D9;filter:blur(var(--feather,2px));
    mix-blend-mode:difference;pointer-events:none;z-index:100;transform:translate(-50%,-50%);will-change:transform;display:none}
  @media (hover:hover) and (pointer:fine){.lens{display:block}}

</style>'''

BODY = '''
<div class="bg"></div>
<div class="grid"></div>
<div class="lens" id="lens"></div>
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
  addEventListener('pointermove',e=>{lens.style.transform=`translate(${e.clientX}px,${e.clientY}px) translate(-50%,-50%)`;},{passive:true});
  addEventListener('pointerleave',()=>{lens.style.transform='translate(-1000px,-1000px)';});
</script>
__FXJS__
</main>
'''

def page(inline):
    return (HEAD.replace('__FONTS__', font_faces(inline)).replace('__FXBASE__', FX_BASE_CSS).replace('__FXPRESETS__', preset_css())
            + BODY.replace('__SPINE__', SPINE).replace('__FXJS__', FX_JS))

repo_doc = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            + page(False).replace('</style>', '</style>\n</head>\n<body>', 1) + '</body>\n</html>\n')
open(os.path.join(REPO, 'index.html'), 'w').write(repo_doc)
FX = open(os.path.join(HERE, 'fx.template.html')).read()
fx_repo = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           + FX.replace('__FONTS__', font_faces(False)).replace('__SPINE__', SPINE).replace('</style>', '</style>\n</head>\n<body>', 1) + '</body>\n</html>\n')
open(os.path.join(REPO, 'fx.html'), 'w').write(fx_repo)
art = FX.replace('__FONTS__', font_faces(True)).replace('__SPINE__', SPINE)
open(os.path.join(HERE, '..', 'artifact.html'), 'w').write(art)
print('index.html', len(repo_doc)//1024, 'KB; fx.html', len(fx_repo)//1024, 'KB; artifact', len(art)//1024, 'KB')
