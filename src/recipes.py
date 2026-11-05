"""Deterministic guided recipes; no prompt translation or content filter."""
from catalog import defaults, MODELS
import modeling_reference
# Change this when existing recipe semantics change; additive recipes keep old inputs valid.
VERSION = 4
SOURCE = 'https://huggingface.co/circlestone-labs/Anima'
MOSS_SOURCE = 'https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md'
NEGATIVE = 'worst quality, low quality, blurry, jpeg artifacts, chromatic aberration, watermark, signature, comic panels, panel layout, split screen, collage, multiple views, reference sheet, white borders'
PHOTO_NEGATIVE = 'worst quality, low quality, watermark, jpeg artifact, anime, manga, cartoon, illustration, painting, CGI, 3d render, low poly, waxy skin, airbrushed skin, oversharpening, oversaturated colors, collage, contact sheet'
FORMATS = {
    '1:1': ('Square','1024x1024','768x768'),
    '16:9': ('Landscape','1024x576','1024x576'),
    '9:16': ('Portrait','576x1024','576x1024'),
    '4:3': ('Landscape','1024x768','768x576'),
    '3:4': ('Portrait','768x1024','576x768'),
    '3:2': ('Landscape','1152x768','768x512'),
    '2:3': ('Portrait','768x1152','512x768'),
}

def model_formats(model=None):
    selected = dict(FORMATS)
    if model in ('z-image', 'z-image-turbo'):
        selected.update({'3:2':('Landscape','960x640','768x512'), '2:3':('Portrait','640x960','512x768')})
    return selected

def formats(model=None):
    return [dict(id=ratio,name=ratio+' · '+label,size=size,preview_size=preview) for ratio,(label,size,preview) in model_formats(model).items()]

def preview_size(size):
    width,height=map(int,size.split('x'))
    return '576x832' if height>width else '832x576' if width>height else '768x768'
RECIPES = [
    dict(id='anima-portrait', name='Cinematic character portrait', size='832x1216',
         description='One character, an expressive gaze, soft lighting and a quiet background.',
         example=dict(subject='an adult bounty hunter with short silver hair and a red coat', scene='on a rooftop above a futuristic city at sunset', details='confident expression, wind moving the coat'),
         scene='at a quiet city overlook at sunset',
         style='cinematic anime illustration, elegant fine linework, refined cel shading, harmonious colors',
         composition='One waist-up character portrait fills the image, with a readable silhouette and a clear focal point on the face. Soft golden rim lighting and subtle reflected fill light illuminate the character. A softly detailed background has atmospheric depth.'),
    dict(id='anima-film', name='Anime film · wide scene', size='1216x832',
         description='A wide film frame with clear action, depth and atmospheric lighting.',
         example=dict(subject='an adult traveler with a blue cloak and a small leather backpack', scene='walking across a wooden bridge toward a mountain town at dawn', details='low mist in the valley, warm lights in the windows'),
         scene='crossing a bridge toward a distant mountain town at dawn',
         style='cinematic anime film still, detailed hand-painted scenery, delicate linework, nuanced colors',
         composition='A wide establishing shot has a clear foreground, middle ground and distant background. Keep the main subject readable and separate from the surroundings. Use soft dawn light, atmospheric perspective and a balanced composition.'),
    dict(id='anima-fantasy', name='Fantasy · heroic character', size='832x1216',
         description='A dramatic character illustration with magic, contrasting light and a readable pose.',
         example=dict(subject='an adult female mage with braided black hair, a green cloak and a wooden staff', scene='at the entrance of an ancient ruined temple', details='small golden magical particles, moss-covered stone, determined expression'),
         scene='standing at the entrance of an ancient ruined temple',
         style='high fantasy anime key visual, intricate costume details, fine clean linework, rich restrained colors',
         composition='Show a three-quarter character view with a grounded, readable pose and a distinct silhouette. Use dramatic side lighting, subtle magical glow and atmospheric depth. Keep the face and main costume details sharp while the background supports the character.'),
    dict(id='anima-neon', name='Cyberpunk · neon night', size='1216x832',
         description='Cool city colors, warm highlights and reflective streets.',
         example=dict(subject='an adult motorcycle courier with a black jacket and an orange helmet under one arm', scene='waiting beside a motorcycle on a rainy city street at night', details='cyan shop windows, orange streetlights, reflected neon'),
         scene='on a rain-soaked city street at night',
         style='cyberpunk anime illustration, crisp fine linework, cinematic color grading, detailed urban scenery',
         composition='A medium-wide shot has a readable subject and layered city depth. Balance cool cyan ambient light with warm orange highlights. Include subtle reflections and rain haze without hiding the main subject.'),
    dict(id='anima-landscape', name='Anime background · landscape', size='1216x832',
         description='Painterly scenery with clear layers of depth; no character required.',
         example=dict(subject='a small coastal village with red roofs and a lighthouse above the harbor', scene='on a clear summer morning', details='wildflowers in the foreground, turquoise sea, distant islands'),
         scene='in soft early morning light',
         style='anime background art, beautiful hand-painted scenery, subtle brush textures, nuanced natural colors',
         composition='A wide landscape composition has foreground framing, a detailed middle ground and a distant horizon. Build depth with atmospheric perspective and soft light. Give the scenery a clear visual focus and keep architectural shapes coherent.'),
    dict(id='anima-cozy', name='Cozy · slice of life', size='1024x1024',
         description='Warm lighting, a calm composition and small storytelling details.',
         example=dict(subject='an adult bookseller with round glasses and a knitted cardigan', scene='arranging books in a small bookshop on a rainy afternoon', details='a sleeping orange cat, a cup of tea, warm wooden shelves'),
         scene='in a small warm bookshop on a rainy afternoon',
         style='slice of life anime illustration, gentle fine linework, soft painterly shading, warm muted colors',
         composition='An intimate medium shot shows a relaxed, readable pose. Soft window light and warm interior lamps illuminate the scene. A few carefully placed environmental details support a calm, balanced composition.'),
    dict(id='anima-manga', name='Manga · ink and screentones', size='832x1216',
         description='Black and white, precise lines, screentones and clear light and dark shapes.',
         example=dict(subject='an adult detective in a long coat holding a closed umbrella', scene='at the entrance to a narrow alley in the rain', details='serious expression, wet cobblestones, strong silhouette'),
         scene='at the entrance to a narrow alley in the rain',
         style='black and white manga illustration, elegant ink linework, screentone shading, strong black and white shapes',
         composition='A dramatic three-quarter character composition has a clear silhouette and readable expression. Balance solid blacks with detailed hatching and quiet white space. Keep the image monochrome and avoid lettering or speech bubbles.'),
]

