"""Blender script: generate an original, asymmetric low-poly kart for view QA."""
import math
from pathlib import Path
import sys
import bpy

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
materials={}
for name,color in {'frame':(.06,.16,.26,1),'nose':(.65,.12,.05,1),'rear':(.15,.38,.1,1),
                   'tire':(.025,.025,.03,1),'metal':(.45,.45,.46,1),'seat':(.08,.09,.12,1)}.items():
    material=bpy.data.materials.new(name);material.diffuse_color=color;material.use_nodes=True
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color
    material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.85;materials[name]=material
def box(name,location,scale,material):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location);obj=bpy.context.object;obj.name=name;obj.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);obj.data.materials.append(materials[material]);return obj
box('chassis',(0,0,.28),(1.1,1.8,.14),'frame')
box('front_nose',(0,-.72,.43),(.58,.8,.3),'nose')
box('seat_base',(0,.08,.49),(.5,.58,.15),'seat')
seat=box('seat_back',(0,.33,.77),(.5,.13,.6),'seat');seat.rotation_euler.x=math.radians(-12)
box('rear_engine',(0,.69,.58),(.48,.42,.42),'rear')
for y,radius,track,label in [(-.63,.24,.58,'front'),(.65,.28,.65,'back')]:
    for x,side in [(-track,'right'),(track,'left')]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=.19,location=(x,y,radius),rotation=(0,math.pi/2,0))
        obj=bpy.context.object;obj.name=label+'_'+side+'_wheel';obj.data.materials.append(materials['tire'])
        bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius*.55,depth=.195,location=(x,y,radius),rotation=(0,math.pi/2,0))
        bpy.context.object.data.materials.append(materials['metal'])
box('exhaust',(0.37,.83,.57),(.13,.55,.12),'metal')
box('steering_column',(0,-.26,.66),(.06,.06,.38),'metal')
bpy.ops.mesh.primitive_torus_add(major_segments=12,minor_segments=6,major_radius=.19,minor_radius=.025,location=(0,-.26,.84),rotation=(math.pi/3,0,0))
bpy.context.object.name='steering_wheel';bpy.context.object.data.materials.append(materials['tire'])
output=Path(sys.argv[sys.argv.index('--')+1]);output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',export_cameras=False,export_lights=False)
