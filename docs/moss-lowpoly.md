# Low Poly with MOSS

Low-poly generation now uses MOSS SFT and visible presets. The separate Anima
PS1 / PSX and Low Poly Style profiles are retired. Anima Aesthetic, Qwen 2.1 and
Krea Pixel Art remain available for their existing workflows.

| Recipe ID | Starting point |
| --- | --- |
| `lowpoly-anything` | Any motif: animals, creatures, props, vehicles, places or full scenes, with your chosen camera. |
| `lowpoly-track-overview` | A complete racing circuit from overhead, with a readable continuous route and sparse scenery. |
| `lowpoly-character` | A complete character with simple clothing and a neutral pose. |
| `lowpoly-vehicle` | A kart or vehicle with readable wheels, chassis, seat and panels. |
| `lowpoly-prop` | One isolated object with visible thicknesses and functional joins. |
| `lowpoly-building` | One modular building with complete roof/wall volumes and clear openings. |
| `lowpoly-diorama` | The existing floating miniature scene. |
| `lowpoly-retro` | The existing early-3D game scene. |
| `lowpoly-world` | The existing faceted landscape/game world. |

Open the [MOSS Low Poly guide](http://127.0.0.1:7861/studio/lowpoly-guide/)
for actual locally generated examples and one-click starters. The four asset
examples include Blender-reference inputs; the three existing scene examples
retain their original compositions. All examples display their actual profile.

**Low Poly · anything** is the general starting point for miscellaneous ideas.
Only describe the motif; add the setting and camera if desired. It does not
impose a character pose, a vehicle structure or a terrain tile. **Track overview**
requests a complete overhead circuit with one closed route and simple surroundings.
Inspect track continuity before rebuilding a drivable route in Blender; this is
a concept image, without an exported road spline or validated track geometry.

Only the subject is required. Use construction notes for proportions, part
connections and poses. Use material/details for a small palette and a few defining
features. MOSS receives the complete visible prompt; no additional language model
or hidden style adapter interprets the request.

Recommended uses **50 Euler steps, CFG 3, flow shift 5**. Blender-reference Draft
and the Anything/Track overview Draft use 30 steps at reduced dimensions; the existing scene Draft recipes retain
20 steps. More detail uses 60 steps. Compare one setting at a time with a fixed
seed. The asset examples are generated in Draft; select Recommended for the
larger final canvas.

```bash
local-image-ai-service recipes --model moss --search 'lowpoly'
local-image-ai-service render --recipe lowpoly-anything --subject 'a fox exploring a crystal cave' --save-dir ./artifacts
local-image-ai-service render --recipe lowpoly-track-overview --example --seed 42 --save-dir ./artifacts/track
local-image-ai-service compose --recipe lowpoly-vehicle --example --seed 42
local-image-ai-service render --recipe lowpoly-vehicle --example \
  --quality standard --seed 42 --save-dir ./artifacts/kart
```

To choose the view and subject explicitly:

```bash
local-image-ai-service render --recipe lowpoly-character \
  --subject 'an adult courier with a green jacket and brown boots' \
  --modeling-view front --modeling-asset character \
  --seed 42 --save-dir ./artifacts/character
```

These outputs are modeling concepts. MOSS does not export a mesh or guarantee
that separately generated views match. Build one approved design as a Blender
blockout, then render the required views from that shared geometry. See
[the reference workflow](blender-references.md).

The existing 38 recipes retain their compiled prompts and settings. Historical
images created with the removed Anima variants remain in the gallery and can be
exported. Only unreferenced service-owned adapter files are removed; shared Anima
base files and original Downloads files are protected.

See [the migration and rendering checks](moss-lowpoly-test-report.md) for measured
example times, visual limitations and gallery/model preservation.
