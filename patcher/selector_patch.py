"""v10.1 conditional selector for the one verified PE build; no external executable."""
import hashlib, struct
from index_probe import EXE_SHA, EXE_OFFSET, OLD, NEW, require

V10_SHA = '7b1fb25bc32c1e8a0f80f35a80c2ba8822593b9f835f5667cedff551ab657f26'
BASE = 0x140000000
LOOP_RVA = 0x0f4c14
LOOP_OFF = 0x0f4014
LOOP_OLD = bytes.fromhex('4c8d3d45dbd9000f1f4400004a8b143e488bcde844f2feff85c0400fb6ff410f44fc4883c6084883fe4872e0')
HELPER_RVA = 0xc44770
HELPER_OFF = 0xc43b70
TEXT_VSIZE_OFF = 0x2b0
TEXT_VSIZE_OLD = 0xc4376e
# Generated from selector.s: GNU as --64; ld -Ttext=0x140c44770
# --defsym text_return=0x14042c23b --defsym language_table=0x140e92760
HELPER = bytes.fromhex('4885c9745b803972752680790175752080790273751a807903007514488d05a87a7eff4839c2743b488b05c1df2400c34c8d05b9df240041b9090000004d8b104989cb418a03413a02750c84c0741449ffc349ffc2ebec4983c00841ffc975dd31c0c34889c8c3')

def sha(b): return hashlib.sha256(b).hexdigest()

def build(original):
    require(sha(original) == EXE_SHA, 'Unsupported original EXE')
    require(original[EXE_OFFSET:EXE_OFFSET+len(OLD)] == OLD, 'Original text call signature mismatch')
    require(original[LOOP_OFF:LOOP_OFF+len(LOOP_OLD)] == LOOP_OLD, 'Selector loop signature mismatch')
    require(struct.unpack_from('<I', original, TEXT_VSIZE_OFF)[0] == TEXT_VSIZE_OLD, 'Unexpected .text size')
    require(original[HELPER_OFF:0xc43c00] == bytes(0xc43c00-HELPER_OFF), 'Nonzero PE padding')
    require(HELPER_OFF+len(HELPER) <= 0xc43c00, 'Helper exceeds existing raw .text')
    # Caller frame and unwind data remain exactly as in vanilla. Replace only loop after all saves.
    # RCX = raw command argument; RDX = return address of shared selector's caller.
    # Helper returns accepted string pointer (or zero); original selector continues its normal copy/fallback.
    code = bytes.fromhex('488bcd488b9424c8000000')
    code += b'\xe8' + struct.pack('<i', HELPER_RVA - (LOOP_RVA+len(code)+5))
    code += bytes.fromhex('48894424204885c0400f95c7')
    require(len(code)<=len(LOOP_OLD), 'Loop replacement exceeds range')
    code = code.ljust(len(LOOP_OLD), b'\x90')
    out=bytearray(original)
    out[LOOP_OFF:LOOP_OFF+len(code)] = code
    out[HELPER_OFF:HELPER_OFF+len(HELPER)] = HELPER
    struct.pack_into('<I', out, TEXT_VSIZE_OFF, HELPER_RVA+len(HELPER)-0x1000)
    require(len(out)==len(original), 'Unexpected EXE size change')
    return bytes(out)