RECIPES += [
    dict(id='anima-watercolor', name='Watercolor · dreamy illustration', size='832x1216',
         description='Delicate colors, visible paper texture and soft color washes.',
         example=dict(subject='an adult botanist with a straw hat holding a bouquet of wildflowers',scene='in a sunny overgrown greenhouse',details='sage green and warm peach colors, translucent leaves'),
         scene='in a sunlit garden',style='watercolor anime illustration, delicate pencil accents, translucent color washes, textured watercolor paper',
         composition='A balanced three-quarter composition has soft edges and carefully placed fine details. Keep the subject readable against a loosely painted background. Use a harmonious pastel palette, gentle daylight and generous breathing room.'),
    dict(id='anima-chibi', name='Chibi · tiny adventurer', size='1024x1024',
         description='A tiny full-body character with exaggerated proportions, a clear silhouette and a simple background.',
         example=dict(subject='a cheerful tiny robot explorer with a round head and an orange backpack',scene='standing beside a small treasure chest on a mossy stone',details='waving one hand, mint green and orange palette'),
         scene='on a small patch of mossy stone',style='chibi anime character illustration, oversized head, small body, cute simplified proportions, clean linework, soft cel shading',
         composition='Show the entire character with a clear silhouette and an expressive face. Use a simple uncluttered backdrop, a grounded contact shadow and cheerful harmonious colors. Keep small accessories easy to read.'),
    dict(id='lowpoly-diorama',model='moss',name='Low Poly · floating diorama',size='1024x1024',
         description='A miniature scene on a floating base, with angular faces and soft studio lighting.',
         example=dict(subject='a small wooden cabin with a red roof beside a pine tree and a blue pond',scene='on a floating chunk of grassy earth',details='a tiny wooden bridge, a few angular rocks, warm light in the cabin windows'),
         scene='on a floating chunk of grassy earth',style='stylized low-poly 3D diorama render, visibly faceted polygon geometry, flat shading, simple matte materials, limited harmonious color palette',
         composition='An isometric three-quarter view shows the complete miniature scene and its solid base. Keep the geometry chunky, silhouettes clean and polygon faces clearly visible. Use a plain pastel background, soft studio lighting and gentle ambient occlusion. Avoid smooth subdivided surfaces and photographic textures.'),
    dict(id='lowpoly-retro',model='moss',name='Low Poly · 1990s game scene',size='1216x832',
         description='Angular 3D game art with distinct silhouettes and bold lighting.',
         example=dict(subject='a red rally car drifting around a mountain hairpin bend',scene='on a winding alpine road at sunset',details='angular pine trees, chunky wheels, dust behind the car, warm orange and cool blue lighting'),
         scene='on a winding mountain road at sunset',style='late-1990s low-poly 3D video game artwork, chunky polygon meshes, flat-shaded faces, simple low-detail materials, bold colors',
         composition='A dynamic wide game-camera view has one clear main action. Separate the main subject from the background with strong silhouettes and contrasting light. Keep all objects consistently low polygon, with angular edges and simplified forms. Avoid photorealistic surfaces and smooth modern CGI.'),
    dict(id='lowpoly-world',model='moss',name='Low Poly · landscape and game world',size='1216x832',
         description='A wide game world with angular mountains, rivers and clear blocks of color.',
         example=dict(subject='a valley with a turquoise river winding between angular mountains and pine forests',scene='under a clear early morning sky',details='a small stone bridge, warm yellow sunlight, cool purple mountain shadows'),
         scene='in clear early morning light',style='stylized low-poly landscape render, large visible polygon faces, flat shading, geometric terrain, simple matte colors',
         composition='A wide elevated camera view has strong foreground, middle ground and background shapes. Guide the eye toward the main subject using the terrain and a clear horizon. Use a restrained color palette and soft atmospheric depth while keeping the polygon facets visibly angular.'),
]

PHOTO_RECIPES = [
    dict(id='photo-portrait', name='Photo · natural portrait', size='832x1216',
         description='A believable portrait with natural skin texture, soft daylight and a quiet background.',
         example=dict(subject='an adult woman with freckles, short curly brown hair and a dark green linen shirt',
                      scene='sitting beside a large window in a quiet apartment',
                      details='a relaxed expression, visible fine lines, a few loose strands of hair'),
         scene='beside a large window in a quiet room',
         style='Natural portrait photography, realistic skin texture, restrained colors',
         composition='A single head-and-shoulders portrait at eye level, with the perspective of an 85mm lens. Soft available daylight reveals fine skin texture and natural facial asymmetry. The eyes are in focus, the background gently falls out of focus, and highlights retain detail.',
         tip='Describe age, hair, expression and clothing. Fine lines and natural skin texture usually give a more believable starting point than beauty or perfection tags.'),
    dict(id='photo-candid', name='Photo · candid everyday', size='1024x1024',
         description='A casual everyday moment with available light and a less polished snapshot feel.',
         example=dict(subject='an adult man with wavy dark hair and a worn denim jacket',
                      scene='laughing at a kitchen table while holding a ceramic coffee mug',
                      details='slightly untidy hair, a half-eaten piece of toast, an unposed expression'),
         scene='taking a break at a small kitchen table in daylight',
         style='Candid everyday photography, unposed snapshot, natural colors and ordinary available light',
         composition='A single informal medium shot at eye level with a natural 35mm field of view. The subject is caught mid-moment rather than posed for a studio portrait. Keep believable skin and fabric texture, modest contrast and a lived-in background, with the main subject clearly in focus.',
         tip='Give the person one small action. Ordinary clothes, a lived-in place and an unposed expression fit this recipe better than studio or fashion language.'),
    dict(id='photo-street', name='Photo · street documentary', size='1216x832',
         description='An observed street moment with environmental detail, layered depth and believable light.',
         example=dict(subject='an adult bicycle mechanic wearing a navy work jacket',
                      scene='repairing a silver city bicycle outside a small neighborhood workshop on an overcast morning',
                      details='grease marks on the hands, worn pavement, a few parked bicycles in the background'),
         scene='on a neighborhood street on an overcast morning',
         style='Documentary street photography, observational realism, restrained color',
         composition='A single environmental frame with a natural 35mm perspective and one clear main action. Show a readable foreground, subject and background with realistic scale. Available street light, believable material wear and moderate depth of field keep the setting recognizable.',
         tip='Name one action, the weather and a specific place. Ask for readable signs explicitly only when you need visible lettering.'),
    dict(id='photo-cinema', name='Photo · cinematic still', size='1216x832',
         description='A realistic film-like frame with motivated lighting, clear action and subtle color grading.',
         example=dict(subject='an adult traveler in a dark wool coat carrying a small canvas bag',
                      scene='waiting alone on a quiet railway platform at blue hour',
                      details='warm platform lamps, faint rain on the pavement, a tired thoughtful expression'),
         scene='on a quiet railway platform at blue hour under warm practical lamps',
         style='Live-action cinematic still, realistic photography, subtle film grain, restrained color grading',
         composition='One wide frame at eye level with a 50mm lens perspective and a clear focal subject. The visible practical lights motivate the illumination and shadows. Preserve realistic skin, cloth and environmental texture, balanced highlights and layered depth. Fill the entire image with the scene.',
         tip='Choose one main action and name the light source. Keep the color palette simple; combining several dramatic lighting styles can make the scene less convincing.'),
    dict(id='photo-product', name='Photo · product studio', size='1024x1024',
         description='A clean product image with coherent materials, controlled reflections and grounded shadows.',
         example=dict(subject='a matte forest-green ceramic coffee mug with a curved handle',
                      scene='on a pale stone tabletop against a warm off-white background',
                      details='subtle glaze texture, a small rounded foot, soft shadow to the right'),
         scene='on a pale tabletop against a simple off-white studio background',
         style='Realistic studio product photography, accurate material texture, neutral color',
         composition='A single product is fully visible in a three-quarter view with the perspective of a 70mm lens. A large softbox creates broad controlled highlights and a grounded contact shadow. The product is sharply defined, its geometry is coherent, and the simple background does not distract from the material.',
         tip='Specify material, finish, color and surface. For glass or metal, describe the reflections you want. Use exact quoted wording when a label matters.'),
    dict(id='photo-landscape', name='Photo · landscape and travel', size='1216x832',
         description='A natural outdoor scene with convincing terrain, atmospheric depth and restrained color.',
         example=dict(subject='a small white lighthouse above a rugged Atlantic coastline',
                      scene='at sunrise after a rain shower, with soft light breaking through the clouds',
                      details='wet dark rocks, pale sea spray, a narrow footpath through coastal grass'),
         scene='in soft morning light after a rain shower',
         style='Realistic landscape photography, natural travel photography, restrained colors',
         composition='A single wide view with a natural 28mm perspective. Distinct foreground, middle ground and a distant horizon establish depth. Realistic terrain scale, fine material texture and atmospheric perspective support the main subject. Retain detail in the sky and shadows without exaggerated HDR or excessive saturation.',
         tip='Name a place type, weather, time of day and one focal feature. Draft is for composition; use Recommended before judging fine landscape detail.'),
    dict(id='photo-interior', name='Photo · architecture and interior', size='1216x832',
         description='A believable interior with straight verticals, natural materials and balanced window light.',
         example=dict(subject='a small reading room with oak bookshelves, a cream armchair and a round side table',
                      scene='in a renovated brick apartment with tall windows on the left',
                      details='linen curtains, visible wood grain, a folded blanket and a few books'),
         scene='in a quiet apartment illuminated by a large side window',
         style='Realistic architectural interior photography, natural materials, balanced daylight',
         composition='A single wide room view from standing eye level with a corrected 24mm lens perspective and straight vertical lines. Furniture has believable scale and spacing. Soft window light, realistic indirect illumination and gentle contact shadows reveal wood, fabric and wall textures. Balance the interior exposure with the visible windows.',
         tip='Describe room size, materials, furniture and window direction. Very wide lenses, tiny rooms and too many objects can produce distorted geometry.'),
    dict(id='photo-food', name='Photo · food and still life', size='1024x1024',
         description='An appetizing close view with natural texture, soft side lighting and simple styling.',
         example=dict(subject='a rustic slice of sourdough toast topped with creamy burrata and roasted tomatoes',
                      scene='on a handmade ceramic plate on a dark wooden table beside a window',
                      details='fresh basil leaves, a few crumbs, a small amount of olive oil catching the light'),
         scene='on a ceramic plate on a wooden table beside a window',
         style='Realistic editorial food photography, natural food texture, restrained warm colors',
         composition='A single close view from a three-quarter angle with a natural 50mm perspective. Soft side light reveals texture and a few gentle highlights. Keep the main ingredients sharp with a softly receding background, believable portions and simple table styling.',
         tip='Name the dish, visible ingredients, plate and surface. Describe a small highlight or a few crumbs rather than adding many unrelated props.'),
]
RECIPES += [dict(r, model='moss', category='photo', checked='2026-10-31') for r in PHOTO_RECIPES]

