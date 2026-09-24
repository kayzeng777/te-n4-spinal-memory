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
            weight=400, ls=.035, lh=.98)
BASE_SIZE = 14
TRACK = .0091   # em of letter-spacing given back per px of size over the base
LEAD = .0164    # of line-height, likewise
WALK_STOP = 26  # px past which tracking and leading stop tightening
# poster size -> the size at NARROW, the ramp's own .857
TEXT_SIZES = dict(t20=(20, 17.1), t18=(18, 15.4), t16=(16, 13.7),
                  t14=(14, 12), t12=(12, 10.3),
                  no=(16, 14),   # the segment numbers: 14 on a phone, not the ramp's 13.7
                  su=(18, 14))   # Sign up: 18 beside the spine, 14 on a phone
MARK_STEP = dict(size=(100, 84), soft=1.92, glow=.04, bloom=9, solid=.76)
MARK_TYPE = dict(weight=400, ls=-.055, lh=.8)


# The poster keeps its three columns -- corner type, spine, lecture -- from WIDE
# down to NARROW, and what makes room for them is everything getting smaller
# together: the spine and every text size slide from their poster size at WIDE
# to their small size at NARROW, on the same line. Stepping one and not the
# other is what made the type look shrunk against a spine that was not.
# Below NARROW the three columns do not fit at any size.
NARROW, WIDE = 760, 1440
# The spine goes further than the type does: it is the widest thing on the
# page, and every px it keeps is a px taken off the lecture beside it, which
# at .75 was squeezed into a strip one long word wide. The type stops at its
# small sizes, which are as small as it reads. The lens is read against the
# spine, so it shrinks by the spine's share.
SPINE_SMALL = .55   # the spine's width at NARROW, of its poster width
CELL = 9            # px per spine cell at WIDE and up
LENS, FEATHER = 100, 8   # the lens's diameter and blur at WIDE, px


def ramp(small, big):
    """A length that is `small` at NARROW, `big` at WIDE, straight between."""
    if small == big:
        return f'{big:g}px'
    slope = (big - small) / (WIDE - NARROW)
    return (f'clamp({small:g}px, calc({small:g}px + {slope:.5f} * (100vw - {NARROW}px)), '
            f'{big:g}px)')


def steps():
    out = dict(mark=dict(MARK_STEP))
    for name, size in TEXT_SIZES.items():
        out[name] = dict(size=size, **{k: BASE[k] for k in ('soft', 'glow', 'bloom', 'solid')})
    return out


def types():
    out = dict(mark=dict(MARK_TYPE))
    for name, size in TEXT_SIZES.items():
        # the walk was fitted up to about 26px; past that it keeps tightening
        # until the letters touch, so it stops there
        d = min(size[0], WALK_STOP) - BASE_SIZE
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
    out.append(PEEK_GROUND)
    return ('<svg width="0" height="0" aria-hidden="true" '
            'style="position:absolute"><defs>' + ''.join(out) + '</defs></svg>')


# The ground a peeking head sits on (see html.peek): the page's green, drawn to
# the outline of the type -- its alpha, glow included, cut hard so the faint
# edge of the bloom does not count, grown out, then softened. The colour is a
# custom property the script sets from where on the screen the head is.
PEEK_GROUND = (
    '<filter id="peek-ground" x="-15%" y="-80%" width="130%" height="260%" '
    'color-interpolation-filters="sRGB">'
    '<feComponentTransfer in="SourceAlpha"><feFuncA type="linear" slope="3" intercept="-.3"/>'
    '</feComponentTransfer>'
    '<feMorphology operator="dilate" radius="16"/>'
    '<feGaussianBlur stdDeviation="8" result="shape"/>'
    '<feFlood class="peek-flood"/>'
    '<feComposite in2="shape" operator="in" result="ground"/>'
    '<feMerge><feMergeNode in="ground"/><feMergeNode in="SourceGraphic"/></feMerge>'
    '</filter>')


# Where everything sits, and the whole of what it takes to move it. `at` is one of
# the four corners; a corner stacks its roles in this order and aligns them to the
# edge it is pinned to, so the right-hand corners are right-aligned without being
# told. `gap` is the space above a role when it follows a sibling in the same
# corner. `step` names a row of STEPS, `set` a row of COLOUR_SETS. width caps the
# measure in ch so it survives a size change. `ls` and `lh` override the step's
# tracking and leading for that role alone. Roles that name the same `box` are
# wrapped together in a div of that class inside their corner, so the corner
# can place them as one: on a phone, `info` is the panel at the foot.
CORNERS = ('head', 'head-r', 'foot', 'foot-r')
ROLES = dict(
    logo=dict(at='head', step='mark', set='a'),
    # The title and subtitle are off the page while where they go is decided;
    # their copy is still in COPY.
    # no width: the column's measure is --col, the same as the lectures' side
    desc=dict(at='foot', step='t14', set='a', box='info'),
    facts=dict(at='foot', step='t14', set='a', gap=21, box='info'),
)


# Type that is not pinned to a corner: the lecture blocks along the spine. Same
# four-layer machinery, same steps and colour sets as the poster roles — the
# only difference is that nothing places them, the spine does.
TEXT = dict(
    lecd=dict(step='t14', set='a'),              # the date and time
    lecw=dict(step='t16', set='a', gap=10),      # who: under the date, over the title
    lect=dict(step='t20', set='a', gap=-4, lh=1),  # close under who: the two are one thing
    lecno=dict(step='no', set='a'),
    lecl=dict(step='t14', set='a', gap=4),   # a chip, the size of the Intro's
    lecb=dict(step='t14', set='a', gap=6),
    lecbio=dict(step='t14', set='a'),           # a speaker's bio, beside their portrait
    lecs=dict(step='t16', set='a', gap=30),
    lecx=dict(step='t20', set='a'),              # the close; its size is set in LEC_CSS      # Sign up, the size of the speaker's name
)

# Where each lecture's Sign Up button goes. One link for the series unless a
# lecture names its own with `signup=`.
SIGNUP = '#'
# The time is its own field, not part of `when`: the series is one time of day,
# but a lecture that falls on the other side of a clock change is not.
TIME = '9am EDT / 9pm CST'

