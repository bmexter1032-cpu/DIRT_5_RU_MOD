"""Compile only our Russian text against locally installed, hash-checked BRA template."""
import csv,json,struct
from pathlib import Path
import index_probe as P
ROOT=Path(__file__).resolve().parent.parent
CSV_SHA='23cc8160b8793fbe9dc181f6bd82429a1f080d5cdd0cb88b66b9df3ae8e25102'
BOOK_SHA='cbdb9c741bac343cc0e4e394fb4df2cbb36d786dcc55479e6af4e2f3aaaed2fb'
LOC_SHA='544f4791c80159340eee3e2d74da517f99660ed556f179807182f3e3ac96fcc3'
BRA_RU_SHA='ff858dcf58fb9275064832b9cd03725c9b7a67dcc0b044b733337204833b2a42'

def compile_loc(bra):
    P.require(P.sha(bra)==P.BRA_SHA and len(bra)==291673,'Original Xbox BRA mismatch')
    csvpath=ROOT/'translations/ru.csv';bookpath=ROOT/'translations/codebook.json'
    P.require(P.sha(csvpath.read_bytes())==CSV_SHA and P.sha(bookpath.read_bytes())==BOOK_SHA,'Translation or codebook hash mismatch')
    book=json.loads(bookpath.read_text('utf-8'))
    mapping={c:bytes([int(k,16)]) for k,c in book['assigned_cyrillic_controls'].items()}
    mapping.update({c:v.encode('ascii') for key in ('latin_visual_equivalents','punctuation_reassignments') for c,v in book[key].items()})
    def encode(s):return b''.join(mapping.get(c,c.encode('utf8')) for c in s)
    with csvpath.open(encoding='utf8',newline='') as f:
        reader=csv.DictReader(f);P.require(reader.fieldnames==['Hash64','Russian'],'CSV structure mismatch');rows=list(reader)
    data={int(r['Hash64'],16):encode(r['Russian']) for r in rows}
    P.require(len(rows)==len(data)==6473,'Expected 6473 unique Russian strings')
    out=bytearray(bra[:0xc7]);pos=0xc7;seen=set()
    for _ in range(6473):
        key,n=struct.unpack_from('<QI',bra,pos);pos+=12+n
        P.require(key in data and key not in seen and pos<=len(bra),'Unexpected original LOC entry');seen.add(key)
        value=data[key];out.extend(struct.pack('<QI',key,len(value)));out.extend(value)
    P.require(pos==len(bra) and seen==set(data),'LOC key coverage mismatch')
    P.require(len(out)==284931 and P.sha(out)==BRA_RU_SHA,'Compiled LOC differs from proven v9.2')
    for off in (0x9b,0xc0):P.require(out[off:off+3]==b'bra','Wrong language header');out[off:off+3]=b'rus'
    for off in (0xa6,0xb2):
        P.require(struct.unpack_from('<Q',out,off)[0]==P.fnv('strings_xbox_bra'),'Wrong language hash');struct.pack_into('<Q',out,off,P.fnv('strings_xbox_rus'))
    P.require(P.sha(out)==LOC_SHA,'Compiled RUS differs from proven v10.1');return bytes(out)
