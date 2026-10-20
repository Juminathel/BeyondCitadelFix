# UE4.25 Kismet bytecode: parse to tree, re-serialize, track in-memory offsets.
# Node = [op, *operands]; operands may be ints, bytes, sub-nodes, lists of nodes.
import struct

# operand kinds
FP, OBJ, NAME, U32, I32, U16, U8, F32, EXPR, PARAMS, STR, USTR = range(12)

def _r(fmt, d, p):
    v = struct.unpack_from(fmt, d, p); return v if len(v) > 1 else v[0]

class Reader:
    def __init__(self, d):
        self.d, self.p, self.m = d, 0, 0     # disk pos, memory pos
    def u8(self):  v = self.d[self.p]; self.p += 1; self.m += 1; return v
    def u16(self): v = _r('<H', self.d, self.p); self.p += 2; self.m += 2; return v
    def u32(self): v = _r('<I', self.d, self.p); self.p += 4; self.m += 4; return v
    def i32(self): v = _r('<i', self.d, self.p); self.p += 4; self.m += 4; return v
    def f32(self): v = _r('<f', self.d, self.p); self.p += 4; self.m += 4; return v
    def raw(self, n, mem=None):
        v = self.d[self.p:self.p+n]; self.p += n; self.m += n if mem is None else mem; return v
    def obj(self): v = _r('<i', self.d, self.p); self.p += 4; self.m += 8; return v
    def name(self): v = _r('<ii', self.d, self.p); self.p += 8; self.m += 12; return v
    def fpath(self):
        n = _r('<i', self.d, self.p); q = self.p + 4
        names = [_r('<ii', self.d, q + 8*i) for i in range(n)]; q += 8*n
        owner = _r('<i', self.d, q); q += 4
        self.p = q; self.m += 8
        return ('FP', tuple(names), owner)

class Node(list):
    """[op, operands...]; .m = memory offset of the opcode (set by parse/emit)."""
    m = None

def parse_expr(r):
    op = r.u8()
    n = Node([op]); n.m = r.m - 1
    a = n.append
    E = lambda: parse_expr(r)
    if op in (0x00, 0x01, 0x02, 0x48, 0x33, 0x6C):    a(r.fpath())
    elif op == 0x04: a(E())
    elif op == 0x06: a(r.u32())
    elif op == 0x07: a(r.u32()); a(E())
    elif op == 0x09: a(r.u16()); a(r.u8()); a(E())
    elif op in (0x0B, 0x15, 0x16, 0x17, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x2D, 0x30,
                0x32, 0x3A, 0x3C, 0x3E, 0x40, 0x4A, 0x4D, 0x50, 0x53, 0x5A, 0x5E, 0x66):
        pass
    elif op == 0x0F: a(r.fpath()); a(E()); a(E())
    elif op in (0x12, 0x19, 0x1A):
        a(E()); a(r.u32()); a(r.fpath()); a(E())
    elif op in (0x13, 0x2E, 0x52, 0x54, 0x55): a(r.obj()); a(E())
    elif op in (0x14, 0x43, 0x44, 0x5C, 0x5F, 0x60, 0x62, 0x6B): a(E()); a(E())
    elif op == 0x18: a(r.u32()); a(E())
    elif op in (0x1B, 0x45): a(r.name()); a(parse_params(r))
    elif op in (0x1C, 0x46, 0x63, 0x68): a(r.obj()); a(parse_params(r))
    elif op == 0x1D: a(r.i32())
    elif op == 0x1E: a(r.f32())
    elif op == 0x1F:
        e = r.d.index(b'\x00', r.p); a(r.raw(e - r.p + 1))
    elif op == 0x20: a(r.obj())
    elif op == 0x21: a(r.name())
    elif op in (0x22, 0x23): a(r.raw(12))
    elif op == 0x24: a(r.u8())
    elif op == 0x29:
        t = r.u8(); a(t)
        if t in (1,): a(E()); a(E()); a(E())
        elif t in (2, 3): a(E())
        elif t == 4: a(r.obj()); a(E()); a(E())
        elif t in (0, 255): pass
        else: raise ValueError('text type %d' % t)
    elif op == 0x2B: a(r.raw(40))
    elif op == 0x2C: a(r.u8())
    elif op == 0x2F:
        a(r.obj()); a(r.i32()); items = []
        while True:
            e = E()
            if e[0] == 0x30: break
            items.append(e)
        a(items)
    elif op == 0x31:
        a(E()); items = []
        while True:
            e = E()
            if e[0] == 0x32: break
            items.append(e)
        a(items)
    elif op == 0x34:
        q = r.p
        while r.d[q:q+2] != b'\x00\x00': q += 2
        a(r.raw(q + 2 - r.p))
    elif op == 0x35 or op == 0x36: a(r.raw(8))
    elif op == 0x38: a(r.u8()); a(E())
    elif op in (0x39, 0x3B):
        a(E()); a(r.i32()); items = []
        end = 0x3A if op == 0x39 else 0x3C
        while True:
            e = E()
            if e[0] == end: break
            items.append(e)
        a(items)
    elif op == 0x3D or op == 0x65:
        a(r.fpath()); a(r.i32()); items = []
        end = 0x3E if op == 0x3D else 0x66
        while True:
            e = E()
            if e[0] == end: break
            items.append(e)
        a(items)
    elif op == 0x3F:
        a(r.fpath()); a(r.fpath()); a(r.i32()); items = []
        while True:
            e = E()
            if e[0] == 0x40: break
            items.append(e)
        a(items)
    elif op == 0x42: a(r.fpath()); a(E())
    elif op == 0x4B: a(r.name())
    elif op == 0x4C: a(r.u32())
    elif op in (0x4E, 0x4F, 0x51, 0x5D, 0x67, 0x6D): a(E())
    elif op == 0x5B: a(r.u32())
    elif op == 0x61: a(r.name()); a(E()); a(E())
    elif op == 0x64: a(r.fpath()); a(E())
    elif op == 0x69:
        nc = r.u16(); a(nc); a(r.u32()); a(E()); cases = []
        for _ in range(nc):
            cv = E(); nxt = r.u32(); res = E(); cases.append([cv, nxt, res])
        a(cases); a(E())
    elif op == 0x6A:
        t = r.u8(); a(t)
        if t == 4: a(r.name())
    else:
        raise ValueError('unknown opcode 0x%02X at disk %d mem %d' % (op, r.p - 1, r.m - 1))
    return n

