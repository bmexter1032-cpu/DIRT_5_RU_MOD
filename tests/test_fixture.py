"""Integration test with user-provided private handoff/diagnostics ZIPs.
Real EXE, NDX, BRA chunks and original font resources; synthetic surrounding
font blocks and synthetic one-byte changes (NOT production glyphs). No game
writes. Run on Linux with sparse-file support and lz4. Do not publish fixtures.
Usage: python tests/test_fixture.py HANDOFF.zip DIAGNOSTICS.zip
"""
import argparse,io,json,os,struct,sys,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'patcher'),str(R/'tools')]
import compiler,fonts,install,index_probe as P,overlay,selector_patch as S,export_fonts

def test(handoff,diagnostics):
    with zipfile.ZipFile(handoff) as h, zipfile.ZipFile(diagnostics) as d:
        def get(t):return h.read(next(n for n in h.namelist() if n.endswith(t)))
        i=get('/vanilla_reference/dat.ndx');e=d.read('game_release.exe');assert P.sha(i)==P.INDEX_SHA and P.sha(e)==P.EXE_SHA
        old=P.layout(i);hashes=json.loads((R/'fonts/original_hashes.json').read_text());resources={}
        for pack in ('dirt5_cyrillic_font_sources.zip','dirt5_extra_font_sources_v3.zip'):
            with zipfile.ZipFile(io.BytesIO(get('/'+pack))) as z:
                for n in z.namelist():
                    name='data:ui/fonts/'+n.rsplit('/',1)[-1]
                    if name in hashes:resources[name]=z.read(n)
        assert set(resources)==set(hashes) and all(P.sha(v)==hashes[n] for n,v in resources.items())
        plain={}
        for n,b in resources.items():
            size,off,ids=fonts.geometry(old,n);assert size==len(b)
            for j,c in enumerate(ids):
                buf=plain.setdefault(c,bytearray(P.BLOCK));a=max(0,off-j*P.BLOCK);end=min(P.BLOCK,off+size-j*P.BLOCK);src=j*P.BLOCK+a-off;buf[a:end]=b[src:src+end-a]
        plain={c:bytes(b) for c,b in plain.items()}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'game';(root/'dat/index').mkdir(parents=True);(root/'_ru_tools').mkdir();ix,ex,_=install.paths(root);ix.write_bytes(i);ex.write_bytes(e)
            for n,size in P.SIZES.items():
                with (root/'dat'/n).open('wb') as f:f.truncate(size)
            with zipfile.ZipFile(io.BytesIO(get('/dirt5_xbox_loc_samples.zip'))) as z:
                for c in range(1102975,1102979):
                    ar,pos,n=struct.unpack_from('<III',old[3],12*c);b=z.read(f'chunks/{c}.lz4block');assert len(b)==n
                    with (root/'dat'/old[5][ar]).open('r+b') as f:f.seek(pos);f.write(b)
            bra=P.read_bra(root,i);loc=compiler.compile_loc(bra);assert P.sha(loc)==compiler.LOC_SHA
            # Synthetic changes only, payload never leaves the temporary directory.
            source=Path(tmp)/'synthetic.zip';manifest={'format':1,'index':P.INDEX_SHA,'exe':P.EXE_SHA,'fonts':{}}
            with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for j,(n,b) in enumerate(sorted(resources.items())):
                    v=bytes([b[0]^1])+b[1:];delta=fonts.xor(b,v);member=f'delta/{j:02d}.xor';z.writestr(member,delta);manifest['fonts'][n]={'size':len(b),'before':P.sha(b),'after':P.sha(v),'delta_sha':P.sha(delta),'member':member}
                z.writestr('manifest.json',json.dumps(manifest))
            actual=fonts.get_chunk
            def mocked(root,layout,c):
                if c in plain and layout[3][12*c:12*c+12]==old[3][12*c:12*c+12]:return b'',plain[c]
                return actual(root,layout,c)
            with patch.object(fonts,'get_chunk',mocked),patch.object(fonts,'PAYLOAD',source):
                fi,changes,after=fonts.build(root,i);p,q,tails=overlay.combine(i,e,bra,loc,fi,changes)
                print('PASS real index + synthetic font changes:',len(changes),'changed blocks')
                # Simulate a legacy v10.1 installation for the exporter.
                m={'version':'v10_test','original_index':P.INDEX_SHA,'original_exe':P.EXE_SHA,'index':P.sha(p),'exe':P.sha(q),'tails':{n:P.sha(t) for n,t in tails.items()},'fonts':after,'loc':compiler.LOC_SHA}
                with zipfile.ZipFile(root/'_ru_tools/dirt5_native_ru_v10_test_backup.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
                    for n,b in [('manifest.json',json.dumps(m)),('original.ndx',i),('original.exe',e),('patched.ndx',p),('patched.exe',q)]+[(n+'.tail',t) for n,t in tails.items()]:z.writestr(n,b)
                for n,t in tails.items():
                    with (root/'dat'/n).open('ab') as f:f.write(t)
                ix.write_bytes(p);ex.write_bytes(S.build(e));exported=Path(tmp)/'exported.zip';export_fonts.export(root,exported)
                # Restore pristine fixture, then perform the real RC path.
                ix.write_bytes(i);ex.write_bytes(e)
                for n,s in P.SIZES.items():
                    with (root/'dat'/n).open('r+b') as f:f.truncate(s)
                with patch.object(fonts,'PAYLOAD',exported):
                    install.apply(root);install.verify(root);install.apply(root);install.restore(root)
                    assert ix.read_bytes()==i and ex.read_bytes()==e
                    # Simulate interrupted append and recovery.
                    _,_,_,_,t,m=install.load_backup(root)
                    for n,b in t.items():
                        with (root/'dat'/n).open('ab') as f:f.write(b[:len(b)//2])
                    install.restore(root)
                    # Reinstall and force post-check failure, verifying automatic rollback.
                    try:
                        with patch.object(install,'verify',side_effect=RuntimeError('injected')):install.apply(root)
                    except RuntimeError as err:assert str(err)=='injected'
                    else:raise AssertionError('Expected injected error')
                    assert ix.read_bytes()==i and ex.read_bytes()==e
                    install.original_sizes(root)
                    # Refuse unknown EXE without modifying it.
                    ex.write_bytes(b'foreign')
                    try:install.apply(root)
                    except RuntimeError:pass
                    else:raise AssertionError('Foreign EXE accepted')
                    assert ex.read_bytes()==b'foreign'
                print('PASS RC apply/verify/idempotence/restore/partial restore/forced failure rollback/foreign EXE refusal; synthetic font changes, real index and EXE')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('handoff',type=Path);a.add_argument('diagnostics',type=Path);x=a.parse_args();test(x.handoff,x.diagnostics)
