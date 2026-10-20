# Build the HUD optimization patch pak from an extracted content tree.
# usage: python3 build_hudopt.py <extracted_root> <work_dir> <out.pak>
import sys, os, glob, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hudopt
from verify import verify
from bindings import find_bindings

# widgets shown during gameplay: throttle bindings + long save cache
GAMEPLAY = ('wid_hud_', 'wid_ammo_hud', 'wid_scope_', 'wid_objective', 'wid_door_key_indicator',
            'wid_lowammo', 'wid_noammo', 'wid_lifebar_boss', 'wid_decoder', 'wid_supplies',
            'wid_stagename', 'wid_helm', 'wid_largemap')

src, work, out = sys.argv[1:4]
patch = os.path.join(work, 'PATCH')
shutil.rmtree(patch, ignore_errors=True)
total = dict(save=0, throttled=0, files=0)
for ua in sorted(glob.glob(src + '/**/*.uasset', recursive=True)):
    base = ua[:-7]; rel = os.path.relpath(base, src); name = os.path.basename(base)
    if not name.startswith(('wid_', 'How_to')): continue
    try:
        if not find_bindings(base)[3]: continue
    except Exception:
        continue
    game = name.startswith(GAMEPLAY)
    hudopt.SAVE_TTL = 0.5 if game else 0.15
    dst = os.path.join(patch, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        st = hudopt.optimize(base, dst, throttle=game, log=lambda *a: None)
    except Exception as ex:
        print('SKIP', rel, repr(ex)); continue
    if not (st['save'] or st['throttled']):
        os.remove(dst + '.uasset'); os.remove(dst + '.uexp'); continue
    n, errs = verify(dst)
    if errs:
        print('FAIL verify', rel, errs[:3])
        os.remove(dst + '.uasset'); os.remove(dst + '.uexp'); continue
    total['save'] += st['save']; total['throttled'] += st['throttled']; total['files'] += 1
    print('%-60s save=%-3d throttled=%-3d props=%d' % (rel, st['save'], st['throttled'], st['props']))
print('TOTAL', total)
subprocess.check_call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mkpak.py'),
                       patch, out])
