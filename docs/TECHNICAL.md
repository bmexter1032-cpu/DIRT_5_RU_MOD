# Architecture and rollback

Text compiler: uses the original Xbox BRA header and key order; v3.2 Russian-only CSV and fixed compact codebook reproduce exactly the previous LOC, then change language identifiers and both FNV-1a hashes to RUS. Translation is not regenerated or edited. The full original-language text is not included.

Archive overlay: resource rows and chunk geometry are checked against the known original index. New `xbox/rus.loc` row and three blocks; per-font XOR deltas reconstruct original-size FNT/GTX resources from installed originals. Only modified chunks are appended to DAT 36/63; original bytes remain. All original localization/audio chunk descriptors are checked. Font deltas are generated from the verified installed v10.1, not guessed from screenshots. The exporter verifies every changed decompressed block equals the legacy installed block, including surrounding bytes. LZ4 compressed bytes/index offsets may vary by library version; decompressed resources must match.

Selector: original nine-language validation is preserved. Exact `rus` returns RUS at the text call site (return RVA 0x42c23b), ENG elsewhere. Same known selector patch as v10.1: loop RVA 0x0f4c14, helper RVA 0xc44770, existing PE padding, RIP-relative references. EXE changes applied locally; no GDK config or Wwise changes. Shared fonts use compact aliases; a separate full glyph isolation was not implemented.

Transaction: check all inputs, build in memory, write verified local backup ZIP of original/patched index and EXE, appended bytes and hashes before any game writes. Append DAT, atomically replace NDX/EXE, verify each installed resource. On failure attempt rollback only for recognizable state. Recovery after interruption uses restore, including a prefix of planned tails. Unrecognized changes are refused. Persistent lock file prevents concurrent patcher writers; close game and avoid launch/update/modding concurrently. No protection against a different program ignoring this lock. Do not upload local backups.

Maintainer: generate `fonts/font_deltas.zip` using `tools/export_fonts.py GAME_DIR OUTPUT` from active v10.1 and its v10 backup. Then run `tools/package_release.py OUTPUT_DIR` from source checkout. Tests and export tool included in source package, not needed at runtime. GitHub source ZIP is intended for extraction and commit, not automatic publication.

Release packaging revision RC.2 intentionally retains the internal backup manifest version `1.0.0-rc.1` to preserve existing RC.1 backup compatibility. Runtime code and payload are unchanged.
