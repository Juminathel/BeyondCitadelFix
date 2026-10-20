# Cooked UE4.25 UStruct/UFunction export layout: tagged props, children, FField props, script.
import struct

def skip_tags(p, d, q):
    """Skip a tagged-property block; returns offset after 'None'."""
    while True:
        ni, nn = struct.unpack_from('<ii', d, q); name = p.nm(ni, nn)
        if name == 'None': return q + 8
        ti, tn = struct.unpack_from('<ii', d, q + 8); typ = p.nm(ti, tn)
        sz, = struct.unpack_from('<i', d, q + 16)
        vo = q + 24
        if typ == 'StructProperty': vo += 8 + 16
        elif typ in ('ByteProperty', 'EnumProperty'): vo += 8
        elif typ == 'ArrayProperty' or typ == 'SetProperty': vo += 8
        elif typ == 'MapProperty': vo += 16
        elif typ == 'BoolProperty': vo += 1
        g = d[vo]; vo += 1
        if g: vo += 16
        q = vo + (0 if typ == 'BoolProperty' else sz)

def read_ffield(p, d, q):
    """Returns (dict, next_offset). Starts at the type FName."""
    ti, tn = struct.unpack_from('<ii', d, q); typ = p.nm(ti, tn); q += 8
    st = q
    ni, nn = struct.unpack_from('<ii', d, q); q += 8
    flags, = struct.unpack_from('<I', d, q); q += 4
    arraydim, elsize = struct.unpack_from('<ii', d, q); q += 8
    pflags, = struct.unpack_from('<Q', d, q); q += 8
    q += 2 + 8 + 1          # RepIndex, RepNotifyFunc, BlueprintReplicationCondition
    f = dict(type=typ, name=p.nm(ni, nn), name_idx=(ni, nn), flags=flags,
             elsize=elsize, pflags=pflags, start=st - 8)
    if typ in ('ObjectProperty', 'WeakObjectProperty', 'LazyObjectProperty',
               'SoftObjectProperty', 'StructProperty', 'ByteProperty',
               'DelegateProperty', 'MulticastDelegateProperty',
               'MulticastInlineDelegateProperty', 'MulticastSparseDelegateProperty',
               'InterfaceProperty'):
        f['ref'], = struct.unpack_from('<i', d, q); q += 4
    elif typ in ('ClassProperty', 'SoftClassProperty'):
        f['ref'], f['meta'] = struct.unpack_from('<ii', d, q); q += 8
    elif typ == 'BoolProperty':
        q += 6
    elif typ == 'EnumProperty':
        f['ref'], = struct.unpack_from('<i', d, q); q += 4
        f['inner'], q = read_ffield(p, d, q)
    elif typ in ('ArrayProperty', 'SetProperty'):
        f['inner'], q = read_ffield(p, d, q)
    elif typ == 'MapProperty':
        f['key'], q = read_ffield(p, d, q)
        f['value'], q = read_ffield(p, d, q)
    elif typ in ('IntProperty', 'FloatProperty', 'StrProperty', 'NameProperty',
                 'TextProperty', 'Int64Property', 'UInt32Property', 'UInt64Property',
                 'Int16Property', 'UInt16Property', 'Int8Property', 'DoubleProperty',
                 'FieldPathProperty'):
        if typ == 'FieldPathProperty':
            f['ref'], = struct.unpack_from('<Q', d, q)[0:1]; q += 8  # FName class
    else:
        raise ValueError('unknown FField type ' + typ)
    f['end'] = q
    return f, q

def parse_struct(p, d, q=0):
    """Parse a UStruct-derived export blob d. Returns dict with offsets."""
    r = {}
    q = skip_tags(p, d, q)
    r['next'], = struct.unpack_from('<i', d, q); q += 4      # UField::Next
    r['super'], = struct.unpack_from('<i', d, q); q += 4
    n, = struct.unpack_from('<i', d, q); q += 4
    r['children'] = list(struct.unpack_from('<%di' % n, d, q)); q += 4 * n
    r['props_off'] = q
    n, = struct.unpack_from('<i', d, q); q += 4
    props = []
    for _ in range(n):
        f, q = read_ffield(p, d, q); props.append(f)
    r['props'] = props
    r['script_hdr'] = q
    r['bc_mem'], r['bc_disk'] = struct.unpack_from('<ii', d, q); q += 8
    r['script_off'] = q
    r['script'] = d[q:q + r['bc_disk']]; q += r['bc_disk']
    r['tail_off'] = q
    return r
