"""Blender-only worker: bake one static GLB and render seven shared-scale cameras."""
import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

VIEWS=('front','left','right','back','top','bottom','three-quarter')
IMAGE_CACHE={}
WARNINGS=set()


def bounds(objects):
    points=[obj.matrix_world@Vector(corner) for obj in objects for corner in obj.bound_box]
    if not points or any(not math.isfinite(value) for point in points for value in point):raise ValueError('The model has invalid bounds.')
    low=Vector(tuple(min(p[axis] for p in points) for axis in range(3)))
    high=Vector(tuple(max(p[axis] for p in points) for axis in range(3)))
    if (high-low).length<1e-6:raise ValueError('The model has no measurable geometry.')
    return low,high


def static_meshes(path):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.scene.frame_set(1)
    graph=bpy.context.evaluated_depsgraph_get();objects=[]
    originals=list(bpy.context.scene.objects)
    for obj in originals:
        if obj.type!='MESH' or obj.hide_render:continue
        evaluated=obj.evaluated_get(graph)
        mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=graph)
        mesh.transform(obj.matrix_world)
        item=bpy.data.objects.new('asset_'+str(len(objects)),mesh);objects.append(item)
    for obj in originals:bpy.data.objects.remove(obj,do_unlink=True)
    for obj in objects:bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    low,high=bounds(objects)
    translation=Vector((-(low.x+high.x)/2,-(low.y+high.y)/2,-low.z))
    for obj in objects:
        obj.data.transform(Matrix.Translation(translation));obj.data.update()
    bpy.context.view_layer.update()
    return objects,dict(min=list(low),max=list(high),dimensions=list(high-low),units='glTF meters',pose='imported static pose at frame 1')


def linear(value):
    return value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4


def display(value):
    value=max(0.,min(1.,value))
    return 12.92*value if value<=.0031308 else 1.055*value**(1/2.4)-.055


def socket_color(socket,uv,vertex_color,depth=0):
    if depth>8:return (0.6,0.6,0.6,1.)
    if not socket.is_linked:
        value=socket.default_value
        return tuple(value) if hasattr(value,'__len__') else (value,value,value,1.)
    node=socket.links[0].from_node
    if node.type=='TEX_IMAGE' and node.image:
        if node.inputs['Vector'].is_linked and node.inputs['Vector'].links[0].from_node.type not in ('UVMAP','TEX_COORD'):
            WARNINGS.add('A texture coordinate transform was approximated during voxel sampling.')
        image=node.image
        if image.name not in IMAGE_CACHE:
            pixels=array.array('f',[0.])*(len(image.pixels));image.pixels.foreach_get(pixels)
            IMAGE_CACHE[image.name]=(image.size[0],image.size[1],pixels,image.colorspace_settings.name)
        width,height,pixels,space=IMAGE_CACHE[image.name]
        x=min(width-1,max(0,int((uv[0]%1)*width)));y=min(height-1,max(0,int((uv[1]%1)*height)))
        index=4*(y*width+x);color=tuple(pixels[index:index+4])
        return tuple(linear(value) for value in color[:3])+(color[3],) if space=='sRGB' else color
    if node.type in ('VERTEX_COLOR','ATTRIBUTE'):return vertex_color
    if node.type=='RGB':return tuple(node.outputs[0].default_value)
    if node.type in ('MIX_RGB','MIX'):
        if node.type=='MIX_RGB':factor,a,b=node.inputs[0],node.inputs[1],node.inputs[2]
        else:
            candidates=[value for value in node.inputs if value.enabled and value.name in ('A','B') and value.type=='RGBA']
            if len(candidates)!=2:
                WARNINGS.add('A complex material color node was approximated.');return (0.6,0.6,0.6,1.)
            factor=node.inputs[0];a,b=candidates
        first=socket_color(a,uv,vertex_color,depth+1);second=socket_color(b,uv,vertex_color,depth+1)
        amount=float(factor.default_value) if not factor.is_linked else 1.
        mixed=tuple(x*y for x,y in zip(first,second)) if node.blend_type=='MULTIPLY' else second
        return tuple((1-amount)*x+amount*y for x,y in zip(first,mixed))
    WARNINGS.add('A complex material color node was approximated.')
    return (0.6,0.6,0.6,1.)


