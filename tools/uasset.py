import struct
class Pkg:
    def __init__(self, path):
        self.d = d = open(path,'rb').read()
        assert struct.unpack_from('<I',d,0)[0] == 0x9E2A83C1
        p = 20
        cvc, = struct.unpack_from('<i', d, p); p += 4 + cvc*20
        self.total_header, = struct.unpack_from('<i', d, p); p += 4
        n, = struct.unpack_from('<i', d, p); p += 4
        p += -n*2 if n < 0 else n
        self.pkg_flags, = struct.unpack_from('<I', d, p); p += 4
        self.name_count, self.name_off = struct.unpack_from('<ii', d, p); p += 8
        if not (self.pkg_flags & 0x80000000):
            n, = struct.unpack_from('<i', d, p); p += 4
            p += -n*2 if n < 0 else n
        p += 8
        self.export_count, self.export_off = struct.unpack_from('<ii', d, p); p += 8
        self.import_count, self.import_off = struct.unpack_from('<ii', d, p)
        self.names = self._names()
    def _names(self):
        out, q = [], self.name_off
        for _ in range(self.name_count):
            n, = struct.unpack_from('<i', self.d, q); q += 4
            if n < 0: s = self.d[q:q-n*2].decode('utf-16-le').rstrip('\x00'); q += -n*2
            else:     s = self.d[q:q+n].decode('latin-1').rstrip('\x00'); q += n
            q += 4; out.append(s)
        return out
    def nm(self, i, num=0):
        s = self.names[i] if 0 <= i < len(self.names) else f'<{i}>'
        return s if num == 0 else f'{s}_{num-1}'
