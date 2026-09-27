#!/usr/bin/env python3
"""Fast, dependency-free dex string/class scanner.

Reads every classes*.dex inside an APK (or a raw .dex file) and reports
class descriptors / string constants matching the supplied regexes.

Walks the dex string-id table directly; enough to enumerate class names and
string literals in seconds even for 100MB+ APKs, no jadx/dexdump required.
"""
import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path


def _uleb128(buf, off):
    result = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def dex_strings(buf):
    if buf[:4] != b'dex\n':
        return []
    string_ids_size, string_ids_off = struct.unpack_from('<II', buf, 0x38)
    if string_ids_size == 0 or string_ids_off == 0:
        return []
    out = []
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', buf, string_ids_off + i * 4)[0]
        if off == 0 or off >= len(buf):
            continue
        try:
            _n, p = _uleb128(buf, off)
        except IndexError:
            continue
        end = buf.find(b'\x00', p)
        if end < 0:
            end = len(buf)
        out.append(buf[p:end].decode('utf-8', 'replace'))
    return out


def iter_dex(path):
    if path.suffix.lower() == '.dex':
        yield path.name, path.read_bytes()
        return
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.endswith('.dex'))
        for n in names:
            yield n, z.read(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--class-re', action='append', default=[])
    ap.add_argument('--string-re', action='append', default=[])
    ap.add_argument('--limit', type=int, default=300)
    args = ap.parse_args()

    cres = [re.compile(p) for p in args.class_re]
    sres = [re.compile(p) for p in args.string_re]
    target = Path(args.target)

    classes = set()
    strs = set()
    total = 0
    for _dexname, buf in iter_dex(target):
        s = dex_strings(buf)
        total += len(s)
        for x in s:
            if len(x) > 2 and x[0] == 'L' and x.endswith(';'):
                classes.add(x)
            else:
                strs.add(x)

    print(f'# scanned {target.name}: {total} strings, {len(classes)} class descriptors',
          file=sys.stderr)

    n = 0
    for r in cres:
        for c in sorted(classes):
            if r.search(c):
                print(f'cls\t{r.pattern}\t{c}')
                n += 1
                if n >= args.limit:
                    print('... truncated', file=sys.stderr)
                    return
    for r in sres:
        for c in sorted(strs):
            if r.search(c):
                print(f'str\t{r.pattern}\t{c}')
                n += 1
                if n >= args.limit:
                    print('... truncated', file=sys.stderr)
                    return
    print(f'# {n} hits', file=sys.stderr)


if __name__ == '__main__':
    main()
