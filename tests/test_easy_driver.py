"""Check RC.3 wrapper guards without touching any game files."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'patcher'))
import easy_driver as E
class TestEasyDriver(unittest.TestCase):
    def test_exact_plan(self):
        index=b'index'; exe=b'exe'; tails={'36_WIP_INIT.dat':b'36','63_WIP_INIT.dat':b'63'}
        plan=(b'old',b'old exe',index,exe,tails,{})
        with patch.object(E,'_original_prepare',return_value=plan),patch.object(E,'EXPECTED_INDEX',E.P.sha(index)),patch.object(E.core,'PATCH_SHA',E.P.sha(exe)),patch.object(E,'EXPECTED_TAILS',{n:E.P.sha(v) for n,v in tails.items()}):
            self.assertIs(E.checked_prepare(None),plan)
    def test_wrong_index_rejected(self):
        with patch.object(E,'_original_prepare',return_value=(b'',b'',b'wrong',b'',{},{})):
            with self.assertRaisesRegex(RuntimeError,'index/EXE differs'): E.checked_prepare(None)
    def test_wrong_tail_rejected(self):
        index=b'index'; exe=b'exe'; plan=(b'',b'',index,exe,{'36_WIP_INIT.dat':b'wrong'}, {})
        with patch.object(E,'_original_prepare',return_value=plan),patch.object(E,'EXPECTED_INDEX',E.P.sha(index)),patch.object(E.core,'PATCH_SHA',E.P.sha(exe)):
            with self.assertRaisesRegex(RuntimeError,'DAT tails differ'): E.checked_prepare(None)
if __name__=='__main__': unittest.main()
