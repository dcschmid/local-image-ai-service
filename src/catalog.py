"""Curated model capabilities and visible, editable style recipes (checked 2026-10-30)."""
from pathlib import Path
CHECKED = '2026-10-30'
MODELS = {
    'moss': dict(name='MOSS SFT', license='Apache-2.0', source='https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT',
                 steps=50, cfg=3., sampler='euler', scheduler='discrete', shift=5., modes=['text'], negative=True,
                 tip='Choose a realistic photography recipe or a low-poly scene. Each recipe prepares lighting, composition and settings; only your subject is required.'),
}
MODELS['anima'] = dict(name='Anima Aesthetic · 1.1', license='CircleStone (commercial image use allowed)',
    license_url='https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md',
    source='https://huggingface.co/circlestone-labs/Anima', steps=35,cfg=4.5,sampler='euler',scheduler='discrete',shift=None,
    modes=['text'],negative=True,tip='For anime and illustration: choose a recipe and describe your subject. Aesthetic needs no score_* tags.')
for identifier,name,source,weight,tip in (
    ('anima-psx','Anima · Low Poly PS1 / PSX','https://civitai.com/models/2485743?modelVersionId=2794693',.9,
     'A trained Anima style for retro game characters, scenes and props. Describe a clear silhouette and simple materials. The PSX LoRA is applied automatically.'),
    ('anima-lowpoly','Anima · Low Poly Style','https://civitai.com/models/2204336?modelVersionId=2692813',.75,
     'A trained Anima style for angular characters, miniature dioramas and game worlds. The recipe adds the l0wp0ly trigger and the Low Poly Style LoRA.'),
):
    # Each style is a selectable profile over the same Anima base components.
    # Keep its adapter identity separate so saved images retain the exact style.
    MODELS[identifier]=dict(MODELS['anima'],name=name,base_model='anima',source=source,license_url=source,
        license='Base: CircleStone · LoRA: creator terms (commercial images allowed)',
        lora_strength=weight,tip=tip)
MODELS['anima-lowpoly']['adapter_revision']='qwen-names-v1'
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
]

def quality_profiles(model):
    m=MODELS[model]
    if not m['negative']:
        return [{'id':'standard','name':'Recommended · fewer steps','steps':m['steps']}]
    anima=model=='anima' or m.get('base_model')=='anima'
    preview=30 if anima else 20
    return [{'id':'preview','name':'Draft · faster','steps':preview},
            {'id':'standard','name':'Recommended','steps':m['steps']},
            {'id':'compare','name':'More steps · compare','steps':45 if anima else 50}]

def model_loras(model,files):
    """Build native adapter settings from trusted configuration, never prompt text."""
    strength=MODELS[model].get('lora_strength')
    return [] if strength is None else [dict(path=Path(files['lora']).name,multiplier=strength)]

def presets():
    return [dict(id=i, name=n, suffix=s, negative=neg, tip=t, source='https://huggingface.co/circlestone-labs/Anima',
                 checked=CHECKED, evidence='Curated style preset; no measured quality guarantee')
            for i,n,s,neg,t in STYLES]

def defaults(model):
    m = MODELS[model]
    return {k:m[k] for k in ('steps','cfg','sampler','scheduler','shift')}
