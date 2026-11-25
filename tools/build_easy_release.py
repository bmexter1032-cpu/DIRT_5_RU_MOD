"""Build RC.4 offline user ZIP. Network access only on maintainer build machine.
No game access; no execution of downloaded code before SHA-256 validation.
Run on Windows x64: py -3 tools/build_easy_release.py
"""
import argparse, hashlib, io, os, shutil, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0-rc.4'
PYVER = '3.13.17'
PYTHON = ('python-3.13.17-embed-amd64.zip',
          'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip',
          '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38')
LZ4 = ('lz4-4.4.5-cp313-cp313-win_amd64.whl',
       'https://files.pythonhosted.org/packages/18/e0/f06028aea741bbecb2a7e9648f4643235279a770c7ffaf70bd4860c73661/lz4-4.4.5-cp313-cp313-win_amd64.whl',
       'da68497f78953017deb20edff0dba95641cc86e7423dfadf7c0264e1ac60dc22')
CORE = {'fonts/README.md': '91b80f522d58fa7153b6d668c6d0aee6e166e59071a8241daa5da64b6282b91f', 'fonts/font_deltas.zip': '48ef88ee8aea8a82626a7f0fc6442b9b20c99411d191ae32992b572957c32023', 'fonts/original_hashes.json': '7d426d18b9932dad99e0d5ac886100456eccb088bee4fd179082836844f2bd19', 'patcher/compiler.py': '986c462cb7c401913caa1be8f617b6b102c4ffc6246c3ec5952e2bf85f14d95f', 'patcher/fonts.py': 'f4f798c7d9b2aaec0866285a966b6bcd7c3ec7dff3d5acd155d7687e5d5b4433', 'patcher/index_probe.py': 'be7cc83cd11925f632b07b6161733bfa3894e982a515ca77b9af8941f664fbd7', 'patcher/install.py': '995592aed86649ce67b0d84ce0bc4f75429c9d2b594e85403f46b77bb9af680e', 'patcher/overlay.py': '1b2e087eccdd6aeffbbc37a68c8e461a77b7cd0392e403d6e3fd813bf1f40c87', 'patcher/selector.s': '529cf02cbdfe4589c7e79c29c07a132062deaa21393f2d90a21c8f6f8f9f2976', 'patcher/selector_patch.py': '1a62812084ed4a6a06cab476a938d75e35bb54a9e386bd171e8c616a566edd75', 'translations/codebook.json': 'cbdb9c741bac343cc0e4e394fb4df2cbb36d786dcc55479e6af4e2f3aaaed2fb', 'translations/ru.csv': '23cc8160b8793fbe9dc181f6bd82429a1f080d5cdd0cb88b66b9df3ae8e25102'}
# Exact hashes from the audited RC.2 source.

def sha(b): return hashlib.sha256(b).hexdigest()
def need(ok, msg):
    if not ok: raise RuntimeError(msg)

def obtain(spec, cache):
    name, url, expected = spec
    path = cache / name
    if not path.exists():
        print('Downloading official dependency:', name, flush=True)
        with urllib.request.urlopen(url, timeout=90) as r: data = r.read(32*1024*1024 + 1)
        need(len(data)<=32*1024*1024 and sha(data)==expected, 'Downloaded SHA256 mismatch: '+name)
        path.write_bytes(data)
    data = path.read_bytes()
    need(sha(data)==expected, 'Cached SHA256 mismatch: '+str(path))
    print('SHA256 PASS:',name,flush=True)
    return data

def extract(data, dest, wheel=False):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        need(z.testzip() is None,'Dependency CRC failure')
        seen=set()
        for member in z.infolist():
            n=member.filename; p=PurePosixPath(n)
            need(not p.is_absolute() and '..' not in p.parts and '\\' not in n and ':' not in n and p.parts, 'Unsafe dependency path: '+n)
            need(n.casefold() not in seen,'Duplicate dependency member: '+n); seen.add(n.casefold())
            need((member.external_attr>>16)&0o170000 != 0o120000,'Symlink in dependency')
            if wheel:
                need(p.parts[0]=='lz4' or p.parts[0]=='lz4-4.4.5.dist-info','Unexpected wheel member: '+n)
            target=dest.joinpath(*p.parts)
            if member.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
            target.parent.mkdir(parents=True,exist_ok=True)
            need(not target.exists(),'Dependency file collision: '+n)
            target.write_bytes(z.read(member))

