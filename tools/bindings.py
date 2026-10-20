import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Pkg
def find_bindings(base):
    p = Pkg(base+'.uasset'); u = open(base+'.uexp','rb').read()
    if 'Bindings' not in p.names or 'ArrayProperty' not in p.names: return p,u,None,[]
    pat = struct.pack('<iiii', p.names.index('Bindings'),0, p.names.index('ArrayProperty'),0)
    t = u.find(pat)
    if t < 0: return p,u,None,[]
    q = t+33
    count, = struct.unpack_from('<i',u,q); q += 4 + 49
    items = []
    for _ in range(count):
        off = q; rec = {}
        while True:
            ni,nn = struct.unpack_from('<ii',u,off); name = p.nm(ni,nn)
            if name == 'None': off += 8; break
            ti,tn = struct.unpack_from('<ii',u,off+8); typ = p.nm(ti,tn)
            sz,_ = struct.unpack_from('<ii',u,off+16)
            vo = off+24
            if typ == 'StructProperty': vo += 24
            elif typ in ('ByteProperty','EnumProperty'): vo += 8
            elif typ == 'BoolProperty': vo += 1
            g = u[vo]; vo += 1
            if g: vo += 16
            rec[name] = (typ, vo, sz)
            off = vo + (0 if typ=='BoolProperty' else sz)
        def fname(k):
            if k not in rec: return None
            i,n = struct.unpack_from('<ii',u,rec[k][1]); return p.nm(i,n)
        def fstr(k):
            if k not in rec: return None
            n, = struct.unpack_from('<i',u,rec[k][1])
            return u[rec[k][1]+4:rec[k][1]+4+n].decode('latin-1').rstrip('\x00') if n>0 else ''
        items.append(dict(obj=fstr('ObjectName'), prop=fname('PropertyName'),
                          func=fname('FunctionName'), prop_off=rec['PropertyName'][1]))
        q = off
    return p,u,count,items
