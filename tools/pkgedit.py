# Editable cooked UE4.25 package (.uasset + .uexp): add names/imports, replace export blobs.
import struct

def _fstr(s):
    b = s.encode('latin-1') + b'\x00'
    return struct.pack('<i', len(b)) + b

class Package:
    def __init__(self, base):
        self.base = base
        self.h = bytearray(open(base + '.uasset', 'rb').read())
        self.x = bytearray(open(base + '.uexp', 'rb').read())
        self._parse_summary()
        self._parse_names()
        self._parse_imports()
        self._parse_exports()

    # ---- summary ----
    def _parse_summary(self):
        d = self.h; q = 0; F = self.f = {}
        def rd(fmt, key=None):
            nonlocal q
            v = struct.unpack_from(fmt, d, q)
            if key: F[key] = (q, fmt)
            q += struct.calcsize(fmt)
            return v[0] if len(v) == 1 else v
        def rstr():
            nonlocal q
            n, = struct.unpack_from('<i', d, q); q += 4
            q += n if n >= 0 else -2 * n
        assert rd('<I') == 0x9E2A83C1
        legacy = rd('<i'); assert legacy == -7
        rd('<i'); rd('<i'); rd('<i')
        ncv = rd('<i'); q += ncv * 20
        rd('<i', 'TotalHeaderSize')
        rstr()
        flags = rd('<I', 'PackageFlags')
        rd('<i', 'NameCount'); rd('<i', 'NameOffset')
        if not (flags & 0x80000000): rstr()
        rd('<i', 'GatherableTextDataCount'); rd('<i', 'GatherableTextDataOffset')
        rd('<i', 'ExportCount'); rd('<i', 'ExportOffset')
        rd('<i', 'ImportCount'); rd('<i', 'ImportOffset')
        rd('<i', 'DependsOffset')
        rd('<i', 'SoftPackageReferencesCount'); rd('<i', 'SoftPackageReferencesOffset')
        rd('<i', 'SearchableNamesOffset'); rd('<i', 'ThumbnailTableOffset')
        q += 16
        ng = rd('<i'); self.gen_pos = q; q += ng * 8
        for _ in range(2):           # Saved/Compatible engine version
            q += 10; rstr()
        rd('<I')                     # CompressionFlags
        nc = rd('<i'); assert nc == 0
        rd('<I')                     # PackageSource
        na = rd('<i')
        for _ in range(na): rstr()
        rd('<i', 'AssetRegistryDataOffset')
        rd('<q', 'BulkDataStartOffset')
        rd('<i', 'WorldTileInfoDataOffset')
        nch = rd('<i'); q += 4 * nch
        rd('<i', 'PreloadDependencyCount'); rd('<i', 'PreloadDependencyOffset')
        self.summary_end = q

    def get(self, k):
        pos, fmt = self.f[k]; return struct.unpack_from(fmt, self.h, pos)[0]
    def put(self, k, v):
        pos, fmt = self.f[k]; struct.pack_into(fmt, self.h, pos, v)

    # ---- names ----
    def _parse_names(self):
        q = self.get('NameOffset'); self.names = []
        for _ in range(self.get('NameCount')):
            n, = struct.unpack_from('<i', self.h, q); q += 4
            if n < 0: s = self.h[q:q - 2 * n].decode('utf-16-le').rstrip('\x00'); q += -2 * n
            else: s = self.h[q:q + n].decode('latin-1').rstrip('\x00'); q += n
            hashes = bytes(self.h[q:q + 4]); q += 4
            self.names.append((s, hashes))
        self.names_end = q
        self.name_index = {s: i for i, (s, _) in enumerate(self.names)}

    def nm(self, i, num=0):
        s = self.names[i][0] if 0 <= i < len(self.names) else '<%d>' % i
        return s if num == 0 else '%s_%d' % (s, num - 1)

    def name(self, s):
        """FName tuple (index, number) for s, adding to the name map if missing."""
        if s in self.name_index: return (self.name_index[s], 0)
        from namehash import name_hashes
        b = _fstr(s) + name_hashes(s)
        self._insert_header(self.names_end, b)
        self.names_end += len(b)
        self.names.append((s, b[-4:])); self.name_index[s] = len(self.names) - 1
        self.put('NameCount', len(self.names))
        struct.pack_into('<i', self.h, self.gen_pos + 4, len(self.names))
        return (len(self.names) - 1, 0)

    # ---- imports ----
    def _parse_imports(self):
        q = self.get('ImportOffset'); self.imports = []
        for _ in range(self.get('ImportCount')):
            cp, cpn, cl, cln, outer, on, onn = struct.unpack_from('<iiiiiii', self.h, q); q += 28
            self.imports.append(dict(cpkg=self.nm(cp, cpn), cls=self.nm(cl, cln), outer=outer,
                                     name=self.nm(on, onn)))

    def find_import(self, name, cls=None, outer=None):
        for i, im in enumerate(self.imports):
            if im['name'] == name and (cls is None or im['cls'] == cls) and \
               (outer is None or im['outer'] == outer):
                return -i - 1
        return None

    def import_(self, cpkg, cls, outer, name):
        r = self.find_import(name, cls, outer)
        if r is not None: return r
        cp = self.name(cpkg); cl = self.name(cls); on = self.name(name)
        b = struct.pack('<iiiiiii', cp[0], cp[1], cl[0], cl[1], outer, on[0], on[1])
        end = self.get('ImportOffset') + 28 * len(self.imports)
        self._insert_header(end, b)
        self.imports.append(dict(cpkg=cpkg, cls=cls, outer=outer, name=name))
        self.put('ImportCount', len(self.imports))
        return -len(self.imports)

    def script_func(self, module, cls, func):
        """Import /Script/<module>.<cls>:<func> as UFunction; returns package index."""
        pkg = self.find_import('/Script/' + module, 'Package', 0)
        if pkg is None: pkg = self.import_('/Script/CoreUObject', 'Package', 0, '/Script/' + module)
        c = self.find_import(cls, 'Class', pkg)
        if c is None: c = self.import_('/Script/CoreUObject', 'Class', pkg, cls)
        return self.import_('/Script/CoreUObject', 'Function', c, func)

    # ---- exports ----
    def _parse_exports(self):
        q = self.get('ExportOffset'); self.exports = []
        H = self.get('TotalHeaderSize')
        for i in range(self.get('ExportCount')):
            cls, sup, tmpl, outer, on, onn, flags = struct.unpack_from('<iiiiiiI', self.h, q)
            ssz, soff = struct.unpack_from('<qq', self.h, q + 28)
            self.exports.append(dict(cls=cls, outer=outer, name=self.nm(on, onn), size=ssz,
                                     off=soff, entry=q - self.get('ExportOffset'),
                                     blob=bytes(self.x[soff - H:soff - H + ssz])))
            q += 104
        last = max(e['off'] + e['size'] for e in self.exports) - H
        self.x_tail = bytes(self.x[last:])
        assert sorted(e['off'] for e in self.exports) == [e['off'] for e in self.exports]

    def class_name(self, idx):
        if idx < 0: return self.imports[-idx - 1]['name']
        if idx > 0: return self.exports[idx - 1]['name']
        return ''

    # ---- low level ----
    OFFSET_FIELDS = ['NameOffset', 'GatherableTextDataOffset', 'ExportOffset', 'ImportOffset',
                     'DependsOffset', 'SoftPackageReferencesOffset', 'SearchableNamesOffset',
                     'ThumbnailTableOffset', 'AssetRegistryDataOffset', 'WorldTileInfoDataOffset',
                     'PreloadDependencyOffset']

    def _insert_header(self, pos, b):
        # section offsets strictly after the insertion point move (sections starting at pos
        # move too, unless pos is inside/at end of that very section -> handled by callers
        # inserting at the end of names/imports, which equals the next section's start)
        for k in self.OFFSET_FIELDS:
            v = self.get(k)
            if v and v >= pos: self.put(k, v + len(b))
        self.put('TotalHeaderSize', self.get('TotalHeaderSize') + len(b))
        self.h[pos:pos] = b

    def save(self, base):
        H = self.get('TotalHeaderSize')
        x = bytearray(); eo = self.get('ExportOffset')
        for e in self.exports:
            off = H + len(x); x += e['blob']
            struct.pack_into('<qq', self.h, eo + e['entry'] + 28, len(e['blob']), off)
        x += self.x_tail
        self.put('BulkDataStartOffset', H + len(x) - len(self.x_tail))
        open(base + '.uasset', 'wb').write(self.h)
        open(base + '.uexp', 'wb').write(x)
