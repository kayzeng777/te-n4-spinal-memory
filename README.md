# te · Spinal Memory

Poster site for the *Spinal Memory* online lecture series.

- `index.html` — the poster. Built, not hand-edited.
- `fx.html` — layered-type tuner, exports to `tools/presets.json`.
- `glow.html` — comparison of four ways to build the glow.
- `artifact.html` — the poster with fonts inlined (gitignored).

## Building

```
python3 tools/ascii_to_spine.py tools/ascii-art.txt tools/spine.svg.part
python3 tools/spine.py          tools/spine.svg.part tools/spine.seg.part
python3 tools/build.py
```

The first step turns an ASCII shade drawing into cells, straightens the
per-row drift and centres on the centre of mass. The second splits it into
nine hoverable segments. The third assembles the pages.

`tools/ascii-art.txt` is the drawing in use. `tools/ascii-art-4level.txt` and
`tools/ascii-art-2.txt` are alternatives; point step one at one of them to try
another spine.
