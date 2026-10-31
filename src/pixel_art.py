"""Deterministic palette and grid cleanup for the curated Krea pixel LoRAs."""
import io
import json
from PIL import Image, PngImagePlugin

GRIDS = (32, 64, 128)
COLORS = (16, 24, 32, 64, 128)

def settings(grid=64, colors=24):
    if type(grid) is not int or grid not in GRIDS:
        raise ValueError('Choose a pixel grid of 32, 64 or 128.')
    if type(colors) is not int or colors not in COLORS:
        raise ValueError('Choose a palette of 16, 24, 32, 64 or 128 colors.')
    return grid, colors

def refine(raw, grid=64, colors=24):
    """Return enlarged PNG, native PNG and metadata. Canvas scale is based on 1024px."""
    settings(grid, colors)
    # Derive one cell size for both axes so non-square canvases keep square pixels.
    cell = 1024 // grid
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if image.width % cell or image.height % cell:
            raise ValueError('The canvas must align with the selected pixel grid.')
        width, height = image.width // cell, image.height // cell
        palette = image.convert('RGB').quantize(colors=colors, method=Image.Quantize.MEDIANCUT,
                                               dither=Image.Dither.NONE)
        native = Image.new('P', (width, height))
        native.putpalette(palette.getpalette())
        pixels = []
        for y in range(height):
            for x in range(width):
                left, top = x * cell, y * cell
                counts = palette.crop((left, top, left+cell, top+cell)).getcolors(256)
                largest = max(count for count, _ in counts)
                tied = sorted(color for count, color in counts if count == largest)
                center = palette.getpixel((left+cell//2, top+cell//2))
                # Prefer a representative center color on ties, then a stable palette index.
                pixels.append(center if center in tied else tied[0])
        native.putdata(pixels)
        native = native.convert('RGB')
        metadata = dict(algorithm_version=1, grid=grid, colors=colors, width=width, height=height, scale=cell)
        info = PngImagePlugin.PngInfo()
        for key, value in image.info.items():
            if isinstance(value, str):
                info.add_text(key, value)
        info.add_text('AtelierPixel', json.dumps(metadata, sort_keys=True))
        out, small = io.BytesIO(), io.BytesIO()
        native.save(small, format='PNG', pnginfo=info)
        native.resize(image.size, Image.Resampling.NEAREST).save(out, format='PNG', pnginfo=info)
        return out.getvalue(), small.getvalue(), metadata
