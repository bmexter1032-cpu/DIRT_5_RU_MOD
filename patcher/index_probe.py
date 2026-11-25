#!/usr/bin/env python3
"""DIRT5 LANG-04: independent Xbox RUS resource, Portuguese marker text, ENG global language."""
import argparse, hashlib, json, os, struct, subprocess, tempfile, zipfile
from pathlib import Path
import lz4.block

INDEX_SHA='275485d8e0125b07749f52c332f5989fcedb1177cea43bd1ae043909d3adf7bd'
EXE_SHA='32d0b080f7e7d1d3d0057815342ddb9b232cc5f629a22b5e2e9318c3e4775efe'
BRA_SHA='38cf63c58a5c9ff3d46029aaff559cc80a60539b2d441aa2b1992608471104a2'
SIZES={'36_WIP_INIT.dat':2093510689,'63_WIP_INIT.dat':1409400101}
ARCH='63_WIP_INIT.dat'; BLOCK=131072; NIL=0xffffffff; ROW=struct.Struct('<QQQ8I')
EXE_OFFSET=0x42b631
OLD=bytes.fromhex('c644244000e87589ccff')
NEW=bytes.fromhex('c7442440727573009090')
RUS='data:localisation/xbox/rus.loc'; BRA='data:localisation/xbox/bra.loc'
BACKUP='dirt5_rus_text_probe_v3_backup.zip'
def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def fnv(s):
    h=0xcbf29ce484222325
    for c in s.encode('ascii'): h=((h^c)*0x100000001b3)&0xffffffffffffffff
    return h
def layout(b):
    e,c,bs=struct.unpack_from('<III',b,12); a=struct.unpack_from('<I',b,32)[0]; n=struct.unpack_from('<Q',b,40)[0]
    require(bs==BLOCK and a==75 and e in (112452,112453) and c in (1246393,1246396),'Unexpected index layout')
    t=48+e*56; at=t+c*12; nt=at+a*8
    require(nt+n==len(b),'Index size mismatch')
    rows=[ROW.unpack_from(b,48+i*56) for i in range(e)]; names=b[nt:]
    def name(o):
        require(o<len(names),'Bad string offset'); end=names.index(b'\0',o); return names[o:end].decode('utf8')
    paths=[name(r[0]) for r in rows]
    require(len(set(paths))==e,'Duplicate index paths')
    archives=[name(struct.unpack_from('<Q',b,at+8*i)[0])+'.dat' for i in range(a)]
    return rows,paths,names,b[t:at],b[at:nt],archives

def read_bra(root,b):
    rows,paths,names,chunks,arch,archives=layout(b)
    r=rows[paths.index(BRA)]; size,start,off=r[3:6]; count=(off+size+BLOCK-1)//BLOCK
    require((size,start,off,count)==(291673,1102975,118691,4),'Unexpected BRA location')
    data=[]
    for k in range(start,start+count):
        ar,pos,length=struct.unpack_from('<III',chunks,k*12)
        require(archives[ar]==ARCH,'Unexpected BRA archive')
        with (root/'dat'/ARCH).open('rb') as f: f.seek(pos); raw=f.read(length)
        require(len(raw)==length,'Truncated original chunk')
        data.append(lz4.block.decompress(raw,uncompressed_size=BLOCK))
    raw=b''.join(data)[off:off+size]
    require(sha(raw)==BRA_SHA,'Original Xbox BRA LOC hash mismatch')
    return raw

def make_loc(raw):
    require(sha(raw)==BRA_SHA,'Wrong BRA LOC')
    b=bytearray(raw)
    for off in (0x9b,0xc0):
        require(b[off:off+3]==b'bra','Unexpected language field'); b[off:off+3]=b'rus'
    for off in (0xa6,0xb2):
        require(struct.unpack_from('<Q',b,off)[0]==fnv('strings_xbox_bra'),'Unexpected LOC hash'); struct.pack_into('<Q',b,off,fnv('strings_xbox_rus'))
    require(struct.unpack_from('<I',b,0xc3)[0]==6473 and b[0xc7:]==raw[0xc7:],'LOC text body changed')
    return bytes(b)

