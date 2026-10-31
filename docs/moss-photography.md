# Realistic photography with MOSS SFT

Research checked on **October 31, 2026**. These are custom Atelier recipes for the installed MOSS SFT model. They add a photographic brief and settings to a subject; they are not downloaded LoRAs or official preset files.

## What to choose

| Studio recipe | Use it for | What to enter |
| --- | --- | --- |
| Photo · natural portrait | A composed, believable portrait | Age, hair, clothing, expression; optionally a setting |
| Photo · candid everyday | An informal snapshot | A person doing one ordinary action in an everyday place |
| Photo · street documentary | People in a recognizable environment | One action, a place and the weather |
| Photo · cinematic still | A realistic film-like scene | A main subject, one action and a visible source of light |
| Photo · product studio | Clean product and material studies | Object, material, finish, color and surface |
| Photo · landscape and travel | Outdoor scenery | A focal feature, terrain, time of day and weather |
| Photo · architecture and interior | Rooms and architectural materials | Room size, furniture, materials and window direction |
| Photo · food and still life | Food with visible texture | Dish, ingredients, plate and table surface |

Choose **Guided · fill in a recipe**, select a photography recipe, enter a subject and click **Generate image**. The recipe selects MOSS automatically. Setting and details are optional. **Use example** supplies a complete starting point, and **View full prompt and settings** shows exactly what is sent.

When selecting MOSS directly, its default recipe is Natural portrait. The three Low Poly recipes remain in their own group. Their prompts and settings are unchanged.

## Settings and their evidence

The [official SFT model card](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT) identifies SFT as a fine-tune using the same inference pipeline as Base. Its example uses 50 steps and CFG 3. It also uses negative-branch layer skipping, so its output is not an exact reference for this quantized local runtime.

The [official user guide](https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md) is titled for Base. It recommends Euler, at least 50 steps, CFG 3–6, Shift 5 and roughly 1–2 megapixels. It favors English descriptions and dimensions divisible by 16. We use that guidance as a starting point and check the installed SFT runtime separately.

| Photography profile | Steps | Size | Purpose |
| --- | ---: | --- | --- |
| Draft | 30 | 576×832, 832×576 or 768×768 | Explore the subject and composition |
| Recommended | 50 | 832×1216, 1216×832 or 1024×1024 | Evaluate photographic detail |
| More detail | 60 | Same as Recommended | An optional comparison with the seed fixed |

All three use Euler, CFG 3 and Shift 5. The existing Low Poly draft profile keeps its 20 steps. More steps are not a guarantee of a better image. Draft deliberately uses fewer steps and a smaller image than the upstream quality recommendation.

The presets use natural-language descriptions of framing, light and materials, following the approach in the [official prompt enhancer](https://github.com/OpenMOSS/MOSS-Image/blob/main/skills/moss-image-prompt-enhancer/SKILL.md). The service composes these descriptions deterministically; it does not run an additional language model. Lens references are visual cues, not enforced optics or actual camera metadata.

## Practical starting points

For people, start with Natural portrait for a composed head-and-shoulders view, or Candid everyday for an informal medium shot. Specify visible features rather than a long list of quality terms. A relaxed expression, ordinary clothing, fine lines or loose hair can make the brief more specific. These are creative choices, not guaranteed realism switches.

For products, distinguish matte ceramic, brushed metal, clear glass and fabric. Describe the object itself before accessories. Keep one surface, one background and one lighting setup. A glossy product remains allowed: photography recipes do not inherit the Low Poly exclusions against photographic textures and glossy plastic.

For interiors, keep furniture counts and spatial relationships simple. Name where the windows are. The recipe requests straight verticals and plausible scale, but generated geometry can still be inconsistent.

For landscapes, combine one focal feature with coherent weather and lighting. “A lighthouse above a rocky coast at sunrise after rain” is a clearer brief than stacking several incompatible scenic styles.

For all recipes, keep the seed fixed and change one field at a time. Test another seed when the composition remains poor. Start a free prompt from a saved image if you need direct control of steps, sampler or negatives. Image settings and the original recipe fields are saved for reuse.

## Negative prompts and scope

Photography recipes use their own visible negative prompt against drawn/CGI styles, waxy skin, oversharpening and collages. It does not add rating restrictions or an automatic content filter. The full positive and negative prompts are shown before generation.

No photography recipe inherits the Low Poly instructions for faceted geometry or its exclusion of photographic textures. Existing Anima and Low Poly recipe outputs were compared with the previous implementation at all three quality levels and are unchanged.

## Other findings

The author of [MOSS SFT DeBand](https://huggingface.co/MATLOWAI/MOSS-Image-SFT-DeBand) documents vertical color bands in smooth SFT backgrounds and provides corrective adapters. This is a model/workflow issue that a photography prompt cannot reliably repair. The adapters have their own detail and compatibility trade-offs and are not installed with these recipes.

The author's [8-step DMD model card](https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd) describes a separate community distillation and adapter workflow. Its few-step settings do not apply to the installed plain SFT model. These presets retain the existing model and use its 50-step quality baseline.

## Local verification

GPU outputs and their full requests are stored separately from the user's gallery under `~/.cache/local-image-ai-service/moss-photography-20261031/`. The results are summarized in [the photography test report](moss-photography-test-report.md).
