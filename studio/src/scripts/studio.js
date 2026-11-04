const $ = (id) => document.getElementById(id);
let token='', catalog, selected, latestImage, referenceId, referenceSize, gallery=[], jobs=[], lastGallery='', lastJobs='', moreExhausted=false, archiveEpoch=0;
const cachedImages=new Map(), selectedImages=new Set(), undoStack=[];
const canvas=$('mask'), ctx=canvas.getContext('2d');
let drawing=false, erasing=false, lastPoint;
const modes={text:'Text → Image',reference:'Modify reference',img2img:'Reimagine image',inpaint:'Edit area'};
const states={queued:'Queued',loading:'Loading model',generating:'Generating',completed:'Completed',failed:'Failed',cancelled:'Cancelled'};
function message(text=''){ $('message').textContent=text; $('message').hidden=!text; }
async function api(path,body,method){
 const res=await fetch('/studio/api/'+path,{method:method||(body===undefined?'GET':'POST'),headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
 if(res.status===401){ if(!$('auth').open)$('auth').showModal(); throw Error('API key required.'); }
 const data=await res.json();if(!res.ok)throw Error(data.error?.message||'Connection failed.');return data;
}
function button(text,fn,cls='quiet'){const b=document.createElement('button');b.type='button';b.className=cls;b.textContent=text;b.addEventListener('click',()=>Promise.resolve().then(fn).catch(e=>message(e.message)));return b;}
function text(tag,value){const node=document.createElement(tag);node.textContent=value;return node;}
// Fetch private images with the API token.
async function imageURL(id){const key=id;if(cachedImages.has(key))return cachedImages.get(key);const res=await fetch('/studio/api/files/'+key,{headers:token?{Authorization:'Bearer '+token}:{}});if(!res.ok)throw Error('Could not load image.');const url=URL.createObjectURL(await res.blob());cachedImages.set(key,url);return url;}
function model(){return catalog.models.find(m=>m.id===$('model').value);}
function updateMode(){const mode=$('mode').value;$('edit-options').hidden=mode==='text';$('mask-options').hidden=mode!=='inpaint';canvas.hidden=mode!=='inpaint';$('strength').disabled=mode==='reference';if(referenceId&&mode!=='text'){ $('editor').hidden=false;$('result').hidden=true;$('empty').hidden=true;}}
function guided(){return $('workflow').value==='guided';}
function recipe(){return catalog.recipes.find(r=>r.id===$('recipe').value);}
function modelingSettings(){return recipe()?.modeling_asset?($('modeling-view').value!=='off'?{modeling_view:$('modeling-view').value,modeling_asset:$('modeling-asset').value}:recipe().default_modeling_view?{modeling_view:'off'}:{}):{};}
function initializeModeling(){for(const [field,items] of [['modeling-view',catalog.modeling.views],['modeling-asset',catalog.modeling.assets]])$(field).replaceChildren(...items.map(item=>{const option=text('option',item.name);option.value=item.id;return option;}));}
function restoreModeling(inputs){if(!recipe()?.modeling_asset)return;$('modeling-view').value=inputs.modeling_view||'off';$('modeling-asset').value=inputs.modeling_asset||recipe().modeling_asset;setRecipe();}
function applyModelingStarter(){const asset=catalog.modeling.assets.find(a=>a.id===$('modeling-asset').value);$('subject').value=asset.example.subject;$('scene').value=asset.example.scene;$('scene-details').value=asset.example.details;$('seed').value=42;setRecipe();updateRecipePreview();}
function guidedRequest(){const body={model:$('model').value,recipe:$('recipe').value,subject:$('subject').value,scene:$('scene').value,details:$('scene-details').value,quality:$('recipe-quality').value,aspect_ratio:$('aspect-ratio').value,...modelingSettings()};if(['z-image','z-image-turbo'].includes(recipe()?.model))body.text=$('visible-text').value;if($('seed').value!=='')body.seed=Number($('seed').value);return body;}
// Ignore older compose responses when the user has already changed the inputs again.
let previewTimer,previewSerial=0;
async function updateRecipePreview(){const serial=++previewSerial;if(!guided()||!$('subject').value.trim()){$('recipe-preview').textContent='Enter a subject to preview the full prompt and settings.';return;}try{const prepared=await api('compose',guidedRequest());if(serial!==previewSerial)return;$('recipe-preview').textContent=prepared.prompt+'\n\nNegative prompt: '+prepared.negative_prompt+'\n\n'+prepared.size+' · '+prepared.steps+' steps · CFG '+prepared.cfg_scale+' · '+prepared.sampler;}catch(e){if(serial===previewSerial)$('recipe-preview').textContent=e.message;}}
function scheduleRecipePreview(){clearTimeout(previewTimer);previewTimer=setTimeout(updateRecipePreview,250);}
let modelingRecipe;
function setRecipe(reset=false){
 const r=recipe();if(!r)return;
 const capable=!!r.modeling_asset;$('modeling-fields').hidden=!capable;
 // New low-poly work starts as a modeling reference; recorded examples and reuse
 // explicitly restore their original purpose after selecting the recipe.
 if(reset||modelingRecipe!==r.id){$('modeling-view').value=capable?(r.default_modeling_view||'three-quarter'):'off';$('modeling-asset').value=r.modeling_asset||'prop';}modelingRecipe=r.id;
 const reference=capable&&$('modeling-view').value!=='off';$('modeling-asset-fields').hidden=!reference;$('modeling-note').hidden=!reference;
 $('scene-label').textContent=reference?'Construction or pose notes':'Setting or action';$('details-label').textContent=reference?'Materials, colors and design details':'Extra details';
 $('scene').placeholder=reference?'Optional: part connections, proportions or a neutral pose':r.scene;
 $('scene-details').placeholder=reference?'For example: three solid material colors, thick roof, simple wheel hubs':'For example: glowing crystals, wind moving the cloak';
 $('example').textContent=reference?'Use recipe example':'Use example';
 $('recipe-description').textContent=r.description;$('recipe-tip').textContent=r.tip||'';$('recipe-tip').hidden=!r.tip;$('visible-text-fields').hidden=!['z-image','z-image-turbo'].includes(r.model);$('subject').placeholder=r.example.subject;
 const format=(model().formats||catalog.formats)?.find(f=>f.id===$('aspect-ratio').value),asset=catalog.modeling.assets.find(a=>a.id===$('modeling-asset').value);
 const sheet=reference&&$('modeling-view').value==='sheet';
 const recommended=reference?(sheet?'1024x1024':asset.size):r.size;const [w,h]=recommended.split('x').map(Number);const draft=reference?(h>w?'576x832':w>h?'832x576':'768x768'):r.preview_size;
 const size=$('recipe-quality').value==='preview'?(format?.preview_size||draft):(format?.size||recommended);
 $('format-note').textContent='Output: '+size.replace('x',' × ')+' px'+(reference?(sheet?' · four proposed AI views':' · single modeling concept'):'');scheduleRecipePreview();
}
function updateWorkflow(){const simple=guided();$('guided-fields').hidden=!simple;$('free-fields').hidden=simple;$('expert-settings').hidden=simple;$('subject').required=simple;$('prompt').required=!simple;setRecipe();}
function setModel(reset=true){const m=model();if(!m)return;$('model-note').textContent=m.tip;$('license').textContent=m.license+' · Model & license ↗';$('license').href=m.license_url||m.source;
 for(const option of $('mode').options){option.disabled=!m.modes.includes(option.value)||(option.value!=='text'&&!m.verified_modes.includes(option.value));option.textContent=modes[option.value]+(m.modes.includes(option.value)&&option.value!=='text'&&!m.verified_modes.includes(option.value)?' · not yet tested':'');}
 if($('mode').selectedOptions[0].disabled)$('mode').value='text';
 $('recipe-quality').querySelector('[value=detail]').disabled=m.id==='z-image-turbo';if(m.id==='z-image-turbo'&&$('recipe-quality').value==='detail')$('recipe-quality').value='standard';$('negative').disabled=!m.negative;$('cfg').disabled=!m.negative;
 for(const size of (m.sizes||[])){if(!Array.from($('size').options).some(o=>o.value===size)){const o=text('option',size.replace('x',' × ')+' · verified locally');o.value=size;o.dataset.extended='true';$('size').append(o);}}
 for(const o of Array.from($('size').options)){if(o.dataset.extended&&!m.sizes.includes(o.value))o.remove();}
 if(!$('size').value)$('size').value='1024x1024';
 if(reset){$('quality').replaceChildren(...m.quality.map(q=>{const o=text('option',q.name);o.value=q.id;return o;}));$('quality').value='standard';$('steps').value=m.defaults.steps;$('cfg').value=m.defaults.cfg;$('sampler').value=m.defaults.sampler;if(!m.negative)$('negative').value='';}
 const previous=$('recipe').value;$('recipe').replaceChildren();for(const [category,label] of [['anime','Anima · anime and illustration'],['photo','MOSS · realistic photography'],['lowpoly','MOSS · Low Poly'],['voxel','MOSS · Voxel Art'],['craft','MOSS · illustration and craft'],['pixel','FLUX · Pixel Art'],['zimage','Z-Image · creative studio'],['zturbo','Z-Image Turbo · quick studies']]){const group=document.createElement('optgroup');group.label=label;for(const r of catalog.recipes.filter(r=>r.category===category)){const o=text('option',r.name);o.value=r.id;o.disabled=!catalog.models.find(model=>model.id===r.model)?.installed;group.append(o);}$('recipe').append(group);}if(catalog.recipes.some(r=>r.id===previous&&r.model===m.id))$('recipe').value=previous;else $('recipe').value=(catalog.recipes.find(r=>r.model===m.id&&r.category==='photo')||catalog.recipes.find(r=>r.model===m.id))?.id;
 const previousRatio=$('aspect-ratio').value;$('aspect-ratio').replaceChildren(...[text('option','Recommended · recipe format'),...(m.formats||catalog.formats||[]).map(f=>{const option=text('option',f.name);option.value=f.id;return option;})]);$('aspect-ratio').options[0].value='auto';$('aspect-ratio').value=previousRatio||'auto';
 updateWorkflow();updateMode();
}
function setPreset(){const preset=catalog.presets.find(p=>p.id===$('preset').value);$('suffix').value=preset.suffix;$('preset-tip').textContent=preset.tip+' · '+preset.evidence;$('negative').value=model().negative?preset.negative:'';}
function request(){if(guided())return guidedRequest();const value={model:$('model').value,mode:$('mode').value,prompt:[$('prompt').value.trim(),$('suffix').value.trim()].filter(Boolean).join(', '),preset:$('preset').value,size:$('size').value,steps:Number($('steps').value),cfg_scale:Number($('cfg').value),sampler:$('sampler').value,negative_prompt:$('negative').disabled?'':$('negative').value,strength:Number($('strength').value),feather:Number($('feather').value)};if($('seed').value!=='')value.seed=Number($('seed').value);if(value.mode!=='text')value.image_id=referenceId;return value;}
async function uploadData(data){return api('uploads',{data:data.split(',')[1]});}
async function setReference(file){
 if(file.size>12*1024*1024)throw Error('Reference image exceeds 12 MiB.');
 const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
 const upload=await uploadData(data);referenceId=upload.id;referenceSize=upload.size;
 const image=$('reference');image.src=await imageURL(upload.id);await image.decode();canvas.width=referenceSize[0];canvas.height=referenceSize[1];ctx.clearRect(0,0,canvas.width,canvas.height);undoStack.length=0;
 $('editor').hidden=false;$('result').hidden=true;$('empty').hidden=true;updateMode();
}
$('upload').addEventListener('change',()=>{if($('upload').files[0])setReference($('upload').files[0]).catch(e=>message(e.message));});
$('generate').addEventListener('submit',async event=>{event.preventDefault();message();$('submit').disabled=true;try{const body=request();if(!guided()&&body.mode!=='text'&&!referenceId)throw Error('Please select a reference image first.');if(body.mode==='inpaint'){const mask=document.createElement('canvas');mask.width=canvas.width;mask.height=canvas.height;const c=mask.getContext('2d');c.fillStyle='black';c.fillRect(0,0,mask.width,mask.height);c.drawImage(canvas,0,0);const pixels=c.getImageData(0,0,mask.width,mask.height);for(let i=0;i<pixels.data.length;i+=4){const v=pixels.data[i];pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=v;pixels.data[i+3]=255;}c.putImageData(pixels,0,0);body.mask_id=(await uploadData(mask.toDataURL('image/png'))).id;}
 const count=Number($('count').value);const seed=body.seed??crypto.getRandomValues(new Uint32Array(1))[0]%2147483648;let accepted=0;try{for(let i=0;i<count;i++){await api('jobs',{...body,seed:(seed+i)%2147483648});accepted++;}}catch(e){throw Error(`${accepted} job${accepted===1?'':'s'} accepted. ${e.message}`);}await refresh();message(count>1?count+' images queued.':'Image queued.');}catch(e){message(e.message);}finally{$('submit').disabled=false;}});
$('workflow').addEventListener('change',updateWorkflow);$('recipe').addEventListener('change',()=>{const r=recipe();if(r.model!==$('model').value){$('model').value=r.model;setModel();}else setRecipe(true);});for(const id of ['subject','scene','scene-details','visible-text','recipe-quality','aspect-ratio'])$(id).addEventListener('input',()=>{if(id==='recipe-quality'||id==='aspect-ratio')setRecipe();else scheduleRecipePreview();});$('example').addEventListener('click',()=>applyExample(recipe()));
for(const id of ['modeling-view','modeling-asset'])$(id).addEventListener('change',()=>setRecipe());
$('modeling-example').addEventListener('click',applyModelingStarter);
$('quality').addEventListener('change',()=>{$('steps').value=model().quality.find(q=>q.id===$('quality').value).steps;});$('model').addEventListener('change',()=>setModel());$('preset').addEventListener('change',setPreset);$('mode').addEventListener('change',updateMode);
$('load').addEventListener('click',async()=>{try{await api('models/load',{model:$('model').value});message('Loading model …');}catch(e){message(e.message);}});
$('strength').addEventListener('input',()=>{$('strength-value').textContent=$('strength').value;});
$('zoom').addEventListener('input',()=>{$('editor').style.width=Number($('zoom').value)*100+'%';});
function snapshot(){if(undoStack.length>=Math.max(1,Math.min(12,Math.floor(32*1024*1024/(canvas.width*canvas.height*4)))))undoStack.shift();undoStack.push(ctx.getImageData(0,0,canvas.width,canvas.height));}
function point(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*canvas.width/r.width,(e.clientY-r.top)*canvas.height/r.height];}
function stroke(e){const p=point(e);ctx.globalCompositeOperation=erasing?'destination-out':'source-over';ctx.strokeStyle='#ff963c';ctx.lineWidth=Number($('brush').value)*canvas.width/canvas.getBoundingClientRect().width;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(...lastPoint);ctx.lineTo(...p);ctx.stroke();lastPoint=p;}
canvas.addEventListener('pointerdown',e=>{snapshot();drawing=true;lastPoint=point(e);canvas.setPointerCapture(e.pointerId);stroke(e);});canvas.addEventListener('pointermove',e=>{if(drawing)stroke(e);});for(const name of ['pointerup','pointercancel'])canvas.addEventListener(name,()=>{drawing=false;});
$('eraser').addEventListener('click',()=>{erasing=!erasing;$('eraser').setAttribute('aria-pressed',String(erasing));$('eraser').textContent=erasing?'Brush':'Eraser';});$('undo').addEventListener('click',()=>{const pixels=undoStack.pop();if(pixels)ctx.putImageData(pixels,0,0);});$('clear-mask').addEventListener('click',()=>{snapshot();ctx.clearRect(0,0,canvas.width,canvas.height);});
async function showResult(item){latestImage=item;$('result').src=await imageURL(item.id);$('result').hidden=false;$('editor').hidden=true;$('empty').hidden=true;$('download').href=$('result').src;$('download').hidden=false;$('reuse-reference').hidden=!catalog.models.some(m=>m.verified_modes.includes('reference'));$('preview-label').textContent=item.request.model+' · '+item.request.size;}
$('reuse-reference').addEventListener('click',async()=>{try{const res=await fetch(await imageURL(latestImage.id));await setReference(new File([await res.blob()],'reference.png',{type:'image/png'}));const candidates=catalog.models.filter(m=>m.installed&&m.verified_modes.includes('reference'));if(candidates.length){$('model').value=candidates[0].id;setModel();$('mode').value='reference';updateMode();}else{message('Reference loaded. Choose an editing mode verified locally.');}}catch(e){message(e.message);}});
async function openDetail(item){selected=item;$('detail-image').src=await imageURL(item.id);$('metadata').textContent=JSON.stringify({Settings:item.request,Sampling:item.sampling,Runtime:item.runtime_revision,Duration:item.seconds+' s',License:catalog.models.find(m=>m.id===item.request.model)?.license||item.license},null,2);$('favorite').textContent=item.favorite?'★ Remove favorite':'☆ Save as favorite';$('detail').showModal();}
$('favorite').addEventListener('click',async()=>{try{selected=await api('gallery/'+selected.id+'/favorite',{favorite:!selected.favorite});$('favorite').textContent=selected.favorite?'★ Remove favorite':'☆ Save as favorite';lastGallery='';await refresh();}catch(e){message(e.message);}});
let deletionTargets=[];
function askDelete(items){deletionTargets=Array.isArray(items)?items:[items];if(!deletionTargets.length)return;$('delete-title').textContent=deletionTargets.length===1?'Delete image?':'Delete '+deletionTargets.length+' images?';$('delete-description').textContent=deletionTargets.length===1?'The PNG and its saved settings will be permanently deleted.':'All '+deletionTargets.length+' selected PNGs and their saved settings will be permanently deleted.';$('delete-confirm').showModal();}
function updateSelection(){const count=selectedImages.size;$('selection-count').textContent=count+' selected';$('delete-selected').disabled=count===0;$('clear-selection').disabled=count===0;for(const card of document.querySelectorAll('.card'))card.querySelector('.select-image').checked=selectedImages.has(card.dataset.imageId);}
$('select-all').addEventListener('click',()=>{for(const item of gallery.filter(i=>!$('only-favorites').checked||i.favorite))selectedImages.add(item.id);updateSelection();});
$('clear-selection').addEventListener('click',()=>{selectedImages.clear();updateSelection();});
$('delete-selected').addEventListener('click',()=>askDelete(gallery.filter(i=>selectedImages.has(i.id))));
// Release the image and clear every view that could still display the deleted image.
function forgetImage(id){const url=cachedImages.get(id);if(url)URL.revokeObjectURL(url);cachedImages.delete(id);selectedImages.delete(id);gallery=gallery.filter(i=>i.id!==id);
 if(selected?.id===id){selected=null;if($('detail').open)$('detail').close();$('detail-image').removeAttribute('src');$('metadata').textContent='';}
 if(latestImage?.id===id){latestImage=null;$('result').hidden=true;$('result').removeAttribute('src');$('download').hidden=true;$('download').removeAttribute('href');$('reuse-reference').hidden=true;$('empty').hidden=false;}
 if($('comparison').open)$('comparison').close();$('comparison-images').replaceChildren();lastGallery='';
}
$('delete-image').addEventListener('click',()=>{if(selected)askDelete(selected);});
$('delete-cancel').addEventListener('click',()=>{$('delete-confirm').close();deletionTargets=[];});
$('delete-confirm-button').addEventListener('click',async()=>{if(!deletionTargets.length)return;const ids=deletionTargets.map(i=>i.id);$('delete-confirm-button').disabled=true;$('delete-cancel').disabled=true;try{if(ids.length===1)await api('gallery/'+ids[0],undefined,'DELETE');else await api('gallery/delete',{ids});archiveEpoch++;for(const id of ids)forgetImage(id);updateSelection();$('delete-confirm').close();deletionTargets=[];await renderGallery();await refresh();message(ids.length===1?'Image deleted.':ids.length+' images deleted.');}catch(e){message(e.message);}finally{$('delete-confirm-button').disabled=false;$('delete-cancel').disabled=false;}});
$('reuse').addEventListener('click',()=>{const r=selected.request;if(!catalog.models.some(m=>m.id===r.model)){$('detail').close();message('This image was created with a removed model. It remains in the library, but its old settings can no longer be loaded.');return;}$('model').value=r.model;setModel();$('seed').value=r.seed;
 if(r.recipe_inputs&&catalog.recipes.some(p=>p.id===r.recipe_inputs.recipe)){$('workflow').value='guided';$('recipe').value=r.recipe_inputs.recipe;$('subject').value=r.recipe_inputs.subject;$('scene').value=r.recipe_inputs.scene||'';$('scene-details').value=r.recipe_inputs.details||'';$('visible-text').value=r.recipe_inputs.text||'';$('aspect-ratio').value=r.recipe_inputs.aspect_ratio||'auto';$('recipe-quality').value=r.recipe_inputs.quality||'standard';updateWorkflow();}
 else{$('workflow').value='free';updateWorkflow();$('preset').value=r.preset||'none';$('suffix').value='';$('prompt').value=r.prompt;for(const [field,key]of [['size','size'],['steps','steps'],['cfg','cfg_scale'],['sampler','sampler'],['negative','negative_prompt']])$(field).value=r[key]??'';}
 if(r.recipe_inputs)restoreModeling(r.recipe_inputs);$('detail').close();showResult(selected).catch(e=>message(e.message));$('workspace').scrollIntoView();});
for(const node of document.querySelectorAll('[data-close]'))node.addEventListener('click',()=>$(node.dataset.close).close());
async function renderGallery(){const grid=$('gallery');grid.replaceChildren();const items=gallery.filter(i=>!$('only-favorites').checked||i.favorite);if(!items.length){grid.append(text('p','Your collection is waiting for its first idea.'));updateSelection();return;}
 for(const item of items){const card=text('article','');card.className='card';const image=document.createElement('img');image.alt=item.request.prompt;image.loading='lazy';image.src=await imageURL(item.id);const open=button('',()=>openDetail(item),'');open.append(image,text('p',(item.favorite?'★ ':'')+(catalog.recipes.find(r=>r.id===item.request.recipe_inputs?.recipe)?.name||item.request.model)+' · '+item.request.size));const select=document.createElement('input');select.type='checkbox';select.className='select-image';select.setAttribute('aria-label','Select image');select.checked=selectedImages.has(item.id);select.addEventListener('change',()=>{if(select.checked)selectedImages.add(item.id);else selectedImages.delete(item.id);updateSelection();});const remove=button('Delete',()=>askDelete(item),'quiet danger delete-card');remove.setAttribute('aria-label','Delete image');card.dataset.imageId=item.id;card.append(open,select,remove);grid.append(card);}
 updateSelection();
}
$('only-favorites').addEventListener('change',()=>{archiveEpoch++;gallery=[];lastGallery='';selectedImages.clear();updateSelection();refresh();});
$('compare').addEventListener('click',async()=>{try{if(selectedImages.size!==2)throw Error('Please select exactly two images in the library.');const container=$('comparison-images');container.replaceChildren();for(const id of selectedImages){const item=gallery.find(i=>i.id===id);const figure=document.createElement('figure'),image=document.createElement('img');image.src=await imageURL(id);image.alt=item.request.prompt;figure.append(image,text('figcaption',`${item.request.model} · ${item.request.steps} steps · CFG ${item.request.cfg_scale} · Seed ${item.request.seed}\n${item.request.prompt}`));container.append(figure);}$('comparison').showModal();}catch(e){message(e.message);}});
function renderJobs(){const container=$('jobs');container.replaceChildren();const active=jobs.filter(j=>['queued','loading','generating'].includes(j.status));$('queue-count').textContent=active.length+' ACTIVE';for(const job of jobs.slice(0,8)){const node=document.createElement('div');node.className='job';const info=document.createElement('div');info.append(text('strong',states[job.status]||job.status),text('p',job.request.model+' · Seed '+job.request.seed));if(job.error)info.append(text('p',job.error));if(job.progress!=null&&job.status==='generating'){const bar=document.createElement('progress');bar.max=1;bar.value=job.progress;bar.setAttribute('aria-label','Progress');info.append(bar);}node.append(info);if(active.includes(job))node.append(button('Cancel',async()=>{await api('jobs/'+job.id+'/cancel',{});await refresh();}));container.append(node);}}
let refreshing=false;
async function archivePage(offset){return api('gallery?offset='+offset+($('only-favorites').checked?'&favorites=1':''));}
// A deletion or filter change invalidates any archive response already in flight.
async function refresh(){if(refreshing)return;refreshing=true;const epoch=archiveEpoch;try{const pages=Math.max(1,Math.ceil(gallery.length/60));const [nextJobs,archive,status]=await Promise.all([api('jobs'),Promise.all(Array.from({length:pages},(_,i)=>archivePage(i*60))),api('status')]);if(epoch!==archiveEpoch)return;jobs=nextJobs;
 const nextGallery=Array.from(new Map(archive.flat().map(item=>[item.id,item])).values());moreExhausted=archive.at(-1).length<60;
 for(const item of [...gallery]){if(!nextGallery.some(n=>n.id===item.id))forgetImage(item.id);}
 gallery=nextGallery;$('more-images').hidden=moreExhausted;
 const j=JSON.stringify(jobs),g=JSON.stringify(gallery);if(j!==lastJobs){lastJobs=j;renderJobs();}if(g!==lastGallery){lastGallery=g;await renderGallery();if(gallery.length&&gallery[0].id!==latestImage?.id)await showResult(gallery[0]);}
 $('health').textContent=status.ready?'● '+status.model+' ready':status.error||'◌ Loading model …';if(status.model!==catalog.models.find(m=>m.loaded)?.id){catalog=await api('catalog');setModel(false);}}catch(e){message(e.message);}finally{refreshing=false;}}
let recipeLimit=6, previewRecipe;
function applyExample(r,scroll=false){
 // Prefer the recorded inputs and seed that produced the displayed example.
 const sample=catalog.examples?.[r.id],inputs=sample?.inputs||r.example;
 $('model').value=r.model;setModel();$('workflow').value='guided';$('recipe').value=r.id;
 $('subject').value=inputs.subject||'';$('scene').value=inputs.scene||'';$('scene-details').value=inputs.details||'';$('visible-text').value=inputs.text||'';
 $('aspect-ratio').value=inputs.aspect_ratio||'auto';$('recipe-quality').value=sample?.quality||'standard';if(sample)$('seed').value=sample.seed;
 updateWorkflow();restoreModeling(inputs);updateRecipePreview();if(scroll)$('workspace').scrollIntoView({behavior:'smooth'});
}
function viewRecipeExample(r){
 const sample=catalog.examples?.[r.id];if(!sample)throw Error('This example is not available yet.');previewRecipe=r;
 $('example-title').textContent=r.name;$('example-image').src=sample.url;$('example-image').alt=r.example.subject;$('example-image').classList.toggle('has-transparency',!!sample.transparent);
 $('example-settings').textContent=(sample.quality==='preview'?'Draft':sample.quality==='detail'?'More detail':'Recommended')+' · '+sample.size+' · '+sample.steps+' steps · CFG '+sample.cfg_scale+' · Seed '+sample.seed+(sample.lora_strength?' · Style strength '+sample.lora_strength:'')+(sample.transparent?' · Transparent background':'');
 $('example-metadata').textContent=JSON.stringify({Inputs:sample.inputs,Prompt:sample.prompt,'Negative prompt':sample.negative_prompt},null,2);
 $('use-preview-example').disabled=!catalog.models.find(m=>m.id===r.model)?.installed;$('recipe-example').showModal();
}
function renderRecipeBrowser(){
 const filter=$('recipe-model-filter').value,query=$('recipe-search').value.trim().toLowerCase();
 const items=catalog.recipes.filter(r=>(filter==='all'||r.model===filter)&&[r.name,r.description,r.model,r.category].join(' ').toLowerCase().includes(query)).sort((a,b)=>Number(!!b.featured)-Number(!!a.featured));
 const shown=items.slice(0,recipeLimit),grid=$('recipe-gallery');grid.replaceChildren();$('recipe-total').textContent=shown.length+' of '+items.length+' recipes';$('more-recipes').hidden=shown.length===items.length;
 if(!shown.length){grid.append(text('p','No recipes match your search.'));return;}
 for(const r of shown){
  const sample=catalog.examples?.[r.id],card=text('article','');card.className='recipe-card';card.dataset.recipeId=r.id;
  if(sample){const open=button('',()=>viewRecipeExample(r),'recipe-preview');open.setAttribute('aria-label','View example: '+r.name);open.classList.toggle('has-transparency',!!sample.transparent);const img=document.createElement('img');img.src=sample.url;img.alt=r.example.subject;img.loading='lazy';img.width=480;img.height=360;open.append(img);card.append(open);}
  const body=text('div','');body.className='recipe-card-body';body.append(text('h3',r.name),text('p',r.description));
  const meta=text('p',sample?(sample.quality==='preview'?'Draft':sample.quality==='detail'?'More detail':'Recommended')+' · '+sample.size+' · '+sample.steps+' steps':'No generated preview yet');meta.className='hint';body.append(meta);
  const use=button(sample?'Use this example':'Use preset',()=>applyExample(r,true),'quiet');use.disabled=!catalog.models.find(m=>m.id===r.model)?.installed;body.append(use);card.append(body);grid.append(card);
 }
}
$('use-preview-example').addEventListener('click',()=>{if(previewRecipe){$('recipe-example').close();applyExample(previewRecipe,true);}});
for(const id of ['recipe-model-filter','recipe-search'])$(id).addEventListener('input',()=>{recipeLimit=6;if(catalog)renderRecipeBrowser();});
$('more-recipes').addEventListener('click',()=>{recipeLimit+=6;renderRecipeBrowser();});
async function init(){try{catalog=await api('catalog');initializeModeling();$('model').replaceChildren(...catalog.models.map(m=>{const o=text('option',m.name+(m.installed?'':' · not installed'));o.value=m.id;o.disabled=!m.installed;return o;}));$('model').value=catalog.models.find(m=>m.id==='anima'&&m.installed)?.id||catalog.models.find(m=>m.loaded)?.id||'moss';$('preset').replaceChildren(...catalog.presets.map(p=>{const o=text('option',p.name);o.value=p.id;return o;}));$('sampler').replaceChildren(...catalog.samplers.map(s=>{const o=text('option',s);o.value=s;return o;}));$('aspect-ratio').replaceChildren(...[text('option','Recommended · recipe format'),...(catalog.formats||[]).map(f=>{const option=text('option',f.name);option.value=f.id;return option;})]);$('aspect-ratio').options[0].value='auto';setModel();setPreset();$('recipe-model-filter').replaceChildren(text('option','All models'),...catalog.models.map(m=>{const option=text('option',m.name);option.value=m.id;return option;}));$('recipe-model-filter').options[0].value='all';renderRecipeBrowser();const requestedRecipe=catalog.recipes.find(r=>r.id===new URLSearchParams(location.search).get('recipe'));if(requestedRecipe&&catalog.models.find(m=>m.id===requestedRecipe.model)?.installed){applyExample(requestedRecipe);const query=new URLSearchParams(location.search),view=query.get('modeling_view'),asset=query.get('modeling_asset');if(requestedRecipe.modeling_asset&&catalog.modeling.views.some(v=>v.id===view)){restoreModeling({modeling_view:view,modeling_asset:catalog.modeling.assets.some(a=>a.id===asset)?asset:requestedRecipe.modeling_asset});if(view!=='off'&&asset)applyModelingStarter();}}await refresh();}catch(e){message(e.message);}}
$('auth-form').addEventListener('submit',async e=>{e.preventDefault();token=$('key').value;$('key').value='';$('auth').close();await init();});
$('more-images').addEventListener('click',async()=>{try{const next=await api('gallery?offset='+gallery.length+($('only-favorites').checked?'&favorites=1':''));gallery.push(...next);moreExhausted=next.length<60;$('more-images').hidden=moreExhausted;await renderGallery();}catch(e){message(e.message);}});
$('mask-upload').addEventListener('change',async()=>{try{const file=$('mask-upload').files[0];if(!file)return;if(!referenceId)throw Error('Load a reference image first.');const url=URL.createObjectURL(file);const image=new Image();try{image.src=url;await image.decode();if(image.width!==canvas.width||image.height!==canvas.height)throw Error('The mask and reference must have the same dimensions.');snapshot();ctx.globalCompositeOperation='source-over';ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);for(let i=0;i<pixels.data.length;i+=4){const alpha=(pixels.data[i]+pixels.data[i+1]+pixels.data[i+2])/3;pixels.data[i]=255;pixels.data[i+1]=150;pixels.data[i+2]=60;pixels.data[i+3]=alpha;}ctx.putImageData(pixels,0,0);}finally{URL.revokeObjectURL(url);}}catch(e){message(e.message);}});
await init();setInterval(refresh,2000);
