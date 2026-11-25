"""Resource-level XOR deltas; no complete game fonts, textures or archive chunks in payload."""
import json,re,struct,zipfile
from pathlib import Path
import lz4.block
import index_probe as P
require=P.require;sha=P.sha
ROOT=Path(__file__).resolve().parent.parent
PAYLOAD=ROOT/'fonts/font_deltas.zip'

def xor(a,b):
    require(len(a)==len(b),'Delta length mismatch');return (int.from_bytes(a,'little')^int.from_bytes(b,'little')).to_bytes(len(a),'little')

def get_chunk(root,layout,cid):
    chunks,archives=layout[3],layout[5]
    ar,pos,n=struct.unpack_from('<III',chunks,cid*12)
    require(0<n<=P.BLOCK*2,'Invalid compressed chunk size')
    with (root/'dat'/archives[ar]).open('rb') as f:f.seek(pos);raw=f.read(n)
    require(len(raw)==n,'Truncated original block');plain=lz4.block.decompress(raw,uncompressed_size=P.BLOCK)
    require(len(plain)==P.BLOCK,'Unexpected block size');return raw,plain

def geometry(layout,name):
    rows,paths=layout[:2];r=rows[paths.index(name)];size,start,off=r[3:6];ids=range(start,start+(off+size+P.BLOCK-1)//P.BLOCK)
    require(size>0 and off<P.BLOCK and ids.stop<=len(layout[3])//12,'Invalid font resource geometry');return size,off,ids

def read_resource(root,layout,name):
    size,off,ids=geometry(layout,name);return b''.join(get_chunk(root,layout,c)[1] for c in ids)[off:off+size]

def validate_manifest(m):
    require(m['format']==1 and m['index']==P.INDEX_SHA and m['exe']==P.EXE_SHA,'Wrong font payload build')
    fonts=m['fonts'];expected=json.loads((ROOT/'fonts/original_hashes.json').read_text('utf-8'));require(len(fonts)==32 and set(fonts)==set(expected),'Expected exact 32 font resources');require(all(d['before']==expected[n] for n,d in fonts.items()),'Original font hashes differ from v9.2 source')
    for name,d in fonts.items():
        require(re.fullmatch(r'data:ui/fonts/[A-Za-z0-9_]+\.(fnt|gtx)',name) is not None,'Unsafe resource name')
        require(0<d['size']<=32*1024*1024 and all(re.fullmatch(r'[0-9a-f]{64}',d[k]) for k in ('before','after','delta_sha')),'Invalid font metadata')
    require(sum(n.endswith('.fnt') for n in fonts)==16,'Expected 16 font definitions');require(sum(n.endswith('.gtx') for n in fonts)==16,'Expected 16 atlases')
    require(len({d['member'] for d in fonts.values()})==32 and all(re.fullmatch(r'delta/\d{2}\.xor',d['member']) for d in fonts.values()),'Unexpected delta members')
    return fonts

def build(root,index,payload=None):
    payload=PAYLOAD if payload is None else payload
    require(payload.is_file(),'Font payload missing: use completed release, not source template')
    layout=P.layout(index);rows,paths,names,chunks,arch,archives=layout
    require(sha(index)==P.INDEX_SHA,'Unsupported original index')
    with zipfile.ZipFile(payload) as z:
        m=json.loads(z.read('manifest.json'));fonts=validate_manifest(m)
        require(set(z.namelist())=={'manifest.json'}|{d['member'] for d in fonts.values()} and len(z.namelist())==33,'Unexpected font ZIP entries')
        ids=sorted({c for name in fonts for c in geometry(layout,name)[2]})
        original={c:get_chunk(root,layout,c) for c in ids};contents={c:bytearray(original[c][1]) for c in ids}
        for name,d in sorted(fonts.items()):
            size,off,cids=geometry(layout,name);require(size==d['size'],'Resource size mismatch '+name)
            raw=b''.join(original[c][1] for c in cids)[off:off+size]
            require(sha(raw)==d['before'],'Original font mismatch '+name)
            info=z.getinfo(d['member']);require(info.file_size==size,'Delta size mismatch '+name)
            delta=z.read(info);require(sha(delta)==d['delta_sha'],'Delta hash mismatch '+name)
            patched=xor(raw,delta);require(sha(patched)==d['after'],'Font output hash mismatch '+name)
            stream=b''.join(contents[c] for c in cids);stream=stream[:off]+patched+stream[off+size:]
            for j,c in enumerate(cids):contents[c][:]=stream[j*P.BLOCK:(j+1)*P.BLOCK]
        for name,d in fonts.items():
            size,off,cids=geometry(layout,name);require(sha(b''.join(contents[c] for c in cids)[off:off+size])==d['after'],'Font overlap mismatch '+name)
    out=bytearray(index);patches={};sizes=P.SIZES.copy();table=48+len(rows)*56
    for cid in ids:
        plain=bytes(contents[cid]);before=original[cid][1]
        if plain==before:continue
        ar,_,_=struct.unpack_from('<III',chunks,cid*12);n=archives[ar];require(n in sizes,'Unexpected target archive')
        packed=lz4.block.compress(plain,mode='high_compression',compression=16,store_size=False)
        require(lz4.block.decompress(packed,uncompressed_size=P.BLOCK)==plain,'LZ4 roundtrip mismatch')
        off=sizes[n];sizes[n]+=len(packed);require(sizes[n]<=0xffffffff,'Archive overflow')
        struct.pack_into('<III',out,table+12*cid,ar,off,len(packed))
        patches[cid]={'archive':n,'offset':off,'size':len(packed),'new_data':packed,'new_sha':sha(packed)}
    require(bool(patches),'No changed font blocks')
    return bytes(out),patches,{n:d['after'] for n,d in fonts.items()}
