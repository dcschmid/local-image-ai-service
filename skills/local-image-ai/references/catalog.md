# Available image models and guided presets

Generated from the service catalog at installation/package time. Query the live catalog for current availability, settings and examples.

## Models

| ID | Model | Use | License |
| --- | --- | --- | --- |
| `moss` | MOSS SFT | Choose a realistic photography recipe or a low-poly scene. Each recipe prepares lighting, composition and settings; only your subject is required. | Apache-2.0 |
| `anima` | Anima Aesthetic · 1.1 | For anime and illustration: choose a recipe and describe your subject. Aesthetic needs no score_* tags. | CircleStone (commercial image use allowed) |
| `qwen21` | Qwen Image 2.1 · Uncensored GGUF | For detailed scenes, typography and transparent stickers. The supplier labels this upstream-weight GGUF uncensored. Qwen Research License: non-commercial research and evaluation only. | Qwen Research (non-commercial research/evaluation) |
| `krea-pixel` | Krea 2 · Pixel Art | Pixel art with the 32, 64 or 128 pixel LoRA on Krea 2 Turbo. Generate at 1024 square, then refine to a clean grid and palette. LoRA and base-model licenses both apply. | LoRAs: MIT · Base: Krea 2 Community License |
| `z-image` | Z-Image | For creative illustration, varied characters and photography. Use descriptive sentences; negative prompts are supported. Recommended: 40 steps and CFG 4. | Apache-2.0 |
| `z-image-turbo` | Z-Image Turbo | For quick photographs, product ideas and short English or Chinese lettering. Eight steps, CFG 1 and no negative prompt; describe the result you want directly. | Apache-2.0 |

## Guided presets

### anima / anime

| ID | Preset | Purpose |
| --- | --- | --- |
| `anima-portrait` | Cinematic character portrait | One character, an expressive gaze, soft lighting and a quiet background. |
| `anima-film` | Anime film · wide scene | A wide film frame with clear action, depth and atmospheric lighting. |
| `anima-fantasy` | Fantasy · heroic character | A dramatic character illustration with magic, contrasting light and a readable pose. |
| `anima-neon` | Cyberpunk · neon night | Cool city colors, warm highlights and reflective streets. |
| `anima-landscape` | Anime background · landscape | Painterly scenery with clear layers of depth; no character required. |
| `anima-cozy` | Cozy · slice of life | Warm lighting, a calm composition and small storytelling details. |
| `anima-manga` | Manga · ink and screentones | Black and white, precise lines, screentones and clear light and dark shapes. |
| `anima-watercolor` | Watercolor · dreamy illustration | Delicate colors, visible paper texture and soft color washes. |
| `anima-chibi` | Chibi · tiny adventurer | A tiny full-body character with exaggerated proportions, a clear silhouette and a simple background. |
| `anima-retro` | Retro anime · 1990s cel look | Hand-painted cel colors, delicate grain and the mood of a 1990s anime frame. |
| `anima-mecha` | Mecha · hangar key visual | A striking giant robot with readable mechanical shapes, scale and dramatic hangar light. |
| `anima-storybook` | Storybook · gouache illustration | Soft gouache shapes, textured paper and a quiet illustrated story moment. |
| `anima-action` | Action · dynamic anime key visual | A strong ready pose, flowing fabric and a clear open silhouette. |
| `anima-woodblock` | Woodblock · moonlit print | Carved contours, flat pigment areas and the texture of a traditional woodblock print. |
| `anima-pastel` | Pastel · soft chalk illustration | Powdery chalk marks, soft edges and luminous colors on textured paper. |
| `anima-dark-fantasy` | Dark fantasy · painted encounter | A painterly fantasy scene with dramatic scale, mist and a readable focal encounter. |
| `anima-solarpunk` | Solarpunk · hopeful city | Sunlit terraces, lush planting and an illustrated city built around everyday life. |

### moss / lowpoly

