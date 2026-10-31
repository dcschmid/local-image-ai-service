"""Translate Anima Kohya text-encoder names for the pinned native loader."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

VERSION=1

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def tensor_name(name):
    # The pinned loader treats Kohya lora_te_* as legacy CLIP names. Explicit
    # Qwen paths select the correct encoder and preserve names such as o_proj.
    if not name.startswith('lora_te_'):return name
    match=re.fullmatch(r'lora_te_layers_(\d+)_(mlp_(?:down|gate|up)_proj|self_attn_(?:q|k|v|o)_proj)\.(alpha|lora_down\.weight|lora_up\.weight)',name)
    if not match:raise ValueError('Unknown Anima text-encoder adapter key: '+name)
    layer,module,suffix=match.groups()
    group,projection=module.split('_',1) if module.startswith('mlp_') else ('self_attn',module.removeprefix('self_attn_'))
    return f'lora.text_encoders.llm.model.layers.{layer}.{group}.{projection}.{suffix}'

def prepare(source,target,expected_sha):
    source,target=Path(source),Path(target)
    if source.resolve()==target.resolve():raise ValueError('Do not overwrite the source adapter')
    if digest(source)!=expected_sha:raise ValueError('Adapter source checksum mismatch')
    receipt_path=target.with_suffix('.json')
    try:
        receipt=json.loads(receipt_path.read_text())
        if receipt.get('version')==VERSION and receipt.get('source_sha256')==expected_sha and target.is_file() and digest(target)==receipt['sha256']:
            return target
    except (OSError,ValueError,KeyError):pass
    temporary=target.with_suffix('.partial')
    try:
        with source.open('rb') as reader:
            length=struct.unpack('<Q',reader.read(8))[0]
            if not 0<length<2**24:raise ValueError('Invalid adapter header')
            header=json.loads(reader.read(length));converted={};changed=0
            for name,value in header.items():
                renamed=tensor_name(name)
                if renamed in converted:raise ValueError('Adapter tensor name collision')
                converted[renamed]=value;changed+=renamed!=name
            if not changed:raise ValueError('No Anima text-encoder keys found')
            metadata=dict(converted.get('__metadata__',{}))
            metadata['atelier_name_conversion']=json.dumps(dict(version=VERSION,source_sha256=expected_sha,renamed=changed),sort_keys=True)
            converted['__metadata__']=metadata
            encoded=json.dumps(converted,separators=(',',':')).encode()
            encoded+=b' '*(-len(encoded)%8)
            target.parent.mkdir(parents=True,exist_ok=True)
            with temporary.open('wb') as writer:
                writer.write(struct.pack('<Q',len(encoded)));writer.write(encoded)
                # Relative tensor offsets and every byte of the numerical payload stay unchanged.
                shutil.copyfileobj(reader,writer,4*1024*1024)
                writer.flush()
                import os
                os.fsync(writer.fileno())
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
    receipt=dict(version=VERSION,source_sha256=expected_sha,sha256=digest(target),renamed=changed)
    receipt_tmp=receipt_path.with_suffix('.tmp');receipt_tmp.write_text(json.dumps(receipt,indent=2)+'\n');receipt_tmp.replace(receipt_path)
    return target