def plan(index,exe,bra,loc=None):
    require(sha(index)==INDEX_SHA and sha(exe)==EXE_SHA,'Original index and EXE required')
    require(exe[EXE_OFFSET:EXE_OFFSET+len(OLD)]==OLD,'EXE byte signature mismatch')
    patched_exe=exe[:EXE_OFFSET]+NEW+exe[EXE_OFFSET+len(OLD):]
    loc=make_loc(bra) if loc is None else loc; packed=[]
    for off in range(0,len(loc),BLOCK):
        p=loc[off:off+BLOCK].ljust(BLOCK,b'\0'); c=lz4.block.compress(p,store_size=False,mode='high_compression',compression=9)
        require(lz4.block.decompress(c,uncompressed_size=BLOCK)==p,'LZ4 roundtrip failed'); packed.append(c)
    rows,paths,names,chunks,arch,archives=layout(index); old_count=len(chunks)//12
    require(len(packed)==3 and archives[63]==ARCH and RUS not in paths,'Unexpected archive layout')
    k=paths.index('data:localisation/xbox/kor.loc'); j=paths.index('data:localisation/xbox/sim.loc'); src=rows[paths.index(BRA)]
    require(j==k+1 and rows[k][7]==j and src[8]==NIL,'Unexpected sibling layout')
    require(src[1]==int.from_bytes(hashlib.md5(BRA.encode()).digest()[:8],'little'),'Unexpected path hash')
    def shift(v): return v if v==NIL or v<j else v+1
    newrows=[]; short=len(names); extra=b'rus.loc\0'; full=short+len(extra); extra+=RUS.encode()+b'\0'
    for i,r in enumerate(rows):
        if i==j:
            newrows.append((full,int.from_bytes(hashlib.md5(RUS.encode()).digest()[:8],'little'),short,len(loc),old_count,0,shift(src[6]),shift(j),NIL,src[9],src[10]))
        v=list(r); v[6:9]=map(shift,r[6:9]);
        if i==k: v[7]=j
        newrows.append(tuple(v))
    newchunks=bytearray(chunks); pos=SIZES[ARCH]
    for p in packed: newchunks+=struct.pack('<III',63,pos,len(p));pos+=len(p)
    header=bytearray(index[:48]);struct.pack_into('<II',header,12,len(newrows),old_count+len(packed));struct.pack_into('<Q',header,40,len(names)+len(extra))
    patched=bytes(header)+b''.join(ROW.pack(*r) for r in newrows)+newchunks+arch+names+extra
    rr,pp,nn,cc,aa,ar=layout(patched)
    require(pp[j]==RUS and pp[:j]+pp[j+1:]==paths and aa==arch and ar==archives and cc[:len(chunks)]==chunks and nn[:len(names)]==names,'Index preservation failed')
    for i,r in enumerate(rows):
        expected=list(r); expected[6:9]=map(shift,r[6:9]);
        if i==k:expected[7]=j
        require(rr[shift(i)]==tuple(expected),'Original index row changed unexpectedly')
    require(rr[j][3:6]==(len(loc),old_count,0) and rr[j][6]==shift(src[6]) and rr[j][7]==shift(j),'New LOC record invalid')
    require(b''.join(lz4.block.decompress(p,uncompressed_size=BLOCK) for p in packed)[:len(loc)]==loc,'LOC reconstruction failed')
    return patched,patched_exe,b''.join(packed),loc

def atomic(path,data):
    fd,temp=tempfile.mkstemp(prefix='.dirt_ru_',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def closed():
    if os.name=='nt':
        r=subprocess.run(['tasklist','/FI','IMAGENAME eq game_release.exe','/FO','CSV','/NH'],capture_output=True,check=True)
        require(b'game_release.exe' not in r.stdout.lower(),'Close DIRT 5 first')
