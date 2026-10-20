# Optimize UMG widget blueprints in place (cooked UE4.25):
#   1) LoadGameFromSlot in read-only functions -> per-widget cache, reloaded at most every SAVE_TTL s
#   2) heavy property bindings -> recomputed at most every THROTTLE s, cached value returned otherwise
# usage: python3 hudopt.py <in_base> <out_base> [--no-throttle]
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkgedit import Package
from ustruct import parse_struct, read_ffield
import kismet
from kismet import Node

SAVE_TTL = 0.5
THROTTLE = 0.08          # max interval; per-binding interval is spread over [THROTTLE/2, THROTTLE]
MIN_THROTTLE_MEM = 400   # bindings with smaller bytecode are cheaper than the throttle check

class Label:
    def __init__(self, node=None): self.node = node

def N(*a): return Node(a)

def fpath_self(name, cls_idx): return ('FP', (name,), cls_idx)

class Ctx:
    def __init__(self, p):
        self.p = p
        self.ci = next(i for i, e in enumerate(p.exports)
                       if p.class_name(e['cls']) == 'WidgetBlueprintGeneratedClass')
        self.cls_idx = self.ci + 1
        self.new_props = []          # FField blobs to append to the class
        self.F = {}
    def fn(self, mod, cls, f):
        k = (mod, cls, f)
        if k not in self.F: self.F[k] = self.p.script_func(mod, cls, f)
        return self.F[k]
    def math(self, mod, cls, f, *args): return N(0x68, self.fn(mod, cls, f), list(args))
    def now(self): return self.math('Engine', 'GameplayStatics', 'GetRealTimeSeconds', N(0x17))
    # timestamps are stored as now + T_OFS so that the zero-initialized value (and values
    # from a previous world, whose clock was ahead) always read as stale
    T_OFS = 1000.0
    def stamp(self, phase=0.0):
        return self.math('Engine', 'KismetMathLibrary', 'Add_FloatFloat', self.now(),
                         N(0x1E, self.T_OFS - phase))
    def age_ok(self, t_fp, ttl):
        # T - now = T_OFS - age ; fresh iff age in [0, ttl)  <=>  T - now in (T_OFS - ttl, T_OFS]
        d = self.math('Engine', 'KismetMathLibrary', 'Subtract_FloatFloat', N(0x01, t_fp), self.now())
        return self.math('Engine', 'KismetMathLibrary', 'InRange_FloatFloat', d,
                         N(0x1E, self.T_OFS - float(ttl)), N(0x1E, self.T_OFS), N(0x28), N(0x27))
    def add_prop(self, template_blob, name):
        """Clone an FField blob (from type FName on) under a new name as a plain member."""
        b = bytearray(template_blob)
        nm = self.p.name(name)
        struct.pack_into('<ii', b, 8, *nm)                 # Name
        struct.pack_into('<I', b, 16, 0x200001)            # EObjectFlags like other members
        pf, = struct.unpack_from('<Q', b, 28)
        pf &= ~(0x80 | 0x100 | 0x400 | 0x2 | 0x8000000)    # drop Parm/OutParm/ReturnParm/Const/Ref
        struct.pack_into('<Q', b, 28, pf | 0x2000)         # Transient
        self.new_props.append(bytes(b))
        return fpath_self(nm, self.cls_idx)

def rewrite(stmts, repl):
    """repl(stmt) -> None (keep) or list of new statements. Jumps to old offsets are remapped
    to the first statement of the replacement; Label operands resolve to their node."""
    out, first = [], {}
    for s in stmts:
        r = repl(s)
        new = [s] if r is None else r
        first[s.m] = new[0]
        out.extend(new)
    def fix(kind, v):
        if isinstance(v, Label): return v.node.m or 0     # forward refs are 0 in pass 1
        if v in first: return first[v].m or 0
        raise ValueError('jump into middle of statement: %d' % v)
    kismet.emit_script(out, fix)          # pass 1: positions
    return kismet.emit_script(out, fix)   # pass 2: final offsets

