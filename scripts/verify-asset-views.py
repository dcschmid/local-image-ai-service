#!/usr/bin/env python3
"""CPU-only integration verification using the original demo kart and color fixtures."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from asset_views import AssetViews,VIEWS,blender_path,validate_glb

COLOR_FIXTURE='''import bpy,sys
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for x in (-1,1):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(x,0,.5));obj=bpy.context.object
 material=bpy.data.materials.new('texture' if x<0 else 'vertex');material.use_nodes=True
 shader=material.node_tree.nodes.get('Principled BSDF')
 if x<0:
  image=bpy.data.images.new('red-green',width=2,height=1);image.pixels[:]=[.9,.02,.02,1,.02,.9,.02,1];image.pack()
  node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;node.interpolation='Closest'
  for polygon in obj.data.polygons:
   for index in polygon.loop_indices:obj.data.uv_layers.active.data[index].uv=(.25 if polygon.index%2 else .75,.5)
 else:
  attribute=obj.data.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='CORNER')
  for value in attribute.data:value.color=(.02,.02,.9,1)
  node=material.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name='Color'
 material.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color']);obj.data.materials.append(material)
bpy.ops.export_scene.gltf(filepath=sys.argv[sys.argv.index('--')+1],export_format='GLB',export_cameras=False,export_lights=False)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    root=args.output or Path(tempfile.mkdtemp(prefix='atelier-asset-verify-'));root.mkdir(parents=True,exist_ok=True)
    renderer=AssetViews(root/'jobs');report=[]
    def render(path,style,front='-Y',grid=64):
        raw=path.read_bytes();validate_glb(raw)
        job=renderer.submit(dict(data=base64.b64encode(raw).decode(),name=path.stem,style=style,front=front,pixel_grid=grid,voxel_grid=24,colors=24))
        deadline=time.monotonic()+340
        while job['status'] in ('queued','rendering') and time.monotonic()<deadline:
            time.sleep(.3);job=renderer.get(job['id'])
        assert job['status']=='completed',job
        directory=renderer.folder(job['id'])/'output';manifest=json.loads((directory/'asset-views.json').read_text())
        assert manifest['source_sha256']==hashlib.sha256(raw).hexdigest()
        assert len(manifest['cameras'])==7 and {camera['projection'] for camera in manifest['cameras']}=={'ORTHO'}
        assert len({camera['ortho_scale'] for camera in manifest['cameras']})==1
        validate_glb((directory/'model.glb').read_bytes())
        with zipfile.ZipFile(directory/'views.zip') as archive:
            assert archive.testzip() is None
            for name,digest in manifest['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
        for view in VIEWS:
            with Image.open(directory/(view+'.png')) as image:
                assert image.size==(512,512) and image.getchannel('A').getbbox()
        if style=='pixel':
            palette=set()
            for view in VIEWS:
                with Image.open(directory/(view+'.native.png')) as image:
                    assert image.size==(grid,grid)
                    assert set(image.getchannel('A').getdata())<={0,255}
                    palette|={pixel[:3] for pixel in image.getdata() if pixel[3]}
            assert len(palette)<=24
        if style=='voxel':assert manifest['voxel']['cells']>0 and manifest['voxel']['approximation']
        report.append(dict(style=style,front=front,seconds=job['seconds'],output=str(directory),source_sha256=manifest['source_sha256'],warnings=manifest['warnings']))
        print(json.dumps(report[-1]),flush=True);return directory,manifest
    demo=ROOT/'studio/public/asset-examples/kart.glb'
    original={}
    for style in ('model','lowpoly','pixel','voxel'):original[style]=render(demo,style)
    reversed_dir,reversed_manifest=render(demo,'pixel','+Y',32)
    camera=lambda manifest,name:next(c for c in manifest['cameras'] if c['view']==name)
    assert camera(original['pixel'][1],'back')['position']==camera(reversed_manifest,'front')['position']
    assert camera(original['pixel'][1],'front')['rotation_quaternion']!=camera(reversed_manifest,'front')['rotation_quaternion']
    fixture_script=root/'colors.py';fixture_script.write_text(COLOR_FIXTURE);fixture=root/'colors.glb'
    with (root/'fixture.log').open('wb') as log:
        # Fixed argv, no shell, trusted fixture script; the output filename follows Blender's -- delimiter.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
        subprocess.run([blender_path(),'--background','--factory-startup','--disable-autoexec','--offline-mode','--python-exit-code','1','--python',str(fixture_script),'--',str(fixture)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=40)
    directory,manifest=render(fixture,'voxel')
    # Both image texels and COLOR_0 must survive conversion, not become gray cubes.
    with Image.open(directory/'sheet.png') as image:
        pixels=list(image.getdata())
        for axis in range(3):assert sum(1 for p in pixels if p[axis]>80 and p[axis]>max(p[i] for i in range(3) if i!=axis)*1.5)>200
    assert not manifest['warnings'],manifest['warnings']
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified all styles, seven cameras, axis reversal, shared palette, embedded textures, vertex colors and ZIP hashes.',flush=True)


if __name__=='__main__':main()
