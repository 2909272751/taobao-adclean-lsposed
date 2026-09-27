#!/usr/bin/env python3
"""Dump every *defined* class (class_def_item) from an APK's classes*.dex.

Unlike the string table, class_defs are the authoritative set of classes the
runtime can actually load.  One pass -> a text file, then grep it freely.
"""
import struct
import sys
import zipfile
from pathlib import Path


def uleb128(buf, off):
    r = 0
    s = 0
    while True:
        b = buf[off]
        off += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            return r, off
        s += 7


def get_string(buf, string_ids_off, idx):
    off = struct.unpack_from('<I', buf, string_ids_off + idx * 4)[0]
    n, p = uleb128(buf, off)
    return buf[p:p + n].decode('utf-8', 'replace')


def class_defs(buf):
    if buf[:4] != b'dex\n':
        return
    # header: string_ids_size@0x38 off@0x3C, type_ids_size@0x40 off@0x44,
    #         class_defs_size@0x60 off@0x64  (class_idx is a *type_ids* index)
    string_ids_size, string_ids_off = struct.unpack_from('<II', buf, 0x38)
    type_ids_size, type_ids_off = struct.unpack_from('<II', buf, 0x40)
    class_defs_size, class_defs_off = struct.unpack_from('<II', buf, 0x60)
    for i in range(class_defs_size):
        class_idx, access, super_idx = struct.unpack_from('<III', buf, class_defs_off + i * 32)
        try:
            string_idx = struct.unpack_from('<I', buf, type_ids_off + class_idx * 4)[0]
            yield get_string(buf, string_ids_off, string_idx), access
        except Exception:
            continue


def iter_dex(path):
    if path.suffix.lower() == '.dex':
        yield path.name, path.read_bytes()
        return
    with zipfile.ZipFile(path) as z:
        for n in sorted(x for x in z.namelist() if x.endswith('.dex')):
            yield n, z.read(n)


def main():
    apk = Path(sys.argv[1])
    out = Path(sys.argv[2])
    n = 0
    with out.open('w', encoding='utf-8') as fh:
        for dexname, buf in iter_dex(apk):
            for desc, access in class_defs(buf):
                fh.write(f'{dexname}\t{access:#010x}\t{desc}\n')
                n += 1
    print(f'{n} class_defs -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