def calls(stmts, p):
    names = set()
    for s in stmts:
        for n in kismet.walk(s):
            if n[0] in (0x68, 0x1C, 0x46):
                i = n[1]; names.add(p.imports[-i - 1]['name'] if i < 0 else p.exports[i - 1]['name'])
            elif n[0] in (0x1B, 0x45): names.add(p.nm(*n[1]))
    return names

def writes_foreign(stmts):
    """True if function assigns into members of other objects (EX_Context as l-value)."""
    for s in stmts:
        for n in kismet.walk(s):
            if n[0] in (0x0F,) and n[2][0] in (0x19, 0x1A): return True
            if n[0] in (0x14, 0x5F, 0x60, 0x44, 0x43) and n[1][0] in (0x19, 0x1A): return True
    return False

MUTATORS = ('Array_', 'Map_', 'Set_')
def writes_foreign_calls(stmts, p):
    """Container mutators applied to another object's member (Array_Add(Ctx(obj).arr) ...)."""
    for s in stmts:
        for n in kismet.walk(s):
            if n[0] in (0x68, 0x1C, 0x46) and n[1] < 0:
                nm = p.imports[-n[1] - 1]['name']
                if nm.startswith(MUTATORS) and not nm.endswith(('Get', 'Length', 'Find', 'Contains',
                        'IsValidIndex', 'LastIndex', 'Keys', 'Values', 'Find_Item', 'Length')):
                    if any(a[0] in (0x19, 0x1A) for a in n[2]): return True
    return False

def writes_self(stmts):
    for s in stmts:
        for n in kismet.walk(s):
            if n[0] == 0x0F and n[2][0] == 0x01: return True
            if n[0] in (0x14, 0x5F, 0x60, 0x44, 0x43) and n[1][0] == 0x01: return True
    return False

def bindings_of(p, ci):
    from bindings import find_bindings
    _, _, _, items = find_bindings(p.base)
    return set(b['func'] for b in items)

