# Low-poly references for rebuilding in Blender

Seven MOSS low-poly asset/scene recipes offer a **Blender reference** composition.
New low-poly selections in guided mode start in three-quarter view. Choose an
asset type: full-body character, vehicle, prop, building or modular environment.
**Use Blender starter** fills an editable example brief. Only the subject is
required. The [in-app guide](http://127.0.0.1:7861/studio/lowpoly-guide/#blender)
includes direct character, kart, building and MOSS prop starters.

The guide also shows a real kart generated with the starter, with a link to its
recorded prompt and settings. It is separate from the 44 recipe examples.

The service prepares a complete silhouette, broad polygon faces, simple joins,
neutral lighting, a plain background and a small material palette. Characters
use a full-body A-pose; vehicles use a level chassis and straight wheels. This
composition replaces the original scene or portrait instructions so contradictory
framing is not mixed into the prompt. Construction/pose notes and material/color
details are optional and visible in the full prompt preview.

| View | Intended use |
| --- | --- |
| Three-quarter | Understand the main volumes and choose a master concept. |
| Front | Explore the front silhouette and landmark placement. |
| Left side | Explore a side profile. |
| Back | Explore a proposed rear design. |
| Top | Explore the footprint of vehicles, props and structures. |
| Concept image | Use the original recipe composition and settings. |

These are requested views, not measured projections. Text-to-image generation
can change proportions, details or the apparent camera. A fixed seed helps with
comparisons but does not lock a design across different prompts. The studio's
current model profiles do not expose a verified image-conditioned multi-view
workflow. Loading a reference image does not change that capability.

The current low-poly workflow uses MOSS. Separate generated views remain
independent design proposals; use the shared-blockout workflow below when the
views must describe the same geometry.

## From a hero image to consistent design sheets

A hero render and a set of separately generated views can disagree even when the
sheet looks polished. Hidden geometry is ambiguous, painted lighting may look
like extra geometry, and fine costume or mechanical details may not fit the
intended low-poly budget. A blueprint label or a green “PASS” badge cannot prove
that the views describe one object.

1. Choose one master concept. Keep the PNG and freeze its silhouette, palette,
   main part list and defining features. Write down the target dimensions and
   asset budget separately; an image does not establish either.
2. Build a simple Blender blockout using boxes, low-sided cylinders and planes.
   Compare it against the master from a fixed camera. Match the outer silhouette
   and large volumes before modeling decorative details.
3. Check shared landmarks. For characters, compare head/body ratio, shoulders,
   belt, hands and feet. For a kart, compare tire size, axle positions, wheelbase,
   chassis width, seat and steering. Decide the hidden surfaces once in the model.
4. Render front, side, back and top from that same scene using orthographic
   cameras. Use a shared origin and consistent scale for views that must align.
   Assemble those renders into the sheet, with labels and palette swatches added
   by the layout rather than painted into the AI reference.
5. Review silhouettes, dimensions and landmarks against the master. Review
   topology, UVs, normals and rigging on the actual mesh. Record what was checked
   and what remains an approximation instead of treating a status badge as proof.

Blender's official manual covers [image empties for references](https://docs.blender.org/manual/en/5.0/modeling/empties.html),
[orthographic cameras](https://docs.blender.org/manual/en/4.1/render/cameras.html)
and [flat shading](https://docs.blender.org/manual/en/latest/modeling/meshes/editing/face/shading.html).
Our recommended workflow uses these tools to obtain consistent views from shared
geometry. The image generator itself does not export meshes, UVs or rigged assets.

## Settings and compatibility

MOSS uses 50 Euler steps, CFG 3 and flow shift 5. Draft uses 30 steps for
modeling references; More detail uses 60 steps. Recommended formats follow the
asset: 832 × 1216 for characters, 1216 × 832 for vehicles/environments and
1024 × 1024 for props/buildings. The aspect-ratio control still overrides these
formats, and all dimensions pass the normal verification checks.

The guided API accepts `modeling_view` (`three-quarter`, `front`, `side`, `back`,
`top`, or `off`) and optional `modeling_asset` (`character`, `vehicle`, `prop`,
`building`, or `scene`). These settings are accepted only for low-poly recipes.
They cannot change adapter paths or sampling limits. `off` or omitted settings
preserve the original recipes. The retained recipe examples and their bundled examples
keep their original compiled prompts; selecting an example restores concept mode.

```json
{
  "recipe": "lowpoly-vehicle",
  "subject": "a compact racing kart with four exposed tires and one seat",
  "modeling_view": "three-quarter",
  "modeling_asset": "vehicle",
  "scene": "straight wheels, level chassis, a centered seat and steering wheel",
  "details": "matte orange body panels, dark blue frame, gray wheel hubs",
  "quality": "standard",
  "seed": 42
}
```

The saved image records the original guided inputs, complete prompt, sampling
settings and `modeling_version` independently of the unchanged recipe version.
Reusing it restores the requested asset type and view. Separate AI views remain
independent concepts; the UI does not mark them as geometrically verified.
