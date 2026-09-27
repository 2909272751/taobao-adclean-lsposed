#!/usr/bin/env python3
"""List method_ids in an APK whose *name* matches a regex, with owner class.

Usage: python tools/dex_methods.py <apk> <regex>
"""
import importlib.util
import re
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('dc', Path(__file__).with_name('dex_callers.py'))
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)


def main():
    apk = Path(sys.argv[1])
    r = re.compile(sys.argv[2])
    seen = set()
    n = 0
    for dex in dc.iter_dex(apk):
        if dex.magic[:4] != b'dex\n':
            continue
        for i in range(dex.method_ids_size):
            cls, name, ret, params = dex.method(i)
            if not r.match(name):
                continue
            key = (cls, name)
            if key in seen:
                continue
            seen.add(key)
            n += 1
            print(f'{dex.name}\t{cls}#{name}(' + ''.join(params) + f'){ret}')
    print(f'# {n} distinct', file=sys.stderr)


if __name__ == '__main__':
    main()
