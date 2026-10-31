"""Single-view low-poly concepts intended for rebuilding in Blender, not measured blueprints."""

VERSION = 1
RECIPE_ASSETS = {
    'lowpoly-diorama': 'scene', 'lowpoly-retro': 'vehicle', 'lowpoly-world': 'scene',
    'lowpoly-character': 'character', 'lowpoly-vehicle': 'vehicle',
    'lowpoly-prop': 'prop', 'lowpoly-building': 'building',
}
ASSETS = {
    'character': dict(name='Character · full body', size='832x1216',
        example=dict(subject='an adult forest courier with short brown hair, a green jacket and brown boots', scene='neutral A-pose, a short jacket ending above the hips, simple trousers', details='three main material colors: forest green cloth, brown leather and cream fabric; one small belt pouch'),
        construction='Use a neutral standing A-pose, arms slightly away from the torso, hands separated from the hips and feet apart on the same ground line. Show the entire character from head to soles. Keep clothing volumes simple and accessories clear of the body silhouette.'),
    'vehicle': dict(name='Vehicle · kart or machine', size='1216x832',
        example=dict(subject='a compact low-poly racing kart with four exposed black tires, one seat and a simple tubular chassis', scene='short front bumper, two axles, centered seat and steering wheel, no driver', details='matte orange body panels, dark blue seat and frame, gray wheel hubs; large solid color regions'),
        construction='Show the complete assembled vehicle with wheels straight, the chassis level and a readable relationship between chassis, axles, wheels and seat. Keep panels, wheel attachments and mechanical joins simple and physically connected. There is no driver.'),
    'prop': dict(name='Prop · single object', size='1024x1024',
        example=dict(subject='a small wooden treasure chest with a flat lid, two iron bands and a square latch', scene='lid closed, rectangular body, clearly visible wood thickness and simple hinges', details='warm brown wood, dark gray iron bands and one brass latch; no scattered coins'),
        construction='Show one complete assembled object in a stable resting position. Make its main volumes, thicknesses and functional joins readable. Keep separate parts visibly connected and small details large enough to rebuild.'),
    'building': dict(name='Building · modular structure', size='1024x1024',
        example=dict(subject='a tiny workshop with a simple gable roof, one front door and one square side window', scene='rectangular footprint, walls of equal height, one separate roof volume on top', details='cream walls, a terracotta roof, dark brown door and window frames; no garden props'),
        construction='Show one complete building from foundation to roof. Use simple wall and roof volumes, visible thicknesses, clear door and window openings and a readable modular structure. Omit surrounding scenery and decorative props.'),
    'scene': dict(name='Environment · modular tile', size='1216x832',
        example=dict(subject='a small low-poly campsite tile with one triangular tent, two pine trees and a short stone path', scene='one flat square ground tile, the objects spaced apart with their bases clearly visible', details='muted green ground, orange tent, dark green trees and gray stones; no distant landscape'),
        construction='Show one compact complete ground tile with a few clearly separated modular structures. Keep paths, ground planes and building footprints readable. Use a simple flat base, sparse props and clear gaps between major forms.'),
}
VIEWS = {
    'three-quarter': dict(name='Three-quarter · understand the forms',
        prompt='One orthographic-style three-quarter view shows the front and left side with only a modest elevation. Parallel edges remain parallel and there is no wide-angle distortion.'),
    'front': dict(name='Front · straight on',
        prompt='One straight-on front view, camera level and centered, orthographic projection, no three-quarter angle and no perspective convergence.'),
    'side': dict(name='Left side · profile',
        prompt='One strict left-side profile, camera level and perpendicular to the side, orthographic projection, no three-quarter angle and no perspective convergence.'),
    'back': dict(name='Back · straight on',
        prompt='One straight-on back view, camera level and centered behind the asset, orthographic projection, no three-quarter angle and no perspective convergence.'),
    'top': dict(name='Top · directly overhead',
        prompt='One top view looking vertically down, orthographic projection, no tilted camera and no perspective convergence.'),
}
STYLES = {
    'moss': 'low-poly 3D asset modeling reference, flat-shaded polygon geometry, simple matte base colors',
}


def options():
    return dict(assets=[dict(id=key, name=value['name'], size=value['size'], example=value['example']) for key, value in ASSETS.items()],
                views=[dict(id='off', name='Concept image · original recipe')] +
                      [dict(id=key, name=value['name']) for key, value in VIEWS.items()])


def compose(body, recipe, fields):
    """Return an optional reference composition while leaving legacy recipes unchanged."""
    if not {'modeling_view', 'modeling_asset'} & body.keys():
        return None
    if recipe['id'] not in RECIPE_ASSETS:
        raise ValueError('Blender reference settings are available only with low-poly recipes.')
    view = body.get('modeling_view', 'off')
    if not isinstance(view, str) or view not in ('off', *VIEWS):
        raise ValueError('Choose a supported Blender reference view.')
    if view == 'off':
        if 'modeling_asset' in body:
            raise ValueError('Choose a Blender reference view before choosing an asset type.')
        return None
    asset = body.get('modeling_asset', RECIPE_ASSETS[recipe['id']])
    if not isinstance(asset, str) or asset not in ASSETS:
        raise ValueError('Choose a supported Blender asset type.')
    # Replace the beauty-shot composition rather than appending contradictory
    # full-body instructions to a portrait, cinematic scene or floating island.
    prompt = f"{STYLES[recipe['model']]}. {fields['subject']}. {VIEWS[view]['prompt']} {ASSETS[asset]['construction']}"
    if fields['scene']:
        prompt += ' Construction and pose requirements: ' + fields['scene'] + '.'
    if fields['details']:
        prompt += ' Design details and material colors: ' + fields['details'] + '.'
    prompt += (' The complete asset fits inside the frame with clear space around every edge, centered on a plain light gray background.'
               ' Use broad simple polygon faces, clear part boundaries and a small palette of solid material colors.'
               ' Neutral even studio lighting reveals the forms with only a faint contact shadow.'
               ' Keep material color separate from lighting: no painted shadows, highlights or reflections in the textures.'
               ' Show a single asset in a single view without text, grids, measurement lines or a surrounding scene.')
    negative = ('worst quality, low quality, blurry, jpeg artifacts, watermark, signature, cropped asset, cut off feet,'
                ' close-up portrait, dramatic pose, motion blur, depth of field, fog, dramatic lighting, hard cast shadows,'
                ' glossy reflections, baked lighting, photorealistic textures, smooth subdivided geometry, tiny surface details,'
                ' floating disconnected parts, collage, split screen, turnaround sheet, multiple views, duplicated asset,'
                ' text, labels, dimension arrows, wireframe overlay, background scenery')
    # Image models tend to favor three-quarter beauty shots. Put the requested
    # direction first and explicitly exclude competing angles for axis views.
    if view == 'side':
        prompt = 'from side, profile, side view, facing right. ' + prompt
        if asset == 'character':
            prompt += ' The head, torso and feet all face right in profile; the far side is occluded by the near side. Do not rotate the torso or camera toward the viewer.'
        else:
            prompt += ' Show only the left-side elevation; the near side occludes the far side. Do not rotate the asset or camera toward the viewer.'
        negative += ', front view, from front, three-quarter view, turned torso, looking at viewer'
    elif view == 'back':
        prompt = 'from behind, back view. ' + prompt
        negative += ', front view, from front, three-quarter view, looking at viewer'
    elif view == 'top':
        prompt = 'from above, top-down view. ' + prompt
        negative += ', front view, side view, three-quarter view, tilted camera'
    return dict(prompt=prompt, negative_prompt=negative, size=ASSETS[asset]['size'])