RECIPES += [
    dict(id='anima-retro', name='Retro anime · 1990s cel look', size='1216x832', featured=True,
         description='Hand-painted cel colors, delicate grain and the mood of a 1990s anime frame.',
         example=dict(subject='an adult space pilot with short auburn hair and a cream flight jacket',scene='beside a large observation window overlooking a blue planet',details='amber instrument lights, a thoughtful expression, reflections on the glass'),
         scene='at a space station observation window above a blue planet',
         style='1990s anime cel illustration, hand-painted background, thin ink linework, restrained cel colors, subtle analog film grain',
         framing='single wide frame, medium character view, clear silhouette, soft amber practical light, atmospheric painted background',
         composition='A single wide anime frame with a readable main character and a painted background.',
         tip='Keep the palette and lighting simple. Describe one character and a specific environment rather than mixing retro cel art with glossy modern CGI.'),
    dict(id='anima-mecha', name='Mecha · hangar key visual', size='832x1216', featured=True,
         description='A striking giant robot with readable mechanical shapes, scale and dramatic hangar light.',
         example=dict(subject='a white and teal exploration mecha with broad shoulder armor and a small orange cockpit',scene='standing inside a vast maintenance hangar',details='a tiny adult engineer near one foot, yellow work lights, subtle wear on the armor'),
         scene='standing inside a maintenance hangar with tall overhead lights',
         style='anime mecha key visual, crisp mechanical linework, layered armor panels, refined cel shading',
         framing='single full-body robot, low camera angle, readable mechanical silhouette, hangar depth, dramatic overhead lighting',
         composition='One complete robot with clearly separated limbs and a coherent silhouette.',
         tip='Specify the robot silhouette, two main colors and one mechanical feature. Small human figures help suggest scale; complex machinery may still need another seed.'),
    dict(id='anima-storybook', name='Storybook · gouache illustration', size='1024x1024',
         description='Soft gouache shapes, textured paper and a quiet illustrated story moment.',
         example=dict(subject='a small red fox wearing a blue scarf and carrying a lantern',scene='walking along a winding path through a moonlit garden',details='oversized wildflowers, warm lantern glow, a tiny moth'),
         scene='on a winding path through a moonlit garden',
         style='storybook gouache illustration, visible paper texture, soft painted shapes, delicate pencil details, muted harmonious colors',
         framing='single illustrated scene, clear central subject, layered plants, warm lantern glow, gentle blue night colors',
         composition='A balanced picture-book illustration with clear shapes and generous breathing room.',
         tip='Use a simple action and a few storytelling props. Paper and gouache cues work best when the palette stays limited.'),
    dict(id='anima-action', name='Action · dynamic anime key visual', size='832x1216',negative_extra='heavy silhouette, extreme backlighting, underexposed face, obscured face, cropped limbs',
         description='A strong ready pose, flowing fabric and a clear open silhouette.',
         example=dict(subject='an adult swordswoman with a short dark bob, a red scarf and a navy coat',scene='standing in a wide ready stance on an open rooftop at sunset',details='one sword held diagonally in front, scarf streaming to the side, warm reflected light on the face'),
         scene='standing in a wide ready stance on an open rooftop at sunset',
         style='dynamic anime action key visual, crisp expressive linework, refined cel shading, vivid controlled colors',
         framing='solo, full body, three-quarter view, grounded wide stance, readable face, open uncluttered background, warm sunset fill light',
         composition='One readable action pose with a clear silhouette and a simple supporting environment.',
         tip='Choose one movement and describe where each important prop is. If limbs become confusing, simplify the pose before adding more detail.'),
    dict(id='moss-clay', model='moss', category='craft', name='Clay · handmade miniature', size='1024x1024', featured=True,
         description='Tactile modeling clay, tiny handmade details and soft miniature-set lighting.',
         example=dict(subject='a tiny green dragon reading a book beside a mushroom-shaped cottage',scene='on a small handmade forest set',details='visible thumbprints in the clay, a terracotta teacup, warm light in the cottage window'),
         scene='on a small handmade forest set',style='handmade clay miniature, stop-motion set aesthetic, tactile modeling clay, subtle fingerprints, soft studio lighting',
         composition='A single three-quarter view of the complete miniature scene. Rounded handmade forms, small surface imperfections and a grounded contact shadow establish scale. A softly blurred simple backdrop keeps the clay subject readable.',
         tip='Ask for tactile clay, small imperfections and one clear scene. This recipe favors rounded handmade forms rather than low-poly facets.'),
    dict(id='moss-paper', model='moss', category='craft', name='Paper cut · layered illustration', size='1216x832', featured=True,
         description='Layered colored paper, crisp cut edges and gentle shadows between the layers.',
         example=dict(subject='a red fox looking up at a crescent moon above rolling forest hills',scene='inside a layered paper-cut forest composition',details='deep blue and warm cream paper, tiny star cutouts, soft shadows between layers'),
         scene='inside a layered paper-cut forest composition',style='layered paper-cut illustration, tangible colored cardstock, clean cut edges, shallow layered depth, restrained color palette',
         composition='A single front-facing paper composition fills the frame. Distinct overlapping silhouettes and soft cast shadows reveal separate paper layers. Keep the main subject readable with large simple shapes and a balanced arrangement.',
         tip='Use a few large silhouettes and three or four colors. Layer shadows and cut edges distinguish the look from an ordinary flat drawing.'),
    dict(id='moss-comic', model='moss', category='craft', name='Comic · bold ink illustration', size='832x1216',negative_extra='text, lettering, title, masthead, speech bubbles',
         description='Bold ink, halftone shading and one strong full-frame comic scene.',
         example=dict(subject='an adult masked courier in a yellow jacket holding a red parcel',scene='on a city rooftop in strong afternoon light',details='wind in the jacket, deep navy shadows, a dramatic low angle'),
         scene='on a city rooftop in strong afternoon light',style='western comic book illustration, bold ink outlines, expressive shapes, halftone shading, limited graphic color palette',
         composition='A single full-frame comic scene has one strong central silhouette and a dramatic low camera angle. Balance large light and dark areas with restrained halftone texture. The entire image contains artwork, without panels, captions or lettering.',
         tip='Start with one readable silhouette and a limited palette. Use Qwen’s poster or cover recipe when exact visible lettering is important.'),
    dict(id='photo-macro', model='moss', category='photo', name='Photo · macro nature', size='1024x1024',
         description='A close natural detail with convincing texture, soft light and a shallow focal plane.',
         example=dict(subject='a bumblebee resting on a purple coneflower',scene='in a quiet garden on a soft overcast morning',details='tiny pollen grains, delicate wing veins, dewdrops on the petals'),
         scene='in a quiet garden on a soft overcast morning',style='realistic macro nature photography, natural color, fine organic texture',
         composition='A single close view with a 100mm macro perspective. The main subject and its immediate surface are sharply defined while the distant garden dissolves into soft bokeh. Diffuse daylight reveals delicate textures without harsh specular glare.',
         tip='Specify one small subject, its surface and two visible details. Keep the background simple; fine insect anatomy can vary across seeds.'),
]

