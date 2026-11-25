# Changelog

## 1.0.0-rc.4 — Installer state

- Read-only status check at opening and after changing the game folder.
- Disable repeated installation and removal; separate shortcut creation.
- Detect recoverable interrupted installations; refuse unknown files.
- Core, payload and runtime versions unchanged.
- RC.3 GUI installation, repeated installation and removal including shortcut cleanup reported successful. RC.4 GUI QA pending.

## 1.0.0-rc.3 — Easy Install

- Windows Forms folder picker and automatic desktop shortcut.
- Offline portable Python 3.13.17 and lz4 4.4.5 in user ZIP; no system Python required.
- Exact verified RC.1 binary output checks, no changes to translation, font payload, selector or backup format.
- GUI and embedded runtime still require Windows acceptance test.


## 1.0.0-rc.2 (documentation and packaging)

- Updated Russian and English instructions, QA record and publication notes.
- No changes to installer, selector, translation, codebook, font payload or BAT files.
- Backup format retains internal version `1.0.0-rc.1` for compatibility with existing installations.
- Official-copy QA and rights review remain pending.

## 1.0.0-rc.1 (release engineering)

- Combined pristine-game installation and rollback, based on v10.1 selector and v10 overlays.
- Compiles the exact v3.2 translation from Russian-only CSV and local BRA template; no distributed original LOC.
- Font XOR deltas derived from the tested v10.1 installation; checked against all 32 resources and changed decompressed blocks.
- BAT entry points, optional native Windows shortcut, no custom EXE.
- Clean install, verification, restore, reinstall and RUS launch passed on one Windows test build. One startup crash was not reproduced; cause unknown. Public release pending official-copy QA and rights review.

## v10.1
Conditional `-language rus` selector, English voices, original language selection preserved; reported successful game test.

## v10
Separate RUS resource with full translation and v9.2 fonts; successful game test with English voices.

## v9.2
Full text and compact glyph system, livery wording and uppercase Ж fixes. Earlier BRA substitution retired.
