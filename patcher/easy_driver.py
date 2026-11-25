"""User-facing wrapper; the RC.1 installer and backup format are unchanged."""
import os, sys, traceback
from pathlib import Path
import install as core
import index_probe as P

EXPECTED_INDEX = "e967d37ef992ddbee877a63e6b23e09ea3aaa688e1ff45ae2109330c71ee3a16"
EXPECTED_TAILS = {
    "36_WIP_INIT.dat": "c7e4636b73dbb5567dfd978679e5e49d5aeb6b8c0793aa1d96d7861b4c30b6b7",
    "63_WIP_INIT.dat": "17e187b735004509e90c0d707a2a2ff2350fd99755b1b9b5dc6d7082b5672b71",
}
_original_prepare = core.prepare

def checked_prepare(root):
    plan = _original_prepare(root)
    _, _, index, exe, tails, _ = plan
    P.require(P.sha(index) == EXPECTED_INDEX and P.sha(exe) == core.PATCH_SHA,
              "Release output index/EXE differs from tested build; game not modified")
    P.require({k:P.sha(v) for k,v in tails.items()} == EXPECTED_TAILS,
              "Release output DAT tails differ from tested build; game not modified")
    return plan

# Read-only status: never acquire the write lock or create game files.
def status(path):
    root = core.locate(Path(path))
    ix, ex, bak = core.paths(root)
    i, e = ix.read_bytes(), ex.read_bytes()
    ih, eh = P.sha(i), P.sha(e)
    original = ih == P.INDEX_SHA and eh == P.EXE_SHA
    installed = ih == EXPECTED_INDEX and eh == core.PATCH_SHA
    if not bak.exists():
        if original:
            core.original_sizes(root)
            P.require(not bak.with_suffix('.creating.zip').exists(), 'Incomplete backup staging exists')
            return 'VANILLA'
        return 'BLOCKED'
    # The backup is retained on uninstall. Its presence alone is not a status.
    oi, oe, pi, pe, tails, manifest = core.load_backup(root)
    P.require(P.sha(pi) == EXPECTED_INDEX and P.sha(pe) == core.PATCH_SHA,
              'Backup does not match tested release')
    P.require({k:P.sha(v) for k,v in tails.items()} == EXPECTED_TAILS,
              'Backup tails do not match tested release')
    P.require(manifest['payload'] == P.sha(core.fonts.PAYLOAD.read_bytes()),
              'Backup font payload differs')
    if i not in (oi, pi) or e not in (oe, pe):
        return 'BLOCKED'
    core.check_tails(root, tails)
    if original and all((root/'dat'/n).stat().st_size == size for n,size in P.SIZES.items()):
        return 'VANILLA'
    if installed:
        # A truncated but valid append is recoverable, not a complete install.
        if any((root/'dat'/n).stat().st_size != P.SIZES[n]+len(t) for n,t in tails.items()):
            return 'RECOVERABLE'
        core.verify(root)
        return 'INSTALLED'
    return 'RECOVERABLE'


def run(action, path):
    if action == 'status':
        print('STATE:', status(path))
        return
    root = core.locate(Path(path))
    if action not in ("install", "uninstall"):
        raise ValueError("Unknown setup action")
    P.closed()
    core.prepare = checked_prepare
    try:
        with core.lock(root):
            if action == "install":
                core.apply(root)
                core.verify(root)
            else:
                core.restore(root)
    finally:
        core.prepare = _original_prepare

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        run(os.environ["DIRT_RU_ACTION"], os.environ["DIRT_RU_GAME"])
    except Exception as exc:
        traceback.print_exc()
        print("ERROR:", str(exc), file=sys.stderr)
        sys.exit(1)
