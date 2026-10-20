import sys,struct; sys.path.insert(0,'/home/alih/bc_tools')
from uasset import Pkg
def exports(base):
    p=Pkg(base+'.uasset'); d=p.d
    # imports
    imps=[]; q=p.import_off
    for _ in range(p.import_count):
        cp,cpn,cl,cln,outer,on,onn=struct.unpack_from('<iiiiiii',d,q); q+=28
        imps.append(p.nm(on,onn))
    ex=[]; q=p.export_off
    for _ in range(p.export_count):
        cls,sup,tmpl,outer,on,onn,flags=struct.unpack_from('<iiiiiiI',d,q)
        ssz,soff=struct.unpack_from('<qq',d,q+28)
        ex.append(dict(cls=imps[-cls-1] if cls<0 else ('exp%d'%cls if cls else ''),name=p.nm(on,onn),outer=outer,size=ssz,off=soff))
        q+=104  # 4.25 export entry size
    return p,ex
if __name__=='__main__':
    p,ex=exports(sys.argv[1])
    for e in ex: print(e['size'],e['cls'],e['name'],e['outer'])