def triangle_color(context,point):
    mesh,triangle=context
    a,b,c=(mesh.vertices[index].co for index in triangle.vertices)
    u=b-a;v=c-a;w=point-a
    denom=u.dot(u)*v.dot(v)-u.dot(v)**2
    if abs(denom)<1e-20:weights=(1.,0.,0.)
    else:
        second=(v.dot(v)*w.dot(u)-u.dot(v)*w.dot(v))/denom
        third=(u.dot(u)*w.dot(v)-u.dot(v)*w.dot(u))/denom;weights=(1-second-third,second,third)
    uv=(0.,0.)
    if mesh.uv_layers.active:
        coords=[mesh.uv_layers.active.data[index].uv for index in triangle.loops]
        uv=tuple(sum(weights[i]*coords[i][axis] for i in range(3)) for axis in range(2))
    vertex_color=(1.,1.,1.,1.)
    attribute=mesh.color_attributes.active_color or next(iter(mesh.color_attributes),None)
    if attribute:
        indices=triangle.loops if attribute.domain=='CORNER' else triangle.vertices
        colors=[attribute.data[index].color for index in indices]
        vertex_color=tuple(sum(weights[i]*colors[i][axis] for i in range(3)) for axis in range(4))
    index=mesh.polygons[triangle.polygon_index].material_index
    material=mesh.materials[index] if index<len(mesh.materials) else None
    if material and material.use_nodes:
        shader=next((node for node in material.node_tree.nodes if node.type=='BSDF_PRINCIPLED'),None)
        if shader:return socket_color(shader.inputs['Base Color'],uv,vertex_color)
    return tuple(material.diffuse_color) if material else vertex_color


def voxelize(objects,resolution,palette_limit):
    low,high=bounds(objects);pitch=max(high-low)/resolution
    dimensions=[max(1,math.ceil((high[i]-low[i])/pitch)) for i in range(3)]
    vertices=[];triangles=[];contexts=[]
    for obj in objects:
        mesh=obj.data;mesh.calc_loop_triangles();offset=len(vertices)
        vertices.extend(vertex.co.copy() for vertex in mesh.vertices)
        for triangle in mesh.loop_triangles:
            triangles.append(tuple(offset+index for index in triangle.vertices));contexts.append((mesh,triangle))
    tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
    cells={};histogram=Counter()
    for x in range(dimensions[0]):
        for y in range(dimensions[1]):
            for z in range(dimensions[2]):
                center=low+Vector(((x+.5)*pitch,(y+.5)*pitch,(z+.5)*pitch))
                point,normal,index,distance=tree.find_nearest(center,pitch*.87)
                if index is None:continue
                color=triangle_color(contexts[index],point)
                key=tuple(round(display(value)*15) for value in color[:3])
                cells[(x,y,z)]=key;histogram[key]+=1
    if not cells:raise ValueError('Voxel conversion produced no surface cells.')
    palette=[item[0] for item in histogram.most_common(palette_limit)]
    palette_index={color:min(range(len(palette)),key=lambda i:sum((a-b)**2 for a,b in zip(color,palette[i]))) for color in histogram}
    face_defs=[((-1,0,0),((0,0,0),(0,0,1),(0,1,1),(0,1,0))),
               ((1,0,0),((1,0,0),(1,1,0),(1,1,1),(1,0,1))),
               ((0,-1,0),((0,0,0),(1,0,0),(1,0,1),(0,0,1))),
               ((0,1,0),((0,1,0),(0,1,1),(1,1,1),(1,1,0))),
               ((0,0,-1),((0,0,0),(0,1,0),(1,1,0),(1,0,0))),
               ((0,0,1),((0,0,1),(1,0,1),(1,1,1),(0,1,1)))]
    points=[];faces=[];materials=[];indices={}
    for (x,y,z),color in cells.items():
        for direction,corners in face_defs:
            neighbor=(x+direction[0],y+direction[1],z+direction[2])
            if neighbor in cells:continue
            face=[]
            for dx,dy,dz in corners:
                key=(x+dx,y+dy,z+dz)
                if key not in indices:
                    indices[key]=len(points);points.append(tuple(low[i]+key[i]*pitch for i in range(3)))
                face.append(indices[key])
            faces.append(face);materials.append(palette_index[color])
    mesh=bpy.data.meshes.new('voxel_surface');mesh.from_pydata(points,[],faces);mesh.update()
    for color in palette:
        material=bpy.data.materials.new('voxel_color');material.use_nodes=True
        rgb=tuple(linear(value/15) for value in color)
        material.diffuse_color=rgb+(1.,)
        shader=material.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=rgb+(1.,);shader.inputs['Roughness'].default_value=.8
        mesh.materials.append(material)
    for face,index in zip(mesh.polygons,materials):face.material_index=index
    for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
    result=bpy.data.objects.new('voxel_asset',mesh);bpy.context.scene.collection.objects.link(result)
    return [result],dict(method='shared surface-cell cubes, internal neighbor faces removed',grid=dimensions,cell_size=pitch,cells=len(cells),palette=len(palette),approximation=True)