# One row per segment of the spine, top to bottom: segment 0 is the top vertebra.
# `when`, `who` and `lang` are one line each; `what` is the title; `about` is prose, and
# a blank line in it starts a paragraph, exactly as in COPY.
# `lang` is the line under the speaker, and belongs with the detail rather than
# the head: it is what you need once you have decided to come.
# `pics` (2-3 images from the lecture) and `speakers` are optional; both sit in
# the detail under `about`. Paths are under images/lectures/, where the
# originals are kept as they came: 'lecture images/' and 'speakers portrait/'. A lecture with two
# speakers lists two: speakers=[dict(face='06-hsu.jpg', bio='...'), dict(...)].
# `bio` is prose like `about`.
LECTURES = [
    dict(when='Oct 10', who='Victoria Soyan Peemot',
         what='Horses and Songs: Multispecies Rhythm and Voice in Inner Asia',
         lang='English',
         signup='https://luma.com/nm7vu01t',
         about='When Tyva people say that the horse is everything in life, this is not a metaphor—it comes from the lived experience of the people who have been mobile pastoralists for millennia, whose lives and identities have been continuously shaped by horses. Drawing on her personal experience and research among mobile pastoralists between the Altai and Sayan mountain ranges in the transnational region of Inner Asia, Dr. Victoria Soyan Peemot explores how Tyvan understandings of voice, sound, and music are rooted in multispecies relationships, with a particular focus on human-equine belonging.\n\nHer research brings together horses and their rich sound world with the people and land to which they co-belong. The lecture discusses how the rhythms and lyrics of Tyvan songs and Tyvan ways of understanding the human voice itself emerge from belonging to the land and cohabiting it with other beings.',
         pics=['lecture images/1-1.JPG', 'lecture images/1-2.jpg'],
         speakers=[dict(face='speakers portrait/01 Victoria.jpeg', bio='Victoria Soyan Peemot is a senior researcher, community advocate, and member of the Soyan kinship group from the Tyva Republic, raised at the Tyvan-Mongolian borderland in a livestock herding family. Her research weaves together Tyva transnational kinship, multispecies relations, and the continuity of pastoralist lifeways and is guided by aaldaar, the Tyvan customary practice of relational reciprocity that extends to land and other-than-human beings.\n\nShe holds a PhD in History and Cultural Heritage Studies from the University of Helsinki (2021). Her book *The Horse In My Blood* (2024) explores human-horse-homeland relationships and histories of state violence. Her second book *Songs of Tyva: A Guide to Tyvan Culture and Language* (2026) draws on emplaced storytelling through folk songs and photographs of the featured homelands. Her broader work engages ethnographic museum collections across Europe, decolonizing archives, and the return of ancestral stories to the communities they belong to.')]),
    dict(when='Oct 11', who='Wantanee Siripattananuntakul',
         what='If There’s No Reply, Is That Silence Still Love?',
         lang='English',
         signup='https://luma.com/3zuyg46f',
         about='Wantanee Siripattananuntakul has lived with Beuys, an African grey parrot, since 2013. After more than a decade together, she has come to know Beuys’ voices, movements, routines, fears, and desires. She has also kept Beuys’ feathers, images, objects, and documents, and turned to science to learn how parrots see, hear, and navigate the world. Yet the more she knows about Beuys, the more aware she becomes of what she cannot know: what the world is like for Beuys.\n\nThat distance extends beyond her relationship with Beuys into her wider artistic practice: when she reconstructs what is no longer there from what remains, traces histories she was never there to witness, or measures a distance exactly and still finds that the number cannot tell her what that distance means. Wantanee keeps looking anyway. She is no longer only asking what she can know, but what makes her think she has received an answer. What makes something an answer, and who decides? And if there is no reply, how does she know that what she calls silence is silence at all?',
         pics=['lecture images/2-1.jpg'],
         speakers=[dict(face='speakers portrait/02 Wantanee.jpg', bio='Wantanee Siripattananuntakul is a Thai contemporary artist working across video, installation, sculpture, sound, and text. Her practice moves between inquiries into economic and political structures and questions of perception that extend beyond human experience. These concerns coexist within her practice, intersecting or remaining distinct depending on the conditions of each project. Her long-standing engagement with inequality, systems of value, and ideological structures often begins with particular political or economic conditions.\n\nAlongside this, her shared life with Beuys, an African grey parrot she has lived with since 2013, has gradually altered the way she approaches questions of perception and position, leading to broader investigations of how other species perceive and orient themselves within worlds that humans can never fully access.')]),
    dict(when='Oct 17', who='Terezie Štindlová',
         what='Do We Need Zoos?',
         lang='English',
         signup='https://luma.com/clizyb3n',
         about='Do we need zoos? Why do we enjoy looking at animals? What lies behind the simple human desire to feel connected to animals? These are the questions Terezie Štindlová set out to ask through her platform [[ZOO Index]], an open archive of visual and textual zoo related material questioning its relevance in contemporary society. In this lecture, Terezie traces the development of [[ZOO Index]] from her initial interests in Zoo design and architecture toward broader questions about human ways of relating to animals, following this thinking as it takes shape through the publication process, the collaborations behind it, and the project’s possible futures.\n\nBefore the talk, the session opens with a short excerpt from a sound piece by artist Qihang Li, an immersive soundscape originally composed for ZOO Index’s book launch in Amsterdam.',
         pics=['lecture images/3-1.jpeg', 'lecture images/3-2.png'],
         speakers=[dict(face='speakers portrait/03 Terezie.jpg', bio='Terezie Štindlová is a designer and one half of a non-workaholic studio Day Shift Office. She’s an author of the online platform and a publication *[[ZOO Index]]*, which examine the (un)relevance of zoos in contemporary society, how they shape our gaze towards nonhuman animals and by extension, ourselves and one another. In her research she’s also looking for links between zoos and current office culture; shedding light on the power dynamics of labour and control exerted through (human) design. She graduated from Werkplaats Typografie in 2023 and is currently based in Amsterdam.')]),
    dict(when='Oct 24', who='Boria Sax (Guest Moderator: Ruoyi Shi)',
         what='Stories, Poetry, and Birdsong',
         lang='English',
         signup='https://luma.com/r415f2wl',
         about='Boria Sax has long studied how animals have moved through human culture, stories, and mythology. This lecture argues that birdsong is similar to the poetry of Dylan Thomas or John Ashbery, where there is almost no literal meaning but a great deal of suggestiveness. Human beings organize experience primarily through storytelling, which serves, among other things, to construct identities, build communities, teach lessons, and set goals. Animals from wolves to fireflies are also constantly exchanging messages. This is especially apparent in birds, for whom songs and calls are used for courtship, proclaiming territory, issuing warnings, and affirming bonds, all of which are also central motifs in the tales told by human beings.\n\nThese vocalizations also resemble human stories in that they modulate their tempo for purposes such as the building or release of dramatic tension. They differ from human stories, and even more from products of artificial intelligence, in that they are profoundly embedded in the world to a point where the question of “truth” or “falsity” can become irrelevant.\n\nThe lecture will be joined by artist Ruoyi Shi as guest moderator.',
         pics=['lecture images/4-1.jpg', 'lecture images/4-2.JPG'],
         speakers=[dict(face='speakers portrait/04 Boria Sax.jpg', bio='Boria Sax is the author of 20 books, mostly on animals in human culture, including *Avian Illuminations: A Cultural History of Birds*, *City of Ravens*, and *The Mythical Zoo: Animals in Myth, Legend, and Literature*. His books have been widely translated including eight into either simplified or traditional Chinese. He teaches at Sing Sing prison and in the graduate English program of Mercy University.'),
                   dict(face='speakers portrait/04 Ruoyi Shi.png', bio='Ruoyi Shi is an interdisciplinary artist based in Los Angeles. Inspired by ancient tales and rituals intertwined with language, habits, and societal norms, she combines humor and fiction to construct her poetic narratives. Her work explores the interface between nature and artificial existences, as well as the notion of truth and its fabrications. Studying the linguistic connection between translation and birds, or bird-like creatures, from both nature and mythology, she expands beyond concepts of language into questions of transformation, migration, and belief.')]),
    dict(when='Oct 25', who='Robert Zhao Renhui',
         what='Seeing Forest: Encounters, Evidence and Ways of Knowing',
         lang='English',
         signup='https://luma.com/o544mqdl',
         about='How do we come to know a forest through the encounters we have within it? Similar questions extend across Robert Zhao Renhui’s practice: what can we know from what we observe and document, and how much can such evidence really tell us?\n\nIn this lecture, Robert shares the fieldwork and artistic processes behind his investigations into Singapore’s secondary forests. Moving between the [[Institute of Critical Zoologists]] which he founded in 2018 and his project *Seeing Forest*, he traces how repeated visits, camera observations and found objects become photographs, moving images, installations and publications. Through stories from the field, this lecture reflects on what images reveal, what remains uncertain, and how sustained attention can change our understanding of the lives and histories that make up a place.',
         pics=['lecture images/5-1.jpg', 'lecture images/5-2.jpg'],
         speakers=[dict(face='speakers portrait/05 robert zhao renhui.jpg', bio='Robert Zhao Renhui is a Singaporean artist whose work examines the complex relationships between humans and non-human life. Working across photography, video, installation, and research-based projects, he investigates secondary forests, invasive species, and landscapes shaped by disturbance. His long-term projects explore how animals adapt within environments altered by colonial histories, urban expansion, and industrial development. He is the founder of the Institute of Critical Zoologists and lives and works in Singapore.\n\nZhao represented Singapore at the 60th Venice Biennale (2024) with *Seeing Forest*, a multi-year study of a secondary forest in Singapore. Recent projects include *5 Albizias* (Singapore/Maluku), research on sloth bears in Hampi (India), water deer in the United Kingdom, and urban deer in Tokyo. Through sustained observation and fieldwork, he challenges distinctions between native and invasive, natural and artificial, proposing instead that disturbance itself becomes habitat.')]),
    dict(when='Oct 31', who='Oscar Salguero',
         what='The Rhizomatic Archive: Interspecies Library',
         lang='English',
         signup='https://luma.com/ek6lzccj',
         about='Interspecies Library is an independent archive launched in a Brooklyn apartment in 2019, as an experiment in mapping a growing, species-wide fascination with more-than-human worlds. In this lecture, founder and curator Oscar Salguero traces the story of this living archive, from informal salon-style gatherings to large-scale gallery exhibitions, original book commissions and limited editions, and, more recently, collaborations to develop an itinerant version of the library that brings these works into new environments and cross-pollinating dialogues.\n\nToday, the archive stewards over 500 volumes by international artists and independent presses, documenting how the book, an ancient human technology, continues to serve as a portal to imagining and embodying shared fungal, bacterial, plant, animal, and viral futures.',
         pics=['lecture images/6-1.jpg', 'lecture images/6-2.jpg'],
         speakers=[dict(face='speakers portrait/06 oscarsalguero.jpg', bio="Oscar Salguero is an independent curator and researcher based in Queens, NY. He is the founder of [[Interspecies Library]], the first archive of artists' books exploring alternative interspecies futures. Salguero curated Interspecies Futures [IF] at Center for Book Arts (2021), and NEO MINERALIA at Center for Craft (2023). His latest curatorial work is Journal of Therolinguistics, an exhibition exploring the poetic study of nonhuman languages, which was presented at Descanso Gardens in California from March 25 to July 5, 2026.")]),
    dict(when='Nov 7', who='许哲瑜 Hsu Che-Yu & 陈琬尹 Chen Wan-Yin',
         what='Specimen of Suffering',
         lang='Chinese (with Zoom translated captions)',
         signup='https://luma.com/event/evt-I5aICYx7KZLnxSw',
         about='This lecture moves from a mallard at Natural History Museum Rotterdam, killed after flying into a glass panel, to the Przewalski’s horses of Mongolia; from the Nazi-era attempt to breed back the extinct Tarpan, to the beasts executed at Taipei Yuan-Shan Zoo during wartime; and on to the pathological specimens held at Amsterdam’s Museum Vrolik—research the artist has pursued across moving image, writing, archival research, and near-forensic methodologies.\n\nTheir works keep asking: how do specimens reconstruct memory? How do they conceal historical violence, or become monuments to their own suffering? This lecture invites us to reconsider how museums, science, and political ideology shape the stories behind these specimens. Beyond this, Hsu and Chen will also discuss the research behind their essay *Suffering and the Specimen*, and drawing on their own works, to trace how these histories move between fieldwork, archival material, and working method.',
         pics=['lecture images/7-1.jpg', 'lecture images/7-2.jpg'],
         speakers=[dict(face='speakers portrait/07-Hsu Che-Yu.jpeg', bio='许哲瑜 Hsu Che-Yu is an artist who lives and works in Taipei and Amsterdam. He studied at the Graduate Institute of Plastic Arts at Tainan National University of the Arts, where he received his master’s degree in 2014. He participated in several international postgraduate programs: 2019-2020 at HISK (Higher Institute for Fine Arts) in Ghent; 2020-2022 at Le Fresnoy—Studio national des arts contemporains in Tourcoing; 2022-2024 at the Rijksakademie van Beeldende Kunsten in Amsterdam.\n\nHis practice includes video works, animations, VR works, and installations. A central theme is the intertwining of media, memory, and the body. Typical is his collaboration with forensic 3D scanning teams, whose technologies he transfers into artistic processes in order to renegotiate historical events, political traumas, or biographical narratives. He has been working closely with writer Chen Wan-Yin since 2014.'),
                   dict(face='speakers portrait/07-Chen Wan-Yin.jpeg', bio='陈琬尹 Chen Wan-Yin is a writer whose practice investigates the technological and biopolitical production of memory. She is a key conceptual collaborator in Hsu Che-Yu’s practice and has been shaping its research-driven artistic methodology since 2014. Together they co-authored *aberrant archive 2015-2025* (dmp editions, Taipei), a publication documenting their decade-long artistic alliance examining post-martial law Taiwanese histories through moving images, text and technological reconstructions. She is currently a PhD candidate in Modern and Contemporary Art at Vrije Universiteit Amsterdam.')]),
    dict(when='Nov 8', who='沙爽 Sha Shuang',
         what='Writing a Cow: From Surveillance Data to Fiction',
         lang='Chinese (with Zoom translated captions)',
         signup='https://luma.com/event/evt-nM4qZM7TCLIBj6Z',
         about='Every cow on the farm has its own number. How much it eats, how far it walks, when it goes into heat, how much milk it gives—all of it is quietly logged by the machines. In 2021, Sha Shuang spent six months at an animal-monitoring data company in Xundian, Yunnan, working alongside a team of programmers. Months of fieldwork left her with a realization: the production system of a cattle farm and human social life aren’t so different after all—both made of bodies, labor, reproduction, care, and the daily experience of being logged and managed by one system or another.\n\nHer essay *Finding the Steppes* grew directly out of these field experiences. This lecture begins with that piece of semi-fiction, tracing why she moved from “monitoring cows” to “writing cows,” and how years of fieldwork among dairy cows, grasslands, milk, data, and ecological systems slowly found their way into her art practice.',
         pics=['lecture images/8-1.png', 'lecture images/8-2.JPG'],
         speakers=[dict(face='speakers portrait/08 Sha Shuang.jpg', bio='沙爽 Sha Shuang is an artist based in Shanghai. Her practice focuses on public space, site-specific engagement, and the intricate relationships between humans, animals, the environment, and production systems. Spanning publishing, painting, moving image, installation, and social practice, her work often develops through fieldwork, interviews, workshops, and collaborative co-creation.\n\nGrounded in concrete lived experiences and local contexts, she addresses issues of standardization, fluidity, relationships, change, memory, and community. In recent years, starting from dairy cows, her research has expanded into dairy production, data monitoring, and ecosystems, translating her fieldwork into moving images, installations, publications, and public programs.')]),
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
             f"--fs:{ramp(st['size'][1], st['size'][0])}", f"--soft:{st['soft']}px",
             f"--glowR:{st['glow']}em", f"--bloomR:{st['bloom']}px",
             f"--slabF:url(#bl-{r['step']})"]
        t = TYPE.get(r['step'])
        if t:
            v += [f"--w:{t['weight']}", f"--ls:{r.get('ls', t['ls'])}em",
                  f"--lh:{r.get('lh', t['lh'])}"]
        if 'width' in r:
            v += [f"--maxw:{r['width']}ch"]
        if r.get('gap'):
            v += [f"--gap:{r['gap']}px"]
        out.append(f".t-{role}{{{';'.join(v)}}}")
    return '\n  '.join(out)


def type_css_small():
    """The size itself slides (see ramp), but a filter cannot read a custom
    property, so the backlight is built twice and swaps halfway down the slide.
    Every other radius is absolute, or in em and follows on its own."""
    return ''.join(f".t-{role}{{--slabF:url(#bl-{r['step']}-s)}}"
                   for role, r in {**ROLES, **TEXT}.items()
                   if STEPS[r['step']]['size'][0] != STEPS[r['step']]['size'][1])


