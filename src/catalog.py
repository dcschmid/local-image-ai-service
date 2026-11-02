"""Curated model capabilities and visible, editable style recipes (checked 2026-11-01)."""
CHECKED = '2026-11-01'
MODELS = {
    'moss': dict(name='MOSS SFT', license='Apache-2.0', source='https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT',
                 steps=50, cfg=3., sampler='euler', scheduler='discrete', shift=5., modes=['text'], negative=True,
                 tip='Choose a realistic photography recipe or a low-poly scene. Each recipe prepares lighting, composition and settings; only your subject is required.'),
}
MODELS['anima'] = dict(name='Anima Aesthetic · 1.1', license='CircleStone (commercial image use allowed)',
    license_url='https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md',
    source='https://huggingface.co/circlestone-labs/Anima', steps=35,cfg=4.5,sampler='euler',scheduler='discrete',shift=None,
    modes=['text'],negative=True,tip='For anime and illustration: choose a recipe and describe your subject. Aesthetic needs no score_* tags.')
MODELS['qwen21'] = dict(name='Qwen Image 2.1 · Uncensored GGUF', license='Qwen Research (non-commercial research/evaluation)',
    license_url='https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE',
    source='https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized',
    steps=40,cfg=6.,sampler='euler',scheduler='flux',shift=None,modes=['text'],negative=True,
    tip='For detailed scenes, typography and transparent stickers. The supplier labels this upstream-weight GGUF uncensored. Qwen Research License: non-commercial research and evaluation only.')
MODELS['krea-pixel'] = dict(name='Krea 2 · Pixel Art',license='LoRAs: MIT · Base: Krea 2 Community License',
    license_url='https://www.krea.ai/krea-2-licensing',source='https://huggingface.co/e-n-v-y/Krea-2-Pixel-Art',
    steps=8,cfg=1.,sampler='euler',scheduler='flux',shift=None,modes=['text'],negative=False,
    extra_sample_args='base_shift=1.15,max_shift=1.15',
    tip='Pixel art with the 32, 64 or 128 pixel LoRA on Krea 2 Turbo. Generate at 1024 square, then refine to a clean grid and palette. LoRA and base-model licenses both apply.')
SAMPLERS = ['euler', 'euler_a', 'heun', 'dpm++2m']
MODELS['z-image'] = dict(name='Z-Image', license='Apache-2.0',
    source='https://huggingface.co/Tongyi-MAI/Z-Image',
    steps=40, cfg=4., sampler='euler', scheduler='discrete', shift=6., modes=['text'], negative=True,
    tip='For creative illustration, varied characters and photography. Use descriptive sentences; negative prompts are supported. Recommended: 40 steps and CFG 4.')
MODELS['z-image-turbo'] = dict(name='Z-Image Turbo', license='Apache-2.0',
    source='https://huggingface.co/Tongyi-MAI/Z-Image-Turbo',
    steps=8, cfg=1., sampler='euler', scheduler='discrete', shift=3., modes=['text'], negative=False,
    tip='For quick photographs, product ideas and short English or Chinese lettering. Eight steps, CFG 1 and no negative prompt; describe the result you want directly.')
STYLES = [
    ('none', 'Custom style', '', '', 'Start by describing the subject, action and composition.'),
    ('photo', 'Natural photograph', 'natural documentary photograph, realistic skin texture, soft daylight, natural colors', '', 'Name a specific light source; avoid excessive sharpness and beauty-related terms.'),
    ('portrait', 'Studio portrait', 'studio portrait photograph, soft key light, subtle rim light, neutral backdrop, detailed skin', '', 'Describe framing, gaze direction and lighting separately.'),
    ('product', 'Product photography', 'professional product photograph, clean seamless backdrop, softbox lighting, accurate material texture', '', 'Specify the material, surface and shadows.'),
    ('cinema', 'Film still', 'cinematic film still, motivated lighting, atmospheric depth, restrained color grading', '', 'Choose one clear main action and one camera angle.'),
    ('comic', 'Western comic', 'western comic book illustration, bold ink outlines, expressive poses, halftone shading, graphic color palette', '', 'Start with individual panels; add clean lettering later.'),
    ('line', 'Clean line art', 'clean line art illustration, precise contours, flat colors, minimal shading, readable silhouettes', '', 'Describe a few shapes and a limited color palette.'),
    ('manga', 'Manga · black and white', 'black and white manga illustration, expressive ink linework, screentone shading, strong contrast', 'color, photorealistic', 'Mention hatching and screentones explicitly.'),
    ('anime', 'Anime · cel shading', 'anime illustration, clean lineart, cel shading, expressive eyes, detailed background', 'photorealistic, 3d render', 'Anima understands tags and sentences. Use guided mode for an easy starting point.'),
    ('background', 'Anime background', 'anime background art, painterly scenery, atmospheric perspective, delicate light, no people', '', 'Describe the foreground, middle ground and background separately.'),
    ('risograph', 'Two-ink risograph', 'two-color risograph illustration, grainy spot ink, slightly offset registration, warm paper texture', '', 'Choose two ink colors and a few large shapes; leave some paper visible.'),
    ('embroidery', 'Hand embroidery', 'hand-embroidered illustration, raised cotton thread, visible satin stitches, woven linen ground', '', 'Use a compact motif, broad stitched shapes and a small thread palette.'),
    ('woodblock', 'Woodblock print', 'woodblock print illustration, carved flowing contours, flat pigment areas, textured washi paper', '', 'Name a few pigments and a strong silhouette.'),
    ('ink-wash', 'Ink wash', 'expressive ink wash illustration, dry-brush contours, soft gray washes, open rice-paper space', '', 'Choose one focal subject and leave broad quiet areas.'),
    ('retro-scifi', 'Vintage science fiction', '1970s science-fiction illustration, airbrushed gouache, subtle print grain, imaginative painted machinery', '', 'Give the scene a scale contrast and a limited palette.'),
    ('pastel', 'Soft pastel', 'soft pastel illustration, powdery chalk strokes, broken edges, textured paper, luminous muted colors', '', 'Prefer broad color masses and a clear focal subject over fine details.'),
    ('voxel', 'Voxel art', 'voxel art, visible cubic blocks, consistent cube size, stepped silhouettes, matte limited palette', '', 'Keep the main shapes chunky. This creates a voxel-style image; use 3D Asset Views for an actual cubic mesh.'),
]

def quality_profiles(model):
    m=MODELS[model]
    if not m['negative']:
        return [{'id':'standard','name':'Recommended · fewer steps','steps':m['steps']}]
    anima=model=='anima'
    preview=30 if anima else 28 if model=='z-image' else 20
    return [{'id':'preview','name':'Draft · faster','steps':preview},
            {'id':'standard','name':'Recommended','steps':m['steps']},
            {'id':'compare','name':'More steps · compare','steps':45 if anima else 50}]

def presets():
    return [dict(id=i, name=n, suffix=s, negative=neg, tip=t,
                 source=MODELS['moss' if i in ('none','photo','portrait','product','cinema','comic','risograph','embroidery','voxel') else 'anima']['source'],
                 checked=CHECKED, evidence='Curated style preset; no measured quality guarantee')
            for i,n,s,neg,t in STYLES]

def defaults(model):
    m = MODELS[model]
    return {k:m[k] for k in ('steps','cfg','sampler','scheduler','shift')}
