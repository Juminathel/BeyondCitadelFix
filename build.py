#!/usr/bin/env python3
"""Build (and optionally install) the HUD optimization paks. Works on Windows, Linux, Steam Deck.

usage:  python build.py "<path to Beyond Citadel>" [install]
        python build.py            (tries the default Steam locations)
"""
import os, sys, shutil, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, 'tools')
sys.path.insert(0, TOOLS)

GAMEPLAY = ('wid_hud_', 'wid_ammo_hud', 'wid_scope_', 'wid_objective', 'wid_door_key_indicator',
            'wid_lowammo', 'wid_noammo', 'wid_lifebar_boss', 'wid_decoder', 'wid_supplies',
            'wid_stagename', 'wid_helm', 'wid_largemap')
PAK_REL = os.path.join('beyond_citadel', 'Content', 'Paks')
MAIN_PAK = 'beyond_citadel-WindowsNoEditor.pak'

def default_game_dirs():
    home = os.path.expanduser('~')
    return [
        r'C:\Program Files (x86)\Steam\steamapps\common\Beyond Citadel',
        r'C:\Program Files\Steam\steamapps\common\Beyond Citadel',
        os.path.join(home, '.local/share/Steam/steamapps/common/Beyond Citadel'),
        os.path.join(home, '.steam/steam/steamapps/common/Beyond Citadel'),
        os.path.join(home, '.steam/debian-installation/steamapps/common/Beyond Citadel'),
    ]

def run(*args):
    subprocess.check_call([sys.executable] + list(args))

def main():
    args = [a for a in sys.argv[1:] if a != 'install']
    install = 'install' in sys.argv[1:]
    if args:
        game = args[0]
    else:
        game = next((d for d in default_game_dirs()
                     if os.path.isfile(os.path.join(d, PAK_REL, MAIN_PAK))), None)
        if not game:
            sys.exit('Game folder not found. Run: python build.py "<path to Beyond Citadel>" install')
    pak = os.path.join(game, PAK_REL, MAIN_PAK)
    if not os.path.isfile(pak):
        sys.exit('Not found: ' + pak)
    print('Game:', game)

    work = os.path.join(HERE, 'work'); out = os.path.join(HERE, 'out')
    shutil.rmtree(work, ignore_errors=True); os.makedirs(out, exist_ok=True)
    src = os.path.join(work, 'src'); build = os.path.join(work, 'build')
    run(os.path.join(TOOLS, 'pakget.py'), pak, src, '/wid_', '/How_to')
    run(os.path.join(TOOLS, 'build_hudopt.py'), src, build, os.path.join(build, 'all_P.pak'))

    patch = os.path.join(build, 'PATCH')
    for root, _, files in os.walk(patch):
        for f in files:
            group = 'HUD' if f.startswith(GAMEPLAY) else 'MENU'
            rel = os.path.relpath(os.path.join(root, f), patch)
            dst = os.path.join(build, group, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, f), dst)
    hud = os.path.join(out, 'zz_hudopt_hud_P.pak'); menus = os.path.join(out, 'zz_hudopt_menus_P.pak')
    run(os.path.join(TOOLS, 'mkpak.py'), os.path.join(build, 'HUD'), hud)
    run(os.path.join(TOOLS, 'mkpak.py'), os.path.join(build, 'MENU'), menus)

    if install:
        for f in (hud, menus):
            shutil.copy2(f, os.path.join(game, PAK_REL))
        print('Installed into', os.path.join(game, PAK_REL))
    else:
        print('Done. Copy the two files from', out, 'into', os.path.join(game, PAK_REL))

if __name__ == '__main__':
    main()
