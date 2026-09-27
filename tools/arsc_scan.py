#!/usr/bin/env python3
"""Read-only resources.arsc scanner: list resource entry names (id/layout/drawable/...)
and their resource ids, filtered by a regex.

Dependency-free. `jadx -r` skips resources, so this is the authoritative way to get
resource *entry names* (the thing to hide UI by, per the LSPosed "hide by resource id"
practice). Prints: 0xRRTTEEEE  <type>/<name>

Usage:
  python arsc_scan.py app.apk --name-re '(^|_)ad(_|$)|advert|splash'
  python arsc_scan.py app.apk --type id --name-re 'ad' --limit 200
"""
import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

RES_STRING_POOL = 0x0001
RES_TABLE = 0x0002
RES_TABLE_PACKAGE = 0x0200
RES_TABLE_TYPE = 0x0201


def parse_string_pool(buf, off):
    """return (strings, end_offset) for a RES_STRING_POOL chunk at off."""
    typ, header_size, size = struct.unpack_from('<HHI', buf, off)
    assert typ == RES_STRING_POOL, hex(typ)
    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from(
        '<IIIII', buf, off + 8)
    utf8 = (flags & (1 << 8)) != 0
    offsets = struct.unpack_from('<%dI' % string_count, buf, off + header_size)
    base = off + strings_start
    out = []
    for o in offsets:
        p = base + o
        if utf8:
            _n, p = _uleb(buf, p)          # utf16 length
            n, p = _uleb(buf, p)           # utf8 byte length
            out.append(buf[p:p + n].decode('utf-8', 'replace'))
        else:
            n = struct.unpack_from('<H', buf, p)[0]
            p += 2
            out.append(buf[p:p + n * 2].decode('utf-16-le', 'replace'))
    return out, off + size


def _uleb(buf, off):
    result = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def iter_entries(buf, pkg_off, pkg_size):
    """yield (res_id, type_name, entry_name) for one RES_TABLE_PACKAGE chunk."""
    typ, header_size, size = struct.unpack_from('<HHI', buf, pkg_off)
    pkg_id = struct.unpack_from('<I', buf, pkg_off + 8)[0]
    # ResTable_package: chunk header(8) + id(4) + name[128] u16 (256) + typeStrings ...
    type_strings_off, _last_type, key_strings_off, _last_key = struct.unpack_from(
        '<IIII', buf, pkg_off + 8 + 4 + 256)
    type_strings, _ = parse_string_pool(buf, pkg_off + type_strings_off)
    key_strings, _ = parse_string_pool(buf, pkg_off + key_strings_off)

    off = pkg_off + header_size
    end = pkg_off + size
    while off < end:
        ctype, cheader, csize = struct.unpack_from('<HHI', buf, off)
        if csize == 0:
            break
        if ctype == RES_TABLE_TYPE:
            type_id = buf[off + 8]
            flags = buf[off + 9]
            entry_count, entries_start = struct.unpack_from('<II', buf, off + 12)
            # config struct follows; its size is the first u32 after entriesStart
            cfg_size = struct.unpack_from('<I', buf, off + 20)[0]
            offsets_base = off + 20 + cfg_size
            tname = type_strings[type_id - 1] if 0 < type_id <= len(type_strings) else f'type{type_id}'
            entries_base = off + entries_start
            sparse = (flags & 0x01) != 0
            for i in range(entry_count):
                if sparse:
                    # sparse entries: u16 idx, u16 offset/4, u16 size, u16 flags
                    _idx, eo4, _sz, _fl = struct.unpack_from('<HHHH', buf, offsets_base + i * 8)
                    eoff = eo4 * 4
                    idx = _idx
                else:
                    eoff = struct.unpack_from('<I', buf, offsets_base + i * 4)[0]
                    idx = i
                if eoff == 0xFFFFFFFF:
                    continue
                # ResTable_entry: u16 size, u16 flags, u32 key_index
                key_index = struct.unpack_from('<I', buf, entries_base + eoff + 4)[0]
                if key_index >= len(key_strings):
                    continue
                res_id = (pkg_id << 24) | (type_id << 16) | idx
                yield res_id, tname, key_strings[key_index]
        off += csize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--name-re', default='.')
    ap.add_argument('--type')
    ap.add_argument('--limit', type=int, default=400)
    args = ap.parse_args()

    with zipfile.ZipFile(Path(args.target)) as z:
        data = z.read('resources.arsc')
    rx = re.compile(args.name_re)
    typ, header_size, size = struct.unpack_from('<HHI', data, 0)
    assert typ == RES_TABLE, hex(typ)
    pkg_count = struct.unpack_from('<I', data, 8)[0]
    off = header_size
    n = 0
    seen = set()
    while off < len(data):
        ctype, cheader, csize = struct.unpack_from('<HHI', data, off)
        if csize == 0:
            break
        if ctype == RES_TABLE_PACKAGE:
            for res_id, tname, ename in iter_entries(data, off, csize):
                if args.type and tname != args.type:
                    continue
                if not rx.search(ename):
                    continue
                key = (res_id, tname, ename)
                if key in seen:
                    continue
                seen.add(key)
                print(f'0x{res_id:08x}\t{tname}/{ename}')
                n += 1
                if n >= args.limit:
                    print('... truncated', file=sys.stderr)
                    return
        off += csize
    print(f'# {n} entries matched', file=sys.stderr)


if __name__ == '__main__':
    main()