PIXEL_RECIPES = [
    dict(id='pixel-loot',name='Pixel · tiny loot icon',
         description='A bold pixel inventory icon with a simple silhouette and a small palette.',
         example=dict(subject='a red mushroom with white spots',scene='centered on a plain white background',details='a cream stem and a bold black outline'),
         scene='centered on a plain white background',
         style='8-bit pixel art inventory icon',
         composition='One large isolated item fills most of the frame. Use a bold readable silhouette, chunky deliberate pixel clusters and simple shading. Leave a clear margin around the item. No lettering or interface.',
         tip='Use one object with a recognizable silhouette. The LoRA produces a clean pixel grid at 1024 square.'),
    dict(id='pixel-character',name='Pixel · adventure character',
         description='A complete pixel game character with readable clothing and pose.',
         example=dict(subject='a small red-haired forest ranger in a green cloak holding a wooden staff',scene='standing in a relaxed three-quarter view against a plain cream background',details='brown boots, a small leather satchel, warm amber highlights'),
         scene='standing in a relaxed three-quarter view against a plain cream background',
         style='retro 16-bit RPG character sprite, crisp square clusters, limited color palette',
         composition='Show one complete character from head to feet, centered, with a clear silhouette and space around the edges. Use a consistent light direction and simple grouped shading. No text or interface.',
         tip='Keep the pose and equipment simple. The LoRA produces a clean pixel grid at 1024 square.'),
    dict(id='pixel-isometric',name='Pixel · isometric hideaway',
         description='A miniature pixel isometric building with tidy forms and cozy details.',
         example=dict(subject='a tiny timber cabin with a red roof and a glowing round window',scene='on one small grassy isometric tile against a dark blue background',details='a stone path, one pine tree, a chimney with a small puff of smoke'),
         scene='on one small grassy isometric tile against a dark blue background',
         style='retro isometric game asset, crisp square clusters, limited color palette',
         composition='Show the complete miniature structure from an elevated three-quarter view on one isolated square ground tile. Consistent isometric perspective, clear roof and walls, simple grouped shadows. No lettering or interface.',
         tip='One building, one ground tile and two or three props work best.'),
    dict(id='pixel-landscape',name='Pixel · scenic world',
         description='A detailed pixel scene with layered scenery and a restrained palette.',
         example=dict(subject='a quiet mountain lake with a small wooden cabin and tall pine trees',scene='at sunset beneath lavender mountains and a peach-colored sky',details='a warm window reflected in the water, reeds in the foreground, a thin crescent moon'),
         scene='at sunset beneath lavender mountains and a peach-colored sky',
         style='detailed pixel art landscape, classic adventure game background',
         composition='One cohesive landscape with distinct foreground, middle distance and background. Group colors into deliberate square clusters and use a consistent light direction. No text, border or interface.',
         tip='Describe a foreground, a focal point and distant scenery. Wide aspect ratios also work.'),
]
RECIPES += [dict(r,model='flux-pixel',category='pixel',size='1024x1024',featured=True,
                 example_quality='standard',checked='2026-11-04') for r in PIXEL_RECIPES]

# MOSS handles the low-poly workflow without separate Anima style adapters.
RECIPES += [
    dict(id='lowpoly-anything', model='moss', category='lowpoly', name='Low Poly · anything',
         size='1024x1024', featured=True, example_quality='preview', preview_steps=30,
         description='A flexible low-poly look for animals, creatures, objects, characters, vehicles, places or complete scenes.',
         example=dict(subject='an orange fox with a cream chest, dark paws and a large angular tail',
                      scene='standing on a mossy rock beside a small blue pond',
                      details='two simple pine trees, broad faceted shapes, soft daylight, a warm restrained palette'),
         scene='in a simple, clearly readable setting that supports the subject',
         style='stylized low-poly 3D game art, visible flat-shaded polygon faces, broad geometric forms, simple matte material colors',
         composition='Adapt the framing and camera to the requested subject and viewpoint. Keep the main subject complete and readable, with clear silhouettes and physically understandable forms. For a scene, separate the foreground, focal subject and background. Use a small harmonious palette, consistent soft light and sparse supporting details. Preserve any requested setting without forcing a character pose, a vehicle layout or an isolated terrain tile. No lettering or interface.',
         negative_extra='wireframe overlay, triangle grid, mesh overlay, tiny surface details',
         tip='Describe anything you want in low poly. Use Setting or action for the camera: for example a bird’s-eye view, a close-up or a wide landscape. Choose Track overview for a complete circuit layout.'),
    dict(id='lowpoly-track-overview', model='moss', category='lowpoly', name='Low Poly · track overview',
         size='1216x832', featured=True, example_quality='preview', preview_steps=30,
         description='An overhead racing-circuit concept with the entire route visible and simple low-poly surroundings.',
         example=dict(subject='a compact coastal kart circuit with one closed kidney-shaped asphalt loop, a small pit garage and two grandstands',
                      scene='seen from directly above, with the entire circuit centered on one rectangular terrain tile',
                      details='a consistent-width dark gray track, red and white curbs, one short checkered start-finish stripe, sparse pine trees and blue water beyond the tile'),
         scene='seen from directly above, with the whole racing circuit visible inside the image',
         style='low-poly 3D racing game track overview, top-down circuit concept, flat-shaded terrain, simple modular structures, broad solid material colors',
         composition='Show one complete closed driving loop in a directly overhead orthographic-style view. Keep its full route visible, continuous and easy to follow, with consistent road width and open space around the outside of the circuit. Use gentle readable corners and clear track boundaries. Place sparse buildings, trees and terrain details beside the route without covering it. Keep a single driving route without branches, intersections, overpasses or a second circuit. No cars, labels, arrows, text, legend or interface.',
         negative_extra='crossroads, road junctions, disconnected road segments, cropped track edges, hidden track sections, overpasses, multiple separate circuits, low camera angle, cars covering the road',
         tip='Describe one circuit, its shape and its environment. The preset requests the complete overhead layout. Treat it as a concept image; inspect continuity and rebuild the drivable route as explicit geometry in Blender.'),
]

