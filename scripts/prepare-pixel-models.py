#!/usr/bin/env python3
"""Bake all DoRA components into private GGUF copies; leave downloaded weights untouched."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time

VERSION=1
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path.home()/'.local/share/local-image-ai-service/models'
LIB=Path.home()/'.cache/local-image-ai-service/krea-converter/ggml-build/src/libggml-base.so'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def merge_dora(weight,down,up,magnitude):
    import numpy as np
    # DoRA rescales each row of W + B@A by its learned magnitude. A plain LoRA
    # merge would silently drop that magnitude and produce a different model.
    adapted=weight+up@down
    norms=np.linalg.norm(adapted,axis=1)
    if np.any(norms<=0) or not np.all(np.isfinite(norms)):raise ValueError('Invalid DoRA norm')
    return np.ascontiguousarray(adapted*(magnitude/norms)[:,None],dtype=np.float32)


def safetensors(path):
    import numpy as np
    with path.open('rb') as stream:
        length=struct.unpack('<Q',stream.read(8))[0]
        if length>2**24:raise ValueError('Oversized tensor header')
        header=json.loads(stream.read(length));start=8+length
        result={}
        for name,entry in header.items():
            if name=='__metadata__':continue
            if entry['dtype']!='BF16':raise ValueError('Expected BF16 pixel DoRA')
            low,high=entry['data_offsets'];stream.seek(start+low)
            data=stream.read(high-low)
            if len(data)!=high-low:raise ValueError('Truncated tensor')
            result[name]=(np.frombuffer(data,dtype='<u2').astype(np.uint32)<<16).view(np.float32).reshape(entry['shape'])
        return result


def valid_receipt(target,source_hashes):
    path=target/'krea-pixel-dora.json'
    try:
        receipt=json.loads(path.read_text())
        if receipt['version']!=VERSION or receipt['sources']!=source_hashes:return None
        if all((target/name).is_file() and digest(target/name)==sha for name,sha in receipt['outputs'].items()):return receipt
    except (OSError,ValueError,KeyError):pass
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ggml-library',type=Path,default=LIB)
    args=parser.parse_args();os.umask(0o077)
    manifest=json.loads((ROOT/'config/models.lock.json').read_text())['krea-pixel']
    inputs={key:TARGET/Path(manifest[key]['file']).name for key in ('diffusion','lora32','lora64','lora128')}
    source_hashes={key:manifest[key]['sha256'] for key in inputs}
    for key,path in inputs.items():
        if digest(path)!=source_hashes[key]:raise ValueError('Source checksum mismatch: '+key)
    if valid_receipt(TARGET,source_hashes):print('DoRA variants already verified',flush=True);return
    import numpy as np
    import gguf
    lib=ctypes.CDLL(str(args.ggml_library))
    lib.ggml_quantize_chunk.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int64,ctypes.c_int64,ctypes.c_int64,ctypes.c_void_p]
    lib.ggml_quantize_chunk.restype=ctypes.c_size_t
    reader=gguf.GGUFReader(str(inputs['diffusion']))
    tensors={t.name:t for t in reader.tensors}
    outputs={};roles={}
    for grid in (32,64,128):
        started=time.monotonic();adapter=safetensors(inputs['lora'+str(grid)])
        target=TARGET/f'Krea-2-Turbo-Pixel{grid}-DoRA-v{VERSION}-Q3_K_M.gguf'
        partial=target.with_suffix('.partial')
        partial.unlink(missing_ok=True)
        if target.resolve()==inputs['diffusion'].resolve():raise ValueError('Refusing to overwrite source')
        shutil.copyfile(inputs['diffusion'],partial)
        applied=set()
        try:
            with partial.open('r+b') as stream:
                for name,magnitude in adapter.items():
                    if not name.endswith('.magnitude'):continue
                    prefix=name.removesuffix('.magnitude')
                    a_name=prefix+'.lora_A.weight';b_name=prefix+'.lora_B.weight'
                    tensor=tensors[prefix.removeprefix('diffusion_model.')+'.weight']
                    dtype=tensor.tensor_type
                    weight=np.empty(tuple(reversed(tensor.shape)),dtype=np.float32)
                    if dtype==gguf.GGMLQuantizationType.F32:weight[:]=tensor.data
                    elif dtype==gguf.GGMLQuantizationType.F16:weight[:]=tensor.data.astype(np.float32)
                    elif dtype in (gguf.GGMLQuantizationType.Q3_K,gguf.GGMLQuantizationType.Q6_K):
                        function=getattr(lib,'dequantize_row_'+dtype.name.lower().replace('_k','_K'))
                        function.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int64]
                        function(tensor.data.ctypes.data,weight.ctypes.data,weight.size)
                    else:raise ValueError('Unexpected base tensor type: '+dtype.name)
                    merged=merge_dora(weight,adapter[a_name],adapter[b_name],magnitude)
                    encoded=np.empty(tensor.n_bytes,dtype=np.uint8)
                    count=lib.ggml_quantize_chunk(int(dtype),merged.ctypes.data,encoded.ctypes.data,0,merged.shape[0],merged.shape[1],None)
                    if count!=tensor.n_bytes:raise ValueError('Unexpected quantized byte count')
                    stream.seek(tensor.data_offset);stream.write(encoded.tobytes())
                    applied.update((name,a_name,b_name))
                if applied!=set(adapter):raise ValueError('Not every DoRA tensor was consumed')
                stream.flush();os.fsync(stream.fileno())
            partial.replace(target)
        finally:partial.unlink(missing_ok=True)
        outputs[target.name]=digest(target);roles['pixel'+str(grid)]=str(target)
        print(json.dumps(dict(grid=grid,tensors=len(applied),seconds=round(time.monotonic()-started,2),sha256=outputs[target.name])),flush=True)
    receipt=dict(version=VERSION,sources=source_hashes,outputs=outputs,roles=roles,gguf='0.19.0',ggml_revision='a77d3623180b2bc1886f3dd04c0aa04156a987ef')
    temporary=TARGET/'krea-pixel-dora.tmp';temporary.write_text(json.dumps(receipt,indent=2)+'\n');temporary.replace(TARGET/'krea-pixel-dora.json')

if __name__=='__main__':main()