def write_zip(path, entries):
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(entries.items()):
            i=zipfile.ZipInfo(name,(2026,11,25,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(i,data,compresslevel=9)
    with zipfile.ZipFile(path) as z: need(z.testzip() is None,'Output CRC failure')

def collect_source():
    paths=[ROOT/n for n in ['README.md','README_EN.md','CHANGELOG.md','THIRD_PARTY_NOTICES.md','requirements.txt','.gitignore','.gitattributes','BUILD_RELEASE.bat']]
    for folder in ('patcher','translations','fonts','docs','tests','tools','installer'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix.lower() in ('.py','.s','.c','.md','.json','.csv','.zip','.ps1','.bat')]
    return {p.relative_to(ROOT).as_posix():p.read_bytes() for p in paths}

def build(out, cache):
    need(os.name=='nt','Build on Windows x64 to execute the embedded runtime smoke test.')
    for name,h in CORE.items(): need(sha((ROOT/name).read_bytes())==h,'Audited core changed: '+name)
    need(not out.exists(),'Output already exists: '+str(out))
    cache.mkdir(parents=True,exist_ok=True)
    py=obtain(PYTHON,cache); wheel=obtain(LZ4,cache)
    with tempfile.TemporaryDirectory(prefix='dirt_ru_rc4_') as temp:
        stage=Path(temp)/'DIRT_5_RU_MOD'; stage.mkdir(); data=stage/'_data'; data.mkdir(); rt=data/'runtime'; rt.mkdir()
        extract(py,rt); extract(wheel,rt)
        need((rt/'LICENSE.txt').is_file(),'Python license missing')
        need(any('license' in p.name.lower() for p in (rt/'lz4-4.4.5.dist-info').rglob('*') if p.is_file()),'Wheel license missing')
        (rt/'python313._pth').write_text('python313.zip\n.\n../patcher\n',encoding='ascii')
        for folder in ('patcher','fonts','translations'):
            shutil.copytree(ROOT/folder,data/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for n in ('Install_RU.bat','Uninstall_RU.bat'): shutil.copyfile(ROOT/'installer'/n,stage/n)
        shutil.copyfile(ROOT/'installer/setup.ps1',data/'setup.ps1')
        # User-facing text in UTF-8 BOM for Notepad, omit Markdown syntax.
        (stage/'README.txt').write_text('DIRT 5 — Русификатор\n\nПолная русская текстовая локализация с оригинальной английской озвучкой.\n\nУстановка\n1. Полностью распакуйте архив. Закройте игру.\n2. Запустите Install_RU.bat.\n3. Выберите папку игры и нажмите «Установить».\nЗапускайте игру через ярлык «DIRT 5 — Русская версия».\n\nУдаление\nЗакройте игру, запустите Uninstall_RU.bat, выберите папку игры и нажмите «Удалить».\n',encoding='utf-8-sig')
        shutil.copyfile(ROOT/'THIRD_PARTY_NOTICES.md',data/'THIRD_PARTY_NOTICES.md')
        (data/'RUNTIME_PROVENANCE.txt').write_text('\n'.join(' | '.join(spec) for spec in (PYTHON,LZ4))+'\n',encoding='ascii')
        probe = ('import sys,struct,lz4,lz4.block,easy_driver; '
                 'assert sys.version_info[:3]==(3,13,17) and struct.calcsize("P")==8; '
                 'assert lz4.__version__=="4.4.5"; '
                 'a=bytes(range(256))*512; b=lz4.block.compress(a,store_size=False,mode="high_compression",compression=9); '
                 'assert lz4.block.decompress(b,uncompressed_size=len(a))==a; print("EMBEDDED RUNTIME PASS")')
        subprocess.run([str(rt/'python.exe'),'-B','-c',probe],cwd=rt,check=True)
        # Parse both PS scripts with Windows PowerShell, without running the UI.
        ps = r'''$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:DIRT_RU_SCRIPT,[ref]$tokens,[ref]$errors); if($errors.Count){$errors | Format-List; exit 1}; Write-Host 'POWERSHELL PARSE PASS' '''
        env=dict(os.environ,DIRT_RU_SCRIPT=str(data/'setup.ps1'))
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',ps],env=env,check=True)
        entries={p.relative_to(stage).as_posix():p.read_bytes() for p in stage.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        src=collect_source()
        # Ensure every audited core byte is carried through the offline package.
        for n,h in CORE.items():need(sha(entries['_data/'+n])==h,'User package changed core: '+n)
        out.mkdir(parents=True)
        user=out/f'DIRT_5_RU_MOD_{VERSION}_Windows.zip'; source=out/f'DIRT_5_RU_MOD_{VERSION}_GitHub_source.zip'
        write_zip(user,{'DIRT_5_RU_MOD/'+k:v for k,v in entries.items()})
        write_zip(source,{'DIRT_5_RU_MOD/'+k:v for k,v in src.items()})
        (out/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in (user,source)),encoding='ascii')
    print('BUILD PASS:',out)
    print('User ZIP contains official portable Python + lz4. No game files were modified.')
    print('Before publication: Windows GUI install/uninstall QA, official build compatibility and rights review.')

if __name__=='__main__':
    from datetime import datetime
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=ROOT.parent/('DIRT_RU_RC4_dist_'+datetime.now().strftime('%Y%m%d_%H%M%S')));a.add_argument('--cache',type=Path,default=ROOT.parent/'DIRT_RU_runtime_cache');args=a.parse_args();build(args.out.resolve(),args.cache.resolve())
