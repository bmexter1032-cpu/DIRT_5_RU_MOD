#!/usr/bin/env python3
"""DIRT_RU 1.0.0 release candidate: append-only overlays and exact selector patch."""
import argparse,contextlib,json,os,subprocess,sys,zipfile
from pathlib import Path
import index_probe as P
import selector_patch as S
import compiler,fonts,overlay
require=P.require;sha=P.sha
VERSION='1.0.0-rc.1'
PATCH_SHA='26252a366b5449bdbddb9284038ce2a5f7f5c7bfd4729463d1690fef6137049e'
BACKUP='DIRT_RU_1_0_backup.zip'

def paths(root):return root/'dat/index/dat.ndx',root/'game_release.exe',root/'_ru_tools'/BACKUP

def original_sizes(root):
    for name,size in P.SIZES.items():require((root/'dat'/name).stat().st_size==size,'Unexpected DAT size: '+name)

def prepare(root):
    P.closed();ix,ex,_=paths(root);i=ix.read_bytes();e=ex.read_bytes()
    require(sha(i)==P.INDEX_SHA and sha(e)==P.EXE_SHA,'Unsupported or modified game. Restore original EXE/index first.');original_sizes(root)
    bra=P.read_bra(root,i);loc=compiler.compile_loc(bra)
    f,patches,hashes=fonts.build(root,i)
    p,_,tails=overlay.combine(i,e,bra,loc,f,patches)
    q=S.build(e);require(sha(q)==PATCH_SHA,'Selector build hash mismatch')
    print('CHECK PASS: 6473 Russian strings, 32 font resources, original LOC/audio unchanged')
    return i,e,p,q,tails,hashes

def save_backup(root,plan):
    _,_,bak=paths(root);i,e,p,q,tails,hashes=plan;bak.parent.mkdir(exist_ok=True)
    require(not bak.exists(),'Backup already exists; refusing overwrite')
    m={'version':VERSION,'original_index':sha(i),'original_exe':sha(e),'index':sha(p),'exe':sha(q),'fonts':hashes,'loc':compiler.LOC_SHA,'tails':{n:sha(t) for n,t in tails.items()},'payload':sha(fonts.PAYLOAD.read_bytes())}
    tmp=bak.with_suffix('.creating.zip');require(not tmp.exists(),'Incomplete backup staging exists; inspect before retrying')
    try:
        with zipfile.ZipFile(tmp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
            for n,b in [('manifest.json',json.dumps(m)),('original.ndx',i),('original.exe',e),('patched.ndx',p),('patched.exe',q)]+[(n+'.tail',t) for n,t in tails.items()]:z.writestr(n,b)
        load_backup(root,tmp)
        require(not bak.exists(),'Backup appeared during preparation');os.replace(tmp,bak)
    except BaseException:
        if tmp.exists():tmp.unlink()
        raise

def load_backup(root,source=None):
    _,_,bak=paths(root)
    with zipfile.ZipFile(source or bak) as z:
        expected={'manifest.json','original.ndx','original.exe','patched.ndx','patched.exe'}|{n+'.tail' for n in P.SIZES}
        require(set(z.namelist())==expected and len(z.namelist())==len(expected),'Invalid backup entries')
        require(z.testzip() is None,'Backup CRC failure');m=json.loads(z.read('manifest.json'));i=z.read('original.ndx');e=z.read('original.exe');p=z.read('patched.ndx');q=z.read('patched.exe');tails={n:z.read(n+'.tail') for n in P.SIZES}
    require(m['version']==VERSION and sha(i)==P.INDEX_SHA==m['original_index'] and sha(e)==P.EXE_SHA==m['original_exe'],'Backup originals mismatch')
    require(sha(p)==m['index'] and sha(q)==m['exe']==PATCH_SHA and q==S.build(e),'Backup patch mismatch')
    require(all(sha(t)==m['tails'][n] for n,t in tails.items()) and m['loc']==compiler.LOC_SHA and len(m['fonts'])==32,'Backup payload mismatch')
    return i,e,p,q,tails,m

def check_tails(root,tails,complete=False):
    for n,t in tails.items():
        f=root/'dat'/n;delta=f.stat().st_size-P.SIZES[n]
        require(0<=delta<=len(t) and (not complete or delta==len(t)),'Foreign DAT size: '+n)
        with f.open('rb') as h:h.seek(P.SIZES[n]);require(h.read()==t[:delta],'Foreign DAT tail: '+n)

def verify(root):
    ix,ex,_=paths(root);i,e,p,q,tails,m=load_backup(root)
    require(ix.read_bytes()==p and ex.read_bytes()==q,'Installed EXE/index mismatch');check_tails(root,tails,True)
    layout=P.layout(p)
    require(sha(fonts.read_resource(root,layout,P.BRA))==P.BRA_SHA,'Original BRA mismatch')
    require(sha(fonts.read_resource(root,layout,P.RUS))==m['loc'],'RUS resource mismatch')
    for n,h in m['fonts'].items():require(sha(fonts.read_resource(root,layout,n))==h,'Font resource mismatch '+n)
    print('VERIFY PASS: RUS, BRA, 32 font resources, conditional selector')

def restore(root):
    P.closed();ix,ex,_=paths(root);i,e,p,q,tails,m=load_backup(root)
    require(ix.read_bytes() in (i,p) and ex.read_bytes() in (e,q),'Foreign EXE/index; refusing rollback');check_tails(root,tails)
    P.atomic(ix,i);P.atomic(ex,e)
    for n in tails:
        with (root/'dat'/n).open('r+b') as f:f.truncate(P.SIZES[n]);f.flush();os.fsync(f.fileno())
    original_sizes(root);require(sha(ix.read_bytes())==P.INDEX_SHA and sha(ex.read_bytes())==P.EXE_SHA,'Restore mismatch')
    print('RESTORE VERIFIED: original EXE/index, original DAT lengths. Backup retained.')

def apply(root):
    P.closed();ix,ex,bak=paths(root)
    if bak.exists():
        i,e,p,q,tails,m=load_backup(root)
        if ix.read_bytes()==p and ex.read_bytes()==q:
            verify(root);print('ALREADY INSTALLED');return
        require(ix.read_bytes()==i and ex.read_bytes()==e,'Incomplete or foreign installation; restore first')
        original_sizes(root)
        plan=prepare(root)
        require(plan[:5]==(i,e,p,q,tails) and plan[5]==m['fonts'] and sha(fonts.PAYLOAD.read_bytes())==m['payload'],'Previous backup differs from new plan; keep it and investigate')
    else:
        plan=prepare(root);i,e,p,q,tails,_=plan;save_backup(root,plan)
    try:
        P.closed();original_sizes(root);require(ix.read_bytes()==i and ex.read_bytes()==e,'Game changed during preparation')
        for n,t in tails.items():
            with (root/'dat'/n).open('ab') as f:
                require(f.tell()==P.SIZES[n],'DAT changed during preparation');f.write(t);f.flush();os.fsync(f.fileno())
        P.atomic(ix,p);P.atomic(ex,q);verify(root)
    except BaseException:
        restore(root);raise
    print('INSTALLED: launch game_release.exe -language rus')

@contextlib.contextmanager
def lock(root):
    folder=root/'_ru_tools';folder.mkdir(exist_ok=True);path=folder/'DIRT_RU.lock'
    with path.open('a+b') as f:
        f.seek(0,2)
        if f.tell()==0:f.write(b'\0');f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            f.seek(0)
            if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)