| ID | Preset | Purpose |
| --- | --- | --- |
| `lowpoly-diorama` | Low Poly · floating diorama | A miniature scene on a floating base, with angular faces and soft studio lighting. |
| `lowpoly-retro` | Low Poly · 1990s game scene | Angular 3D game art with distinct silhouettes and bold lighting. |
| `lowpoly-world` | Low Poly · landscape and game world | A wide game world with angular mountains, rivers and clear blocks of color. |
| `lowpoly-anything` | Low Poly · anything | A flexible low-poly look for animals, creatures, objects, characters, vehicles, places or complete scenes. |
| `lowpoly-track-overview` | Low Poly · track overview | An overhead racing-circuit concept with the entire route visible and simple low-poly surroundings. |
| `lowpoly-character` | Low Poly · character reference | One full-body low-poly character with simple clothing, a neutral pose and a readable silhouette. |
| `lowpoly-vehicle` | Low Poly · kart and vehicle reference | One complete low-poly vehicle with clear wheels, chassis and panel connections. |
| `lowpoly-prop` | Low Poly · prop reference | A single low-poly object with clear thicknesses, simple joins and a plain background. |
| `lowpoly-building` | Low Poly · building reference | A complete modular building with readable wall, roof, door and window volumes. |
| `lowpoly-character-sheet` | Low Poly · character concept sheet | Four proposed views of one character design. AI estimates can differ; use a 3D model for geometry-consistent views. |
| `lowpoly-kart-sheet` | Low Poly · kart concept sheet | Four proposed views of one kart design. AI estimates can differ; use a 3D model for geometry-consistent views. |
| `lowpoly-prop-sheet` | Low Poly · prop concept sheet | Four proposed views of one prop design. AI estimates can differ; use a 3D model for geometry-consistent views. |

### moss / photo

| ID | Preset | Purpose |
| --- | --- | --- |
| `photo-portrait` | Photo · natural portrait | A believable portrait with natural skin texture, soft daylight and a quiet background. |
| `photo-candid` | Photo · candid everyday | A casual everyday moment with available light and a less polished snapshot feel. |
| `photo-street` | Photo · street documentary | An observed street moment with environmental detail, layered depth and believable light. |
| `photo-cinema` | Photo · cinematic still | A realistic film-like frame with motivated lighting, clear action and subtle color grading. |
| `photo-product` | Photo · product studio | A clean product image with coherent materials, controlled reflections and grounded shadows. |
| `photo-landscape` | Photo · landscape and travel | A natural outdoor scene with convincing terrain, atmospheric depth and restrained color. |
| `photo-interior` | Photo · architecture and interior | A believable interior with straight verticals, natural materials and balanced window light. |
| `photo-food` | Photo · food and still life | An appetizing close view with natural texture, soft side lighting and simple styling. |
| `photo-macro` | Photo · macro nature | A close natural detail with convincing texture, soft light and a shallow focal plane. |

### moss / craft

| ID | Preset | Purpose |
| --- | --- | --- |
| `moss-clay` | Clay · handmade miniature | Tactile modeling clay, tiny handmade details and soft miniature-set lighting. |
| `moss-paper` | Paper cut · layered illustration | Layered colored paper, crisp cut edges and gentle shadows between the layers. |
| `moss-comic` | Comic · bold ink illustration | Bold ink, halftone shading and one strong full-frame comic scene. |
| `moss-risograph` | Risograph · two-ink print | Two spot inks, visible paper grain and slightly offset printed layers. |
| `moss-embroidery` | Embroidery · stitched illustration | Raised colored thread, visible stitches and a tactile woven fabric ground. |
| `moss-felt` | Needle felt · tiny wool world | Soft wool fibers, rounded handmade figures and a miniature scene. |
| `moss-stained-glass` | Stained glass · luminous window | Jewel-colored glass shapes, dark lead outlines and glowing transmitted light. |

### qwen21 / qwen

| ID | Preset | Purpose |
| --- | --- | --- |
| `qwen-poster` | Qwen · graphic travel poster | A bold illustrated poster with a clear subject and optional exact headline. |
| `qwen-sticker` | Qwen · transparent sticker | An isolated sticker illustration with a transparent PNG background. |
| `qwen-portrait` | Qwen · editorial portrait | A detailed photographic portrait with natural texture and editorial framing. |
| `qwen-product` | Qwen · product campaign | A polished product scene with deliberate materials, reflections and optional label text. |
| `qwen-cover` | Qwen · illustrated book cover | A dramatic illustrated cover with a clear focal scene and optional title. |
| `qwen-world` | Qwen · isometric world | A detailed miniature world with coherent architecture, scale and lighting. |
| `qwen-infographic` | Qwen · illustrated explainer | A simple illustrated process with a short heading and a few clearly separated stages. |
| `qwen-exploded` | Qwen · exploded product concept | Separated product layers with readable materials and a coherent assembly direction. |
| `qwen-packaging` | Qwen · packaging concept | One package with a clear front label, material texture and a coordinated graphic motif. |
| `qwen-neon-sign` | Qwen · neon lettering scene | Short luminous lettering integrated into a rainy cinematic street scene. |

