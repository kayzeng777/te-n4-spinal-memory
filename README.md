# te · Spinal Memory

Poster site for the *Spinal Memory* online lecture series.

- `index.html` — the poster. Built, not hand-edited.
- `artifact.html` — the poster with fonts inlined (gitignored).

## Building

```
python3 tools/ascii_to_spine.py tools/ascii-art.txt tools/spine.svg.part
python3 tools/spine.py          tools/spine.svg.part tools/spine.seg.part
python3 tools/build.py
```

The poster is set entirely in PP Neue Montreal. `fonts/Apoc-Variable.woff2` is
left on disk but no longer served.

The first step turns an ASCII shade drawing into cells, straightens the
per-row drift and centres on the centre of mass. The second splits it into
nine hoverable segments. The third assembles the pages.

## Poster type

The type effect is one SVG filter per role per breakpoint, generated in
`tools/build.py` (`TYPE`, `type_filter`). It builds the letterform out of a
**distance field** — `feMorphology erode` stacked into equal-width shells around
the contour — rather than a Gaussian blur of the alpha. That matters: a blurred
alpha is a *thickness* field, so a stem's middle reads deeper than a hairline's
and the effect comes out uneven; equal-width shells are the same on every stroke
and in every direction.

Three layers merge per role: an outer glow (`dilate` then Gaussian, so thin
strokes glow as much as thick ones), the edge colour filling the glyph, and the
fill colour carried inward by the distance field.

Every length derives from the role's font size, and the inward distance derives
from the **stem width** (`PP_STEM`), not the font size — stem width is not
proportional to size across families. When too little core would be left, the
filter falls back to a solid fill on its own.

Only `te` (an SVG logotype) and the PP information block are set on the poster;
Apoc is no longer used there, so the poster pages skip that font face.

`tools/ascii-art.txt` is the drawing in use. `tools/ascii-art-4level.txt` and
`tools/ascii-art-2.txt` are alternatives; point step one at one of them to try
another spine.
