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
# What goes in, not what comes out: the grain over the page is an overlay, and
# an overlay with noise centred on mid-grey is the identity only in the mean --
# what clips at the top of a channel's range never comes back, so every channel
# lifts a little. These values are pre-compensated, and land on #F28532 orange
# and #FDF48E yellow once the grain is over them.
COLOUR_SETS = dict(
    a=dict(ink='#f28030', glow='#fdf48a', bloom='#fdf48a'),
    b=dict(ink='#277c3c', glow='#fdf48a', bloom='#fdf48a'),
)

# The type scale, from one step. BASE is the only text size anyone sets: every
# other one is this one resized, and what "resized" means is the whole of the
# rule below. Anything already relative — the em radii, the ratios, the
# unitless — carries over untouched. The two that must not carry over are
# tracking and leading, because type wants less of both the bigger it gets, so
# they are walked per pixel of size by TRACK and LEAD. Retune BASE and the
# whole ramp moves with it.
#
# `mark` is outside the ramp. It is a logotype at 110px, tuned on its own, and
# a rule fitted over a 12-to-20px range has nothing to say about it.
BASE = dict(soft=.9, glow=2.22, bloom=5.2, solid=.84,
            weight=400, ls=.035, lh=.92)
BASE_SIZE = 14
TRACK = .0091   # em of letter-spacing given back per px of size over the base
LEAD = .0164    # of line-height, likewise
# poster size -> the size under the 760px breakpoint, the ramp's own .857
TEXT_SIZES = dict(t20=(20, 17.1), t18=(18, 15.4), t16=(16, 13.7),
                  t14=(14, 12), t12=(12, 10.3))
MARK_STEP = dict(size=(100, 66), soft=1.92, glow=.04, bloom=9, solid=.76)
MARK_TYPE = dict(weight=400, ls=-.055, lh=.8)


def steps():
    out = dict(mark=dict(MARK_STEP))
    for name, size in TEXT_SIZES.items():
        out[name] = dict(size=size, **{k: BASE[k] for k in ('soft', 'glow', 'bloom', 'solid')})
    return out


def types():
    out = dict(mark=dict(MARK_TYPE))
    for name, size in TEXT_SIZES.items():
        d = size[0] - BASE_SIZE
        out[name] = dict(weight=BASE['weight'],
                         ls=round(BASE['ls'] - TRACK * d, 4),
                         lh=round(BASE['lh'] - LEAD * d, 3))
    return out


STEPS = steps()
TYPE = types()

# The backlight. A fourth copy of the block whose pixels are never drawn: the
# filter takes only its alpha, fattens it (dilate), lets the letters bleed into
# each other (blur) and then cuts the result at a threshold (the colour matrix),
# so what comes out is ONE SILHOUETTE OF THE WHOLE BLOCK — not a box behind the
# lines, and not an outline per glyph. That silhouette is filled flat for the
# slab, blurred again for the halo, and the halo is merged over itself `stack`
# times: the same trick as writing one box-shadow N times, alpha accumulating
# until the edge stops being a gradient and starts being a thickness.
#
# Every radius here is in em, so the base's numbers are already the whole ramp:
# a backlight tuned at 14px is the same backlight at 20. Only the mark differs,
# for the same reason it differs above.
#
# ONE COLOUR, for every backlight on the page. It is not a per-step choice and
# there is no way to make it one: eight lecture blocks and four corners lit in
# four shades of almost-the-same-yellow is not a decision anyone makes on
# purpose, it is what happens when the knob exists.
BACKLIGHT_COLOUR = '#eae5ae'
BASE_BACK = dict(dilate=.15, merge=.075, hard=6.7, halo=.41, stack=13,
                 slab=.1, glow=.14)     # slab/glow are opacities; see above
MARK_BACK = dict(dilate=.065, merge=.06, hard=2, halo=.12, stack=4,
                 slab=.66, glow=.72)


def backlight(step):
    b = dict(MARK_BACK if step == 'mark' else BASE_BACK)
    b['slab'] = (BACKLIGHT_COLOUR, b['slab'])
    b['glow'] = (BACKLIGHT_COLOUR, b['glow'])
    return b


def stack_table(n, steps=64):
    """The alpha a layer reaches after being drawn over itself n times.

    Dense on purpose: the alpha coming in is the halo's flood opacity at most,
    around .14, so the whole curve is read out of its first tenth, and a table
    coarse enough to interpolate across that tenth bands the gradient.
    """
    n = max(1, round(n))
    return ' '.join(f'{1 - (1 - k / steps) ** n:.4f}' for k in range(steps + 1))


def bl_filter(fid, step, fs):
    b = backlight(step)
    k = b['hard']
    d, g, h = b['dilate'] * fs, b['merge'] * fs, b['halo'] * fs
    return (f'<filter id="{fid}" x="-120%" y="-120%" width="340%" height="340%" '
            'color-interpolation-filters="sRGB">'
            f'<feMorphology data-bl="dilate" in="SourceAlpha" operator="dilate" radius="{d:.2f}" result="fat"/>'
            f'<feGaussianBlur data-bl="merge" in="fat" stdDeviation="{g:.2f}" result="soft"/>'
            '<feColorMatrix data-bl="hard" in="soft" type="matrix" result="sil" '
            f'values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 {k:g} {-k / 2:g}"/>'
            f'<feFlood data-bl="slab" flood-color="{b["slab"][0]}" flood-opacity="{b["slab"][1]:g}" result="sc"/>'
            '<feComposite in="sc" in2="sil" operator="in" result="slab"/>'
            f'<feGaussianBlur data-bl="halo" in="sil" stdDeviation="{h:.2f}" result="hb"/>'
            f'<feFlood data-bl="glow" flood-color="{b["glow"][0]}" flood-opacity="{b["glow"][1]:g}" result="hc"/>'
            '<feComposite in="hc" in2="hb" operator="in" result="halo0"/>'
            # Drawing the same halo N times over itself is 1-(1-a)^N on its
            # alpha and nothing else -- the colour is the same colour. So the
            # stack is a curve on one layer, not N composites of a region 11x
            # the size of the box, 45 times over. Same picture, one pass.
            f'<feComponentTransfer data-bl="stack" in="halo0" result="halo">'
            f'<feFuncA type="table" tableValues="{stack_table(b["stack"])}"/>'
            '</feComponentTransfer>'
            '<feMerge><feMergeNode in="halo"/>'
            '<feMergeNode in="slab"/></feMerge></filter>')


def backlight_defs():
    """One filter per step, plus a second one per step whose size changes under
    the breakpoint — a filter cannot read a custom property, so the small screen
    needs its own radii rather than a scaled variable."""
    out = []
    for step, st in STEPS.items():
        big, small = st['size']
        out.append(bl_filter(f'bl-{step}', step, big))
        if small != big:
            out.append(bl_filter(f'bl-{step}-s', step, small))
    return ('<svg width="0" height="0" aria-hidden="true" '
            'style="position:absolute"><defs>' + ''.join(out) + '</defs></svg>')


# Where everything sits, and the whole of what it takes to move it. `at` is one of
# the four corners; a corner stacks its roles in this order and aligns them to the
# edge it is pinned to, so the right-hand corners are right-aligned without being
# told. `gap` is the space above a role when it follows a sibling in the same
# corner. `step` names a row of STEPS, `set` a row of COLOUR_SETS. width caps the
# measure in ch so it survives a size change.
CORNERS = ('head', 'head-r', 'foot', 'foot-r')
ROLES = dict(
    logo=dict(at='head', step='mark', set='a'),
    title=dict(at='foot', step='t20', set='a'),
    tag=dict(at='foot', step='t14', set='a', gap=6, width=32),
    info=dict(at='foot', step='t16', set='a', gap=48),
    desc=dict(at='foot', step='t14', set='a', gap=48, width=19),
)