# The measure is capped against the viewport as well as in ch: the poster's
# blocks are max-content and pinned to a corner, so on a narrow screen a measure
# set in ch would simply run off the edge.
TYPE_CSS = '''.t{--fit:var(--col-fit, calc(100vw - 2 * var(--pad) - var(--tools,0px)));
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
  .t>*>*{margin:0}
  .t>*>p+p{margin-top:.75em}
  /* A chip labels what follows it: a small pill, drawn in the text's own
     colour on every layer, so it takes the same glow as the words. */
  .t>*>*+.chip{margin-top:1.5em}
  .t>*>.chip+p{margin-top:.4em}
  /* Centred on the letters themselves, not on the line box: text-box trims
     the box to the cap height above and the baseline below, so equal padding
     is equal space round the capitals at every size. Padding the line box
     instead could only be tuned by eye, and what was right at one size was a
     pixel out at the other. Where text-box is not supported, the old uneven
     padding stands in. */
  .t .chip>span{display:inline-block;font-size:.78em;line-height:1;
    padding:.3em .6em .16em;border:1px solid currentColor;border-radius:999px}
  @supports (text-box:trim-both cap alphabetic){
    .t .chip>span{text-box:trim-both cap alphabetic;padding:.38em .6em}
  }
  .t a{color:inherit;text-decoration:none}
  .t a::after{content:"\\2009\\2197"}
  /* Five copies of every word, stacked. Only the top one takes a selection, so
     a drag across two blocks copies the text once and not five times. */
  .t>:not(.core){-webkit-user-select:none;user-select:none}
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
                      # a link is followed on the top copy; the rest stay out of
                      # the tab order, or every link would be five stops
                      + '>' + (html if name == 'core'
                               else html.replace('<a ', '<a tabindex="-1" '))
                      + f'</{tag}>' for name in LAYERS)
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
<!-- The hieroglyph face is only for the animals, and must not hold up the
     page: a plain stylesheet link blocks the first paint until it answers,
     and where Google is unreachable (mainland China) that is a timeout. As
     media=print it loads without blocking, and switches on when it lands. -->
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Egyptian+Hieroglyphs&display=swap" media="print" onload="this.media='all'">
<style>
  __FONTS__

  :root{
    --font-sans:"PP Neue Montreal",-apple-system,"Helvetica Neue",Arial,sans-serif;
    --ink:#101410; --ink-brown:#822D00; --ink-soft:rgba(16,20,16,.7);
    --cell:min(__CELL__, calc(66vw / __COLS__));
  }
  *{box-sizing:border-box}
  html,body{margin:0;min-height:100%}
  body{min-height:100vh;background:#92CA87;color:var(--ink);position:relative;font-family:var(--font-sans);}
  .bg{position:fixed;inset:0;z-index:-1;
    background:linear-gradient(180deg,#66BF8C 0%,#92CA87 70%,#68C08D 100%)}
  /* Over everything, including the spine and the type — it is the medium, not a
     property of any one layer. Constant cell size, so it never tracks a font. */
  /* ?scrollgrain lays the grain over the document instead of over the screen.
     The reasoning was that a fixed blend has its backdrop change on every frame
     of a scroll, while one travelling with the page does not -- but it measured
     WORSE, and the reason is the area: over the document the blended region is
     the whole 2200px of it rather than one viewport. Kept as a record of a road
     that does not go anywhere. The grain stays fixed. */
  body{position:relative}
  .grain.scroll{position:absolute;top:0;left:0;right:var(--tools,0);bottom:auto;
    height:100%}
  .grain{position:fixed;inset:0 var(--tools,0) 0 0;z-index:4;pointer-events:none;
    mix-blend-mode:overlay;opacity:__GRAINA__;
    background-size:__GRAINSIZE__ __GRAINSIZE__;background-image:__GRAINURL__}
  :root{--grid-img:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><path d='M0 0H1M0 0V1' fill='none' stroke='%23cccccc' stroke-width='.05' stroke-dasharray='.14 .1'/></svg>")}
  .grid{position:absolute;inset:0;pointer-events:none;z-index:0;
    background-image:var(--grid-img);
    background-size:var(--cell) var(--cell);
    background-position:calc(50% + var(--cell) / 2)
      calc(var(--poster-h, 0px) + var(--main-top) + var(--pre, 0px));}
  main{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;
    padding:calc(var(--main-top) + var(--pre, 0px)) 0 calc(12vh + var(--post, 0px));
    margin-right:var(--tools,0)}
  /* --pre and --post are room the script lends above and below the spine, so
     an opened segment at either end can still be brought to the middle. */
  :root{--main-top:8vh}
  /* Three drawings in one place: the 9,300 elements that never change, then a
     layer for the animals and a layer for the photographs, which are the only
     things that do. Neither takes the pointer, so a hit test still lands on
     the cells in the base.

     The base is NOT given a layer of its own. It was, on the reasoning that a
     still drawing should be rasterised once -- but a texture the size of the
     whole spine, about 900x4400 device pixels, costs more to keep and to
     composite than redrawing it saves. Measured slower, so it is off. ?base
     puts it back. What the split was worth is that a photograph fading in no
     longer drags the drawing underneath it into the repaint. */
  .spine{width:calc(__COLS__ * var(--cell));height:auto;overflow:visible;display:block}
  .spine.anim,.spine.pics{position:absolute;left:0;top:0;pointer-events:none}
  .cells rect{stroke:#cccccc;stroke-width:.05;stroke-dasharray:.14 .1;shape-rendering:crispEdges}
  .glyphs{--gfs:1.57px;--gdy:0.41px}
  .glyphs text{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace;font-size:var(--gfs);text-anchor:middle;dominant-baseline:auto;transform:translateY(var(--gdy));pointer-events:none}
  .glyphs text.h{font-family:"Noto Sans Egyptian Hieroglyphs",sans-serif;font-size:1.5px;dominant-baseline:central;transform:none}
  /* The photo left the segment for a layer of its own, so it is lit by its
     own class now rather than by the segment's. Fading it there no longer
     touches the drawing underneath it. */
  /* Fading a clipped photograph re-rasterises it on every frame of the fade
     unless it has a layer to fade ON. With one, opacity is the compositor's
     job and the picture is drawn once. The layer is one segment's box, not
     the page. */
  .pic{opacity:0;transition:opacity var(--lec-out,.26s) ease;will-change:opacity}
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
  /* Beside the spine a corner has only its own column: the measure is capped
     at the room between the page edge and the spine, never across it. */
  @media not all and (max-width:__NARROW__px){
    /* The spine in the middle of the page, everything written in the column
       left of it, and the lecture blocks in the room right of it. --spine-x
       is where the spine starts; the grid under it and the room beside it
       follow it. --col is the written column's measure: its own width, but
       never closer to the spine than 40px, so on a narrower screen the
       column gives way rather than the spine moving off centre. */
    :root{--spine-x:calc((100vw - var(--tools,0px) - __COLS__ * var(--cell)) / 2);
      --col:min(clamp(280px, 26vw, 380px), calc(var(--spine-x) - var(--pad) - 40px))}
    .poster{--col-fit:var(--col)}
    main{align-items:flex-start;margin-left:var(--spine-x)}
    .grid{background-position-x:var(--spine-x)}
    /* The right-hand corners share their side with the lecture blocks, so they step
       aside while one is up. */
    .head-r,.foot-r{transition:opacity var(--lec-in,.24s) ease}
    body:has(.lec.on) :is(.head-r,.foot-r){opacity:0;pointer-events:none;transition-duration:var(--lec-off,0s)}
    /* The bottom-left column is longer than some screens are tall. It stays
       on the bottom margin while it fits; when it does not, it stops under the
       logo and scrolls on its own. The first child's auto margin is what does
       both -- it takes the slack when there is some and is zero when there is
       none, so the top is never scrolled out of reach. The box is padded by
       the glow's reach, or the scroller would clip the light off the edges,
       and that padding fades, so a line scrolled up under the logo goes soft
       rather than being cut -- but nothing at rest sits in the fade. */
    .poster>.foot{--halo:26px;
      top:calc(var(--pad) + __MARKFS__ + 80px - var(--halo));
      bottom:calc(var(--pad) - var(--halo));left:calc(var(--pad) - var(--halo));
      padding:var(--halo);overflow-y:auto;scrollbar-width:none;
      -webkit-mask-image:linear-gradient(to bottom,transparent,#000 var(--halo));
      mask-image:linear-gradient(to bottom,transparent,#000 var(--halo))}
    .poster>.foot::-webkit-scrollbar{display:none}
    .poster>.foot>:first-child{margin-top:auto}
  }
  /* Pinned to the right, but read from the left. */
  .poster>.foot-r{align-items:flex-start;text-align:left}
  /* Four corners. Everything on the poster is pinned to one of them, so a new
     block is a class, not a new rule. The right-hand pair is set right-aligned:
     they grow inward, away from their edge. */
  .poster>*{display:flex;flex-direction:column}
  .head,.foot{left:var(--pad);align-items:flex-start;text-align:left}
  .head-r,.foot-r{right:var(--pad);align-items:flex-end;text-align:right}
  .head,.head-r{top:var(--pad)}
  .foot,.foot-r{bottom:var(--pad)}
  /* A role that follows a sibling in the same corner sets its own space above,
     and so does one inside a box -- the first one too, since the box itself
     has no gap to give. */
  .poster>*>*+*{margin-top:var(--gap,0)}
  .poster .info{display:flex;flex-direction:column;align-items:flex-start}
  .poster .info>*{margin-top:var(--gap,0)}
  /* A block stays in the corner it was placed in at every width. The measures
     are in ch and capped against --fit, which is what keeps the two bottom
     corners from meeting. */
  /* A phone. Three columns will not fit at any size, so the poster stops being
     a poster laid over the page and becomes the top of it: the corners come
     down out of their fixed positions and are read first, top to bottom, and
     the spine follows, as wide as the margins allow.

     --poster-h is where the spine starts now, which the grid has to know to
     stay on the cells. */
  @media (max-width:__NARROW__px){
    :root{--pad:16px;--cell:calc((100vw - 2 * var(--pad)) * .72 / __COLS__)}
    .poster{position:relative;inset:auto;z-index:2;pointer-events:auto;
      display:flex;flex-direction:column}
    .poster>*{position:relative;left:auto;right:auto;top:auto;bottom:auto;
      width:auto;will-change:auto}
    /* The panel at the foot of the screen: the information, or an open
       lecture in its place. Its ground is not the panel's own: it is laid
       once, behind whichever of the two is up, and fades out ABOVE the panel.
       The words fade separately, inside the panel, so a line scrolled up has
       gone before it reaches the part of the ground the spine shows through
       -- when the two faded together, the last line and the spine overlapped.
       The top of the screen gets the same, smaller, so the spine does not
       meet the edge in a hard line. Both sit over the spine and under the
       head and the panel's words (main is below the poster; an open lecture
       is lifted over them inside main). */
    /* Two heights: the information's panel, and an open lecture's. --panel
       is whichever is up, so the ground behind it follows. */
    :root{--info-panel:200px;--lec-panel:440px;--panel:var(--info-panel);
      --halo:26px;--panel-fade:26px}
    body:has(.lec.open){--panel:var(--lec-panel)}
    main{padding-bottom:calc(var(--info-panel) + 24px + var(--post, 0px))}
    main::before,main::after{content:"";position:fixed;left:0;right:0;z-index:2;
      pointer-events:none}
    main::before{top:0;height:64px;background:linear-gradient(#66bf8c,rgb(102 191 140 / 0))}
    main::after{bottom:0;height:calc(var(--panel) + var(--panel-fade));
      background:linear-gradient(rgb(139 200 136 / 0),#8bc888 var(--panel-fade),#68c08d)}
    /* The top: the logo on the left, the title over the subtitle in the
       middle of the page, each on one line. Two equal outer columns are what
       keep the middle one centred on the page rather than on what is left
       beside the logo. The foot corner dissolves (display:contents) so its
       title and subtitle take the middle column and its info box leaves for
       the panel. The logo spans both rows and is taller than the two lines
       together; the second row takes what is left over, or the grid shares
       it out and the subtitle drifts away from the title. */
    .poster{display:grid;grid-template-columns:1fr auto 1fr;grid-template-rows:auto 1fr;
      column-gap:12px;align-items:start}
    /* It stays at the top while the spine scrolls under it, with no ground of
       its own: the spine runs on up to the top of the screen. Only the pieces take the pointer,
       so a tap in the gap still lands on the spine. */
    .poster{position:fixed;top:0;left:0;right:0;pointer-events:none;padding-bottom:0}
    .poster>*,.poster .info{pointer-events:auto}
    .poster>.head{grid-row:1 / span 2}
    .t-logo{--fs:44px}
    .poster>.foot{display:contents}
    .head-r,.foot-r{display:none}
    /* A line scrolled up fades over --info-fade; the first line sits
       --info-lead under the top of the solid ground. The fade is the longer,
       so the box reaches up past the solid ground by the difference, and
       there the words' fade and the ground's overlap a little -- traded for
       a smaller gap between the spine and the first line (the ground's fade
       plus the lead). */
    .poster .info{--info-fade:26px;--info-lead:0px;
      position:fixed;left:0;right:0;bottom:0;
      height:calc(var(--info-panel) + var(--info-fade) - var(--info-lead));
      padding:var(--info-fade) var(--pad) var(--pad);overflow-y:auto;scrollbar-width:none;
      -webkit-mask-image:linear-gradient(to bottom,transparent,#000 var(--info-fade));
      mask-image:linear-gradient(to bottom,transparent,#000 var(--info-fade))}
    .poster .info::-webkit-scrollbar{display:none}
    .poster .info>:first-child{margin-top:0}
    .poster .info>.t{--maxw:100%}
    body:has(.lec.open) .poster .info{visibility:hidden}
    /* The page itself does not scroll on a phone: the spine scrolls in main,
       which covers the screen, and the panel scrolls on its own beside it.
       When the page scrolled, the browser's bars came and went with it and
       the screen changed height under the panel; and with the panel's
       scroller inside the page's, a swipe on the panel just after a swipe on
       the spine was often taken as more of the page. Two scrollers side by
       side leave nothing to decide: a finger scrolls what it is on.

       The grid goes with the spine, so it is drawn on main and scrolls with
       its content (background-attachment:local). The spine starts just under
       the title. */
    :root{--main-top:4px}
    /* Nothing left over to scroll, either. body's min-height is 100vh, and
       on iOS 100vh is the screen with the bars away -- taller than the page
       with them showing, so the page could still be dragged up by the
       difference, taking the head off the top with it. Hence the head is
       fixed, too, rather than sticky: it no longer rides on the page at all. */
    html,body{height:100%;min-height:0;overflow:hidden;overscroll-behavior:none}
    .grid{display:none}
    main{position:fixed;inset:0;margin:0;overflow-y:auto;overscroll-behavior:contain;
      scrollbar-width:none;
      padding-top:calc(var(--poster-h, 0px) + var(--main-top) + var(--pre, 0px));
      background-image:var(--grid-img);background-size:var(--cell) var(--cell);
      background-attachment:local;
      background-position:calc(50% + var(--cell) / 2)
        calc(var(--poster-h, 0px) + var(--main-top) + var(--pre, 0px))}
    main::-webkit-scrollbar{display:none}
    .poster .info{overscroll-behavior:contain}
  }
  @media (max-width:__MID__px){
    __TYPECSS_SMALL__
  }
  /* The lens is read against the spine, so it shrinks with it, on the same
     slide and by the same share -- the feather too, or a smaller lens would
     come out softer. ?lens and ?feather still override both. */
  .lens{--lens:__LENS__;--feather:__FEATHER__}
  .lens{position:fixed;left:0;top:0;width:var(--lens,100px);height:var(--lens,100px);border-radius:50%;--lens-rgb:138 138 138;background:rgb(var(--lens-rgb));filter:blur(var(--feather,8px));
    mix-blend-mode:difference;pointer-events:none;z-index:100;transform:translate(-1000px,-1000px);will-change:transform;display:none}
  @media (hover:hover) and (pointer:fine){.lens{display:block}}
  /* ?bakedlens draws the same Gaussian into an image once instead of running
     the filter on every frame. It is cheaper -- a blend cannot be cached and
     the filter widens the patch of backdrop it has to read -- but the live
     filter is the one that looks right, so it is the one that ships. */
  .lens.baked{filter:none;border-radius:0;background:none no-repeat center/100% 100%;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><path d='M0 0H1M0 0V1' fill='none' stroke='%23cccccc' stroke-width='.05' stroke-dasharray='.14 .1'/></svg>");
    width:calc(var(--lens,100px) + 6 * var(--feather,8px));
    height:calc(var(--lens,100px) + 6 * var(--feather,8px))}
    width:calc(var(--lens,100px) + 6 * var(--feather,8px));
    height:calc(var(--lens,100px) + 6 * var(--feather,8px));
    background:radial-gradient(circle closest-side,rgb(var(--lens-rgb) / 1.000) 0%,rgb(var(--lens-rgb) / 1.000) 10%,rgb(var(--lens-rgb) / 1.000) 20%,rgb(var(--lens-rgb) / 1.000) 30%,rgb(var(--lens-rgb) / 0.995) 40%,rgb(var(--lens-rgb) / 0.948) 50%,rgb(var(--lens-rgb) / 0.758) 60%,rgb(var(--lens-rgb) / 0.411) 70%,rgb(var(--lens-rgb) / 0.125) 80%,rgb(var(--lens-rgb) / 0.019) 90%,rgb(var(--lens-rgb) / 0.001) 100%)}

</style>'''