def parse_params(r):
    items = []
    while True:
        e = parse_expr(r)
        if e[0] == 0x16: return items
        items.append(e)

def parse_script(d):
    r = Reader(d); out = []
    while r.p < len(d):
        out.append(parse_expr(r))
    return out, r.m

# ---- emit ----
class Writer:
    def __init__(self): self.b = bytearray(); self.m = 0
    def u8(self, v): self.b.append(v); self.m += 1
    def u16(self, v): self.b += struct.pack('<H', v); self.m += 2
    def u32(self, v): self.b += struct.pack('<I', v); self.m += 4
    def i32(self, v): self.b += struct.pack('<i', v); self.m += 4
    def f32(self, v): self.b += struct.pack('<f', v); self.m += 4
    def raw(self, v): self.b += v; self.m += len(v)
    def obj(self, v): self.b += struct.pack('<i', v); self.m += 8
    def name(self, v): self.b += struct.pack('<ii', *v); self.m += 12
    def fpath(self, v):
        _, names, owner = v
        self.b += struct.pack('<i', len(names))
        for nm in names: self.b += struct.pack('<ii', *nm)
        self.b += struct.pack('<i', owner); self.m += 8

def emit_expr(w, n, fix):
    """fix(kind, value) -> value: lets caller remap jump targets (kind 'jmp')."""
    op = n[0]; n.m = w.m; w.u8(op)
    E = lambda x: emit_expr(w, x, fix)
    if op in (0x00, 0x01, 0x02, 0x48, 0x33, 0x6C): w.fpath(n[1])
    elif op == 0x04: E(n[1])
    elif op == 0x06: w.u32(fix('jmp', n[1]))
    elif op == 0x07: w.u32(fix('jmp', n[1])); E(n[2])
    elif op == 0x09: w.u16(n[1]); w.u8(n[2]); E(n[3])
    elif op in (0x0B, 0x15, 0x16, 0x17, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x2D, 0x30,
                0x32, 0x3A, 0x3C, 0x3E, 0x40, 0x4A, 0x4D, 0x50, 0x53, 0x5A, 0x5E, 0x66):
        pass
    elif op == 0x0F: w.fpath(n[1]); E(n[2]); E(n[3])
    elif op in (0x12, 0x19, 0x1A):
        E(n[1]); pos = len(w.b); w.u32(0); start = w.m
        w.fpath(n[3]); m0 = w.m; E(n[4])
        # skip = memory size of the context expression (after rvalue pointer)
        struct.pack_into('<I', w.b, pos, w.m - m0)
    elif op in (0x13, 0x2E, 0x52, 0x54, 0x55): w.obj(n[1]); E(n[2])
    elif op in (0x14, 0x43, 0x44, 0x5C, 0x5F, 0x60, 0x62, 0x6B): E(n[1]); E(n[2])
    elif op == 0x18:
        pos = len(w.b); w.u32(0); m0 = w.m; E(n[2])
        struct.pack_into('<I', w.b, pos, w.m - m0)
    elif op in (0x1B, 0x45): w.name(n[1]); [E(x) for x in n[2]]; w.u8(0x16)
    elif op in (0x1C, 0x46, 0x63, 0x68): w.obj(n[1]); [E(x) for x in n[2]]; w.u8(0x16)
    elif op == 0x1D: w.i32(n[1])
    elif op == 0x1E: w.f32(n[1])
    elif op == 0x1F: w.raw(n[1])
    elif op == 0x20: w.obj(n[1])
    elif op == 0x21: w.name(n[1])
    elif op in (0x22, 0x23, 0x2B, 0x35, 0x36, 0x34): w.raw(n[1])
    elif op == 0x24 or op == 0x2C: w.u8(n[1])
    elif op == 0x29:
        t = n[1]; w.u8(t)
        if t == 4: w.obj(n[2]); E(n[3]); E(n[4])
        else: [E(x) for x in n[2:]]
    elif op == 0x2F: w.obj(n[1]); w.i32(n[2]); [E(x) for x in n[3]]; w.u8(0x30)
    elif op == 0x31: E(n[1]); [E(x) for x in n[2]]; w.u8(0x32)
    elif op == 0x38: w.u8(n[1]); E(n[2])
    elif op in (0x39, 0x3B):
        E(n[1]); w.i32(n[2]); [E(x) for x in n[3]]; w.u8(0x3A if op == 0x39 else 0x3C)
    elif op in (0x3D, 0x65):
        w.fpath(n[1]); w.i32(n[2]); [E(x) for x in n[3]]; w.u8(0x3E if op == 0x3D else 0x66)
    elif op == 0x3F:
        w.fpath(n[1]); w.fpath(n[2]); w.i32(n[3]); [E(x) for x in n[4]]; w.u8(0x40)
    elif op == 0x42: w.fpath(n[1]); E(n[2])
    elif op == 0x4B: w.name(n[1])
    elif op == 0x4C: w.u32(fix('jmp', n[1]))
    elif op in (0x4E, 0x4F, 0x51, 0x5D, 0x67, 0x6D): E(n[1])
    elif op == 0x5B: w.u32(fix('jmp', n[1]))
    elif op == 0x61: w.name(n[1]); E(n[2]); E(n[3])
    elif op == 0x64: w.fpath(n[1]); E(n[2])
    elif op == 0x69:
        w.u16(n[1]); endpos = len(w.b); w.u32(0); E(n[3])
        for cv, _, res in n[4]:
            E(cv); np_ = len(w.b); w.u32(0); E(res)
            struct.pack_into('<I', w.b, np_, w.m)      # next case starts here
        E(n[5])
        struct.pack_into('<I', w.b, endpos, w.m)       # end of whole switch
    elif op == 0x6A:
        w.u8(n[1])
        if n[1] == 4: w.name(n[2])
    else:
        raise ValueError('emit: unknown op 0x%02X' % op)

def emit_script(stmts, fix=lambda k, v: v):
    w = Writer()
    for s in stmts: emit_expr(w, s, fix)
    return bytes(w.b), w.m

def walk(n):
    yield n
    for x in n[1:]:
        if isinstance(x, Node): yield from walk(x)
        elif isinstance(x, list):
            for y in x:
                if isinstance(y, Node): yield from walk(y)
                elif isinstance(y, list):
                    for z in y:
                        if isinstance(z, Node): yield from walk(z)