def shortcut(root):
    require(os.name=='nt','Windows only');verify(root)
    env=dict(os.environ,DIRT_RU_GAME=str(root))
    command=r'''$ErrorActionPreference='Stop'; $g=$env:DIRT_RU_GAME; $p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'DIRT 5 - RU.lnk'; $s=New-Object -ComObject WScript.Shell; $l=$s.CreateShortcut($p); if(Test-Path -LiteralPath $p){if($l.TargetPath -ne (Join-Path $g 'game_release.exe') -or $l.Arguments -ne '-language rus'){throw 'Shortcut exists and differs; not overwriting'}}; $l.TargetPath=Join-Path $g 'game_release.exe'; $l.Arguments='-language rus'; $l.WorkingDirectory=$g; $l.IconLocation=(Join-Path $g 'game_release.exe')+',0'; $l.Save(); Write-Host $p'''
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=env,check=True)

def locate(root):
    if root is None:
        root=Path(input('DIRT 5 game folder (contains game_release.exe): ').strip().strip('"'))
    root=root.expanduser().resolve();ix,ex,_=paths(root);require(ix.is_file() and ex.is_file(),'Game root not found');return root

def main():
    require(sys.flags.optimize==0,'Do not use Python -O');p=argparse.ArgumentParser();p.add_argument('action',choices=['check','apply','verify','restore','shortcut','launch']);p.add_argument('root',type=Path,nargs='?');a=p.parse_args();root=locate(a.root)
    if a.action in ('apply','restore'):
        with lock(root):globals()[a.action](root)
    elif a.action=='launch':
        P.closed();verify(root);subprocess.Popen([str(root/'game_release.exe'),'-language','rus'],cwd=root)
    elif a.action=='check':prepare(root)
    else:globals()[a.action](root)

if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:raise SystemExit('ERROR: '+str(e))