LEC_CSS = '''.peek-flood{flood-color:var(--peek-green,#80C58A)}
  /* The lecture blocks. One per segment of the spine, parked at the middle of
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
    --side:calc(100vw - var(--tools,0px) - __COLS__ * var(--cell)
      - var(--spine-x, calc((100vw - var(--tools,0px) - __COLS__ * var(--cell)) / 2)));
    --lec-gap:48px}       /* between the spine and the block, at most */
  /* A block's own measures, wherever it is housed (see .sheet). */
  .lecs,.sheet{
    --lec-rise:10px;      /* how far a block travels as it arrives */
    --lec-under:28px;     /* Sign Up to the description, in an open block */
    --lec-top-open:36px;  /* the top of the screen to an open block's first line */
    --lec-lead:8px;
    --lec-halo:26px}   /* how far the type's glow reaches past its box */
  /* On a phone the blocks leave the spine for here: an open one is a panel
     that scrolls, and inside main it would be a scroller inside the spine's,
     so a swipe on it was taken as the spine's. Side by side, it is not. */
  .sheet{position:relative;z-index:3;
    /* as in .lecs: the unseen blocks take nothing; .lec.open takes it back */
    pointer-events:none}
  /* Every block starts on the same vertical line. That line is the widest the
     spine ever gets, not the width of this segment, so a narrow vertebra does
     not pull its block inboard of the others and the eight left edges stack. */
  /* The head straddles the segment's centre of mass, so three lines of type sit
     level with the middle of the shape they name. .more is taken out of the
     flow below it, which is what keeps the head still while the detail opens:
     the block's own height is the head's height and nothing else. */
  /* Three columns: the written one, the spine, the lectures. The lectures'
     column is the written one's mirror -- the same measure, --col, set in
     from the right edge by the same --pad the written one is set in from the
     left -- so the two sides of the spine are the same width. */
  .lec{position:absolute;left:100%;
    --lec-w:var(--col, calc(var(--side) - 2 * var(--pad)));
    margin-left:calc(var(--side) - var(--pad) - var(--lec-w));
    top:calc(var(--y) * 100%);
    width:var(--lec-w);
    opacity:0;transform:translateY(calc(-50% + var(--lec-rise)));
    transition:opacity var(--lec-off), transform var(--lec-off);
    will-change:opacity,transform;
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
  /* A closed detail is height:0 with its whole text overflowing it, and
     overflow counts toward how far the page scrolls. So a hover near the end
     of the page lengthened the page, the leave shortened it, and at the
     bottom the browser pulled the scroll back up each time: the spine rose
     and fell under the pointer. Closed, it is clipped -- but not its glow. */
  .lec:not(.open) .more{overflow:clip;overflow-clip-margin:var(--lec-halo)}
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
  .lec .more-in>*+*,.lec .scroll>*+*{margin-top:calc(var(--lec-lead) + var(--gap,0px))}
  .lec .more-in>:first-child,.lec .scroll>:first-child{margin-top:var(--gap,0px)}
  /* Each line's glow spills onto the line under it, and in document order the
     one underneath paints last and washes over the one above. Reversed: the
     first line keeps its edges and every glow falls behind what came before.
     .more carries a clip-path, so it is its own stacking context and the two
     inside it order among themselves. */
  .lec>*,.lec .more-in>*,.lec .scroll>*{position:relative}
  .lec .scroll>:nth-child(1){z-index:9}
  .lec .scroll>:nth-child(2){z-index:8}
  .lec .scroll>:nth-child(3){z-index:7}
  .lec .scroll>:nth-child(4){z-index:6}
  .lec .scroll>:nth-child(5){z-index:5}
  .lec>:nth-child(1){z-index:4}
  .lec>:nth-child(2){z-index:3}
  .lec>:nth-child(3){z-index:2}
  .lec>:nth-child(4){z-index:1}
  .lec .more-in>:nth-child(1){z-index:3}
  .lec .more-in>:nth-child(2){z-index:2}
  .lec .more-in>:nth-child(3){z-index:1}
  .lec>*+*{margin-top:calc(var(--lec-lead) + var(--gap,0px))}
  /* The numbers sit on the spine itself, dead centre of each segment, so a
     number and the photo it belongs to arrive in the same place. They are
     always up: they say there are eight of these before anything is hovered. */
  .t-lecno{position:absolute;left:calc(var(--nx) * 100%);
    top:calc(var(--ny) * 100%);transform:translate(-50%, -50%);
    opacity:.8;transition:opacity var(--lec-off)}
  .t-lecno.on{opacity:1;transition:opacity var(--lec-in) ease}
  /* The lecture's pictures: one above the other, each the full measure and
     its own shape. */
  .lec .lec-pics{display:grid;gap:8px;margin-top:calc(var(--lec-lead) + 14px)}
  .lec .lec-pics img{width:100%;height:auto;display:block}
  /* A speaker: the bio, then the portrait under it, uncropped. */
  .lec .lec-sp{margin-top:calc(var(--lec-lead) + 14px)}
  .lec .lec-sp .face{width:50%;height:auto;display:block;margin-top:12px}
  .lec .t{max-width:100%}
  .lec .t>*{max-width:100%}
  .lec.on{content-visibility:visible;opacity:1;transform:translateY(-50%);
    transition-duration:var(--lec-in),var(--lec-in)}
  /* An open block is something to read, copy from and click through, so it
     takes the pointer. A hovered one does not: it goes the moment the pointer
     leaves its segment, and it would only ever be caught half way. */
  .lec.open{pointer-events:auto}
  /* A link, not a button: the words underlined, the arrow after them not. */
  .lec .signup{display:block;width:max-content;color:inherit;text-decoration:none}
  .lec .signup .u{text-decoration:underline;text-decoration-thickness:1px;
    text-underline-offset:.18em}
  .lec .signup:focus-visible{outline:2px solid #f28030;outline-offset:3px}
  /* Once the column narrows, an open block's detail runs long enough to reach
     its neighbours, and a hovered neighbour lands on it. Whichever it lands
     on, the hovered one is on top: it is the one just asked for. Left to
     document order, a hover above the open block went under it. Beside the
     spine only -- on a phone the block is a sheet with its own place. */
  @media not all and (max-width:__NARROW__px){
    .lec.open{z-index:1}
    .lec.on:not(.open){z-index:2}
    /* An open block is pinned to the screen and takes its whole height: the
       head, the language and Sign Up at the top, level with the logo, and
       under them the rest, which scrolls on its own down to the foot of the
       screen. A scroll that reaches its end stops there rather than carrying
       on into the page, so the spine scrolls under a block that stays, and the
       block scrolls without moving the spine. --lecs-r is where .lecs ends on
       the screen, set by the script: fixed, the block no longer has .lecs to
       hang off. */
    .lec.open{position:fixed;left:var(--lecs-r,100%);top:0;height:100vh;
      padding-top:var(--lec-top-open);box-sizing:border-box;transform:none;
      display:flex;flex-direction:column;
      /* No transitions: the move from the segment to here is the script's
         (arrive()), which knows where the head was. */
      transition:none}
    .lec.open .more{transition:none}
    .lec.open>*{flex-shrink:0}
    /* The detail takes what is left of the screen, so nothing is measured
       here: --more-h is the beside-the-spine reveal's number, not this one's. */
    .lec.open .more{height:auto;flex:1 1 0;min-height:0;display:flex;flex-direction:column}
    .lec.open .more-in{flex:1 1 0;min-height:0;display:flex;flex-direction:column}
    .lec.open .more-in>:not(.scroll){flex-shrink:0}
    /* While another segment is hovered, that one's head is laid over the open
       block on a ground of the page's own green, drawn to the outline of the
       type and its glow (#peek-ground). Leaving the segment takes it away with
       the head. */
    html.peek .lec.on:not(.open){filter:url(#peek-ground)}
    /* The glow needs room at the scroller's sides, so the box reaches out by
       the halo and the padding takes it back. At the top it cannot: that room
       is Sign Up's, and text scrolled into it would run behind it. There the
       edge fades instead, once there is something scrolled up past it (.up,
       set by the script). The foot is the screen's own edge. */
    .lec.open .scroll{flex:1 1 0;min-height:0;overflow-y:auto;overscroll-behavior:contain;
      scrollbar-width:none;--ft:0px;
      margin-left:calc(-1 * var(--lec-halo));margin-right:calc(-1 * var(--lec-halo));
      padding:var(--lec-halo) var(--lec-halo) var(--pad);
      /* the first line's glow needs the halo above it too: the box starts
         that much higher, in the space under Sign Up, and the padding puts the
         words back --lec-under below it */
      margin-top:calc(var(--lec-under) - var(--lec-halo));
      -webkit-mask-image:linear-gradient(transparent,#000 var(--ft));
      mask-image:linear-gradient(transparent,#000 var(--ft))}
    .lec.open .scroll.up{--ft:var(--lec-halo)}
    .lec.open .scroll::-webkit-scrollbar{display:none}
    /* level with the date: its top is the block's first line's */
    .lec.open .lec-close{display:block;position:absolute;top:calc(var(--lec-top-open) - 2px);right:0;z-index:5;
      margin:0;padding:0 2px;border:0;background:none;cursor:pointer;line-height:0}
    .lec-close .t-lecx{--fs:__CLOSEFS__;--lh:.5;--w:300}   /* narrows with the type */
  }
  /* The phone's close button; beside the spine a click elsewhere does it. */
  .lec-close{display:none}
  /* On a phone the open lecture takes the panel at the foot of the screen, the
     one the information sits in the rest of the time: its when and who and
     title across the top with Sign Up and the close beside them, and the
     description under them; the panel scrolls as a whole. .more and its inner
     box step out of the way (display:contents) so the pieces inside them can
     be laid out on the panel's own grid. */
  @media (max-width:__NARROW__px){
    /* Laid out as the information's panel is: the first line --lec-top
       under the top of the solid ground, the box reaching up past it so a
       line scrolled up has the whole --halo to fade over. */
    .lec{--lec-top:6px;
      position:fixed;left:0;right:0;top:auto;bottom:0;width:auto;
      height:calc(var(--lec-panel) + var(--halo) - var(--lec-top));margin:0;
      padding:var(--halo) var(--pad) var(--pad);
      overflow-y:auto;scrollbar-width:none;overscroll-behavior:contain;
      /* no pointer-events here: all eight panels are stacked on the screen,
         seven of them unseen, and only the open one (.lec.open, above) may
         take a tap -- the rest would swallow every tap on the spine behind */
      -webkit-mask-image:linear-gradient(to bottom,transparent,#000 var(--halo));
      mask-image:linear-gradient(to bottom,transparent,#000 var(--halo));
      display:grid;grid-template-columns:1fr auto auto;
      grid-template-rows:auto auto auto auto auto;align-content:start;column-gap:12px;align-items:start}
    /* The panel changes in one frame. It used to rise and fade in, but the
       one it replaced -- the information, or the last lecture -- went at once,
       so every tap left the panel's ground empty for a quarter of a second:
       a flash between the two. */
    .lec,.lec.on{transform:none;transition:none}
    .lec::-webkit-scrollbar{display:none}
    /* over the segment numbers, which come later in the page and would
       otherwise show through */
    .lec.open{z-index:3}
    .lec .more,.lec .more-in{display:contents}
    .lec>.t-lecd{grid-area:1/1}
    .lec>.t-lecw{grid-area:2/1}
    .lec>.t-lect{grid-area:3/1/4/-1}   /* the title takes the full width */
    /* both span the date's row and the speaker's, so their height does not
       open the gap between the two */
    .lec .signup{grid-area:1/2/3/3;margin:0}
    .lec-close{grid-area:1/3/3/4;display:block;margin:0;padding:0 2px;border:0;
      background:none;cursor:pointer}
    .lec-close .t-lecx{--fs:26px;--lh:.8;--slabF:url(#bl-t20-s)}
    .lec .t-lecl{grid-area:4/1/5/-1}
    .lec .scroll{grid-area:5/1/6/-1;margin-top:var(--lec-lead)}
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
<div class="sheet"></div>
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
      nos.forEach((n,i)=>n&&n.classList.toggle('on',i===hot||i===open));
      // another segment hovered while one is open: its head is laid over the
      // open block on a ground of its own (html.peek)
      const pk=open!==-1&&hot!==-1&&hot!==open;
      document.documentElement.classList.toggle('peek',pk);
      if(pk)ground(lecs[hot]);}
    // The green under a peeking head is the page's own at that height: .bg's
    // gradient, which is fixed to the screen, read off at the head's middle.
    const BG=[[0,[0x66,0xBF,0x8C]],[.7,[0x92,0xCA,0x87]],[1,[0x68,0xC0,0x8D]]];
    function ground(l){if(!l)return;
      const b=l.parentNode.getBoundingClientRect();
      const t=Math.min(1,Math.max(0,(b.top+l.offsetTop)/innerHeight));
      const k=t<=BG[1][0]?0:1,[t0,c0]=BG[k],[t1,c1]=BG[k+1],f=(t-t0)/(t1-t0);
      document.documentElement.style.setProperty('--peek-green',
        'rgb('+c0.map((v,i)=>Math.round(v+(c1[i]-v)*f)).join(' ')+')');}
    // Opening a segment brings it to the middle of the screen. Only a click does
    // this — a hover that moved the page would move itself out from under the
    // cursor. The scroll is its own tween because scrollIntoView's smooth scroll
    // has neither a duration nor a curve to set, and the point here is slowness.
    const GLIDE=520, DEAD=24;   // ms end to end; px already near enough to leave alone
    // Starts slow, arrives slow. For a pure ease-in, swap in t=>t*t*t.
    const EASE=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
    const still=matchMedia('(prefers-reduced-motion: reduce)');
    let tween=null,dir=0;   // the glide's direction, -1 up or 1 down
    let lastWheel=-1e9,coast=false;
    // On a phone the sheet takes the bottom of the screen, so "the middle" is
    // the middle of what is left above it.
    const narrow=matchMedia('(max-width:__NARROW__px)'),root=document.documentElement;
    // The first segment sits too near the top of the page, and the last too near
    // the bottom, for any scroll to bring them to the middle. So the page is
    // lent the room: exactly as much above or below the spine as the segment
    // needs. Changing the room above moves everything under it, so the scroll
    // is corrected by what the segment moved and nothing on screen jumps; the
    // glide then starts from where the reader was.
    //
    // Lending only ever adds. Room that is on screen cannot be taken away
    // without the page jumping by that much -- open 01, then 02, and the room
    // 01 needed is still right there above the spine -- so what the segment
    // now open no longer needs is handed back by reclaim(), and only the part
    // of it out of sight.
    let pre=0,post=0,want=[0,0];
    function setRoom(p,q){
      pre=p;post=q;
      root.style.setProperty('--pre',p+'px');
      root.style.setProperty('--post',q+'px');}
    // Measured against the bottom of main, not the page's scroll height: an
    // open block hangs past the end of main, and counting what hangs there as
    // room already made lends the last segment too little to reach the middle.
    const main=document.getElementById('content');
    // On a phone the page does not scroll; main does (see the phone's CSS).
    // Every scroll here goes through these. main covers the screen, so a
    // point on the screen is a point in main's box either way.
    const inMain=()=>narrow.matches;
    const getY=()=>inMain()?main.scrollTop:scrollY;
    const setY=y=>{if(inMain())main.scrollTop=y;else scrollTo(0,y);};
    const viewH=()=>inMain()?main.clientHeight:innerHeight;
    const endY=()=>inMain()?main.scrollHeight:scrollY+main.getBoundingClientRect().bottom;
    const maxY=()=>inMain()?main.scrollHeight-main.clientHeight
                           :document.documentElement.scrollHeight-innerHeight;
    // Where the blocks live: beside the spine in .lecs, or on a phone in
    // .sheet, out of main (see .sheet).
    const home=document.querySelector('.lecs'),sheet=document.querySelector('.sheet');
    function house(){const box=narrow.matches?sheet:home;
      lecs.forEach(l=>{if(l&&l.parentNode!==box)box.appendChild(l);});}
    house();narrow.addEventListener('change',house);
    // The open block is fixed to the screen (see LEC_CSS), and takes its left
    // edge from where .lecs ends. The page does not scroll sideways, so this
    // only moves with the window.
    const edge=()=>root.style.setProperty('--lecs-r',home.getBoundingClientRect().right+'px');
    edge();addEventListener('resize',edge,{passive:true});
    // Opening beside the spine moves the block from its segment to the top of
    // the screen, and it goes there at once: the head is already showing, so
    // fading it out and in again flashed, and carrying it up read as a scroll.
    // Only the detail, which was not showing, fades in under it.
    function arrive(l){if(!l||still.matches)return;const m=l.querySelector('.more');
      if(m)m.animate([{opacity:0},{opacity:1}],{duration:520,easing:'cubic-bezier(.3,0,.2,1)'});}
    // whether an open block's scroller has anything scrolled up past it (.up)
    const ends=sc=>sc.classList.toggle('up',sc.scrollTop>1);
    const scrolls=lecs.map(l=>l&&l.querySelector('.scroll'));
    scrolls.forEach(sc=>sc&&sc.addEventListener('scroll',()=>ends(sc),{passive:true}));
    // `at` is where on the screen the segment's centre is to land.
    function lend(g,at){
      const b=g.getBoundingClientRect();
      const y=getY()+(b.top+b.bottom)/2-pre;      // the centre, with nothing lent
      const end=endY()-pre-post;
      const p=Math.max(0,Math.round(at-y));
      const q=Math.max(0,Math.round(y-at+viewH()-end));
      want=[p,q];
      if(p<=pre&&q<=post)return;
      setRoom(Math.max(p,pre),Math.max(q,post));
      setY(getY()+g.getBoundingClientRect().top-b.top);}
    // Taken back only as far as it is out of sight -- above the top of the
    // screen for the room above, below the bottom for the room below -- and
    // never below what the open segment still needs, so the page never moves
    // under the reader to get it back. Runs whenever scrolling settles.
    function reclaim(){
      if(tween||(!pre&&!post))return;
      const [wp,wq]=open===-1?[0,0]:want;
      const y=Math.floor(getY());
      const p=Math.max(wp,pre-Math.max(0,y));
      const q=Math.max(wq,post-Math.max(0,Math.floor(endY()-getY()-viewH())));
      if(p===pre&&q===post)return;
      const dy=p-pre;
      setRoom(p,q);if(dy)setY(getY()+dy);}
    addEventListener('scrollend',reclaim,{passive:true});
    main.addEventListener('scrollend',reclaim,{passive:true});
    // Closing gives ALL the lent room back. What is out of sight goes at once
    // (reclaim); what is on screen is let out over a glide, so the spine
    // settles back where it began rather than jumping there -- or, as it did
    // before, staying off where the first or last segment was brought to.
    let giving=null;
    function release(){
      tween=null;reclaim();
      if(!pre&&!post)return;
      if(still.matches){setRoom(0,0);return;}
      const p0=pre,q0=post,t0=performance.now(),id={};giving=id;
      (function step(now){
        if(giving!==id||open!==-1)return;   // opened again: that lends anew
        const k=Math.min(1,(now-t0)/GLIDE),e=1-EASE(k);
        setRoom(Math.round(p0*e),Math.round(q0*e));
        if(k<1)requestAnimationFrame(step);})(t0);}
    function glide(g,l){
      const b=g.getBoundingClientRect();
      // on a phone the head is stuck over the top of the screen and the block
      // is the panel over the foot, so the segment goes to the middle of what
      // is left between them
      const top=narrow.matches?poster.offsetHeight:0;
      const at=top+(viewH()-top-(narrow.matches?
        parseFloat(getComputedStyle(root).getPropertyValue('--lec-panel'))||0:0))/2;
      lend(g,at);
      const c=g.getBoundingClientRect();
      const to=Math.max(0,Math.min(getY()+(c.top+c.bottom)/2-at,maxY()));
      const from=getY(),d=to-from;
      if(Math.abs(d)<DEAD)return false;   // nothing moved, so nothing to hold
      if(still.matches){setY(to);return true;}
      // The tween below is a main-thread scroll: every frame the whole paint
      // pipeline has to finish inside that frame, and it is moving about 32px
      // a frame across 9,300 elements. The browser's own smooth scroll runs on
      // the compositor, which can move tiles it has already rasterised -- at
      // the price of the duration and the curve, which it does not let you set.
      if(/[?&]nativeglide/.test(location.search)){
        (inMain()?main:window).scrollTo({top:to,behavior:'smooth'});return true;}
      const t0=performance.now(),id={};tween=id;dir=Math.sign(d);
      coast=t0-lastWheel<GAP;             // clicked mid-coast
      (function step(now){
        if(tween!==id)return;               // the reader took the scroll back
        const k=Math.min(1,(now-t0)/GLIDE);
        setY(from+d*EASE(k));
        if(k<1)requestAnimationFrame(step);else{tween=null;reclaim();}})(t0);
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
      // a finger is never hovering: its moves are a scroll, and a block that
      // came up under a scrolling thumb would be one nobody asked for
      if(e.pointerType==='touch')return;
      if(held&&Math.hypot(e.clientX-px,e.clientY-py)<=3)return;   // the glide's own
      held=false;px=e.clientX;py=e.clientY;
      if(!queued){queued=true;requestAnimationFrame(look);}},{passive:true});
    addEventListener('pointerleave',()=>{held=false;px=py=-1;
      if(PINNED&&open!==-1)return;
      if(hot!==-1){hot=-1;sync();}});
    // A trackpad keeps coasting after the fingers lift, and near the end of
    // the page the wheel events go on arriving with nothing left to scroll. The
    // segments down there are reached by scrolling, so a click on one lands in
    // that coast -- and a glide that any wheel event cancelled was cancelled
    // before it moved, whichever way it was going.
    //
    // A coast is one unbroken stream of events. So the stream that was already
    // running at the click is the reader's last scroll, not a new one, and is
    // let run out; what takes the scroll back is a wheel after a break in it,
    // and then only one going against the glide.
    const GAP=120;   // ms between wheel events that still counts as one stream
    addEventListener('wheel',e=>{
      const now=performance.now(),gap=now-lastWheel;lastWheel=now;
      if(tween){
        if(coast&&gap<GAP)return;
        coast=false;
        if(Math.sign(e.deltaY)===dir)return;}
      tween=null;held=false;},{passive:true});
    ['touchstart','keydown'].forEach(e=>
      addEventListener(e,()=>{tween=null;held=false;},{passive:true}));
    segs.forEach((g,i)=>{
      // a finger does not hover, so on a phone what is lit is what is open
      g.addEventListener('click',e=>{open=(open===i?-1:i);hot=narrow.matches?open:i;
        sync();                        // renders the block; only then is it measurable
        if(open===i&&!narrow.matches)arrive(lecs[i]);
        if(open===i){note(mores[i]);const sc=scrolls[i];
          if(sc){sc.scrollTop=0;setTimeout(()=>ends(sc),300);}}
        if(open===i){px=e.clientX;py=e.clientY;held=glide(g,lecs[i]);}
        else release();
        e.stopPropagation();});
    });
    // The open block takes clicks now -- to select its text, to follow its
    // link -- and none of them should reach the document and close it.
    lecs.forEach(l=>{if(!l)return;
      l.addEventListener('click',e=>e.stopPropagation());
      // the phone's panel has its own way out
      l.querySelector('.lec-close').addEventListener('click',e=>{e.stopPropagation();
        open=-1;hot=-1;sync();release();});});
    // Where the poster ends is where the spine, and the grid under it, begin.
    // (The poster used to fill the whole first screen, title pushed down to
    // its foot; with the heading now at the top it is simply read in order.)
    const poster=document.querySelector('.poster');
    function intro(){
      if(!narrow.matches){root.style.removeProperty('--poster-h');return;}
      root.style.setProperty('--poster-h',poster.offsetHeight+'px');
    }
    addEventListener('resize',()=>{if(open!==-1)note(mores[open]);},{passive:true});
    intro();
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(intro);
    addEventListener('resize',intro,{passive:true});
    // A click outside closes everything, and it says where the pointer is:
    // a click does not have to be preceded by a move, so its own coordinates
    // are the only ones that are certainly current. Pinned, it closes nothing:
    // clicking the open segment again is the way back out.
    document.addEventListener('click',e=>{if(PINNED)return;
      open=-1;held=false;px=e.clientX;py=e.clientY;look();sync();release();});
    sync();
  })();
  const lens=document.getElementById('lens'), q=new URLSearchParams(location.search);
  if(q.get('lens'))lens.style.setProperty('--lens',q.get('lens')+'px');
  if(q.get('feather'))lens.style.setProperty('--feather',q.get('feather')+'px');
  if(q.get('lenscolor')){const h=q.get('lenscolor').replace('#','');
    lens.style.setProperty('--lens-rgb',
      [0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(' '));}
  if(q.has('bakedlens'))lens.classList.add('baked');
  if(q.has('scrollgrain')){const g=document.querySelector('.grain');if(g)g.classList.add('scroll');}
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
  if(q.has('base')){const b=document.querySelector('.spine.base');if(b)b.style.willChange='transform';}
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
    title='Spinal Memory',                             # not on the page for now
    tag='[Research & Practice on\nNon-Human Animals]',  # likewise; a chip
    desc='[Intro]\n'
         'Spinal Memory, the 4th issue of te magazine, grew out of a reflection on '
         'the imagining of non-human animals\u2014examining how humans control, domesticate, '
         'and make use of animal bodies, while also trying to sketch out a new, open-ended '
         'relationship not yet fixed in form, one that reaches toward the future. As an '
         'extension of this issue, we are launching our first online lecture series, '
         'inviting 9 speakers to give 8 online lectures.'
         '\n\n'
         'Each speaker approaches this theme in a completely different way: years of '
         'companionship and careful field observation, or history, design, writing, '
         'moving image, archives, and data. How should we '
         'approach, investigate, or simply imagine what it might mean to live alongside '
         'non-human animals? And from there, how do we turn that into practice and research? '
         'Weaving together text and practice, each speaker unfolds their own way of working, '
         'sometimes out in the open landscapes of pasture and forest, sometimes back at a '
         'worktable or in an archive.',
    facts='[Cost]\n$10 USD / \u00a566 CNY per lecture'
         '\n\n'
         '[Duration]\n1.5 hours per lecture (including Q&A)'
         '\n\n'
         '[Capacity]\nLimited to 50 participants per lecture'
         '\n\n'
         '[Note]\nRegistrants will receive a replay link valid for one month after the '
         'lecture; replays do not include the live Q&A'
         '\n\n'
         '[Digital Reading Room]\n'
         'For our participants, alongside the lecture series, we will also build a Digital Reading Room, '
         'gathering further readings and moving-image material prepared by the speakers. '
         'The conversation between creators, scholars, and audiences won\u2019t end with a '
         'single talk. It will keep opening up through ongoing reading, response, and '
         'addition, and through thinking together about our sympoiesis with all living '
         'things.',
)


# tag -> the element each role's copy is wrapped in. The logo is a drawing, the
# description is two paragraphs, so neither is a single text element.
# Where a [[link]] in the copy goes, by its text.
LINKS = {'Digital Reading Room': '#',
         'ZOO Index': 'https://zooindex.net/',
         'Institute of Critical Zoologists': 'https://www.criticalzoologists.org/main.html',
         'Interspecies Library': 'https://interspecieslibrary.com/'}

ROLE_TAG = dict(logo='div', title='h1', tag='div', info='p', desc='div', facts='div',
                lecd='p', lecw='p', lect='p', lecl='div', lecb='div', lecbio='div',
                lecno='p', lecs='p', lecx='span')


def copy_html(role, text):
    """Plain text in, markup out. Only the roles wrapped in a div can hold
    paragraphs; the rest are a single text element, so every newline is a break.
    In a div, a paragraph that opens with a `[Label]` line opens with a chip,
    `[[text]]` anywhere is a link to LINKS[text], and `*text*` is italic."""
    esc = lambda t: t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    link = lambda t: re.sub(r'\[\[(.+?)\]\]', lambda m: f'<a href="{LINKS.get(m[1], "#")}" '
                            f'target="_blank" rel="noopener">{m[1]}</a>', t)
    paras = [p for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    em = lambda t: re.sub(r'\*([^*]+)\*', r'<em>\1</em>', t)
    br = lambda p: '<br>'.join(em(link(esc(line))) for line in p.split('\n'))
    def para(p):
        whole = re.fullmatch(r'\[([^\[\]]+)\]', p.strip())
        if whole:
            return f'<p class="chip"><span>{br(whole[1])}</span></p>'
        head, _, rest = p.strip().partition('\n')
        m = re.fullmatch(r'\[([^\[\]]+)\]', head.strip())
        if m:
            return (f'<p class="chip"><span>{esc(m[1])}</span></p>'
                    + (f'<p>{br(rest)}</p>' if rest.strip() else ''))
        return f'<p>{br(p)}</p>'
    if ROLE_TAG[role] == 'div':
        return ''.join(para(p) for p in paras)
    return '<br>'.join(br(p) for p in paras)


def corners():
    """One div per corner that has anything in it, holding its roles in order."""
    out = []
    for corner in CORNERS:
        roles = at_corner(corner)
        if not roles:
            continue
        inner, box = '', None
        for r in roles:
            b = ROLES[r].get('box')
            if b != box:
                inner += ('</div>' if box else '') + (f'<div class="{b}">' if b else '')
                box = b
            inner += (layers(ROLE_TAG[r], r, LOGO, **{'aria-label': 'te'}) if r == 'logo'
                      else layers(ROLE_TAG[r], r, copy_html(r, COPY[r])))
        inner += '</div>' if box else ''
        out.append(f'  <div class="{corner}">{inner}</div>')
    return '\n'.join(out)


LEC_IMAGES = 'images/lectures'
LEC_IMAGE_MAX = 1400   # px, the long side of the copy the page loads
LEC_FACE_MAX = 800     # a portrait is shown at half the measure, uncropped


def web_copy(path, web, size):
    """The original as an sRGB JPEG no longer than `size` on its long side.
    Print originals come in CMYK, and a plain convert() gets their colours
    wrong; their own ICC profile is the way across."""
    import io
    from PIL import Image, ImageCms, ImageOps
    im = ImageOps.exif_transpose(Image.open(path))
    icc = im.info.get('icc_profile')
    if im.mode == 'CMYK' and icc:
        im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                       ImageCms.createProfile('sRGB'), outputMode='RGB')
    im = im.convert('RGB')
    im.thumbnail((size, size), Image.LANCZOS)
    os.makedirs(os.path.dirname(web), exist_ok=True)
    im.save(web, quality=84, optimize=True, progressive=True)


def lec_img(name, size=None, **attrs):
    """An <img> with its own width and height on it, so the box is the right
    shape before the file arrives: the detail's height is measured to open it,
    and an image that loaded later would push its bottom off. None if the file
    is not there yet -- the lecture goes up without it."""
    from PIL import Image
    path = os.path.join(REPO, LEC_IMAGES, name)
    if not os.path.exists(path):
        print(f'  missing {LEC_IMAGES}/{name} -- left out')
        return None
    # Whatever size the file comes in, the page gets a copy no longer than
    # LEC_IMAGE_MAX on its long side, made here and remade when the original
    # changes -- so an original can go in straight off the camera.
    # The copy's name is the original's, folder and all, lower-cased with
    # anything but letters and digits made a hyphen: no spaces in a URL.
    slug = re.sub(r'[^a-z0-9]+', '-', os.path.splitext(name)[0].lower()).strip('-')
    web = os.path.join(REPO, LEC_IMAGES, 'web', slug + '.jpg')
    if not os.path.exists(web) or os.path.getmtime(web) < os.path.getmtime(path):
        web_copy(path, web, size or LEC_IMAGE_MAX)
    w, h = Image.open(web).size
    src = os.path.relpath(web, REPO)
    extra = ''.join(f' {k}="{v}"' for k, v in attrs.items())
    return (f'<img src="{src}" width="{w}" height="{h}" alt="" '
            f'loading="lazy" decoding="async"{extra}>'), w / h


def lec_extra(lec):
    """The pictures and the speakers, under the description."""
    out = ''
    pics = [p for p in (lec_img(n) for n in lec.get('pics', [])) if p]
    if pics:
        out += '<div class="lec-pics">' + ''.join(t for t, _ in pics) + '</div>'
    # One chip over the lot -- Speaker, or Speakers when there are two -- on
    # the first bio, as the Intro's is on the description.
    sps = lec.get('speakers', [])
    for k, sp in enumerate(sps):
        face = sp.get('face') and lec_img(sp['face'], size=LEC_FACE_MAX, **{'class': 'face'})
        chip = ('[Speakers]\n' if len(sps) > 1 else '[Speaker]\n') if k == 0 else ''
        out += ('<div class="lec-sp">'
                + layers('div', 'lecbio', copy_html('lecbio', chip + sp.get('bio', '')))
                + (face[0] if face else '') + '</div>')
    return out


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
        # A hover is worth the four things that tell you which lecture this is;
        # everything else waits inside .more, which only an open segment shows.
        # The number is not here — it sits on the segment, up in its own corner.
        out.append(
            f'<div class="lec" data-lec="{i}" style="--y:{cy:.4f}">'
            + layers('p', 'lecd', copy_html('lecd', lec['when'] + '\u2002'
                                            + lec.get('time', TIME)))
            + layers('p', 'lecw', copy_html('lecw', lec['who']))
            + layers('p', 'lect', copy_html('lect', lec['what']))
            # the language is a chip, and Sign Up comes straight under it: both
            # stay put while what is below them scrolls
            + '<div class="more"><div class="more-in">'
            + layers('div', 'lecl', copy_html('lecl', f"[{lec['lang']}]"))
            + f'<a class="signup" href="{lec.get("signup", SIGNUP)}" target="_blank" '
              f'rel="noopener">'
              + layers('p', 'lecs', '<span class="u">Sign up</span>\u2009\u2197') + '</a>'
            + '<div class="scroll">'
            + layers('div', 'lecb', copy_html('lecb', lec['about']))
            + lec_extra(lec)
            + '</div>'
            + '</div></div>'
            # the same five layers as every other word, so it glows as they do
            + '<button class="lec-close" type="button" aria-label="Close">'
            + layers('span', 'lecx', '\u00d7') + '</button>'
            + '</div>')
    return '\n'.join(out)


TOOLS_CSS = '.tools{position:fixed;right:0;top:0;bottom:0;z-index:200;width:272px;overflow:auto;\n    background:#141614;color:#ECEEE9;font:11px/1.4 var(--font-sans);letter-spacing:.04em;\n    padding-bottom:18px;display:none}\n  .tools.on{display:block}\n  html.has-tools{--tools:272px}\n  .tools h3{margin:0;padding:8px 12px;font-size:10px;font-weight:600;letter-spacing:.14em;\n    text-transform:uppercase;background:#1D201D;color:#9BA39A;position:sticky;top:0}\n  .tools section{padding:7px 12px;border-bottom:1px solid #2A2E2A;display:grid;gap:5px}\n  .tools .f{display:grid;grid-template-columns:1fr 4.4em;gap:7px;align-items:center}\n  .tools label{color:#C8D4C2}\n  .tools input,.tools select{background:#0D0F0D;border:1px solid #2A2E2A;color:#ECEEE9;\n    font:inherit;padding:3px 4px;border-radius:3px;width:100%}\n  .tools input[type=number]{text-align:right}\n  .tools input[type=range]{grid-column:1/-1;accent-color:#C8D4C2;padding:0;border:0}\n  .tools textarea{width:100%;height:220px;background:#0D0F0D;color:#C8D4C2;\n    border:1px solid #2A2E2A;border-radius:3px;font:10px/1.45 ui-monospace,Menlo,monospace;\n    padding:6px;resize:vertical}\n  .tools .hint{color:#6E766C;font-size:9.5px;line-height:1.35}'


PANEL_JS = '(function(){\n  if(!/[?&]tools/.test(location.search)) return;\n  const D = __DATA__;\n  D.all = Object.assign({}, D.roles, D.text);\n  D.order = Object.keys(D.all);\n\n  // The same rule as steps()/types() in build.py: every text step is the base\n  // resized, and only tracking and leading are walked with the size. Kept in\n  // step with it by hand — if the rule there changes, it changes here.\n  function derive() {\n    D.steps = {mark: D.markStep};\n    D.type = {mark: D.markType};\n    D.back = {mark: back(D.markBack)};\n    Object.entries(D.sizes).forEach(([n, size]) => {\n      const d = Math.min(size[0], D.walkStop) - D.baseSize;\n      D.steps[n] = {size, soft: D.base.soft, glow: D.base.glow,\n                    bloom: D.base.bloom, solid: D.base.solid};\n      D.type[n] = {weight: D.base.weight,\n                   ls: +(D.base.ls - D.track * d).toFixed(4),\n                   lh: +(D.base.lh - D.lead * d).toFixed(3)};\n      D.back[n] = back(D.baseBack);\n    });\n  }\n  // the backlight\'s opacities are its own; its colour is the page\'s\n  const back = b => Object.assign({}, b, {slab: [D.blc, b.slab], glow: [D.blc, b.glow]});\n  derive();\n  const redraw = () => { derive(); apply(); Object.keys(D.steps).forEach(paintBack); dump(); };\n  const panel = document.getElementById(\'tools\');\n  panel.classList.add(\'on\');\n  document.documentElement.classList.add(\'has-tools\');\n\n  const $ = (t, a = {}, kids = []) => {\n    const el = document.createElement(t);\n    for (const k in a) k === \'text\' ? el.textContent = a[k] : el.setAttribute(k, a[k]);\n    kids.forEach(c => el.appendChild(c));\n    return el;\n  };\n  const field = (box, label, input) => {\n    box.appendChild($(\'div\', {class: \'f\'}, [$(\'label\', {text: label}), input]));\n    return input;\n  };\n  const num = (v, min, max, step) => $(\'input\', {type: \'number\', value: v, min, max, step});\n  const slider = (box, v, min, max, step) => {\n    const r = $(\'input\', {type: \'range\', min, max, step, value: v});\n    box.appendChild(r); return r;\n  };\n  const colour = (v, onset) => {\n    const el = $(\'input\', {type: \'color\', value: v});\n    el.oninput = e => onset(e.target.value);\n    return el;\n  };\n\n  // The backlight is one SVG filter per step, built by build.py and not\n  // rebuildable from here -- but every number in it lives on an attribute that\n  // takes a new value in place: a morphology radius, two deviations, a matrix\n  // and two floods. Only `stack` needs nodes added or removed. The radii are in\n  // em of the step\'s own size, so each of a step\'s two filters (poster, and the\n  // small-screen one) is painted from its own font size.\n  function paintBack(name) {\n    const b = D.back[name], st = D.steps[name];\n    [[st.size[0], \'bl-\' + name], [st.size[1], \'bl-\' + name + \'-s\']].forEach(([fs, id]) => {\n      const f = document.getElementById(id);\n      if (!f) return;\n      const q = k => f.querySelector(\'[data-bl="\' + k + \'"]\');\n      q(\'dilate\').setAttribute(\'radius\', (b.dilate * fs).toFixed(2));\n      q(\'merge\').setAttribute(\'stdDeviation\', (b.merge * fs).toFixed(2));\n      q(\'halo\').setAttribute(\'stdDeviation\', (b.halo * fs).toFixed(2));\n      q(\'hard\').setAttribute(\'values\',\n        \'0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 \' + b.hard + \' \' + (-b.hard / 2));\n      [\'slab\', \'glow\'].forEach(k => {\n        q(k).setAttribute(\'flood-color\', b[k][0]);\n        q(k).setAttribute(\'flood-opacity\', b[k][1]);\n      });\n      // same curve as stack_table() in build.py\n      const n = Math.max(1, Math.round(b.stack)), S = 64, v = [];\n      for (let k = 0; k <= S; k++) v.push((1 - Math.pow(1 - k / S, n)).toFixed(4));\n      q(\'stack\').firstElementChild.setAttribute(\'tableValues\', v.join(\' \'));\n    });\n  }\n\n  const pick = (v, opts) => {\n    const sel = $(\'select\');\n    opts.forEach(o => {\n      const opt = $(\'option\', {value: o});\n      opt.textContent = o;\n      if (o === v) opt.selected = true;\n      sel.appendChild(opt);\n    });\n    return sel;\n  };\n\n  // The same rule as copy_html in build.py: a blank line starts a paragraph, a\n  // single newline is a break, and only the div-wrapped roles take paragraphs.\n  function copyHtml(role, text) {\n    const esc = t => t.replace(/&/g, \'&amp;\').replace(/</g, \'&lt;\').replace(/>/g, \'&gt;\');\n    const paras = text.trim().split(/\\n\\s*\\n/).filter(p => p.trim());\n    const link = t => t.replace(/\\[\\[(.+?)\\]\\]/g, (_, x) =>\n      \'<a href="\' + (D.links[x] || \'#\') + \'" target="_blank" rel="noopener">\' + x + \'</a>\');\n    const em = t => t.replace(/\\*([^*]+)\\*/g, \'<em>$1</em>\');\n    const br = p => p.split(\'\\n\').map(l => em(link(esc(l)))).join(\'<br>\');\n    const para = p => { const t = p.trim(), n = t.indexOf(\'\\n\');\n      const w = t.match(/^\\[([^\\[\\]]+)\\]$/);\n      if (w) return \'<p class="chip"><span>\' + br(w[1]) + \'</span></p>\';\n      const head = n < 0 ? t : t.slice(0, n), rest = n < 0 ? \'\' : t.slice(n + 1);\n      const m = head.trim().match(/^\\[([^\\[\\]]+)\\]$/);\n      return m ? \'<p class="chip"><span>\' + esc(m[1]) + \'</span></p>\'\n                 + (rest.trim() ? \'<p>\' + br(rest) + \'</p>\' : \'\')\n               : \'<p>\' + br(p) + \'</p>\'; };\n    return D.tag[role] === \'div\'\n      ? paras.map(para).join(\'\')\n      : paras.map(br).join(\'<br>\');\n  }\n  function setCopy(role) {\n    const el = document.querySelector(\'.t-\' + role);\n    if (!el) return;\n    const html = copyHtml(role, D.copy[role]);\n    [...el.children].forEach(layer => layer.innerHTML = html);\n  }\n\n  // The one place a role\'s numbers reach the page. Corners are re-filled in the\n  // declared order so moving one role never reshuffles the others.\n  function apply() {\n    D.order.forEach(role => {\n      const r = D.all[role], st = D.steps[r.step], c = D.sets[r.set];\n      document.querySelectorAll(\'.t-\' + role).forEach(el => {\n      const s = el.style;\n      s.setProperty(\'--fs\', st.size[0] + \'px\');\n      s.setProperty(\'--soft\', st.soft + \'px\');\n      s.setProperty(\'--solid\', st.solid == null ? 1 : st.solid);\n      s.setProperty(\'--glowR\', st.glow + \'em\');\n      s.setProperty(\'--bloomR\', st.bloom + \'px\');\n      s.setProperty(\'--slabF\', \'url(#bl-\' + r.step + \')\');\n      // 字重、字距、行距属于字号档，不属于角色——换档要整套跟过去\n      const ty = D.type[r.step] || {};\n      s.setProperty(\'--w\', ty.weight);\n      s.setProperty(\'--ls\', (r.ls ?? ty.ls) + \'em\');\n      s.setProperty(\'--lh\', r.lh ?? ty.lh);\n      s.setProperty(\'--ink\', c.ink);\n      s.setProperty(\'--glow\', c.glow);\n      s.setProperty(\'--bloom\', c.bloom);\n      s.setProperty(\'--gap\', (r.gap || 0) + \'px\');\n      s.setProperty(\'--maxw\', r.width ? r.width + \'ch\' : \'var(--fit)\');\n      });\n    });\n    // spacing and size both move the detail\'s height, and the reveal animates\n    // to a number that was measured before this edit\n    if (window.__lecMeasure) window.__lecMeasure();\n    D.corners.forEach(corner => {\n      const box = document.querySelector(\'.\' + corner);\n      if (!box) return;\n      Object.keys(D.roles).filter(role => D.roles[role].at === corner)\n             .forEach(role => { const b = D.roles[role].box;\n               (b && box.querySelector(\'.\' + b) || box)\n                 .appendChild(document.querySelector(\'.t-\' + role)); });\n    });\n  }\n\n  Object.entries(D.all).forEach(([role, r]) => {\n    const pinned = role in D.roles;\n    panel.appendChild($(\'h3\', {text: role + (pinned ? \'\' : \' · 讲座\')}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n\n    field(box, \'字号档\', pick(r.step, Object.keys(D.steps)))\n      .onchange = e => { r.step = e.target.value; apply(); dump(); };\n    if (pinned) field(box, \'位置\', pick(r.at, D.corners))\n      .onchange = e => { r.at = e.target.value; apply(); dump(); };\n    field(box, \'配色\', pick(r.set, Object.keys(D.sets)))\n      .onchange = e => { r.set = e.target.value; apply(); dump(); };\n\n    const g = field(box, \'上方间距 px\', num(r.gap || 0, 0, 160, 2));\n    const gr = slider(box, r.gap || 0, 0, 160, 2);\n    const setGap = v => { r.gap = +v; g.value = v; gr.value = v; apply(); dump(); };\n    g.oninput = e => setGap(e.target.value);\n    gr.oninput = e => setGap(e.target.value);\n\n    if (role in D.copy) {\n      box.appendChild($(\'div\', {class: \'hint\', text: \'文案：空行分段，单个换行是换行\'}));\n      const ta = document.createElement(\'textarea\');\n      ta.value = D.copy[role];\n      ta.rows = role === \'desc\' ? 8 : 4;\n      ta.spellcheck = false;\n      ta.style.cssText = \'height:auto;font:10px/1.5 var(--font-sans)\';\n      box.appendChild(ta);\n      ta.oninput = () => { D.copy[role] = ta.value; setCopy(role); dump(); };\n    }\n\n    const w = field(box, \'宽度 ch · 0=不限\', num(r.width || 0, 0, 90, 1));\n    const wr = slider(box, r.width || 0, 0, 90, 1);\n    const setW = v => { r.width = +v; w.value = v; wr.value = v; apply(); dump(); };\n    w.oninput = e => setW(e.target.value);\n    wr.oninput = e => setW(e.target.value);\n  });\n\n  // A step is shared by every role that names it, so these move type all over\n  // the poster at once. soft is the blur on the ink layer -- the one that\n  // decides whether small type is legible -- and glow and bloom are the haze\n  // around it. The slab filter is built at build time from `size`, so changing\n  // size here moves the type without moving its silhouette: rebuild to see it.\n  // One section, not one per step: the ramp has a single hand-set size in it.\n  {\n    panel.appendChild($(\'h3\', {text: \'基准 t\' + D.baseSize}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    const B = D.base;\n    knob(\'字距 em · ls\', -.12, .3, .005, () => B.ls, v => B.ls = v);\n    knob(\'行距 · lh\', .6, 2, .01, () => B.lh, v => B.lh = v);\n    knob(\'字重\', 100, 700, 50, () => B.weight, v => B.weight = v);\n    knob(\'模糊 px · soft\', 0, 4, .02, () => B.soft, v => B.soft = v);\n    knob(\'实心度 · solid\', 0, 1, .02, () => B.solid, v => B.solid = v);\n    knob(\'内发光 em · glow\', 0, 3, .01, () => B.glow, v => B.glow = v);\n    knob(\'外发光 px · bloom\', 0, 40, .1, () => B.bloom, v => B.bloom = v);\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'其余字号由此算出。下面两个是阶梯的斜率：每大 1px，字距和行距各收回多少。\'}));\n    knob(\'字距斜率 · TRACK\', 0, .04, .0005, () => D.track, v => D.track = v);\n    knob(\'行距斜率 · LEAD\', 0, .06, .0005, () => D.lead, v => D.lead = v);\n  }\n\n  // The backlight. Radii in em, so the base\'s numbers are the whole ramp.\n  [[\'基准 背光\', D.baseBack], [\'mark 背光\', D.markBack]].forEach(([title, b]) => {\n    panel.appendChild($(\'h3\', {text: title}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    knob(\'实色不透明\', 0, 1, .02, () => b.slab, v => b.slab = v);\n    knob(\'晕色不透明\', 0, 1, .02, () => b.glow, v => b.glow = v);\n    knob(\'外扩 em · dilate\', 0, .4, .005, () => b.dilate, v => b.dilate = v);\n    knob(\'合并 em · merge\', 0, .3, .005, () => b.merge, v => b.merge = v);\n    knob(\'晕开 em · halo\', 0, .8, .005, () => b.halo, v => b.halo = v);\n    knob(\'叠加次数 · stack\', 1, 24, 1, () => b.stack, v => b.stack = v);\n    knob(\'切边硬度 · hard\', .5, 12, .1, () => b.hard, v => b.hard = v);\n  });\n\n  // ONE colour, for every backlight on the page. Per-step would only ever\n  // produce four shades of almost-the-same-yellow lit side by side.\n  {\n    panel.appendChild($(\'h3\', {text: \'背光颜色 · 全局\'}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    field(box, \'颜色\', colour(D.blc, v => { D.blc = v; redraw(); }));\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'整页所有背光共用这一个颜色。浓淡分别在上面两节的不透明度里调。\'}));\n  }\n\n  {\n    panel.appendChild($(\'h3\', {text: \'mark · 字号档\'}));\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const knob = (label, min, max, step, read, write) => {\n      const n = field(box, label, num(read(), min, max, step));\n      const r = slider(box, read(), min, max, step);\n      const set = v => { write(+v); n.value = v; r.value = v; redraw(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    const S = D.markStep, T = D.markType;\n    knob(\'字号 px\', 8, 200, .5, () => S.size[0], v => S.size[0] = v);\n    knob(\'字距 em · ls\', -.12, .3, .005, () => T.ls, v => T.ls = v);\n    knob(\'行距 · lh\', .6, 2, .01, () => T.lh, v => T.lh = v);\n    knob(\'字重\', 100, 700, 50, () => T.weight, v => T.weight = v);\n    knob(\'模糊 px · soft\', 0, 4, .02, () => S.soft, v => S.soft = v);\n    knob(\'实心度 · solid\', 0, 1, .02, () => S.solid, v => S.solid = v);\n    knob(\'内发光 em · glow\', 0, 3, .01, () => S.glow, v => S.glow = v);\n    knob(\'外发光 px · bloom\', 0, 40, .1, () => S.bloom, v => S.bloom = v);\n  }\n\n  // The two gaps that belong to the lecture blocks rather than to any one role.\n  panel.appendChild($(\'h3\', {text: \'讲座间距\'}));\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const lecs = document.querySelector(\'.lecs\');\n    const pxKnob = (label, prop, min, max, step) => {\n      const cur = parseFloat(getComputedStyle(lecs).getPropertyValue(prop)) || 0;\n      const n = field(box, label, num(cur, min, max, step));\n      const r = slider(box, cur, min, max, step);\n      const set = v => { lecs.style.setProperty(prop, v + \'px\'); n.value = v; r.value = v; dump(); };\n      n.oninput = e => set(e.target.value);\n      r.oninput = e => set(e.target.value);\n    };\n    pxKnob(\'行距 --lec-lead\', \'--lec-lead\', 0, 60, 1);\n    pxKnob(\'离脊柱 --lec-gap\', \'--lec-gap\', 0, 200, 2);\n  }\n\n  panel.appendChild($(\'h3\', {text: \'页边距\'}));\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    const cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue(\'--pad\'));\n    const p = field(box, \'--pad px\', num(cur, 8, 96, 2));\n    const pr = slider(box, cur, 8, 96, 2);\n    const setPad = v => {\n      document.documentElement.style.setProperty(\'--pad\', v + \'px\');\n      p.value = v; pr.value = v; dump();\n    };\n    p.oninput = e => setPad(e.target.value);\n    pr.oninput = e => setPad(e.target.value);\n  }\n\n  panel.appendChild($(\'h3\', {text: \'导出 · 贴回 build.py\'}));\n  const out = $(\'textarea\', {readonly: \'\', spellcheck: \'false\'});\n  {\n    const box = $(\'section\');\n    panel.appendChild(box);\n    box.appendChild(out);\n    box.appendChild($(\'div\', {class: \'hint\', text:\n      \'面板只改这一页，刷新就回到 build.py 里的值。\' +\n      \'导出的是手调的那些数，不是它们算出来的阶梯。\'}));\n  }\n\n  function dump() {\n    const q = s => "\'" + s + "\'";\n    const row = (role, withAt) => {\n      const r = D.all[role];\n      const bits = [];\n      if (withAt) bits.push(\'at=\' + q(r.at));\n      bits.push(\'step=\' + q(r.step), \'set=\' + q(r.set));\n      if (r.gap) bits.push(\'gap=\' + r.gap);\n      if (r.width) bits.push(\'width=\' + r.width);\n      if (r.ls != null) bits.push(\'ls=\' + r.ls);\n      if (r.lh != null) bits.push(\'lh=\' + r.lh);\n      return \'    \' + role + \'=dict(\' + bits.join(\', \') + \'),\';\n    };\n    const py = s => "\'" + s.replace(/\\\\/g, \'\\\\\\\\\').replace(/\'/g, "\\\\\'")\n      .replace(/\\n/g, \'\\\\n\') + "\'";\n    const copy = Object.keys(D.copy).map(k => \'    \' + k + \'=\' + py(D.copy[k]) + \',\');\n    // Only the hand-set numbers come back out. The ramp is a rule, and printing\n    // the five sizes it produces would invite pasting them back as five tables.\n    const B = D.base, S = D.markStep, T = D.markType;\n    const dict = (name, pairs) => name + \' = dict(\' + pairs.join(\', \') + \')\';\n    const bk = (name, b) => dict(name, [\'dilate=\' + b.dilate, \'merge=\' + b.merge,\n      \'hard=\' + b.hard, \'halo=\' + b.halo, \'stack=\' + Math.round(b.stack),\n      \'slab=\' + b.slab, \'glow=\' + b.glow]);\n    const lecs = getComputedStyle(document.querySelector(\'.lecs\'));\n    out.value =\n        dict(\'BASE\', [\'soft=\' + B.soft, \'glow=\' + B.glow, \'bloom=\' + B.bloom,\n                      \'solid=\' + B.solid, \'weight=\' + B.weight,\n                      \'ls=\' + B.ls, \'lh=\' + B.lh]) + \'\\n\'\n      + \'TRACK = \' + D.track + \'\\n\'\n      + \'LEAD = \' + D.lead + \'\\n\\n\'\n      + dict(\'MARK_STEP\', [\'size=(\' + S.size[0] + \', \' + S.size[1] + \')\',\n                           \'soft=\' + S.soft, \'glow=\' + S.glow, \'bloom=\' + S.bloom,\n                           \'solid=\' + S.solid]) + \'\\n\'\n      + dict(\'MARK_TYPE\', [\'weight=\' + T.weight, \'ls=\' + T.ls, \'lh=\' + T.lh]) + \'\\n\\n\'\n      + "BACKLIGHT_COLOUR = \'" + D.blc + "\'\\n"\n      + bk(\'BASE_BACK\', D.baseBack) + \'\\n\'\n      + bk(\'MARK_BACK\', D.markBack) + \'\\n\\n\'\n      + \'ROLES = dict(\\n\' + Object.keys(D.roles).map(r => row(r, true)).join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'TEXT = dict(\\n\' + Object.keys(D.text).map(r => row(r, false)).join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'COPY = dict(\\n\' + copy.join(\'\\n\') + \'\\n)\\n\\n\'\n      + \'--pad: \' + getComputedStyle(document.documentElement).getPropertyValue(\'--pad\').trim()\n      + \'\\n--lec-lead: \' + lecs.getPropertyValue(\'--lec-lead\').trim()\n      + \'\\n--lec-gap: \' + lecs.getPropertyValue(\'--lec-gap\').trim();\n  }\n\n  apply(); dump();\n})();\n'


def tools_panel():
    """A side panel for placing and sizing the roles. It appears on ?tools only —
    the poster itself should not ship a dev panel. It edits the same three tables
    the build reads, and prints ROLES back as Python to paste into this file."""
    data = json.dumps(dict(roles=ROLES, text=TEXT, sets=COLOUR_SETS,
                           base=BASE, baseSize=BASE_SIZE, walkStop=WALK_STOP, track=TRACK, lead=LEAD,
                           sizes=TEXT_SIZES, markStep=MARK_STEP, markType=MARK_TYPE,
                           baseBack=BASE_BACK, markBack=MARK_BACK, blc=BACKLIGHT_COLOUR,
                           corners=list(CORNERS), copy=COPY, tag=ROLE_TAG, links=LINKS),
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
                .replace('__CLOSEFS__', ramp(28, 36))
                .replace('__GRAINURL__', grain).replace('__GRAINA__', str(GRAIN['opacity']))
                .replace('__GRAINSIZE__', f"{GRAIN['cell'] * 40:g}px")
                .replace('__CELL__', ramp(CELL * SPINE_SMALL, CELL))
                .replace('__LENS__', ramp(LENS * SPINE_SMALL, LENS))
                .replace('__FEATHER__', ramp(FEATHER * SPINE_SMALL, FEATHER))
                .replace('__MARKFS__', ramp(MARK_STEP['size'][1], MARK_STEP['size'][0]))
                .replace('__NARROW__', str(NARROW)).replace('__MID__', str((NARROW + WIDE) // 2))
                .replace('__COLS__', f'{cols:g}').replace('__ROWS__', str(rows))
            + BODY.replace('__NARROW__', str(NARROW)).replace('__SPINE__', spine).replace('__LECS__', lectures_html()).replace('__CORNERS__', corners()).replace('__BACKLIGHT__', backlight_defs())
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
