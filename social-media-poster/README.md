# Social media poster

A 1080×1350 (4:5) cut of the te issue 4 lecture poster, made for screen
recordings posted to social media. Open `index.html` (live at
`/social-media-poster/`) and record it; the spine climbs on its own.

## Editing it

**Do not edit `index.html` or `poster.html` here** (the two SVGs are the exception: they are the lettering itself). Both are generated and
will be overwritten. Everything comes from the last section of
`tools/build.py`, which starts at the comment `# The social cut`. Edit there,
then rebuild from the repository root:

```
python3 tools/build.py
```

That section only overrides the site: anything it does not mention (colours,
glow, the spine drawing, the lectures) comes from the rest of `build.py`,
and changing it there changes the main site too.

Where things live in that section:

| What | Where |
| --- | --- |
| The words | Not type: two drawings from Figma, `top-right.svg` and `bottom-left.svg` in this folder, exported from the 1080×1350 frame with their glow. Re-export and replace the file to change them; each is pinned to its corner at `LETTERING` in `build.py` (file and width in 1080 units) |
| Spine width, lens (the x-ray circle) | `SOCIAL_CSS`: `--cell`, `.lens{--lens}` |
| Grain size | `GRAIN_PX` |
| Scroll speed | `LOOP` in `SOCIAL_JS` (seconds per round); `?loop=` or `?speed=0` in the URL for a one-off |
| Canvas size | `648` / `810` in the frame page at the end (1080×1350 at 0.6) |

The poster is laid out at 648×810 and scaled to fit the screen, so every
size in px is a size on that canvas, not on the phone.