def camera_rotation(location,target,up=Vector((0,0,1))):
    back=(location-target).normalized();right=up.cross(back).normalized();actual_up=back.cross(right).normalized()
    return Matrix((right,actual_up,back)).transposed().to_quaternion()


def main():
    source,settings_path,output=map(Path,sys.argv[sys.argv.index('--')+1:])
    settings=json.loads(settings_path.read_text());objects,source_bounds=static_meshes(source)
    voxel=None
    if settings['style']=='voxel':objects,voxel=voxelize(objects,settings['voxel_grid'],settings['colors'])
    if settings['style']!='model':
        for obj in objects:
            if settings['style'] in ('lowpoly','voxel'):
                for polygon in obj.data.polygons:polygon.use_smooth=False
            for material in obj.data.materials:
                if not material or not material.use_nodes:continue
                for shader in material.node_tree.nodes:
                    if shader.type!='BSDF_PRINCIPLED':continue
                    for key,value in (('Metallic',0.),('Roughness',.85),('Emission Strength',0.),('Specular IOR Level',.15)):
                        if key in shader.inputs:
                            for link in list(shader.inputs[key].links):material.node_tree.links.remove(link)
                            shader.inputs[key].default_value=value
    bpy.context.view_layer.update()
    low,high=bounds(objects);center=(low+high)/2;diameter=(high-low).length
    front={'-Y':Vector((0,-1,0)),'+Y':Vector((0,1,0)),'-X':Vector((-1,0,0)),'+X':Vector((1,0,0))}[settings['front']]
    up=Vector((0,0,1));left=up.cross(front)
    locations={'front':front,'left':left,'right':-left,'back':-front,'top':up,'bottom':-up,
               'three-quarter':(front+left+up*.6).normalized()}
    rotations={view:camera_rotation(center+direction*diameter*3,center,front if view in ('top','bottom') else up) for view,direction in locations.items()}
    corners=[obj.matrix_world@Vector(corner) for obj in objects for corner in obj.bound_box]
    required=[]
    for rotation in rotations.values():
        projected=[rotation.inverted()@(point-center) for point in corners]
        required.extend(max(p[axis] for p in projected)-min(p[axis] for p in projected) for axis in (0,1))
    scale=max(required)*1.16
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(output/'model.glb'),export_format='GLB',use_selection=True,export_cameras=False,export_lights=False)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x=scene.render.resolution_y=settings['pixel_grid'] if settings['style']=='pixel' else 512
    scene.render.resolution_percentage=100;scene.render.film_transparent=True
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    world=bpy.data.worlds.new('asset_studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.world=world
    for name,offset,energy,size in [('key',Vector((2,-3,4)),500,3),('fill',Vector((-3,-1,2)),300,3),('rim',Vector((0,3,3)),350,2)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=energy*(diameter/2)**2;data.shape='DISK';data.size=size*diameter/2
        light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=center+offset*diameter/2
        light.rotation_mode='QUATERNION';light.rotation_quaternion=camera_rotation(light.location,center)
    data=bpy.data.cameras.new('asset_camera');data.type='ORTHO';data.ortho_scale=scale;data.clip_start=max(.00001,diameter/10000);data.clip_end=diameter*20
    camera=bpy.data.objects.new('asset_camera',data);scene.collection.objects.link(camera);scene.camera=camera
    cameras=[]
    for index,view in enumerate(VIEWS):
        camera.location=center+locations[view]*diameter*3;camera.rotation_mode='QUATERNION';camera.rotation_quaternion=rotations[view]
        scene.render.filepath=str(output/(view+'.png'));bpy.ops.render.render(write_still=True)
        cameras.append(dict(view=view,position=list(camera.location),rotation_quaternion=list(rotations[view]),projection='ORTHO',ortho_scale=scale))
        temporary=output/'progress.tmp';temporary.write_text(json.dumps(dict(completed=index+1,view=view)));temporary.replace(output/'progress.json')
    manifest=dict(schema_version=1,renderer='Blender '+bpy.app.version_string,engine='Cycles CPU',source_bounds=source_bounds,
                  rendered_bounds=dict(min=list(low),max=list(high),dimensions=list(high-low)),cameras=cameras,voxel=voxel,warnings=sorted(WARNINGS),
                  appearance='imported PBR' if settings['style']=='model' else 'material base colors, neutral non-emissive studio shading',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (output/'asset-views.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
