# papercraft

An agent skill for building games, interactive scenes, web pages, animations and videos in one handcrafted
**pop-up papercraft style**, for any subject: printed cardstock pieces with thin cut edges that fold up on hinges from
a printed ground, soft layered shadows coloured by the world, a tilt-shift macro lens looking down into the world,
calm hinge motion and soft paper sounds.

It teaches the method and carries the hard-won numbers from a shipped three.js pop-up game: what makes a frame read as
a photographed paper model (matte paper, every print a small layered paper collage with contrasting accents, a thin
dark cut edge with a pale highlight on the lit side, soft shadows tinted by the world, a dense world of chunky pieces,
a tilt-shift macro lens), how to build any piece from a set of structure types you can extend (slotted crosses,
layered flats, folded boxes and prisms, domes, printed water, and built decks, bridges and stairs for anything walked
on), how paper moves, lives and sounds, how to build a character whose cards never cut into each other, and a
measure-and-critique loop.

Your prompt and your references decide the world: its palette, ground, buildings, creatures and weather. References
are one way to set the direction: a shot of a paper model can be the look target itself, while photos, sketches or a
moodboard give the theme and the designs, which the agent rebuilds in paper. It uses an image generator only when
you ask it to, and everything can be made in code. A gallery of five worlds from the source game, each with the
prompt that made it, shows the quality bar, and sixteen more frames (a reef, a station deck, a rainy city, an
interior, a page UI, a figure sheet, ...) show how far the style reaches; none of it is content to copy. The agent designs and writes its
own subject's pieces; the bundled code is plumbing (paper, cards, the layered print, hinges, light, lens, walking,
life) plus worked examples from one countryside world.

The same world renders in any frame: a 16:9 film, a 9:16 Reel, a square or 4:5 post, a 4K master, an ultrawide still
or a phone page. The lens keeps to the frame's short side, a vertical frame comes closer and keeps the subject clear
of the platform's captions, and prints and blur follow the resolution. `capture.py` renders stills and MP4 clips at
the standard sizes (`--size reel`, `square`, `4k`, ...).

## Install

```bash
npx skills add xikhar/papercraft
```

Or copy `skills/papercraft/` into your agent's skills folder. Works with any agent that supports
[Agent Skills](https://agentskills.io) (Claude Code, Codex, Cursor, Gemini CLI, OpenCode, ...). Then just ask for
something paper:

- "make our bakery landing page feel like a pop-up storybook"
- "a small three.js scene of a harbour town that folds up out of the ground"
- "a dome on Mars as a paper diorama, with a rover that pops up"
- "a 20-second paper diorama animation of a city waking up, rendered to mp4"
- "a night market on stilts over a lagoon, in the colours of the photos I attached"
- "a forest shrine from this moodboard; generate a few concept frames first and let me pick one"
- "an 8-second vertical Reel of a paper lighthouse town waking up at dawn"

## What is inside

```
skills/papercraft/
|-- SKILL.md                 the material model, direction from references, the paper spec, routing, workflow, checks
|-- references/              loaded on demand: gallery, structures (the structure types), look, palettes,
|                            mechanisms, motion, worlds, procedural art, formats (sizes, safe areas, export),
|                            image-gen (optional references), sound, paper UI, three.js, 2D web, engines, process
|-- assets/
|   |-- lib/                 the plumbing, import as is:
|   |                        paperkit-2d.js (paper sheets, cut outlines, ngon/roundedRect/cloud, outline validation,
|   |                        layered print, drawing-to-cut, 2D decks)
|   |                        paperkit-3d.js (paper material, cards with thickness, laminated imageCard cutouts,
|   |                        extrudedLayerStack reliefs, hinges, the cross family, fan pairs, box folds, prism folds
|   |                        on any plan, platforms, PCSS soft shadows, macro lens)
|   |                        paper-motion.js (latched paper spring, wind sway, fixed clock, walk field, glideSchedule,
|   |                        polarCameraPos, checkContinuity with cuts and loop seams)
|   |                        paper-sound.js (procedural paper foley, warm/crisp/soft presets, collector, WAV export)
|   |                        paper-music.js (procedural felt-piano, wooden-hall reverb, harp & bells, live + offline)
|   |                        paper-life.js (weather, flyers, smoke, bursts, cloud shadows, terrain-aware creatures)
|   |-- examples/            worked examples to read, not parts to assemble: countryside.js (one world's pieces and
|   |                        prints), built-ground.js (a bridge, stairs on stringers, a ramp, a masonry terrace, a
|   |                        cottage)
|   |-- templates/           popup-3d (three.js: a fixed harness; the hero is optional, and a film scripts its
|   |                        rises, camera, light over time and score) and popup-2d (Canvas 2D: a walking hero's world), each with
|   |                        an example scene to replace; popup-3d/structures.html: the hinged structure types in
|   |                        plain placeholders
|   |-- gallery/             five worlds from the source game (forest, desert, snow, spring, autumn): the quality
|   |                        bar, each paired with its prompt in references/gallery.md; gallery/range/: sixteen
|   |                        generated direction frames of other subjects and kinds of work in the same craft
|   `-- lights.json          light presets by light condition (key, fill, shadow colour, haze)
`-- scripts/                 capture.py (headless frames and colour-checked MP4s at any format size, timeline=,
                             time= stills of a film, --audio mix, --loop, --verify-frames, walks, build report),
                             extract_cutouts.py (chroma-key
                             cutout splitter and despill), measure.py (look metrics), ab_sheet.py, paper_textures.py
tests/                       node tests/unit.mjs (the kit's engine-free parts); python tests/cutouts.py (the
                             cutout splitter on drawn sheets with known answers); python tests/browser.py (the
                             templates in a real browser: page errors, look gates, hero clipping, video frames
                             and colour on both capture paths, a film's light, lamps and stills, audio levels;
                             about three minutes)
```

The templates are a fixed harness with a replaceable look: serve `skills/papercraft/assets/` over http
(`npx serve skills/papercraft/assets` or `python -m http.server -d skills/papercraft/assets 8000`) and open
`/templates/popup-3d/` or `/templates/popup-2d/` (`/templates/popup-3d/structures.html` shows the hinged structure
types). Both example scenes walk a hero with WASD / arrows (`?still` for the fixed overview); the 3D harness also
runs with no hero (a diorama, a film), the 2D one needs one. In your own project, copy `assets/lib/` and
the template's harness (`harness.js` for 3D, `harness-2d.js` for 2D), write your own `scene.js`, and point
`"papercraft/"` in the page's import map at the folder that holds `lib/`. Add `?size=1080x1920` (or `?aspect=9:16`) to
see another format. For review frames, `python skills/papercraft/scripts/capture.py <project folder> overview
"walk=x,z;x,z"` renders them headless (it needs Playwright with Chrome, and ffmpeg for video) and reports the build
time, the slowest prints, whether the hero's cards cut into each other and any page error; `--size reel
"clip:timeline=8,30" --audio` renders a vertical clip with its sound and encodes the MP4.

## License

MIT