# Example inputs explicitly select the shared Blender composition, so the web
# example, CLI --example and isolated example builder all reproduce the same request.
MOSS_ASSET_RECIPES = [
    ('lowpoly-character', 'character', 'Low Poly · character reference', 'One full-body low-poly character with simple clothing, a neutral pose and a readable silhouette.'),
    ('lowpoly-vehicle', 'vehicle', 'Low Poly · kart and vehicle reference', 'One complete low-poly vehicle with clear wheels, chassis and panel connections.'),
    ('lowpoly-prop', 'prop', 'Low Poly · prop reference', 'A single low-poly object with clear thicknesses, simple joins and a plain background.'),
    ('lowpoly-building', 'building', 'Low Poly · building reference', 'A complete modular building with readable wall, roof, door and window volumes.'),
]
for identifier, asset, name, description in MOSS_ASSET_RECIPES:
    settings = modeling_reference.ASSETS[asset]
    RECIPES.append(dict(id=identifier, model='moss', category='lowpoly', name=name, size=settings['size'],
        description=description, featured=True, example_quality='preview',
        example=dict(settings['example'], modeling_view='three-quarter', modeling_asset=asset),
        scene='isolated on a plain light gray background',
        style='low-poly 3D asset concept, flat-shaded polygon geometry, broad angular forms, simple matte material colors',
        composition=modeling_reference.VIEWS['three-quarter']['prompt']+' '+settings['construction']+
                    ' The complete asset fits inside the frame with space around all edges. Use neutral even lighting, a faint contact shadow and a small solid-color palette. No labels, grid or surrounding scenery.',
        tip='MOSS prepares the low-poly look. Use Blender reference for a clear asset view; choose one main subject and a few large material colors.'))

