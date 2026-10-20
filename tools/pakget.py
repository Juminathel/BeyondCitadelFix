import struct, sys, io, zlib, os
P, OUT = sys.argv[1], sys.argv[2]; pats = sys.argv[3:]
f = open(P,'rb'); f.seek(0,2); sz=f.tell()
f.seek(max(0,sz-1024)); tail=f.read(); i=tail.rfind(bytes.fromhex('e1126f5a'))
pos = sz-len(tail)+i
f.seek(pos); magic,ver,ioff,isz = struct.unpack('<IIqq', f.read(24))
f.seek(ioff); idx=io.BytesIO(f.read(isz))
def rs(b):
    n=struct.unpack('<i',b.read(4))[0]
    return b.read(-n*2).decode('utf-16-le').rstrip('\x00') if n<0 else b.read(n).decode('utf-8','replace').rstrip('\x00')
rs(idx); n=struct.unpack('<i',idx.read(4))[0]; ok=0
for _ in range(n):
    name=rs(idx); off,size,usize=struct.unpack('<qqq',idx.read(24))
    cmi=struct.unpack('<I',idx.read(4))[0]; idx.read(20); blocks=[]
    if cmi:
        c=struct.unpack('<i',idx.read(4))[0]
        blocks=[struct.unpack('<qq',idx.read(16)) for _ in range(c)]
    idx.read(5)
    if pats and not any(p in name for p in pats): continue
    data=None
    for base in (off,0):
        try:
            if cmi==0: f.seek(off+53); buf=f.read(usize)
            else:
                buf=b''
                for b0,b1 in blocks:
                    f.seek(base+b0); buf+=zlib.decompress(f.read(b1-b0))
            if len(buf)==usize: data=buf; break
        except Exception: pass
    if data is None: continue
    q=os.path.join(OUT,name); os.makedirs(os.path.dirname(q),exist_ok=True)
    open(q,'wb').write(data); ok+=1
print('извлечено', ok, file=sys.stderr)
