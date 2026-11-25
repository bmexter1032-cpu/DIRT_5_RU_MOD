"""Preserved v10 resource/index merge; original LOC/audio descriptors remain intact."""
import struct
import lz4.block
import index_probe as P
require=P.require;sha=P.sha

def combine(index,exe,bra,loc,font_index,patches):
    # Proven insertion code, with supplied compiled RUS instead of marker text.
    p,q,rus_tail,_=P.plan(index,exe,bra,loc)
    rows,paths,names,chunks,arch,archives=P.layout(index)
    fr,fp,fn,fc,fa,farch=P.layout(font_index)
    require((fr,fp,fn,fa,farch)==(rows,paths,names,arch,archives),'Font-only builder changed original resource rows')
    require(len(fc)==len(chunks),'Unexpected font chunk table size')
    # No font chunk may overlap any original language LOC or audio resource.
    changed=set(patches)
    for name,r in zip(paths,rows):
        if not name.startswith(('data:localisation/','data:audio/')):continue
        size,start,off=r[3:6]
        if size:
            count=(off+size+P.BLOCK-1)//P.BLOCK
            require(not any(c in changed for c in range(start,start+count)),'Font overlay touches protected resource '+name)
    table=48+len(rows)*56
    # Confirm font-index modifications are exactly those declared by the builder.
    expected=bytearray(index)
    tails={n:bytearray() for n in P.SIZES}
    for cid,rec in sorted(patches.items(),key=lambda kv:(kv[1]['archive'],kv[1]['offset'])):
        n=rec['archive'];data=rec['new_data'];ar=archives.index(n)
        require(n in tails,'Unexpected archive: '+n)
        require(rec['offset']==P.SIZES[n]+len(tails[n]) and len(data)==rec['size'] and sha(data)==rec['new_sha'],'Invalid font append record')
        require(len(lz4.block.decompress(data,uncompressed_size=P.BLOCK))==P.BLOCK,'Font LZ4 failure')
        tails[n].extend(data)
        struct.pack_into('<III',expected,table+12*cid,ar,rec['offset'],len(data))
    require(bytes(expected)==font_index,'Unexpected font index change')
    # New LOC is appended after all font overlays in DAT 63; shift only its 3 new records.
    rr,pp,nn,cc,aa,ar=P.layout(p)
    out=bytearray(p);new_table=48+len(rr)*56
    for cid in changed:
        out[new_table+cid*12:new_table+cid*12+12]=fc[cid*12:cid*12+12]
    for cid in range(len(chunks)//12,len(cc)//12):
        a,pos,n=struct.unpack_from('<III',cc,cid*12)
        require(archives[a]==P.ARCH,'Unexpected RUS archive')
        struct.pack_into('<III',out,new_table+cid*12,a,pos+len(tails[P.ARCH]),n)
    tails[P.ARCH].extend(rus_tail)
    out=bytes(out)
    xr,xp,xn,xc,xa,xar=P.layout(out)
    require((xr,xp,xn,xa,xar)==(rr,pp,nn,aa,ar),'Combined resource rows changed')
    # Validate every original LOC and audio chunk descriptor, not just BRA.
    for name,r in zip(paths,rows):
        if name.startswith(('data:localisation/','data:audio/')) and r[3]:
            start=r[4];end=start+(r[5]+r[3]+P.BLOCK-1)//P.BLOCK
            require(xc[start*12:end*12]==chunks[start*12:end*12],'Original protected chunk changed: '+name)
    # Read the new resource through final index using only planned append bytes.
    r=xr[xp.index(P.RUS)]; blocks=[]
    for cid in range(r[4],r[4]+(r[3]+P.BLOCK-1)//P.BLOCK):
        a,pos,n=struct.unpack_from('<III',xc,cid*12);fn=archives[a];off=pos-P.SIZES[fn]
        require(off>=0 and off+n<=len(tails[fn]),'New LOC outside append')
        blocks.append(lz4.block.decompress(bytes(tails[fn][off:off+n]),uncompressed_size=P.BLOCK))
    require(b''.join(blocks)[:r[3]]==loc,'RUS reconstruction failed')
    return out,q,{n:bytes(b) for n,b in tails.items()}