# Curated 2026-11-01 from the model authors' prompting/capability guides.
# These are our templates, not official presets or guarantees of a particular style.
ADDITIONAL_RECIPES = [
    dict(id='moss-risograph', model='moss', category='craft', name='Risograph · two-ink print', size='832x1216',
         description='Two spot inks, visible paper grain and slightly offset printed layers.',
         example=dict(subject='a red bicycle leaning against a leafy blue greenhouse', scene='on an ivory paper print', details='coral red and cobalt blue inks, generous cream margins'),
         scene='on warm ivory paper', style='two-color risograph illustration, grainy soy ink, imperfect registration, overlapping spot colors',
         composition='One bold illustration with large simplified shapes, open paper highlights and restrained ink overlap. Keep the subject readable without lettering.',
         tip='Name two ink colors and leave some paper visible. This is a raster print concept, not separated print plates.'),
    dict(id='moss-embroidery', model='moss', category='craft', name='Embroidery · stitched illustration', size='1024x1024',
         description='Raised colored thread, visible stitches and a tactile woven fabric ground.',
         example=dict(subject='an orange fox curled around a crescent moon with tiny blue flowers', scene='embroidered onto oatmeal linen', details='satin stitches, French knots, a small forest-green leaf border'),
         scene='embroidered onto natural linen', style='photographed hand embroidery, tactile cotton thread, visible satin stitches and French knots, woven linen texture',
         composition='An overhead close view of one complete stitched motif. Soft side light reveals raised threads and gentle fabric shadows; leave breathing room around the design.',
         tip='Use broad shapes and a few thread colors. The output is a visual concept, not a machine embroidery file.'),
    dict(id='moss-felt', model='moss', category='craft', name='Needle felt · tiny wool world', size='1024x1024',
         description='Soft wool fibers, rounded handmade figures and a miniature scene.',
         example=dict(subject='a tiny hedgehog carrying a red mushroom umbrella', scene='on a moss-green wool hill', details='loose fuzzy fibers, a small blue puddle, warm softbox light'),
         scene='on a small wool-covered miniature set', style='needle-felted wool miniature, soft fuzzy fibers, handmade rounded shapes, macro craft photography',
         composition='One complete miniature in a three-quarter view, with soft side light revealing wool texture. Keep the backdrop quiet and the silhouette clear.',
         tip='Ask for visible wool fibers and one simple action to distinguish the look from smooth clay.'),
    dict(id='moss-stained-glass', model='moss', category='craft', name='Stained glass · luminous window', size='832x1216',
         description='Jewel-colored glass shapes, dark lead outlines and glowing transmitted light.',
         example=dict(subject='a kingfisher perched above river reeds', scene='inside one arched stained-glass window', details='turquoise, amber and ruby glass, rippled hand-blown texture'),
         scene='inside one illuminated stained-glass window', style='stained-glass artwork, luminous jewel colors, dark lead came outlines, textured translucent glass',
         composition='Show the complete window straight on, with broad connected glass pieces and a strong central motif. Light shines through the colored glass; no text.',
         tip='Use a recognizable silhouette and a few large color areas. Glass joins are an illustration, not a fabrication pattern.'),
    dict(id='anima-woodblock', model='anima', category='anime', name='Woodblock · moonlit print', size='832x1216',
         description='Carved contours, flat pigment areas and the texture of a traditional woodblock print.',
         example=dict(subject='a white crane standing among wind-bent reeds', scene='beside a quiet river under a large autumn moon', details='indigo water, vermilion leaves, warm paper highlights'),
         scene='beside a quiet river at dusk', style='Japanese woodblock print illustration, carved flowing contours, flat pigment, textured washi paper',
         framing='single vertical print, asymmetrical composition, broad flat colors, open paper highlights, no lettering',
         composition='One balanced print with large readable shapes and a limited palette.',
         tip='Specify two or three pigments and a clear silhouette. Keep modern camera and glossy rendering terms out of the description.'),
    dict(id='anima-pastel', model='anima', category='anime', name='Pastel · soft chalk illustration', size='1024x1024',
         description='Powdery chalk marks, soft edges and luminous colors on textured paper.',
         example=dict(subject='an adult astronomer in a lavender coat carrying a brass telescope', scene='walking through a peach-colored evening meadow', details='dusty blue shadows, golden grasses, a few first stars'),
         scene='in a quiet meadow at dusk', style='soft pastel illustration, powdery chalk strokes, textured paper, luminous muted colors',
         framing='single illustrated scene, readable main figure, soft broken edges, broad color masses, gentle evening light',
         composition='A calm scene with textured color masses and a clear focal point.',
         tip='Describe the chalk surface and a restrained palette; very fine costume details compete with the soft medium.'),
    dict(id='anima-dark-fantasy', model='anima', category='anime', name='Dark fantasy · painted encounter', size='832x1216',
         description='A painterly fantasy scene with dramatic scale, mist and a readable focal encounter.',
         example=dict(subject='an adult armored traveler holding a small lantern before a sleeping stone dragon', scene='at the entrance to an overgrown ruined cathedral', details='mossy arches, cool blue fog, one warm light on the traveler'),
         scene='among ancient overgrown ruins', style='dark fantasy digital painting, expressive brushwork, weathered stone, restrained cool colors',
         framing='single vertical illustration, small readable foreground traveler, immense creature in middle distance, warm focal light, layered mist',
         composition='One encounter with strong scale contrast and a visible focal subject.',
         tip='Describe where the small and large subjects sit in the scene. Keep some light on the main figure so the silhouette stays readable.'),
    dict(id='anima-solarpunk', model='anima', category='anime', name='Solarpunk · hopeful city', size='1216x832',
         description='Sunlit terraces, lush planting and an illustrated city built around everyday life.',
         example=dict(subject='a hillside neighborhood with planted balconies, a small tram and rooftop gardens', scene='on a clear spring morning', details='cream architecture, terracotta walkways, solar canopies and hanging vines'),
         scene='under clear warm morning light', style='solarpunk anime environment illustration, hand-painted architectural scenery, lush greenery, hopeful warm colors',
         framing='single wide establishing view, clear foreground terrace, connected middle-ground paths, distant hillside, readable architecture',
         composition='One coherent neighborhood with layered depth and a clear focal route.',
         tip='Choose a small neighborhood and three important structures. Greenery should support the paths and building silhouettes.'),
    dict(id='pixel-creature', model='flux-pixel', category='pixel', name='Pixel · creature sprite', size='1024x1024',
         description='One complete game creature with grouped shading and an expressive silhouette.',
         example=dict(subject='a round turquoise cave lizard with orange crystal horns', scene='in a side-on idle pose on a plain cream background', details='short sturdy legs, a curled tail, one bright amber eye'),
         scene='in an idle pose on a plain background', style='retro monster sprite, crisp square clusters, limited color palette',
         composition='Show one complete creature with space around every edge, distinct limbs and simple grouped shadows. No sprite sheet, interface or text.',
         tip='Request one pose. Multiple generations do not guarantee matching animation frames; the background stays opaque.'),
    dict(id='pixel-portrait', model='flux-pixel', category='pixel', name='Pixel · dialogue portrait', size='1024x1024',
         description='A readable character bust suitable as a starting point for a game dialogue portrait.',
         example=dict(subject='an adult airship captain with silver hair, round goggles and a navy scarf', scene='in a three-quarter bust view on a plain muted blue background', details='a friendly raised eyebrow, brass collar clasp, warm skin highlights'),
         scene='as a bust portrait on a plain background', style='retro RPG dialogue portrait, crisp square clusters, limited color palette',
         composition='A single head-and-shoulders portrait fills the image, leaving clear space above the hair. Keep the face expressive and clothing shapes broad. No dialogue box or lettering.',
         tip='Give the face one expression and one distinctive accessory.'),
    dict(id='pixel-vehicle', model='flux-pixel', category='pixel', name='Pixel · tiny vehicle', size='1024x1024',
         description='One small vehicle with clear wheels, readable bodywork and a simple background.',
         example=dict(subject='a yellow lunar delivery rover with four chunky dark wheels and a small blue cargo box', scene='in a side view on a plain cream background', details='one orange headlight, a short antenna, simple gray chassis'),
         scene='in a side view on a plain background', style='retro game vehicle sprite, crisp square clusters, limited color palette',
         composition='Show the complete vehicle with all outer edges inside the frame. Use broad body panels, readable wheels and one light direction. No track, interface or text.',
         tip='Choose side view or three-quarter view and a few large parts. This is one concept, not matched directional sprites.'),
    dict(id='pixel-dungeon', model='flux-pixel', category='pixel', name='Pixel · dungeon room', size='1024x1024',
         description='A single overhead game room with clear boundaries and a few readable props.',
         example=dict(subject='one small stone alchemist room with a round cauldron, wooden shelves and a blue rug', scene='seen from directly overhead', details='two amber lamps, one entrance at the bottom, moss in the stone corners'),
         scene='seen from directly overhead as one complete room', style='top-down pixel art dungeon environment, deliberate square clusters, limited color palette',
         composition='Keep the entire rectangular room visible with clear floor space, wall boundaries and one entrance. Place a few large props near the walls. No interface, characters or text.',
         tip='Use this as a room concept. It does not provide a seamless tileset, collision map or guaranteed navigable layout.'),
    dict(id='zimage-fantasy', model='z-image', category='zimage', name='Z-Image · fantasy matte painting', size='1216x832',
         description='A wide imaginative world with painted atmosphere and monumental scale.',
         example=dict(subject='a stone observatory built on the back of an immense sleeping tortoise', scene='in a misty mountain valley at dawn', details='tiny warm windows, hanging gardens, a narrow bridge over the river'),
         scene='in a misty mountain valley at dawn', style='fantasy matte painting, expressive painted textures, cinematic atmospheric depth',
         composition='One wide establishing view with a clear foreground, a monumental middle-ground subject and distant layered mountains. Keep the main silhouette readable and the lighting coherent.',
         tip='Describe one impossible idea with concrete materials and scale cues. Use the normal model for variety and negative-prompt control.'),
    dict(id='zimage-ink', model='z-image', category='zimage', name='Z-Image · ink wash', size='832x1216',
         description='Expressive black ink, soft washes and open rice-paper space.',
         example=dict(subject='a black heron standing on a weathered branch above still water', scene='among pale mist and loosely painted reeds', details='one small vermilion leaf, dry-brush feathers, abundant open paper'),
         scene='among pale mist and open rice-paper space', style='sumi-e ink wash illustration, expressive dry brush, bleeding black ink, textured rice paper',
         composition='A single vertical composition balances one dark focal silhouette with broad empty areas and pale gray washes. Keep the forms loose and avoid lettering or seals.',
         tip='Name the ink medium and one focal silhouette. Open paper is part of the composition, so keep extra details sparse.'),
    dict(id='zimage-retro-scifi', model='z-image', category='zimage', name='Z-Image · retro science fiction', size='832x1216',
         description='Airbrushed planets, imaginative machinery and the palette of a vintage paperback.',
         example=dict(subject='a lone explorer in an orange pressure suit facing a giant ring-shaped space station', scene='on a pale desert moon under a violet sky', details='airbrushed gradients, two distant planets, a tiny cream exploration vehicle'),
         scene='on a pale desert moon beneath a violet sky', style='1970s science-fiction paperback illustration, airbrushed gouache, subtle print grain, imaginative painted machinery',
         composition='One vertical cover-like artwork with a small foreground explorer and a large distant structure. Keep the upper sky open, the palette limited and the image free of lettering.',
         tip='Describe a vintage medium, palette and strong scale contrast. Use Qwen Cover when a checked title is the main requirement.'),
    dict(id='zimage-fashion', model='z-image', category='zimage', name='Z-Image · editorial fashion', size='832x1216', photographic=True,
         description='A deliberate fashion photograph with expressive fabric and directional light.',
         example=dict(subject='an adult model wearing an oversized rust-orange coat and sculptural black boots', scene='beside a curved concrete wall in late afternoon', details='wind lifting one coat panel, a relaxed grounded pose, long soft shadows'),
         scene='beside a textured architectural wall', style='editorial fashion photography, natural fabric texture, restrained art direction',
         composition='Show one complete outfit in a three-quarter full-body view with clear space above the head and below the feet. Directional daylight reveals the fabric and architecture while keeping the face readable.',
         tip='Name the garment silhouette, material and one pose. Negative prompts are available in free prompt mode.'),
    dict(id='zimage-botanical', model='z-image', category='zimage', name='Z-Image · botanical plate', size='832x1216',
         description='A delicate scientific-style plant illustration with clear stems, leaves and flowers.',
         example=dict(subject='one flowering branch of wild blackberry with ripe dark berries and white blossoms', scene='on warm ivory paper', details='fine pen contours, translucent watercolor, pale green leaf undersides'),
         scene='on warm ivory paper', style='vintage botanical watercolor illustration, fine pen contours, delicate transparent washes',
         composition='Show one complete plant specimen with readable branching, leaf shapes and flower details, centered with broad paper margins. No labels, scale bars or text.',
         tip='Use one plant and verify its anatomy. This is decorative artwork, not a reliable identification plate.'),
    dict(id='zimage-turbo-photo', model='z-image-turbo', category='zturbo', name='Z-Image Turbo · everyday photograph', size='1024x1024', photographic=True,
         description='A quick natural photograph with available light and an unforced everyday moment.',
         example=dict(subject='an adult bicycle mechanic with curly dark hair wearing a faded blue work shirt', scene='taking a tea break by an open workshop door', details='a relaxed smile, grease on the fingers, soft overcast daylight'),
         scene='beside an open workshop door in soft daylight', style='natural candid photograph, realistic skin and fabric texture, restrained colors',
         composition='One eye-level medium view with a relaxed main subject and a quietly detailed environment. Available daylight, subtle natural grain and believable shadows.',
         tip='Describe what should be visible directly. Turbo uses eight steps and ignores negative-prompt workflows.'),
    dict(id='zimage-turbo-cinema', model='z-image-turbo', category='zturbo', name='Z-Image Turbo · cinematic night', size='1216x832', photographic=True,
         description='A fast film-like scene with a clear action and motivated practical lighting.',
         example=dict(subject='an adult traveler with a red suitcase waiting beside a small mountain train', scene='at a quiet station during blue hour', details='warm carriage windows, cool mist, one yellow platform lamp'),
         scene='at a quiet station during blue hour', style='cinematic film still, realistic photographic texture, restrained teal and amber colors',
         composition='One wide frame with a readable main action and layered depth. Warm practical lights illuminate the subject against cool evening air, with subtle reflections and controlled contrast.',
         tip='Choose one action and two light sources. Local generation speed depends on resolution and CPU offloading.'),
    dict(id='zimage-turbo-product', model='z-image-turbo', category='zturbo', name='Z-Image Turbo · product study', size='1024x1024', photographic=True,
         description='A fast material and lighting study of one clearly framed product.',
         example=dict(subject='a matte cobalt-blue portable radio with cream knobs and a woven speaker grille', scene='on a pale peach studio sweep', details='one broad softbox reflection, subtle contact shadow, brushed metal antenna'),
         scene='on a clean neutral studio sweep', style='professional product photograph, controlled softbox lighting, accurate material texture',
         composition='One complete product in a clear three-quarter view, centered with room around its outline. A soft contact shadow grounds it and restrained reflections reveal the materials.',
         tip='Specify the material and finish of each major part. Use this to iterate on shape and color quickly.'),
    dict(id='zimage-turbo-sign', model='z-image-turbo', category='zturbo', name='Z-Image Turbo · storefront lettering', size='1216x832', photographic=True,
         description='A small storefront scene with one short English or Chinese sign.',
         example=dict(subject='a tiny corner flower shop with one dark green painted sign', scene='on a quiet cobbled street after light rain', details='terracotta pots, cream awning, warm light through the doorway', text='PETAL'),
         scene='on a quiet street after light rain', style='natural architectural photograph, realistic storefront materials, soft daylight',
         composition='One straight-on view shows the complete storefront. Put the exact requested wording on the single large sign above the door, with clear letter spacing and restrained decoration.',
         tip='Keep Visible text short and inspect the spelling. English and Chinese are documented strengths; other scripts need checking.'),
    dict(id='zimage-turbo-food', model='z-image-turbo', category='zturbo', name='Z-Image Turbo · food editorial', size='1024x1024', photographic=True,
         description='A quick appetizing food photograph with soft side light and tactile ingredients.',
         example=dict(subject='a bowl of creamy pumpkin soup with toasted seeds and a small swirl of cream', scene='on a dark wooden table beside a large window', details='a torn slice of bread, linen napkin, a few scattered pumpkin seeds'),
         scene='on a wooden table beside a large window', style='editorial food photography, natural ingredient textures, gentle warm colors',
         composition='One close three-quarter view keeps the main dish sharp and the surrounding table softly receding. Soft window light reveals texture, gentle highlights and believable portions.',
         tip='Use one dish, one surface and a few props. More steps are not the quality control for this distilled model.'),
]
for recipe in ADDITIONAL_RECIPES:
    recipe['checked'] = '2026-11-01'
    recipe['evidence'] = 'Curated template based on model-author guidance; inspect the generated example for style fit.'
    if recipe['model'] in ('z-image', 'z-image-turbo'):
        # Stay within the public API's 1024-dimension limit until local GPU
        # verification has established larger sizes for these exact weights.
        recipe['size'] = {'832x1216':'768x1024', '1216x832':'1024x768'}.get(recipe['size'], recipe['size'])
