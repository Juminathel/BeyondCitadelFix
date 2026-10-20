# Pretty-print Kismet bytecode of a function: python3 disasm.py <base> <func>
import sys, struct
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from exports import exports
from ustruct import parse_struct
import kismet

OPN = {0x00:'Local',0x01:'Inst',0x02:'Default',0x04:'Return',0x06:'Jump',0x07:'JumpIfNot',
0x0B:'Nothing',0x0F:'Let',0x12:'ClassCtx',0x13:'MetaCast',0x14:'LetBool',0x17:'Self',0x18:'Skip',
0x19:'Ctx',0x1A:'CtxFS',0x1B:'VFunc',0x1C:'FFunc',0x1D:'Int',0x1E:'Float',0x1F:'Str',0x20:'Obj',
0x21:'Name',0x22:'Rot',0x23:'Vec',0x24:'Byte',0x25:'Int0',0x26:'Int1',0x27:'True',0x28:'False',
0x29:'Text',0x2A:'NoObj',0x2C:'IntB',0x2E:'DynCast',0x2F:'StructConst',0x31:'SetArray',
0x38:'PrimCast',0x42:'StructMember',0x45:'LVFunc',0x46:'LFFunc',0x48:'LocalOut',0x4C:'PushFlow',
0x4D:'PopFlow',0x4E:'CompJump',0x4F:'PopFlowIfNot',0x53:'EndOfScript',0x5F:'LetObj',0x65:'ArrayConst',
0x68:'Math',0x69:'Switch',0x6B:'ArrayGetByRef'}

class Ctx:
    def __init__(self, base):
        self.p, self.ex = exports(base)
        d = self.p.d; q = self.p.import_off; self.imps = []
        for _ in range(self.p.import_count):
            cp, cpn, cl, cln, outer, on, onn = struct.unpack_from('<iiiiiii', d, q); q += 28
            self.imps.append((self.p.nm(on, onn), outer))
    def ref(self, i):
        if i < 0:
            n, o = self.imps[-i - 1]
            return (self.ref(o) + '.' if o else '') + n
        if i > 0: return self.ex[i - 1]['name']
        return 'null'
    def fp(self, v):
        return '.'.join(self.p.nm(*n) for n in v[1])

def fmt(c, n):
    op = n[0]; name = OPN.get(op, '0x%02X' % op); args = []
    for x in n[1:]:
        if isinstance(x, kismet.Node): args.append(fmt(c, x))
        elif isinstance(x, tuple) and x and x[0] == 'FP': args.append(c.fp(x))
        elif isinstance(x, tuple): args.append(c.p.nm(*x))
        elif isinstance(x, list):
            args.append('[' + ', '.join(fmt(c, y) if isinstance(y, kismet.Node) else
                                        '{' + ', '.join(fmt(c, z) if isinstance(z, kismet.Node) else str(z) for z in y) + '}'
                                        for y in x) + ']')
        else: args.append(str(x))
    if op in (0x1C, 0x46, 0x68, 0x13, 0x2E, 0x20) and isinstance(n[1], int):
        args[0] = c.ref(n[1])
    return name + '(' + ', '.join(args) + ')'

if __name__ == '__main__':
    c = Ctx(sys.argv[1]); u = open(sys.argv[1] + '.uexp', 'rb').read(); H = c.p.total_header
    for e in c.ex:
        if e['name'] == sys.argv[2] and e['cls'] == 'Function':
            s = parse_struct(c.p, u[e['off'] - H:e['off'] - H + e['size']])
            print('locals:', [(f['type'], f['name'], hex(f['pflags'])) for f in s['props']])
            st, _ = kismet.parse_script(s['script'])
            for x in st: print('%6d  %s' % (x.m, fmt(c, x)))
