# Structural verification of a (patched) widget package.
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkgedit import Package
from ustruct import parse_struct
import kismet

def verify(base):
    p = Package(base); errs = []
    exp_props = {}
    for i, e in enumerate(p.exports):
        cn = p.class_name(e['cls'])
        if cn in ('Function', 'WidgetBlueprintGeneratedClass', 'BlueprintGeneratedClass'):
            s = parse_struct(p, e['blob'])
            exp_props[i + 1] = set(f['name_idx'] for f in s['props'])
            if cn == 'WidgetBlueprintGeneratedClass': cls_idx = i + 1
    nfun = 0
    for i, e in enumerate(p.exports):
        if p.class_name(e['cls']) != 'Function': continue
        s = parse_struct(p, e['blob']); nfun += 1
        assert s['tail_off'] + 12 <= len(e['blob']), e['name']
        try: st, mem = kismet.parse_script(s['script'])
        except Exception as ex: errs.append((e['name'], 'parse', repr(ex))); continue
        if mem != s['bc_mem']: errs.append((e['name'], 'mem', mem, s['bc_mem']))
        b, m = kismet.emit_script(st)
        if b != s['script']: errs.append((e['name'], 'reemit'))
        starts = set(x.m for x in st)
        if st and st[-1][0] != 0x53: errs.append((e['name'], 'no EndOfScript'))
        for x in st:
            for n in kismet.walk(x):
                if n[0] in (0x06, 0x07, 0x4C) and not e['name'].startswith('ExecuteUbergraph'):
                    if n[1] not in starts: errs.append((e['name'], 'bad jump', n[1]))
                for a in n[1:]:
                    if isinstance(a, tuple) and a and a[0] == 'FP' and a[2] > 0:
                        own = a[2]
                        if own in exp_props and a[1][-1] not in exp_props[own]:
                            errs.append((e['name'], 'unresolved prop', p.nm(*a[1][-1]), own))
    return nfun, errs

if __name__ == '__main__':
    n, errs = verify(sys.argv[1])
    print(os.path.basename(sys.argv[1]), 'functions', n, 'errors', len(errs))
    for x in errs[:20]: print('  ', x)
