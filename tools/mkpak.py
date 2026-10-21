import struct, sys, os, hashlib
root, out = sys.argv[1], sys.argv[2]
files = sorted((os.path.relpath(os.path.join(dp,x), root).replace(os.sep,'/'), os.path.join(dp,x))
               for dp,_,fn in os.walk(root) for x in fn)
def fstr(s):
    b=s.encode('utf-8')+b'\x00'; return struct.pack('<i',len(b))+b
def entry(off,size,sha): return struct.pack('<qqqI',off,size,size,0)+sha+struct.pack('<BI',0,0)
body, recs = bytearray(), []
for name, full in files:
    data=open(full,'rb').read(); sha=hashlib.sha1(data).digest(); off=len(body)
    body += entry(0,len(data),sha)+data; recs.append((name,off,len(data),sha))
index = bytearray(fstr('../../../')+struct.pack('<i',len(recs)))
for name,off,size,sha in recs: index += fstr(name)+entry(off,size,sha)
foot = b'\x00'*17 + struct.pack('<IIqq',0x5A6F12E1,9,len(body),len(index))
foot += hashlib.sha1(bytes(index)).digest() + b'\x00' + b'Zlib'.ljust(32,b'\x00') + b'\x00'*128
assert len(foot)==222
open(out,'wb').write(bytes(body)+bytes(index)+foot)
print(f'{out}: {len(recs)} files, {os.path.getsize(out)} bytes')
