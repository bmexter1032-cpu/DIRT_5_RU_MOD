# Compatibility

Verified prototype on the PC build under test (MicrosoftGame.config package version 1.2770.47.0; prior source labels game build 1.0.14616.537, relationship not independently verified). Hashes are authoritative, not edition labels.

| Original | SHA-256 / bytes |
|---|---|
| game_release.exe | `32d0b080f7e7d1d3d0057815342ddb9b232cc5f629a22b5e2e9318c3e4775efe` |
| dat/index/dat.ndx | `275485d8e0125b07749f52c332f5989fcedb1177cea43bd1ae043909d3adf7bd` |
| dat/36_WIP_INIT.dat | 2093510689 |
| dat/63_WIP_INIT.dat | 1409400101 |
| Xbox BRA LOC | `38cf63c58a5c9ff3d46029aaff559cc80a60539b2d441aa2b1992608471104a2` |

Patched selector SHA-256 `26252a366b5449bdbddb9284038ce2a5f7f5c7bfd4729463d1690fef6137049e`. RUS LOC `544f4791c80159340eee3e2d74da517f99660ed556f179807182f3e3ac96fcc3`. The font manifest additionally checks all 32 original and patched resource hashes. Entire multigigabyte DAT files are not hashed. No compatibility claims for other EXEs or indexes; never bypass checks. Original-language rendering was reported satisfactory for tested screens, but fonts are still shared. Other editions, online mode and mods are unverified. Game updates may invalidate the patch: stop, verify the exact build, do not force rollback over foreign files.
