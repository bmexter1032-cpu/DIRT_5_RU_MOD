# Release gate

Historical game reports: v10 independent Russian text + English speech; v10.1 RUS/ENG/BRA switching worked; font compatibility reported satisfactory. These are prototype reports, not a clean-install test of this RC. Offline selector harness compares original versus modified code; the RC must separately pass its clean-install path.

Before publishing:

1. Export real font payload from active v10.1; expect EXPORT PASS and SHA256.
2. Restore v10.1 EXE to v10 with old upgrade.py restore, then restore v10 to pristine with old native_ru.py restore. Keep backups. Do not run the new uninstaller on the legacy install.
3. Run Check/Install/Verify from the completed user ZIP on the restored game. Check RUS menu, subtitles, English speech, small fonts, livery label and Ж; launch ENG and BRA and check rendering/voices. Test other original codes where possible. Verify ordinary launch without arguments.
4. Test uninstall, compare original EXE/index hashes and original sizes; reinstall from same package; check foreign input refusal. Check shortcut.
5. Test a clean official supported copy and record exact hashes. Review redistribution rights and font provenance, choose code license, scan final archives, publish signed/hashed assets. Do not claim Steam or online support without evidence.

## Local engineering tests completed for this template

- Compiled the actual BRA from four real original LZ4 chunks: RUS LOC SHA-256 matched the proven v10.1 resource exactly.
- Built the actual original EXE into the exact known v10.1 hash. Linux x86-64 harness: 180 selector calls including all nine languages, invalid/missing arguments and RUS, compared against vanilla at a relocated image base (locale/IAT mocked).
- `tests/test_fixture.py`: used the real index, EXE, BRA chunks and all 32 actual original font resources from the private handoff. Surrounding font chunks synthesized, one-byte font changes synthesized. Verified overlay merge, exporter, RC apply, verify, idempotence, restore, partial append recovery, automatic rollback on injected post-check failure and refusal of a foreign EXE. The synthetic payload was temporary and is not distributed. This is not a test of the actual v9.2 font payload, Windows shortcuts or game loading of RC.

## RC.1 acceptance record — 2026-11-25

- Maintainer reported the real font export, 32 exact resources; payload SHA-256 `48ef88ee8aea8a82626a7f0fc6442b9b20c99411d191ae32992b572957c32023`.
- Both distributed ZIPs passed SHA-256 and CRC validation in an independent audit. All shared files byte-identical; 6,473 unique nonempty translation records. All 32 original font files from the private handoff were independently XOR-patched and matched the manifest output hashes. The real local BRA template compiled to the expected RUS hash, and the local original EXE produced the expected v10.1 selector hash.
- Windows clean install via Python CLI: check/apply/verify succeeded. The first launch crashed after logos before the disclaimer. Backup comparison showed identical original EXE/index, patched index and both DAT tails; selector hash also identical to v10.1. A second launch without modifications worked and returned exit code 0. No crash cause was established.
- Maintainer reported successful restore, check, reinstall, verify, shortcut creation command and RUS launch. Original-language switching and font rendering were previously tested on v10.1, not exhaustively retested for all codes on RC.
- Pending: actual BAT entry-point and shortcut-click test on a legitimate official copy, no-argument and language-switching regression tests, repeated startup tests, permissions and font provenance. Keep private until these gates are resolved.

## RC.2 packaging record

RC.2 is a documentation-only release revision. Runtime code, BAT entry points, translation, codebook and font payload are byte-for-byte identical to RC.1. The prior game tests refer to RC.1; RC.2 was not launched independently on Windows. All outstanding official-copy, BAT/shortcut and distribution gates remain.

## RC.3 and RC.4

RC.3: maintainer reported successful portable runtime build, GUI install twice, GUI uninstall and desktop shortcut removal. RC.4 adds read-only state detection and disables redundant actions. Windows UI regression and official-copy QA pending.
