# FNameEntrySerialized hashes (UE4.25): NonCasePreservingHash, CasePreservingHash (low 16 bits)
import struct

def _tables():
    dep = []
    for i in range(256):
        c = i << 24
        for _ in range(8): c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        dep.append(c)
    sb8 = []
    for i in range(256):
        c = i
        for _ in range(8): c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        sb8.append(c)
    return dep, sb8
DEP, SB8 = _tables()

def strihash_deprecated(s):
    h = 0
    for ch in s.encode('latin-1'):
        if 97 <= ch <= 122: ch -= 32
        h = ((h >> 8) & 0x00FFFFFF) ^ DEP[(h ^ ch) & 0xFF]
    return h

def strcrc32(s):
    crc = 0xFFFFFFFF
    for ch in s.encode('latin-1'):
        for _ in range(4):
            crc = (crc >> 8) ^ SB8[(crc ^ ch) & 0xFF]; ch >>= 8
    return ~crc & 0xFFFFFFFF

def name_hashes(s):
    return struct.pack('<HH', strihash_deprecated(s) & 0xFFFF, strcrc32(s) & 0xFFFF)
