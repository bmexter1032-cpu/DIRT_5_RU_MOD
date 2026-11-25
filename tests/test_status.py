"""Exercise the RC.4 state machine with small files; never touch the game."""
import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'patcher'))
import easy_driver as E

class StatusTest(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.ix,self.ex,self.bak=E.core.paths(self.root)
        self.ix.parent.mkdir(parents=True);self.bak.parent.mkdir()
        self.oi,self.oe,self.pi,self.pe=b'original index',b'original exe',b'patched index',b'patched exe'
        self.tails={'36_WIP_INIT.dat':b'font tail','63_WIP_INIT.dat':b'loc tail'}
        self.sizes={n:8 for n in self.tails}
        self.manifest={'payload':E.P.sha(E.core.fonts.PAYLOAD.read_bytes())}
        for obj,name,value in [(E.P,'INDEX_SHA',E.P.sha(self.oi)),(E.P,'EXE_SHA',E.P.sha(self.oe)),(E,'EXPECTED_INDEX',E.P.sha(self.pi)),(E.core,'PATCH_SHA',E.P.sha(self.pe)),(E.P,'SIZES',self.sizes),(E,'EXPECTED_TAILS',{n:E.P.sha(t) for n,t in self.tails.items()})]:
            self.stack.enter_context(patch.object(obj,name,value))
        self.loader=self.stack.enter_context(patch.object(E.core,'load_backup',return_value=(self.oi,self.oe,self.pi,self.pe,self.tails,self.manifest)))
        self.verify=self.stack.enter_context(patch.object(E.core,'verify'))
        self.set_files(self.oi,self.oe,False)
    def set_files(self,i,e,full):
        self.ix.write_bytes(i);self.ex.write_bytes(e)
        for n,t in self.tails.items(): (self.root/'dat'/n).write_bytes(b'0'*8+(t if full else b''))
    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def expect(self,value):
        before=self.snapshot();self.assertEqual(E.status(self.root),value);self.assertEqual(before,self.snapshot())
    def test_fresh(self): self.expect('VANILLA');self.loader.assert_not_called()
    def test_restored_backup_retained(self): self.bak.touch();self.expect('VANILLA');self.verify.assert_not_called()
    def test_installed(self): self.bak.touch();self.set_files(self.pi,self.pe,True);self.expect('INSTALLED');self.verify.assert_called_once_with(self.root)
    def test_missing_backup(self): self.set_files(self.pi,self.pe,True);self.expect('BLOCKED')
    def test_partial_append(self):
        self.bak.touch();self.set_files(self.oi,self.oe,False)
        with (self.root/'dat'/'36_WIP_INIT.dat').open('ab') as f:f.write(self.tails['36_WIP_INIT.dat'][:3])
        self.expect('RECOVERABLE')
    def test_patched_but_truncated(self): self.bak.touch();self.set_files(self.pi,self.pe,False);self.expect('RECOVERABLE');self.verify.assert_not_called()
    def test_mixed_index_exe(self): self.bak.touch();self.set_files(self.pi,self.oe,True);self.expect('RECOVERABLE')
    def test_foreign(self): self.bak.touch();self.ex.write_bytes(b'unknown');self.expect('BLOCKED')
    def test_bad_tail(self):
        self.bak.touch();self.set_files(self.pi,self.pe,True)
        (self.root/'dat'/'36_WIP_INIT.dat').write_bytes(b'0'*8+b'x')
        before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Foreign DAT tail'):E.status(self.root)
        self.assertEqual(before,self.snapshot())
    def test_backup_corrupt(self):
        self.bak.touch();self.loader.side_effect=RuntimeError('bad backup')
        with self.assertRaisesRegex(RuntimeError,'bad backup'):E.status(self.root)
    def test_pending_backup(self):
        self.bak.with_suffix('.creating.zip').touch()
        with self.assertRaisesRegex(RuntimeError,'Incomplete backup'):E.status(self.root)
if __name__=='__main__':unittest.main()