# Type that is not pinned to a corner: the lecture blocks along the spine. Same
# four-layer machinery, same steps and colour sets as the poster roles — the
# only difference is that nothing places them, the spine does.
TEXT = dict(
    lecn=dict(step='t14', set='a'),
    lect=dict(step='t20', set='a'),
    lecno=dict(step='t14', set='a'),
    lecl=dict(step='t12', set='a', gap=12),
    lecb=dict(step='t14', set='a', gap=6, width=38),
)

# One row per segment of the spine, top to bottom: segment 0 is the top vertebra.
# `when`, `who` and `lang` are one line each; `what` is the title; `about` is prose, and
# a blank line in it starts a paragraph, exactly as in COPY.
# `lang` is the line under the speaker, and belongs with the detail rather than
# the head: it is what you need once you have decided to come.
LECTURES = [
    dict(when='Oct 10', who='Victoria Soyan Peemot',
         what='Horses and Songs: Multispecies Rhythm and Voice in Inner Asia',
         lang='English',
         about='When Tyva people say that the horse is everything in life, this is not a metaphor—it comes from the lived experience of the people who have been mobile pastoralists for millennia, whose lives and identities have been continuously shaped by horses. Drawing on her personal experience and research among mobile pastoralists between the Altai and Sayan mountain ranges in the transnational region of Inner Asia, Dr. Victoria Soyan Peemot explores how Tyvan understandings of voice, sound, and music are rooted in multispecies relationships, with a particular focus on human-equine belonging. Her research brings together horses and their rich sound world with the people and land to which they co-belong. The lecture discusses how the rhythms and lyrics of Tyvan songs and Tyvan ways of understanding the human voice itself emerge from belonging to the land and cohabiting it with other beings.'),
    dict(when='Oct 11', who='Wantanee Siripattananuntakul',
         what='If There’s No Reply, Is That Silence Still Love?',
         lang='English',
         about='Wantanee Siripattananuntakul has lived with Beuys, an African grey parrot, since 2013. After more than a decade together, she has come to know Beuys’ voices, movements, routines, fears, and desires. She has also kept Beuys’ feathers, images, objects, and documents, and turned to science to learn how parrots see, hear, and navigate the world. Yet the more she knows about Beuys, the more aware she becomes of what she cannot know: what the world is like for Beuys. That distance extends beyond her relationship with Beuys into her wider artistic practice: when she reconstructs what is no longer there from what remains, traces histories she was never there to witness, or measures a distance exactly and still finds that the number cannot tell her what that distance means. Wantanee keeps looking anyway. She is no longer only asking what she can know, but what makes her think she has received an answer. What makes something an answer, and who decides? And if there is no reply, how does she know that what she calls silence is silence at all?'),
    dict(when='Oct 17', who='Terezie Štindlová',
         what='Do We Need Zoos?',
         lang='English',
         about='Do we need zoos? Why do we enjoy looking at animals? What lies behind the simple human desire to feel connected to animals? These are the questions Terezie Štindlová set out to ask through her platform ZOO Index, an open archive of visual and textual zoo related material questioning its relevance in contemporary society. In this lecture, Terezie traces the development of ZOO Index from her initial interests in Zoo design and architecture toward broader questions about human ways of relating to animals, following this thinking as it takes shape through the publication process, the collaborations behind it, and the project’s possible futures.\n\nBefore the talk, the session opens with a short excerpt from a sound piece by artist Qihang Li, an immersive soundscape originally composed for ZOO Index’s book launch in Amsterdam.'),
    dict(when='Oct 24', who='Boria Sax (Guest Moderator: Ruoyi Shi)',
         what='Stories, Poetry, and Birdsong',
         lang='English',
         about='Boria Sax has long studied how animals have moved through human culture, stories, and mythology. This lecture argues that birdsong is similar to the poetry of Dylan Thomas or John Ashbery, where there is almost no literal meaning but a great deal of suggestiveness. Human beings organize experience primarily through storytelling, which serves, among other things, to construct identities, build communities, teach lessons, and set goals. Animals from wolves to fireflies are also constantly exchanging messages. This is especially apparent in birds, for whom songs and calls are used for courtship, proclaiming territory, issuing warnings, and affirming bonds, all of which are also central motifs in the tales told by human beings. These vocalizations also resemble human stories in that they modulate their tempo for purposes such as the building or release of dramatic tension. They differ from human stories and, even more, from products of artificial intelligence in that they are profoundly dependent on context.\n\nThe lecture will be joined by artist Ruoyi Shi as guest moderator.'),
    dict(when='Oct 25', who='Robert Zhao Renhui',
         what='Seeing Forest: Encounters, Evidence and Ways of Knowing',
         lang='English',
         about='How do we come to know a forest through the encounters we have within it? Similar questions extend across Robert Zhao Renhui’s practice: what can we know from what we observe and document, and how much can such evidence really tell us? In this lecture, Robert shares the fieldwork and artistic processes behind his investigations into Singapore’s secondary forests. Moving between the Institute of Critical Zoologists which he founded in 2018 and his project *Seeing Forest*, he traces how repeated visits, camera observations and found objects become photographs, moving images, installations and publications. Through stories from the field, this lecture reflects on what images reveal, what remains uncertain, and how sustained attention can change our understanding of the lives and histories that make up a place.'),
    dict(when='Oct 31', who='Oscar Salguero',
         what='The Rhizomatic Archive: Interspecies Library',
         lang='English',
         about='Interspecies Library is an independent archive launched in a Brooklyn apartment in 2019, as an experiment in mapping a growing, species-wide fascination with more-than-human worlds. In this lecture, founder and curator Oscar Salguero traces the story of this living archive, from informal salon-style gatherings to large-scale gallery exhibitions, original book commissions and limited editions, and, more recently, collaborations to develop an itinerant version of the library that brings these works into new environments and cross-pollinating dialogues. Today, the archive stewards over 500 volumes by international artists and independent presses, documenting how the book, an ancient human technology, continues to serve as a portal to imagining and embodying shared fungal, bacterial, plant, animal, and viral futures.'),
    dict(when='Nov 7', who='许哲瑜 Hsu Che-Yu & 陈琬尹 Chen Wan-Yin',
         what='Specimen of Suffering',
         lang='Chinese (with real-time Translated Captions via Zoom)',
         about='This lecture moves from a mallard at Natural History Museum Rotterdam, killed after flying into a glass panel, to the Przewalski’s horses of Mongolia; from the Nazi-era attempt to breed back the extinct Tarpan, to the beasts executed at Taipei Yuan-Shan Zoo during wartime; and on to the pathological specimens held at Amsterdam’s Museum Vrolik—research the artist has pursued across moving image, writing, archival research, and near-forensic methodologies. Their works keep asking: how do specimens reconstruct memory? How do they conceal historical violence, or become monuments to their own suffering? This lecture invites us to reconsider how museums, science, and political ideology shape the stories behind these specimens. Beyond this, Hsu and Chen will also discuss the research behind their essay *Suffering and the Specimen*, and drawing on their own works, to trace how these histories move between fieldwork, archival material, and working method.'),
    dict(when='Nov 8', who='沙爽 Sha Shuang',
         what='Writing a Cow: From Surveillance Data to Fiction',
         lang='Chinese (with real-time Translated Captions via Zoom)',
         about='Every cow on the farm has its own number. How much it eats, how far it walks, when it goes into heat, how much milk it gives—all of it is quietly logged by the machines. In 2021, Sha Shuang spent six months at an animal-monitoring data company in Xundian, Yunnan, working alongside a team of programmers. Months of fieldwork left her with a realization: the production system of a cattle farm and human social life aren’t so different after all—both made of bodies, labor, reproduction, care, and the daily experience of being logged and managed by one system or another. Her essay *Finding the Steppes* grew directly out of these field experiences. This lecture begins with that piece of semi-fiction, tracing why she moved from “monitoring cows” to “writing cows,” and how years of fieldwork among dairy cows, grasslands, milk, data, and ecological systems slowly found their way into her art practice.'),
]