### krea-pixel / pixel

| ID | Preset | Purpose |
| --- | --- | --- |
| `pixel-loot` | Pixel · tiny loot icon | A bold 32-pixel inventory icon with a simple silhouette and a small palette. |
| `pixel-character` | Pixel · adventure character | A complete 64-pixel game character with readable clothing and pose. |
| `pixel-isometric` | Pixel · isometric hideaway | A miniature 64-pixel isometric building with tidy forms and cozy details. |
| `pixel-landscape` | Pixel · scenic world | A detailed 128-pixel scene with layered scenery and a restrained palette. |
| `pixel-creature` | Pixel · creature sprite | One complete game creature with grouped shading and an expressive silhouette. |
| `pixel-portrait` | Pixel · dialogue portrait | A readable character bust suitable as a starting point for a game dialogue portrait. |
| `pixel-vehicle` | Pixel · tiny vehicle | One small vehicle with clear wheels, readable bodywork and a simple background. |
| `pixel-dungeon` | Pixel · dungeon room | A single overhead game room with clear boundaries and a few readable props. |
| `pixel-character-sheet` | Pixel · character concept sheet | Four proposed views of one character design. AI estimates can differ; use a 3D model for geometry-consistent views. |
| `pixel-kart-sheet` | Pixel · kart concept sheet | Four proposed views of one kart design. AI estimates can differ; use a 3D model for geometry-consistent views. |
| `pixel-prop-sheet` | Pixel · prop concept sheet | Four proposed views of one prop design. AI estimates can differ; use a 3D model for geometry-consistent views. |

### z-image / zimage

| ID | Preset | Purpose |
| --- | --- | --- |
| `zimage-fantasy` | Z-Image · fantasy matte painting | A wide imaginative world with painted atmosphere and monumental scale. |
| `zimage-ink` | Z-Image · ink wash | Expressive black ink, soft washes and open rice-paper space. |
| `zimage-retro-scifi` | Z-Image · retro science fiction | Airbrushed planets, imaginative machinery and the palette of a vintage paperback. |
| `zimage-fashion` | Z-Image · editorial fashion | A deliberate fashion photograph with expressive fabric and directional light. |
| `zimage-botanical` | Z-Image · botanical plate | A delicate scientific-style plant illustration with clear stems, leaves and flowers. |

### z-image-turbo / zturbo

| ID | Preset | Purpose |
| --- | --- | --- |
| `zimage-turbo-photo` | Z-Image Turbo · everyday photograph | A quick natural photograph with available light and an unforced everyday moment. |
| `zimage-turbo-cinema` | Z-Image Turbo · cinematic night | A fast film-like scene with a clear action and motivated practical lighting. |
| `zimage-turbo-product` | Z-Image Turbo · product study | A fast material and lighting study of one clearly framed product. |
| `zimage-turbo-sign` | Z-Image Turbo · storefront lettering | A small storefront scene with one short English or Chinese sign. |
| `zimage-turbo-food` | Z-Image Turbo · food editorial | A quick appetizing food photograph with soft side light and tactile ingredients. |

### moss / voxel

| ID | Preset | Purpose |
| --- | --- | --- |
| `voxel-character` | Voxel · character asset | A cubic voxel-style character concept with readable block shapes and a small material palette. |
| `voxel-kart` | Voxel · kart asset | A cubic voxel-style kart concept with readable block shapes and a small material palette. |
| `voxel-prop` | Voxel · prop asset | A cubic voxel-style prop concept with readable block shapes and a small material palette. |
| `voxel-building` | Voxel · building asset | A cubic voxel-style building concept with readable block shapes and a small material palette. |
| `voxel-diorama` | Voxel · diorama asset | A cubic voxel-style diorama concept with readable block shapes and a small material palette. |
| `voxel-anything` | Voxel · anything | Voxel-style creatures, objects and small worlds built from clear cubic blocks. |
