const $=id=>document.getElementById(id);
let token='',modelFile,available=false,active,submitting=false,polling=false,renderEpoch=0;
const urls=new Map();
function message(value=''){$('message').textContent=value;$('message').hidden=!value;}
function element(tag,value){const node=document.createElement(tag);node.textContent=value;return node;}
function button(label,action){const node=element('button',label);node.type='button';node.className='quiet';node.addEventListener('click',()=>Promise.resolve().then(action).catch(e=>message(e.message)));return node;}
function remember(id){try{sessionStorage.setItem('atelier-asset-job',id);}catch{/* Recovery also works through the recent render list. */}}
async function response(path,body){
 const res=await fetch('/studio/api/assets'+path,{method:body===undefined?'GET':'POST',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
 if(res.status===401){if(!$('auth').open)$('auth').showModal();throw Error('Connect with your API key to continue.');}
 if(!res.ok){let error;try{error=await res.json();}catch{}throw Error(error?.error?.message||'The asset request failed.');}return res;
}
async function api(path='',body){return(await response(path,body)).json();}
async function fileURL(path){if(!urls.has(path)){const relative=path.replace(/^\/studio\/api\/assets/,'');urls.set(path,URL.createObjectURL(await(await response(relative)).blob()));}return urls.get(path);}
async function download(path,name){const link=document.createElement('a');link.href=await fileURL(path);link.download=name;document.body.append(link);link.click();link.remove();}
function updateForm(){const style=$('asset-style').value;$('pixel-options').hidden=style!=='pixel';$('voxel-options').hidden=style!=='voxel';$('palette-options').hidden=!['pixel','voxel'].includes(style);$('render-asset').disabled=!available||!modelFile||submitting;}
function choose(file){
 if(!/\.glb$/i.test(file.name)||file.size>32*1024*1024||file.size<20)throw Error('Choose a binary GLB file between 20 bytes and 32 MiB.');
 modelFile=file;$('file-state').textContent=file.name+' · '+(file.size/1024/1024).toFixed(2)+' MiB';$('asset-file').removeAttribute('aria-invalid');updateForm();message();
}
function releaseImages(){for(const url of urls.values())URL.revokeObjectURL(url);urls.clear();}
async function show(job){
 const epoch=++renderEpoch;
 active=job;remember(job.id);const busy=['queued','rendering'].includes(job.status);
 $('asset-status').textContent=job.status==='rendering'?'Rendering '+Math.round(job.progress*7)+' / 7 views on CPU':job.status[0].toUpperCase()+job.status.slice(1);
 $('asset-progress').hidden=!busy;$('asset-progress').value=job.progress;$('cancel-asset').hidden=!busy;
 if(job.status==='failed')message(job.error||'The model could not be rendered.');
 if(job.status!=='completed'){$('asset-result').hidden=true;$('asset-empty').hidden=false;$('asset-empty').querySelector('h3').textContent=busy?'Your model is being rendered.':'Render '+job.status+'.';return;}
 releaseImages();$('asset-result').hidden=true;$('asset-frames').replaceChildren();
 const sheet=await fileURL(job.sheet);if(epoch!==renderEpoch)return;
 $('asset-sheet').src=sheet;$('asset-sheet').classList.toggle('pixel-art',job.style==='pixel');$('result-name').textContent=job.name;$('asset-empty').hidden=true;$('asset-result').hidden=false;
 $('asset-downloads').replaceChildren(...[['ZIP · all files',job.bundle,'asset-views.zip'],['Rendered GLB',job.model,'model.glb'],['Manifest',job.manifest,'asset-views.json'],['Contact sheet',job.sheet,'sheet.png']].map(([label,url,name])=>button(label,()=>download(url,name))));
 const manifest=await api('/'+job.id+'/files/asset-views.json');if(epoch!==renderEpoch)return;
 $('asset-provenance').textContent='Seven views from one model · front '+job.front+' · '+manifest.renderer+' · '+manifest.engine+'. '+manifest.consistency+(manifest.warnings?.length?' '+manifest.warnings.join(' '):'');
 const frames=await Promise.all(job.views.map(async view=>{const figure=document.createElement('figure'),image=document.createElement('img');image.src=await fileURL(view.url);image.alt=view.name+' view of '+job.name;image.width=image.height=512;image.className=job.style==='pixel'?'pixel-art':'';figure.append(image,element('figcaption',view.name),button('PNG · '+view.name,()=>download(view.url,view.id+'.png')));if(view.native_url)figure.append(button('Native pixels · '+view.name,()=>download(view.native_url,view.id+'.native.png')));return figure;}));
 if(epoch===renderEpoch)$('asset-frames').replaceChildren(...frames);
}
async function recent(){const jobs=await api();$('asset-jobs').replaceChildren(...(jobs.length?jobs.map(job=>{const row=element('div','');row.className='job';const info=element('div','');info.append(element('strong',job.name),element('p',job.style+' · '+job.status));row.append(info,button('Open '+job.name,async()=>{message();await show(await api('/'+job.id));}));return row;}):[element('p','No model renders yet.')]));return jobs;}
async function refresh(){if(polling||submitting)return;polling=true;try{if(active&&['queued','rendering'].includes(active.status)){await show(await api('/'+active.id));if(!['queued','rendering'].includes(active.status))await recent();}}catch(e){message(e.message);}finally{polling=false;}}
$('asset-style').addEventListener('change',updateForm);
$('asset-file').addEventListener('change',()=>{try{modelFile=undefined;if($('asset-file').files[0])choose($('asset-file').files[0]);else{$('file-state').textContent='No model selected.';updateForm();}}catch(e){$('asset-file').setAttribute('aria-invalid','true');message(e.message);updateForm();}});
$('demo').addEventListener('click',async()=>{try{const res=await fetch('/studio/asset-examples/kart.glb');if(!res.ok)throw Error('The demo model could not be loaded.');choose(new File([await res.blob()],'atelier-demo-kart.glb'));$('asset-file').value='';$('asset-name').value='Demo kart';}catch(e){message(e.message);}});
$('asset-form').addEventListener('submit',async event=>{
 event.preventDefault();if(!modelFile||submitting)return;submitting=true;updateForm();message();let sent=false;
 try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Could not read the model file.'));reader.readAsDataURL(modelFile);});
 const body={data,name:$('asset-name').value,style:$('asset-style').value,front:$('asset-front').value,pixel_grid:Number($('asset-grid').value),colors:Number($('asset-colors').value),voxel_grid:Number($('voxel-grid').value)};
 sent=true;const job=await api('',body);await show(job);await recent();
 }catch(e){message(e.message+(sent?' Check Recent model renders before submitting again; the request may already have been accepted.':''));try{await recent();}catch{}}
 finally{submitting=false;updateForm();}
});
$('cancel-asset').addEventListener('click',async()=>{if(!active)return;try{await show(await api('/'+active.id+'/cancel',{}));await recent();}catch(e){message(e.message);}});
$('refresh-assets').addEventListener('click',()=>recent().catch(e=>message(e.message)));
$('auth-form').addEventListener('submit',event=>{event.preventDefault();token=$('key').value;$('key').value='';$('auth').close();initialize();});
async function initialize(){try{const options=await api('/options');available=options.available;$('health').textContent=available?'Blender available · CPU rendering':'Blender is required for model views';updateForm();const jobs=await recent();let saved;try{saved=sessionStorage.getItem('atelier-asset-job');}catch{}const job=jobs.find(job=>job.id===saved)||jobs[0];if(job)await show(job);message();}catch(e){message(e.message);}}
initialize();setInterval(refresh,1000);window.addEventListener('pagehide',releaseImages);
