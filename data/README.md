# ROMs

Place the ROM files for Pac-Man and/or Ms. Pac-Man (Midway) directly in this folder, then pick the
game with `--rom-set`:

```sh
python main.py --rom-set pacman      # Pac-Man (the default)
python main.py --rom-set mspacman    # Ms. Pac-Man
```

The ROMs are not included: you must legally own them. They are the files of MAME's `pacman` and
`mspacman` sets. Both games can share this folder: the files they have in common are identical,
and their tiles/sprites have different names (`pacman.5e`/`pacman.5f` against `5e`/`5f`).
The CRC32 of every file is checked on load (`--skip-checksums` turns mismatches into warnings).

| File | Size | CRC32 | Contents | Pac-Man | Ms. Pac-Man |
|---|---|---|---|:---:|:---:|
| `pacman.6e` | 4096 | `C1E6AB10` | Code 1 | ✓ | ✓ |
| `pacman.6f` | 4096 | `1A6FB2D4` | Code 2 | ✓ | ✓ |
| `pacman.6h` | 4096 | `BCDD1BEB` | Code 3 | ✓ | ✓ |
| `pacman.6j` | 4096 | `817D94E3` | Code 4 | ✓ | ✓ |
| `82s123.7f` | 32 | `2FC650BD` | Colour PROM | ✓ | ✓ |
| `82s126.4a` | 256 | `3EB3A8E4` | Palette PROM | ✓ | ✓ |
| `82s126.1m` | 256 | `A9CC86BF` | Sound PROM 1 | ✓ | ✓ |
| `82s126.3m` | 256 | `77245B66` | Sound PROM 2 | ✓ | ✓ |
| `pacman.5e` | 4096 | `0C944964` | Pac-Man tiles | ✓ | |
| `pacman.5f` | 4096 | `958FEDF9` | Pac-Man sprites | ✓ | |
| `5e` | 4096 | `5C281D01` | Ms. Pac-Man tiles | | ✓ |
| `5f` | 4096 | `615AF909` | Ms. Pac-Man sprites | | ✓ |
| `u5` | 2048 | `F45FBBCD` | Aux board ROM (encrypted) | | ✓ |
| `u6` | 4096 | `A90E7000` | Aux board ROM (encrypted) | | ✓ |
| `u7` | 4096 | `C82CD714` | Aux board ROM (encrypted) | | ✓ |
