#!/usr/bin/env bash
# Build the HUD optimization paks from your own copy of Beyond Citadel.
# usage: ./build.sh "<game dir>" [install]
set -euo pipefail
GAME="${1:?usage: ./build.sh \"<path to Beyond Citadel>\" [install]}"
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$HERE/tools"
WORK="$HERE/work"
PAK="$GAME/beyond_citadel/Content/Paks/beyond_citadel-WindowsNoEditor.pak"

rm -rf "$WORK"; mkdir -p "$WORK"
python3 "$T/pakget.py" "$PAK" "$WORK/src" /wid_ /How_to
python3 "$T/build_hudopt.py" "$WORK/src" "$WORK/build" "$WORK/build/all_P.pak" > "$WORK/build.log"
grep TOTAL "$WORK/build.log"

# split: gameplay HUD vs menus
cd "$WORK/build"; rm -rf HUD MENU; mkdir -p HUD MENU
(cd PATCH && find . -type f) | while read -r f; do
  case "$(basename "$f")" in
    wid_hud_*|wid_ammo_hud*|wid_scope_*|wid_objective*|wid_door_key_indicator*|wid_lowammo*|\
    wid_noammo*|wid_lifebar_boss*|wid_decoder*|wid_supplies*|wid_stagename*|wid_helm*|wid_largemap*) d=HUD;;
    *) d=MENU;;
  esac
  mkdir -p "$d/$(dirname "$f")"; cp "PATCH/$f" "$d/$f"
done
mkdir -p "$HERE/out"
python3 "$T/mkpak.py" HUD  "$HERE/out/zz_hudopt_hud_P.pak"
python3 "$T/mkpak.py" MENU "$HERE/out/zz_hudopt_menus_P.pak"

if [ "${2:-}" = install ]; then
  cp "$HERE"/out/zz_hudopt_*_P.pak "$GAME/beyond_citadel/Content/Paks/"
  echo "installed into $GAME/beyond_citadel/Content/Paks/"
fi