def at_corner(corner):
    """The roles pinned to one corner, in the order they are declared."""
    return [r for r in ROLES if ROLES[r]['at'] == corner]


# Paint order, back to front. `core` is the same letterform as `ink` with no
# blur on it, laid over the top: `ink`'s blur never reaches full opacity on a
# stroke narrower than about four times its radius, so at 14px the yellow under
# it came through and the stroke's middle read #f5933f instead of the orange it
# was given. The blurred copy is now only the fringe; the middle is the colour.
LAYERS = ('slab', 'bloom', 'tight', 'ink', 'core')

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
             f"--solid:{st.get('solid', 1)}",
             f"--fs:{st['size'][0]}px", f"--soft:{st['soft']}px",
             f"--glowR:{st['glow']}em", f"--bloomR:{st['bloom']}px",
             f"--slabF:url(#bl-{r['step']})"]
        t = TYPE.get(r['step'])
        if t:
            v += [f"--w:{t['weight']}", f"--ls:{t['ls']}em", f"--lh:{t['lh']}"]
        if 'width' in r:
            v += [f"--maxw:{r['width']}ch"]
        if r.get('gap'):
            v += [f"--gap:{r['gap']}px"]
        out.append(f".t-{role}{{{';'.join(v)}}}")
    return '\n  '.join(out)


