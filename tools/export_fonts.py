"""Maintainer only: extract resource XOR deltas from the already verified v10.1 installation."""
import argparse,json,os,struct,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'patcher'))
import index_probe as P
import selector_patch as S
import compiler,fonts,overlay,install
import lz4.block
require=P.require;sha=P.sha

def export(root,out):
    P.closed();require(not out.exists(),'Output exists; not overwriting')
    bak=root/'_ru_tools/dirt5_native_ru_v10_test_backup.zip'
    with zipfile.ZipFile(bak) as z:
        require(z.testzip() is None,'Legacy backup CRC failure');m=json.loads(z.read('manifest.json'));i=z.read('original.ndx');e=z.read('original.exe');p=z.read('patched.ndx');q=z.read('patched.exe');tails={n:z.read(n+'.tail') for n in P.SIZES}
    require(m['version']=='v10_test' and sha(i)==m['original_index']==P.INDEX_SHA and sha(e)==m['original_exe']==P.EXE_SHA,'Legacy original mismatch')
    require(sha(p)==m['index'] and sha(q)==m['exe']==S.V10_SHA and q==e[:P.EXE_OFFSET]+P.NEW+e[P.EXE_OFFSET+len(P.OLD):],'Legacy patch mismatch')
    require((root/'game_release.exe').read_bytes()==S.build(e) and sha(S.build(e))==install.PATCH_SHA,'Expected active v10.1 EXE')
    require((root/'dat/index/dat.ndx').read_bytes()==p,'Expected active v10 index')
    require(all(sha(t)==m['tails'][n] for n,t in tails.items()),'Legacy tail manifest mismatch');install.check_tails(root,tails,True)
    old=P.layout(i);new=P.layout(p)
    bra=P.read_bra(root,i);loc=compiler.compile_loc(bra)
    require(m['loc']==compiler.LOC_SHA and fonts.read_resource(root,new,P.RUS)==loc and fonts.read_resource(root,new,P.BRA)==bra,'Installed LOC mismatch')
    require(len(m['fonts'])==32,'Legacy font manifest incomplete')
    manifest={'format':1,'index':P.INDEX_SHA,'exe':P.EXE_SHA,'fonts':{}}
    out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.creating.zip');require(not tmp.exists(),'Staging file exists')
    try:
        with zipfile.ZipFile(tmp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for idx,(name,expected) in enumerate(sorted(m['fonts'].items())):
                require(name.startswith('data:ui/fonts/') and name.endswith(('.fnt','.gtx')),'Unexpected legacy font name')
                a=fonts.read_resource(root,old,name);b=fonts.read_resource(root,new,name)
                require(sha(b)==expected and len(a)==len(b),'Legacy font mismatch '+name)
                delta=fonts.xor(a,b);member=f'delta/{idx:02d}.xor';z.writestr(member,delta)
                manifest['fonts'][name]={'size':len(a),'before':sha(a),'after':sha(b),'delta_sha':sha(delta),'member':member}
            fonts.validate_manifest(manifest);z.writestr('manifest.json',json.dumps(manifest,indent=2,sort_keys=True))
        # Rebuild all overlay blocks from resource deltas, compare the *decompressed* bytes
        # with the verified installed v10, including surrounding non-font bytes.
        fi,patches,hashes=fonts.build(root,i,tmp)
        require(hashes==m['fonts'],'Rebuilt font hashes mismatch')
        oldchunks=old[3];newchunks=new[3]
        changed={c for c in range(len(oldchunks)//12) if oldchunks[c*12:c*12+12]!=newchunks[c*12:c*12+12]}
        require(changed==set(patches),'Legacy changed chunk set differs from rebuilt font overlays')
        for c,record in patches.items():
            expected=fonts.get_chunk(root,new,c)[1];actual=lz4.block.decompress(record['new_data'],uncompressed_size=P.BLOCK)
            require(actual==expected,'Non-font bytes or rebuilt chunk mismatch '+str(c))
        final,_,newtails=overlay.combine(i,e,bra,loc,fi,patches)
        fl=P.layout(final);require(fl[:3]==new[:3] and fl[4:]==new[4:],'Rebuilt resource tree differs')
        os.replace(tmp,out)
    except BaseException:
        if tmp.exists():tmp.unlink()
        raise
    print('EXPORT PASS: 32 exact font resources; all changed blocks identical after decompression; RUS LOC identical')
    print('FONT PAYLOAD SHA256:',sha(out.read_bytes()));print(out)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('game',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    try:export(a.game.resolve(),a.output.resolve())
    except (Exception,KeyboardInterrupt) as e:raise SystemExit('ERROR: '+str(e))