def optimize(inb, outb, throttle=True, log=print):
    p = Package(inb); c = Ctx(p)
    binds = bindings_of(p, c.ci)
    cls_blob = p.exports[c.ci]['blob']
    cls = parse_struct(p, cls_blob)
    slots = {}            # slot string -> (sg_fp, st_fp)
    stats = dict(save=0, save_funcs=0, throttled=0, skipped_write=0)
    # synthetic FloatProperty FField: type, name, flags, ArrayDim, ElementSize, PropertyFlags,
    # RepIndex, RepNotifyFunc, BlueprintReplicationCondition
    float_tmpl = (struct.pack('<ii', *p.name('FloatProperty')) + struct.pack('<ii', *p.name('None'))
                  + struct.pack('<IiiQH', 0, 1, 4, 0, 0) + struct.pack('<ii', *p.name('None')) + b'\x00')
    k_thr = 0
    for ei, e in enumerate(p.exports):
        if p.class_name(e['cls']) != 'Function' or e['outer'] != c.cls_idx: continue
        if e['name'].startswith('ExecuteUbergraph'): continue
        s = parse_struct(p, e['blob'])
        if not s['script']: continue
        stmts, mem = kismet.parse_script(s['script'])
        cn = calls(stmts, p)
        has_load = 'LoadGameFromSlot' in cn
        ro = not ({'SaveGameToSlot', 'AsyncSaveGameToSlot', 'DeleteGameInSlot'} & cn) \
             and not writes_foreign(stmts) and not writes_foreign_calls(stmts, p)
        is_bind = e['name'] in binds
        fflags, = struct.unpack_from('<I', e['blob'], s['tail_off'])
        pure = bool(fflags & 0x10000000)
        do_save = has_load and ro and (is_bind or pure)
        if has_load and not ro: stats['skipped_write'] += 1
        ret = next((f for f in s['props'] if f['pflags'] & 0x400), None)
        do_thr = (throttle and is_bind and ret is not None and ro and not writes_self(stmts)
                  and (mem >= MIN_THROTTLE_MEM or has_load))
        if not (do_save or do_thr): continue


        def save_repl(st):
            if not (st[0] == 0x5F and st[2][0] == 0x68 and
                    p.imports[-st[2][1] - 1]['name'] == 'LoadGameFromSlot'): return None
            args = st[2][2]
            if len(args) != 2 or args[0][0] != 0x1F: return None
            slot = args[0][1]
            if slot not in slots:
                i = len(slots)
                # object cache: clone the local receiving the LoadGameFromSlot result
                dst = st[1]
                lp = next(f for f in s['props'] if f['name_idx'] == dst[1][1][0])
                sg = c.add_prop(e['blob'][lp['start']:lp['end']], 'bcopt_sg%d' % i)
                stt = c.add_prop(float_tmpl, 'bcopt_st%d' % i)
                slots[slot] = (sg, stt)
            sg, stt = slots[slot]
            stats['save'] += 1
            l_load, l_end = Label(), Label()
            a = N(0x07, l_load, c.age_ok(stt, SAVE_TTL))
            b = N(0x5F, st[1], N(0x01, sg))
            j = N(0x06, l_end)
            ld = N(0x5F, N(0x01, sg), st[2])
            l_load.node = ld
            t = N(0x0F, stt, N(0x01, stt), c.stamp())
            fin = N(0x5F, st[1], N(0x01, sg))
            # l_end = statement after the replacement: emit a no-op anchor
            anchor = N(0x0B); l_end.node = anchor
            return [a, b, j, ld, t, fin, anchor]

        new = stmts
        if do_save:
            stats['save_funcs'] += 1
            b, m = rewrite(stmts, save_repl)
            new, _ = kismet.parse_script(b)

        if do_thr:
            i = k_thr; k_thr += 1
            rp = e['blob'][ret['start']:ret['end']]
            cache = c.add_prop(rp, 'bcopt_c%d' % i)
            tt = c.add_prop(float_tmpl, 'bcopt_t%d' % i)
            ret_fp = ('FP', (ret['name_idx'],), ei + 1)
            for st in new:                       # use the exact path the function uses
                for n in kismet.walk(st):
                    if n[0] == 0x48: ret_fp = n[1]; break
            l_comp = Label()
            pro = [N(0x07, l_comp, c.age_ok(tt, THROTTLE)),
                   N(0x0F, ret_fp, N(0x48, ret_fp), N(0x01, cache)),
                   N(0x04, N(0x48, ret_fp))]
            phase = THROTTLE * 0.5 * ((i * 0.618034) % 1.0)
            comp = N(0x0F, tt, N(0x01, tt), c.stamp(phase))
            l_comp.node = comp
            # keep original offsets for jump remap: rewrite() over [pro, comp] + body
            heads = pro + [comp]
            def thr_repl(st, _first=[True]):
                r = []
                if _first[0]: r += heads; _first[0] = False
                if st[0] == 0x04: r.append(N(0x0F, cache, N(0x01, cache), N(0x48, ret_fp)))
                if not r: return None
                return r + [st]
            b, m = rewrite(new, thr_repl)
            # rewrite maps old jump targets to the first new stmt; for the very first original
            # statement that would be the prologue, which is exactly the function entry: fine,
            # but a backward jump to offset 0 must not re-run the prologue -> check
            first_off = new[0].m
            for st in new:
                for n in kismet.walk(st):
                    if n[0] in (0x06, 0x07, 0x4C) and n[1] == first_off:
                        raise ValueError('jump to entry in ' + e['name'])
            stats['throttled'] += 1
        else:
            b, m = kismet.emit_script(new)

        # rebuild function blob
        blob = bytearray(e['blob'])
        blob[s['script_hdr']:s['tail_off']] = struct.pack('<ii', m, len(b)) + b
        e['blob'] = bytes(blob)

    if c.new_props:
        cls = parse_struct(p, cls_blob)
        q = cls['props_off']; n, = struct.unpack_from('<i', cls_blob, q)
        nb = bytearray(cls_blob)
        ins = cls['script_hdr']
        nb[ins:ins] = b''.join(c.new_props)
        struct.pack_into('<i', nb, q, n + len(c.new_props))
        p.exports[c.ci]['blob'] = bytes(nb)
    stats['props'] = len(c.new_props)
    p.save(outb)
    return stats

if __name__ == '__main__':
    st = optimize(sys.argv[1], sys.argv[2], throttle='--no-throttle' not in sys.argv)
    print(os.path.basename(sys.argv[1]), st)