RECIPES += ADDITIONAL_RECIPES

ASSET_RECIPES = []
for family,model in (('lowpoly','moss'),('pixel','flux-pixel')):
    for asset,label in (('character','character'),('vehicle','kart'),('prop','prop')):
        example=dict(modeling_reference.ASSETS[asset]['example'],modeling_view='sheet',modeling_asset=asset)
        ASSET_RECIPES.append(dict(id=family+'-'+label+'-sheet',model=model,category='lowpoly' if family=='lowpoly' else 'pixel',
            name=('Low Poly' if family=='lowpoly' else 'Pixel')+' · '+label+' concept sheet',size='1024x1024',
            description='Four proposed views of one '+label+' design. AI estimates can differ; use a 3D model for geometry-consistent views.',
            example=example,scene='on a plain light gray background',style='game asset concept sheet',composition='Four aligned proposed views of one asset.',
            default_modeling_view='sheet',example_quality='standard' if family=='pixel' else 'preview',
            tip='Compare the four proposed silhouettes, part counts and colors yourself.'))
for identifier,asset,label in (('voxel-character','character','character'),('voxel-kart','vehicle','kart'),
                              ('voxel-prop','prop','prop'),('voxel-building','building','building'),('voxel-diorama','scene','diorama')):
    example=dict(modeling_reference.ASSETS[asset]['example'],modeling_view='three-quarter',modeling_asset=asset)
    ASSET_RECIPES.append(dict(id=identifier,model='moss',category='voxel',name='Voxel · '+label+' asset',size=modeling_reference.ASSETS[asset]['size'],
        description='A cubic voxel-style '+label+' concept with readable block shapes and a small material palette.',
        example=example,scene='on a plain light gray background',style='voxel art, visible cubic blocks, stepped forms, consistent cube size, matte limited colors',
        composition='One complete voxel-style asset, clear silhouette, neutral light and plain background.',
        tip='This preset generates a voxel-style image.'))