def type_css_small():
    """The breakpoint only moves font sizes. Every radius is absolute except the
    tight glow, which is in em and follows on its own."""
    return ''.join(f".t-{role}{{--fs:{STEPS[r['step']]['size'][1]}px;"
                   f"--slabF:url(#bl-{r['step']}-s)}}"
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
  /* Only the first layer is in flow; the other three are laid over it, so the
     box is the size of the text and the light spills outside it. */
  .t>*+*{position:absolute;inset:0}
  /* The layers must agree to the pixel, and a paragraph's own margin is enough
     to break that: the in-flow layer lets it collapse THROUGH, while the three
     absolute ones are block formatting contexts and keep it inside, so their
     text lands a whole margin lower than the slab drawn behind it. Zero it here
     — on every layer at once — and say what the gap between paragraphs is. */
  .t>*>p{margin:0}
  .t>*>p+p{margin-top:.75em}
  /* The slab's own pixels are thrown away — the filter keeps nothing but its
     alpha and returns the silhouette. Hence the flat black: it is never seen. */
  .t .slab{color:#000;filter:var(--slabF)}
  .t .bloom{color:var(--bloom);filter:blur(var(--bloomR));opacity:1}
  .t .tight{color:transparent;
    text-shadow:0 0 calc(var(--glowR) * .35) var(--glow), 0 0 var(--glowR) var(--glow)}
  .t .ink{filter:blur(var(--soft))}
  .t .core{color:var(--ink);opacity:var(--solid)}
  /* text-shadow does nothing to an SVG, so the mark's tight glow is a pair of
     drop-shadows, and the layer needs a fill for them to have any alpha to cast. */
  .t-logo{line-height:0}
  .t-logo svg{height:var(--fs);width:auto;display:block;overflow:visible}
  .t-logo .slab svg{fill:#000}
  .t-logo .bloom svg{fill:var(--bloom);filter:blur(var(--bloomR));opacity:1}
  .t-logo .tight svg{fill:var(--glow);
    filter:drop-shadow(0 0 calc(var(--glowR) * .35) var(--glow)) drop-shadow(0 0 var(--glowR) var(--glow))}
  .t-logo .ink svg{fill:var(--ink);filter:blur(var(--soft))}
  .t-logo .core{opacity:var(--solid)}
  .t-logo .core svg{fill:var(--ink)}'''


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
  /* Three drawings in one place. The base is the 9,300 elements that never
     change, so it gets a layer of its own and is rasterised once; the two
     above hold the only things that move. Neither takes the pointer, so a
     hit test still lands on the cells in the base. */
  .spine{width:calc(__COLS__ * var(--cell));height:auto;overflow:visible;display:block}
  .spine.base{will-change:transform}
  .spine.anim,.spine.pics{position:absolute;left:0;top:0;pointer-events:none}
  .cells rect{stroke:#cccccc;stroke-width:.05;stroke-dasharray:.14 .1;shape-rendering:crispEdges}
  .glyphs{--gfs:1.57px;--gdy:0.41px}
  .glyphs text{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace;font-size:var(--gfs);text-anchor:middle;dominant-baseline:auto;transform:translateY(var(--gdy));pointer-events:none}
  .glyphs text.h{font-family:"Noto Sans Egyptian Hieroglyphs",sans-serif;font-size:1.5px;dominant-baseline:central;transform:none}
  /* The photo left the segment for a layer of its own, so it is lit by its
     own class now rather than by the segment's. Fading it there no longer
     touches the drawing underneath it. */
  .pic{opacity:0;transition:opacity var(--lec-out,.26s) ease}
  /* `on` is hover-or-open as the script sees it. Not the same as :hover —
     after a click glides the spine under a still cursor, nothing is hovered
     until the reader moves, and :hover cannot be told that. */
  .pic.on{opacity:1}
  .seg{cursor:pointer}
  __TYPEBASE__
  __TOOLSCSS__
  __TYPECSS__
  __LECCSS__
  :root{--pad:24px}
  /* --tools is the width the side panel takes when it is open, so the stage
     gives way and the right-hand corners stay visible. */
  .poster{position:fixed;inset:0 var(--tools,0) 0 0;z-index:3;pointer-events:none;padding:var(--pad)}
  /* Nothing in the corners changes after load, but a filtered element gets
     re-rasterised whenever anything forces it to, and two things force it
     every frame: the lens blending against what is under it, and the grain
     blending over that. A blended element has to be composited against its
     backdrop, and a backdrop that is not a layer of its own is redrawn to
     provide one. Giving each corner its own layer means the filter runs once
     and what it produced is pasted from then on. ?nocache takes it back off. */
  .poster>*{position:absolute;pointer-events:auto;width:max-content;margin:0;
    will-change:transform}
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
  /* in: how fast a block arrives. out: how fast the photo under it leaves.
     The type does not leave — it cuts, so releasing a segment gives the poster
     straight back rather than holding a fading ghost of the last one. */
  :root{--lec-in:.24s; --lec-out:.26s; --lec-off:0s}
  .lecs{position:absolute;inset:0;pointer-events:none;
    /* room the spine leaves on one side, which is what a block has to live in */
    --side:calc((100vw - var(--tools,0px) - __COLS__ * var(--cell)) / 2);
    --lec-gap:48px;       /* between the spine and the block */
    --lec-rise:10px;      /* how far a block travels as it arrives */
    --lec-lead:8px;
    --lec-halo:26px}   /* how far the type's glow reaches past its box */
  /* Every block starts on the same vertical line. That line is the widest the
     spine ever gets, not the width of this segment, so a narrow vertebra does
     not pull its block inboard of the others and the eight left edges stack. */
  /* The head straddles the segment's centre of mass, so three lines of type sit
     level with the middle of the shape they name. .more is taken out of the
     flow below it, which is what keeps the head still while the detail opens:
     the block's own height is the head's height and nothing else. */
  .lec{position:absolute;left:100%;margin-left:var(--lec-gap);
    top:calc(var(--y) * 100%);
    width:max(18ch, min(38ch, calc(var(--side) - var(--lec-gap) - var(--pad))));
    opacity:0;transform:translateY(calc(-50% + var(--lec-rise)));
    transition:opacity var(--lec-off), transform var(--lec-off);
    /* Seven of these eight are always invisible, and opacity:0 does not stop
       a thing being rendered -- it is rasterised in full and then composited
       at zero. Which meant the page drew every word of all eight blurbs,
       five times over, three of those blurred, to show one of them. */
    content-visibility:hidden}
  /* The detail is the click's half of the bargain. It is laid out either way,
     so opening one does not reflow the block around it -- only its height and
     its ink change, and the block stays centred on its own segment throughout. */
  /* The detail is back in the flow, so the block's height is head plus detail
     and translateY(-50%) keeps the WHOLE thing level with the segment however
     much of it is showing.

     Which rules out the usual 0fr -> 1fr reveal: overflow's clip box and the
     box that height is measured from are the same box, so the room the glow
     needs is room the layout would count too (and padding on a clipped box
     cannot collapse to zero at all). clip-path is the way out -- it takes
     negative insets, so it reaches past the box on three sides and never
     touches a letter, while only the bottom edge sweeps down as it opens.
     --more-h is the detail's natural height, measured once the fonts land. */
  .lec .more{height:0;opacity:0;
    clip-path:inset(calc(-1 * var(--lec-halo)) calc(-1 * var(--lec-halo)) 0);
    transition:height var(--lec-off), opacity var(--lec-off),
               clip-path var(--lec-off)}
  .lec.open .more{height:var(--more-h, auto);opacity:1;
    clip-path:inset(calc(-1 * var(--lec-halo)));
    transition-duration:var(--lec-in),var(--lec-in),var(--lec-in)}
  /* --lec-lead is the block's own rhythm; a role's --gap is what the panel adds
     on top of it, the same knob that spaces the roles in the corners. The
     detail's first line takes only its gap: its distance from the title above
     is already .more's lead. */
  .lec .more-in>*+*{margin-top:calc(var(--lec-lead) + var(--gap,0px))}
  .lec .more-in>:first-child{margin-top:var(--gap,0px)}
  /* Each line's glow spills onto the line under it, and in document order the
     one underneath paints last and washes over the one above. Reversed: the
     first line keeps its edges and every glow falls behind what came before.
     .more carries a clip-path, so it is its own stacking context and the two
     inside it order among themselves. */
  .lec>*,.lec .more-in>*{position:relative}
  .lec>:nth-child(1){z-index:3}
  .lec>:nth-child(2){z-index:2}
  .lec>:nth-child(3){z-index:1}
  .lec .more-in>:nth-child(1){z-index:2}
  .lec .more-in>:nth-child(2){z-index:1}
  .lec>*+*{margin-top:calc(var(--lec-lead) + var(--gap,0px))}
  /* The numbers sit on the spine itself, dead centre of each segment, so a
     number and the photo it belongs to arrive in the same place. They are
     always up: they say there are eight of these before anything is hovered. */
  .t-lecno{position:absolute;left:calc(var(--nx) * 100%);
    top:calc(var(--ny) * 100%);transform:translate(-50%, -50%);
    opacity:.8;transition:opacity var(--lec-off)}
  .t-lecno.on{opacity:1;transition:opacity var(--lec-in) ease}
  .lec .t{max-width:100%}
  .lec .t>*{max-width:100%}
  .lec.on{content-visibility:visible;opacity:1;transform:translateY(-50%);
    transition-duration:var(--lec-in),var(--lec-in)}
  /* Not enough room beside the spine any more: the block lies over it, from the
     left edge of the spine, where the segment\'s photo is its ground. */
  @media (max-width:1100px){
    .lecs{--lec-gap:0px}
    .lec{left:0;margin-left:0;width:min(38ch,100%)}
  }'''


BODY = '''
__BACKLIGHT__
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
    const nos=segs.map((g,i)=>document.querySelector('.t-lecno[data-lec="'+i+'"]'));
    // the photo moved to a layer of its own, so it is lit directly
    const pics=segs.map((g,i)=>document.querySelector('.pics .pic[data-seg="'+i+'"]'));
    // A collapsed .more is height:0 with its content overflowing, so the inner
    // box still lays out at full size and can be measured where it stands.
    // Measured at the moment of opening, which is the only moment the number is
    // needed and the only one certain to be current: the height moves for the
    // font swap, for a reflow, and for every drag of a spacing slider in the
    // panel, and a stale one shears the bottom off the detail. (A
    // ResizeObserver does not help here -- .more is height:0 with the box
    // overflowing it, and that box's changes are not reported.)
    const mores=[...document.querySelectorAll('.lec .more')];
    const note=m=>{const h=m&&m.firstElementChild.offsetHeight;
      if(h)m.style.setProperty('--more-h',h+'px');};
    const noteAll=()=>mores.forEach(note);
    noteAll();
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(noteAll);
    addEventListener('resize',noteAll,{passive:true});
    window.__lecMeasure=noteAll;   // the tuning panel re-measures after it edits
    // While the tuning panel is up, a chosen segment STAYS chosen: the reader
    // is over at the sliders, not over the spine, and a block that went out the
    // moment the pointer left it is a block they can never watch themselves
    // change. Nothing here is true of the poster — it is ?tools and nothing else.
    const PINNED=/[?&]tools/.test(location.search);
    let hot=-1, open=-1;
    function sync(){segs.forEach((g,i)=>{
      g.classList.toggle('active',i===open);
      g.classList.toggle('hot',i===hot);
      if(pics[i])pics[i].classList.toggle('on',i===hot||i===open);
      const l=lecs[i];if(!l)return;
      l.classList.toggle('on',i===hot||i===open);
      l.classList.toggle('open',i===open);});
      nos.forEach((n,i)=>n&&n.classList.toggle('on',i===hot||i===open));}
    // Opening a segment brings it to the middle of the screen. Only a click does
    // this — a hover that moved the page would move itself out from under the
    // cursor. The scroll is its own tween because scrollIntoView's smooth scroll
    // has neither a duration nor a curve to set, and the point here is slowness.
    const GLIDE=520, DEAD=24;   // ms end to end; px already near enough to leave alone
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
    function look(){queued=false;if(PINNED&&open!==-1)return;
      const i=at(px,py);if(i!==hot){hot=i;sync();}}
    addEventListener('pointermove',e=>{
      if(held&&Math.hypot(e.clientX-px,e.clientY-py)<=3)return;   // the glide's own
      held=false;px=e.clientX;py=e.clientY;
      if(!queued){queued=true;requestAnimationFrame(look);}},{passive:true});
    addEventListener('pointerleave',()=>{held=false;px=py=-1;
      if(PINNED&&open!==-1)return;
      if(hot!==-1){hot=-1;sync();}});
    ['wheel','touchstart','keydown'].forEach(e=>
      addEventListener(e,()=>{tween=null;held=false;},{passive:true}));
    segs.forEach((g,i)=>{
      g.addEventListener('click',e=>{open=(open===i?-1:i);hot=i;
        sync();                        // renders the block; only then is it measurable
        if(open===i)note(mores[i]);
        if(open===i){px=e.clientX;py=e.clientY;held=glide(g);}
        e.stopPropagation();});
    });
    // A click outside closes everything, and it says where the pointer is:
    // a click does not have to be preceded by a move, so its own coordinates
    // are the only ones that are certainly current. Pinned, it closes nothing:
    // clicking the open segment again is the way back out.
    document.addEventListener('click',e=>{if(PINNED)return;
      open=-1;held=false;px=e.clientX;py=e.clientY;look();sync();});
    sync();
  })();
  const lens=document.getElementById('lens'), q=new URLSearchParams(location.search);
  if(q.get('lens'))lens.style.setProperty('--lens',q.get('lens')+'px');
  if(q.get('feather'))lens.style.setProperty('--feather',q.get('feather')+'px');
  if(q.get('lenscolor'))lens.style.background='#'+q.get('lenscolor').replace('#','');
  if(q.get('cell'))document.documentElement.style.setProperty('--cell',q.get('cell')+'px');
  // Two switches for judging what the blending costs, on the machine it is being
  // judged on. Both of these are full-viewport composites and they are stacked:
  // the lens blends with everything under it and moves with the pointer, and the
  // grain blends over everything including the lens. ?nolens / ?nograin / ?flat.
  if(q.has('nolens')||q.has('flat')||q.has('plain'))lens.remove();
  if(q.has('nograin')||q.has('flat')||q.has('plain')){const g=document.querySelector('.grain');if(g)g.remove();}
  // ?nofilter drops the backlight: one SVG filter chain per role, over a filter
  // region 3.4x the box in each direction, which is 11x the area to rasterise.
  if(q.has('nofilter')||q.has('plain'))
    document.querySelectorAll('.t .slab').forEach(e=>e.remove());
  // Three knives for the type, each cutting one suspect and nothing else.
  // ?nodilate  the feMorphology only -- the slowest primitive in the chain,
  //            roughly O(radius^2) per pixel, and the radius is in device px.
  // ?tight     the filter REGION: 340% of the box each way is 11x its area,
  //            and the halo only ever needs about 3 sigma of margin.
  // ?onelayer  everything but the crisp copy: no slab, no bloom, no tight,
  //            no ink. Tests the five-times-over rendering rather than any
  //            one effect in it.
  if(q.has('nodilate'))
    document.querySelectorAll('[data-bl=dilate]').forEach(e=>e.setAttribute('radius','0'));
  if(q.has('tight'))
    document.querySelectorAll('filter[id^=bl-]').forEach(f=>{
      f.setAttribute('x','-40%');f.setAttribute('y','-90%');
      f.setAttribute('width','180%');f.setAttribute('height','280%');});
  if(q.has('onelayer'))
    document.querySelectorAll('.t .slab,.t .bloom,.t .tight,.t .ink').forEach(e=>e.remove());
  // ?onelayer said the cost is the copies, not the primitives. One switch per
  // copy, then, so what each one is worth can be weighed against what it costs:
  //   slab   the backlight silhouette (?nofilter)
  //   bloom  the text blurred wide, in the bloom colour
  //   tight  transparent text carrying two text-shadows
  //   ink    the text blurred slightly, under the crisp copy
  ['bloom','tight','ink'].forEach(n=>{
    if(q.has('no'+n))document.querySelectorAll('.t .'+n).forEach(e=>e.remove());});
  if(q.has('nocache'))
    document.querySelectorAll('.poster>*').forEach(e=>e.style.willChange='auto');
  // ?nostroke: every cell draws its own dashed outline, and a dashed stroke is
  // walked dash by dash at raster time -- 4766 cells x ~22 dashes is ~100k
  // segments per repaint of the spine, at whatever the device pixel ratio is.
  if(q.has('nostroke')||q.has('plain')){
    const st=document.createElement('style');
    st.textContent='.cells rect{stroke:none}';document.head.appendChild(st);}
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
  // cells: ~5% show a hieroglyph animal at a time, 7s each, then another cell
  // takes over. While one is up, its cell takes that glyph's colour as a solid
  // block and the animal is drawn black on the light tones, white on the dark.
  //
  // None of that touches the drawing. The base is read once for where the cells
  // are and what colour each one is, and everything after that is written into
  // the layer above it, out of a pool made at the start: an opaque block in the
  // cell's own colour, which hides the ▓ beneath it, and the animal over that.
  // The animal overhangs its cell, and being in the layer above is what puts it
  // over its neighbours -- the old drawing had to re-order nodes to manage it.
  (function(){
    if(/[?&](noanim|plain)/.test(location.search))return;
    const SYMS=Array.from('𓃠𓃰𓃱𓃯𓃸𓃵𓃗𓃙𓃟𓄀𓄁𓄂𓄃𓃚𓃛𓃜𓃞𓃓𓃔𓃕𓃖𓃦𓃬𓃷𓃹𓃻𓃾𓄅𓄇𓆈𓆉𓆌𓆏𓆗𓆙𓆐𓆓𓆊𓆣𓆤𓆦𓆧𓆨𓆝𓆡𓅂𓅐𓅓𓅟𓅮𓅰𓆀');
    const SHARE=0.05, HOLD=7000, TICK=250, NS='http://www.w3.org/2000/svg';
    const base=document.querySelector('.spine.base'),
          host=document.querySelector('.spine.anim .glyphs');
    if(!base||!host)return;
    // One read of the drawing, and it is never read or written again.
    const glyphs=[...base.querySelectorAll('.glyphs text')];if(!glyphs.length)return;
    const rects=new Map([...base.querySelectorAll('.cells rect')]
      .map(r=>[r.dataset.c+','+r.dataset.r,r]));
    const cell=glyphs.map(t=>{const r=rects.get(t.dataset.c+','+t.dataset.r);
      return {c:+t.dataset.c, r:+t.dataset.r, col:(t.getAttribute('fill')||'').toUpperCase(),
              x:+r.getAttribute('x'), y:+r.getAttribute('y'),
              w:+r.getAttribute('width'), h:+r.getAttribute('height')};});
    // perceived brightness; the cut sits just above the accent orange (156) and
    // below the cream-orange midpoint (196) and the green of the holes (172), so
    // only the darkest tone of the ramp takes white ink.
    const light=c=>{const n=parseInt(c.slice(1),16);
      return !isNaN(n)&&((n>>16&255)*299+(n>>8&255)*587+(n&255)*114)/1000>165;};
    const idx=new Map(cell.map((d,i)=>[d.c+','+d.r,i]));
    const TARGET=Math.round(cell.length*SHARE);
    // the pool: one block and one animal each, made once, moved and recoloured
    const pool=[];
    for(let k=0;k<TARGET;k++){
      const g=document.createElementNS(NS,'g');
      const b=document.createElementNS(NS,'rect'), t=document.createElementNS(NS,'text');
      t.setAttribute('class','h');g.append(b,t);g.style.display='none';
      host.appendChild(g);pool.push({g,b,t});}
    const spare=pool.slice(), slot=new Map(), active=new Set(), due=new Map();
    const rnd=n=>Math.floor(Math.random()*n);
    const free=i=>{const d=cell[i];return !active.has(i)&&
      ![[1,0],[-1,0],[0,1],[0,-1]].some(([dc,dr])=>{
        const j=idx.get((d.c+dc)+','+(d.r+dr));return j!==undefined&&active.has(j);});};
    function on(i,first){
      const p=spare.pop();if(!p)return false;
      const d=cell[i];
      p.b.setAttribute('x',d.x);p.b.setAttribute('y',d.y);
      p.b.setAttribute('width',d.w);p.b.setAttribute('height',d.h);
      p.b.setAttribute('fill',d.col);
      p.t.setAttribute('x',d.x+d.w/2);p.t.setAttribute('y',d.y+d.h/2);
      p.t.setAttribute('fill',light(d.col)?'#000':'#fff');
      p.t.textContent=SYMS[rnd(SYMS.length)];
      p.g.style.display='';
      slot.set(i,p);active.add(i);
      due.set(i,performance.now()+(first?Math.random()*HOLD:HOLD));
      return true;}
    function off(i){const p=slot.get(i);if(p){p.g.style.display='none';spare.push(p);}
      slot.delete(i);active.delete(i);due.delete(i);}
    function spawn(first){for(let k=0;k<80;k++){const i=rnd(cell.length);
      if(free(i)&&on(i,first))return true;}return false;}
    for(let n=0;n<TARGET*3&&active.size<TARGET;n++)spawn(true);
    // Everything that falls due in one TICK is done together: the layer is
    // small, but a write to it is still a write, and four a second is enough.
    setInterval(()=>{
      if(document.hidden)return;
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
    info='Online Lectures\n5 weeks\nOct 10 ~ Nov 7, 2026\n9am EDT / 9pm CST',
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
                lecn='p', lect='p', lecl='p', lecb='div', lecno='p')


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
    width = float(re.search(r'viewBox="0 0 ([\d.]+) ', SPINE).group(1))
    cx = float(re.search(r'<svg data-cx="([\d.]+)"', SPINE).group(1)) / width
    bands = [float(m) for m in re.findall(
        r'<g class="seg"[^>]*data-cy="([\d.]+)"', SPINE)]
    out = []
    for i, lec in enumerate(LECTURES[:len(bands)]):
        # Both the number and the block hang off the segment's centre of mass,
        # which spine.py works out -- the middle of the box is not where a
        # tapering vertebra looks like its middle. The number's x is the whole
        # drawing's centre, one line for all eight, not each segment's own.
        cy = bands[i] / height
        out.append(layers('p', 'lecno', f'{i + 1:02d}', **{
            'data-lec': i, 'style': f'--nx:{cx:.4f};--ny:{cy:.4f}'}))
        # A hover is worth the three things that tell you which lecture this is;
        # everything else waits inside .more, which only an open segment shows.
        # The number is not here — it sits on the segment, up in its own corner.
        out.append(
            f'<div class="lec" data-lec="{i}" style="--y:{cy:.4f}">'
            + layers('p', 'lecn', copy_html('lecn', lec['when'] + '\n' + lec['who']))
            + layers('p', 'lect', copy_html('lect', lec['what']))
            + '<div class="more"><div class="more-in">'
            + layers('p', 'lecl', copy_html('lecl', lec['lang']))
            + layers('div', 'lecb', copy_html('lecb', lec['about']))
            + '</div></div></div>')
    return '\n'.join(out)


TOOLS_CSS = '.tools{position:fixed;right:0;top:0;bottom:0;z-index:200;width:272px;overflow:auto;\n    background:#141614;color:#ECEEE9;font:11px/1.4 var(--font-sans);letter-spacing:.04em;\n    padding-bottom:18px;display:none}\n  .tools.on{display:block}\n  html.has-tools{--tools:272px}\n  .tools h3{margin:0;padding:8px 12px;font-size:10px;font-weight:600;letter-spacing:.14em;\n    text-transform:uppercase;background:#1D201D;color:#9BA39A;position:sticky;top:0}\n  .tools section{padding:7px 12px;border-bottom:1px solid #2A2E2A;display:grid;gap:5px}\n  .tools .f{display:grid;grid-template-columns:1fr 4.4em;gap:7px;align-items:center}\n  .tools label{color:#C8D4C2}\n  .tools input,.tools select{background:#0D0F0D;border:1px solid #2A2E2A;color:#ECEEE9;\n    font:inherit;padding:3px 4px;border-radius:3px;width:100%}\n  .tools input[type=number]{text-align:right}\n  .tools input[type=range]{grid-column:1/-1;accent-color:#C8D4C2;padding:0;border:0}\n  .tools textarea{width:100%;height:220px;background:#0D0F0D;color:#C8D4C2;\n    border:1px solid #2A2E2A;border-radius:3px;font:10px/1.45 ui-monospace,Menlo,monospace;\n    padding:6px;resize:vertical}\n  .tools .hint{color:#6E766C;font-size:9.5px;line-height:1.35}'


PANEL_JS = '(function(){\n  if(!/[?&]tools/.test(location.search)) return;\n  const D = __DATA__;\n  D.all = Object.assign({}, D.roles, D.text);\n  D.order = Object.keys(D.all);\n\n  // The same rule as steps()/types() in build.py: every text step is the base\n  // resized, and only tracking and leading are walked with the size. Kept in\n  // step with it by hand — if the rule there changes, it changes here.\n  function derive() {\n    D.steps = {mark: D.markStep};\n    D.type = {mark: D.markType};\n    D.back = {mark: back(D.markBack)};\n    Object.entries(D.sizes).forEach(([n, size]) => {\n      const d = size[0] - D.baseSize;\n      D.steps[n] = {size, soft: D.base.soft, glow: D.base.glow,\n                    bloom: D.base.bloom, solid: D.base.solid};\n      D.type[n] = {weight: D.base.weight,\n                   ls: +(D.base.ls - D.track * d).toFixed(4),\n                   lh: +(D.base.lh - D.lead * d).toFixed(3)};\n      D.back[n] = back(D.baseBack);\n    });\n  }\n  // the backlight\'s opacities are its own; its colour is the page\'s\n  const back = b => Object.assign({}, b, {slab: [D.blc, b.slab], glow: [D.blc, b.glow]});\n  derive();\n  const redraw = () => { derive(); apply(); Object.keys(D.steps).forEach(paintBack); dump(); };\n  const panel = document.getElementById(\'tools\');\n  panel.classList.add(\'on\');\n  document.documentElement.classList.add(\'has-tools\');\n\n  const $ = (t, a = {}, kids = []) => {\n    const el = document.createElement(t);\n    for (const k in a) k === \'text\' ? el.textContent = a[k] : el.setAttribute(k, a[k]);\n    kids.forEach(c => el.appendChild(c));\n    return el;\n  };\n  const field = (box, label, input) => {\n    box.appendChild($(\'div\', {class: \'f\'}, [$(\'label\', {text: label}), input]));\n    return input;\n  };\n  const num = (v, min, max, step) => $(\'input\', {type: \'number\', value: v, min, max, step});\n  const slider = (box, v, min, max, step) => {\n    const r = $(\'input\', {type: \'range\', min, max, step, value: v});\n    box.appendChild(r); return r;\n  };\n  const colour = (v, onset) => {\n    const el = $(\'input\', {type: \'color\', value: v});\n    el.oninput = e => onset(e.target.value);\n    return el;\n  };\n\n  // The backlight is one SVG filter per step, built by build.py and not\n  // rebuildable from here -- but every number in it lives on an attribute that\n  // takes a new value in place: a morphology radius, two deviations, a matrix\n  // and two floods. Only `stack` needs nodes added or removed. The radii are in\n  // em of the step\'s own size, so each of a step\'s two filters (poster, and the\n  // small-screen one) is painted from its own font size.\n  function paintBack(name) {\n    const b = D.back[name], st = D.steps[name];\n    [[st.size[0], \'bl-\' + name], [st.size[1], \'bl-\' + name + \'-s\']].forEach(([fs, id]) => {\n      const f = document.getElementById(id);\n      if (!f) return;\n      const q = k => f.querySelector(\'[data-bl="\' + k + \'"]\');\n      q(\'dilate\').setAttribute(\'radius\', (b.dilate * fs).toFixed(2));\n      q(\'merge\').setAttribute(\'stdDeviation\', (b.merge * fs).toFixed(2));\n      q(\'halo\').setAttribute(\'stdDeviation\', (b.halo * fs).toFixed(2));\n      q(\'hard\').setAttribute(\'values\',\n        \'0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 \' + b.hard + \' \' + (-b.hard / 2));\n      [\'slab\', \'glow\'].forEach(k => {\n        q(k).setAttribute(\'flood-color\', b[k][0]);\n        q(k).setAttribute(\'flood-opacity\', b[k][1]);\n      });\n      // same curve as stack_table() in build.py\n      const n = Math.max(1, Math.round(b.stack)), S = 64, v = [];\n      for (let k = 0; k <= S; k++) v.push((1 - Math.pow(1 - k / S, n)).toFixed(4));\n      q(\'stack\').firstElementChild.setAttribute(\'tableValues\', v.join(\' \'));\n    });\n  }\n\n  const pick = (v, opts) => {\n    const sel = $(\'select\');\n    opts.forEach(o => {\n      const opt = $(\'option\', {value: o});\n      opt.textContent = o;\n      if (o === v) opt.selected = true;\n      sel.appendChild(opt);\n    });\n    return sel;\n  };\n\n  // The same rule as copy_html in build.py: a blank line starts a paragraph, a\n  // single newline is a break, and only the div-wrapped roles take paragraphs.\n  function copyHtml(role, text) {\n    const esc = t => t.replace(/&/g, \'&amp;\').replace(/</g, \'&lt;\').replace(/>/g, \'&gt;\');\n    const paras = text.trim().split(/\\n\\s*\\n/).filter(p => p.trim());\n    const br = p => p.split(\'\\n\').map(esc).join(\'<br>\');\n    return D.tag[role] === \'div\'\n      ? paras.map(p => \'<p>\' + br(p) + \'</p>\').join(\'\')\n      : paras.map(br).join(\'<br>\');\n  }\n  function setCopy(role) {\n    const el = document.querySelector(\'.t-\' + role);\n    if (!el) return;\n    const html = copyHtml(role, D.copy[role]);\n    [...el.children].forEach(layer => layer.innerHTML = html);\n  }\n\n  // The one place a role\'s numbers reach the page. Corners are re-filled in the\n  // declared order so moving one role never reshuffles the others.\n  function apply() {\n    D.order.forEach(role => {\n      const r = D.all[role], st = D.steps[r.step], c = D.sets[r.set];\n      document.querySelectorAll(\'.t-\' + role).forEach(el => {\n      const s = el.style;\n      s.setProperty(\'--fs\', st.size[0] + \'px\');\n      s.setProperty(\'--soft\', st.soft + \'px\');\n      s.setProperty(\'--solid\', st.solid == null ? 1 : st.solid);\n      s.setProperty(\'--glowR\', st.glow + \'em\');\n      s.setProperty(\'--bloomR\', st.bloom + \'px\');\n      s.setProperty(\'--slabF\', \'url(#bl-\' + r.step + \')\');\n      // 字重、字距、行距属于字号档，不属于角色——换档要整套跟过去\n      const ty = D.type[r.step] || {};\n      s.setProperty(\'--w\', ty.weight);\n      s.setProperty(\'--ls\', ty.ls + \'em\');\n      s.setProperty(\'--lh\', ty.lh);\n      s.setProperty(\'--ink\', c.ink);\n      s.setProperty(\'--glow\', c.glow);\n      s.setProperty(\'--bloom\', c.bloom);\n      s.setProperty(\'--gap\', (r.gap || 0) + \'px\');\n      s.setProperty(\'--maxw\', r.width ? r.width + \'ch\' : \'var(--fit)\');\n      });\n    });\n    // spacing and size both move the detail\'s height, and the reveal animates\n    // to a number that was measured before this edit\n    if (window.__lecMeasure) window.__lecMeasure();\n    D.corners.forEach(corner => {\n      const box = document.querySelector(\'.\' + corner);\n      if (!box) return;\n      Object.keys(D.roles).filter(role => D.roles[role].at === corner)\n             .forEach(role => box.appendChild(document.querySelector(\'.t-\' + role)));\n    });\n  }\n\n  Object.entries(D.all).forEach(([role, r]) => {\n    const pinned = role in D.roles;\n    panel.appendChild($(\'h3\', {text: role + (pinned ? \'\' : \' · 讲座\')}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n\n    field(box, \'字号档\', pick(r.step, Object.keys(D.steps)))\n      .onchange = e => { r.step = e.target.value; apply(); dump(); };\n    if (pinned) field(box, \'位置\', pick(r.at, D.corners))\n      .onchange = e => { r.at = e.target.value; apply(); dump(); };\n    field(box, \'配色\', pick(r.set, Object.keys(D.sets)))\n      .onchange = e => { r.set = e.target.value; apply(); dump(); };\n\n    const g = field(box, \'上方间距 px\', num(r.gap || 0, 0, 160, 2));\n    const gr = slider(box, r.gap || 0, 0, 160, 2);\n    const setGap = v => { r.gap = +v; g.value = v; gr.value = v; apply(); dump(); };\n    g.oninput = e => setGap(e.target.value);\n    gr.oninput = e => setGap(e.target.value);\n\n    if (role in D.copy) {\n      box.appendChild($(\'div\', {class: \'hint\', text: \'文案：空行分段，单个换行是换行\'}));\n      const ta = document.createElement(\'textarea\');\n      ta.value = D.copy[role];\n      ta.rows = role === \'desc\' ? 8 : 4;\n      ta.spellcheck = false;\n      ta.style.cssText = \'height:auto;font:10px/1.5 var(--font-sans)\';\n      box.appendChild(ta);\n      ta.oninput = () => { D.copy[role] = ta.value; setCopy(role); dump(); };\n    }\n\n    const w = field(box, \'宽度 ch · 0=不限\', num(r.width || 0, 0, 90, 1));\n    const wr = slider(box, r.width || 0, 0, 90, 1);\n    const setW = v => { r.width = +v; w.value = v; wr.value = v; apply(); dump(); };\n    w.oninput = e => setW(e.target.value);\n    wr.oninput = e => setW(e.target.value);\n  });\n\n  // A step is shared by every role that names it, so these move type all over\n  // the poster at once. soft is the blur on the ink layer -- the one that\n  // decides whether small type is legible -- and glow and bloom are the haze\n  // around it. The slab filter is built at build time from `size`, so changing\n  // size here moves the type without moving its silhouette: rebuild to see it.\n  // One section, not one per step: the ramp has a single hand-set size in it.\n  {\n    panel.appendChild($(\'h3\', {text: \'基准 t\' + D.baseSize}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    const B = D.base;\n    knob(\'字距 em · ls\', -.12, .3, .005, () => B.ls, v => B.ls = v);\n    knob(\'行距 · lh\', .6, 2, .01, () => B.lh, v => B.lh = v);\n    knob(\'字重\', 100, 700, 50, () => B.weight, v => B.weight = v);\n    knob(\'模糊 px · soft\', 0, 4, .02, () => B.soft, v => B.soft = v);\n    knob(\'实心度 · solid\', 0, 1, .02, () => B.solid, v => B.solid = v);\n    knob(\'内发光 em · glow\', 0, 3, .01, () => B.glow, v => B.glow = v);\n    knob(\'外发光 px · bloom\', 0, 40, .1, () => B.bloom, v => B.bloom = v);\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'其余字号由此算出。下面两个是阶梯的斜率：每大 1px，字距和行距各收回多少。\'}));\n    knob(\'字距斜率 · TRACK\', 0, .04, .0005, () => D.track, v => D.track = v);\n    knob(\'行距斜率 · LEAD\', 0, .06, .0005, () => D.lead, v => D.lead = v);\n  }\n\n  // The backlight. Radii in em, so the base\'s numbers are the whole ramp.\n  [[\'基准 背光\', D.baseBack], [\'mark 背光\', D.markBack]].forEach(([title, b]) => {\n    panel.appendChild($(\'h3\', {text: title}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    knob(\'实色不透明\', 0, 1, .02, () => b.slab, v => b.slab = v);\n    knob(\'晕色不透明\', 0, 1, .02, () => b.glow, v => b.glow = v);\n    knob(\'外扩 em · dilate\', 0, .4, .005, () => b.dilate, v => b.dilate = v);\n    knob(\'合并 em · merge\', 0, .3, .005, () => b.merge, v => b.merge = v);\n    knob(\'晕开 em · halo\', 0, .8, .005, () => b.halo, v => b.halo = v);\n    knob(\'叠加次数 · stack\', 1, 24, 1, () => b.stack, v => b.stack = v);\n    knob(\'切边硬度 · hard\', .5, 12, .1, () => b.hard, v => b.hard = v);\n  });\n\n  // ONE colour, for every backlight on the page. Per-step would only ever\n  // produce four shades of almost-the-same-yellow lit side by side.\n  {\n    panel.appendChild($(\'h3\', {text: \'背光颜色 · 全局\'}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    field(box, \'颜色\', colour(D.blc, v => { D.blc = v; redraw(); }));\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'整页所有背光共用这一个颜色。浓淡分别在上面两节的不透明度里调。\'}));\n  }\n\n  {\n    panel.appendChild($(\'h3\', {text: \'mark · 字号档\'}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    const S = D.markStep, T = D.markType;\n    knob(\'字号 px\', 8, 200, .5, () => S.size[0], v => S.size[0] = v);\n    knob(\'字距 em · ls\', -.12, .3, .005, () => T.ls, v => T.ls = v);\n    knob(\'行距 · lh\', .6, 2, .01, () => T.lh, v => T.lh = v);\n    knob(\'字重\', 100, 700, 50, () => T.weight, v => T.weight = v);\n    knob(\'模糊 px · soft\', 0, 4, .02, () => S.soft, v => S.soft = v);\n    knob(\'实心度 · solid\', 0, 1, .02, () => S.solid, v => S.solid = v);\n    knob(\'内发光 em · glow\', 0, 3, .01, () => S.glow, v => S.glow = v);\n    knob(\'外发光 px · bloom\', 0, 40, .1, () => S.bloom, v => S.bloom = v);\n  }\n\n  // The two gaps that belong to the lecture blocks rather than to any one role.\n  panel.appendChild($(\'h3\', {text: \'讲座间距\'}));\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const lecs = document.querySelector(\'.lecs\');\n    const pxKnob = (label, prop, min, max, step) => {\n      const cur = parseFloat(getComputedStyle(lecs).getPropertyValue(prop)) || 0;\n      const n = field(box, label, num(cur, min, max, step));\n      const r = slider(box, cur, min, max, step);\n      const set = v => { lecs.style.setProperty(prop, v + \'px\'); n.value = v; r.value = v; dump(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    pxKnob(\'行距 --lec-lead\', \'--lec-lead\', 0, 60, 1);\n    pxKnob(\'离脊柱 --lec-gap\', \'--lec-gap\', 0, 200, 2);\n  }\n\n  panel.appendChild($(\'h3\', {text: \'页边距\'}));\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue(\'--pad\'));\n    const p = field(box, \'--pad px\', num(cur, 8, 96, 2));\n    const pr = slider(box, cur, 8, 96, 2);\n    const setPad = v => {\n      document.documentElement.style.setProperty(\'--pad\', v + \'px\');\n      p.value = v; pr.value = v; dump();\n    };\n    p.oninput = e => setPad(e.target.value);\n    pr.oninput = e => setPad(e.target.value);\n  }\n\n  panel.appendChild($(\'h3\', {text: \'导出 · 贴回 build.py\'}));\n  const out = $(\'textarea\', {readonly: \'\', spellcheck: \'false\'});\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    box.appendChild(out);\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'面板只改这一页，刷新就回到 build.py 里的值。\' +\n      \'导出的是手调的那些数，不是它们算出来的阶梯。\'}));\n  }\n\n  function dump() {\n    const q = s => "\'" + s + "\'";\n    const row = (role, withAt) => {\n      const r = D.all[role];\n      const bits = [];\n      if (withAt) bits.push(\'at=\' + q(r.at));\n      bits.push(\'step=\' + q(r.step), \'set=\' + q(r.set));\n      if (r.gap) bits.push(\'gap=\' + r.gap);\n      if (r.width) bits.push(\'width=\' + r.width);\n      return \'    \' + role + \'=dict(\' + bits.join(\', \') + \'),\';\n    };\n    const py = s => "\'" + s.replace(/\\\\/g, \'\\\\\\\\\').replace(/\'/g, "\\\\\'")\n      .replace(/\\n/g, \'\\\\n\') + "\'";\n    const copy = Object.keys(D.copy).map(k => \'    \' + k + \'=\' + py(D.copy[k]) + \',\');\n    // Only the hand-set numbers come back out. The ramp is a rule, and printing\n    // the five sizes it produces would invite pasting them back as five tables.\n    const B = D.base, S = D.markStep, T = D.markType;\n    const dict = (name, pairs) => name + \' = dict(\' + pairs.join(\', \') + \')\';\n    const bk = (name, b) => dict(name, [\'dilate=\' + b.dilate, \'merge=\' + b.merge,\n      \'hard=\' + b.hard, \'halo=\' + b.halo, \'stack=\' + Math.round(b.stack),\n      \'slab=\' + b.slab, \'glow=\' + b.glow]);\n    const lecs = getComputedStyle(document.querySelector(\'.lecs\'));\n    out.value =\n        dict(\'BASE\', [\'soft=\' + B.soft, \'glow=\' + B.glow, \'bloom=\' + B.bloom,\n                      \'solid=\' + B.solid, \'weight=\' + B.weight,\n                      \'ls=\' + B.ls, \'lh=\' + B.lh]) + \'\\n\'\n      + \'TRACK = \' + D.track + \'\\n\'\n      + \'LEAD = \' + D.lead + \'\\n\\n\'\n      + dict(\'MARK_STEP\', [\'size=(\' + S.size[0] + \', \' + S.size[1] + \')\',\n                           \'soft=\' + S.soft, \'glow=\' + S.glow, \'bloom=\' + S.bloom,\n                           \'solid=\' + S.solid]) + \'\\n\'\n      + dict(\'MARK_TYPE\', [\'weight=\' + T.weight, \'ls=\' + T.ls, \'lh=\' + T.lh]) + \'\\n\\n\'\n      + "BACKLIGHT_COLOUR = \'" + D.blc + "\'\\n"\n      + bk(\'BASE_BACK\', D.baseBack) + \'\\n\'\n      + bk(\'MARK_BACK\', D.markBack) + \'\\n\\n\'\n      + \'ROLES = dict(\\n\' + Object.keys(D.roles).map(r => row(r, true)).join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'TEXT = dict(\\n\' + Object.keys(D.text).map(r => row(r, false)).join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'COPY = dict(\\n\' + copy.join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'--pad: \' + getComputedStyle(document.documentElement).getPropertyValue(\'--pad\').trim()\n      + \'\\n--lec-lead: \' + lecs.getPropertyValue(\'--lec-lead\').trim()\n      + \'\\n--lec-gap: \' + lecs.getPropertyValue(\'--lec-gap\').trim();\n  }\n\n  apply(); dump();\n})();\n'


def tools_panel():
    """A side panel for placing and sizing the roles. It appears on ?tools only —
    the poster itself should not ship a dev panel. It edits the same three tables
    the build reads, and prints ROLES back as Python to paste into this file."""
    data = json.dumps(dict(roles=ROLES, text=TEXT, sets=COLOUR_SETS,
                           base=BASE, baseSize=BASE_SIZE, track=TRACK, lead=LEAD,
                           sizes=TEXT_SIZES, markStep=MARK_STEP, markType=MARK_TYPE,
                           baseBack=BASE_BACK, markBack=MARK_BACK, blc=BACKLIGHT_COLOUR,
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
            + BODY.replace('__SPINE__', spine).replace('__LECS__', lectures_html()).replace('__CORNERS__', corners()).replace('__BACKLIGHT__', backlight_defs())
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
