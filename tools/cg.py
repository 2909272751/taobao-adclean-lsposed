#!/usr/bin/env python3
"""Query the caller index produced by tools/dex_callers.py.

Usage:
  python tools/cg.py callgraph.tsv callers <regex> [n]     # who calls a callee matching regex
  python tools/cg.py callgraph.tsv callees <regex> [n]     # what a caller matching regex calls
  python tools/cg.py callgraph.tsv both    <regex> [n]
"""
import re
import sys


def main():
    path, mode, pat = sys.argv[1], sys.argv[2], sys.argv[3]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    r = re.compile(pat)
    callers, callees = [], []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) != 2:
                continue
            caller, callee = p
            if mode in ('callers', 'both') and r.search(callee):
                callers.append(line.rstrip('\n'))
            if mode in ('callees', 'both') and r.search(caller):
                callees.append(line.rstrip('\n'))
    if mode in ('callers', 'both'):
        print(f'### CALLERS ({len(callers)}) of /{pat}/')
        for h in callers[:n]:
            print('  ' + h)
    if mode in ('callees', 'both'):
        print(f'### CALLEES ({len(callees)}) of /{pat}/')
        for h in callees[:n]:
            print('  ' + h)


if __name__ == '__main__':
    main()
