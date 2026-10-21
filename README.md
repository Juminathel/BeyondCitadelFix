# BeyondCitadelFix

**English** | [Русский](README.ru.md)

HUD/UI performance fix for **Beyond Citadel** (UE 4.25): removes the lag that starts when you put the helmet on.
Result on PC: **40–60 unstable FPS → 120 FPS**. Main goal: a stable 60 FPS on Steam Deck.

## Download

**[Latest release](https://github.com/Juminathel/BeyondCitadelFix/releases/latest)**: two files,
`zz_hudopt_hud_P.pak` and `zz_hudopt_menus_P.pak`.

Built for **game version 1.0**. If the game gets updated, remove the patch (or rebuild it, see below).

## Installation

Put **both** `.pak` files into the game's `beyond_citadel/Content/Paks/` folder:

| platform | path |
|---|---|
| Windows | `C:\Program Files (x86)\Steam\steamapps\common\Beyond Citadel\beyond_citadel\Content\Paks\` |
| Steam Deck | `/home/deck/.local/share/Steam/steamapps/common/Beyond Citadel/beyond_citadel/Content/Paks/` |

If your Steam library is on another drive: Steam → right-click the game → Manage → Browse local files.

> ⚠️ **Do not delete or replace** the original `beyond_citadel-WindowsNoEditor.pak` in the same folder.
> It is the whole game; without it the game will not start.

**Uninstall:** delete only `zz_hudopt_hud_P.pak` and `zz_hudopt_menus_P.pak`.

**If the game crashes:** remove `zz_hudopt_menus_P.pak` first; if that doesn't help, remove `zz_hudopt_hud_P.pak` too.
If something breaks, please open an issue.

## What was wrong

UMG widget binding functions (the engine calls them every frame) call `LoadGameFromSlot`: they read and
deserialize a save file from disk **every frame, for every element**.
In the main HUD (`wid_hud_minimap_dual`) 29 elements did this (42 load sites); menus and shops had up to 268.
With the helmet on, many elements are visible → thousands of save reads per second,
FPS drops and garbage-collection stutter. Steam Deck is hit hardest (Proton, weaker CPU).

## What the patch does

The patch edits the compiled Kismet bytecode inside the cooked assets (no project source is needed):

1. **Save cache.** `LoadGameFromSlot` in read-only functions is replaced with a cache stored in the widget
   itself (reloaded at most every 0.5 s for the gameplay HUD, 0.15 s for menus). Functions that write
   to the save or save it are left untouched.
2. **Binding throttle** (gameplay HUD only). Heavy bindings are recomputed every 40–80 ms
   (different periods per binding, so there are no synchronized spikes); other frames return the cached value.
   Every element keeps updating; nothing is frozen.

Total: 252 widgets, 4219 save loads replaced, 378 bindings throttled.

## Building from source

Only Python 3 is needed (Windows, Linux, Steam Deck). The patch is built from your own copy of the game:

```bash
python build.py "<path to Beyond Citadel>" install
```

Without a path, the script looks for the game in the default Steam folders. Without `install` it only builds
the files into `out/`. On Linux you can also run `./build.sh "<path>" install`.

## Tools (`tools/`)

| file | purpose |
|---|---|
| `pakget.py` | extract files from a v9 pak |
| `mkpak.py` | build a v9 pak (mount `../../../`) |
| `pkgedit.py` | edit .uasset/.uexp: names, imports, offset fix-ups |
| `namehash.py` | FName hashes for the name map |
| `ustruct.py` | parse UStruct/UFunction exports and FField properties |
| `kismet.py` | UE4.25 Kismet bytecode disassembler/assembler (in-memory offsets) |
| `disasm.py` | print a function's bytecode: `python3 disasm.py <base> <func>` |
| `reach.py` | which `LoadGameFromSlot` calls are reachable from an event (Tick, hit, …) |
| `hudopt.py` | the optimizer itself (save cache + throttle) |
| `verify.py` | structural package check (jumps, property references, sizes) |
| `build_hudopt.py` | runs the optimizer over every widget with bindings |
| `bindings.py`, `uasset.py`, `exports.py` | parsing helpers |

The parser is tested on all 15,386 functions in the game (parse → rebuild is byte-identical); the package
editor on 863 Blueprint packages.

## Known limitations / next steps

- The player character (`BP_hero`) is nativized into C++ (inside the `.exe`); these tools can't edit it.
- Enemies call `LoadGameFromSlot` only on hits and deaths, not in Tick or in frequent timers:
  5–36 call sites per event. Not patched yet: death logic writes to the save (stats, quests),
  so caching there is risky.
