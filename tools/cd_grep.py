#!/usr/bin/env python3
"""Categorised grep over a dex class_defs dump (from tools/dex_classdefs.py).

Usage: python tools/cd_grep.py <classdefs.txt> [pattern ...]
Patterns are Python regexes matched against the full descriptor.
"""
import re
import sys
from pathlib import Path

def main():
    f = Path(sys.argv[1])
    pats = sys.argv[2:]
    res = [re.compile(p) for p in pats]
    with f.open(encoding='utf-8') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            desc = parts[2]
            for p, raw in zip(res, pats):
                if p.search(desc):
                    print(f'{raw}\t{parts[0]}\t{desc}')
                    break

if __name__ == '__main__':
    main()