ASSET_RECIPES.append(dict(id='voxel-anything',model='moss',category='voxel',name='Voxel · anything',size='1024x1024',
    description='Voxel-style creatures, objects and small worlds built from clear cubic blocks.',
    example=dict(subject='a small orange fox beside a blue pond and three pine trees',scene='on one square voxel terrain tile',details='large visible cubes, orange fur, green trees and pale blue water'),
    scene='on a simple square base',style='voxel art 3D scene, large visible cubic blocks, stepped forms, limited matte colors',
    composition='One complete miniature scene with a consistent cube size and clear color groups, seen from an elevated three-quarter angle.',
    tip='Describe the main shapes and a few colors. This is an image concept; it does not contain voxel geometry.'))
for recipe in ASSET_RECIPES:recipe.update(checked='2026-11-02',evidence='Curated asset concept; camera directions and cross-view geometry are not certified.')
RECIPES += ASSET_RECIPES

def recipes():
    return [dict(r, model=r.get('model','anima'), version=VERSION,preview_size=preview_size(r['size']),
                 modeling_asset=modeling_reference.RECIPE_ASSETS.get(r['id']),
                 category=r.get('category','anime' if r.get('model','anima')=='anima' else 'lowpoly'),
                 source={'anima':SOURCE,'moss':MOSS_SOURCE,'flux-pixel':'https://huggingface.co/adirik/pixel-art-lora-flux.2-klein-4B'}.get(r.get('model','anima'),MODELS[r.get('model','anima')]['source']),
                 checked=r.get('checked','2026-10-31'), steps=defaults(r.get('model','anima'))['steps'],
                 cfg_scale=defaults(r.get('model','anima'))['cfg'],sampler='euler') for r in RECIPES]

def compose(body):
    allowed={'model','recipe','subject','scene','details','text','aspect_ratio','quality','seed','modeling_view','modeling_asset'}
    if set(body)-allowed:
        raise ValueError('Unknown guided settings. Use recipe inputs, Blender reference options or free prompt mode for custom parameters.')
    recipe=next((r for r in RECIPES if r['id']==body.get('recipe')),None)
    if recipe is None: raise ValueError('Unknown recipe.')
    model=recipe.get('model','anima')
    if body.get('model',model)!=model:raise ValueError('This recipe belongs to model '+model+'.')
    fields={}
    for key,maximum in [('subject',2000),('scene',2000),('details',2000),('text',600)]:
        value=body.get(key,'')
        if not isinstance(value,str) or len(value)>maximum:
            raise ValueError(f'{key}: use at most {maximum} characters.')
        fields[key]=value.strip()
    if not fields['subject']: raise ValueError('Enter what you would like to see in the image.')
    if fields['text'] and model not in ('z-image','z-image-turbo'):raise ValueError('Visible text is available in Z-Image recipes. Use the details field with other models.')
    ratio=body.get('aspect_ratio','auto')
    if not isinstance(ratio,str) or (ratio!='auto' and ratio not in FORMATS):raise ValueError('Choose a supported aspect ratio or Recommended.')
    quality=body.get('quality','standard')
    if quality not in ('preview','standard','detail'):raise ValueError('Unknown quality profile.')
    reference=modeling_reference.compose(body,dict(recipe,model=model),fields)
    scene=fields['scene'] or recipe['scene']
    prompt=f"single image, single scene, {recipe['style']}. Main subject: {fields['subject']}. Setting and action: {scene}. {recipe['composition']}"
    if fields['details']:prompt+=' Additional requested details: '+fields['details']+'.'
    if model=='anima':
        framing={
            'anima-portrait':'solo, portrait, upper body, looking at viewer, golden rim light, softly blurred background',
            'anima-film':'wide shot, clear foreground and background, atmospheric perspective, soft dawn light',
            'anima-fantasy':'solo, three-quarter view, readable pose, dramatic side light, subtle magical glow',
            'anima-neon':'medium-wide shot, cyan ambient light, orange highlights, wet reflections, atmospheric depth',
            'anima-landscape':'wide landscape, layered scenery, distant horizon, soft morning light',
            'anima-cozy':'medium shot, relaxed pose, soft window light, warm interior lamps, calm composition',
            'anima-manga':'three-quarter view, strong silhouette, expressive face, hatching, balanced black and white',
            'anima-watercolor':'three-quarter view, pastel palette, gentle daylight, soft edges, loosely painted background',
            'anima-chibi':'full body, simple background, clear silhouette, cheerful colors, soft contact shadow',
        }
        prompt=f"{recipe['style']}, {recipe.get('framing',framing.get(recipe['id']))}. {fields['subject']}, {scene}."
        if fields['details']:prompt+=' '+fields['details']+'.'
    photo=recipe.get('category')=='photo'
    if photo:
        prompt=f"{recipe['style']}. The image shows {fields['subject']}, {scene}. {recipe['composition']}"
        if fields['details']:prompt+=' Additional details: '+fields['details']+'.'
        negative=PHOTO_NEGATIVE
    else:
        negative=NEGATIVE+(', color, colored illustration' if recipe['id']=='anima-manga' else ', manga, comic, storyboard, letterboxing')
        if recipe['id'].startswith('lowpoly-'):negative+=' , smooth subdivided geometry, photorealistic textures, glossy plastic'
    if recipe.get('category')=='craft' or model in ('z-image','z-image-turbo'):
        prompt=f"{recipe['style']}. {fields['subject']}, {scene}. {recipe['composition']}"
        if fields['details']:prompt+=' Additional details: '+fields['details']+'.'
        if fields['text']:prompt+=' Visible wording must read exactly: '+repr(fields['text'])+'. Preserve the spelling, capitalization and line breaks.'
        if recipe.get('transparent'):prompt='This is an RGBA image with transparency. '+prompt+' The image has alpha channel and the background is transparent.'
        negative=PHOTO_NEGATIVE if recipe.get('photographic') else 'worst quality, low quality, watermark, jpeg artifacts, collage, split screen, cropped main subject'
    if recipe.get('negative_extra'):negative+=', '+recipe['negative_extra']
    if not MODELS[model]['negative']:negative=''
    if model=='flux-pixel':
        prompt=f"PXART4. {recipe['style']}. {fields['subject']}, {scene}. {recipe['composition']}"
        if fields['details']:prompt+=' Additional details: '+fields['details']+'.'
    if reference:
        prompt,negative=reference['prompt'],reference['negative_prompt']
    selected_formats=model_formats(model)
    size=(reference['size'] if reference else recipe['size']) if ratio=='auto' else selected_formats[ratio][1]
    draft_size=preview_size(size) if ratio=='auto' else selected_formats[ratio][2]
    sampling_model=model
    steps={'anima':{'preview':30,'standard':35,'detail':45},'moss':{'preview':recipe.get('preview_steps',30 if photo or reference else 20),'standard':50,'detail':60},'flux-pixel':{'preview':12,'standard':20,'detail':35},'z-image':{'preview':28,'standard':40,'detail':50},'z-image-turbo':dict.fromkeys(('preview','standard','detail'),8)}[sampling_model]
    result=dict(model=model,prompt=prompt,size=draft_size if quality=='preview' else size,
                steps=steps[quality],cfg_scale=defaults(model)['cfg'],sampler='euler',negative_prompt=negative,preset='none')
    if 'seed' in body:result['seed']=body['seed']
    return result
